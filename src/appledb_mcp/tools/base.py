"""Base utilities for MCP tools"""

import logging
from functools import wraps
from typing import Any, Callable

from ..utils.errors import AppleDBError

logger = logging.getLogger(__name__)


def handle_tool_errors(func: Callable) -> Callable:
    """Decorator to handle errors in MCP tools

    This decorator catches AppleDBError and ValueError exceptions and returns
    user-friendly error messages. Unexpected exceptions are logged and returned
    as generic errors.

    Args:
        func: The async function to wrap

    Returns:
        Wrapped function that handles errors gracefully
    """
    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> str:
        try:
            return await func(*args, **kwargs)
        except (AppleDBError, ValueError) as e:
            # User-friendly error message for known errors
            logger.debug(f"Tool error in {func.__name__}: {e}")
            return f"Error: {str(e)}"
        except Exception as e:
            # Log unexpected errors
            logger.exception(f"Unexpected error in {func.__name__}")
            return f"Unexpected error: {str(e)}"

    return wrapper
