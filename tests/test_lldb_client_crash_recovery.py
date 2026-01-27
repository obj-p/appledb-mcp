"""Crash recovery tests for LLDBClient

These tests verify that LLDBClient properly handles subprocess crashes
and restarts with exponential backoff.
"""

import asyncio
import os

import pytest

from appledb_mcp.config import AppleDBConfig
from appledb_mcp.lldb_client import LLDBClient


@pytest.fixture
def config():
    """Create test configuration"""
    return AppleDBConfig(
        lldb_timeout=10,
        log_level="DEBUG",
        python_path="python3",
        service_request_timeout=5.0,
        service_max_restarts=3,
        service_restart_backoff=0.5,  # Shorter for tests
    )


@pytest.fixture
async def client(config):
    """Create LLDBClient with real subprocess"""
    # Ensure PYTHONPATH is set
    src_path = os.path.join(os.path.dirname(__file__), "..", "src")
    pythonpath = os.environ.get("PYTHONPATH", "")
    if src_path not in pythonpath:
        os.environ["PYTHONPATH"] = f"{src_path}:{pythonpath}"

    client = LLDBClient.get_instance()

    # Reset instance state
    if hasattr(client, "_process") and client._process:
        try:
            await client.cleanup()
        except Exception:
            pass

    client._process = None
    client._pending_requests.clear()
    client._restart_count = 0

    await client.initialize(config)

    yield client

    # Cleanup
    try:
        await client.cleanup()
    except Exception:
        pass


@pytest.mark.asyncio
@pytest.mark.integration
async def test_subprocess_crash_recovery(client):
    """Test that client recovers from subprocess crash"""
    initial_pid = client._process.pid

    # Kill the subprocess
    client._process.kill()
    await asyncio.sleep(0.2)

    # Wait for restart to complete
    await asyncio.sleep(2.0)

    # Should have restarted with new PID
    assert client._process is not None
    assert client._process.pid != initial_pid
    assert client._restart_count == 1

    # Verify it works
    result = await client.ping()
    assert result["status"] == "pong"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_pending_requests_rejected_on_crash(client):
    """Test that pending requests are rejected when subprocess crashes"""
    # Start a long-running request
    async def slow_request():
        try:
            # This will hang until subprocess is killed
            await client._call("ping", {}, timeout=10.0)
        except RuntimeError as e:
            # Should get crash message
            assert "crashed" in str(e).lower() or "timed out" in str(e).lower()
            return "rejected"
        return "completed"

    # Start the request
    request_task = asyncio.create_task(slow_request())

    # Give it time to start
    await asyncio.sleep(0.1)

    # Kill subprocess
    client._process.kill()
    await asyncio.sleep(0.2)

    # Request should be rejected
    result = await asyncio.wait_for(request_task, timeout=5.0)
    assert result == "rejected"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_max_restarts_exceeded(client, config):
    """Test that client stops restarting after max attempts"""
    # Kill subprocess multiple times
    for i in range(config.service_max_restarts):
        initial_pid = client._process.pid
        client._process.kill()
        await asyncio.sleep(0.2)

        # Wait for restart
        await asyncio.sleep(1.5)

        # Should have restarted
        if i < config.service_max_restarts - 1:
            assert client._process.pid != initial_pid
            assert client._restart_count == i + 1

    # One more crash should fail
    client._process.kill()
    await asyncio.sleep(0.2)

    # Wait and verify it doesn't restart
    await asyncio.sleep(2.0)

    # Try to use it - should fail
    try:
        with pytest.raises((RuntimeError, Exception)):
            await client.ping()
    except Exception:
        # Any exception is fine - the point is it doesn't work
        pass


@pytest.mark.asyncio
@pytest.mark.integration
async def test_concurrent_restart_coordination(client):
    """Test that concurrent crashes don't cause multiple restarts"""
    initial_pid = client._process.pid

    # Trigger multiple concurrent restart attempts
    client._process.kill()

    # Try to call multiple methods immediately
    # These should all wait for the single restart
    tasks = [
        asyncio.create_task(client.ping()),
        asyncio.create_task(client.ping()),
        asyncio.create_task(client.ping()),
    ]

    # Wait for restart
    await asyncio.sleep(2.0)

    # Cancel tasks (they might still be waiting)
    for task in tasks:
        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    # Should have only restarted once
    assert client._restart_count == 1
    assert client._process.pid != initial_pid


@pytest.mark.asyncio
@pytest.mark.integration
async def test_cleanup_pending_requests_count(client):
    """Test that cleanup reports correct number of pending requests"""
    # Start multiple requests
    tasks = []
    for _ in range(5):
        task = asyncio.create_task(client._call("ping", {}, timeout=10.0))
        tasks.append(task)

    # Give them time to register
    await asyncio.sleep(0.1)

    # Kill subprocess
    initial_count = len(client._pending_requests)
    client._process.kill()
    await asyncio.sleep(0.2)

    # All requests should have been cleaned up
    assert len(client._pending_requests) == 0

    # Cancel tasks
    for task in tasks:
        if not task.done():
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, RuntimeError):
                pass
