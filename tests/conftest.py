"""Pytest configuration and fixtures for testing appledb-mcp"""

from unittest.mock import MagicMock, Mock

import pytest


@pytest.fixture
def mock_lldb_debugger():
    """Mock LLDB SBDebugger"""
    debugger = Mock()
    debugger.IsValid.return_value = True
    debugger.GetVersionString.return_value = "lldb-1400.0.0"
    debugger.SetAsync.return_value = None
    debugger.CreateTarget.return_value = Mock()
    debugger.GetSelectedTarget.return_value = Mock()
    return debugger


@pytest.fixture
def mock_lldb_target():
    """Mock LLDB SBTarget"""
    target = Mock()
    target.IsValid.return_value = True
    target.GetTriple.return_value = "arm64-apple-macosx"
    target.GetProcess.return_value = Mock()
    target.AttachToProcessWithID.return_value = Mock()
    target.AttachToProcessWithName.return_value = Mock()
    target.Launch.return_value = Mock()
    return target


@pytest.fixture
def mock_lldb_process():
    """Mock LLDB SBProcess"""
    process = Mock()
    process.IsValid.return_value = True
    process.GetProcessID.return_value = 12345
    process.GetName.return_value = "test_process"
    process.GetState.return_value = 5  # eStateStopped
    process.Detach.return_value = Mock(Fail=Mock(return_value=False))
    process.Kill.return_value = Mock(Fail=Mock(return_value=False))
    return process


@pytest.fixture
def mock_lldb_error():
    """Mock LLDB SBError"""
    error = Mock()
    error.Fail.return_value = False
    error.Success.return_value = True
    error.GetCString.return_value = ""
    return error


@pytest.fixture
def mock_lldb_listener():
    """Mock LLDB SBListener"""
    return Mock()


@pytest.fixture
def mock_lldb_launch_info():
    """Mock LLDB SBLaunchInfo"""
    launch_info = Mock()
    launch_info.GetLaunchFlags.return_value = 0
    launch_info.SetLaunchFlags.return_value = None
    launch_info.SetEnvironmentEntryAtIndex.return_value = None
    return launch_info
