"""Tests for execution control tools"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from appledb_mcp.tools import execution
from appledb_mcp.utils.errors import InvalidStateError, ProcessNotAttachedError


@pytest.fixture
def mock_manager():
    """Mock debugger manager"""
    with patch("appledb_mcp.tools.execution.LLDBDebuggerManager.get_instance") as mock:
        manager = MagicMock()
        mock.return_value = manager
        yield manager


class TestContinue:
    """Tests for lldb_continue tool"""

    @pytest.mark.asyncio
    async def test_continue_success(self, mock_manager):
        """Test successful continue"""
        mock_manager.continue_execution = AsyncMock(return_value="running")

        result = await execution.lldb_continue()

        assert "✓ Execution continued" in result
        assert "running" in result
        mock_manager.continue_execution.assert_called_once()

    @pytest.mark.asyncio
    async def test_continue_not_stopped(self, mock_manager):
        """Test continue when not stopped"""
        mock_manager.continue_execution = AsyncMock(
            side_effect=InvalidStateError("Cannot continue: process is not stopped (state: running)")
        )

        result = await execution.lldb_continue()

        assert "Error:" in result
        assert "not stopped" in result

    @pytest.mark.asyncio
    async def test_continue_not_attached(self, mock_manager):
        """Test continue when not attached"""
        mock_manager.continue_execution = AsyncMock(
            side_effect=ProcessNotAttachedError("No process attached")
        )

        result = await execution.lldb_continue()

        assert "Error:" in result
        assert "process attached" in result.lower()


class TestPause:
    """Tests for lldb_pause tool"""

    @pytest.mark.asyncio
    async def test_pause_success(self, mock_manager):
        """Test successful pause"""
        mock_manager.pause_execution = AsyncMock(
            return_value="Stop reason: signal\nLocation: main at test.c:10"
        )

        result = await execution.lldb_pause()

        assert "✓ Execution paused" in result
        assert "Stop reason:" in result
        mock_manager.pause_execution.assert_called_once()

    @pytest.mark.asyncio
    async def test_pause_not_running(self, mock_manager):
        """Test pause when not running"""
        mock_manager.pause_execution = AsyncMock(
            side_effect=InvalidStateError("Cannot pause: process is not running (state: stopped)")
        )

        result = await execution.lldb_pause()

        assert "Error:" in result
        assert "not running" in result

    @pytest.mark.asyncio
    async def test_pause_not_attached(self, mock_manager):
        """Test pause when not attached"""
        mock_manager.pause_execution = AsyncMock(
            side_effect=ProcessNotAttachedError("No process attached")
        )

        result = await execution.lldb_pause()

        assert "Error:" in result
        assert "process attached" in result.lower()


class TestStepOver:
    """Tests for lldb_step_over tool"""

    @pytest.mark.asyncio
    async def test_step_over_success(self, mock_manager):
        """Test successful step over"""
        mock_manager.step_over = AsyncMock(
            return_value="Location: func at file.c:42"
        )

        result = await execution.lldb_step_over()

        assert "✓ Stepped over" in result
        assert "Location:" in result
        mock_manager.step_over.assert_called_once_with(thread_id=None)

    @pytest.mark.asyncio
    async def test_step_over_with_thread_id(self, mock_manager):
        """Test step over with specific thread ID"""
        mock_manager.step_over = AsyncMock(
            return_value="Location: func at file.c:42"
        )

        result = await execution.lldb_step_over(thread_id=123)

        assert "✓ Stepped over" in result
        mock_manager.step_over.assert_called_once_with(thread_id=123)

    @pytest.mark.asyncio
    async def test_step_over_not_stopped(self, mock_manager):
        """Test step over when not stopped"""
        mock_manager.step_over = AsyncMock(
            side_effect=InvalidStateError("Cannot step: process is not stopped")
        )

        result = await execution.lldb_step_over()

        assert "Error:" in result
        assert "not stopped" in result

    @pytest.mark.asyncio
    async def test_step_over_invalid_thread(self, mock_manager):
        """Test step over with invalid thread ID"""
        mock_manager.step_over = AsyncMock(
            side_effect=ValueError("Invalid thread ID: 999")
        )

        result = await execution.lldb_step_over(thread_id=999)

        assert "Error:" in result
        assert "Invalid thread" in result or "999" in result


class TestStepInto:
    """Tests for lldb_step_into tool"""

    @pytest.mark.asyncio
    async def test_step_into_success(self, mock_manager):
        """Test successful step into"""
        mock_manager.step_into = AsyncMock(
            return_value="Location: inner_func at file.c:10"
        )

        result = await execution.lldb_step_into()

        assert "✓ Stepped into" in result
        assert "Location:" in result
        mock_manager.step_into.assert_called_once_with(thread_id=None)

    @pytest.mark.asyncio
    async def test_step_into_with_thread_id(self, mock_manager):
        """Test step into with specific thread ID"""
        mock_manager.step_into = AsyncMock(
            return_value="Location: inner_func at file.c:10"
        )

        result = await execution.lldb_step_into(thread_id=456)

        assert "✓ Stepped into" in result
        mock_manager.step_into.assert_called_once_with(thread_id=456)


class TestStepOut:
    """Tests for lldb_step_out tool"""

    @pytest.mark.asyncio
    async def test_step_out_success(self, mock_manager):
        """Test successful step out"""
        mock_manager.step_out = AsyncMock(
            return_value="Location: caller at file.c:20"
        )

        result = await execution.lldb_step_out()

        assert "✓ Stepped out" in result
        assert "Location:" in result
        mock_manager.step_out.assert_called_once_with(thread_id=None)

    @pytest.mark.asyncio
    async def test_step_out_with_thread_id(self, mock_manager):
        """Test step out with specific thread ID"""
        mock_manager.step_out = AsyncMock(
            return_value="Location: caller at file.c:20"
        )

        result = await execution.lldb_step_out(thread_id=789)

        assert "✓ Stepped out" in result
        mock_manager.step_out.assert_called_once_with(thread_id=789)
