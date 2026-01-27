"""LLDB Client for subprocess communication with LLDB service

This module implements a client that communicates with the standalone LLDB service
via JSON-RPC over stdin/stdout. It manages the subprocess lifecycle, handles crashes
with automatic restart, and provides the same API as LLDBDebuggerManager.
"""

import asyncio
import json
import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .config import AppleDBConfig
from .models import DebuggerState, ProcessInfo
from .utils.errors import (
    FrameworkLoadError,
    InvalidStateError,
    LLDBError,
    ProcessNotAttachedError,
    ProcessNotFoundError,
)

logger = logging.getLogger(__name__)


class LLDBClient:
    """Singleton client for LLDB subprocess communication

    This class manages communication with the LLDB service subprocess via JSON-RPC.
    It provides automatic crash recovery, request timeout handling, and a clean API
    that mirrors LLDBDebuggerManager.

    Architecture:
        Claude Code → MCP Server (Python 3.10+) → LLDBClient → [subprocess] → LLDB Service (Python 3.9) → LLDB
    """

    # Singleton pattern
    _instance: Optional["LLDBClient"] = None
    _lock = asyncio.Lock()

    def __new__(cls) -> "LLDBClient":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        # Only initialize once
        if hasattr(self, "_initialized"):
            return

        # Subprocess management
        self._process: Optional[asyncio.subprocess.Process] = None
        self._config: Optional[AppleDBConfig] = None
        self._ready: Optional[asyncio.Event] = None

        # JSON-RPC communication
        self._request_id_counter: int = 0
        self._pending_requests: Dict[int, Tuple[asyncio.Future, float]] = {}
        self._reader_task: Optional[asyncio.Task] = None
        self._stderr_task: Optional[asyncio.Task] = None
        self._monitor_task: Optional[asyncio.Task] = None
        self._reset_task: Optional[asyncio.Task] = None
        self._request_timeout: float = 30.0

        # Crash recovery and restart coordination
        self._restart_count: int = 0
        self._max_restarts: int = 3
        self._last_restart: float = 0.0
        self._restarting: bool = False
        self._restart_lock: Optional[asyncio.Lock] = None

        self._initialized = True

    @classmethod
    def get_instance(cls) -> "LLDBClient":
        """Get the singleton instance

        Returns:
            The singleton LLDBClient instance
        """
        return cls()

    async def initialize(self, config: AppleDBConfig) -> None:
        """Initialize LLDB client and start subprocess

        Args:
            config: Configuration object

        Raises:
            RuntimeError: If Python 3.9+ not found or subprocess fails to start
        """
        logger.info("Initializing LLDB client")

        # Create new event and lock for this event loop
        self._ready = asyncio.Event()
        self._restart_lock = asyncio.Lock()

        # Store config for use in restarts
        self._config = config
        self._request_timeout = config.service_request_timeout
        self._max_restarts = config.service_max_restarts

        # Start subprocess
        await self._start_subprocess()
        await self._wait_for_ready()

        # Send initialize RPC to configure service
        config_dict = self._config_to_dict(config)
        await self._call("initialize", {"config": config_dict})

        # Start restart counter reset task
        self._last_restart = asyncio.get_event_loop().time()
        self._reset_task = asyncio.create_task(self._reset_restart_counter_after_stable_period())

        logger.info("LLDB client initialized successfully")

    def _config_to_dict(self, config: AppleDBConfig) -> dict:
        """Convert AppleDBConfig to dict for service initialization

        Args:
            config: Configuration object

        Returns:
            Dictionary with config fields for LLDB service
        """
        return {
            "lldb_timeout": config.lldb_timeout,
            "log_level": config.log_level,
            "max_backtrace_frames": config.max_backtrace_frames,
            "max_variable_depth": config.max_variable_depth,
        }

    def _find_python_path(self, config: AppleDBConfig) -> str:
        """Find Python 3.9+ interpreter

        Args:
            config: Configuration object

        Returns:
            Path to Python 3.9+ interpreter

        Raises:
            RuntimeError: If no suitable Python found
        """
        # 1. Use explicit config if set
        if config.python_path != "python3":
            python_path = config.python_path
            if not self._check_python_version(python_path):
                raise RuntimeError(
                    f"Python at {python_path} is not version 3.9+"
                )
            return python_path

        # 2. Try python3.9
        if shutil.which("python3.9"):
            return "python3.9"

        # 3. Try python3 (check version >= 3.9)
        python3 = shutil.which("python3")
        if python3 and self._check_python_version(python3):
            return python3

        raise RuntimeError(
            "No Python 3.9+ found. Install Python 3.9+ or set "
            "APPLEDB_PYTHON_PATH environment variable."
        )

    def _check_python_version(self, python_path: str) -> bool:
        """Check if Python version is >= 3.9

        Args:
            python_path: Path to Python interpreter

        Returns:
            True if version >= 3.9, False otherwise
        """
        try:
            result = subprocess.run(
                [python_path, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            # Parse "Python 3.9.6" -> (3, 9, 6)
            version_str = result.stdout.strip().split()[1]
            major, minor, *_ = map(int, version_str.split("."))
            return (major, minor) >= (3, 9)
        except Exception as e:
            logger.warning(f"Failed to check Python version: {e}")
            return False

    async def _start_subprocess(self) -> None:
        """Start LLDB service subprocess with task cleanup"""
        logger.info("Starting LLDB service subprocess")

        # Step 1: Cancel and await old tasks
        for task in [self._reader_task, self._stderr_task, self._monitor_task, self._reset_task]:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        # Step 2: Kill old process if exists
        if self._process and self._process.returncode is None:
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                logger.warning("Process didn't terminate, killing forcefully")
                self._process.kill()
                await self._process.wait()

        # Step 3: Start new process
        python_path = self._find_python_path(self._config)
        env = os.environ.copy()
        # Ensure src/ is in PYTHONPATH for lldb_service import
        src_path = str(Path(__file__).parent.parent)
        pythonpath = env.get("PYTHONPATH", "")
        if pythonpath:
            env["PYTHONPATH"] = f"{src_path}:{pythonpath}"
        else:
            env["PYTHONPATH"] = src_path

        self._ready.clear()  # Clear ready event before starting

        self._process = await asyncio.create_subprocess_exec(
            python_path,
            "-m",
            "lldb_service",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            cwd=src_path,
        )

        # Step 4: Start reader tasks with error handling
        self._reader_task = asyncio.create_task(self._read_responses())
        self._stderr_task = asyncio.create_task(self._read_stderr())
        self._monitor_task = asyncio.create_task(self._monitor_process())

        logger.info(f"Started LLDB service subprocess (PID: {self._process.pid})")

    async def _wait_for_ready(self, timeout: float = 5.0) -> None:
        """Wait for ready notification from service

        Args:
            timeout: Timeout in seconds

        Raises:
            RuntimeError: If service doesn't send ready signal or exits
        """
        try:
            await asyncio.wait_for(self._ready.wait(), timeout=timeout)
            logger.info("LLDB service ready")
        except asyncio.TimeoutError:
            # Check if subprocess is still alive
            if self._process.returncode is not None:
                raise RuntimeError(
                    f"LLDB service exited during startup (code: {self._process.returncode})"
                )
            # Subprocess alive but no ready signal
            raise RuntimeError(
                "LLDB service failed to send ready signal within 5 seconds"
            )

    async def _read_responses(self) -> None:
        """Background task to read stdout responses"""
        try:
            while self._process and self._process.returncode is None:
                line = await self._process.stdout.readline()
                if not line:  # EOF - subprocess died
                    logger.error("LLDB service died (stdout closed)")
                    # Signal restart needed
                    asyncio.create_task(self._handle_subprocess_death())
                    break

                try:
                    response = json.loads(line.decode().strip())
                    await self._handle_response(response)
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse JSON response: {e}, line: {line}")
                    continue

        except Exception as e:
            logger.error(f"Reader task crashed: {e}", exc_info=True)

    async def _read_stderr(self) -> None:
        """Background task to read stderr logs"""
        try:
            while self._process and self._process.returncode is None:
                line = await self._process.stderr.readline()
                if not line:
                    break
                log_msg = line.decode().strip()
                if log_msg:
                    logger.info(f"[LLDB-SERVICE] {log_msg}")
        except Exception as e:
            logger.error(f"Stderr reader failed: {e}")

    async def _monitor_process(self) -> None:
        """Monitor subprocess and trigger restart on unexpected exit

        This task waits for the process to exit and triggers a restart
        if it exits unexpectedly after successful initialization. This
        provides faster crash detection than relying on EOF detection.
        """
        try:
            returncode = await self._process.wait()
            # Only trigger restart if process died after successful initialization
            if returncode != 0 and self._ready.is_set():
                logger.error(f"LLDB service exited unexpectedly (code: {returncode})")
                await self._handle_subprocess_death()
        except Exception as e:
            logger.error(f"Process monitor failed: {e}")

    async def _reset_restart_counter_after_stable_period(self) -> None:
        """Reset restart counter after stable uptime period

        This task monitors service uptime and resets the restart counter
        after the service has been stable for the configured period. This
        prevents permanent failure after transient crashes spread over time.
        """
        try:
            while True:
                await asyncio.sleep(60)  # Check every minute
                if self._ready.is_set() and self._restart_count > 0:
                    uptime = asyncio.get_event_loop().time() - self._last_restart
                    reset_time = self._config.service_restart_reset_time
                    if uptime > reset_time:
                        logger.info(
                            f"Resetting restart counter from {self._restart_count} "
                            f"after {uptime:.0f}s stable operation"
                        )
                        self._restart_count = 0
        except asyncio.CancelledError:
            pass  # Expected on shutdown
        except Exception as e:
            logger.error(f"Restart counter reset task failed: {e}")

    async def _handle_response(self, response: dict) -> None:
        """Handle JSON-RPC response by resolving corresponding future

        Args:
            response: JSON-RPC response dictionary
        """
        # Check if it's a notification (no id field)
        if "id" not in response:
            await self._handle_notification(response)
            return

        request_id = response["id"]
        future_tuple = self._pending_requests.pop(request_id, None)

        if not future_tuple:
            logger.warning(f"Received response for unknown request ID: {request_id}")
            return

        future, timestamp = future_tuple

        if future.done():
            logger.warning(f"Future already done for request ID: {request_id}")
            return

        # Check for error response
        if "error" in response:
            exception = self._map_error_to_exception(response["error"])
            future.set_exception(exception)
        else:
            future.set_result(response.get("result"))

    async def _handle_notification(self, notification: dict) -> None:
        """Handle server-sent notifications

        Args:
            notification: JSON-RPC notification dictionary
        """
        method = notification.get("method")

        if method == "ready":
            logger.debug("Received ready notification from LLDB service")
            self._ready.set()
        else:
            logger.warning(f"Unknown notification: {method}")

    def _map_error_to_exception(self, error: Dict) -> Exception:
        """Map JSON-RPC error codes to Python exceptions

        Args:
            error: Error dictionary with code and message

        Returns:
            Appropriate exception instance
        """
        code = error.get("code", -32603)
        message = error.get("message", "Unknown error")

        # Map error codes to exceptions
        error_map = {
            -32000: LLDBError,
            -32001: ProcessNotAttachedError,
            -32002: InvalidStateError,
            -32003: ProcessNotFoundError,
            -32004: FrameworkLoadError,
            -32602: ValueError,
        }

        exception_class = error_map.get(code, RuntimeError)
        return exception_class(message)

    async def _call(
        self, method: str, params: Dict, timeout: Optional[float] = None
    ) -> Any:
        """Send JSON-RPC request and await response with timeout

        Args:
            method: RPC method name
            params: Method parameters
            timeout: Optional timeout override

        Returns:
            Result from service

        Raises:
            RuntimeError: If service not ready or timeout
        """
        if not self._ready.is_set():
            raise RuntimeError("LLDB service not ready")

        timeout = timeout or self._request_timeout
        request_id = self._request_id_counter
        self._request_id_counter += 1

        future: asyncio.Future = asyncio.Future()
        timestamp = asyncio.get_event_loop().time()
        self._pending_requests[request_id] = (future, timestamp)

        try:
            # Send request
            request = {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": method,
                "params": params,
            }
            line = json.dumps(request) + "\n"
            try:
                self._process.stdin.write(line.encode())
                await self._process.stdin.drain()
            except BrokenPipeError:
                logger.error("Subprocess stdin closed unexpectedly")
                self._pending_requests.pop(request_id, None)
                raise RuntimeError("LLDB service died during request")

            # Wait for response with timeout
            result = await asyncio.wait_for(future, timeout=timeout)
            self._pending_requests.pop(request_id, None)  # Cleanup on success
            return result

        except asyncio.TimeoutError:
            self._pending_requests.pop(request_id, None)
            raise RuntimeError(f"RPC call '{method}' timed out after {timeout}s")

    async def _handle_subprocess_death(self) -> None:
        """Coordinate restart to prevent concurrent restarts"""
        if not self._restart_lock:
            logger.error("Restart lock not initialized")
            return

        async with self._restart_lock:
            if not self._restarting:
                self._restarting = True
                try:
                    await self._restart_subprocess()
                finally:
                    self._restarting = False

    async def _restart_subprocess(self) -> None:
        """Restart subprocess with exponential backoff

        Raises:
            RuntimeError: If max restarts exceeded
        """
        # Clean up pending requests first
        self._cleanup_pending_requests(
            "LLDB service crashed - debugging session lost"
        )

        self._restart_count += 1

        if self._restart_count > self._max_restarts:
            raise RuntimeError(
                f"LLDB service crashed repeatedly ({self._max_restarts}+ times)"
            )

        # Exponential backoff: 1s, 2s, 4s
        backoff = self._config.service_restart_backoff * (
            2 ** (self._restart_count - 1)
        )
        logger.warning(
            f"Restarting LLDB service in {backoff}s "
            f"(attempt {self._restart_count}/{self._max_restarts})"
        )
        await asyncio.sleep(backoff)

        await self._start_subprocess()
        await self._wait_for_ready()

        # Re-initialize service with config
        config_dict = self._config_to_dict(self._config)
        await self._call("initialize", {"config": config_dict})

        # Update last restart timestamp for restart counter reset
        self._last_restart = asyncio.get_event_loop().time()

        logger.info("LLDB service restarted successfully")

    def _cleanup_pending_requests(self, error_msg: str) -> None:
        """Reject all pending requests with error

        Args:
            error_msg: Error message to set on futures
        """
        count = len(self._pending_requests)
        for request_id, (future, timestamp) in list(self._pending_requests.items()):
            if not future.done():
                future.set_exception(RuntimeError(error_msg))
        self._pending_requests.clear()
        logger.warning(f"Rejected {count} pending requests due to crash")

    async def cleanup(self) -> None:
        """Clean up LLDB service subprocess"""
        logger.info("Cleaning up LLDB service")

        # Step 1: Send cleanup RPC with short timeout
        try:
            await asyncio.wait_for(self._call("cleanup", {}), timeout=5.0)
        except Exception as e:
            logger.warning(f"Cleanup RPC failed: {e}")

        # Step 2: Cancel background tasks
        for task in [self._reader_task, self._stderr_task, self._monitor_task, self._reset_task]:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        # Step 3: Terminate process gracefully
        if self._process and self._process.returncode is None:
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                logger.warning("Process didn't terminate, killing forcefully")
                self._process.kill()
                await self._process.wait()

        logger.info("LLDB service cleanup complete")

    # API Methods that mirror LLDBDebuggerManager

    async def attach_process_by_pid(self, pid: int) -> ProcessInfo:
        """Attach to process by PID

        Args:
            pid: Process ID

        Returns:
            ProcessInfo with process details

        Raises:
            ProcessNotFoundError: If process not found
            InvalidStateError: If already attached
            LLDBError: If attach fails
        """
        result = await self._call("attach_process", {"pid": pid})
        return ProcessInfo(**result)

    async def attach_process_by_name(self, name: str) -> ProcessInfo:
        """Attach to process by name

        Args:
            name: Process name

        Returns:
            ProcessInfo with process details

        Raises:
            ProcessNotFoundError: If process not found
            InvalidStateError: If already attached
            LLDBError: If attach fails
        """
        result = await self._call("attach_process", {"name": name})
        return ProcessInfo(**result)

    async def launch_app(
        self,
        executable: str,
        args: Optional[List[str]] = None,
        env: Optional[Dict[str, str]] = None,
        stop_at_entry: bool = True,
    ) -> ProcessInfo:
        """Launch application for debugging

        Args:
            executable: Path to executable
            args: Command-line arguments
            env: Environment variables
            stop_at_entry: Stop at entry point

        Returns:
            ProcessInfo with process details

        Raises:
            InvalidStateError: If already attached
            LLDBError: If launch fails
        """
        params = {
            "executable": executable,
            "args": args or [],
            "env": env or {},
            "stop_at_entry": stop_at_entry,
        }
        result = await self._call("launch_app", params)
        return ProcessInfo(**result)

    async def detach(self, kill: bool = False) -> None:
        """Detach from process

        Args:
            kill: Kill process if True

        Raises:
            ProcessNotAttachedError: If not attached
        """
        await self._call("detach", {"kill": kill})

    async def continue_execution(self) -> str:
        """Continue process execution

        Returns:
            Status message

        Raises:
            ProcessNotAttachedError: If not attached
        """
        result = await self._call("continue_execution", {})
        return result.get("state", "running") if isinstance(result, dict) else result

    async def pause_execution(self) -> str:
        """Pause process execution

        Returns:
            Status message

        Raises:
            ProcessNotAttachedError: If not attached
        """
        result = await self._call("pause_execution", {})
        return result.get("description", "paused") if isinstance(result, dict) else result

    async def step_over(self, thread_id: Optional[int] = None) -> str:
        """Step over current line

        Args:
            thread_id: Optional thread ID

        Returns:
            Status message

        Raises:
            ProcessNotAttachedError: If not attached
        """
        params = {"thread_id": thread_id} if thread_id is not None else {}
        result = await self._call("step_over", params)
        return result.get("location", "stepped") if isinstance(result, dict) else result

    async def step_into(self, thread_id: Optional[int] = None) -> str:
        """Step into function

        Args:
            thread_id: Optional thread ID

        Returns:
            Status message

        Raises:
            ProcessNotAttachedError: If not attached
        """
        params = {"thread_id": thread_id} if thread_id is not None else {}
        result = await self._call("step_into", params)
        return result.get("location", "stepped") if isinstance(result, dict) else result

    async def step_out(self, thread_id: Optional[int] = None) -> str:
        """Step out of function

        Args:
            thread_id: Optional thread ID

        Returns:
            Status message

        Raises:
            ProcessNotAttachedError: If not attached
        """
        params = {"thread_id": thread_id} if thread_id is not None else {}
        result = await self._call("step_out", params)
        return result.get("location", "stepped") if isinstance(result, dict) else result

    async def evaluate_expression(
        self,
        expression: str,
        language: Optional[str] = None,
        frame_index: int = 0,
        thread_id: Optional[int] = None,
    ) -> dict:
        """Evaluate expression in context

        Args:
            expression: Expression to evaluate
            language: Optional language hint ("swift", "objc", "c++", "c")
            frame_index: Stack frame index
            thread_id: Optional thread ID

        Returns:
            Evaluation result dictionary

        Raises:
            ProcessNotAttachedError: If not attached
        """
        params = {
            "expression": expression,
            "frame_index": frame_index,
        }
        if language is not None:
            params["language"] = language
        if thread_id is not None:
            params["thread_id"] = thread_id
        result = await self._call("evaluate_expression", params)
        return result

    async def get_backtrace(
        self,
        thread_id: Optional[int] = None,
        max_frames: Optional[int] = None,
    ) -> List[dict]:
        """Get backtrace for thread

        Args:
            thread_id: Optional thread ID
            max_frames: Maximum frames to return

        Returns:
            List of frame dictionaries

        Raises:
            ProcessNotAttachedError: If not attached
        """
        params = {}
        if thread_id is not None:
            params["thread_id"] = thread_id
        if max_frames is not None:
            params["max_frames"] = max_frames
        result = await self._call("get_backtrace", params)
        # Handler returns {"frames": [...]}, extract the list
        return result.get("frames", []) if isinstance(result, dict) else result

    async def get_variables(
        self,
        frame_index: int = 0,
        thread_id: Optional[int] = None,
        max_depth: Optional[int] = None,
    ) -> List[dict]:
        """Get variables for frame

        Args:
            frame_index: Stack frame index
            thread_id: Optional thread ID
            max_depth: Maximum depth for nested variables

        Returns:
            List of variable dictionaries

        Raises:
            ProcessNotAttachedError: If not attached
        """
        params = {"frame_index": frame_index}
        if thread_id is not None:
            params["thread_id"] = thread_id
        if max_depth is not None:
            params["max_depth"] = max_depth
        result = await self._call("get_variables", params)
        # Handler returns {"variables": [...]}, extract the list
        return result.get("variables", []) if isinstance(result, dict) else result

    async def load_framework(
        self,
        framework_path: Optional[str] = None,
        framework_name: Optional[str] = None,
    ) -> dict:
        """Load framework into process

        Args:
            framework_path: Path to framework (mutually exclusive with framework_name)
            framework_name: Named framework to load (mutually exclusive with framework_path)

        Returns:
            Result dictionary with status

        Raises:
            ProcessNotAttachedError: If not attached
            FrameworkLoadError: If load fails
            ValueError: If neither or both parameters provided
        """
        params = {}
        if framework_path is not None:
            params["framework_path"] = framework_path
        if framework_name is not None:
            params["framework_name"] = framework_name
        result = await self._call("load_framework", params)
        return result

    async def get_debugger_state(self) -> DebuggerState:
        """Get current debugger state

        Returns:
            DebuggerState with complete state snapshot
        """
        result = await self._call("get_debugger_state", {})
        return DebuggerState(**result)

    async def ping(self) -> dict:
        """Health check

        Returns:
            Dictionary with status, attached, and state
        """
        # Service returns "pong"
        result = await self._call("ping", {})
        # Get debugger state
        state = await self.get_debugger_state()
        return {
            "status": result,
            "attached": state.attached,
            "state": state.state,
        }
