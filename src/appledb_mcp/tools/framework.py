"""Framework loading MCP tools"""

import json
import logging
from typing import Optional

from ..debugger import LLDBDebuggerManager
from ..server import mcp
from .base import handle_tool_errors

logger = logging.getLogger(__name__)


@mcp.tool()
@handle_tool_errors
async def lldb_load_framework(
    framework_path: Optional[str] = None,
    framework_name: Optional[str] = None
) -> str:
    """Load a dynamic framework into the debugged process

    This tool allows loading dynamic frameworks into the currently attached process.
    The operation is idempotent - if the framework is already loaded, it will not be loaded again.

    Args:
        framework_path: Explicit path to framework binary (mutually exclusive with framework_name)
        framework_name: Named framework from bundled/dev locations (mutually exclusive with framework_path)

    Returns:
        JSON string with load result details

    Raises:
        ProcessNotAttachedError: If no process is currently attached
        ValueError: If neither or both parameters provided, or invalid framework_name
        FileNotFoundError: If framework path cannot be resolved
        LLDBError: If framework loading fails

    Examples:
        Load by explicit path: lldb_load_framework(framework_path="/path/to/myframework.framework/myframework")
        Load by name: lldb_load_framework(framework_name="myframework")
    """
    logger.info(f"Loading framework: path={framework_path}, name={framework_name}")

    manager = LLDBDebuggerManager.get_instance()
    result = await manager.load_framework(
        framework_path=framework_path,
        framework_name=framework_name
    )

    # Format success message
    if result["already_loaded"]:
        status = f"✓ Framework already loaded at {hex(result['address'])}"
    else:
        status = f"✓ Framework loaded successfully at {hex(result['address'])}"

    message = f"{status}\n{result['message']}"

    # Return JSON for programmatic access, but with a human-readable message
    return f"{message}\n\nDetails: {json.dumps(result, indent=2)}"
