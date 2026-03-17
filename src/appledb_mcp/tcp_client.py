"""Ephemeral TCP client for JSON-RPC communication with LLDB server"""

import asyncio
import json
import logging
from typing import Any, Dict, Optional

from .utils.errors import (
    FrameworkLoadError,
    InvalidStateError,
    LLDBError,
    ProcessNotAttachedError,
    ProcessNotFoundError,
)

logger = logging.getLogger(__name__)

DEFAULT_PORT = 5037


def _map_error(error: Dict) -> Exception:
    """Map JSON-RPC error codes to Python exceptions."""
    code = error.get("code", -32603)
    message = error.get("message", "Unknown error")
    error_map = {
        -32000: LLDBError,
        -32001: ProcessNotAttachedError,
        -32002: InvalidStateError,
        -32003: ProcessNotFoundError,
        -32004: FrameworkLoadError,
        -32602: ValueError,
    }
    exception_class = error_map.get(code, RuntimeError)
    return exception_class(message)


class LLDBTCPClient:
    """Ephemeral TCP client for JSON-RPC.

    Each call opens a connection, sends one request, gets the response,
    and closes. No persistent connections. Like ADB's client model.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = DEFAULT_PORT):
        self.host = host
        self.port = port

    async def call(self, method: str, params: Optional[Dict] = None, timeout: float = 30.0) -> Any:
        """Send a JSON-RPC request and return the result.

        Args:
            method: RPC method name
            params: Method parameters
            timeout: Request timeout in seconds

        Returns:
            Result from the server

        Raises:
            ConnectionRefusedError: If server is not running
            RuntimeError: If request times out
            LLDBError/etc: Mapped from JSON-RPC error codes
        """
        params = params or {}

        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(self.host, self.port),
            timeout=5.0,
        )

        try:
            request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": method,
                "params": params,
            }
            writer.write((json.dumps(request) + "\n").encode())
            await writer.drain()

            line = await asyncio.wait_for(reader.readline(), timeout=timeout)
            if not line:
                raise RuntimeError("Server closed connection without response")

            response = json.loads(line.decode().strip())

            if "error" in response:
                raise _map_error(response["error"])

            return response.get("result")
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    async def ping(self) -> bool:
        """Check if server is reachable."""
        try:
            result = await self.call("ping", timeout=3.0)
            return result == "pong"
        except Exception:
            return False
