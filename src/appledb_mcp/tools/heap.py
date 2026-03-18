"""Heap introspection MCP tools

These tools use the AppleDBRuntime Swift framework, which gets dynamically
loaded into the debugged process. The framework provides heap walking,
class introspection, and retain cycle detection using malloc zone enumeration
and ObjC runtime APIs.
"""

import json
import logging
import subprocess
from pathlib import Path
from typing import Optional

from ..lldb_client import LLDBClient
from ..server import mcp
from .base import handle_tool_errors

logger = logging.getLogger(__name__)

# Path to the framework relative to project root
_FRAMEWORK_DIR = Path(__file__).parent.parent.parent.parent / "frameworks"
_BUILD_SCRIPT = Path(__file__).parent.parent.parent.parent / "AppleDBRuntime" / "build.sh"


async def _ensure_runtime(client: LLDBClient) -> None:
    """Ensure AppleDBRuntime framework is loaded. Auto-builds if missing."""
    framework_path = _FRAMEWORK_DIR / "AppleDBRuntime.framework" / "AppleDBRuntime"

    if not framework_path.exists():
        logger.info("AppleDBRuntime not found, building...")
        if not _BUILD_SCRIPT.exists():
            raise RuntimeError(
                "AppleDBRuntime build script not found. "
                "Expected at: AppleDBRuntime/build.sh"
            )
        result = subprocess.run(
            ["bash", str(_BUILD_SCRIPT)],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode != 0:
            raise RuntimeError(f"Failed to build AppleDBRuntime: {result.stderr}")
        logger.info("AppleDBRuntime built successfully")

    await client.load_framework(framework_name="AppleDBRuntime")


async def _eval_runtime(client: LLDBClient, expression: str) -> list | dict:
    """Evaluate an AppleDBRuntime expression and parse the JSON result."""
    result = await client.evaluate_expression(
        expression=expression,
        language="objc",
        timeout=120.0,
    )

    if result.get("error"):
        raise RuntimeError(f"Expression eval failed: {result['error']}")

    # LLDB returns NSString summary with surrounding quotes and escaped inner quotes
    summary = result.get("summary", "") or ""
    # Strip surrounding quotes: '"....."' -> '.....'
    if summary.startswith('"') and summary.endswith('"'):
        summary = summary[1:-1]
    # Unescape inner quotes
    summary = summary.replace('\\"', '"')
    summary = summary.replace('\\\\', '\\')

    if not summary:
        return []

    return json.loads(summary)


@mcp.tool()
@handle_tool_errors
async def lldb_heap_summary(limit: int = 50) -> str:
    """Show heap class histogram — instance count and total size per class

    Enumerates all live heap objects in the debugged process using malloc
    zone introspection. Groups by class, sorted by total memory usage.

    Args:
        limit: Maximum number of classes to show (default 50)

    Returns:
        Table of classes with instance count and total memory size
    """
    client = LLDBClient.get_instance()
    await _ensure_runtime(client)

    data = await _eval_runtime(client, "[AppleDBRuntime heapSummary]")

    if isinstance(data, dict) and "error" in data:
        return f"Error: {data['error']}"

    if not data:
        return "No heap objects found"

    entries = data[:limit] if isinstance(data, list) else []

    output = f"Heap summary ({len(entries)} classes shown):\n\n"
    output += f"{'Class':<50} {'Count':>8} {'Size':>12}\n"
    output += "-" * 72 + "\n"

    total_count = 0
    total_size = 0
    for entry in entries:
        cls = entry.get("class", "?")
        count = entry.get("count", 0)
        size = entry.get("totalSize", 0)
        total_count += count
        total_size += size

        if size >= 1_048_576:
            size_str = f"{size / 1_048_576:.1f} MB"
        elif size >= 1024:
            size_str = f"{size / 1024:.1f} KB"
        else:
            size_str = f"{size} B"

        output += f"{cls:<50} {count:>8} {size_str:>12}\n"

    output += "-" * 72 + "\n"
    total_size_str = f"{total_size / 1_048_576:.1f} MB" if total_size >= 1_048_576 else f"{total_size / 1024:.1f} KB"
    output += f"{'Total':<50} {total_count:>8} {total_size_str:>12}"

    return output


@mcp.tool()
@handle_tool_errors
async def lldb_heap_instances(class_name: str) -> str:
    """Find all instances of a specific class on the heap

    Args:
        class_name: The class name to search for (e.g., "UIView", "MyViewController")

    Returns:
        List of instances with address and size
    """
    client = LLDBClient.get_instance()
    await _ensure_runtime(client)

    expr = f'[AppleDBRuntime instancesOf:@"{class_name}"]'
    data = await _eval_runtime(client, expr)

    if isinstance(data, dict) and "error" in data:
        return f"Error: {data['error']}"

    if not data:
        return f"No instances of '{class_name}' found"

    output = f"{len(data)} instance(s) of '{class_name}':\n\n"
    for entry in data:
        addr = entry.get("address", "?")
        size = entry.get("size", 0)
        output += f"  {addr}  ({size} bytes)\n"

    return output


@mcp.tool()
@handle_tool_errors
async def lldb_heap_describe(address: str) -> str:
    """Describe a heap object — class hierarchy, ivars, properties

    Args:
        address: Memory address as hex string (e.g., "0x600001234")

    Returns:
        Detailed object description with class chain, ivars, and properties
    """
    client = LLDBClient.get_instance()
    await _ensure_runtime(client)

    addr_int = int(address, 16) if address.startswith("0x") else int(address)
    expr = f"[AppleDBRuntime describeAddress:{addr_int}]"
    data = await _eval_runtime(client, expr)

    if isinstance(data, dict) and "error" in data:
        return f"Error: {data['error']}"

    cls = data.get("class", "?")
    addr = data.get("address", address)
    size = data.get("size", 0)
    supers = data.get("superclasses", [])

    output = f"Object at {addr}\n"
    output += f"  Class: {cls} ({size} bytes)\n"
    if supers:
        output += f"  Inherits: {' > '.join(supers)}\n"

    ivars = data.get("ivarValues", data.get("ivars", []))
    if ivars:
        output += f"\n  Ivars ({len(ivars)}):\n"
        for ivar in ivars:
            name = ivar.get("name", "?")
            typ = ivar.get("type", "")
            if "class" in ivar:
                output += f"    {name}: {ivar['class']} @ {ivar.get('address', '?')}\n"
            elif "value" in ivar:
                output += f"    {name}: {ivar['value']} ({typ})\n"
            else:
                output += f"    {name}: ({typ})\n"

    props = data.get("properties", [])
    if props:
        output += f"\n  Properties ({len(props)}):\n"
        for prop in props:
            output += f"    {prop.get('name', '?')}\n"

    return output


@mcp.tool()
@handle_tool_errors
async def lldb_heap_references(address: str) -> str:
    """Show what objects a given object references (outbound references)

    Args:
        address: Memory address as hex string (e.g., "0x600001234")

    Returns:
        List of referenced objects with ivar name, class, and address
    """
    client = LLDBClient.get_instance()
    await _ensure_runtime(client)

    addr_int = int(address, 16) if address.startswith("0x") else int(address)
    expr = f"[AppleDBRuntime referencesFrom:{addr_int}]"
    data = await _eval_runtime(client, expr)

    if isinstance(data, dict) and "error" in data:
        return f"Error: {data['error']}"

    if not data:
        return "No outbound references found"

    output = f"{len(data)} reference(s):\n\n"
    for ref in data:
        ivar = ref.get("ivar", "?")
        cls = ref.get("class", "?")
        addr = ref.get("address", "?")
        output += f"  .{ivar} -> {cls} @ {addr}\n"

    return output


@mcp.tool()
@handle_tool_errors
async def lldb_heap_retain_cycles(address: str, max_depth: int = 10) -> str:
    """Detect retain cycles starting from an object

    Follows strong (object) references via BFS and detects cycles
    that loop back to the starting object.

    Args:
        address: Memory address as hex string (e.g., "0x600001234")
        max_depth: Maximum search depth (default 10)

    Returns:
        List of detected retain cycles, or "No cycles found"
    """
    client = LLDBClient.get_instance()
    await _ensure_runtime(client)

    addr_int = int(address, 16) if address.startswith("0x") else int(address)
    expr = f"[AppleDBRuntime retainCyclesFrom:{addr_int} maxDepth:{max_depth}]"
    data = await _eval_runtime(client, expr)

    if isinstance(data, dict) and "error" in data:
        return f"Error: {data['error']}"

    if not data:
        return "No retain cycles detected"

    output = f"{len(data)} retain cycle(s) found:\n\n"
    for i, cycle in enumerate(data, 1):
        nodes = cycle.get("cycle", [])
        output += f"  Cycle {i}:\n"
        for j, node in enumerate(nodes):
            prefix = "    -> " if j > 0 else "    "
            output += f"{prefix}{node}\n"
        output += "\n"

    return output
