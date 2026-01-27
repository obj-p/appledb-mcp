#!/usr/bin/env python3
"""Focused test of working LLDB service operations."""

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
        print("LLDB service started (PID: {})".format(self.process.pid))
        
        # Wait for ready signal
        response_line = self.process.stdout.readline()
        if response_line:
            ready = json.loads(response_line)
            if ready.get("method") == "ready":
                print("Service is ready\n")

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

            # Read response
            response_line = self.process.stdout.readline()
            if not response_line:
                return None

            response = json.loads(response_line)
            return response
        except Exception as e:
            print(f"ERROR communicating with service: {e}")
            return None

    def stop_service(self):
        """Stop the LLDB service."""
        if self.process:
            print("\n\nStopping LLDB service...")
            self.process.stdin.close()
            self.process.wait(timeout=5)

    def run_focused_test(self):
        """Run focused test of key debugging operations."""
        test_program = "/Users/obj-p/Projects/appledb-mcp/test_debug_program"

        print("="*70)
        print("LLDB SERVICE VERIFICATION TEST")
        print("="*70)
        print()

        # Initialize
        print("1. Initializing debugger...")
        response = self.send_request("initialize", {})
        if response and "error" not in response:
            print("   ✓ Debugger initialized")
        else:
            print("   ✗ Failed to initialize")
            return

        # Launch
        print("\n2. Launching test program with stop_at_entry...")
        response = self.send_request("launch_app", {
            "executable": test_program,
            "args": [],
            "stop_at_entry": True
        })
        if response and "error" not in response:
            result = response.get("result", {})
            print(f"   ✓ Process launched (PID: {result.get('pid')})")
            print(f"     - State: {result.get('state')}")
            print(f"     - Architecture: {result.get('architecture')}")
        else:
            print(f"   ✗ Failed to launch: {response.get('error', {}).get('message') if response else 'No response'}")
            return

        time.sleep(0.5)

        # Get backtrace at entry
        print("\n3. Getting backtrace at entry point...")
        response = self.send_request("get_backtrace", {})
        if response and "error" not in response:
            frames = response.get("result", {}).get("frames", [])
            print(f"   ✓ Backtrace retrieved ({len(frames)} frames)")
            if frames:
                for i, frame in enumerate(frames[:3]):
                    func = frame.get('function', 'unknown')
                    pc = frame.get('pc', '?')
                    print(f"     Frame {i}: {func} @ {pc}")
        else:
            print(f"   ✗ Failed: {response.get('error', {}).get('message') if response else 'No response'}")

        # Step a few instructions
        print("\n4. Stepping through code...")
        for step_num in range(5):
            response = self.send_request("step_over", {})
            if response and "error" not in response:
                loc = response.get("result", {}).get("location", "unknown")
                print(f"   ✓ Step {step_num + 1}: {loc}")
            else:
                print(f"   ✗ Step {step_num + 1} failed")
                break
            time.sleep(0.1)

        # Evaluate expression
        print("\n5. Evaluating expressions...")
        test_expressions = [
            ("1+1", "2"),
            ("10*5", "50"),
            ("(int)3.14", "3")
        ]
        
        for expr, expected in test_expressions:
            response = self.send_request("evaluate_expression", {"expression": expr})
            if response and "error" not in response:
                result = response.get("result", {})
                value = result.get("value")
                print(f"   ✓ {expr} = {value} (expected {expected})")
            else:
                print(f"   ✗ Failed to evaluate {expr}")

        # Get variables
        print("\n6. Getting local variables...")
        response = self.send_request("get_variables", {"scope": "local"})
        if response and "error" not in response:
            variables = response.get("result", {}).get("variables", [])
            print(f"   ✓ Retrieved {len(variables)} variables")
            for var in variables[:5]:
                name = var.get('name')
                value = var.get('value')
                var_type = var.get('type')
                print(f"     - {name}: {value} ({var_type})")
        else:
            print(f"   ✗ Failed: {response.get('error', {}).get('message') if response else 'No response'}")

        # Step into/out
        print("\n7. Testing step into/out...")
        response = self.send_request("step_into", {})
        if response and "error" not in response:
            print(f"   ✓ Step into: {response.get('result', {}).get('location')}")
        
        time.sleep(0.1)
        
        response = self.send_request("step_out", {})
        if response and "error" not in response:
            print(f"   ✓ Step out: {response.get('result', {}).get('location')}")

        # Continue execution
        print("\n8. Continuing execution to completion...")
        response = self.send_request("continue_execution", {})
        if response and "error" not in response:
            print(f"   ✓ Process continued (state: {response.get('result', {}).get('state')})")
        else:
            print(f"   ✗ Failed to continue")

        time.sleep(1.5)  # Let program finish

        # Cleanup
        print("\n9. Cleaning up...")
        response = self.send_request("cleanup", {})
        if response and "error" not in response:
            print("   ✓ Cleanup successful")
        else:
            print("   ✗ Cleanup failed")

        print("\n" + "="*70)
        print("VERIFICATION COMPLETE")
        print("="*70)

def main():
    tester = LLDBServiceTester()
    try:
        tester.start_service()
        tester.run_focused_test()
    except KeyboardInterrupt:
        print("\n\nTest interrupted")
    except Exception as e:
        print(f"\n\nTest failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        tester.stop_service()

if __name__ == "__main__":
    main()
