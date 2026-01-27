"""Models for appledb-mcp - re-exported from lldb_service for compatibility

NOTE: This file re-exports models from lldb_service to ensure schema compatibility
between the MCP server and LLDB service. Both services share the same model definitions.

IMPORTANT: For this import to work, the src/ directory must be in PYTHONPATH:
  export PYTHONPATH="${PWD}/src:${PYTHONPATH}"

Or when installed as packages, both should be under the same namespace.
"""

# Import all models from LLDB service
from lldb_service.models import (
    ProcessInfo,
    ThreadInfo,
    FrameInfo,
    VariableInfo,
    EvaluationResult,
    TargetInfo,
    DebuggerState,
)

__all__ = [
    "ProcessInfo",
    "ThreadInfo",
    "FrameInfo",
    "VariableInfo",
    "EvaluationResult",
    "TargetInfo",
    "DebuggerState",
]
