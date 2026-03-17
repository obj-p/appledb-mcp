"""Tests for TCP client"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import json

from appledb_mcp.tcp_client import LLDBTCPClient, _map_error
from appledb_mcp.utils.errors import LLDBError, ProcessNotAttachedError, InvalidStateError


class TestMapError:
    def test_lldb_error(self):
        err = _map_error({"code": -32000, "message": "fail"})
        assert isinstance(err, LLDBError)
        assert str(err) == "fail"

    def test_not_attached(self):
        err = _map_error({"code": -32001, "message": "no process"})
        assert isinstance(err, ProcessNotAttachedError)

    def test_invalid_state(self):
        err = _map_error({"code": -32002, "message": "bad state"})
        assert isinstance(err, InvalidStateError)

    def test_unknown_code(self):
        err = _map_error({"code": -99999, "message": "unknown"})
        assert isinstance(err, RuntimeError)


class TestLLDBTCPClient:
    @pytest.mark.asyncio
    async def test_call_success(self):
        mock_reader = AsyncMock()
        mock_writer = MagicMock()
        mock_writer.drain = AsyncMock()
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()

        response = {"jsonrpc": "2.0", "id": 1, "result": "pong"}
        mock_reader.readline = AsyncMock(
            return_value=(json.dumps(response) + "\n").encode()
        )

        with patch("appledb_mcp.tcp_client.asyncio.open_connection",
                    AsyncMock(return_value=(mock_reader, mock_writer))):
            client = LLDBTCPClient(port=5037)
            result = await client.call("ping")
            assert result == "pong"

    @pytest.mark.asyncio
    async def test_call_error_response(self):
        mock_reader = AsyncMock()
        mock_writer = MagicMock()
        mock_writer.drain = AsyncMock()
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()

        response = {"jsonrpc": "2.0", "id": 1, "error": {"code": -32001, "message": "No process"}}
        mock_reader.readline = AsyncMock(
            return_value=(json.dumps(response) + "\n").encode()
        )

        with patch("appledb_mcp.tcp_client.asyncio.open_connection",
                    AsyncMock(return_value=(mock_reader, mock_writer))):
            client = LLDBTCPClient(port=5037)
            with pytest.raises(ProcessNotAttachedError):
                await client.call("get_backtrace")

    @pytest.mark.asyncio
    async def test_ping_success(self):
        with patch.object(LLDBTCPClient, "call", AsyncMock(return_value="pong")):
            client = LLDBTCPClient()
            assert await client.ping() is True

    @pytest.mark.asyncio
    async def test_ping_failure(self):
        with patch.object(LLDBTCPClient, "call", AsyncMock(side_effect=ConnectionRefusedError)):
            client = LLDBTCPClient()
            assert await client.ping() is False
