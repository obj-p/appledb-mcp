"""MCP server implementation using FastMCP"""

import logging
from contextlib import asynccontextmanager

from mcp.server.fastmcp import FastMCP

from .config import AppleDBConfig
from .debugger import LLDBDebuggerManager

logger = logging.getLogger(__name__)


@asynccontextmanager
async def app_lifespan(server: FastMCP):
    """Manage LLDB debugger lifecycle

    This context manager initializes the LLDB debugger when the server starts
    and cleans it up when the server shuts down.

    Args:
        server: The FastMCP server instance
    """
    # Load configuration
    config = AppleDBConfig()
    logger.info(f"Loaded configuration: log_level={config.log_level}")

    # Initialize LLDB debugger
    logger.info("Initializing LLDB debugger")
    debugger_manager = LLDBDebuggerManager.get_instance()
    try:
        debugger_manager.initialize(config)
    except RuntimeError as e:
        logger.error(f"Failed to initialize LLDB: {e}")
        raise

    try:
        yield
    finally:
        # Clean up on shutdown
        logger.info("Shutting down LLDB debugger")
        await debugger_manager.cleanup()


# Create FastMCP server instance
mcp = FastMCP("appledb", lifespan=app_lifespan)


# Tools will be registered in subsequent phases
# For now, just provide a health check tool for testing

@mcp.tool()
async def health_check() -> str:
    """Check if the MCP server and LLDB debugger are healthy

    Returns:
        Health status message
    """
    try:
        manager = LLDBDebuggerManager.get_instance()
        debugger = manager.get_debugger()
        return f"✓ MCP server running, LLDB debugger initialized (version: {debugger.GetVersionString()})"
    except Exception as e:
        return f"✗ Error: {str(e)}"
