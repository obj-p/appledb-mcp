# appledb-mcp

An MCP (Model Context Protocol) server that exposes LLDB debugging capabilities for iOS and macOS applications.

## Features

- **Process Management**: Attach to running processes or launch apps for debugging
- **Execution Control**: Continue, step over, step into, step out
- **Expression Evaluation**: Execute Swift, Objective-C, and C++ expressions in the debugger
- **iOS-Specific Tools**: Dynamic framework injection (integrates with [xcdb](https://github.com/obj-p/xcdb))
- **State Inspection**: Variables, backtraces, process state

## Requirements

- **macOS** 12.0 or higher (LLDB required)
- **Python** 3.10 or higher
- **Xcode Command Line Tools** (for LLDB)

Check LLDB availability:
```bash
python3 -c "import lldb; print('LLDB available')"
```

If LLDB is not found, install Xcode Command Line Tools:
```bash
xcode-select --install
```

## Installation

### From Source

```bash
git clone https://github.com/obj-p/appledb-mcp.git
cd appledb-mcp
pip install -e .
```

### Development Installation

```bash
pip install -e ".[dev]"
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
        "APPLEDB_AUTO_LOAD_XCDB": "true",
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
| `APPLEDB_XCDB_FRAMEWORK` | Path to xcdb framework binary | Auto-detected |
| `APPLEDB_AUTO_LOAD_XCDB` | Auto-load xcdb on process attach | `true` |
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

### Inspection (Coming soon)
- `lldb_evaluate` - Evaluate an expression
- `lldb_get_backtrace` - Get stack trace
- `lldb_get_variables` - Get local variables

### Framework Loading (Coming soon)
- `lldb_load_framework` - Load xcdb or custom framework

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

**Current Version**: 0.1.0 (Phase 3: Execution Control)

- ✅ Core MCP server infrastructure
- ✅ LLDB debugger singleton management
- ✅ Configuration system
- ✅ Logging and error handling
- ✅ Process management tools (Phase 2)
- ✅ Execution control tools (Phase 3)
- 🚧 Inspection tools (Phase 4)
- 🚧 Framework loading (Phase 5)
- 🚧 Resources (Phase 6)

## License

MIT

## Author

Jason Prasad

## Related Projects

- [xcdb](https://github.com/obj-p/xcdb) - LLDB extensions for iOS debugging
