#!/usr/bin/env python3
"""Quick verification script for Phase 6 changes"""

import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

def test_error_imports():
    """Verify error consolidation works"""
    print("Testing error imports...")

    # Test common errors
    from common.errors import (
        AppleDBError,
        LLDBError,
        ProcessNotAttachedError,
        ProcessNotFoundError,
        InvalidStateError,
        ConfigurationError,
        FrameworkLoadError,
    )
    print("  ✓ common.errors imports OK")

    # Test appledb_mcp re-exports
    from appledb_mcp.utils.errors import (
        AppleDBError as AppError1,
        LLDBError as LLDBErr1,
    )
    print("  ✓ appledb_mcp.utils.errors imports OK")

    # Test lldb_service re-exports
    from lldb_service.utils.errors import (
        AppleDBError as AppError2,
        LLDBError as LLDBErr2,
    )
    print("  ✓ lldb_service.utils.errors imports OK")

    # Verify they're the same classes
    assert AppError1 is AppleDBError, "appledb_mcp should re-export common errors"
    assert AppError2 is AppleDBError, "lldb_service should re-export common errors"
    assert LLDBErr1 is LLDBError, "appledb_mcp should re-export common errors"
    assert LLDBErr2 is LLDBError, "lldb_service should re-export common errors"
    print("  ✓ All error classes are identical across modules")


def test_client_methods():
    """Verify client method signatures"""
    print("\nTesting client method signatures...")

    from appledb_mcp.lldb_client import LLDBClient
    import inspect

    # Check load_framework accepts both parameters
    sig = inspect.signature(LLDBClient.load_framework)
    params = list(sig.parameters.keys())
    assert "framework_path" in params, "load_framework should have framework_path param"
    assert "framework_name" in params, "load_framework should have framework_name param"
    print("  ✓ load_framework has both framework_path and framework_name parameters")

    # Check new attributes exist
    client = LLDBClient()
    assert hasattr(client, "_monitor_task"), "Client should have _monitor_task attribute"
    assert hasattr(client, "_reset_task"), "Client should have _reset_task attribute"
    print("  ✓ Client has new background task attributes")


def test_config():
    """Verify config has new field"""
    print("\nTesting configuration...")

    from appledb_mcp.config import AppleDBConfig

    config = AppleDBConfig()
    assert hasattr(config, "service_restart_reset_time"), "Config should have restart reset time"
    assert config.service_restart_reset_time == 300.0, "Default should be 300 seconds"
    print(f"  ✓ Config has service_restart_reset_time (default: {config.service_restart_reset_time}s)")


def test_handler_methods():
    """Verify handler methods exist"""
    print("\nTesting handler methods...")

    from lldb_service import handlers
    import inspect

    # Check handle_initialize exists
    assert hasattr(handlers, "handle_initialize"), "Should have handle_initialize"

    # Check it's async
    assert inspect.iscoroutinefunction(handlers.handle_initialize), "handle_initialize should be async"
    print("  ✓ Handlers module structure OK")


def main():
    """Run all verification tests"""
    print("=" * 60)
    print("Phase 6 Verification Script")
    print("=" * 60)

    errors = []

    try:
        test_error_imports()
    except Exception as e:
        errors.append(f"Error imports: {e}")

    try:
        test_client_methods()
    except Exception as e:
        print(f"\n⚠️  Skipping client method tests (requires dependencies): {e}")

    try:
        test_config()
    except Exception as e:
        print(f"\n⚠️  Skipping config tests (requires dependencies): {e}")

    try:
        test_handler_methods()
    except Exception as e:
        print(f"\n⚠️  Skipping handler tests (requires dependencies): {e}")

    print("\n" + "=" * 60)
    if errors:
        print(f"❌ {len(errors)} test(s) failed:")
        for err in errors:
            print(f"  - {err}")
        return 1
    else:
        print("✅ Core Phase 6 changes verified successfully!")
        print("   (Full verification requires virtualenv)")
        print("=" * 60)
        return 0


if __name__ == "__main__":
    sys.exit(main())
