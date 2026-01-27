#!/bin/bash
# Wrapper script to run appledb-mcp with LLDB support

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Set PYTHONPATH to include LLDB Python bindings
export PYTHONPATH=$(lldb -P):$PYTHONPATH

# Activate venv and run
source "$SCRIPT_DIR/venv-mcp/bin/activate"
exec python -m appledb_mcp "$@"
