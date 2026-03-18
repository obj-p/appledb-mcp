"""Configuration management for appledb-mcp"""

import os
from pathlib import Path
from typing import List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppleDBConfig(BaseSettings):
    """Configuration for appledb-mcp server

    All settings can be configured via environment variables with the APPLEDB_ prefix.
    """

    model_config = SettingsConfigDict(env_prefix="APPLEDB_", case_sensitive=False)

    # LLDB timeout for commands (seconds)
    lldb_timeout: int = Field(default=30, description="Timeout for LLDB operations in seconds")

    # Log level
    log_level: str = Field(default="INFO", description="Logging level")

    # Performance limits
    max_backtrace_frames: int = Field(
        default=100, description="Maximum frames to return in backtrace"
    )
    max_variable_depth: int = Field(
        default=3, description="Maximum depth for variable inspection"
    )

    # Subprocess management
    lldb_python: str = Field(
        default="python3",
        description="Path to Python 3.9+ interpreter with LLDB bindings"
    )
    service_max_restarts: int = Field(
        default=3,
        description="Maximum automatic restarts on service crash"
    )
    service_restart_backoff: float = Field(
        default=1.0,
        description="Base backoff time (seconds) for restart exponential backoff"
    )
    service_request_timeout: float = Field(
        default=30.0,
        description="Timeout for RPC requests to LLDB service (seconds)"
    )
    service_restart_reset_time: float = Field(
        default=300.0,
        description="Time in seconds of stable operation before resetting restart counter"
    )
