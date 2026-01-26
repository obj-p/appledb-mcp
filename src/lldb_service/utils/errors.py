"""Custom exceptions for LLDB service"""


class AppleDBError(Exception):
    """Base exception for all appledb-mcp errors"""

    pass


class LLDBError(AppleDBError):
    """Error related to LLDB operations"""

    pass


class InvalidStateError(AppleDBError):
    """Error when operation is invalid in current state"""

    pass


class ProcessNotFoundError(AppleDBError):
    """Error when target process cannot be found"""

    pass


class ProcessNotAttachedError(AppleDBError):
    """Error when operation requires attached process but none is attached"""

    pass


class FrameworkLoadError(AppleDBError):
    """Error when loading a framework fails"""

    pass


class ConfigurationError(AppleDBError):
    """Error in configuration"""

    pass
