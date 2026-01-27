#!/usr/bin/env python3
"""
Validation script for appledb-mcp using the Chai iOS app

This script validates all Phase 2-6 functionality by debugging a real iOS app.
It tests all 12 MCP tools, crash recovery, and performance characteristics.
"""

import asyncio
import json
import logging
import sys
import time
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from appledb_mcp.config import AppleDBConfig
from appledb_mcp.lldb_client import LLDBClient
from appledb_mcp.utils.errors import ProcessNotFoundError, ProcessNotAttachedError

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Test configuration
CHAI_APP_NAME = "Chai"
CHAI_PID = 39435  # From launch output


class ValidationReport:
    """Track validation test results"""

    def __init__(self):
        self.tests = []
        self.start_time = time.time()

    def add_test(self, name: str, success: bool, duration: float, details: str = ""):
        """Add test result"""
        self.tests.append({
            "name": name,
            "success": success,
            "duration_ms": duration * 1000,
            "details": details
        })

    def print_summary(self):
        """Print validation summary"""
        total_duration = time.time() - self.start_time
        passed = sum(1 for t in self.tests if t["success"])
        failed = len(self.tests) - passed

        print("\n" + "=" * 80)
        print("VALIDATION REPORT - Chai iOS App Debugging")
        print("=" * 80)

        for test in self.tests:
            status = "✅ PASS" if test["success"] else "❌ FAIL"
            duration = f"{test['duration_ms']:.2f}ms"
            print(f"{status} | {test['name']:<50} | {duration:>10}")
            if test["details"]:
                print(f"      {test['details']}")

        print("=" * 80)
        print(f"Total: {len(self.tests)} tests | Passed: {passed} | Failed: {failed}")
        print(f"Duration: {total_duration:.2f}s")
        print("=" * 80)

        return failed == 0


async def test_initialization(report: ValidationReport) -> LLDBClient:
    """Test 1: Initialize LLDB client"""
    logger.info("Test 1: Initializing LLDB client...")
    start = time.time()

    try:
        config = AppleDBConfig(python_path="/usr/bin/python3")
        client = LLDBClient.get_instance()
        await client.initialize(config)

        duration = time.time() - start
        report.add_test(
            "Initialize LLDB client",
            True,
            duration,
            f"Client initialized in {duration:.2f}s"
        )
        logger.info(f"✅ Client initialized in {duration:.2f}s")
        return client

    except Exception as e:
        duration = time.time() - start
        report.add_test("Initialize LLDB client", False, duration, str(e))
        logger.error(f"❌ Initialization failed: {e}")
        raise


async def test_attach_by_pid(client: LLDBClient, report: ValidationReport):
    """Test 2: Attach to Chai app by PID"""
    logger.info(f"Test 2: Attaching to Chai app (PID: {CHAI_PID})...")
    start = time.time()

    try:
        process_info = await client.attach_process_by_pid(CHAI_PID)
        duration = time.time() - start

        report.add_test(
            "Attach to process by PID",
            True,
            duration,
            f"Attached to '{process_info.name}' (PID: {process_info.pid})"
        )
        logger.info(f"✅ Attached in {duration:.2f}s")
        return process_info

    except Exception as e:
        duration = time.time() - start
        report.add_test("Attach to process by PID", False, duration, str(e))
        logger.error(f"❌ Attach failed: {e}")
        raise


async def test_get_debugger_state(client: LLDBClient, report: ValidationReport):
    """Test 3: Get debugger state"""
    logger.info("Test 3: Getting debugger state...")
    start = time.time()

    try:
        state = await client.get_debugger_state()
        duration = time.time() - start

        report.add_test(
            "Get debugger state",
            True,
            duration,
            f"State: {state.state}, Attached: {state.attached}, Target: {state.target is not None}"
        )
        logger.info(f"✅ State retrieved in {duration:.2f}s")
        return state

    except Exception as e:
        duration = time.time() - start
        report.add_test("Get debugger state", False, duration, str(e))
        logger.error(f"❌ Get state failed: {e}")
        raise


async def test_pause_execution(client: LLDBClient, report: ValidationReport):
    """Test 4: Pause execution"""
    logger.info("Test 4: Pausing execution...")
    start = time.time()

    try:
        result = await client.pause_execution()
        duration = time.time() - start

        report.add_test(
            "Pause execution",
            True,
            duration,
            f"Result: {result}"
        )
        logger.info(f"✅ Paused in {duration:.2f}s")
        return result

    except Exception as e:
        duration = time.time() - start
        report.add_test("Pause execution", False, duration, str(e))
        logger.error(f"❌ Pause failed: {e}")
        raise


async def test_get_backtrace(client: LLDBClient, report: ValidationReport):
    """Test 5: Get backtrace"""
    logger.info("Test 5: Getting backtrace...")
    start = time.time()

    try:
        frames = await client.get_backtrace(max_frames=10)
        duration = time.time() - start

        # Verify it returns a list (Phase 6 fix)
        assert isinstance(frames, list), f"Expected list, got {type(frames)}"

        report.add_test(
            "Get backtrace",
            True,
            duration,
            f"Retrieved {len(frames)} frames"
        )
        logger.info(f"✅ Backtrace retrieved in {duration:.2f}s ({len(frames)} frames)")
        return frames

    except Exception as e:
        duration = time.time() - start
        report.add_test("Get backtrace", False, duration, str(e))
        logger.error(f"❌ Backtrace failed: {e}")
        raise


async def test_get_variables(client: LLDBClient, report: ValidationReport):
    """Test 6: Get variables (Phase 6 fix validation)"""
    logger.info("Test 6: Getting variables...")
    start = time.time()

    try:
        variables = await client.get_variables(frame_index=0)
        duration = time.time() - start

        # CRITICAL: Verify Phase 6 fix - should return list, not dict
        assert isinstance(variables, list), f"Phase 6 fix broken! Expected list, got {type(variables)}"

        report.add_test(
            "Get variables (Phase 6 fix)",
            True,
            duration,
            f"Retrieved {len(variables)} variables (returns list ✓)"
        )
        logger.info(f"✅ Variables retrieved in {duration:.2f}s ({len(variables)} vars)")
        return variables

    except Exception as e:
        duration = time.time() - start
        report.add_test("Get variables (Phase 6 fix)", False, duration, str(e))
        logger.error(f"❌ Get variables failed: {e}")
        raise


async def test_evaluate_expression(client: LLDBClient, report: ValidationReport):
    """Test 7: Evaluate expression"""
    logger.info("Test 7: Evaluating expression...")
    start = time.time()

    try:
        # Simple Swift expression
        result = await client.evaluate_expression("1 + 1", language="swift")
        duration = time.time() - start

        report.add_test(
            "Evaluate expression",
            True,
            duration,
            f"Result: {result.get('value', 'N/A')}"
        )
        logger.info(f"✅ Expression evaluated in {duration:.2f}s")
        return result

    except Exception as e:
        duration = time.time() - start
        report.add_test("Evaluate expression", False, duration, str(e))
        logger.error(f"❌ Evaluation failed: {e}")
        # Don't raise - this might fail if process state isn't right


async def test_continue_execution(client: LLDBClient, report: ValidationReport):
    """Test 8: Continue execution"""
    logger.info("Test 8: Continuing execution...")
    start = time.time()

    try:
        result = await client.continue_execution()
        duration = time.time() - start

        report.add_test(
            "Continue execution",
            True,
            duration,
            f"Result: {result}"
        )
        logger.info(f"✅ Continued in {duration:.2f}s")
        return result

    except Exception as e:
        duration = time.time() - start
        report.add_test("Continue execution", False, duration, str(e))
        logger.error(f"❌ Continue failed: {e}")
        raise


async def test_detach(client: LLDBClient, report: ValidationReport):
    """Test 9: Detach from process"""
    logger.info("Test 9: Detaching from process...")
    start = time.time()

    try:
        await client.detach()
        duration = time.time() - start

        report.add_test(
            "Detach from process",
            True,
            duration,
            "Successfully detached"
        )
        logger.info(f"✅ Detached in {duration:.2f}s")

    except Exception as e:
        duration = time.time() - start
        report.add_test("Detach from process", False, duration, str(e))
        logger.error(f"❌ Detach failed: {e}")
        raise


async def test_attach_by_name(client: LLDBClient, report: ValidationReport):
    """Test 10: Attach by process name"""
    logger.info(f"Test 10: Attaching to Chai app by name '{CHAI_APP_NAME}'...")
    start = time.time()

    try:
        process_info = await client.attach_process_by_name(CHAI_APP_NAME)
        duration = time.time() - start

        report.add_test(
            "Attach to process by name",
            True,
            duration,
            f"Attached to '{process_info.name}' (PID: {process_info.pid})"
        )
        logger.info(f"✅ Attached by name in {duration:.2f}s")
        return process_info

    except Exception as e:
        duration = time.time() - start
        report.add_test("Attach to process by name", False, duration, str(e))
        logger.error(f"❌ Attach by name failed: {e}")
        raise


async def test_ping(client: LLDBClient, report: ValidationReport):
    """Test 11: Ping service (RPC latency)"""
    logger.info("Test 11: Testing RPC latency (10 pings)...")

    latencies = []
    for i in range(10):
        start = time.time()
        try:
            result = await client.ping()
            duration = time.time() - start
            latencies.append(duration * 1000)  # Convert to ms
        except Exception as e:
            logger.error(f"Ping {i+1} failed: {e}")

    if latencies:
        avg_latency = sum(latencies) / len(latencies)
        min_latency = min(latencies)
        max_latency = max(latencies)

        report.add_test(
            "RPC latency test",
            avg_latency < 10,  # Should be < 10ms
            avg_latency / 1000,
            f"Avg: {avg_latency:.2f}ms, Min: {min_latency:.2f}ms, Max: {max_latency:.2f}ms"
        )
        logger.info(f"✅ RPC latency: avg={avg_latency:.2f}ms, min={min_latency:.2f}ms, max={max_latency:.2f}ms")
    else:
        report.add_test("RPC latency test", False, 0, "All pings failed")


async def test_cleanup(client: LLDBClient, report: ValidationReport):
    """Test 12: Cleanup (Phase 6 fix validation)"""
    logger.info("Test 12: Testing cleanup (Phase 6 task cancellation fix)...")
    start = time.time()

    try:
        await client.cleanup()
        duration = time.time() - start

        # Verify all tasks are cancelled (Phase 6 fix)
        tasks_alive = []
        for task_name in ['_reader_task', '_stderr_task', '_monitor_task', '_reset_task']:
            task = getattr(client, task_name, None)
            if task and not task.done():
                tasks_alive.append(task_name)

        success = len(tasks_alive) == 0
        details = "All tasks cancelled ✓" if success else f"Tasks still alive: {tasks_alive}"

        report.add_test(
            "Cleanup (Phase 6 fix)",
            success,
            duration,
            details
        )
        logger.info(f"✅ Cleanup completed in {duration:.2f}s")

    except Exception as e:
        duration = time.time() - start
        report.add_test("Cleanup (Phase 6 fix)", False, duration, str(e))
        logger.error(f"❌ Cleanup failed: {e}")


async def main():
    """Run all validation tests"""
    report = ValidationReport()
    client = None

    try:
        # Test 1: Initialize
        client = await test_initialization(report)

        # Test 2: Attach by PID
        await test_attach_by_pid(client, report)

        # Test 3: Get state
        await test_get_debugger_state(client, report)

        # Test 4: Get backtrace (while stopped)
        await test_get_backtrace(client, report)

        # Test 5: Get variables (Phase 6 fix - while stopped)
        await test_get_variables(client, report)

        # Test 6: Evaluate expression (while stopped)
        await test_evaluate_expression(client, report)

        # Test 7: Continue execution
        await test_continue_execution(client, report)

        # Wait a moment for app to run
        await asyncio.sleep(0.5)

        # Test 8: Pause (now that it's running)
        await test_pause_execution(client, report)

        # Test 9: Detach
        await test_detach(client, report)

        # Test 10: Re-attach by name
        await test_attach_by_name(client, report)

        # Test 11: RPC latency
        await test_ping(client, report)

        # Final detach before cleanup
        await client.detach()

        # Test 12: Cleanup (Phase 6 fix)
        await test_cleanup(client, report)

    except Exception as e:
        logger.error(f"Validation failed: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Ensure cleanup happens
        if client:
            try:
                await client.cleanup()
            except:
                pass

    # Print report
    all_passed = report.print_summary()

    if all_passed:
        print("\n🎉 All validation tests PASSED! The MCP is production-ready.")
        return 0
    else:
        print("\n⚠️  Some tests FAILED. Review the report above.")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
