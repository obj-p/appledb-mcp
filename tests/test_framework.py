"""Tests for framework loading functionality"""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from appledb_mcp.config import AppleDBConfig
from appledb_mcp.debugger import LLDBDebuggerManager, ProcessState
from appledb_mcp.tools.framework import lldb_load_framework
from appledb_mcp.utils.errors import LLDBError, ProcessNotAttachedError
from appledb_mcp.utils.framework_resolver import resolve_framework_path


class TestFrameworkResolver:
    """Tests for framework path resolution"""

    def test_resolve_from_env_var(self, tmp_path):
        """Test resolving framework from environment variable"""
        # Create a dummy framework file
        framework_path = tmp_path / "testframework"
        framework_path.touch()

        result = resolve_framework_path("testframework", env_var_path=framework_path)
        assert result == str(framework_path)

    def test_resolve_from_env_var_not_exists(self, tmp_path):
        """Test that non-existent env var path falls back to other locations"""
        non_existent = tmp_path / "does_not_exist"

        # Should raise FileNotFoundError since no bundled or dev frameworks exist
        with pytest.raises(FileNotFoundError) as exc_info:
            resolve_framework_path("testframework", env_var_path=non_existent)
        assert "Framework 'testframework' not found" in str(exc_info.value)

    def test_resolve_from_bundled(self, tmp_path, monkeypatch):
        """Test resolving framework from bundled location"""
        # Create bundled framework structure - simulating the package structure
        # We need tmp_path / src / appledb_mcp / utils / framework_resolver.py
        # So bundled should be at tmp_path / frameworks / ...
        fake_module_path = tmp_path / "src" / "appledb_mcp" / "utils" / "framework_resolver.py"
        fake_module_path.parent.mkdir(parents=True)
        fake_module_path.touch()

        bundled_path = tmp_path / "frameworks" / "testframework.framework" / "testframework"
        bundled_path.parent.mkdir(parents=True)
        bundled_path.touch()

        # Patch __file__ in the framework_resolver module itself
        import appledb_mcp.utils.framework_resolver as resolver_module
        monkeypatch.setattr(resolver_module, '__file__', str(fake_module_path))

        result = resolve_framework_path("testframework")
        assert result == str(bundled_path)

    def test_resolve_from_dev_location(self, tmp_path, monkeypatch):
        """Test resolving framework from development location"""
        # Create dev framework structure
        dev_path = tmp_path / "Projects" / "testframework" / "build" / "testframework.framework" / "testframework"
        dev_path.parent.mkdir(parents=True)
        dev_path.touch()

        # Mock Path.home() to return tmp_path
        with patch("appledb_mcp.utils.framework_resolver.Path") as mock_path:
            mock_path.home.return_value = tmp_path
            # Make Path() constructor work normally
            mock_path.side_effect = lambda *args: Path(*args) if args else Path()

            result = resolve_framework_path("testframework")
            assert result == str(dev_path)

    def test_resolve_not_found(self):
        """Test error when framework not found anywhere"""
        with pytest.raises(FileNotFoundError) as exc_info:
            resolve_framework_path("nonexistent")
        assert "Framework 'nonexistent' not found" in str(exc_info.value)


class TestFrameworkLoading:
    """Tests for framework loading in debugger"""

    @pytest.fixture
    def mock_lldb(self):
        """Mock LLDB module"""
        with patch("appledb_mcp.debugger.lldb") as mock:
            # Mock SBError
            mock.SBError.return_value = Mock(
                Fail=Mock(return_value=False),
                GetCString=Mock(return_value="")
            )
            # Mock SBFileSpec
            mock.SBFileSpec.return_value = Mock()
            yield mock

    @pytest.fixture
    def debugger_manager(self, mock_lldb):
        """Create debugger manager instance"""
        # Reset singleton
        LLDBDebuggerManager._instance = None

        manager = LLDBDebuggerManager.get_instance()
        config = AppleDBConfig()

        # Mock the debugger
        mock_debugger = Mock()
        mock_target = Mock()
        mock_process = Mock()

        mock_debugger.GetSelectedTarget.return_value = mock_target
        mock_target.IsValid.return_value = True
        mock_target.GetProcess.return_value = mock_process
        mock_process.IsValid.return_value = True

        manager._debugger = mock_debugger
        manager._config = config
        manager._state = ProcessState.ATTACHED_STOPPED

        return manager

    @pytest.mark.asyncio
    async def test_load_framework_by_path(self, debugger_manager, mock_lldb, tmp_path):
        """Test loading framework by explicit path"""
        # Create a dummy framework file
        framework_path = tmp_path / "test.framework" / "test"
        framework_path.parent.mkdir()
        framework_path.touch()

        # Mock the target and process
        mock_target = debugger_manager.get_target()
        mock_process = debugger_manager.get_process()

        # No modules loaded yet
        mock_target.GetNumModules.return_value = 0

        # Mock LoadImage to return address
        mock_process.LoadImage.return_value = 0x1000

        # Mock run_lldb_operation
        with patch("appledb_mcp.debugger.run_lldb_operation") as mock_run:
            mock_run.return_value = 0x1000

            result = await debugger_manager.load_framework(framework_path=str(framework_path))

            assert result["success"] is True
            assert result["address"] == 0x1000
            assert result["already_loaded"] is False
            assert "test" in result["message"]

    @pytest.mark.asyncio
    async def test_load_framework_by_name(self, debugger_manager, mock_lldb, tmp_path):
        """Test loading framework by name"""
        # Create a dummy framework file
        framework_path = tmp_path / "testframework"
        framework_path.touch()

        # Mock the target and process
        mock_target = debugger_manager.get_target()
        mock_process = debugger_manager.get_process()

        # No modules loaded yet
        mock_target.GetNumModules.return_value = 0

        # Mock LoadImage to return address
        mock_process.LoadImage.return_value = 0x2000

        # Mock resolve_framework_path
        with patch("appledb_mcp.debugger.resolve_framework_path") as mock_resolve:
            mock_resolve.return_value = str(framework_path)

            # Mock run_lldb_operation
            with patch("appledb_mcp.debugger.run_lldb_operation") as mock_run:
                mock_run.return_value = 0x2000

                result = await debugger_manager.load_framework(framework_name="testframework")

                assert result["success"] is True
                assert result["address"] == 0x2000
                assert result["already_loaded"] is False
                assert "testframework" in result["message"]

    @pytest.mark.asyncio
    async def test_load_framework_already_loaded(self, debugger_manager, mock_lldb, tmp_path):
        """Test loading framework that is already loaded (idempotency)"""
        framework_path = tmp_path / "testframework"
        framework_path.touch()

        # Mock the target and process
        mock_target = debugger_manager.get_target()

        # Mock that module is already loaded
        mock_module = Mock()
        mock_module.GetFileSpec.return_value.GetFilename.return_value = "testframework"
        mock_module.GetObjectFileHeaderAddress.return_value.GetLoadAddress.return_value = 0x3000

        mock_target.GetNumModules.return_value = 1
        mock_target.GetModuleAtIndex.return_value = mock_module

        # Mock resolve_framework_path
        with patch("appledb_mcp.debugger.resolve_framework_path") as mock_resolve:
            mock_resolve.return_value = str(framework_path)

            result = await debugger_manager.load_framework(framework_name="testframework")

            assert result["success"] is True
            assert result["address"] == 0x3000
            assert result["already_loaded"] is True
            assert "already loaded" in result["message"]

    @pytest.mark.asyncio
    async def test_load_framework_not_attached(self):
        """Test error when trying to load framework without attached process"""
        # Reset singleton
        LLDBDebuggerManager._instance = None

        manager = LLDBDebuggerManager.get_instance()
        config = AppleDBConfig()

        # Mock the debugger but set state to DETACHED
        mock_debugger = Mock()
        manager._debugger = mock_debugger
        manager._config = config
        manager._state = ProcessState.DETACHED

        with pytest.raises(ProcessNotAttachedError) as exc_info:
            await manager.load_framework(framework_name="testframework")
        assert "no process attached" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_load_framework_invalid_params(self, debugger_manager):
        """Test error when invalid parameters provided"""
        # Neither parameter
        with pytest.raises(ValueError) as exc_info:
            await debugger_manager.load_framework()
        assert "must be provided" in str(exc_info.value)

        # Both parameters
        with pytest.raises(ValueError) as exc_info:
            await debugger_manager.load_framework(
                framework_path="/some/path",
                framework_name="testframework"
            )
        assert "Cannot specify both" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_load_framework_invalid_name(self, debugger_manager):
        """Test error when invalid framework name provided"""
        with pytest.raises(ValueError) as exc_info:
            await debugger_manager.load_framework(framework_name="invalid")
        assert "Unknown framework name" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_load_framework_lldb_error(self, debugger_manager, mock_lldb, tmp_path):
        """Test error when LLDB fails to load framework"""
        framework_path = tmp_path / "testframework"
        framework_path.touch()

        # Mock the target and process
        mock_target = debugger_manager.get_target()
        mock_process = debugger_manager.get_process()

        # No modules loaded yet
        mock_target.GetNumModules.return_value = 0

        # Mock run_lldb_operation to raise error
        with patch("appledb_mcp.debugger.resolve_framework_path") as mock_resolve:
            mock_resolve.return_value = str(framework_path)

            with patch("appledb_mcp.debugger.run_lldb_operation") as mock_run:
                # Simulate LLDB error
                error = Mock()
                error.Fail.return_value = True
                error.GetCString.return_value = "Permission denied"
                mock_lldb.SBError.return_value = error

                with pytest.raises(LLDBError) as exc_info:
                    await debugger_manager.load_framework(framework_name="testframework")
                assert "Failed to load framework" in str(exc_info.value)

class TestFrameworkTool:
    """Tests for the lldb_load_framework MCP tool"""

    @pytest.fixture
    def mock_manager(self):
        """Mock debugger manager"""
        with patch("appledb_mcp.tools.framework.LLDBDebuggerManager.get_instance") as mock:
            manager = Mock()
            mock.return_value = manager
            yield manager

    @pytest.mark.asyncio
    async def test_tool_load_by_path(self, mock_manager):
        """Test tool with explicit path"""
        mock_manager.load_framework = AsyncMock(return_value={
            "success": True,
            "address": 0x1000,
            "already_loaded": False,
            "message": "Successfully loaded framework 'test'"
        })

        result = await lldb_load_framework(framework_path="/path/to/test.framework/test")

        assert "✓" in result
        assert "0x1000" in result
        assert "test" in result
        mock_manager.load_framework.assert_called_once_with(
            framework_path="/path/to/test.framework/test",
            framework_name=None
        )

    @pytest.mark.asyncio
    async def test_tool_load_by_name(self, mock_manager):
        """Test tool with framework name"""
        mock_manager.load_framework = AsyncMock(return_value={
            "success": True,
            "address": 0x2000,
            "already_loaded": False,
            "message": "Successfully loaded framework 'testframework'"
        })

        result = await lldb_load_framework(framework_name="testframework")

        assert "✓" in result
        assert "0x2000" in result
        assert "testframework" in result
        mock_manager.load_framework.assert_called_once_with(
            framework_path=None,
            framework_name="testframework"
        )

    @pytest.mark.asyncio
    async def test_tool_already_loaded(self, mock_manager):
        """Test tool when framework already loaded"""
        mock_manager.load_framework = AsyncMock(return_value={
            "success": True,
            "address": 0x3000,
            "already_loaded": True,
            "message": "Framework 'testframework' was already loaded"
        })

        result = await lldb_load_framework(framework_name="testframework")

        assert "already loaded" in result
        assert "0x3000" in result

    @pytest.mark.asyncio
    async def test_tool_error_handling(self, mock_manager):
        """Test tool error handling"""
        mock_manager.load_framework = AsyncMock(
            side_effect=ProcessNotAttachedError("No process attached")
        )

        result = await lldb_load_framework(framework_name="testframework")

        assert "Error:" in result
        assert "No process attached" in result
