# Development Setup for appledb-mcp on macOS

## LLDB Python Compatibility Issue

**TL;DR**: macOS LLDB Python bindings are built specifically for the system Python version (3.9.6), but the MCP SDK requires Python 3.10+. This creates a compatibility conflict.

### The Problem

1. **LLDB Requirement**: appledb-mcp needs LLDB Python bindings
2. **LLDB Limitation**: macOS LLDB is built against system Python 3.9.6 only
3. **MCP Requirement**: The MCP SDK requires Python 3.10+

The LLDB binary is located at:
```
/Applications/Xcode.app/Contents/SharedFrameworks/LLDB.framework/Resources/Python/lldb/_lldb.cpython-39-darwin.so
```

Note the `cpython-39` - this means it only works with Python 3.9.

### Solution Options

#### Option 1: Create Python 3.12 Symlink (Recommended for Development)

Create a symlink to make LLDB work with Python 3.12:

```bash
cd /Applications/Xcode.app/Contents/SharedFrameworks/LLDB.framework/Resources/Python/lldb/
sudo ln -s _lldb.cpython-39-darwin.so _lldb.cpython-312-darwin.so
```

**Note**: This requires admin password and modifies system files. It may break with Xcode updates.

#### Option 2: Use uv with System Python Integration

Use `uv` to create a project that can access both system packages and installed packages:

```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create project with system site packages
cd /Users/obj-p/Projects/appledb-mcp
uv venv --system-site-packages --python 3.9
source .venv/bin/activate

# Install dependencies (this will fail for mcp, but we can work around it)
uv pip install -e .
```

#### Option 3: Manual Dependency Installation (Current Workaround)

Install only the dependencies that work with Python 3.9:

```bash
# Use system Python
/usr/bin/python3 -m pip install --user pydantic pydantic-settings

# For MCP, we need to work around the version requirement
# (Not recommended for production, but works for development)
```

#### Option 4: Wait for LLDB Python 3.10+ Support

Apple may update LLDB bindings in future Xcode releases to support Python 3.10+.

## Current Development Setup

For now, here's the working setup on this machine:

### 1. Verify LLDB Works with System Python

```bash
PYTHONPATH=$(lldb -P):$PYTHONPATH /usr/bin/python3 -c "import lldb; print(lldb.SBDebugger.GetVersionString())"
```

Expected output:
```
lldb-1703.0.236.21
Apple Swift version 6.2.3...
```

### 2. Install in venv-mcp (Python 3.12)

```bash
source venv-mcp/bin/activate
pip install -e .
```

This installs the package but LLDB won't work without the symlink.

### 3. Use Wrapper Script

The `run_appledb_mcp.sh` wrapper script:
- Sets PYTHONPATH to include LLDB
- Activates the venv
- Runs the server

```bash
./run_appledb_mcp.sh
```

### 4. Claude Desktop Configuration

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "appledb": {
      "command": "/Users/obj-p/Projects/appledb-mcp/run_appledb_mcp.sh",
      "env": {
        "APPLEDB_LOG_LEVEL": "DEBUG"
      }
    }
  }
}
```

## Testing the Setup

### Test 1: LLDB Import

```bash
source venv-mcp/bin/activate
PYTHONPATH=$(lldb -P):$PYTHONPATH python -c "import lldb; print('✓ LLDB works')"
```

If this fails with `ModuleNotFoundError: No module named '_lldb'`, you need Option 1 (symlink).

### Test 2: Server Startup

```bash
./run_appledb_mcp.sh
```

Should see:
```
2026-01-25 00:00:00,000 - __main__ - INFO - Starting appledb-mcp server
2026-01-25 00:00:00,000 - appledb_mcp.server - INFO - Loaded configuration: log_level=DEBUG
2026-01-25 00:00:00,000 - appledb_mcp.server - INFO - Initializing LLDB debugger
```

### Test 3: Health Check via Claude

Once configured in Claude Desktop:

```
User: Check debugger health

Claude: [Calls health_check tool]
```

Expected response:
```
✓ MCP server running, LLDB debugger initialized (version: lldb-1703.0.236.21)
```

## Troubleshooting

### Error: 'NoneType' object has no attribute 'SBDebugger'

**Cause**: LLDB import failed, lldb is None

**Solution**: Create the Python 3.12 symlink (Option 1 above)

### Error: No module named '_lldb'

**Cause**: LLDB binary doesn't match Python version

**Solution**:
1. Use system Python 3.9.6, OR
2. Create symlink for your Python version

### Error: No module named 'mcp'

**Cause**: MCP not installed or wrong Python version

**Solution**: Install in venv with `pip install -e .`

## Recommended Setup (When Symlink is Created)

Once you create the Python 3.12 symlink, the setup becomes much simpler:

```bash
# 1. Create symlink (one time, requires sudo)
cd /Applications/Xcode.app/Contents/SharedFrameworks/LLDB.framework/Resources/Python/lldb/
sudo ln -s _lldb.cpython-39-darwin.so _lldb.cpython-312-darwin.so

# 2. Install package
cd /Users/obj-p/Projects/appledb-mcp
source venv-mcp/bin/activate
pip install -e .

# 3. Test
PYTHONPATH=$(lldb -P):$PYTHONPATH python -m appledb_mcp
```

## Future Improvements

1. **Xcode 15+**: Newer Xcode versions may include Python 3.10+ bindings
2. **Custom LLDB Build**: Build LLDB from source with Python 3.12 support
3. **Docker**: Run in container with proper Python/LLDB versions
4. **Alternative**: Switch to using `lldb` command-line tool instead of Python bindings

## Notes

- This issue is specific to macOS and how Apple ships LLDB
- Linux distributions typically provide LLDB Python bindings for multiple Python versions
- This affects all Python-based LLDB tools on macOS, not just appledb-mcp
