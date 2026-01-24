"""Unit tests for process management tools"""

import pytest
from unittest.mock import AsyncMock, Mock, patch, MagicMock

from appledb_mcp.debugger import LLDBDebuggerManager, ProcessState
from appledb_mcp.tools.process import lldb_attach_process, lldb_detach, lldb_launch_app
from appledb_mcp.utils.errors import InvalidStateError, LLDBError, ProcessNotAttachedError


@pytest.fixture
def reset_debugger_singleton():
    """Reset the debugger singleton between tests"""
    LLDBDebuggerManager._instance = None
    yield
    LLDBDebuggerManager._instance = None


@pytest.fixture
def mock_lldb_module():
    """Mock the lldb module"""
    mock_lldb = MagicMock()

    # Mock LLDB constants
    mock_lldb.eLaunchFlagStopAtEntry = 0x1
    mock_lldb.eStateStopped = 5
    mock_lldb.eStateRunning = 9

    # Mock SBDebugger
    mock_debugger = Mock()
    mock_debugger.IsValid.return_value = True
    mock_debugger.GetVersionString.return_value = "lldb-1400.0.0"
    mock_debugger.SetAsync.return_value = None

    # Mock SBTarget
    mock_target = Mock()
    mock_target.IsValid.return_value = True
    mock_target.GetTriple.return_value = "arm64-apple-macosx"

    # Mock SBProcess
    mock_process = Mock()
    mock_process.IsValid.return_value = True
    mock_process.GetProcessID.return_value = 12345
    mock_process.GetName.return_value = "test_app"
    mock_process.GetState.return_value = 5

    # Mock SBError
    mock_error = Mock()
    mock_error.Fail.return_value = False
    mock_error.Success.return_value = True
    mock_error.GetCString.return_value = ""

    # Mock SBListener
    mock_listener = Mock()

    # Mock SBLaunchInfo
    mock_launch_info = Mock()
    mock_launch_info.GetLaunchFlags.return_value = 0

    # Set up mock returns
    mock_lldb.SBDebugger.Initialize = Mock()
    mock_lldb.SBDebugger.Create.return_value = mock_debugger
    mock_lldb.SBDebugger.Destroy = Mock()
    mock_lldb.SBDebugger.Terminate = Mock()
    mock_lldb.SBError.return_value = mock_error
    mock_lldb.SBListener.return_value = mock_listener
    mock_lldb.SBLaunchInfo.return_value = mock_launch_info

    mock_debugger.CreateTarget.return_value = mock_target
    mock_debugger.GetSelectedTarget.return_value = mock_target

    mock_target.AttachToProcessWithID.return_value = mock_process
    mock_target.AttachToProcessWithName.return_value = mock_process
    mock_target.Launch.return_value = mock_process
    mock_target.GetProcess.return_value = mock_process

    mock_process.Detach.return_value = mock_error
    mock_process.Kill.return_value = mock_error

    return mock_lldb


class TestAttachProcess:
    """Tests for lldb_attach_process tool"""

    @pytest.mark.asyncio
    async def test_attach_by_pid_success(self, reset_debugger_singleton, mock_lldb_module):
        """Test successful attach by PID"""
        with patch('appledb_mcp.debugger.lldb', mock_lldb_module):
            with patch('appledb_mcp.utils.lldb_helpers.lldb', mock_lldb_module):
                from appledb_mcp.config import AppleDBConfig

                # Initialize debugger
                manager = LLDBDebuggerManager.get_instance()
                manager.initialize(AppleDBConfig())

                # Attach to process
                result = await lldb_attach_process(pid=12345)

                # Verify result
                assert "Attached to process" in result
                assert "12345" in result
                assert "test_app" in result
                assert manager.get_state() == ProcessState.ATTACHED_STOPPED

    @pytest.mark.asyncio
    async def test_attach_by_name_success(self, reset_debugger_singleton, mock_lldb_module):
        """Test successful attach by process name"""
        with patch('appledb_mcp.debugger.lldb', mock_lldb_module):
            with patch('appledb_mcp.utils.lldb_helpers.lldb', mock_lldb_module):
                from appledb_mcp.config import AppleDBConfig

                # Initialize debugger
                manager = LLDBDebuggerManager.get_instance()
                manager.initialize(AppleDBConfig())

                # Attach to process
                result = await lldb_attach_process(name="test_app")

                # Verify result
                assert "Attached to process" in result
                assert "test_app" in result
                assert manager.get_state() == ProcessState.ATTACHED_STOPPED

    @pytest.mark.asyncio
    async def test_attach_no_pid_or_name(self, reset_debugger_singleton, mock_lldb_module):
        """Test attach fails when neither pid nor name provided"""
        with patch('appledb_mcp.debugger.lldb', mock_lldb_module):
            with patch('appledb_mcp.utils.lldb_helpers.lldb', mock_lldb_module):
                from appledb_mcp.config import AppleDBConfig

                # Initialize debugger
                manager = LLDBDebuggerManager.get_instance()
                manager.initialize(AppleDBConfig())

                # Attempt to attach without pid or name
                result = await lldb_attach_process()

                # Should return error message
                assert "Error" in result
                assert "pid" in result.lower() or "name" in result.lower()

    @pytest.mark.asyncio
    async def test_attach_both_pid_and_name(self, reset_debugger_singleton, mock_lldb_module):
        """Test attach fails when both pid and name provided"""
        with patch('appledb_mcp.debugger.lldb', mock_lldb_module):
            with patch('appledb_mcp.utils.lldb_helpers.lldb', mock_lldb_module):
                from appledb_mcp.config import AppleDBConfig

                # Initialize debugger
                manager = LLDBDebuggerManager.get_instance()
                manager.initialize(AppleDBConfig())

                # Attempt to attach with both pid and name
                result = await lldb_attach_process(pid=12345, name="test_app")

                # Should return error message
                assert "Error" in result
                assert "Cannot specify both" in result

    @pytest.mark.asyncio
    async def test_attach_already_attached(self, reset_debugger_singleton, mock_lldb_module):
        """Test attach fails when already attached"""
        with patch('appledb_mcp.debugger.lldb', mock_lldb_module):
            with patch('appledb_mcp.utils.lldb_helpers.lldb', mock_lldb_module):
                from appledb_mcp.config import AppleDBConfig

                # Initialize debugger and attach
                manager = LLDBDebuggerManager.get_instance()
                manager.initialize(AppleDBConfig())
                await lldb_attach_process(pid=12345)

                # Attempt to attach again
                result = await lldb_attach_process(pid=67890)

                # Should return error message
                assert "Error" in result
                assert "Already attached" in result


class TestLaunchApp:
    """Tests for lldb_launch_app tool"""

    @pytest.mark.asyncio
    async def test_launch_app_success(self, reset_debugger_singleton, mock_lldb_module):
        """Test successful app launch"""
        with patch('appledb_mcp.debugger.lldb', mock_lldb_module):
            with patch('appledb_mcp.utils.lldb_helpers.lldb', mock_lldb_module):
                from appledb_mcp.config import AppleDBConfig

                # Initialize debugger
                manager = LLDBDebuggerManager.get_instance()
                manager.initialize(AppleDBConfig())

                # Launch app
                result = await lldb_launch_app(executable="/path/to/test_app")

                # Verify result
                assert "Launched application" in result
                assert "test_app" in result
                assert "12345" in result
                assert manager.get_state() == ProcessState.ATTACHED_STOPPED

    @pytest.mark.asyncio
    async def test_launch_app_with_args(self, reset_debugger_singleton, mock_lldb_module):
        """Test app launch with command-line arguments"""
        with patch('appledb_mcp.debugger.lldb', mock_lldb_module):
            with patch('appledb_mcp.utils.lldb_helpers.lldb', mock_lldb_module):
                from appledb_mcp.config import AppleDBConfig

                # Initialize debugger
                manager = LLDBDebuggerManager.get_instance()
                manager.initialize(AppleDBConfig())

                # Launch app with args
                result = await lldb_launch_app(
                    executable="/path/to/test_app",
                    args=["--verbose", "--debug"]
                )

                # Verify result
                assert "Launched application" in result
                assert manager.get_state() == ProcessState.ATTACHED_STOPPED

    @pytest.mark.asyncio
    async def test_launch_app_with_env(self, reset_debugger_singleton, mock_lldb_module):
        """Test app launch with environment variables"""
        with patch('appledb_mcp.debugger.lldb', mock_lldb_module):
            with patch('appledb_mcp.utils.lldb_helpers.lldb', mock_lldb_module):
                from appledb_mcp.config import AppleDBConfig

                # Initialize debugger
                manager = LLDBDebuggerManager.get_instance()
                manager.initialize(AppleDBConfig())

                # Launch app with env
                result = await lldb_launch_app(
                    executable="/path/to/test_app",
                    env={"DEBUG": "1", "LOG_LEVEL": "verbose"}
                )

                # Verify result
                assert "Launched application" in result

    @pytest.mark.asyncio
    async def test_launch_app_no_stop_at_entry(self, reset_debugger_singleton, mock_lldb_module):
        """Test app launch without stopping at entry"""
        with patch('appledb_mcp.debugger.lldb', mock_lldb_module):
            with patch('appledb_mcp.utils.lldb_helpers.lldb', mock_lldb_module):
                from appledb_mcp.config import AppleDBConfig

                # Initialize debugger
                manager = LLDBDebuggerManager.get_instance()
                manager.initialize(AppleDBConfig())

                # Launch app without stopping at entry
                result = await lldb_launch_app(
                    executable="/path/to/test_app",
                    stop_at_entry=False
                )

                # Verify result
                assert "Launched application" in result
                assert "Stopped at entry: False" in result

    @pytest.mark.asyncio
    async def test_launch_app_already_attached(self, reset_debugger_singleton, mock_lldb_module):
        """Test launch fails when already attached"""
        with patch('appledb_mcp.debugger.lldb', mock_lldb_module):
            with patch('appledb_mcp.utils.lldb_helpers.lldb', mock_lldb_module):
                from appledb_mcp.config import AppleDBConfig

                # Initialize debugger and attach
                manager = LLDBDebuggerManager.get_instance()
                manager.initialize(AppleDBConfig())
                await lldb_attach_process(pid=12345)

                # Attempt to launch app
                result = await lldb_launch_app(executable="/path/to/test_app")

                # Should return error message
                assert "Error" in result
                assert "Already attached" in result


class TestDetach:
    """Tests for lldb_detach tool"""

    @pytest.mark.asyncio
    async def test_detach_success(self, reset_debugger_singleton, mock_lldb_module):
        """Test successful detach"""
        with patch('appledb_mcp.debugger.lldb', mock_lldb_module):
            with patch('appledb_mcp.utils.lldb_helpers.lldb', mock_lldb_module):
                from appledb_mcp.config import AppleDBConfig

                # Initialize debugger and attach
                manager = LLDBDebuggerManager.get_instance()
                manager.initialize(AppleDBConfig())
                await lldb_attach_process(pid=12345)

                # Detach
                result = await lldb_detach()

                # Verify result
                assert "Successfully detached" in result
                assert manager.get_state() == ProcessState.DETACHED

    @pytest.mark.asyncio
    async def test_detach_with_kill(self, reset_debugger_singleton, mock_lldb_module):
        """Test detach with kill"""
        with patch('appledb_mcp.debugger.lldb', mock_lldb_module):
            with patch('appledb_mcp.utils.lldb_helpers.lldb', mock_lldb_module):
                from appledb_mcp.config import AppleDBConfig

                # Initialize debugger and attach
                manager = LLDBDebuggerManager.get_instance()
                manager.initialize(AppleDBConfig())
                await lldb_attach_process(pid=12345)

                # Detach with kill
                result = await lldb_detach(kill=True)

                # Verify result
                assert "Successfully killed" in result
                assert manager.get_state() == ProcessState.DETACHED

    @pytest.mark.asyncio
    async def test_detach_not_attached(self, reset_debugger_singleton, mock_lldb_module):
        """Test detach fails when not attached"""
        with patch('appledb_mcp.debugger.lldb', mock_lldb_module):
            with patch('appledb_mcp.utils.lldb_helpers.lldb', mock_lldb_module):
                from appledb_mcp.config import AppleDBConfig

                # Initialize debugger without attaching
                manager = LLDBDebuggerManager.get_instance()
                manager.initialize(AppleDBConfig())

                # Attempt to detach
                result = await lldb_detach()

                # Should return error message
                assert "Error" in result
                assert "No process attached" in result
