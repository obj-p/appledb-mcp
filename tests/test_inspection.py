"""Tests for inspection MCP tools"""

from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from appledb_mcp.debugger import LLDBDebuggerManager, ProcessState
from appledb_mcp.tools.inspection import lldb_evaluate, lldb_get_backtrace, lldb_get_variables
from appledb_mcp.utils.errors import InvalidStateError, ProcessNotAttachedError


@pytest.fixture
def mock_value():
    """Mock LLDB SBValue for expression evaluation"""
    value = MagicMock()
    value.GetValue.return_value = "42"
    value.GetTypeName.return_value = "int"
    value.GetSummary.return_value = None

    # Mock error
    error = MagicMock()
    error.Fail.return_value = False
    error.GetCString.return_value = ""
    value.GetError.return_value = error

    return value


@pytest.fixture
def mock_value_with_error():
    """Mock LLDB SBValue with evaluation error"""
    value = MagicMock()
    value.GetValue.return_value = None
    value.GetTypeName.return_value = None
    value.GetSummary.return_value = None

    # Mock error
    error = MagicMock()
    error.Fail.return_value = True
    error.GetCString.return_value = "error: use of undeclared identifier 'foo'"
    value.GetError.return_value = error

    return value


@pytest.fixture
def mock_value_with_summary():
    """Mock LLDB SBValue with summary"""
    value = MagicMock()
    value.GetValue.return_value = "0x00007ff8"
    value.GetTypeName.return_value = "NSString *"
    value.GetSummary.return_value = '"Hello, World!"'

    # Mock error
    error = MagicMock()
    error.Fail.return_value = False
    error.GetCString.return_value = ""
    value.GetError.return_value = error

    return value


@pytest.fixture
def mock_frame_with_evaluation(mock_value):
    """Mock LLDB frame with expression evaluation"""
    frame = MagicMock()
    frame.IsValid.return_value = True
    frame.EvaluateExpression.return_value = mock_value
    return frame


@pytest.fixture
def mock_variables():
    """Mock LLDB SBValueList for variables"""
    value_list = MagicMock()
    value_list.GetSize.return_value = 3

    # Create mock variables
    var1 = MagicMock()
    var1.IsValid.return_value = True
    var1.GetName.return_value = "argc"
    var1.GetTypeName.return_value = "int"
    var1.GetValue.return_value = "1"
    var1.GetSummary.return_value = None

    var2 = MagicMock()
    var2.IsValid.return_value = True
    var2.GetName.return_value = "argv"
    var2.GetTypeName.return_value = "char **"
    var2.GetValue.return_value = "0x00007ff8"
    var2.GetSummary.return_value = None

    var3 = MagicMock()
    var3.IsValid.return_value = True
    var3.GetName.return_value = "myString"
    var3.GetTypeName.return_value = "NSString *"
    var3.GetValue.return_value = "0x00007ff9"
    var3.GetSummary.return_value = '"Test"'

    value_list.GetValueAtIndex.side_effect = [var1, var2, var3]

    return value_list


class TestLLDBEvaluate:
    """Tests for lldb_evaluate tool"""

    @pytest.mark.asyncio
    async def test_evaluate_simple_expression(self, mock_value):
        """Test evaluating a simple expression"""
        manager = LLDBDebuggerManager.get_instance()
        manager._state = ProcessState.ATTACHED_STOPPED

        with patch.object(manager, 'evaluate_expression', new_callable=AsyncMock) as mock_eval:
            mock_eval.return_value = {
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
            mock_eval.assert_called_once_with(
                expression="myVariable",
                language=None,
                frame_index=0,
            )

    @pytest.mark.asyncio
    async def test_evaluate_with_language(self):
        """Test evaluating with specific language"""
        manager = LLDBDebuggerManager.get_instance()
        manager._state = ProcessState.ATTACHED_STOPPED

        with patch.object(manager, 'evaluate_expression', new_callable=AsyncMock) as mock_eval:
            mock_eval.return_value = {
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
            mock_eval.assert_called_once_with(
                expression="self",
                language="swift",
                frame_index=0,
            )

    @pytest.mark.asyncio
    async def test_evaluate_with_frame_index(self):
        """Test evaluating in specific frame"""
        manager = LLDBDebuggerManager.get_instance()
        manager._state = ProcessState.ATTACHED_STOPPED

        with patch.object(manager, 'evaluate_expression', new_callable=AsyncMock) as mock_eval:
            mock_eval.return_value = {
                "value": "123",
                "type": "long",
                "summary": None,
                "error": None,
            }

            result = await lldb_evaluate(expression="argc", frame_index=2)

            assert "✓" in result
            mock_eval.assert_called_once_with(
                expression="argc",
                language=None,
                frame_index=2,
            )

    @pytest.mark.asyncio
    async def test_evaluate_with_error(self):
        """Test evaluation error handling"""
        manager = LLDBDebuggerManager.get_instance()
        manager._state = ProcessState.ATTACHED_STOPPED

        with patch.object(manager, 'evaluate_expression', new_callable=AsyncMock) as mock_eval:
            mock_eval.return_value = {
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
    async def test_evaluate_not_attached(self):
        """Test evaluation when not attached"""
        manager = LLDBDebuggerManager.get_instance()
        manager._state = ProcessState.DETACHED

        with patch.object(manager, 'evaluate_expression', new_callable=AsyncMock) as mock_eval:
            mock_eval.side_effect = InvalidStateError("Cannot evaluate: process is not stopped")

            result = await lldb_evaluate(expression="test")

            assert "Error" in result
            assert "not stopped" in result


class TestLLDBGetBacktrace:
    """Tests for lldb_get_backtrace tool"""

    @pytest.mark.asyncio
    async def test_get_backtrace_basic(self):
        """Test getting basic backtrace"""
        manager = LLDBDebuggerManager.get_instance()
        manager._state = ProcessState.ATTACHED_STOPPED

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

        with patch.object(manager, 'get_backtrace', new_callable=AsyncMock) as mock_bt:
            mock_bt.return_value = frames

            result = await lldb_get_backtrace()

            assert "✓" in result
            assert "2 frames" in result
            assert "#0: main" in result
            assert "main.c:42" in result
            assert "#1: start" in result
            assert "0x100002345" in result
            mock_bt.assert_called_once_with(thread_id=None, max_frames=None)

    @pytest.mark.asyncio
    async def test_get_backtrace_with_thread_id(self):
        """Test getting backtrace for specific thread"""
        manager = LLDBDebuggerManager.get_instance()
        manager._state = ProcessState.ATTACHED_STOPPED

        with patch.object(manager, 'get_backtrace', new_callable=AsyncMock) as mock_bt:
            mock_bt.return_value = []

            result = await lldb_get_backtrace(thread_id=5)

            mock_bt.assert_called_once_with(thread_id=5, max_frames=None)

    @pytest.mark.asyncio
    async def test_get_backtrace_with_max_frames(self):
        """Test getting backtrace with frame limit"""
        manager = LLDBDebuggerManager.get_instance()
        manager._state = ProcessState.ATTACHED_STOPPED

        with patch.object(manager, 'get_backtrace', new_callable=AsyncMock) as mock_bt:
            mock_bt.return_value = [{"index": i, "pc": hex(0x100000000 + i*0x1000),
                                    "function": f"func{i}", "file": None, "line": None,
                                    "module": "test"} for i in range(10)]

            result = await lldb_get_backtrace(max_frames=10)

            assert "10 frames" in result
            mock_bt.assert_called_once_with(thread_id=None, max_frames=10)

    @pytest.mark.asyncio
    async def test_get_backtrace_empty(self):
        """Test backtrace with no frames"""
        manager = LLDBDebuggerManager.get_instance()
        manager._state = ProcessState.ATTACHED_STOPPED

        with patch.object(manager, 'get_backtrace', new_callable=AsyncMock) as mock_bt:
            mock_bt.return_value = []

            result = await lldb_get_backtrace()

            assert "No frames available" in result

    @pytest.mark.asyncio
    async def test_get_backtrace_not_attached(self):
        """Test backtrace when not attached"""
        manager = LLDBDebuggerManager.get_instance()
        manager._state = ProcessState.DETACHED

        with patch.object(manager, 'get_backtrace', new_callable=AsyncMock) as mock_bt:
            mock_bt.side_effect = ProcessNotAttachedError("No process attached")

            result = await lldb_get_backtrace()

            assert "Error" in result
            assert "process attached" in result


class TestLLDBGetVariables:
    """Tests for lldb_get_variables tool"""

    @pytest.mark.asyncio
    async def test_get_variables_basic(self):
        """Test getting variables"""
        manager = LLDBDebuggerManager.get_instance()
        manager._state = ProcessState.ATTACHED_STOPPED

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

        with patch.object(manager, 'get_variables', new_callable=AsyncMock) as mock_vars:
            mock_vars.return_value = variables

            result = await lldb_get_variables()

            assert "✓" in result
            assert "2 total" in result
            assert "argc: int = 1" in result
            assert "argv: char **" in result
            mock_vars.assert_called_once_with(
                frame_index=0,
                include_arguments=True,
                include_locals=True,
            )

    @pytest.mark.asyncio
    async def test_get_variables_with_summary(self):
        """Test variables with summaries"""
        manager = LLDBDebuggerManager.get_instance()
        manager._state = ProcessState.ATTACHED_STOPPED

        variables = [
            {
                "name": "myString",
                "type": "NSString *",
                "value": "0x00007ff9",
                "summary": '"Hello, World!"',
            },
        ]

        with patch.object(manager, 'get_variables', new_callable=AsyncMock) as mock_vars:
            mock_vars.return_value = variables

            result = await lldb_get_variables()

            assert "myString: NSString *" in result
            assert "Hello, World!" in result

    @pytest.mark.asyncio
    async def test_get_variables_only_arguments(self):
        """Test getting only arguments"""
        manager = LLDBDebuggerManager.get_instance()
        manager._state = ProcessState.ATTACHED_STOPPED

        with patch.object(manager, 'get_variables', new_callable=AsyncMock) as mock_vars:
            mock_vars.return_value = []

            result = await lldb_get_variables(include_locals=False)

            mock_vars.assert_called_once_with(
                frame_index=0,
                include_arguments=True,
                include_locals=False,
            )

    @pytest.mark.asyncio
    async def test_get_variables_only_locals(self):
        """Test getting only locals"""
        manager = LLDBDebuggerManager.get_instance()
        manager._state = ProcessState.ATTACHED_STOPPED

        with patch.object(manager, 'get_variables', new_callable=AsyncMock) as mock_vars:
            mock_vars.return_value = []

            result = await lldb_get_variables(include_arguments=False)

            mock_vars.assert_called_once_with(
                frame_index=0,
                include_arguments=False,
                include_locals=True,
            )

    @pytest.mark.asyncio
    async def test_get_variables_different_frame(self):
        """Test getting variables from different frame"""
        manager = LLDBDebuggerManager.get_instance()
        manager._state = ProcessState.ATTACHED_STOPPED

        with patch.object(manager, 'get_variables', new_callable=AsyncMock) as mock_vars:
            mock_vars.return_value = []

            result = await lldb_get_variables(frame_index=3)

            assert "frame 3" in result
            mock_vars.assert_called_once_with(
                frame_index=3,
                include_arguments=True,
                include_locals=True,
            )

    @pytest.mark.asyncio
    async def test_get_variables_empty(self):
        """Test with no variables"""
        manager = LLDBDebuggerManager.get_instance()
        manager._state = ProcessState.ATTACHED_STOPPED

        with patch.object(manager, 'get_variables', new_callable=AsyncMock) as mock_vars:
            mock_vars.return_value = []

            result = await lldb_get_variables()

            assert "No variables available in frame 0" in result

    @pytest.mark.asyncio
    async def test_get_variables_not_stopped(self):
        """Test getting variables when not stopped"""
        manager = LLDBDebuggerManager.get_instance()
        manager._state = ProcessState.ATTACHED_RUNNING

        with patch.object(manager, 'get_variables', new_callable=AsyncMock) as mock_vars:
            mock_vars.side_effect = InvalidStateError("Cannot get variables: process is not stopped")

            result = await lldb_get_variables()

            assert "Error" in result
            assert "not stopped" in result
