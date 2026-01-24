#!/usr/bin/env python3
"""Integration test for MCP tools - tests without LLDB"""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

# Import the tools
from appledb_mcp.tools.process import lldb_attach_process, lldb_launch_app, lldb_detach
from appledb_mcp.models import ProcessInfo


async def test_tools():
    """Test that MCP tools work correctly with mocked LLDB"""
    print("\n=== Testing MCP Tools ===\n")

    # Mock the debugger manager
    with patch('appledb_mcp.tools.process.LLDBDebuggerManager') as mock_manager_class:
        mock_manager = Mock()
        mock_manager_class.get_instance.return_value = mock_manager

        # Test 1: Attach by PID
        print("Test 1: Attach by PID")
        mock_manager.attach_process_by_pid = AsyncMock(
            return_value=ProcessInfo(
                pid=12345,
                name="test_app",
                state="stopped",
                architecture="arm64"
            )
        )

        result = await lldb_attach_process(pid=12345)
        print(f"  Result: {result}")
        assert "12345" in result
        assert "test_app" in result
        print("  ✅ PASSED\n")

        # Test 2: Attach by name
        print("Test 2: Attach by name")
        mock_manager.attach_process_by_name = AsyncMock(
            return_value=ProcessInfo(
                pid=67890,
                name="MyApp",
                state="stopped",
                architecture="x86_64"
            )
        )

        result = await lldb_attach_process(name="MyApp")
        print(f"  Result: {result}")
        assert "67890" in result
        assert "MyApp" in result
        print("  ✅ PASSED\n")

        # Test 3: Launch app
        print("Test 3: Launch app")
        mock_manager.launch_app = AsyncMock(
            return_value=ProcessInfo(
                pid=11111,
                name="MyApp",
                state="stopped",
                architecture="arm64"
            )
        )

        result = await lldb_launch_app(executable="/path/to/MyApp")
        print(f"  Result: {result}")
        assert "11111" in result
        assert "MyApp" in result
        print("  ✅ PASSED\n")

        # Test 4: Detach
        print("Test 4: Detach")
        mock_manager.detach = AsyncMock()

        result = await lldb_detach()
        print(f"  Result: {result}")
        assert "detached" in result.lower()
        print("  ✅ PASSED\n")

        # Test 5: Error handling - no PID or name
        print("Test 5: Error handling - no PID or name")
        result = await lldb_attach_process()
        print(f"  Result: {result}")
        assert "Error" in result
        print("  ✅ PASSED\n")

    print("=== All MCP tool tests passed! ===\n")


if __name__ == "__main__":
    asyncio.run(test_tools())
