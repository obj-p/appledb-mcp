#!/usr/bin/env python3
"""Test script for LLDB service

This script tests basic JSON-RPC communication with the LLDB service.
"""

import json
import subprocess
import sys
import time


def send_request(proc, method, params=None, request_id=1):
    """Send JSON-RPC request to service.

    Args:
        proc: Subprocess instance
        method: RPC method name
        params: Optional parameters dict
        request_id: Request ID

    Returns:
        Response dict
    """
    request = {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": method,
    }
    if params is not None:
        request["params"] = params

    # Send request
    request_str = json.dumps(request) + "\n"
    proc.stdin.write(request_str.encode())
    proc.stdin.flush()

    # Read response
    response_str = proc.stdout.readline().decode()
    return json.loads(response_str)


def test_ping(proc):
    """Test ping method."""
    print("Testing ping...")
    response = send_request(proc, "ping")

    if response.get("result") == "pong":
        print("✓ Ping test passed")
        return True
    else:
        print(f"✗ Ping test failed: {response}")
        return False


def test_initialize(proc):
    """Test initialize method."""
    print("Testing initialize...")
    config = {"max_backtrace_frames": 50}
    response = send_request(proc, "initialize", {"config": config})

    if response.get("result", {}).get("success"):
        print("✓ Initialize test passed")
        return True
    else:
        print(f"✗ Initialize test failed: {response}")
        return False


def test_get_debugger_state(proc):
    """Test get_debugger_state method."""
    print("Testing get_debugger_state...")
    response = send_request(proc, "get_debugger_state")

    result = response.get("result", {})
    if "attached" in result and "state" in result:
        print(f"✓ Get debugger state test passed: attached={result['attached']}, state={result['state']}")
        return True
    else:
        print(f"✗ Get debugger state test failed: {response}")
        return False


def test_attach_detach(proc):
    """Test attach and detach with a sleep process."""
    print("Testing attach and detach...")

    # Start a sleep process
    sleep_proc = subprocess.Popen(["/bin/sleep", "60"])
    pid = sleep_proc.pid
    print(f"Started sleep process with PID {pid}")

    # Give it a moment to start
    time.sleep(0.5)

    try:
        # Test attach
        response = send_request(proc, "attach_process", {"pid": pid})
        result = response.get("result", {})

        if result.get("pid") == pid:
            print(f"✓ Attach test passed: attached to PID {pid}")
        else:
            print(f"✗ Attach test failed: {response}")
            sleep_proc.kill()
            return False

        # Test detach
        response = send_request(proc, "detach", {"kill": False})
        if response.get("result", {}).get("success"):
            print("✓ Detach test passed")
            sleep_proc.kill()
            return True
        else:
            print(f"✗ Detach test failed: {response}")
            sleep_proc.kill()
            return False

    except Exception as e:
        print(f"✗ Attach/detach test failed with error: {e}")
        sleep_proc.kill()
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("LLDB Service Test Suite")
    print("=" * 60)

    # Start LLDB service
    print("\nStarting LLDB service...")
    proc = subprocess.Popen(
        ["/usr/bin/python3", "-m", "lldb_service"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd="/Users/obj-p/Projects/appledb-mcp/src",
    )

    # Wait for ready signal
    print("Waiting for ready signal...")
    try:
        ready_line = proc.stdout.readline().decode()
        ready_msg = json.loads(ready_line)
        if ready_msg.get("method") == "ready":
            print("✓ Ready signal received")
        else:
            print(f"✗ Unexpected first message: {ready_msg}")
            proc.terminate()
            return 1
    except Exception as e:
        print(f"✗ Failed to receive ready signal: {e}")
        proc.terminate()
        return 1

    # Run tests
    results = []

    try:
        results.append(test_ping(proc))
        results.append(test_initialize(proc))
        results.append(test_get_debugger_state(proc))
        results.append(test_attach_detach(proc))

    except Exception as e:
        print(f"\n✗ Test suite failed with error: {e}")
        proc.terminate()
        return 1

    finally:
        # Cleanup
        print("\nCleaning up...")
        try:
            send_request(proc, "cleanup")
        except:
            pass
        proc.terminate()
        proc.wait(timeout=2)

    # Print summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total}")

    if passed == total:
        print("\n✓ All tests passed!")
        return 0
    else:
        print(f"\n✗ {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
