# LLDB Service Architecture

## Overview

To avoid Python version binary compatibility issues, we split appledb-mcp into two services:

1. **MCP Server** (Python 3.12) - Handles MCP protocol, Claude Code integration
2. **LLDB Service** (Python 3.9 system) - Handles actual LLDB operations

## Architecture

```
┌─────────────────┐
│  Claude Code    │
└────────┬────────┘
         │ MCP Protocol (stdio)
         ▼
┌─────────────────┐
│  MCP Server     │  Python 3.12 (venv-mcp)
│  (FastMCP)      │  - Tool handlers
│                 │  - Input validation
│                 │  - Response formatting
└────────┬────────┘
         │ JSON-RPC (stdio or HTTP)
         ▼
┌─────────────────┐
│  LLDB Service   │  Python 3.9 (system)
│  (Simple RPC)   │  - LLDB operations
│                 │  - Debugger singleton
│                 │  - Direct LLDB bindings
└────────┬────────┘
         │ Python bindings
         ▼
┌─────────────────┐
│      LLDB       │
└─────────────────┘
```

## Communication Protocol

### Option 1: JSON-RPC over stdio (RECOMMENDED)

**Advantages:**
- No network ports needed
- MCP server manages LLDB service lifecycle
- Simple error handling
- Line-buffered communication

**Message Format:**
```json
// Request
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "attach_process",
  "params": {"pid": 12345}
}

// Response
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "pid": 12345,
    "name": "MyApp",
    "state": "stopped",
    "architecture": "arm64-apple-macosx"
  }
}

// Error
{
  "jsonrpc": "2.0",
  "id": 1,
  "error": {
    "code": -32000,
    "message": "Process not found",
    "data": {"pid": 12345}
  }
}
```

### Option 2: HTTP localhost

**Advantages:**
- Can test with curl
- Service can run independently
- RESTful design option

**Disadvantages:**
- Port management
- Network security concerns (even localhost)
- More complex lifecycle management

## File Structure

```
appledb-mcp/
├── src/
│   ├── appledb_mcp/           # MCP Server (Python 3.12)
│   │   ├── __main__.py
│   │   ├── server.py          # FastMCP server
│   │   ├── lldb_client.py     # Client to LLDB service (NEW)
│   │   ├── tools/             # MCP tool handlers
│   │   └── ...
│   │
│   └── lldb_service/          # LLDB Service (Python 3.9)
│       ├── __main__.py        # Service entry point
│       ├── server.py          # JSON-RPC server
│       ├── debugger.py        # LLDB operations (moved from appledb_mcp)
│       └── handlers.py        # RPC method handlers
│
├── venv-mcp/                  # Python 3.12 venv
├── run_appledb_mcp.sh         # Starts MCP server
└── run_lldb_service.sh        # Starts LLDB service (for testing)
```

## Implementation Steps

### Phase 1: Create LLDB Service

1. Create `src/lldb_service/` directory
2. Move LLDB operations from `appledb_mcp/debugger.py` to `lldb_service/debugger.py`
3. Create JSON-RPC server in `lldb_service/server.py`
4. Test LLDB service independently with system Python

### Phase 2: Create LLDB Client

1. Create `appledb_mcp/lldb_client.py` - subprocess management + JSON-RPC
2. Start LLDB service as subprocess on MCP server startup
3. Proxy all LLDB calls through the client

### Phase 3: Update MCP Tools

1. Update tools to use `lldb_client` instead of `LLDBDebuggerManager`
2. Keep same API surface (tools don't change)
3. Handle subprocess lifecycle (start, stop, restart on crash)

### Phase 4: Testing & Cleanup

1. Test full workflow
2. Update documentation
3. Remove old LLDB integration from MCP server

## LLDB Service API

### Methods

All methods correspond to current `LLDBDebuggerManager` methods:

- `initialize(config)` - Initialize LLDB debugger
- `attach_process(pid?, name?)` - Attach to process
- `launch_app(executable, args?, env?, stop_at_entry?)` - Launch app
- `detach(kill?)` - Detach from process
- `continue_execution()` - Continue
- `pause()` - Pause
- `step_over(thread_id?)` - Step over
- `step_into(thread_id?)` - Step into
- `step_out(thread_id?)` - Step out
- `evaluate_expression(expression, language?, frame_index?)` - Evaluate
- `get_backtrace(thread_id?, max_frames?)` - Get backtrace
- `get_variables(frame_index?, include_arguments?, include_locals?)` - Get variables
- `load_framework(framework_path?, framework_name?)` - Load framework
- `get_debugger_state()` - Get state
- `cleanup()` - Cleanup

### Error Handling

LLDB service returns JSON-RPC errors with codes:
- `-32000` - `LLDBError`
- `-32001` - `ProcessNotAttachedError`
- `-32002` - `InvalidStateError`
- `-32003` - `ProcessNotFoundError`

## Lifecycle Management

### Startup

1. MCP server starts (Python 3.12)
2. MCP server spawns LLDB service subprocess (Python 3.9 system)
3. LLDB service initializes and sends ready signal
4. MCP server starts accepting MCP requests

### Shutdown

1. MCP server receives shutdown signal
2. MCP server sends `cleanup` to LLDB service
3. LLDB service cleans up LLDB resources
4. LLDB service exits gracefully
5. MCP server waits for subprocess exit
6. MCP server exits

### Error Recovery

If LLDB service crashes:
1. MCP server detects subprocess exit
2. Log error with exit code
3. Restart LLDB service (with backoff)
4. Return error to pending requests
5. After 3 failed restarts, fail permanently

## Testing Strategy

### Unit Tests

- **MCP Server**: Mock `lldb_client` for testing tools
- **LLDB Service**: Mock `lldb` module for testing handlers

### Integration Tests

1. Start LLDB service manually
2. Send JSON-RPC requests via stdio/HTTP
3. Verify responses
4. Test with actual LLDB operations

### End-to-End Tests

1. Start full MCP server
2. Connect Claude Code
3. Test debugging workflow
4. Verify error handling

## Advantages of This Architecture

1. **No binary hacks** - Each service uses correct Python version
2. **Isolation** - LLDB crashes don't affect MCP server
3. **Testability** - Services can be tested independently
4. **Flexibility** - Easy to swap implementations
5. **Debugging** - Can attach debugger to each service separately
6. **Performance** - Can optimize each service independently

## Migration Path

1. **v0.1.0**: Current single-process architecture (ship as-is with known limitations)
2. **v0.2.0**: Two-process architecture (breaking change, better foundation)
3. **Future**: Could add more services (SwiftUI inspector, etc.)

## Open Questions

1. **Communication protocol**: stdio JSON-RPC or HTTP? (Recommendation: stdio)
2. **Serialization**: How to handle complex LLDB objects? (Recommendation: convert to dicts)
3. **Performance**: Is IPC overhead acceptable? (Test needed)
4. **Error recovery**: How aggressive should restart logic be? (Recommendation: 3 tries with backoff)
