#!/usr/bin/env python3
"""Test LLDB service with breakpoints to inspect actual program variables."""

import subprocess
import json
import time
import os

class LLDBServiceTester:
    def __init__(self):
        self.process = None
        self.request_id = 0

    def start_service(self):
        """Start the LLDB service subprocess."""
        print("Starting LLDB service...")
        env = os.environ.copy()
        env['PYTHONPATH'] = '/Users/obj-p/Projects/appledb-mcp/src:/Applications/Xcode-26.2.0.app/Contents/SharedFrameworks/LLDB.framework/Resources/Python'

        self.process = subprocess.Popen(
            ['/usr/bin/python3', '-m', 'lldb_service'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            text=True,
            bufsize=1
        )
        
        # Wait for ready signal
        response_line = self.process.stdout.readline()
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
            self.process.stdin.write(request_json)
            self.process.stdin.flush()
            response_line = self.process.stdout.readline()
            if response_line:
                return json.loads(response_line)
        except Exception as e:
            print(f"ERROR: {e}")
        return None

    def stop_service(self):
        """Stop the LLDB service."""
        if self.process:
            print("\nStopping service...")
            self.process.stdin.close()
            self.process.wait(timeout=5)

    def test_with_expressions(self):
        """Test debugging with expression evaluation."""
        test_program = "/Users/obj-p/Projects/appledb-mcp/test_debug_program"

        print("="*70)
        print("TESTING LLDB SERVICE WITH PROGRAM VARIABLES")
        print("="*70)
        print()

        # Initialize and launch without stop_at_entry
        print("1. Initializing and launching program...")
        self.send_request("initialize", {})
        response = self.send_request("launch_app", {
            "executable": test_program,
            "args": [],
            "stop_at_entry": False  # Don't stop at entry
        })
        
        if response and "error" not in response:
            print(f"   ✓ Launched (PID: {response.get('result', {}).get('pid')})")
        else:
            print(f"   ✗ Failed: {response.get('error') if response else 'No response'}")
            return

        time.sleep(0.3)

        # Try to pause the running process
        print("\n2. Pausing the running process...")
        response = self.send_request("pause", {})
        if response and "error" not in response:
            print("   ✓ Process paused")
        else:
            # Process might have already finished, try to continue anyway
            print(f"   Note: Pause returned: {response.get('error', {}).get('message') if response else 'Unknown'}")

        time.sleep(0.2)

        # Check where we are
        print("\n3. Getting current location...")
        response = self.send_request("get_backtrace", {})
        if response and "error" not in response:
            frames = response.get("result", {}).get("frames", [])
            if frames:
                print(f"   Current function: {frames[0].get('function')}")
                print(f"   Location: {frames[0].get('file')}:{frames[0].get('line')}")

        # Try to evaluate variables if we're in main
        print("\n4. Trying to evaluate program variables...")
        test_vars = ["num1", "num2", "argc", "argv"]
        for var in test_vars:
            response = self.send_request("evaluate_expression", {"expression": var})
            if response and "error" not in response:
                result = response.get("result", {})
                if result.get("error"):
                    print(f"   - {var}: not in scope")
                else:
                    print(f"   ✓ {var} = {result.get('value')} ({result.get('type')})")
            else:
                print(f"   - {var}: evaluation failed")

        # Cleanup
        print("\n5. Cleaning up...")
        self.send_request("cleanup", {})
        print("   ✓ Done")

        print("\n" + "="*70)

def main():
    tester = LLDBServiceTester()
    try:
        tester.start_service()
        tester.test_with_expressions()
    except Exception as e:
        print(f"\nTest failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        tester.stop_service()

if __name__ == "__main__":
    main()
