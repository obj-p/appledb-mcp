"""Unit tests for LLDBClient with mocked subprocess

These tests mock the subprocess to verify JSON-RPC communication,
error handling, and state management without requiring LLDB.
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from appledb_mcp.config import AppleDBConfig
from appledb_mcp.lldb_client import LLDBClient
from appledb_mcp.models import ProcessInfo
from appledb_mcp.utils.errors import (
    InvalidStateError,
    LLDBError,
    ProcessNotAttachedError,
)


@pytest.fixture
def config():
    """Create test configuration"""
    return AppleDBConfig(
        lldb_timeout=10,
        log_level="DEBUG",
        python_path="python3",
        service_request_timeout=5.0,
        service_max_restarts=3,
        service_restart_backoff=1.0,
    )


@pytest.fixture
async def mock_subprocess():
    """Create mock subprocess with stdin/stdout/stderr"""
    mock_proc = MagicMock()
    mock_proc.pid = 12345
    mock_proc.returncode = None

    # Create mock streams
    mock_proc.stdin = AsyncMock()
    mock_proc.stdin.write = MagicMock()
    mock_proc.stdin.drain = AsyncMock()

    mock_proc.stdout = AsyncMock()
    mock_proc.stderr = AsyncMock()

    # Queue for responses
    response_queue = asyncio.Queue()

    async def readline_stdout():
        """Simulate readline from stdout"""
        try:
            line = await response_queue.get()
            return line
        except asyncio.CancelledError:
            return b""

    async def readline_stderr():
        """Simulate readline from stderr"""
        await asyncio.sleep(0.01)
        return b""

    mock_proc.stdout.readline = readline_stdout
    mock_proc.stderr.readline = readline_stderr
    mock_proc.wait = AsyncMock()
    mock_proc.terminate = MagicMock()
    mock_proc.kill = MagicMock()

    # Store queue for test access
    mock_proc._response_queue = response_queue

    return mock_proc


@pytest.fixture
async def client(config, mock_subprocess):
    """Create LLDBClient with mocked subprocess"""
    client = LLDBClient.get_instance()

    # Reset instance state for clean test
    client._process = None
    client._pending_requests.clear()
    client._restart_count = 0

    with patch("asyncio.create_subprocess_exec", return_value=mock_subprocess):
        # Send ready notification after initialization
        async def send_ready():
            await asyncio.sleep(0.01)
            await mock_subprocess._response_queue.put(
                json.dumps({"jsonrpc": "2.0", "method": "ready"}).encode() + b"\n"
            )

        asyncio.create_task(send_ready())

        await client.initialize(config)

    yield client

    # Cleanup
    if client._reader_task and not client._reader_task.done():
        client._reader_task.cancel()
        try:
            await client._reader_task
        except asyncio.CancelledError:
            pass
    if client._stderr_task and not client._stderr_task.done():
        client._stderr_task.cancel()
        try:
            await client._stderr_task
        except asyncio.CancelledError:
            pass


@pytest.mark.asyncio
async def test_singleton_pattern():
    """Test that LLDBClient follows singleton pattern"""
    instance1 = LLDBClient.get_instance()
    instance2 = LLDBClient.get_instance()
    assert instance1 is instance2


@pytest.mark.asyncio
async def test_python_version_check():
    """Test Python version checking"""
    client = LLDBClient.get_instance()
    config = AppleDBConfig()

    # Test with valid Python 3.9+
    assert client._check_python_version("python3") is True


@pytest.mark.asyncio
async def test_successful_rpc_call(client, mock_subprocess):
    """Test successful JSON-RPC call"""

    # Queue response
    async def send_response():
        await asyncio.sleep(0.01)
        response = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {"pid": 1234, "name": "test", "state": "stopped", "architecture": "arm64"},
        }
        await mock_subprocess._response_queue.put(
            json.dumps(response).encode() + b"\n"
        )

    asyncio.create_task(send_response())

    # Call attach_process_by_pid
    result = await client.attach_process_by_pid(1234)

    assert isinstance(result, ProcessInfo)
    assert result.pid == 1234
    assert result.name == "test"


@pytest.mark.asyncio
async def test_rpc_error_mapping(client, mock_subprocess):
    """Test that RPC errors are mapped to correct exceptions"""

    # Queue error response
    async def send_error():
        await asyncio.sleep(0.01)
        response = {
            "jsonrpc": "2.0",
            "id": 1,
            "error": {"code": -32001, "message": "No process attached"},
        }
        await mock_subprocess._response_queue.put(
            json.dumps(response).encode() + b"\n"
        )

    asyncio.create_task(send_error())

    # Call should raise ProcessNotAttachedError
    with pytest.raises(ProcessNotAttachedError, match="No process attached"):
        await client.continue_execution()


@pytest.mark.asyncio
async def test_rpc_timeout(client, mock_subprocess):
    """Test RPC timeout handling"""
    # Don't send response - should timeout
    with pytest.raises(RuntimeError, match="timed out"):
        await client._call("test_method", {}, timeout=0.1)


@pytest.mark.asyncio
async def test_error_code_mapping():
    """Test error code to exception mapping"""
    # Create client without initializing
    client = LLDBClient.get_instance()

    # Test various error codes
    test_cases = [
        (-32000, LLDBError),
        (-32001, ProcessNotAttachedError),
        (-32002, InvalidStateError),
        (-32602, ValueError),
        (-32603, RuntimeError),
    ]

    for code, expected_exception in test_cases:
        error = {"code": code, "message": "Test error"}
        exc = client._map_error_to_exception(error)
        assert isinstance(exc, expected_exception)


@pytest.mark.asyncio
async def test_config_to_dict(config):
    """Test configuration conversion to dict"""
    client = LLDBClient.get_instance()
    config_dict = client._config_to_dict(config)

    assert config_dict["lldb_timeout"] == config.lldb_timeout
    assert config_dict["log_level"] == config.log_level
    assert config_dict["max_backtrace_frames"] == config.max_backtrace_frames
    assert config_dict["max_variable_depth"] == config.max_variable_depth


@pytest.mark.asyncio
async def test_all_api_methods_exist():
    """Test that all required API methods exist"""
    client = LLDBClient.get_instance()

    required_methods = [
        "attach_process_by_pid",
        "attach_process_by_name",
        "launch_app",
        "detach",
        "continue_execution",
        "pause_execution",
        "step_over",
        "step_into",
        "step_out",
        "evaluate_expression",
        "get_backtrace",
        "get_variables",
        "load_framework",
        "get_debugger_state",
        "ping",
    ]

    for method_name in required_methods:
        assert hasattr(client, method_name)
        method = getattr(client, method_name)
        assert callable(method)


@pytest.mark.asyncio
async def test_cleanup(client, mock_subprocess):
    """Test cleanup process"""
    # Queue cleanup response
    async def send_cleanup_response():
        await asyncio.sleep(0.01)
        response = {"jsonrpc": "2.0", "id": client._request_id_counter, "result": None}
        await mock_subprocess._response_queue.put(
            json.dumps(response).encode() + b"\n"
        )

    asyncio.create_task(send_cleanup_response())

    await client.cleanup()

    # Verify tasks are cancelled
    assert client._reader_task is None or client._reader_task.done()
    assert client._stderr_task is None or client._stderr_task.done()
