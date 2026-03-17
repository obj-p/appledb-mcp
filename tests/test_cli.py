"""Tests for the CLI"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from click.testing import CliRunner

from appledb_mcp.cli import main


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def mock_server_running():
    """Mock server as running (skip auto-start)"""
    with patch("appledb_mcp.cli._is_server_running", return_value=True):
        yield


@pytest.fixture
def mock_run():
    """Mock the _run helper"""
    with patch("appledb_mcp.cli._run") as mock:
        yield mock


class TestServerCommands:
    def test_server_status_not_running(self, runner):
        with patch("appledb_mcp.cli._is_server_running", return_value=False), \
             patch("appledb_mcp.cli._get_server_pid", return_value=None):
            result = runner.invoke(main, ["server-status"])
            assert result.exit_code == 0
            assert "not running" in result.output.lower()

    def test_server_status_running(self, runner):
        with patch("appledb_mcp.cli._is_server_running", return_value=True), \
             patch("appledb_mcp.cli._get_server_pid", return_value=1234):
            result = runner.invoke(main, ["server-status"])
            assert result.exit_code == 0
            assert "running" in result.output.lower()

    def test_kill_server_not_running(self, runner):
        with patch("appledb_mcp.cli._get_server_pid", return_value=None):
            result = runner.invoke(main, ["kill-server"])
            assert "No server running" in result.output


class TestAttach:
    def test_attach_by_pid(self, runner, mock_server_running, mock_run):
        mock_run.return_value = {"pid": 1234, "name": "MyApp", "state": "stopped", "architecture": "arm64"}
        result = runner.invoke(main, ["attach", "1234"])
        assert result.exit_code == 0
        assert "MyApp" in result.output
        mock_run.assert_called_once_with(5037, "attach_process", {"pid": 1234})

    def test_attach_by_name(self, runner, mock_server_running, mock_run):
        mock_run.return_value = {"pid": 5678, "name": "Safari", "state": "stopped", "architecture": "arm64"}
        result = runner.invoke(main, ["attach", "-n", "Safari"])
        assert result.exit_code == 0
        assert "Safari" in result.output

    def test_attach_no_args(self, runner, mock_server_running):
        result = runner.invoke(main, ["attach"])
        assert result.exit_code != 0


class TestStatus:
    def test_status_detached(self, runner, mock_server_running, mock_run):
        mock_run.return_value = {"attached": False, "state": "detached", "process": None, "target": None, "threads": [], "loaded_frameworks": []}
        result = runner.invoke(main, ["status"])
        assert result.exit_code == 0
        assert "detached" in result.output

    def test_status_attached(self, runner, mock_server_running, mock_run):
        mock_run.return_value = {
            "attached": True, "state": "stopped",
            "process": {"pid": 1234, "name": "MyApp", "state": "stopped", "architecture": "arm64"},
            "target": {"triple": "arm64-apple-macosx", "executable": "/path/to/app"},
            "threads": [{"id": 1}], "loaded_frameworks": [],
        }
        result = runner.invoke(main, ["status"])
        assert result.exit_code == 0
        assert "MyApp" in result.output
        assert "1234" in result.output


class TestExecution:
    def test_continue(self, runner, mock_server_running, mock_run):
        mock_run.return_value = {"state": "running"}
        result = runner.invoke(main, ["continue"])
        assert result.exit_code == 0

    def test_pause(self, runner, mock_server_running, mock_run):
        mock_run.return_value = {"description": "Stopped at main.c:10"}
        result = runner.invoke(main, ["pause"])
        assert result.exit_code == 0

    def test_step_over(self, runner, mock_server_running, mock_run):
        mock_run.return_value = {"location": "main at test.c:42"}
        result = runner.invoke(main, ["step", "over"])
        assert result.exit_code == 0


class TestInspection:
    def test_eval(self, runner, mock_server_running, mock_run):
        mock_run.return_value = {"value": "42", "type": "int", "summary": None, "error": None}
        result = runner.invoke(main, ["eval", "x"])
        assert result.exit_code == 0
        assert "42" in result.output

    def test_bt(self, runner, mock_server_running, mock_run):
        mock_run.return_value = {"frames": [
            {"index": 0, "function": "main", "file": "test.c", "line": 10, "pc": "0x100", "module": "app"}
        ]}
        result = runner.invoke(main, ["bt"])
        assert result.exit_code == 0
        assert "main" in result.output

    def test_cmd(self, runner, mock_server_running, mock_run):
        mock_run.return_value = {"output": "some output", "error": "", "success": True}
        result = runner.invoke(main, ["cmd", "help"])
        assert result.exit_code == 0
        assert "some output" in result.output


class TestBreakpoints:
    def test_bp_set_by_location(self, runner, mock_server_running, mock_run):
        mock_run.return_value = {"id": 1, "locations": 1}
        result = runner.invoke(main, ["bp", "set", "main.c:42"])
        assert result.exit_code == 0
        assert "Breakpoint 1" in result.output
        mock_run.assert_called_with(5037, "set_breakpoint", {"file": "main.c", "line": 42})

    def test_bp_set_by_symbol(self, runner, mock_server_running, mock_run):
        mock_run.return_value = {"id": 2, "locations": 3}
        result = runner.invoke(main, ["bp", "set", "viewDidLoad"])
        assert result.exit_code == 0
        mock_run.assert_called_with(5037, "set_breakpoint", {"symbol": "viewDidLoad"})

    def test_bp_list(self, runner, mock_server_running, mock_run):
        mock_run.return_value = {"breakpoints": [
            {"id": 1, "enabled": True, "file": "main.c", "line": 10, "symbol": None, "hit_count": 2}
        ]}
        result = runner.invoke(main, ["bp", "list"])
        assert result.exit_code == 0
        assert "main.c:10" in result.output

    def test_bp_delete(self, runner, mock_server_running, mock_run):
        mock_run.return_value = {"success": True}
        result = runner.invoke(main, ["bp", "delete", "1"])
        assert result.exit_code == 0
        assert "deleted" in result.output.lower()
