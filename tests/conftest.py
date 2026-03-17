"""Pytest configuration and fixtures for testing appledb-mcp"""

from unittest.mock import MagicMock, Mock

import pytest

from appledb_mcp.lldb_client import LLDBClient


@pytest.fixture
def reset_client_singleton():
    """Reset LLDBClient singleton between tests"""
    LLDBClient._instance = None
    yield
    LLDBClient._instance = None


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
def mock_thread():
    """Mock LLDB thread"""
    thread = MagicMock()
    thread.IsValid.return_value = True
    thread.GetThreadID.return_value = 1
    thread.StepOver.return_value = None
    thread.StepInto.return_value = None
    thread.StepOut.return_value = None
    thread.GetStopDescription.return_value = "breakpoint"

    # Mock frame
    frame = MagicMock()
    frame.IsValid.return_value = True
    frame.GetFunctionName.return_value = "main"
    frame.GetPC.return_value = 0x100000000

    # Mock line entry
    line_entry = MagicMock()
    line_entry.IsValid.return_value = True
    line_entry.GetLine.return_value = 42

    # Mock file spec
    file_spec = MagicMock()
    file_spec.GetFilename.return_value = "test.c"
    line_entry.GetFileSpec.return_value = file_spec

    frame.GetLineEntry.return_value = line_entry
    thread.GetFrameAtIndex.return_value = frame

    return thread


@pytest.fixture
def mock_frame():
    """Mock LLDB frame"""
    frame = MagicMock()
    frame.IsValid.return_value = True
    frame.GetFunctionName.return_value = "test_function"
    frame.GetPC.return_value = 0x100001000

    # Mock line entry
    line_entry = MagicMock()
    line_entry.IsValid.return_value = True
    line_entry.GetLine.return_value = 10

    # Mock file spec
    file_spec = MagicMock()
    file_spec.GetFilename.return_value = "main.c"
    line_entry.GetFileSpec.return_value = file_spec

    frame.GetLineEntry.return_value = line_entry

    return frame


@pytest.fixture
def mock_lldb_target():
    """Mock LLDB SBTarget"""
    # Mock executable
    mock_executable = Mock()
    mock_executable.IsValid.return_value = True
    mock_executable.GetFilename.return_value = "test_app"

    target = Mock()
    target.IsValid.return_value = True
    target.GetTriple.return_value = "arm64-apple-macosx"
    target.GetExecutable.return_value = mock_executable
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


@pytest.fixture
def mock_lldb_value():
    """Mock LLDB SBValue"""
    value = MagicMock()
    value.IsValid.return_value = True
    value.GetName.return_value = "test_var"
    value.GetTypeName.return_value = "int"
    value.GetValue.return_value = "42"
    value.GetSummary.return_value = None

    # Mock error
    error = MagicMock()
    error.Fail.return_value = False
    error.GetCString.return_value = ""
    value.GetError.return_value = error

    return value


@pytest.fixture
def mock_lldb_value_list():
    """Mock LLDB SBValueList"""
    value_list = MagicMock()
    value_list.GetSize.return_value = 0
    return value_list


@pytest.fixture
def mock_lldb_expression_options():
    """Mock LLDB SBExpressionOptions"""
    options = MagicMock()
    options.SetLanguage.return_value = None
    return options


@pytest.fixture
def mock_lldb_module():
    """Mock LLDB SBModule"""
    module = MagicMock()
    module.IsValid.return_value = True

    file_spec = MagicMock()
    file_spec.IsValid.return_value = True
    file_spec.GetFilename.return_value = "libtest.dylib"
    module.GetFileSpec.return_value = file_spec

    return module
