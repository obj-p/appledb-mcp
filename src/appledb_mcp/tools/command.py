"""LLDB command passthrough MCP tool"""

import logging
from ..lldb_client import LLDBClient
from ..server import mcp
from .base import handle_tool_errors

logger = logging.getLogger(__name__)


@mcp.tool()
@handle_tool_errors
async def lldb_command(command: str) -> str:
    """Execute any LLDB command and return the raw output.

    This is a passthrough to the LLDB command interpreter, giving access
    to the full LLDB command set. Examples: "bt", "register read",
    "memory read 0x100", "breakpoint set -n main", "help".

    Args:
        command: The LLDB command to execute

    Returns:
        Raw LLDB command output
    """
    logger.info(f"Executing LLDB command: {command}")
    client = LLDBClient.get_instance()
    result = await client.execute_command(command)

    output = ""
    if result["output"]:
        output += result["output"]
    if result["error"]:
        if output:
            output += "\n"
        output += result["error"]
    if not output.strip():
        output = "(no output)"
    return output
