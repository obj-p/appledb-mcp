# Examples - Claude Desktop Configuration

## Claude Desktop Configuration

The `claude_desktop_config.json` file shows how to configure Claude Desktop to use the appledb-mcp server.

### Setup Instructions

1. **Find your Claude Desktop config location**:
   ```bash
   # macOS
   ~/Library/Application Support/Claude/claude_desktop_config.json
   ```

2. **Update the configuration**:
   - Replace `/path/to/your/venv/bin/python3` with your actual virtualenv Python path
   - Adjust environment variables as needed

3. **Configuration Options**:

   | Variable | Default | Description |
   |----------|---------|-------------|
   | `APPLEDB_LOG_LEVEL` | `INFO` | Log level (DEBUG, INFO, WARNING, ERROR) |
   | `APPLEDB_LLDB_TIMEOUT` | `30` | Timeout for LLDB operations (seconds) |
   | `APPLEDB_PYTHON_PATH` | `python3` | Path to Python 3.9+ for LLDB service |
   | `APPLEDB_SERVICE_MAX_RESTARTS` | `3` | Max automatic restarts on crash |
   | `APPLEDB_SERVICE_RESTART_BACKOFF` | `1.0` | Base backoff time for restarts (seconds) |
   | `APPLEDB_SERVICE_REQUEST_TIMEOUT` | `30.0` | RPC request timeout (seconds) |
   | `APPLEDB_SERVICE_RESTART_RESET_TIME` | `300.0` | Reset restart counter after stable time (seconds) |
   | `APPLEDB_MAX_BACKTRACE_FRAMES` | `100` | Max frames in backtrace |
   | `APPLEDB_MAX_VARIABLE_DEPTH` | `3` | Max depth for variable inspection |

### Example Configuration

**Minimal** (uses defaults):
```json
{
  "mcpServers": {
    "appledb": {
      "command": "/Users/yourname/Projects/appledb-mcp/venv/bin/python3",
      "args": ["-m", "appledb_mcp"]
    }
  }
}
```

**With Custom Settings**:
```json
{
  "mcpServers": {
    "appledb": {
      "command": "/Users/yourname/Projects/appledb-mcp/venv/bin/python3",
      "args": ["-m", "appledb_mcp"],
      "env": {
        "APPLEDB_LOG_LEVEL": "DEBUG",
        "APPLEDB_LLDB_TIMEOUT": "60",
        "APPLEDB_PYTHON_PATH": "/usr/bin/python3",
        "APPLEDB_MAX_BACKTRACE_FRAMES": "50",
        "APPLEDB_MAX_VARIABLE_DEPTH": "5"
      }
    }
  }
}
```

### Troubleshooting

**LLDB not found**:
- Ensure Xcode Command Line Tools are installed: `xcode-select --install`
- Verify LLDB works: `lldb --version`
- Set correct Python path: `APPLEDB_PYTHON_PATH=/usr/bin/python3`

**Service crashes**:
- Check logs in Claude Desktop: View → Developer → Show Logs
- Increase timeout: `APPLEDB_LLDB_TIMEOUT=60`
- Enable debug logging: `APPLEDB_LOG_LEVEL=DEBUG`

**Permission errors**:
- macOS may prompt for debugger permissions
- Allow in System Settings → Privacy & Security → Developer Tools

### Testing the Configuration

After updating your Claude Desktop config:

1. Restart Claude Desktop
2. Open a new conversation
3. Try a debugging command:
   ```
   List all running processes
   ```

If configured correctly, the MCP server will respond with process information.

### Two-Server Architecture

The configuration starts the **MCP Server** (Python 3.10+), which automatically manages the **LLDB Service** subprocess (Python 3.9). You don't need to configure the LLDB service separately.

**Architecture**:
```
Claude Desktop → MCP Server (Python 3.10+)
                     ↓
                 LLDBClient
                     ↓
              LLDB Service (Python 3.9)
                     ↓
                  LLDB API
```

The `APPLEDB_PYTHON_PATH` specifies which Python to use for the LLDB service subprocess. Default is `python3`, but `/usr/bin/python3` is recommended for macOS system Python with LLDB bindings.
