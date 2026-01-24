"""Pydantic models for data validation and responses"""

from typing import Optional

from pydantic import BaseModel, Field


class ProcessInfo(BaseModel):
    """Information about an attached process"""

    pid: int = Field(..., description="Process ID")
    name: str = Field(..., description="Process name")
    state: str = Field(..., description="Process state (stopped, running, etc.)")
    architecture: str = Field(..., description="Process architecture (e.g., arm64, x86_64)")


class ThreadInfo(BaseModel):
    """Information about a thread"""

    id: int = Field(..., description="Thread ID")
    name: str = Field(default="", description="Thread name")
    state: str = Field(..., description="Thread state")
    stop_reason: Optional[str] = Field(None, description="Reason thread stopped")
    is_selected: bool = Field(default=False, description="Whether this is the selected thread")


class FrameInfo(BaseModel):
    """Information about a stack frame"""

    index: int = Field(..., description="Frame index (0 = current)")
    pc: str = Field(..., description="Program counter (address)")
    function: str = Field(..., description="Function name")
    file: Optional[str] = Field(None, description="Source file path")
    line: Optional[int] = Field(None, description="Line number in source file")
    module: str = Field(..., description="Module/library name")


class VariableInfo(BaseModel):
    """Information about a variable"""

    name: str = Field(..., description="Variable name")
    type: str = Field(..., description="Variable type")
    value: str = Field(..., description="Variable value as string")
    summary: str = Field(default="", description="Variable summary/description")


class EvaluationResult(BaseModel):
    """Result of expression evaluation"""

    value: str = Field(..., description="Result value as string")
    type: str = Field(..., description="Result type")
    summary: str = Field(default="", description="Result summary")
    error: Optional[str] = Field(None, description="Error message if evaluation failed")
