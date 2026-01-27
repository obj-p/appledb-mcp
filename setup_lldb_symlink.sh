#!/bin/bash
# Setup script to create LLDB Python 3.12 symlink
# This allows Python 3.12 to use LLDB Python bindings

set -e

echo "=== LLDB Python 3.12 Setup ==="
echo
echo "This script will create a symlink to allow Python 3.12 to use LLDB."
echo "It requires admin (sudo) access."
echo

# Find Xcode path
XCODE_PATH=$(xcode-select -p 2>/dev/null || echo "/Applications/Xcode.app/Contents/Developer")
LLDB_PATH="$XCODE_PATH/../SharedFrameworks/LLDB.framework/Resources/Python/lldb"

echo "Xcode path: $XCODE_PATH"
echo "LLDB Python path: $LLDB_PATH"
echo

# Check if source file exists
if [ ! -f "$LLDB_PATH/_lldb.cpython-39-darwin.so" ]; then
    echo "ERROR: LLDB Python 3.9 bindings not found!"
    echo "Expected at: $LLDB_PATH/_lldb.cpython-39-darwin.so"
    exit 1
fi

# Check if symlink already exists
if [ -L "$LLDB_PATH/_lldb.cpython-312-darwin.so" ]; then
    echo "✓ Symlink already exists!"
    ls -la "$LLDB_PATH/_lldb.cpython-3"*
    exit 0
fi

# Create symlink
echo "Creating symlink..."
sudo ln -s _lldb.cpython-39-darwin.so "$LLDB_PATH/_lldb.cpython-312-darwin.so"

# Verify
if [ -L "$LLDB_PATH/_lldb.cpython-312-darwin.so" ]; then
    echo
    echo "✓ Symlink created successfully!"
    echo
    ls -la "$LLDB_PATH/_lldb.cpython-3"*
    echo
    echo "You can now use LLDB with Python 3.12:"
    echo "  PYTHONPATH=\$(lldb -P):\$PYTHONPATH python3.12 -c 'import lldb; print(lldb.SBDebugger.GetVersionString())'"
else
    echo "ERROR: Failed to create symlink"
    exit 1
fi
