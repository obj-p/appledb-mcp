"""LLDB debugger singleton manager"""

import asyncio
import logging
from enum import Enum
from typing import Optional, Set

from .config import AppleDBConfig
from .models import ProcessInfo
from .utils.errors import InvalidStateError, LLDBError, ProcessNotAttachedError
from .utils.lldb_helpers import check_lldb_available, get_lldb_path, run_lldb_operation

try:
    import lldb
except ImportError:
    lldb = None  # type: ignore

logger = logging.getLogger(__name__)


class ProcessState(Enum):
    """Process attachment state"""

    DETACHED = "detached"
    ATTACHED_STOPPED = "stopped"
    ATTACHED_RUNNING = "running"


class LLDBDebuggerManager:
    """Singleton manager for LLDB debugger instance

    This class manages a single LLDB debugger instance throughout the server lifecycle.
    It provides thread-safe access to LLDB operations and tracks process state.
    """

    _instance: Optional["LLDBDebuggerManager"] = None
    _lock = asyncio.Lock()

    def __new__(cls) -> "LLDBDebuggerManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        # Only initialize once
        if hasattr(self, "_initialized"):
            return

        self._debugger: Optional[lldb.SBDebugger] = None
        self._state = ProcessState.DETACHED
        self._loaded_frameworks: Set[str] = set()
        self._config: Optional[AppleDBConfig] = None
        self._initialized = True

    @classmethod
    def get_instance(cls) -> "LLDBDebuggerManager":
        """Get the singleton instance

        Returns:
            The singleton LLDBDebuggerManager instance
        """
        return cls()

    def initialize(self, config: AppleDBConfig) -> None:
        """Initialize LLDB debugger (idempotent)

        Args:
            config: Configuration object

        Raises:
            RuntimeError: If LLDB is not available
        """
        if self._debugger is not None:
            logger.debug("LLDB debugger already initialized")
            return

        if not check_lldb_available():
            lldb_path = get_lldb_path()
            error_msg = "LLDB not found. "
            if lldb_path:
                error_msg += f"Add to PYTHONPATH: export PYTHONPATH={lldb_path}:$PYTHONPATH"
            else:
                error_msg += "Install Xcode: xcode-select --install"
            raise RuntimeError(error_msg)

        logger.info("Initializing LLDB debugger")
        lldb.SBDebugger.Initialize()
        self._debugger = lldb.SBDebugger.Create()
        self._debugger.SetAsync(False)  # Synchronous mode for simplicity
        self._config = config
        logger.info("LLDB debugger initialized successfully")

    def get_debugger(self) -> lldb.SBDebugger:
        """Get current debugger instance

        Returns:
            The LLDB SBDebugger instance

        Raises:
            RuntimeError: If debugger not initialized
        """
        if self._debugger is None:
            raise RuntimeError("Debugger not initialized. Call initialize() first.")
        return self._debugger

    def get_target(self) -> lldb.SBTarget:
        """Get currently selected target

        Returns:
            The current SBTarget

        Raises:
            RuntimeError: If no valid target selected
        """
        debugger = self.get_debugger()
        target = debugger.GetSelectedTarget()
        if not target.IsValid():
            raise RuntimeError("No valid target selected")
        return target

    def get_process(self) -> lldb.SBProcess:
        """Get currently attached process

        Returns:
            The current SBProcess

        Raises:
            ProcessNotAttachedError: If no valid process attached
        """
        try:
            target = self.get_target()
        except RuntimeError:
            raise ProcessNotAttachedError("No process attached")

        process = target.GetProcess()
        if not process.IsValid():
            raise ProcessNotAttachedError("No process attached")
        return process

    def is_attached(self) -> bool:
        """Check if attached to a process

        Returns:
            True if attached to a valid process, False otherwise
        """
        return self._state != ProcessState.DETACHED

    def get_state(self) -> ProcessState:
        """Get current process state

        Returns:
            Current ProcessState
        """
        return self._state

    def _set_state(self, state: ProcessState) -> None:
        """Set process state

        Args:
            state: New process state
        """
        logger.debug(f"Process state: {self._state.value} -> {state.value}")
        self._state = state

    async def attach_process_by_pid(self, pid: int) -> ProcessInfo:
        """Attach to a process by PID

        Args:
            pid: Process ID to attach to

        Returns:
            ProcessInfo with details about attached process

        Raises:
            InvalidStateError: If already attached to a process
            LLDBError: If attach operation fails
        """
        async with self._lock:
            if self._state != ProcessState.DETACHED:
                raise InvalidStateError(f"Already attached to a process (state: {self._state.value})")

            debugger = self.get_debugger()

            # Create target and attach
            error = lldb.SBError()
            target = debugger.CreateTarget("")

            if not target.IsValid():
                raise LLDBError("Failed to create target")

            listener = lldb.SBListener("attach-listener")
            process = await run_lldb_operation(
                target.AttachToProcessWithID, listener, pid, error
            )

            if error.Fail() or not process.IsValid():
                error_msg = error.GetCString() if error.Fail() else "Unknown error"
                raise LLDBError(f"Failed to attach to process {pid}: {error_msg}")

            self._set_state(ProcessState.ATTACHED_STOPPED)
            logger.info(f"Attached to process {pid}")

            # Return process info
            return ProcessInfo(
                pid=process.GetProcessID(),
                name=process.GetName() or "",
                state="stopped",
                architecture=target.GetTriple() or "unknown",
            )

    async def attach_process_by_name(self, name: str) -> ProcessInfo:
        """Attach to a process by name

        Args:
            name: Process name to attach to

        Returns:
            ProcessInfo with details about attached process

        Raises:
            InvalidStateError: If already attached to a process
            LLDBError: If attach operation fails
        """
        async with self._lock:
            if self._state != ProcessState.DETACHED:
                raise InvalidStateError(f"Already attached to a process (state: {self._state.value})")

            debugger = self.get_debugger()

            # Create target and attach by name
            error = lldb.SBError()
            target = debugger.CreateTarget("")

            if not target.IsValid():
                raise LLDBError("Failed to create target")

            listener = lldb.SBListener("attach-listener")
            process = await run_lldb_operation(
                target.AttachToProcessWithName, listener, name, False, error
            )

            if error.Fail() or not process.IsValid():
                error_msg = error.GetCString() if error.Fail() else "Unknown error"
                raise LLDBError(f"Failed to attach to process '{name}': {error_msg}")

            self._set_state(ProcessState.ATTACHED_STOPPED)
            logger.info(f"Attached to process '{name}' (PID {process.GetProcessID()})")

            # Return process info
            return ProcessInfo(
                pid=process.GetProcessID(),
                name=process.GetName() or "",
                state="stopped",
                architecture=target.GetTriple() or "unknown",
            )

    async def launch_app(
        self,
        executable: str,
        args: Optional[list[str]] = None,
        env: Optional[dict[str, str]] = None,
        stop_at_entry: bool = True,
    ) -> ProcessInfo:
        """Launch an application for debugging

        Args:
            executable: Path to executable or .app bundle
            args: Optional command-line arguments
            env: Optional environment variables
            stop_at_entry: If True, stop at entry point; otherwise run

        Returns:
            ProcessInfo with details about launched process

        Raises:
            InvalidStateError: If already attached to a process
            LLDBError: If launch operation fails
        """
        async with self._lock:
            if self._state != ProcessState.DETACHED:
                raise InvalidStateError(f"Already attached to a process (state: {self._state.value})")

            debugger = self.get_debugger()

            # Handle .app bundles - resolve to executable
            resolved_executable = executable
            if executable.endswith(".app"):
                import os
                # Look for executable inside .app/Contents/MacOS/
                app_name = os.path.basename(executable).replace(".app", "")
                possible_executable = os.path.join(executable, "Contents", "MacOS", app_name)
                if os.path.exists(possible_executable):
                    resolved_executable = possible_executable
                else:
                    raise LLDBError(f"Could not find executable in .app bundle: {executable}")

            # Create target
            error = lldb.SBError()
            target = await run_lldb_operation(
                debugger.CreateTarget, resolved_executable, None, None, True, error
            )

            if error.Fail() or not target.IsValid():
                error_msg = error.GetCString() if error.Fail() else "Unknown error"
                raise LLDBError(f"Failed to create target for '{resolved_executable}': {error_msg}")

            # Set up launch info
            launch_info = lldb.SBLaunchInfo(args or [])
            if env:
                env_list = [f"{key}={value}" for key, value in env.items()]
                for i, env_entry in enumerate(env_list):
                    launch_info.SetEnvironmentEntryAtIndex(env_entry, i)

            if stop_at_entry:
                launch_info.SetLaunchFlags(launch_info.GetLaunchFlags() | lldb.eLaunchFlagStopAtEntry)

            # Launch process
            error = lldb.SBError()
            process = await run_lldb_operation(target.Launch, launch_info, error)

            if error.Fail() or not process.IsValid():
                error_msg = error.GetCString() if error.Fail() else "Unknown error"
                raise LLDBError(f"Failed to launch '{resolved_executable}': {error_msg}")

            state = ProcessState.ATTACHED_STOPPED if stop_at_entry else ProcessState.ATTACHED_RUNNING
            self._set_state(state)
            logger.info(f"Launched '{resolved_executable}' (PID {process.GetProcessID()})")

            # Return process info
            return ProcessInfo(
                pid=process.GetProcessID(),
                name=process.GetName() or "",
                state="stopped" if stop_at_entry else "running",
                architecture=target.GetTriple() or "unknown",
            )

    async def detach(self, kill: bool = False) -> None:
        """Detach from current process

        Args:
            kill: If True, kill the process; otherwise just detach

        Raises:
            ProcessNotAttachedError: If no process attached
        """
        async with self._lock:
            if self._state == ProcessState.DETACHED:
                raise ProcessNotAttachedError("No process attached")

            process = self.get_process()

            if kill:
                error = process.Kill()
                if error.Fail():
                    raise LLDBError(f"Failed to kill process: {error.GetCString()}")
                logger.info(f"Killed process {process.GetProcessID()}")
            else:
                error = process.Detach()
                if error.Fail():
                    raise LLDBError(f"Failed to detach: {error.GetCString()}")
                logger.info(f"Detached from process {process.GetProcessID()}")

            self._set_state(ProcessState.DETACHED)
            self._loaded_frameworks.clear()

    async def continue_execution(self) -> str:
        """Continue execution of paused process

        Returns:
            String describing the new state

        Raises:
            ProcessNotAttachedError: If no process attached
            InvalidStateError: If process is not stopped
        """
        async with self._lock:
            if self._state != ProcessState.ATTACHED_STOPPED:
                raise InvalidStateError(
                    f"Cannot continue: process is not stopped (state: {self._state.value})"
                )

            process = self.get_process()
            error = await run_lldb_operation(process.Continue)

            if error.Fail():
                raise LLDBError(f"Failed to continue: {error.GetCString()}")

            self._set_state(ProcessState.ATTACHED_RUNNING)
            logger.info("Process continued")

            return self._state.value

    async def pause_execution(self) -> str:
        """Pause execution of running process

        Returns:
            String describing stop reason and location

        Raises:
            ProcessNotAttachedError: If no process attached
            InvalidStateError: If process is not running
        """
        async with self._lock:
            if self._state != ProcessState.ATTACHED_RUNNING:
                raise InvalidStateError(
                    f"Cannot pause: process is not running (state: {self._state.value})"
                )

            process = self.get_process()
            error = await run_lldb_operation(process.Stop)

            if error.Fail():
                raise LLDBError(f"Failed to pause: {error.GetCString()}")

            self._set_state(ProcessState.ATTACHED_STOPPED)
            logger.info("Process paused")

            # Get stop reason and location
            thread = process.GetSelectedThread()
            if not thread.IsValid():
                return "paused"

            stop_reason = thread.GetStopDescription(256)
            location = self._get_frame_location(thread)

            return f"Stop reason: {stop_reason}\n{location}"

    async def step_over(self, thread_id: Optional[int] = None) -> str:
        """Step over current line

        Args:
            thread_id: Optional thread ID. If None, uses selected thread

        Returns:
            String describing current frame location

        Raises:
            ProcessNotAttachedError: If no process attached
            InvalidStateError: If process is not stopped
            ValueError: If thread ID is invalid
        """
        async with self._lock:
            if self._state != ProcessState.ATTACHED_STOPPED:
                raise InvalidStateError(
                    f"Cannot step: process is not stopped (state: {self._state.value})"
                )

            thread = self._get_thread(thread_id)
            await run_lldb_operation(thread.StepOver)

            # State remains ATTACHED_STOPPED
            logger.info(f"Stepped over (thread {thread.GetThreadID()})")

            return self._get_frame_location(thread)

    async def step_into(self, thread_id: Optional[int] = None) -> str:
        """Step into function call

        Args:
            thread_id: Optional thread ID. If None, uses selected thread

        Returns:
            String describing current frame location

        Raises:
            ProcessNotAttachedError: If no process attached
            InvalidStateError: If process is not stopped
            ValueError: If thread ID is invalid
        """
        async with self._lock:
            if self._state != ProcessState.ATTACHED_STOPPED:
                raise InvalidStateError(
                    f"Cannot step: process is not stopped (state: {self._state.value})"
                )

            thread = self._get_thread(thread_id)
            await run_lldb_operation(thread.StepInto)

            # State remains ATTACHED_STOPPED
            logger.info(f"Stepped into (thread {thread.GetThreadID()})")

            return self._get_frame_location(thread)

    async def step_out(self, thread_id: Optional[int] = None) -> str:
        """Step out of current function

        Args:
            thread_id: Optional thread ID. If None, uses selected thread

        Returns:
            String describing current frame location

        Raises:
            ProcessNotAttachedError: If no process attached
            InvalidStateError: If process is not stopped
            ValueError: If thread ID is invalid
        """
        async with self._lock:
            if self._state != ProcessState.ATTACHED_STOPPED:
                raise InvalidStateError(
                    f"Cannot step: process is not stopped (state: {self._state.value})"
                )

            thread = self._get_thread(thread_id)
            await run_lldb_operation(thread.StepOut)

            # State remains ATTACHED_STOPPED
            logger.info(f"Stepped out (thread {thread.GetThreadID()})")

            return self._get_frame_location(thread)

    def _get_thread(self, thread_id: Optional[int] = None):
        """Get thread by ID or selected thread

        Args:
            thread_id: Optional thread ID. If None, returns selected thread

        Returns:
            The requested SBThread

        Raises:
            ValueError: If thread ID is invalid or no thread available
        """
        process = self.get_process()

        if thread_id is not None:
            thread = process.GetThreadByID(thread_id)
            if not thread.IsValid():
                raise ValueError(f"Invalid thread ID: {thread_id}")
            return thread

        # Use selected thread
        thread = process.GetSelectedThread()
        if not thread.IsValid():
            raise ValueError("No valid thread selected")

        return thread

    def _get_frame_location(self, thread) -> str:
        """Get current frame location for a thread

        Args:
            thread: The thread to get frame location from

        Returns:
            Formatted string with function, file, and line info
        """
        frame = thread.GetFrameAtIndex(0)
        if not frame.IsValid():
            return "Location: <unknown>"

        function = frame.GetFunctionName() or "<unknown>"
        line_entry = frame.GetLineEntry()

        if line_entry.IsValid():
            file_spec = line_entry.GetFileSpec()
            filename = file_spec.GetFilename() or "<unknown>"
            line_number = line_entry.GetLine()
            return f"Location: {function} at {filename}:{line_number}"
        else:
            pc = frame.GetPC()
            return f"Location: {function} at {hex(pc)}"

    async def cleanup(self) -> None:
        """Clean up debugger resources

        This should be called when shutting down the server.
        """
        if self._debugger is None:
            return

        logger.info("Cleaning up LLDB debugger")

        # Detach from any attached process
        try:
            if self.is_attached():
                await self.detach()
        except Exception as e:
            logger.warning(f"Error detaching during cleanup: {e}")

        # Destroy debugger
        lldb.SBDebugger.Destroy(self._debugger)
        lldb.SBDebugger.Terminate()
        self._debugger = None
        self._loaded_frameworks.clear()
        logger.info("LLDB debugger cleaned up")
