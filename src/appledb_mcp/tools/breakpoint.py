"""Breakpoint management MCP tools"""

import logging
from typing import Optional

from ..lldb_client import LLDBClient
from ..server import mcp
from .base import handle_tool_errors

logger = logging.getLogger(__name__)


@mcp.tool()
@handle_tool_errors
async def lldb_set_breakpoint(
    file: Optional[str] = None,
    line: Optional[int] = None,
    symbol: Optional[str] = None,
    module: Optional[str] = None,
    condition: Optional[str] = None,
) -> str:
    """Set a breakpoint by file:line or symbol name

    Args:
        file: Source file path (use with line)
        line: Line number in source file (use with file)
        symbol: Function/symbol name to break on
        module: Module to restrict symbol search to
        condition: Conditional expression (breakpoint only triggers when true)

    Returns:
        Breakpoint details

    Examples:
        By location: lldb_set_breakpoint(file="main.c", line=42)
        By symbol: lldb_set_breakpoint(symbol="viewDidLoad")
        With condition: lldb_set_breakpoint(symbol="malloc", condition="$arg1 > 1024")
    """
    logger.info(f"Setting breakpoint: file={file}, line={line}, symbol={symbol}")

    client = LLDBClient.get_instance()
    result = await client.set_breakpoint(
        file=file, line=line, symbol=symbol, module=module, condition=condition
    )

    output = f"Breakpoint {result['id']} set"
    if result.get("file") and result.get("line"):
        output += f" at {result['file']}:{result['line']}"
    elif result.get("symbol"):
        output += f" on '{result['symbol']}'"
    output += f"\n  Locations: {result.get('locations', 0)}"
    if result.get("condition"):
        output += f"\n  Condition: {result['condition']}"
    return output


@mcp.tool()
@handle_tool_errors
async def lldb_list_breakpoints() -> str:
    """List all breakpoints

    Returns:
        Formatted list of all breakpoints with their details
    """
    client = LLDBClient.get_instance()
    breakpoints = await client.list_breakpoints()

    if not breakpoints:
        return "No breakpoints set"

    output = f"{len(breakpoints)} breakpoint(s):\n"
    for bp in breakpoints:
        status = "enabled" if bp.get("enabled", True) else "disabled"
        output += f"\n  #{bp['id']}: {status}"
        if bp.get("file") and bp.get("line"):
            output += f", {bp['file']}:{bp['line']}"
        if bp.get("symbol"):
            output += f", symbol='{bp['symbol']}'"
        output += f", locations={bp.get('locations', 0)}, hits={bp.get('hit_count', 0)}"
        if bp.get("condition"):
            output += f"\n    condition: {bp['condition']}"
    return output


@mcp.tool()
@handle_tool_errors
async def lldb_delete_breakpoint(breakpoint_id: int) -> str:
    """Delete a breakpoint by ID

    Args:
        breakpoint_id: The breakpoint ID to delete (from lldb_list_breakpoints)

    Returns:
        Confirmation message
    """
    logger.info(f"Deleting breakpoint {breakpoint_id}")

    client = LLDBClient.get_instance()
    await client.delete_breakpoint(breakpoint_id)
    return f"Breakpoint {breakpoint_id} deleted"
