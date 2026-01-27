"""Custom exception classes for appledb-mcp"""


class AppleDBError(Exception):
    """Base exception for appledb-mcp"""

    pass


class LLDBError(AppleDBError):
    """LLDB operation failed"""

    pass


class ProcessNotAttachedError(LLDBError):
    """No process currently attached"""

    pass


class ProcessNotFoundError(LLDBError):
    """Process not found"""

    pass


class InvalidStateError(AppleDBError):
    """Operation invalid for current process state"""

    pass


class ConfigurationError(AppleDBError):
    """Configuration error"""

    pass


class FrameworkLoadError(LLDBError):
    """Framework loading error"""

    pass
