#!/usr/bin/env python3
"""Comprehensive test suite for LLDB service

Tests error handling, edge cases, and sequential requests.
"""

import json
import subprocess
import sys
import time


def send_request(proc, method, params=None, request_id=1):
    """Send JSON-RPC request and get response."""
    request = {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": method,
    }
    if params is not None:
        request["params"] = params

    request_str = json.dumps(request) + "\n"
    proc.stdin.write(request_str.encode())
    proc.stdin.flush()

    response_str = proc.stdout.readline().decode()
    return json.loads(response_str)


def test_invalid_json(proc):
    """Test that service handles invalid JSON gracefully."""
    print("Testing invalid JSON handling...")

    # Send invalid JSON
    proc.stdin.write(b"not valid json\n")
    proc.stdin.flush()

    response_str = proc.stdout.readline().decode()
    response = json.loads(response_str)

    if response.get("error", {}).get("code") == -32700:
        print("✓ Invalid JSON handled correctly (error -32700)")
        return True
    else:
        print(f"✗ Invalid JSON test failed: {response}")
        return False


def test_unknown_method(proc):
    """Test that service rejects unknown methods."""
    print("Testing unknown method handling...")

    response = send_request(proc, "non_existent_method")

    if response.get("error", {}).get("code") == -32601:
        print("✓ Unknown method rejected correctly (error -32601)")
        return True
    else:
        print(f"✗ Unknown method test failed: {response}")
        return False


def test_missing_method(proc):
    """Test that service handles missing method field."""
    print("Testing missing method field...")

    request = {"jsonrpc": "2.0", "id": 1}
    proc.stdin.write((json.dumps(request) + "\n").encode())
    proc.stdin.flush()

    response_str = proc.stdout.readline().decode()
    response = json.loads(response_str)

    if response.get("error", {}).get("code") == -32600:
        print("✓ Missing method handled correctly (error -32600)")
        return True
    else:
        print(f"✗ Missing method test failed: {response}")
        return False


def test_sequential_requests(proc):
    """Test multiple sequential requests."""
    print("Testing sequential requests...")

    # Send 5 ping requests in sequence
    for i in range(5):
        response = send_request(proc, "ping", request_id=i+1)
        if response.get("result") != "pong" or response.get("id") != i+1:
            print(f"✗ Sequential request {i+1} failed: {response}")
            return False

    print("✓ Sequential requests handled correctly")
    return True


def test_initialize_twice(proc):
    """Test that initialize is idempotent."""
    print("Testing idempotent initialize...")

    config = {"max_backtrace_frames": 50}

    # First initialize
    response1 = send_request(proc, "initialize", {"config": config}, request_id=1)
    if not response1.get("result", {}).get("success"):
        print(f"✗ First initialize failed: {response1}")
        return False

    # Second initialize (should succeed, idempotent)
    response2 = send_request(proc, "initialize", {"config": config}, request_id=2)
    if not response2.get("result", {}).get("success"):
        print(f"✗ Second initialize failed: {response2}")
        return False

    print("✓ Initialize is idempotent")
    return True


def test_get_state_uninitialized(proc):
    """Test getting debugger state before initialization."""
    print("Testing get_debugger_state before initialize...")

    # This should work even before initialize
    response = send_request(proc, "get_debugger_state")

    result = response.get("result", {})
    if "attached" in result and result["attached"] == False:
        print("✓ Get state works before initialize")
        return True
    else:
        print(f"✗ Get state test failed: {response}")
        return False


def test_detach_when_not_attached(proc):
    """Test detach when no process is attached."""
    print("Testing detach when not attached...")

    response = send_request(proc, "detach")

    # Should return an error (ProcessNotAttachedError = -32001)
    if response.get("error", {}).get("code") == -32001:
        print("✓ Detach correctly fails when not attached (error -32001)")
        return True
    else:
        print(f"✗ Detach test failed: {response}")
        return False


def test_launch_invalid_executable(proc):
    """Test launching non-existent executable."""
    print("Testing launch with invalid executable...")

    # Initialize first
    send_request(proc, "initialize", {"config": {}})

    # Try to launch non-existent file
    response = send_request(proc, "launch_app", {
        "executable": "/nonexistent/path/to/app"
    })

    # Should return an error
    if "error" in response:
        print(f"✓ Launch correctly fails for invalid executable (error {response['error']['code']})")
        return True
    else:
        print(f"✗ Launch test failed: {response}")
        return False


def test_evaluate_without_process(proc):
    """Test evaluating expression without attached process."""
    print("Testing evaluate_expression without process...")

    response = send_request(proc, "evaluate_expression", {
        "expression": "1 + 1"
    })

    # Should return an error (InvalidStateError = -32002)
    if response.get("error", {}).get("code") == -32002:
        print("✓ Evaluate correctly fails without process (error -32002)")
        return True
    else:
        print(f"✗ Evaluate test failed: {response}")
        return False


def main():
    """Run comprehensive test suite."""
    print("=" * 60)
    print("LLDB Service Comprehensive Test Suite")
    print("=" * 60)
    print()

    # Start LLDB service
    print("Starting LLDB service...")
    proc = subprocess.Popen(
        ["/usr/bin/python3", "-m", "lldb_service"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd="/Users/obj-p/Projects/appledb-mcp/src",
        env={
            "PYTHONPATH": "/Users/obj-p/Projects/appledb-mcp/src:/Applications/Xcode-26.2.0.app/Contents/SharedFrameworks/LLDB.framework/Resources/Python"
        }
    )

    # Wait for ready signal
    try:
        ready_line = proc.stdout.readline().decode()
        ready_msg = json.loads(ready_line)
        if ready_msg.get("method") == "ready":
            print("✓ Ready signal received")
            print()
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
        # Error handling tests
        results.append(test_invalid_json(proc))
        results.append(test_unknown_method(proc))
        results.append(test_missing_method(proc))

        # Sequential requests
        results.append(test_sequential_requests(proc))

        # State management tests
        results.append(test_get_state_uninitialized(proc))
        results.append(test_initialize_twice(proc))

        # Error condition tests
        results.append(test_detach_when_not_attached(proc))
        results.append(test_launch_invalid_executable(proc))
        results.append(test_evaluate_without_process(proc))

    except Exception as e:
        print(f"\n✗ Test suite failed with error: {e}")
        import traceback
        traceback.print_exc()
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
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()

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
