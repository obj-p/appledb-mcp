"""Entry point for appledb-mcp MCP server"""

import logging
import os
import sys


def setup_logging() -> None:
    """Configure logging to stderr (required for stdio transport)

    MCP servers using stdio transport must not write to stdout, as that
    channel is reserved for MCP protocol messages. All logging goes to stderr.
    """
    log_level = os.getenv("APPLEDB_LOG_LEVEL", "INFO")
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stderr,  # CRITICAL: Must use stderr, not stdout
    )


def main() -> None:
    """Main entry point for the MCP server"""
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("Starting appledb-mcp server")

    try:
        from appledb_mcp.server import mcp

        # Run the MCP server with stdio transport
        mcp.run(transport="stdio")
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
