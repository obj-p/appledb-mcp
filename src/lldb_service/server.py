"""JSON-RPC 2.0 server with stdio transport"""

import asyncio
import json
import logging
import sys
from typing import Any, Callable, Dict

logger = logging.getLogger(__name__)


class JSONRPCServer:
    """JSON-RPC 2.0 server using stdin/stdout transport.

    This server:
    - Reads line-delimited JSON-RPC requests from stdin
    - Dispatches to registered handlers
    - Writes line-delimited JSON-RPC responses to stdout
    - Uses a single event loop for all requests to preserve async context
    """

    def __init__(self):
        self.handlers: Dict[str, Callable] = {}
        self.running = False

    def register_handler(self, method: str, handler: Callable) -> None:
        """Register RPC method handler.

        Args:
            method: RPC method name
            handler: Async function to handle the method
        """
        self.handlers[method] = handler
        logger.debug(f"Registered handler for method: {method}")

    def _error_response(self, request_id: Any, code: int, message: str) -> dict:
        """Create JSON-RPC error response.

        Args:
            request_id: Request ID (may be None)
            code: Error code
            message: Error message

        Returns:
            JSON-RPC error response dict
        """
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": code, "message": message},
        }

    async def handle_request(self, request: dict) -> dict:
        """Process single JSON-RPC request with timeout.

        Args:
            request: Parsed JSON-RPC request

        Returns:
            JSON-RPC response dict
        """
        request_id = request.get("id")

        try:
            # Validate JSON-RPC 2.0 format
            if request.get("jsonrpc") != "2.0":
                return self._error_response(request_id, -32600, "Invalid Request: missing jsonrpc field")

            method = request.get("method")
            if not method:
                return self._error_response(request_id, -32600, "Invalid Request: missing method")

            # Check if handler exists
            if method not in self.handlers:
                return self._error_response(request_id, -32601, f"Method not found: {method}")

            params = request.get("params", {})

            # Dispatch to handler with 30s timeout
            try:
                result = await asyncio.wait_for(
                    self.handlers[method](params),
                    timeout=30.0
                )

                return {"jsonrpc": "2.0", "id": request_id, "result": result}

            except asyncio.TimeoutError:
                logger.error(f"Timeout executing method: {method}")
                return self._error_response(request_id, -32000, "Operation timeout")

        except ValueError as e:
            logger.error(f"ValueError in request: {e}")
            return self._error_response(request_id, -32602, f"Invalid params: {str(e)}")

        except RuntimeError as e:
            logger.error(f"RuntimeError in request: {e}")
            return self._error_response(request_id, -32603, f"Internal error: {str(e)}")

        except Exception as e:
            logger.error(f"Unexpected error in request: {e}", exc_info=True)
            return self._error_response(request_id, -32603, f"Internal error: {str(e)}")

    async def run(self) -> None:
        """Main server loop - CRITICAL: single event loop for all requests.

        This method:
        1. Reads requests from stdin (non-blocking)
        2. Handles each request
        3. Writes responses to stdout
        4. Maintains the same event loop throughout
        """
        self.running = True
        loop = asyncio.get_event_loop()

        # Configure stdout for line buffering
        sys.stdout.reconfigure(line_buffering=True)

        logger.info("JSON-RPC server starting")

        while self.running:
            try:
                # Read stdin asynchronously (non-blocking)
                line = await loop.run_in_executor(None, sys.stdin.readline)

                if not line:  # EOF
                    logger.info("EOF received, shutting down")
                    break

                line = line.strip()
                if not line:  # Empty line
                    continue

                try:
                    request = json.loads(line)
                    logger.debug(f"Received request: {request.get('method', 'unknown')}")

                    response = await self.handle_request(request)

                    print(json.dumps(response), flush=True)
                    logger.debug(f"Sent response for: {request.get('method', 'unknown')}")

                except json.JSONDecodeError as e:
                    logger.error(f"JSON parse error: {e}")
                    error = self._error_response(None, -32700, f"Parse error: {str(e)}")
                    print(json.dumps(error), flush=True)

            except Exception as e:
                logger.error(f"Error in server loop: {e}", exc_info=True)
                # Continue running even if one request fails
                continue

        logger.info("JSON-RPC server stopped")

    def stop(self) -> None:
        """Stop the server."""
        self.running = False
