"""TCP JSON-RPC 2.0 server for persistent LLDB service"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Optional

from .server import JSONRPCServer

logger = logging.getLogger(__name__)

# Default port matching ADB convention
DEFAULT_PORT = 5037
STATE_DIR = Path.home() / ".appledb"


class TCPJSONRPCServer(JSONRPCServer):
    """JSON-RPC 2.0 server over TCP.

    Extends JSONRPCServer with TCP transport. All handler registration
    and request dispatching is inherited — only the I/O transport changes.
    Supports multiple concurrent client connections.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = DEFAULT_PORT):
        super().__init__()
        self.host = host
        self.port = port
        self._server: Optional[asyncio.AbstractServer] = None

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        """Handle a single client connection.

        Reads one JSON-RPC request, processes it, sends the response, and closes.
        This matches the ephemeral client pattern (connect, send, receive, disconnect).
        """
        addr = writer.get_extra_info("peername")
        logger.debug(f"Client connected from {addr}")

        try:
            while True:
                line = await reader.readline()
                if not line:  # Client disconnected
                    break

                line_str = line.decode().strip()
                if not line_str:
                    continue

                try:
                    request = json.loads(line_str)
                    logger.debug(f"Received request: {request.get('method', 'unknown')}")

                    response = await self.handle_request(request)

                    response_bytes = (json.dumps(response) + "\n").encode()
                    writer.write(response_bytes)
                    await writer.drain()
                    logger.debug(f"Sent response for: {request.get('method', 'unknown')}")

                except json.JSONDecodeError as e:
                    logger.error(f"JSON parse error: {e}")
                    error = self._error_response(None, -32700, f"Parse error: {str(e)}")
                    writer.write((json.dumps(error) + "\n").encode())
                    await writer.drain()

        except (ConnectionResetError, BrokenPipeError):
            logger.debug(f"Client {addr} disconnected")
        except Exception as e:
            logger.error(f"Error handling client {addr}: {e}", exc_info=True)
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
            logger.debug(f"Client {addr} connection closed")

    def _write_state_files(self) -> None:
        """Write PID and port to state directory for CLI discovery."""
        STATE_DIR.mkdir(parents=True, exist_ok=True)

        pid_file = STATE_DIR / "server.pid"
        pid_file.write_text(str(os.getpid()))

        port_file = STATE_DIR / "server.port"
        port_file.write_text(str(self.port))

        logger.info(f"State files written to {STATE_DIR}")

    def _cleanup_state_files(self) -> None:
        """Remove state files on shutdown."""
        for name in ("server.pid", "server.port"):
            state_file = STATE_DIR / name
            try:
                state_file.unlink(missing_ok=True)
            except Exception as e:
                logger.warning(f"Failed to remove {state_file}: {e}")

    async def run(self) -> None:
        """Start TCP server and serve until stopped."""
        self.running = True

        self._server = await asyncio.start_server(
            self.handle_client, self.host, self.port
        )

        self._write_state_files()

        addrs = ", ".join(str(s.getsockname()) for s in self._server.sockets)
        logger.info(f"LLDB server listening on {addrs}")
        print(f"LLDB server listening on {self.host}:{self.port}", file=sys.stderr)

        try:
            async with self._server:
                await self._server.serve_forever()
        finally:
            self._cleanup_state_files()
            logger.info("TCP server stopped")

    def stop(self) -> None:
        """Stop the TCP server."""
        self.running = False
        if self._server:
            self._server.close()
