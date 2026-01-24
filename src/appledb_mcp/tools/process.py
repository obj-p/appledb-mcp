"""Process management MCP tools"""

import logging
from typing import Dict, List, Optional

from ..debugger import LLDBDebuggerManager
from ..server import mcp
from .base import handle_tool_errors

logger = logging.getLogger(__name__)


@mcp.tool()
@handle_tool_errors
async def lldb_attach_process(
    pid: Optional[int] = None,
    name: Optional[str] = None
) -> str:
    """Attach to a running process by PID or name

    Args:
        pid: Process ID to attach to (mutually exclusive with name)
        name: Process name to attach to (mutually exclusive with pid)

    Returns:
        Success message with process details

    Raises:
        ValueError: If neither or both pid and name are provided
        InvalidStateError: If already attached to a process
        LLDBError: If attach operation fails

    Examples:
        Attach by PID: lldb_attach_process(pid=1234)
        Attach by name: lldb_attach_process(name="MyApp")
    """
    # Validate inputs
    if not pid and not name:
        raise ValueError("Either 'pid' or 'name' must be provided")
    if pid and name:
        raise ValueError("Cannot specify both 'pid' and 'name'")

    manager = LLDBDebuggerManager.get_instance()

    # Attach by PID or name
    if pid:
        logger.info(f"Attaching to process by PID: {pid}")
        result = await manager.attach_process_by_pid(pid)
    else:
        logger.info(f"Attaching to process by name: {name}")
        result = await manager.attach_process_by_name(name)

    return (
        f"✓ Attached to process '{result.name}'\n"
        f"  PID: {result.pid}\n"
        f"  Architecture: {result.architecture}\n"
        f"  State: {result.state}"
    )


@mcp.tool()
@handle_tool_errors
async def lldb_launch_app(
    executable: str,
    args: Optional[List[str]] = None,
    env: Optional[Dict[str, str]] = None,
    stop_at_entry: bool = True
) -> str:
    """Launch an application for debugging

    Args:
        executable: Path to executable or .app bundle
        args: Optional command-line arguments to pass to the application
        env: Optional environment variables (as key-value pairs)
        stop_at_entry: If True, stop at entry point; if False, run immediately

    Returns:
        Success message with process details

    Raises:
        InvalidStateError: If already attached to a process
        LLDBError: If launch operation fails

    Examples:
        Launch app: lldb_launch_app(executable="/path/to/app")
        With args: lldb_launch_app(executable="/path/to/app", args=["--verbose"])
        With env: lldb_launch_app(executable="/path/to/app", env={"DEBUG": "1"})
    """
    logger.info(f"Launching application: {executable}")

    manager = LLDBDebuggerManager.get_instance()
    result = await manager.launch_app(
        executable=executable,
        args=args,
        env=env,
        stop_at_entry=stop_at_entry
    )

    return (
        f"✓ Launched application '{result.name}'\n"
        f"  PID: {result.pid}\n"
        f"  Architecture: {result.architecture}\n"
        f"  State: {result.state}\n"
        f"  Stopped at entry: {stop_at_entry}"
    )


@mcp.tool()
@handle_tool_errors
async def lldb_detach(kill: bool = False) -> str:
    """Detach from the current process

    Args:
        kill: If True, kill the process; if False, just detach and let it continue

    Returns:
        Success message

    Raises:
        ProcessNotAttachedError: If no process is currently attached

    Examples:
        Detach and let run: lldb_detach()
        Kill process: lldb_detach(kill=True)
    """
    logger.info(f"Detaching from process (kill={kill})")

    manager = LLDBDebuggerManager.get_instance()
    await manager.detach(kill=kill)

    action = "killed" if kill else "detached from"
    return f"✓ Successfully {action} process"
