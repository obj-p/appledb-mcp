#!/usr/bin/env python3
"""Manual test script for appledb-mcp tools"""

import asyncio
import sys

# Add LLDB to path
sys.path.insert(0, '/Applications/Xcode-26.2.0.app/Contents/SharedFrameworks/LLDB.framework/Resources/Python')

from appledb_mcp.config import AppleDBConfig
from appledb_mcp.debugger import LLDBDebuggerManager


async def test_attach_by_pid(pid: int):
    """Test attaching to a process by PID"""
    print(f"\n=== Testing attach to PID {pid} ===")

    # Initialize debugger
    config = AppleDBConfig()
    manager = LLDBDebuggerManager.get_instance()
    manager.initialize(config)

    print(f"✓ LLDB initialized")

    # Attach to process
    try:
        process_info = await manager.attach_process_by_pid(pid)
        print(f"✓ Attached to process:")
        print(f"  - PID: {process_info.pid}")
        print(f"  - Name: {process_info.name}")
        print(f"  - State: {process_info.state}")
        print(f"  - Architecture: {process_info.architecture}")

        # Get debugger state
        state = manager.get_state()
        print(f"  - Manager state: {state.value}")

        # Detach
        print("\n=== Testing detach ===")
        await manager.detach()
        print("✓ Detached successfully")

        state = manager.get_state()
        print(f"  - Manager state after detach: {state.value}")

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        await manager.cleanup()


async def test_attach_by_name(name: str):
    """Test attaching to a process by name"""
    print(f"\n=== Testing attach to process name '{name}' ===")

    # Initialize debugger
    config = AppleDBConfig()
    manager = LLDBDebuggerManager.get_instance()

    # Reinitialize since we cleaned up
    manager._debugger = None
    manager._initialized = False
    manager.initialize(config)

    print(f"✓ LLDB initialized")

    try:
        process_info = await manager.attach_process_by_name(name)
        print(f"✓ Attached to process:")
        print(f"  - PID: {process_info.pid}")
        print(f"  - Name: {process_info.name}")

        # Detach
        await manager.detach()
        print("✓ Detached successfully")

    except Exception as e:
        print(f"✗ Error: {e}")
    finally:
        await manager.cleanup()


async def main():
    if len(sys.argv) < 2:
        print("Usage: python test_manual.py <pid>")
        sys.exit(1)

    pid = int(sys.argv[1])

    # Test attach by PID
    await test_attach_by_pid(pid)

    # Test attach by name
    await test_attach_by_name("test_app")


if __name__ == "__main__":
    asyncio.run(main())
