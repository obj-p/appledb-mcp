"""Tests for heap introspection tools"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from appledb_mcp.tools.heap import (
    lldb_heap_summary,
    lldb_heap_instances,
    lldb_heap_describe,
    lldb_heap_references,
    lldb_heap_retain_cycles,
)
from appledb_mcp.utils.errors import ProcessNotAttachedError


@pytest.fixture
def mock_client():
    with patch("appledb_mcp.tools.heap.LLDBClient") as mock_cls:
        client = MagicMock()
        mock_cls.get_instance.return_value = client
        # load_framework succeeds
        client.load_framework = AsyncMock(return_value={
            "success": True, "address": 0x1000, "already_loaded": True,
            "message": "Already loaded",
        })
        yield client


def _make_eval_result(json_data):
    """Create a mock evaluate_expression result with JSON in summary field."""
    json_str = json.dumps(json_data)
    # LLDB wraps string summaries in quotes
    summary = f'"{json_str}"'
    return {"value": "0x0", "type": "NSString *", "summary": summary, "error": None}


class TestHeapSummary:
    @pytest.mark.asyncio
    async def test_summary_basic(self, mock_client):
        data = [
            {"class": "UIView", "count": 100, "totalSize": 24000},
            {"class": "NSString", "count": 500, "totalSize": 16000},
        ]
        mock_client.evaluate_expression = AsyncMock(return_value=_make_eval_result(data))

        with patch("appledb_mcp.tools.heap._FRAMEWORK_DIR") as mock_dir:
            mock_dir.__truediv__ = lambda self, x: MagicMock(
                __truediv__=lambda self, x: MagicMock(exists=lambda: True)
            )
            result = await lldb_heap_summary()

        assert "UIView" in result
        assert "NSString" in result
        assert "100" in result
        assert "500" in result

    @pytest.mark.asyncio
    async def test_summary_empty(self, mock_client):
        mock_client.evaluate_expression = AsyncMock(return_value=_make_eval_result([]))

        with patch("appledb_mcp.tools.heap._FRAMEWORK_DIR") as mock_dir:
            mock_dir.__truediv__ = lambda self, x: MagicMock(
                __truediv__=lambda self, x: MagicMock(exists=lambda: True)
            )
            result = await lldb_heap_summary()

        assert "No heap objects found" in result

    @pytest.mark.asyncio
    async def test_summary_not_attached(self, mock_client):
        mock_client.load_framework = AsyncMock(
            side_effect=ProcessNotAttachedError("No process attached")
        )

        with patch("appledb_mcp.tools.heap._FRAMEWORK_DIR") as mock_dir:
            mock_dir.__truediv__ = lambda self, x: MagicMock(
                __truediv__=lambda self, x: MagicMock(exists=lambda: True)
            )
            result = await lldb_heap_summary()

        assert "Error" in result
        assert "No process attached" in result


class TestHeapInstances:
    @pytest.mark.asyncio
    async def test_instances_found(self, mock_client):
        data = [
            {"address": "0x600001234", "size": 240, "class": "MyVC"},
            {"address": "0x600005678", "size": 240, "class": "MyVC"},
        ]
        mock_client.evaluate_expression = AsyncMock(return_value=_make_eval_result(data))

        with patch("appledb_mcp.tools.heap._FRAMEWORK_DIR") as mock_dir:
            mock_dir.__truediv__ = lambda self, x: MagicMock(
                __truediv__=lambda self, x: MagicMock(exists=lambda: True)
            )
            result = await lldb_heap_instances(class_name="MyVC")

        assert "2 instance(s)" in result
        assert "0x600001234" in result
        assert "0x600005678" in result

    @pytest.mark.asyncio
    async def test_instances_none(self, mock_client):
        mock_client.evaluate_expression = AsyncMock(return_value=_make_eval_result([]))

        with patch("appledb_mcp.tools.heap._FRAMEWORK_DIR") as mock_dir:
            mock_dir.__truediv__ = lambda self, x: MagicMock(
                __truediv__=lambda self, x: MagicMock(exists=lambda: True)
            )
            result = await lldb_heap_instances(class_name="Nonexistent")

        assert "No instances" in result


class TestHeapDescribe:
    @pytest.mark.asyncio
    async def test_describe_object(self, mock_client):
        data = {
            "address": "0x600001234",
            "class": "MyViewController",
            "size": 480,
            "superclasses": ["UIViewController", "UIResponder", "NSObject"],
            "ivars": [],
            "properties": [{"name": "title"}],
            "ivarValues": [
                {"name": "view", "type": "@", "class": "UIView", "address": "0x600009999"},
                {"name": "count", "type": "i", "value": "42"},
            ],
        }
        mock_client.evaluate_expression = AsyncMock(return_value=_make_eval_result(data))

        with patch("appledb_mcp.tools.heap._FRAMEWORK_DIR") as mock_dir:
            mock_dir.__truediv__ = lambda self, x: MagicMock(
                __truediv__=lambda self, x: MagicMock(exists=lambda: True)
            )
            result = await lldb_heap_describe(address="0x600001234")

        assert "MyViewController" in result
        assert "UIViewController" in result
        assert "UIView" in result
        assert "42" in result


class TestHeapReferences:
    @pytest.mark.asyncio
    async def test_references(self, mock_client):
        data = [
            {"ivar": "view", "address": "0x600009999", "class": "UIView"},
            {"ivar": "delegate", "address": "0x600008888", "class": "AppDelegate"},
        ]
        mock_client.evaluate_expression = AsyncMock(return_value=_make_eval_result(data))

        with patch("appledb_mcp.tools.heap._FRAMEWORK_DIR") as mock_dir:
            mock_dir.__truediv__ = lambda self, x: MagicMock(
                __truediv__=lambda self, x: MagicMock(exists=lambda: True)
            )
            result = await lldb_heap_references(address="0x600001234")

        assert "2 reference(s)" in result
        assert ".view" in result
        assert "UIView" in result

    @pytest.mark.asyncio
    async def test_no_references(self, mock_client):
        mock_client.evaluate_expression = AsyncMock(return_value=_make_eval_result([]))

        with patch("appledb_mcp.tools.heap._FRAMEWORK_DIR") as mock_dir:
            mock_dir.__truediv__ = lambda self, x: MagicMock(
                __truediv__=lambda self, x: MagicMock(exists=lambda: True)
            )
            result = await lldb_heap_references(address="0x600001234")

        assert "No outbound references" in result


class TestHeapRetainCycles:
    @pytest.mark.asyncio
    async def test_cycle_found(self, mock_client):
        data = [
            {"cycle": [
                "0x1 (ViewControllerA)",
                "0x2 (ViewControllerB)",
                "0x1 (ViewControllerA)",
            ]},
        ]
        mock_client.evaluate_expression = AsyncMock(return_value=_make_eval_result(data))

        with patch("appledb_mcp.tools.heap._FRAMEWORK_DIR") as mock_dir:
            mock_dir.__truediv__ = lambda self, x: MagicMock(
                __truediv__=lambda self, x: MagicMock(exists=lambda: True)
            )
            result = await lldb_heap_retain_cycles(address="0x1")

        assert "1 retain cycle(s)" in result
        assert "ViewControllerA" in result
        assert "ViewControllerB" in result

    @pytest.mark.asyncio
    async def test_no_cycles(self, mock_client):
        mock_client.evaluate_expression = AsyncMock(return_value=_make_eval_result([]))

        with patch("appledb_mcp.tools.heap._FRAMEWORK_DIR") as mock_dir:
            mock_dir.__truediv__ = lambda self, x: MagicMock(
                __truediv__=lambda self, x: MagicMock(exists=lambda: True)
            )
            result = await lldb_heap_retain_cycles(address="0x1")

        assert "No retain cycles" in result
