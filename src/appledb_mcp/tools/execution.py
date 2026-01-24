"""Execution control MCP tools"""

import logging
from typing import Optional

from ..debugger import LLDBDebuggerManager
from ..server import mcp
from .base import handle_tool_errors

logger = logging.getLogger(__name__)


@mcp.tool()
@handle_tool_errors
async def lldb_continue() -> str:
    """Continue execution of paused process

    Resumes execution of a stopped process. The process must be in a stopped
    state before calling this tool.

    Returns:
        Success message with new process state

    Raises:
        ProcessNotAttachedError: If no process is attached
        InvalidStateError: If process is not stopped

    Examples:
        Continue execution: lldb_continue()
    """
    logger.info("Continuing execution")

    manager = LLDBDebuggerManager.get_instance()
    result = await manager.continue_execution()

    return f"✓ Execution continued\n  State: {result}"


@mcp.tool()
@handle_tool_errors
async def lldb_pause() -> str:
    """Pause execution of running process

    Pauses execution of a running process. The process must be in a running
    state before calling this tool.

    Returns:
        Success message with stop reason and location

    Raises:
        ProcessNotAttachedError: If no process is attached
        InvalidStateError: If process is not running

    Examples:
        Pause execution: lldb_pause()
    """
    logger.info("Pausing execution")

    manager = LLDBDebuggerManager.get_instance()
    result = await manager.pause_execution()

    return f"✓ Execution paused\n{result}"


@mcp.tool()
@handle_tool_errors
async def lldb_step_over(thread_id: Optional[int] = None) -> str:
    """Step over current line

    Steps over the current line of code without entering function calls.
    If thread_id is not provided, uses the currently selected thread.

    Args:
        thread_id: Optional thread ID to step. If None, uses selected thread

    Returns:
        Success message with current frame location

    Raises:
        ProcessNotAttachedError: If no process is attached
        InvalidStateError: If process is not stopped
        ValueError: If specified thread ID is invalid

    Examples:
        Step over: lldb_step_over()
        Step over specific thread: lldb_step_over(thread_id=1)
    """
    logger.info(f"Stepping over (thread_id={thread_id})")

    manager = LLDBDebuggerManager.get_instance()
    result = await manager.step_over(thread_id=thread_id)

    return f"✓ Stepped over\n{result}"


@mcp.tool()
@handle_tool_errors
async def lldb_step_into(thread_id: Optional[int] = None) -> str:
    """Step into function call

    Steps into the current line of code, entering function calls.
    If thread_id is not provided, uses the currently selected thread.

    Args:
        thread_id: Optional thread ID to step. If None, uses selected thread

    Returns:
        Success message with current frame location

    Raises:
        ProcessNotAttachedError: If no process is attached
        InvalidStateError: If process is not stopped
        ValueError: If specified thread ID is invalid

    Examples:
        Step into: lldb_step_into()
        Step into specific thread: lldb_step_into(thread_id=1)
    """
    logger.info(f"Stepping into (thread_id={thread_id})")

    manager = LLDBDebuggerManager.get_instance()
    result = await manager.step_into(thread_id=thread_id)

    return f"✓ Stepped into\n{result}"


@mcp.tool()
@handle_tool_errors
async def lldb_step_out(thread_id: Optional[int] = None) -> str:
    """Step out of current function

    Steps out of the current function, returning to the caller.
    If thread_id is not provided, uses the currently selected thread.

    Args:
        thread_id: Optional thread ID to step. If None, uses selected thread

    Returns:
        Success message with current frame location

    Raises:
        ProcessNotAttachedError: If no process is attached
        InvalidStateError: If process is not stopped
        ValueError: If specified thread ID is invalid

    Examples:
        Step out: lldb_step_out()
        Step out specific thread: lldb_step_out(thread_id=1)
    """
    logger.info(f"Stepping out (thread_id={thread_id})")

    manager = LLDBDebuggerManager.get_instance()
    result = await manager.step_out(thread_id=thread_id)

    return f"✓ Stepped out\n{result}"
