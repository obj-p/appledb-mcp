"""LLDB Service entry point

This module provides the entry point for running the LLDB service as a subprocess.
Run with: python -m lldb_service
"""

import asyncio
import json
import logging
import signal
import sys

# Validate Python version FIRST (before any other imports)
if sys.version_info < (3, 9):
    error = {"error": f"Requires Python 3.9+, got {sys.version}"}
    print(json.dumps(error), file=sys.stderr)
    sys.exit(1)

# Validate LLDB availability
try:
    import lldb  # noqa: F401
except ImportError:
    error = {"error": "LLDB module not available. Install Xcode Command Line Tools."}
    print(json.dumps(error), file=sys.stderr)
    sys.exit(1)

from .debugger import LLDBDebuggerManager
from .handlers import (
    handle_attach_process,
    handle_cleanup,
    handle_continue_execution,
    handle_detach,
    handle_evaluate_expression,
    handle_get_backtrace,
    handle_get_debugger_state,
    handle_get_variables,
    handle_initialize,
    handle_launch_app,
    handle_load_framework,
    handle_pause,
    handle_ping,
    handle_step_into,
    handle_step_out,
    handle_step_over,
)
from .server import JSONRPCServer

logger = logging.getLogger(__name__)


async def main() -> None:
    """Main entry point for LLDB service."""

    # Setup logging to stderr (stdout reserved for JSON-RPC)
    logging.basicConfig(
        level=logging.INFO,
        format="[LLDB-SERVICE] %(levelname)s: %(message)s",
        stream=sys.stderr,
        force=True,
    )

    logger.info("LLDB Service starting")
    logger.info(f"Python version: {sys.version}")

    # Create server
    server = JSONRPCServer()

    # Register all 16 handlers
    server.register_handler("ping", handle_ping)
    server.register_handler("initialize", handle_initialize)
    server.register_handler("attach_process", handle_attach_process)
    server.register_handler("launch_app", handle_launch_app)
    server.register_handler("detach", handle_detach)
    server.register_handler("continue_execution", handle_continue_execution)
    server.register_handler("pause", handle_pause)
    server.register_handler("step_over", handle_step_over)
    server.register_handler("step_into", handle_step_into)
    server.register_handler("step_out", handle_step_out)
    server.register_handler("evaluate_expression", handle_evaluate_expression)
    server.register_handler("get_backtrace", handle_get_backtrace)
    server.register_handler("get_variables", handle_get_variables)
    server.register_handler("load_framework", handle_load_framework)
    server.register_handler("get_debugger_state", handle_get_debugger_state)
    server.register_handler("cleanup", handle_cleanup)

    logger.info("Registered 16 RPC handlers")

    # Setup signal handlers for graceful shutdown
    def handle_shutdown(signum):
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, shutting down")
        server.stop()

        # Cleanup debugger
        try:
            manager = LLDBDebuggerManager.get_instance()
            # Run cleanup in a task
            asyncio.create_task(manager.cleanup())
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

        sys.exit(0)

    # Register signal handlers
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda s=sig: handle_shutdown(s))

    logger.info("Signal handlers registered")

    # Send ready signal
    ready_signal = {"jsonrpc": "2.0", "method": "ready", "params": {}}
    print(json.dumps(ready_signal), flush=True)
    logger.info("Ready signal sent")

    # Run server with single event loop
    await server.run()

    logger.info("LLDB Service stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
