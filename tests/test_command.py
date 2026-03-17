"""Tests for LLDB command passthrough tool"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from appledb_mcp.tools.command import lldb_command


@pytest.fixture
def mock_client():
    with patch("appledb_mcp.tools.command.LLDBClient") as mock_cls:
        client = MagicMock()
        mock_cls.get_instance.return_value = client
        yield client


class TestLLDBCommand:

    @pytest.mark.asyncio
    async def test_command_with_output(self, mock_client):
        mock_client.execute_command = AsyncMock(return_value={
            "output": "frame #0: 0x100003f20 test`main at test.c:5:3",
            "error": "",
            "success": True,
        })
        result = await lldb_command(command="bt")
        assert "frame #0" in result
        assert "test.c:5" in result
        mock_client.execute_command.assert_called_once_with("bt")

    @pytest.mark.asyncio
    async def test_command_with_error(self, mock_client):
        mock_client.execute_command = AsyncMock(return_value={
            "output": "",
            "error": "error: 'foo' is not a valid command.",
            "success": False,
        })
        result = await lldb_command(command="foo")
        assert "not a valid command" in result

    @pytest.mark.asyncio
    async def test_command_with_both_output_and_error(self, mock_client):
        mock_client.execute_command = AsyncMock(return_value={
            "output": "some output",
            "error": "warning: something",
            "success": True,
        })
        result = await lldb_command(command="some_cmd")
        assert "some output" in result
        assert "warning:" in result

    @pytest.mark.asyncio
    async def test_command_empty_output(self, mock_client):
        mock_client.execute_command = AsyncMock(return_value={
            "output": "",
            "error": "",
            "success": True,
        })
        result = await lldb_command(command="settings set auto-confirm true")
        assert "(no output)" in result

    @pytest.mark.asyncio
    async def test_command_help(self, mock_client):
        mock_client.execute_command = AsyncMock(return_value={
            "output": "Debugger commands:\n  bt -- ...\n  breakpoint -- ...",
            "error": "",
            "success": True,
        })
        result = await lldb_command(command="help")
        assert "Debugger commands" in result
