"""LLDB helper utilities"""

import asyncio
from typing import Any, Callable, Optional

try:
    import lldb
except ImportError:
    lldb = None  # type: ignore


async def run_lldb_operation(func: Callable, *args: Any, **kwargs: Any) -> Any:
    """Run a blocking LLDB operation in a thread pool

    Args:
        func: The LLDB function to call
        *args: Positional arguments to pass to func
        **kwargs: Keyword arguments to pass to func

    Returns:
        The result of the LLDB operation
    """
    return await asyncio.to_thread(func, *args, **kwargs)


def state_to_string(state: Any) -> str:
    """Convert LLDB state to string

    Args:
        state: LLDB StateType enum value

    Returns:
        Human-readable state string
    """
    if lldb is None:
        return "unknown"

    state_map = {
        lldb.eStateInvalid: "invalid",
        lldb.eStateUnloaded: "unloaded",
        lldb.eStateConnected: "connected",
        lldb.eStateAttaching: "attaching",
        lldb.eStateLaunching: "launching",
        lldb.eStateStopped: "stopped",
        lldb.eStateRunning: "running",
        lldb.eStateStepping: "stepping",
        lldb.eStateCrashed: "crashed",
        lldb.eStateDetached: "detached",
        lldb.eStateExited: "exited",
        lldb.eStateSuspended: "suspended",
    }
    return state_map.get(state, "unknown")


def get_stop_reason_string(thread: Any) -> str:
    """Get human-readable stop reason from thread

    Args:
        thread: LLDB SBThread object

    Returns:
        Human-readable stop reason string
    """
    if lldb is None:
        return "unknown"

    reason = thread.GetStopReason()
    reason_map = {
        lldb.eStopReasonInvalid: "invalid",
        lldb.eStopReasonNone: "none",
        lldb.eStopReasonTrace: "trace",
        lldb.eStopReasonBreakpoint: "breakpoint",
        lldb.eStopReasonWatchpoint: "watchpoint",
        lldb.eStopReasonSignal: "signal",
        lldb.eStopReasonException: "exception",
        lldb.eStopReasonExec: "exec",
        lldb.eStopReasonPlanComplete: "step",
    }
    return reason_map.get(reason, "unknown")


def check_lldb_available() -> bool:
    """Check if LLDB is available

    Returns:
        True if lldb module can be imported, False otherwise
    """
    return lldb is not None


def get_lldb_path() -> Optional[str]:
    """Get LLDB Python module path

    Returns:
        Path to LLDB Python module, or None if not available
    """
    import subprocess

    try:
        result = subprocess.run(
            ["lldb", "-P"], capture_output=True, text=True, timeout=5, check=False
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None
