# appledb-mcp

An LLDB debugger bridge for iOS and macOS — works as both an MCP server and a standalone CLI (ADB-style).

## Architecture

```
                     ┌──────────────────────────────┐
                     │  LLDB Server (persistent)     │
                     │  Python 3.9 + LLDB bindings   │
                     │  TCP port 5037 (default)       │
                     │  JSON-RPC over TCP             │
                     └──────────┬───────────────────┘
                                │
               ┌────────────────┼────────────────┐
               │                │                 │
         ┌─────┴─────┐  ┌──────┴──────┐  ┌──────┴──────┐
         │  CLI       │  │  CLI        │  │  MCP Server │
         │ (attach)   │  │ (bt)        │  │  (Python    │
         │ ephemeral  │  │ ephemeral   │  │   3.10+)    │
         └───────────┘  └─────────────┘  └─────────────┘
```

**LLDB Server**: Persistent daemon (like ADB server) running on a known TCP port. Maintains all debugging state — attached processes, breakpoints, threads. Uses Python 3.9 with LLDB bindings.

**CLI**: Ephemeral commands that connect to the server, send a request, print the result, and exit. Auto-starts the server if not running.

**MCP Server**: Runs with Python 3.10+ (MCP SDK requirement). Can operate standalone (spawns its own LLDB subprocess) or connect to the persistent server.

## Features

- **Process Management**: Attach to running processes or launch apps for debugging
- **Execution Control**: Continue, pause, step over/into/out
- **Expression Evaluation**: Swift, Objective-C, C++, and C expressions
- **LLDB Command Passthrough**: Run any LLDB command directly
- **Breakpoint Management**: Set, list, and delete breakpoints
- **Thread Inspection**: List threads, backtraces, variables
- **Framework Loading**: Dynamic framework injection

## Requirements

- **macOS** 12.0 or higher
- **Python** 3.10 or higher
- **Xcode Command Line Tools** (`xcode-select --install`)

## Installation

```bash
git clone https://github.com/obj-p/appledb-mcp.git
cd appledb-mcp
pip install -e .
```

## CLI Usage

```bash
# Server management
appledb start-server              # Start LLDB server daemon
appledb server-status             # Check if server is running
appledb kill-server               # Stop the server

# Process management (auto-starts server if needed)
appledb attach 1234               # Attach by PID
appledb attach -n Safari          # Attach by name
appledb launch /path/to/app       # Launch app for debugging
appledb detach                    # Detach from process
appledb detach --kill             # Kill process

# Debugging
appledb status                    # Show debugger state
appledb continue                  # Continue execution
appledb pause                     # Pause execution
appledb step over                 # Step over/into/out

# Inspection
appledb eval "myVariable"         # Evaluate expression
appledb eval "self" --lang swift  # With language hint
appledb bt                        # Show backtrace
appledb vars                      # Show variables
appledb threads                   # List threads

# Breakpoints
appledb bp set main.c:42          # Set by file:line
appledb bp set viewDidLoad        # Set by symbol
appledb bp set malloc -c '$arg1 > 1024'  # With condition
appledb bp list                   # List breakpoints
appledb bp delete 1               # Delete breakpoint

# Raw LLDB commands
appledb cmd register read         # Any LLDB command
appledb cmd memory read 0x100

# MCP mode
appledb mcp                       # Run as MCP server (stdio)
```

### Port Discovery

The CLI finds the server port in this order:
1. `--port` flag
2. `APPLEDB_PORT` environment variable
3. `~/.appledb/server.port` file (written by `start-server`)
4. Default: `5037`

## MCP Usage

### With Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

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

### Available MCP Tools

| Category | Tools |
|----------|-------|
| **Process** | `health_check`, `lldb_attach_process`, `lldb_launch_app`, `lldb_detach` |
| **Execution** | `lldb_continue`, `lldb_pause`, `lldb_step_over`, `lldb_step_into`, `lldb_step_out` |
| **Inspection** | `lldb_evaluate`, `lldb_get_backtrace`, `lldb_get_variables`, `lldb_list_threads` |
| **Breakpoints** | `lldb_set_breakpoint`, `lldb_list_breakpoints`, `lldb_delete_breakpoint` |
| **Command** | `lldb_command` (raw LLDB passthrough) |
| **Framework** | `lldb_load_framework` |

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `APPLEDB_LOG_LEVEL` | Logging level (DEBUG, INFO, WARNING, ERROR) | `INFO` |
| `APPLEDB_LLDB_TIMEOUT` | Timeout for LLDB operations (seconds) | `30` |
| `APPLEDB_LLDB_PYTHON` | Python 3.9+ interpreter with LLDB bindings | `python3` |
| `APPLEDB_PORT` | TCP port for server | `5037` |
| `APPLEDB_SERVICE_MAX_RESTARTS` | Max automatic subprocess restarts | `3` |
| `APPLEDB_SERVICE_RESTART_BACKOFF` | Base restart backoff (seconds) | `1.0` |
| `APPLEDB_SERVICE_REQUEST_TIMEOUT` | RPC request timeout (seconds) | `30.0` |
| `APPLEDB_SERVICE_RESTART_RESET_TIME` | Stable uptime before restart counter reset | `300.0` |
| `APPLEDB_MAX_BACKTRACE_FRAMES` | Max frames in backtrace | `100` |
| `APPLEDB_MAX_VARIABLE_DEPTH` | Max depth for variable inspection | `3` |

## Development

```bash
pip install -e ".[dev]"

# Unit tests (no LLDB required)
pytest tests/ -v --ignore=tests/lldb_service

# Integration tests (require LLDB + running server)
pytest tests/ -v -m integration

# Formatting and linting
black src/ tests/
ruff check src/ tests/
mypy src/appledb_mcp
```

## Troubleshooting

### "ModuleNotFoundError: No module named 'lldb'"

Install Xcode Command Line Tools and set PYTHONPATH:
```bash
xcode-select --install
export PYTHONPATH=$(lldb -P):$PYTHONPATH
```

### Permission Denied When Attaching

macOS requires debugging permissions. Options:
1. Sign binary for debugging (recommended)
2. Use Xcode to grant permissions
3. `sudo appledb attach <pid>` (not recommended)

### Server Won't Start

Check logs: `appledb start-server --log-level DEBUG`
Verify LLDB: `python3 -c "import lldb; print('OK')"`

## License

MIT

## Author

Jason Prasad
