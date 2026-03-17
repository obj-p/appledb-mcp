"""MCP server implementation using FastMCP"""

import logging
from contextlib import asynccontextmanager

from mcp.server.fastmcp import FastMCP

from .config import AppleDBConfig
from .lldb_client import LLDBClient

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

    # Initialize LLDB client
    logger.info("Initializing LLDB client")
    client = LLDBClient.get_instance()
    try:
        await client.initialize(config)
    except RuntimeError as e:
        logger.error(f"Failed to initialize LLDB client: {e}")
        raise

    try:
        yield
    finally:
        # Clean up on shutdown
        logger.info("Shutting down LLDB client")
        await client.cleanup()


# Create FastMCP server instance
mcp = FastMCP("appledb", lifespan=app_lifespan)

# Import tools to register them with the MCP server
# This must be done after mcp instance is created
from .tools import process, execution, inspection, framework, command, breakpoint  # noqa: E402, F401


# Health check tool for testing

@mcp.tool()
async def health_check() -> str:
    """Check if the MCP server and LLDB service are healthy

    Returns:
        Health status message
    """
    try:
        client = LLDBClient.get_instance()
        health = await client.ping()
        return f"✓ MCP server running, LLDB service healthy (attached: {health['attached']}, state: {health['state']})"
    except Exception as e:
        return f"✗ Error: {str(e)}"
