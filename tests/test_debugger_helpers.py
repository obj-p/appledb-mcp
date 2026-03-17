"""Tests for LLDBDebuggerManager helper methods

These test the helper methods on the LLDB service's debugger manager.
Since these methods use the lldb module directly, we mock it at the module level.
"""

import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def debugger_manager():
    """Create a debugger manager with mocked LLDB"""
    with patch("lldb_service.debugger.lldb") as mock_lldb:
        with patch("lldb_service.debugger.check_lldb_available", return_value=True):
            from lldb_service.debugger import LLDBDebuggerManager

            # Reset singleton
            LLDBDebuggerManager._instance = None

            manager = LLDBDebuggerManager.get_instance()

            # Mock debugger
            mock_debugger = MagicMock()
            mock_debugger.IsValid.return_value = True
            manager._debugger = mock_debugger

            # Mock process and target
            mock_target = MagicMock()
            mock_target.IsValid.return_value = True
            mock_debugger.GetSelectedTarget.return_value = mock_target

            mock_process = MagicMock()
            mock_process.IsValid.return_value = True
            mock_target.GetProcess.return_value = mock_process

            yield manager

            # Reset singleton after test
            LLDBDebuggerManager._instance = None


class TestGetFrameLocation:
    """Tests for _get_frame_location helper"""

    def test_get_frame_location_with_valid_line_entry(self, debugger_manager):
        """Test getting frame location with valid line entry"""
        thread = MagicMock()
        frame = MagicMock()
        frame.IsValid.return_value = True
        frame.GetFunctionName.return_value = "test_func"

        line_entry = MagicMock()
        line_entry.IsValid.return_value = True
        line_entry.GetLine.return_value = 42

        file_spec = MagicMock()
        file_spec.GetFilename.return_value = "test.c"
        line_entry.GetFileSpec.return_value = file_spec

        frame.GetLineEntry.return_value = line_entry
        thread.GetFrameAtIndex.return_value = frame

        result = debugger_manager._get_frame_location(thread)
        assert result == "Location: test_func at test.c:42"

    def test_get_frame_location_with_invalid_frame(self, debugger_manager):
        """Test getting frame location with invalid frame"""
        thread = MagicMock()
        frame = MagicMock()
        frame.IsValid.return_value = False
        thread.GetFrameAtIndex.return_value = frame

        result = debugger_manager._get_frame_location(thread)
        assert result == "Location: <unknown>"

    def test_get_frame_location_without_line_entry(self, debugger_manager):
        """Test getting frame location when line entry is invalid (PC hex fallback)"""
        thread = MagicMock()
        frame = MagicMock()
        frame.IsValid.return_value = True
        frame.GetFunctionName.return_value = "test_func"
        frame.GetPC.return_value = 0x100001234

        line_entry = MagicMock()
        line_entry.IsValid.return_value = False
        frame.GetLineEntry.return_value = line_entry

        thread.GetFrameAtIndex.return_value = frame

        result = debugger_manager._get_frame_location(thread)
        assert result == "Location: test_func at 0x100001234"

    def test_get_frame_location_with_unknown_function(self, debugger_manager):
        """Test getting frame location with unknown function name"""
        thread = MagicMock()
        frame = MagicMock()
        frame.IsValid.return_value = True
        frame.GetFunctionName.return_value = None

        line_entry = MagicMock()
        line_entry.IsValid.return_value = True
        line_entry.GetLine.return_value = 10

        file_spec = MagicMock()
        file_spec.GetFilename.return_value = "file.c"
        line_entry.GetFileSpec.return_value = file_spec

        frame.GetLineEntry.return_value = line_entry
        thread.GetFrameAtIndex.return_value = frame

        result = debugger_manager._get_frame_location(thread)
        assert result == "Location: <unknown> at file.c:10"


class TestGetThread:
    """Tests for _get_thread helper"""

    def test_get_thread_by_id(self, debugger_manager):
        """Test getting thread by specific ID"""
        mock_process = debugger_manager.get_process()

        mock_thread = MagicMock()
        mock_thread.IsValid.return_value = True
        mock_process.GetThreadByID.return_value = mock_thread

        result = debugger_manager._get_thread(thread_id=123)

        assert result == mock_thread
        mock_process.GetThreadByID.assert_called_once_with(123)

    def test_get_thread_by_invalid_id(self, debugger_manager):
        """Test getting thread with invalid ID raises ValueError"""
        mock_process = debugger_manager.get_process()

        mock_thread = MagicMock()
        mock_thread.IsValid.return_value = False
        mock_process.GetThreadByID.return_value = mock_thread

        with pytest.raises(ValueError, match="Invalid thread ID: 999"):
            debugger_manager._get_thread(thread_id=999)

    def test_get_thread_selected(self, debugger_manager):
        """Test getting selected thread when no ID specified"""
        mock_process = debugger_manager.get_process()

        mock_thread = MagicMock()
        mock_thread.IsValid.return_value = True
        mock_process.GetSelectedThread.return_value = mock_thread

        result = debugger_manager._get_thread()

        assert result == mock_thread
        mock_process.GetSelectedThread.assert_called_once()

    def test_get_thread_no_valid_selected(self, debugger_manager):
        """Test getting selected thread when none is valid raises ValueError"""
        mock_process = debugger_manager.get_process()

        mock_thread = MagicMock()
        mock_thread.IsValid.return_value = False
        mock_process.GetSelectedThread.return_value = mock_thread

        with pytest.raises(ValueError, match="No valid thread selected"):
            debugger_manager._get_thread()
