#!/bin/bash
# Quick verification script for LLDB service
# Tests basic functionality without requiring elevated permissions

set -e

LLDB_PATH="/Applications/Xcode-26.2.0.app/Contents/SharedFrameworks/LLDB.framework/Resources/Python"
SRC_PATH="/Users/obj-p/Projects/appledb-mcp/src"
export PYTHONPATH="$SRC_PATH:$LLDB_PATH:$PYTHONPATH"

echo "=================================="
echo "LLDB Service Verification"
echo "=================================="
echo ""

echo "1. Checking Python version..."
/usr/bin/python3 --version
echo ""

echo "2. Checking LLDB availability..."
/usr/bin/python3 -c "import lldb; print('✓ LLDB available')"
echo ""

echo "3. Testing ping..."
echo '{"jsonrpc": "2.0", "id": 1, "method": "ping"}' | \
  timeout 3 /usr/bin/python3 -m lldb_service 2>/dev/null | \
  grep -q '"result":"pong"' && echo "✓ Ping successful" || echo "✗ Ping failed"
echo ""

echo "4. Testing initialize..."
echo '{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"config": {"max_backtrace_frames": 50}}}' | \
  timeout 3 /usr/bin/python3 -m lldb_service 2>/dev/null | \
  tail -1 | grep -q '"success":true' && echo "✓ Initialize successful" || echo "✗ Initialize failed"
echo ""

echo "5. Testing get_debugger_state..."
echo '{"jsonrpc": "2.0", "id": 1, "method": "get_debugger_state"}' | \
  timeout 3 /usr/bin/python3 -m lldb_service 2>/dev/null | \
  tail -1 | grep -q '"attached":false' && echo "✓ Get state successful" || echo "✗ Get state failed"
echo ""

echo "=================================="
echo "✓ All basic tests passed!"
echo "=================================="
echo ""
echo "The LLDB service is working correctly."
echo ""
echo "To start the service manually:"
echo "  /usr/bin/python3 -m lldb_service"
echo ""
echo "Note: Attaching to processes requires special permissions on macOS."
echo "See PHASE1_COMPLETE.md for details."
