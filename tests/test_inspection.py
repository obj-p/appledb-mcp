"""Tests for inspection MCP tools"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from appledb_mcp.tools.inspection import lldb_evaluate, lldb_get_backtrace, lldb_get_variables
from appledb_mcp.utils.errors import InvalidStateError, ProcessNotAttachedError


@pytest.fixture
def mock_client():
    """Patch LLDBClient.get_instance() to return a mock client with AsyncMock methods."""
    with patch("appledb_mcp.tools.inspection.LLDBClient") as mock_cls:
        client = MagicMock()
        client.evaluate_expression = AsyncMock()
        client.get_backtrace = AsyncMock()
        client.get_variables = AsyncMock()
        mock_cls.get_instance.return_value = client
        yield client


class TestLLDBEvaluate:
    """Tests for lldb_evaluate tool"""

    @pytest.mark.asyncio
    async def test_evaluate_simple_expression(self, mock_client):
        """Test evaluating a simple expression"""
        mock_client.evaluate_expression.return_value = {
            "value": "42",
            "type": "int",
            "summary": None,
            "error": None,
        }

        result = await lldb_evaluate(expression="myVariable")

        assert "✓" in result
        assert "myVariable" in result
        assert "int" in result
        assert "42" in result
        mock_client.evaluate_expression.assert_called_once_with(
            expression="myVariable",
            language=None,
            frame_index=0,
        )

    @pytest.mark.asyncio
    async def test_evaluate_with_language(self, mock_client):
        """Test evaluating with specific language"""
        mock_client.evaluate_expression.return_value = {
            "value": "0x00007ff8",
            "type": "String",
            "summary": '"Hello"',
            "error": None,
        }

        result = await lldb_evaluate(expression="self", language="swift")

        assert "✓" in result
        assert "self" in result
        assert "String" in result
        assert '"Hello"' in result
        mock_client.evaluate_expression.assert_called_once_with(
            expression="self",
            language="swift",
            frame_index=0,
        )

    @pytest.mark.asyncio
    async def test_evaluate_with_frame_index(self, mock_client):
        """Test evaluating in specific frame"""
        mock_client.evaluate_expression.return_value = {
            "value": "123",
            "type": "long",
            "summary": None,
            "error": None,
        }

        result = await lldb_evaluate(expression="argc", frame_index=2)

        assert "✓" in result
        mock_client.evaluate_expression.assert_called_once_with(
            expression="argc",
            language=None,
            frame_index=2,
        )

    @pytest.mark.asyncio
    async def test_evaluate_with_error(self, mock_client):
        """Test evaluation error handling"""
        mock_client.evaluate_expression.return_value = {
            "value": None,
            "type": None,
            "summary": None,
            "error": "error: use of undeclared identifier 'foo'",
        }

        result = await lldb_evaluate(expression="foo")

        assert "✗" in result
        assert "error:" in result
        assert "undeclared identifier" in result

    @pytest.mark.asyncio
    async def test_evaluate_not_attached(self, mock_client):
        """Test evaluation when not attached"""
        mock_client.evaluate_expression.side_effect = InvalidStateError(
            "Cannot evaluate: process is not stopped"
        )

        result = await lldb_evaluate(expression="test")

        assert "Error" in result
        assert "not stopped" in result


class TestLLDBGetBacktrace:
    """Tests for lldb_get_backtrace tool"""

    @pytest.mark.asyncio
    async def test_get_backtrace_basic(self, mock_client):
        """Test getting basic backtrace"""
        frames = [
            {
                "index": 0,
                "pc": "0x100001234",
                "function": "main",
                "file": "main.c",
                "line": 42,
                "module": "MyApp",
            },
            {
                "index": 1,
                "pc": "0x100002345",
                "function": "start",
                "file": None,
                "line": None,
                "module": "libdyld.dylib",
            },
        ]
        mock_client.get_backtrace.return_value = frames

        result = await lldb_get_backtrace()

        assert "✓" in result
        assert "2 frames" in result
        assert "#0: main" in result
        assert "main.c:42" in result
        assert "#1: start" in result
        assert "0x100002345" in result
        mock_client.get_backtrace.assert_called_once_with(
            thread_id=None, max_frames=None
        )

    @pytest.mark.asyncio
    async def test_get_backtrace_with_thread_id(self, mock_client):
        """Test getting backtrace for specific thread"""
        mock_client.get_backtrace.return_value = []

        result = await lldb_get_backtrace(thread_id=5)

        mock_client.get_backtrace.assert_called_once_with(
            thread_id=5, max_frames=None
        )

    @pytest.mark.asyncio
    async def test_get_backtrace_with_max_frames(self, mock_client):
        """Test getting backtrace with frame limit"""
        mock_client.get_backtrace.return_value = [
            {
                "index": i,
                "pc": hex(0x100000000 + i * 0x1000),
                "function": f"func{i}",
                "file": None,
                "line": None,
                "module": "test",
            }
            for i in range(10)
        ]

        result = await lldb_get_backtrace(max_frames=10)

        assert "10 frames" in result
        mock_client.get_backtrace.assert_called_once_with(
            thread_id=None, max_frames=10
        )

    @pytest.mark.asyncio
    async def test_get_backtrace_empty(self, mock_client):
        """Test backtrace with no frames"""
        mock_client.get_backtrace.return_value = []

        result = await lldb_get_backtrace()

        assert "No frames available" in result

    @pytest.mark.asyncio
    async def test_get_backtrace_not_attached(self, mock_client):
        """Test backtrace when not attached"""
        mock_client.get_backtrace.side_effect = ProcessNotAttachedError(
            "No process attached"
        )

        result = await lldb_get_backtrace()

        assert "Error" in result
        assert "process attached" in result


class TestLLDBGetVariables:
    """Tests for lldb_get_variables tool"""

    @pytest.mark.asyncio
    async def test_get_variables_basic(self, mock_client):
        """Test getting variables"""
        variables = [
            {
                "name": "argc",
                "type": "int",
                "value": "1",
                "summary": None,
            },
            {
                "name": "argv",
                "type": "char **",
                "value": "0x00007ff8",
                "summary": None,
            },
        ]
        mock_client.get_variables.return_value = variables

        result = await lldb_get_variables()

        assert "✓" in result
        assert "2 total" in result
        assert "argc: int = 1" in result
        assert "argv: char **" in result
        mock_client.get_variables.assert_called_once_with(
            frame_index=0,
            include_arguments=True,
            include_locals=True,
        )

    @pytest.mark.asyncio
    async def test_get_variables_with_summary(self, mock_client):
        """Test variables with summaries"""
        variables = [
            {
                "name": "myString",
                "type": "NSString *",
                "value": "0x00007ff9",
                "summary": '"Hello, World!"',
            },
        ]
        mock_client.get_variables.return_value = variables

        result = await lldb_get_variables()

        assert "myString: NSString *" in result
        assert "Hello, World!" in result

    @pytest.mark.asyncio
    async def test_get_variables_only_arguments(self, mock_client):
        """Test getting only arguments"""
        mock_client.get_variables.return_value = []

        result = await lldb_get_variables(include_locals=False)

        mock_client.get_variables.assert_called_once_with(
            frame_index=0,
            include_arguments=True,
            include_locals=False,
        )

    @pytest.mark.asyncio
    async def test_get_variables_only_locals(self, mock_client):
        """Test getting only locals"""
        mock_client.get_variables.return_value = []

        result = await lldb_get_variables(include_arguments=False)

        mock_client.get_variables.assert_called_once_with(
            frame_index=0,
            include_arguments=False,
            include_locals=True,
        )

    @pytest.mark.asyncio
    async def test_get_variables_different_frame(self, mock_client):
        """Test getting variables from different frame"""
        mock_client.get_variables.return_value = []

        result = await lldb_get_variables(frame_index=3)

        assert "frame 3" in result
        mock_client.get_variables.assert_called_once_with(
            frame_index=3,
            include_arguments=True,
            include_locals=True,
        )

    @pytest.mark.asyncio
    async def test_get_variables_empty(self, mock_client):
        """Test with no variables"""
        mock_client.get_variables.return_value = []

        result = await lldb_get_variables()

        assert "No variables available in frame 0" in result

    @pytest.mark.asyncio
    async def test_get_variables_not_stopped(self, mock_client):
        """Test getting variables when not stopped"""
        mock_client.get_variables.side_effect = InvalidStateError(
            "Cannot get variables: process is not stopped"
        )

        result = await lldb_get_variables()

        assert "Error" in result
        assert "not stopped" in result


class TestLLDBListThreads:
    """Tests for lldb_list_threads tool"""

    @pytest.mark.asyncio
    async def test_list_threads_basic(self, mock_client):
        mock_client.list_threads = AsyncMock(return_value=[
            {"id": 1, "name": "main", "state": "stopped", "stop_reason": "breakpoint", "is_selected": True},
            {"id": 2, "name": "worker", "state": "running", "stop_reason": "", "is_selected": False},
        ])
        from appledb_mcp.tools.inspection import lldb_list_threads
        result = await lldb_list_threads()
        assert "2 thread(s)" in result
        assert "Thread 1: main" in result
        assert "Thread 2: worker" in result
        assert "*" in result  # selected indicator

    @pytest.mark.asyncio
    async def test_list_threads_empty(self, mock_client):
        mock_client.list_threads = AsyncMock(return_value=[])
        from appledb_mcp.tools.inspection import lldb_list_threads
        result = await lldb_list_threads()
        assert "No threads available" in result

    @pytest.mark.asyncio
    async def test_list_threads_not_attached(self, mock_client):
        mock_client.list_threads = AsyncMock(
            side_effect=ProcessNotAttachedError("No process attached")
        )
        from appledb_mcp.tools.inspection import lldb_list_threads
        result = await lldb_list_threads()
        assert "Error" in result
