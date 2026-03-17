"""Unit tests for process management tools"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from lldb_service.models import ProcessInfo
from appledb_mcp.tools.process import lldb_attach_process, lldb_detach, lldb_launch_app
from appledb_mcp.utils.errors import InvalidStateError, LLDBError, ProcessNotAttachedError


@pytest.fixture
def mock_client():
    """Mock LLDBClient.get_instance() to return a mock client"""
    with patch("appledb_mcp.tools.process.LLDBClient") as mock_cls:
        client = MagicMock()
        mock_cls.get_instance.return_value = client
        yield client


def _make_process_info(pid=12345, name="test_app", state="stopped", architecture="arm64"):
    """Helper to create a ProcessInfo instance"""
    return ProcessInfo(pid=pid, name=name, state=state, architecture=architecture)


class TestAttachProcess:
    """Tests for lldb_attach_process tool"""

    @pytest.mark.asyncio
    async def test_attach_by_pid_success(self, mock_client):
        """Test successful attach by PID"""
        mock_client.attach_process_by_pid = AsyncMock(
            return_value=_make_process_info(pid=12345, name="test_app")
        )

        result = await lldb_attach_process(pid=12345)

        assert "Attached to process" in result
        assert "test_app" in result
        assert "12345" in result
        assert "arm64" in result
        assert "stopped" in result
        mock_client.attach_process_by_pid.assert_awaited_once_with(12345)

    @pytest.mark.asyncio
    async def test_attach_by_name_success(self, mock_client):
        """Test successful attach by process name"""
        mock_client.attach_process_by_name = AsyncMock(
            return_value=_make_process_info(pid=99999, name="Safari")
        )

        result = await lldb_attach_process(name="Safari")

        assert "Attached to process" in result
        assert "Safari" in result
        assert "99999" in result
        mock_client.attach_process_by_name.assert_awaited_once_with("Safari")

    @pytest.mark.asyncio
    async def test_attach_no_pid_or_name(self, mock_client):
        """Test attach fails when neither pid nor name provided"""
        result = await lldb_attach_process()

        assert "Error" in result
        assert "pid" in result.lower() or "name" in result.lower()
        mock_client.attach_process_by_pid.assert_not_called()
        mock_client.attach_process_by_name.assert_not_called()

    @pytest.mark.asyncio
    async def test_attach_both_pid_and_name(self, mock_client):
        """Test attach fails when both pid and name provided"""
        result = await lldb_attach_process(pid=12345, name="test_app")

        assert "Error" in result
        assert "Cannot specify both" in result
        mock_client.attach_process_by_pid.assert_not_called()
        mock_client.attach_process_by_name.assert_not_called()

    @pytest.mark.asyncio
    async def test_attach_already_attached(self, mock_client):
        """Test attach fails when already attached"""
        mock_client.attach_process_by_pid = AsyncMock(
            side_effect=InvalidStateError("Already attached to a process")
        )

        result = await lldb_attach_process(pid=67890)

        assert "Error" in result
        assert "Already attached" in result


class TestLaunchApp:
    """Tests for lldb_launch_app tool"""

    @pytest.mark.asyncio
    async def test_launch_app_success(self, mock_client):
        """Test successful app launch"""
        mock_client.launch_app = AsyncMock(
            return_value=_make_process_info(pid=12345, name="test_app")
        )

        result = await lldb_launch_app(executable="/path/to/test_app")

        assert "Launched application" in result
        assert "test_app" in result
        assert "12345" in result
        mock_client.launch_app.assert_awaited_once_with(
            executable="/path/to/test_app",
            args=None,
            env=None,
            stop_at_entry=True,
        )

    @pytest.mark.asyncio
    async def test_launch_app_with_args(self, mock_client):
        """Test app launch with command-line arguments"""
        mock_client.launch_app = AsyncMock(
            return_value=_make_process_info(pid=12345, name="test_app")
        )

        result = await lldb_launch_app(
            executable="/path/to/test_app",
            args=["--verbose", "--debug"],
        )

        assert "Launched application" in result
        mock_client.launch_app.assert_awaited_once_with(
            executable="/path/to/test_app",
            args=["--verbose", "--debug"],
            env=None,
            stop_at_entry=True,
        )

    @pytest.mark.asyncio
    async def test_launch_app_with_env(self, mock_client):
        """Test app launch with environment variables"""
        mock_client.launch_app = AsyncMock(
            return_value=_make_process_info(pid=12345, name="test_app")
        )

        result = await lldb_launch_app(
            executable="/path/to/test_app",
            env={"DEBUG": "1", "LOG_LEVEL": "verbose"},
        )

        assert "Launched application" in result
        mock_client.launch_app.assert_awaited_once_with(
            executable="/path/to/test_app",
            args=None,
            env={"DEBUG": "1", "LOG_LEVEL": "verbose"},
            stop_at_entry=True,
        )

    @pytest.mark.asyncio
    async def test_launch_app_stop_at_entry_false(self, mock_client):
        """Test app launch without stopping at entry"""
        mock_client.launch_app = AsyncMock(
            return_value=_make_process_info(pid=12345, name="test_app", state="running")
        )

        result = await lldb_launch_app(
            executable="/path/to/test_app",
            stop_at_entry=False,
        )

        assert "Launched application" in result
        assert "Stopped at entry: False" in result
        mock_client.launch_app.assert_awaited_once_with(
            executable="/path/to/test_app",
            args=None,
            env=None,
            stop_at_entry=False,
        )

    @pytest.mark.asyncio
    async def test_launch_app_already_attached(self, mock_client):
        """Test launch fails when already attached"""
        mock_client.launch_app = AsyncMock(
            side_effect=InvalidStateError("Already attached to a process")
        )

        result = await lldb_launch_app(executable="/path/to/test_app")

        assert "Error" in result
        assert "Already attached" in result


class TestDetach:
    """Tests for lldb_detach tool"""

    @pytest.mark.asyncio
    async def test_detach_success(self, mock_client):
        """Test successful detach"""
        mock_client.detach = AsyncMock(return_value=None)

        result = await lldb_detach()

        assert "Successfully detached from process" in result
        mock_client.detach.assert_awaited_once_with(kill=False)

    @pytest.mark.asyncio
    async def test_detach_with_kill(self, mock_client):
        """Test detach with kill"""
        mock_client.detach = AsyncMock(return_value=None)

        result = await lldb_detach(kill=True)

        assert "Successfully killed process" in result
        mock_client.detach.assert_awaited_once_with(kill=True)

    @pytest.mark.asyncio
    async def test_detach_not_attached(self, mock_client):
        """Test detach fails when not attached"""
        mock_client.detach = AsyncMock(
            side_effect=ProcessNotAttachedError("No process attached")
        )

        result = await lldb_detach()

        assert "Error" in result
        assert "No process attached" in result
