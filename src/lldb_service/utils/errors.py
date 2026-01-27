"""Custom exceptions for LLDB service

This module re-exports all error classes from the shared common.errors module.
This maintains backward compatibility while using a single source of truth.
"""

from common.errors import (
    AppleDBError,
    ConfigurationError,
    FrameworkLoadError,
    InvalidStateError,
    LLDBError,
    ProcessNotAttachedError,
    ProcessNotFoundError,
)

__all__ = [
    "AppleDBError",
    "LLDBError",
    "InvalidStateError",
    "ProcessNotFoundError",
    "ProcessNotAttachedError",
    "FrameworkLoadError",
    "ConfigurationError",
]
