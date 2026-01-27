"""Shared exception classes for appledb-mcp

This module defines all custom exceptions used by both the MCP server
and the LLDB service. Having a single source of truth prevents schema
divergence and makes error handling consistent across services.
"""


class AppleDBError(Exception):
    """Base exception for all appledb-mcp errors

    All custom exceptions in the project inherit from this base class,
    making it easy to catch any project-specific error.
    """

    pass


class LLDBError(AppleDBError):
    """Error related to LLDB operations

    Raised when an LLDB API call or operation fails. This includes
    debugger initialization, process control, and inspection failures.
    """

    pass


class ProcessNotAttachedError(LLDBError):
    """Error when operation requires attached process but none is attached

    Raised when attempting debugging operations (breakpoints, continue,
    inspection) without first attaching to a process.
    """

    pass


class ProcessNotFoundError(LLDBError):
    """Error when target process cannot be found

    Raised when attempting to attach to a process by name or PID that
    doesn't exist or is not accessible.
    """

    pass


class InvalidStateError(AppleDBError):
    """Error when operation is invalid in current state

    Raised when attempting an operation that's not valid in the current
    debugger state (e.g., continuing a non-running process).
    """

    pass


class ConfigurationError(AppleDBError):
    """Configuration error

    Raised when there are problems with configuration values,
    missing required settings, or invalid configuration.
    """

    pass


class FrameworkLoadError(LLDBError):
    """Framework loading error

    Raised when attempting to load a framework fails, either because
    the framework doesn't exist, can't be found, or LLDB can't load it.
    """

    pass
