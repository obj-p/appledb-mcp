"""Tests for framework loading functionality"""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from appledb_mcp.tools.framework import lldb_load_framework
from appledb_mcp.utils.errors import LLDBError, ProcessNotAttachedError
from lldb_service.utils.framework_resolver import resolve_framework_path


class TestFrameworkResolver:
    """Tests for framework path resolution"""

    def test_resolve_from_env_var(self, tmp_path):
        """Test resolving framework from environment variable"""
        framework_path = tmp_path / "testframework"
        framework_path.touch()

        result = resolve_framework_path("testframework", env_var_path=framework_path)
        assert result == str(framework_path)

    def test_resolve_from_env_var_not_exists(self, tmp_path):
        """Test that non-existent env var path falls back to other locations"""
        non_existent = tmp_path / "does_not_exist"

        with pytest.raises(FileNotFoundError) as exc_info:
            resolve_framework_path("testframework", env_var_path=non_existent)
        assert "Framework 'testframework' not found" in str(exc_info.value)

    def test_resolve_from_bundled(self, tmp_path, monkeypatch):
        """Test resolving framework from bundled location"""
        fake_module_path = tmp_path / "src" / "lldb_service" / "utils" / "framework_resolver.py"
        fake_module_path.parent.mkdir(parents=True)
        fake_module_path.touch()

        bundled_path = tmp_path / "frameworks" / "testframework.framework" / "testframework"
        bundled_path.parent.mkdir(parents=True)
        bundled_path.touch()

        import lldb_service.utils.framework_resolver as resolver_module
        monkeypatch.setattr(resolver_module, '__file__', str(fake_module_path))

        result = resolve_framework_path("testframework")
        assert result == str(bundled_path)

    def test_resolve_not_found(self):
        """Test error when framework not found anywhere"""
        with pytest.raises(FileNotFoundError) as exc_info:
            resolve_framework_path("nonexistent")
        assert "Framework 'nonexistent' not found" in str(exc_info.value)


class TestFrameworkTool:
    """Tests for the lldb_load_framework MCP tool"""

    @pytest.fixture
    def mock_client(self):
        """Mock LLDBClient for framework tool"""
        with patch("appledb_mcp.tools.framework.LLDBClient") as mock_cls:
            client = MagicMock()
            mock_cls.get_instance.return_value = client
            yield client

    @pytest.mark.asyncio
    async def test_tool_load_by_path(self, mock_client):
        """Test tool with explicit path"""
        mock_client.load_framework = AsyncMock(return_value={
            "success": True,
            "address": 0x1000,
            "already_loaded": False,
            "message": "Successfully loaded framework 'test'"
        })

        result = await lldb_load_framework(framework_path="/path/to/test.framework/test")

        assert "✓" in result
        assert "0x1000" in result
        assert "test" in result
        mock_client.load_framework.assert_called_once_with(
            framework_path="/path/to/test.framework/test",
            framework_name=None
        )

    @pytest.mark.asyncio
    async def test_tool_load_by_name(self, mock_client):
        """Test tool with framework name"""
        mock_client.load_framework = AsyncMock(return_value={
            "success": True,
            "address": 0x2000,
            "already_loaded": False,
            "message": "Successfully loaded framework 'testframework'"
        })

        result = await lldb_load_framework(framework_name="testframework")

        assert "✓" in result
        assert "0x2000" in result
        assert "testframework" in result
        mock_client.load_framework.assert_called_once_with(
            framework_path=None,
            framework_name="testframework"
        )

    @pytest.mark.asyncio
    async def test_tool_already_loaded(self, mock_client):
        """Test tool when framework already loaded"""
        mock_client.load_framework = AsyncMock(return_value={
            "success": True,
            "address": 0x3000,
            "already_loaded": True,
            "message": "Framework 'testframework' was already loaded"
        })

        result = await lldb_load_framework(framework_name="testframework")

        assert "already loaded" in result
        assert "0x3000" in result

    @pytest.mark.asyncio
    async def test_tool_no_params(self, mock_client):
        """Test tool with neither parameter"""
        result = await lldb_load_framework()

        assert "Error" in result
        assert "must be provided" in result

    @pytest.mark.asyncio
    async def test_tool_both_params(self, mock_client):
        """Test tool with both parameters"""
        result = await lldb_load_framework(
            framework_path="/path/to/test", framework_name="test"
        )

        assert "Error" in result
        assert "Cannot specify both" in result

    @pytest.mark.asyncio
    async def test_tool_error_handling(self, mock_client):
        """Test tool error handling"""
        mock_client.load_framework = AsyncMock(
            side_effect=ProcessNotAttachedError("No process attached")
        )

        result = await lldb_load_framework(framework_name="testframework")

        assert "Error:" in result
        assert "No process attached" in result
