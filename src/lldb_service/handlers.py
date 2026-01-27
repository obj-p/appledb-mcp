"""RPC method handlers - map JSON-RPC methods to debugger operations"""

import logging
from typing import Any, Dict

from .debugger import LLDBDebuggerManager
from .utils.errors import (
    FrameworkLoadError,
    InvalidStateError,
    LLDBError,
    ProcessNotAttachedError,
    ProcessNotFoundError,
)

logger = logging.getLogger(__name__)


async def handle_ping(params: Dict[str, Any]) -> str:
    """Handle ping RPC call.

    Returns:
        "pong"
    """
    return "pong"


async def handle_initialize(params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle initialize RPC call.

    Args:
        params: {"config": {...}}

    Returns:
        {"success": true}

    Raises:
        RuntimeError: If LLDB is not available
    """
    config = params.get("config", {})

    # Reconfigure logging with provided level
    log_level = config.get("log_level", "INFO").upper()
    if not hasattr(logging, log_level):
        logger.warning(f"Invalid log level '{log_level}', using INFO")
        log_level = "INFO"
    logging.getLogger().setLevel(getattr(logging, log_level))
    logger.info(f"Log level set to {log_level}")

    manager = LLDBDebuggerManager.get_instance()

    try:
        manager.initialize(config)
        return {"success": True}
    except RuntimeError as e:
        logger.error(f"Initialization failed: {e}")
        raise


async def handle_attach_process(params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle attach_process RPC call.

    Args:
        params: {"pid": int} or {"name": str}

    Returns:
        ProcessInfo dict

    Raises:
        ValueError: If neither pid nor name provided
        InvalidStateError: If already attached
        LLDBError: If attach fails
    """
    manager = LLDBDebuggerManager.get_instance()

    pid = params.get("pid")
    name = params.get("name")

    if pid is not None:
        process_info = await manager.attach_process_by_pid(pid)
    elif name is not None:
        process_info = await manager.attach_process_by_name(name)
    else:
        raise ValueError("Either 'pid' or 'name' required")

    # Convert Pydantic model to dict
    return process_info.model_dump()


async def handle_launch_app(params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle launch_app RPC call.

    Args:
        params: {
            "executable": str,
            "args": list[str] (optional),
            "env": dict[str, str] (optional),
            "stop_at_entry": bool (optional)
        }

    Returns:
        ProcessInfo dict

    Raises:
        ValueError: If executable not provided
        InvalidStateError: If already attached
        LLDBError: If launch fails
    """
    manager = LLDBDebuggerManager.get_instance()

    executable = params.get("executable")
    if not executable:
        raise ValueError("'executable' parameter required")

    args = params.get("args")
    env = params.get("env")
    stop_at_entry = params.get("stop_at_entry", True)

    process_info = await manager.launch_app(
        executable=executable,
        args=args,
        env=env,
        stop_at_entry=stop_at_entry,
    )

    return process_info.model_dump()


async def handle_detach(params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle detach RPC call.

    Args:
        params: {"kill": bool (optional)}

    Returns:
        {"success": true}

    Raises:
        ProcessNotAttachedError: If no process attached
        LLDBError: If detach fails
    """
    manager = LLDBDebuggerManager.get_instance()
    kill = params.get("kill", False)

    await manager.detach(kill=kill)
    return {"success": True}


async def handle_continue_execution(params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle continue_execution RPC call.

    Returns:
        {"state": str}

    Raises:
        ProcessNotAttachedError: If no process attached
        InvalidStateError: If process not stopped
        LLDBError: If continue fails
    """
    manager = LLDBDebuggerManager.get_instance()
    state = await manager.continue_execution()
    return {"state": state}


async def handle_pause(params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle pause RPC call.

    Returns:
        {"description": str}

    Raises:
        ProcessNotAttachedError: If no process attached
        InvalidStateError: If process not running
        LLDBError: If pause fails
    """
    manager = LLDBDebuggerManager.get_instance()
    description = await manager.pause_execution()
    return {"description": description}


async def handle_step_over(params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle step_over RPC call.

    Args:
        params: {"thread_id": int (optional)}

    Returns:
        {"location": str}

    Raises:
        ProcessNotAttachedError: If no process attached
        InvalidStateError: If process not stopped
        ValueError: If invalid thread ID
    """
    manager = LLDBDebuggerManager.get_instance()
    thread_id = params.get("thread_id")

    location = await manager.step_over(thread_id=thread_id)
    return {"location": location}


async def handle_step_into(params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle step_into RPC call.

    Args:
        params: {"thread_id": int (optional)}

    Returns:
        {"location": str}

    Raises:
        ProcessNotAttachedError: If no process attached
        InvalidStateError: If process not stopped
        ValueError: If invalid thread ID
    """
    manager = LLDBDebuggerManager.get_instance()
    thread_id = params.get("thread_id")

    location = await manager.step_into(thread_id=thread_id)
    return {"location": location}


async def handle_step_out(params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle step_out RPC call.

    Args:
        params: {"thread_id": int (optional)}

    Returns:
        {"location": str}

    Raises:
        ProcessNotAttachedError: If no process attached
        InvalidStateError: If process not stopped
        ValueError: If invalid thread ID
    """
    manager = LLDBDebuggerManager.get_instance()
    thread_id = params.get("thread_id")

    location = await manager.step_out(thread_id=thread_id)
    return {"location": location}


async def handle_evaluate_expression(params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle evaluate_expression RPC call.

    Args:
        params: {
            "expression": str,
            "language": str (optional),
            "frame_index": int (optional)
        }

    Returns:
        {"value": str, "type": str, "summary": str, "error": str | null}

    Raises:
        ValueError: If expression not provided or invalid parameters
        ProcessNotAttachedError: If no process attached
        InvalidStateError: If process not stopped
    """
    manager = LLDBDebuggerManager.get_instance()

    expression = params.get("expression")
    if not expression:
        raise ValueError("'expression' parameter required")

    language = params.get("language")
    frame_index = params.get("frame_index", 0)

    result = await manager.evaluate_expression(
        expression=expression,
        language=language,
        frame_index=frame_index,
    )

    return result


async def handle_get_backtrace(params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle get_backtrace RPC call.

    Args:
        params: {
            "thread_id": int (optional),
            "max_frames": int (optional)
        }

    Returns:
        {"frames": list[dict]}

    Raises:
        ProcessNotAttachedError: If no process attached
        ValueError: If invalid thread ID
    """
    manager = LLDBDebuggerManager.get_instance()

    thread_id = params.get("thread_id")
    max_frames = params.get("max_frames")

    frames = await manager.get_backtrace(thread_id=thread_id, max_frames=max_frames)
    return {"frames": frames}


async def handle_get_variables(params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle get_variables RPC call.

    Args:
        params: {
            "frame_index": int (optional),
            "include_arguments": bool (optional),
            "include_locals": bool (optional)
        }

    Returns:
        {"variables": list[dict]}

    Raises:
        ProcessNotAttachedError: If no process attached
        InvalidStateError: If process not stopped
        ValueError: If invalid frame index
    """
    manager = LLDBDebuggerManager.get_instance()

    frame_index = params.get("frame_index", 0)
    include_arguments = params.get("include_arguments", True)
    include_locals = params.get("include_locals", True)

    variables = await manager.get_variables(
        frame_index=frame_index,
        include_arguments=include_arguments,
        include_locals=include_locals,
    )

    return {"variables": variables}


async def handle_load_framework(params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle load_framework RPC call.

    Args:
        params: {
            "framework_path": str (optional),
            "framework_name": str (optional)
        }

    Returns:
        {
            "success": bool,
            "address": int,
            "already_loaded": bool,
            "message": str
        }

    Raises:
        ValueError: If neither or both parameters provided
        ProcessNotAttachedError: If no process attached
        FileNotFoundError: If framework cannot be resolved
        LLDBError: If framework load fails
    """
    manager = LLDBDebuggerManager.get_instance()

    framework_path = params.get("framework_path")
    framework_name = params.get("framework_name")

    try:
        result = await manager.load_framework(
            framework_path=framework_path,
            framework_name=framework_name,
        )
        return result
    except FileNotFoundError as e:
        # Convert to FrameworkLoadError for proper error code mapping
        raise FrameworkLoadError(str(e)) from e


async def handle_get_debugger_state(params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle get_debugger_state RPC call.

    Returns:
        DebuggerState dict

    Raises:
        None (safe to call anytime)
    """
    manager = LLDBDebuggerManager.get_instance()
    state = await manager.get_debugger_state()
    return state.model_dump()


async def handle_cleanup(params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle cleanup RPC call.

    Returns:
        {"success": true}

    Raises:
        None (safe to call anytime)
    """
    manager = LLDBDebuggerManager.get_instance()
    await manager.cleanup()
    return {"success": True}


# Error code mapping for JSON-RPC errors
ERROR_CODE_MAP = {
    LLDBError: -32000,
    ProcessNotAttachedError: -32001,
    InvalidStateError: -32002,
    ProcessNotFoundError: -32003,
    FrameworkLoadError: -32004,
    ValueError: -32602,
    RuntimeError: -32603,
}


def get_error_code(error: Exception) -> int:
    """Get JSON-RPC error code for exception.

    Args:
        error: Exception instance

    Returns:
        JSON-RPC error code
    """
    for error_type, code in ERROR_CODE_MAP.items():
        if isinstance(error, error_type):
            return code
    return -32603  # Internal error (default)
