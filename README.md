# appledb-mcp

An MCP (Model Context Protocol) server that exposes LLDB debugging capabilities for iOS and macOS applications.

## Features

- **Process Management**: Attach to running processes or launch apps for debugging
- **Execution Control**: Continue, step over, step into, step out
- **Expression Evaluation**: Execute Swift, Objective-C, and C++ expressions in the debugger
- **Framework Loading**: Dynamic framework injection for runtime modifications
- **State Inspection**: Variables, backtraces, process state

## Requirements

- **macOS** 12.0 or higher
- **Python** 3.10 or higher
- **Xcode Command Line Tools** (provides LLDB and Python bindings)

### LLDB Availability

This project requires LLDB Python bindings, which come with Xcode Command Line Tools.

**Step 1:** Install Xcode Command Line Tools (if not already installed):
```bash
xcode-select --install
```

**Step 2:** Verify LLDB is available:
```bash
lldb --version
```

You should see output like: `lldb-1703.0.236.21` or similar.

**Step 3:** Test LLDB Python bindings:
```bash
python3 -c "import lldb; print('LLDB available')"
```

If this succeeds, you're ready to install appledb-mcp.

### Troubleshooting LLDB

If `import lldb` fails, ensure you're using system Python or set PYTHONPATH:

```bash
export PYTHONPATH=$(lldb -P):$PYTHONPATH
python3 -c "import lldb; print('LLDB available')"
```

**Note**: LLDB Python bindings may not work in virtual environments. Use system Python 3.10+ or install the package globally.

## Installation

### From Source

```bash
git clone https://github.com/obj-p/appledb-mcp.git
cd appledb-mcp
pip install -e .
```

**Verify Installation:**
```bash
python3 -c "from appledb_mcp.server import mcp; print('✓ appledb-mcp installed successfully')"
```

### Development Installation

```bash
pip install -e ".[dev]"
```

**Run Tests:**
```bash
pytest tests/
```

## Usage

### With Claude Desktop

Add to your Claude Desktop configuration file:

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "appledb": {
      "command": "python3",
      "args": ["-m", "appledb_mcp"],
      "env": {
        "APPLEDB_LOG_LEVEL": "INFO"
      }
    }
  }
}
```

Restart Claude Desktop after updating the configuration.

### Standalone

```bash
python3 -m appledb_mcp
```

## Configuration

Configuration is done via environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `APPLEDB_LOG_LEVEL` | Logging level (DEBUG, INFO, WARNING, ERROR) | `INFO` |
| `APPLEDB_LLDB_TIMEOUT` | Timeout for LLDB operations (seconds) | `30` |

## Available MCP Tools

### Process Management
- `health_check` - Check server health and LLDB status
- `lldb_attach_process` - Attach to a running process by PID or name
- `lldb_launch_app` - Launch an app with debugging
- `lldb_detach` - Detach from the current process

### Execution Control
- `lldb_continue` - Continue execution
- `lldb_pause` - Pause execution
- `lldb_step_over` - Step over
- `lldb_step_into` - Step into
- `lldb_step_out` - Step out

### Inspection
- `lldb_evaluate` - Evaluate expressions (supports Swift, Objective-C, C++, C)
- `lldb_get_backtrace` - Get stack trace for thread
- `lldb_get_variables` - Get local variables and arguments in frame

### Framework Loading
- `lldb_load_framework` - Load custom frameworks dynamically

## Development

### Running Tests

```bash
# Unit tests (fast, no LLDB required)
pytest tests/

# Integration tests (require LLDB)
pytest tests/ -m integration
```

### Code Formatting

```bash
black src/ tests/
ruff check src/ tests/
```

### Type Checking

```bash
mypy src/appledb_mcp
```

## Project Status

**Current Version**: 0.1.0 (Phase 4: Inspection Tools)

- ✅ Core MCP server infrastructure
- ✅ LLDB debugger singleton management
- ✅ Configuration system
- ✅ Logging and error handling
- ✅ Process management tools (Phase 2)
- ✅ Execution control tools (Phase 3)
- ✅ Inspection tools (Phase 4)
- 🚧 Framework loading (Phase 5)
- 🚧 Resources (Phase 6)

## Troubleshooting

### "ModuleNotFoundError: No module named 'lldb'"

**Cause**: LLDB Python bindings not available in current Python environment.

**Solutions**:
1. Install Xcode Command Line Tools: `xcode-select --install`
2. Use system Python instead of virtual environment
3. Set PYTHONPATH: `export PYTHONPATH=$(lldb -P):$PYTHONPATH`

### "RuntimeError: LLDB not found"

**Cause**: LLDB module cannot be imported at runtime.

**Solution**: The error message will include the exact PYTHONPATH to add:
```bash
export PYTHONPATH=/Applications/Xcode.app/Contents/SharedFrameworks/LLDB.framework/Resources/Python:$PYTHONPATH
```

### Tests Failing in Virtual Environment

**Cause**: LLDB Python bindings don't work in venv.

**Solution**: Run tests with system Python and PYTHONPATH:
```bash
PYTHONPATH=$(lldb -P) python3 -m pytest tests/
```

### Claude Desktop Connection Issues

**Symptoms**: Tools not appearing or server not starting.

**Solutions**:
1. Check logs: `~/Library/Logs/Claude/mcp*.log`
2. Verify config: `~/Library/Application Support/Claude/claude_desktop_config.json`
3. Restart Claude Desktop completely
4. Test server manually: `python3 -m appledb_mcp`

### Permission Denied When Attaching

**Cause**: macOS requires debugging permissions.

**Solutions**:
1. Run with sudo (not recommended): `sudo python3 -m appledb_mcp`
2. Sign binary for debugging (recommended for development)
3. Use Xcode to grant permissions
4. Disable SIP (not recommended): Only for development machines

## Compatibility

- **Tested on**: macOS 14+ (Sonoma), Xcode 15+
- **LLDB Versions**: lldb-1703+ (uses standard LLDB API)
- **Python Versions**: 3.10, 3.11, 3.12, 3.14
- **Platforms**: macOS (primary), iOS Simulator (tested), Physical iOS devices (should work)

## License

MIT

## Author

Jason Prasad
