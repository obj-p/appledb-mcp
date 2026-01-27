"""Inspection MCP tools"""

import logging
from typing import Optional

from ..lldb_client import LLDBClient
from ..server import mcp
from .base import handle_tool_errors

logger = logging.getLogger(__name__)


@mcp.tool()
@handle_tool_errors
async def lldb_evaluate(
    expression: str,
    language: Optional[str] = None,
    frame_index: int = 0,
) -> str:
    """Evaluate expression in debugger context

    Evaluates an expression in the context of the current debugging session.
    Supports multiple languages (Swift, Objective-C, C++, C) with automatic
    or manual language selection.

    Args:
        expression: Expression to evaluate (e.g., "myVariable", "self.property")
        language: Optional language hint ("swift", "objc", "c++", "c")
        frame_index: Stack frame index to evaluate in (0 = current frame)

    Returns:
        Formatted evaluation result with value, type, and summary

    Raises:
        ProcessNotAttachedError: If no process is attached
        InvalidStateError: If process is not stopped
        ValueError: If invalid language or frame index

    Examples:
        Evaluate variable: lldb_evaluate(expression="myVariable")
        Evaluate with language: lldb_evaluate(expression="self", language="swift")
        Evaluate in specific frame: lldb_evaluate(expression="argc", frame_index=1)
    """
    logger.info(f"Evaluating expression: {expression} (language={language}, frame_index={frame_index})")

    client = LLDBClient.get_instance()
    result = await client.evaluate_expression(
        expression=expression,
        language=language,
        frame_index=frame_index,
    )

    # Format result
    if result["error"]:
        return f"✗ Evaluation failed\n  Error: {result['error']}"

    output = f"✓ Expression: {expression}\n"
    output += f"  Type: {result['type']}\n"
    output += f"  Value: {result['value']}\n"
    if result['summary']:
        output += f"  Summary: {result['summary']}"

    return output


@mcp.tool()
@handle_tool_errors
async def lldb_get_backtrace(
    thread_id: Optional[int] = None,
    max_frames: Optional[int] = None,
) -> str:
    """Get stack trace for thread

    Returns the call stack (backtrace) for the specified thread, showing
    the sequence of function calls that led to the current execution point.

    Args:
        thread_id: Optional thread ID. If None, uses the selected thread
        max_frames: Maximum number of frames to return (default: 100)

    Returns:
        Formatted backtrace with frame index, function, file, and line info

    Raises:
        ProcessNotAttachedError: If no process is attached
        ValueError: If specified thread ID is invalid

    Examples:
        Get backtrace: lldb_get_backtrace()
        Specific thread: lldb_get_backtrace(thread_id=1)
        Limit frames: lldb_get_backtrace(max_frames=10)
    """
    logger.info(f"Getting backtrace (thread_id={thread_id}, max_frames={max_frames})")

    client = LLDBClient.get_instance()
    frames = await client.get_backtrace(
        thread_id=thread_id,
        max_frames=max_frames,
    )

    if not frames:
        return "No frames available"

    # Format backtrace
    output = f"✓ Backtrace ({len(frames)} frames):\n"
    for frame in frames:
        output += f"\n  #{frame['index']}: {frame['function']}"
        if frame['file'] and frame['line']:
            output += f"\n      at {frame['file']}:{frame['line']}"
        else:
            output += f"\n      at {frame['pc']}"
        if frame['module']:
            output += f"\n      in {frame['module']}"

    return output


@mcp.tool()
@handle_tool_errors
async def lldb_get_variables(
    frame_index: int = 0,
    include_arguments: bool = True,
    include_locals: bool = True,
) -> str:
    """Get local variables in frame

    Returns all variables visible in the specified stack frame, including
    function arguments and local variables.

    Args:
        frame_index: Stack frame index (0 = current frame)
        include_arguments: Include function arguments in results
        include_locals: Include local variables in results

    Returns:
        Formatted list of variables with name, type, value, and summary

    Raises:
        ProcessNotAttachedError: If no process is attached
        InvalidStateError: If process is not stopped
        ValueError: If invalid frame index

    Examples:
        Get all variables: lldb_get_variables()
        Only arguments: lldb_get_variables(include_locals=False)
        Only locals: lldb_get_variables(include_arguments=False)
        Different frame: lldb_get_variables(frame_index=1)
    """
    logger.info(f"Getting variables (frame_index={frame_index}, args={include_arguments}, locals={include_locals})")

    client = LLDBClient.get_instance()
    variables = await client.get_variables(
        frame_index=frame_index,
        include_arguments=include_arguments,
        include_locals=include_locals,
    )

    if not variables:
        return f"✓ No variables available in frame {frame_index}"

    # Format variables
    output = f"✓ Variables in frame {frame_index} ({len(variables)} total):\n"
    for var in variables:
        output += f"\n  {var['name']}: {var['type']}"
        if var['value']:
            output += f" = {var['value']}"
        if var['summary']:
            output += f"\n    Summary: {var['summary']}"

    return output
