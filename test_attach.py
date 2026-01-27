#!/usr/bin/env python3
"""Test LLDB service by attaching to a running process."""

import subprocess
import json
import time
import os
import signal

class LLDBAttachTester:
    def __init__(self):
        self.service_process = None
        self.target_process = None
        self.request_id = 0

    def start_target_process(self):
        """Start a simple target process that we can attach to."""
        print("Starting target process (sleep 30)...")
        self.target_process = subprocess.Popen(
            ['sleep', '30'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        print(f"Target process PID: {self.target_process.pid}\n")
        time.sleep(0.5)  # Let it start
        return self.target_process.pid

    def start_service(self):
        """Start the LLDB service subprocess."""
        print("Starting LLDB service...")
        env = os.environ.copy()
        env['PYTHONPATH'] = '/Users/obj-p/Projects/appledb-mcp/src:/Applications/Xcode-26.2.0.app/Contents/SharedFrameworks/LLDB.framework/Resources/Python'

        self.service_process = subprocess.Popen(
            ['/usr/bin/python3', '-m', 'lldb_service'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            text=True,
            bufsize=1
        )
        
        # Wait for ready signal
        response_line = self.service_process.stdout.readline()
        if response_line:
            ready = json.loads(response_line)
            if ready.get("method") == "ready":
                print("LLDB service ready\n")

    def send_request(self, method, params=None):
        """Send a JSON-RPC request and get the response."""
        self.request_id += 1
        request = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
            "id": self.request_id
        }

        request_json = json.dumps(request) + '\n'

        try:
            self.service_process.stdin.write(request_json)
            self.service_process.stdin.flush()
            response_line = self.service_process.stdout.readline()
            if response_line:
                return json.loads(response_line)
        except Exception as e:
            print(f"ERROR: {e}")
        return None

    def stop_service(self):
        """Stop the LLDB service."""
        if self.service_process:
            print("\nStopping LLDB service...")
            self.service_process.stdin.close()
            self.service_process.wait(timeout=5)

    def stop_target(self):
        """Stop the target process."""
        if self.target_process:
            print("Stopping target process...")
            self.target_process.terminate()
            self.target_process.wait(timeout=2)

    def test_attach(self):
        """Test attaching to a running process."""
        target_pid = self.start_target_process()

        print("="*70)
        print("TESTING LLDB ATTACH TO RUNNING PROCESS")
        print("="*70)
        print()

        # Initialize
        print("1. Initializing debugger...")
        response = self.send_request("initialize", {})
        if response and "error" not in response:
            print("   ✓ Initialized")
        else:
            print(f"   ✗ Failed: {response}")
            return

        # Attach to process
        print(f"\n2. Attaching to process {target_pid}...")
        response = self.send_request("attach_process", {"pid": target_pid})
        if response and "error" not in response:
            result = response.get("result", {})
            print(f"   ✓ Attached successfully")
            print(f"     - PID: {result.get('pid')}")
            print(f"     - Name: {result.get('name')}")
            print(f"     - State: {result.get('state')}")
        else:
            error = response.get("error", {}) if response else {}
            print(f"   ✗ Failed: {error.get('message', 'Unknown error')}")
            # On macOS, this might fail due to code signing/SIP
            print("   Note: This may fail due to macOS security (SIP, code signing)")
            return

        # Get backtrace
        print("\n3. Getting backtrace of attached process...")
        response = self.send_request("get_backtrace", {})
        if response and "error" not in response:
            frames = response.get("result", {}).get("frames", [])
            print(f"   ✓ Backtrace retrieved ({len(frames)} frames)")
            for i, frame in enumerate(frames[:5]):
                print(f"     Frame {i}: {frame.get('function')} @ {frame.get('pc')}")
        else:
            print(f"   ✗ Failed to get backtrace")

        # Detach
        print("\n4. Detaching from process...")
        response = self.send_request("detach", {"kill": False})
        if response and "error" not in response:
            print("   ✓ Detached successfully")
        else:
            error = response.get("error", {}) if response else {}
            print(f"   Note: Detach returned: {error.get('message', 'Unknown')}")

        # Cleanup
        print("\n5. Cleaning up...")
        self.send_request("cleanup", {})
        print("   ✓ Done")

        print("\n" + "="*70)

def main():
    tester = LLDBAttachTester()
    try:
        tester.start_service()
        tester.test_attach()
    except Exception as e:
        print(f"\nTest failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        tester.stop_service()
        tester.stop_target()

if __name__ == "__main__":
    main()
