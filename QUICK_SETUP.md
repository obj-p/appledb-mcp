# Quick Setup for appledb-mcp Development

Follow these steps to get appledb-mcp working with Claude Desktop on your machine.

## Step 1: Create LLDB Symlink

Run the setup script (requires sudo password):

```bash
cd /Users/obj-p/Projects/appledb-mcp
./setup_lldb_symlink.sh
```

This creates a symlink that allows Python 3.12 to use LLDB Python bindings.

## Step 2: Verify LLDB Works

```bash
source venv-mcp/bin/activate
PYTHONPATH=$(lldb -P):$PYTHONPATH python -c "import lldb; print('✓ LLDB works:', lldb.SBDebugger.GetVersionString())"
```

Expected output:
```
✓ LLDB works: lldb-1703.0.236.21
```

## Step 3: Test Server Startup

```bash
./run_appledb_mcp.sh
```

You should see:
```
2026-01-25 XX:XX:XX,XXX - __main__ - INFO - Starting appledb-mcp server
2026-01-25 XX:XX:XX,XXX - appledb_mcp.server - INFO - Loaded configuration: log_level=INFO
2026-01-25 XX:XX:XX,XXX - appledb_mcp.server - INFO - Initializing LLDB debugger
```

Press Ctrl+C to stop.

## Step 4: Configure Claude Desktop

Create or edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "appledb": {
      "command": "/Users/obj-p/Projects/appledb-mcp/run_appledb_mcp.sh",
      "env": {
        "APPLEDB_LOG_LEVEL": "INFO"
      }
    }
  }
}
```

## Step 5: Restart Claude Desktop

1. Quit Claude Desktop completely
2. Reopen Claude Desktop
3. The appledb MCP server should connect automatically

## Step 6: Test in Claude

Ask Claude to check the debugger:

```
User: Check debugger health

Claude: I'll check the debugger health.
[Calls health_check tool]

Result: ✓ MCP server running, LLDB debugger initialized (version: lldb-1703.0.236.21)
```

## Troubleshooting

### If Step 2 Fails (LLDB Import Error)

The symlink might not have been created. Try:

```bash
# Manual symlink creation
cd /Applications/Xcode.app/Contents/SharedFrameworks/LLDB.framework/Resources/Python/lldb
sudo ln -s _lldb.cpython-39-darwin.so _lldb.cpython-312-darwin.so
```

### If Server Won't Start

Check logs:
```bash
tail -f ~/Library/Logs/Claude/mcp*.log
```

Common issues:
1. **LLDB not found**: Run setup_lldb_symlink.sh
2. **Module errors**: Run `source venv-mcp/bin/activate && pip install -e .`
3. **Permission errors**: Check that run_appledb_mcp.sh is executable (`chmod +x`)

### If Claude Desktop Won't Connect

1. Check configuration file syntax (valid JSON)
2. Check absolute path to run_appledb_mcp.sh
3. Restart Claude Desktop completely (quit from menu bar)
4. Check ~/Library/Logs/Claude/ for error logs

## Quick Reference Commands

```bash
# Activate development environment
cd /Users/obj-p/Projects/appledb-mcp
source venv-mcp/bin/activate

# Test LLDB import
PYTHONPATH=$(lldb -P):$PYTHONPATH python -c "import lldb; print('OK')"

# Run server manually
./run_appledb_mcp.sh

# Run tests
pytest tests/ -v -m "not integration"

# Check code quality
black --check src/ tests/
ruff check src/ tests/
mypy src/appledb_mcp

# View Claude logs
tail -f ~/Library/Logs/Claude/mcp*.log
```

## Next Steps

Once setup is working:
- Read [examples/basic_usage.md](examples/basic_usage.md) for debugging workflows
- Review [docs/API.md](docs/API.md) for complete tool reference
- Try debugging a simple app to test the tools

## Getting Help

If you encounter issues:
1. Check [DEVELOPMENT_SETUP.md](DEVELOPMENT_SETUP.md) for detailed troubleshooting
2. Review error messages in Claude logs
3. Create a GitHub issue with error details
