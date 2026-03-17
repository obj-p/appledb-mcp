"""Tests for breakpoint management tools"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from appledb_mcp.tools.breakpoint import (
    lldb_set_breakpoint,
    lldb_list_breakpoints,
    lldb_delete_breakpoint,
)
from appledb_mcp.utils.errors import LLDBError, ProcessNotAttachedError


@pytest.fixture
def mock_client():
    with patch("appledb_mcp.tools.breakpoint.LLDBClient") as mock_cls:
        client = MagicMock()
        mock_cls.get_instance.return_value = client
        yield client


class TestSetBreakpoint:
    @pytest.mark.asyncio
    async def test_set_by_location(self, mock_client):
        mock_client.set_breakpoint = AsyncMock(return_value={
            "id": 1, "locations": 1, "enabled": True, "hit_count": 0,
            "condition": None, "file": "main.c", "line": 42, "symbol": None,
        })
        result = await lldb_set_breakpoint(file="main.c", line=42)
        assert "Breakpoint 1 set" in result
        assert "main.c:42" in result
        mock_client.set_breakpoint.assert_called_once_with(
            file="main.c", line=42, symbol=None, module=None, condition=None
        )

    @pytest.mark.asyncio
    async def test_set_by_symbol(self, mock_client):
        mock_client.set_breakpoint = AsyncMock(return_value={
            "id": 2, "locations": 3, "enabled": True, "hit_count": 0,
            "condition": None, "file": None, "line": None, "symbol": "main",
        })
        result = await lldb_set_breakpoint(symbol="main")
        assert "Breakpoint 2 set" in result
        assert "'main'" in result
        assert "Locations: 3" in result

    @pytest.mark.asyncio
    async def test_set_with_condition(self, mock_client):
        mock_client.set_breakpoint = AsyncMock(return_value={
            "id": 3, "locations": 1, "enabled": True, "hit_count": 0,
            "condition": "x > 10", "file": "test.c", "line": 5, "symbol": None,
        })
        result = await lldb_set_breakpoint(file="test.c", line=5, condition="x > 10")
        assert "Condition: x > 10" in result

    @pytest.mark.asyncio
    async def test_set_no_params(self, mock_client):
        mock_client.set_breakpoint = AsyncMock(
            side_effect=ValueError("Must specify file+line or symbol")
        )
        result = await lldb_set_breakpoint()
        assert "Error" in result

    @pytest.mark.asyncio
    async def test_set_not_attached(self, mock_client):
        mock_client.set_breakpoint = AsyncMock(
            side_effect=ProcessNotAttachedError("No process attached")
        )
        result = await lldb_set_breakpoint(symbol="main")
        assert "Error" in result
        assert "No process attached" in result


class TestListBreakpoints:
    @pytest.mark.asyncio
    async def test_list_with_breakpoints(self, mock_client):
        mock_client.list_breakpoints = AsyncMock(return_value=[
            {"id": 1, "locations": 1, "enabled": True, "hit_count": 2,
             "condition": None, "file": "main.c", "line": 10, "symbol": None},
            {"id": 2, "locations": 3, "enabled": False, "hit_count": 0,
             "condition": "x > 5", "file": None, "line": None, "symbol": "malloc"},
        ])
        result = await lldb_list_breakpoints()
        assert "2 breakpoint(s)" in result
        assert "#1: enabled" in result
        assert "main.c:10" in result
        assert "#2: disabled" in result
        assert "malloc" in result
        assert "condition: x > 5" in result

    @pytest.mark.asyncio
    async def test_list_empty(self, mock_client):
        mock_client.list_breakpoints = AsyncMock(return_value=[])
        result = await lldb_list_breakpoints()
        assert "No breakpoints set" in result

    @pytest.mark.asyncio
    async def test_list_not_attached(self, mock_client):
        mock_client.list_breakpoints = AsyncMock(
            side_effect=ProcessNotAttachedError("No process attached")
        )
        result = await lldb_list_breakpoints()
        assert "Error" in result


class TestDeleteBreakpoint:
    @pytest.mark.asyncio
    async def test_delete_success(self, mock_client):
        mock_client.delete_breakpoint = AsyncMock(return_value=True)
        result = await lldb_delete_breakpoint(breakpoint_id=1)
        assert "Breakpoint 1 deleted" in result
        mock_client.delete_breakpoint.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_delete_not_found(self, mock_client):
        mock_client.delete_breakpoint = AsyncMock(
            side_effect=LLDBError("Failed to delete breakpoint 999")
        )
        result = await lldb_delete_breakpoint(breakpoint_id=999)
        assert "Error" in result

    @pytest.mark.asyncio
    async def test_delete_not_attached(self, mock_client):
        mock_client.delete_breakpoint = AsyncMock(
            side_effect=ProcessNotAttachedError("No process attached")
        )
        result = await lldb_delete_breakpoint(breakpoint_id=1)
        assert "Error" in result
