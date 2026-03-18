"""Data models for the LLDB service.

Uses stdlib dataclasses instead of pydantic so the LLDB service can run
on system Python (3.9) without any third-party dependencies.
"""

from dataclasses import dataclass, field, asdict
from typing import List, Optional


@dataclass
class ProcessInfo:
    """Information about an attached process"""
    pid: int
    name: str
    state: str
    architecture: str

    def model_dump(self) -> dict:
        return asdict(self)


@dataclass
class ThreadInfo:
    """Information about a thread"""
    id: int
    state: str
    name: str = ""
    stop_reason: Optional[str] = None
    is_selected: bool = False

    def model_dump(self) -> dict:
        return asdict(self)


@dataclass
class FrameInfo:
    """Information about a stack frame"""
    index: int
    pc: str
    function: str
    module: str
    file: Optional[str] = None
    line: Optional[int] = None

    def model_dump(self) -> dict:
        return asdict(self)


@dataclass
class VariableInfo:
    """Information about a variable"""
    name: str
    type: str
    value: str
    summary: str = ""

    def model_dump(self) -> dict:
        return asdict(self)


@dataclass
class EvaluationResult:
    """Result of expression evaluation"""
    value: str
    type: str
    summary: str = ""
    error: Optional[str] = None

    def model_dump(self) -> dict:
        return asdict(self)


@dataclass
class TargetInfo:
    """Information about the debug target"""
    triple: str
    executable: Optional[str] = None

    def model_dump(self) -> dict:
        return asdict(self)


@dataclass
class BreakpointInfo:
    """Information about a breakpoint"""
    id: int
    locations: int = 0
    enabled: bool = True
    hit_count: int = 0
    condition: Optional[str] = None
    file: Optional[str] = None
    line: Optional[int] = None
    symbol: Optional[str] = None

    def model_dump(self) -> dict:
        return asdict(self)


@dataclass
class DebuggerState:
    """Complete debugger state snapshot"""
    attached: bool
    state: str
    process: Optional[ProcessInfo] = None
    target: Optional[TargetInfo] = None
    threads: List[ThreadInfo] = field(default_factory=list)
    loaded_frameworks: List[str] = field(default_factory=list)

    def model_dump(self) -> dict:
        d = {
            "attached": self.attached,
            "state": self.state,
            "process": self.process.model_dump() if self.process else None,
            "target": self.target.model_dump() if self.target else None,
            "threads": [t.model_dump() for t in self.threads],
            "loaded_frameworks": self.loaded_frameworks,
        }
        return d
