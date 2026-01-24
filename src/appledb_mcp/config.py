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
