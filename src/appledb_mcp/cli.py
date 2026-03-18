"""AppleDB CLI - LLDB debugger bridge (ADB-style)"""

import asyncio
import json
import logging
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Optional

import click

from .tcp_client import LLDBTCPClient, DEFAULT_PORT

STATE_DIR = Path.home() / ".appledb"


def _resolve_port(port_option: Optional[int]) -> int:
    """Resolve server port using discovery order:
    1. --port flag
    2. APPLEDB_PORT env var
    3. ~/.appledb/server.port file
    4. Default 5037
    """
    if port_option is not None:
        return port_option

    env_port = os.environ.get("APPLEDB_PORT")
    if env_port:
        return int(env_port)

    port_file = STATE_DIR / "server.port"
    if port_file.exists():
        try:
            return int(port_file.read_text().strip())
        except (ValueError, OSError):
            pass

    return DEFAULT_PORT


def _is_server_running(port: int) -> bool:
    """Check if server is running on given port."""
    async def _check():
        client = LLDBTCPClient(port=port)
        return await client.ping()
    try:
        return asyncio.run(_check())
    except Exception:
        return False


def _get_server_pid() -> Optional[int]:
    """Get PID of running server from state file."""
    pid_file = STATE_DIR / "server.pid"
    if pid_file.exists():
        try:
            pid = int(pid_file.read_text().strip())
            # Check if process is alive
            os.kill(pid, 0)
            return pid
        except (ValueError, OSError):
            pass
    return None


def _find_lldb_python() -> str:
    """Find a Python interpreter that can import LLDB.

    Discovery order:
    1. APPLEDB_LLDB_PYTHON env var
    2. /usr/bin/python3 (macOS system Python, usually has LLDB)
    3. python3 on PATH with lldb -P PYTHONPATH
    """
    # 1. Explicit env var
    explicit = os.environ.get("APPLEDB_LLDB_PYTHON")
    if explicit:
        return explicit

    # 2. Get LLDB Python path for testing candidates
    lldb_python_path = None
    try:
        result = subprocess.run(
            ["lldb", "-P"], capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            lldb_python_path = result.stdout.strip()
    except Exception:
        pass

    # 3. Try common system Python paths
    for candidate in ["/usr/bin/python3", "python3.9", "python3"]:
        import shutil
        path = candidate if candidate.startswith("/") else shutil.which(candidate)
        if not path or not os.path.exists(path):
            continue
        try:
            env = os.environ.copy()
            if lldb_python_path:
                env["PYTHONPATH"] = lldb_python_path
            result = subprocess.run(
                [path, "-c", "import lldb"],
                capture_output=True, text=True, timeout=5, env=env
            )
            if result.returncode == 0:
                return path
        except Exception:
            continue

    # Fall back to system python3
    return "/usr/bin/python3"


def _start_server_background(port: int) -> None:
    """Start LLDB server as background process."""
    python_path = _find_lldb_python()
    src_path = str(Path(__file__).parent.parent)

    # Set up PYTHONPATH with LLDB bindings
    env = os.environ.copy()
    try:
        result = subprocess.run(
            ["lldb", "-P"], capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            lldb_python_path = result.stdout.strip()
            pythonpath = env.get("PYTHONPATH", "")
            env["PYTHONPATH"] = f"{src_path}:{lldb_python_path}:{pythonpath}".rstrip(":")
        else:
            env["PYTHONPATH"] = f"{src_path}:{env.get('PYTHONPATH', '')}".rstrip(":")
    except Exception:
        env["PYTHONPATH"] = f"{src_path}:{env.get('PYTHONPATH', '')}".rstrip(":")

    # Start server as detached subprocess
    proc = subprocess.Popen(
        [python_path, "-m", "lldb_service", "--tcp", "--port", str(port)],
        cwd=src_path,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )

    # Wait briefly for startup
    for _ in range(20):  # Up to 2 seconds
        time.sleep(0.1)
        if _is_server_running(port):
            click.echo(f"Server started on port {port} (PID {proc.pid})", err=True)
            return

    # Check if process died
    if proc.poll() is not None:
        stderr = proc.stderr.read().decode() if proc.stderr else ""
        raise click.ClickException(f"Server failed to start: {stderr}")

    click.echo(f"Server starting on port {port} (PID {proc.pid})", err=True)


def _ensure_server(port: int) -> None:
    """Ensure server is running, auto-start if needed."""
    if not _is_server_running(port):
        click.echo("Server not running. Starting...", err=True)
        _start_server_background(port)


def _run(port: int, method: str, params: Optional[dict] = None) -> Any:
    """Run a JSON-RPC call against the server."""
    async def _call():
        client = LLDBTCPClient(port=port)
        return await client.call(method, params or {})
    return asyncio.run(_call())


@click.group()
@click.option("--port", type=int, default=None, envvar="APPLEDB_PORT",
              help=f"Server port (default: {DEFAULT_PORT})")
@click.option("--log-level", default="WARNING", help="Log level")
@click.pass_context
def main(ctx, port, log_level):
    """AppleDB - LLDB debugger bridge"""
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.WARNING),
        format="%(levelname)s: %(message)s",
        stream=sys.stderr,
    )
    ctx.ensure_object(dict)
    ctx.obj["port"] = _resolve_port(port)


# ── Server lifecycle ─────────────────────────────────────────────

@main.command("start-server")
@click.option("--port", type=int, default=None, help="Port to listen on")
@click.pass_context
def start_server(ctx, port):
    """Start the LLDB server daemon"""
    port = port or ctx.obj["port"]
    if _is_server_running(port):
        click.echo(f"Server already running on port {port}")
        return
    _start_server_background(port)


@main.command("kill-server")
@click.pass_context
def kill_server(ctx):
    """Stop the LLDB server"""
    pid = _get_server_pid()
    if pid is None:
        click.echo("No server running")
        return
    try:
        os.kill(pid, signal.SIGTERM)
        click.echo(f"Server (PID {pid}) stopped")
        # Clean up state files
        for name in ("server.pid", "server.port"):
            try:
                (STATE_DIR / name).unlink(missing_ok=True)
            except Exception:
                pass
    except ProcessLookupError:
        click.echo("Server not running (stale PID file)")
        for name in ("server.pid", "server.port"):
            try:
                (STATE_DIR / name).unlink(missing_ok=True)
            except Exception:
                pass


@main.command("server-status")
@click.pass_context
def server_status(ctx):
    """Check server status"""
    port = ctx.obj["port"]
    pid = _get_server_pid()
    if _is_server_running(port):
        click.echo(f"Server running on port {port} (PID {pid})")
    else:
        click.echo("Server not running")


# ── MCP mode ─────────────────────────────────────────────────────

@main.command("mcp")
def mcp_mode():
    """Run as MCP server (stdio transport)"""
    from appledb_mcp.__main__ import main as mcp_main
    mcp_main()


# ── Debugging commands ───────────────────────────────────────────

@main.command()
@click.argument("pid", type=int, required=False)
@click.option("-n", "--name", help="Process name to attach to")
@click.pass_context
def attach(ctx, pid, name):
    """Attach to a process by PID or name"""
    port = ctx.obj["port"]
    _ensure_server(port)

    if not pid and not name:
        raise click.UsageError("Provide PID or --name")

    params = {"pid": pid} if pid else {"name": name}
    try:
        result = _run(port, "attach_process", params)
        click.echo(f"Attached to '{result['name']}' (PID {result['pid']}, {result['architecture']})")
    except Exception as e:
        raise click.ClickException(str(e))


@main.command()
@click.argument("executable")
@click.option("--args", multiple=True, help="Arguments to pass")
@click.option("--no-stop", is_flag=True, help="Don't stop at entry point")
@click.pass_context
def launch(ctx, executable, args, no_stop):
    """Launch an application for debugging"""
    port = ctx.obj["port"]
    _ensure_server(port)

    params = {
        "executable": executable,
        "args": list(args),
        "env": {},
        "stop_at_entry": not no_stop,
    }
    try:
        result = _run(port, "launch_app", params)
        click.echo(f"Launched '{result['name']}' (PID {result['pid']})")
    except Exception as e:
        raise click.ClickException(str(e))


@main.command()
@click.option("--kill", is_flag=True, help="Kill the process instead of detaching")
@click.pass_context
def detach(ctx, kill):
    """Detach from the current process"""
    port = ctx.obj["port"]
    _ensure_server(port)

    try:
        _run(port, "detach", {"kill": kill})
        action = "Killed" if kill else "Detached from"
        click.echo(f"{action} process")
    except Exception as e:
        raise click.ClickException(str(e))


@main.command()
@click.pass_context
def status(ctx):
    """Show debugger state"""
    port = ctx.obj["port"]
    _ensure_server(port)

    try:
        state = _run(port, "get_debugger_state", {})
        if not state.get("attached"):
            click.echo("State: detached (no process attached)")
            return
        proc = state.get("process", {})
        click.echo(f"State: {state['state']}")
        click.echo(f"Process: {proc.get('name', '?')} (PID {proc.get('pid', '?')})")
        click.echo(f"Architecture: {proc.get('architecture', '?')}")
        threads = state.get("threads", [])
        if threads:
            click.echo(f"Threads: {len(threads)}")
        frameworks = state.get("loaded_frameworks", [])
        if frameworks:
            click.echo(f"Frameworks: {', '.join(frameworks)}")
    except Exception as e:
        raise click.ClickException(str(e))


@main.command("continue")
@click.pass_context
def continue_exec(ctx):
    """Continue execution"""
    port = ctx.obj["port"]
    _ensure_server(port)
    try:
        result = _run(port, "continue_execution", {})
        click.echo(f"Continued ({result.get('state', 'running')})")
    except Exception as e:
        raise click.ClickException(str(e))


@main.command()
@click.pass_context
def pause(ctx):
    """Pause execution"""
    port = ctx.obj["port"]
    _ensure_server(port)
    try:
        result = _run(port, "pause", {})
        click.echo(result.get("description", "Paused"))
    except Exception as e:
        raise click.ClickException(str(e))


@main.command()
@click.argument("direction", type=click.Choice(["over", "into", "out"]), default="over")
@click.option("--thread", type=int, default=None, help="Thread ID")
@click.pass_context
def step(ctx, direction, thread):
    """Step execution (over, into, or out)"""
    port = ctx.obj["port"]
    _ensure_server(port)

    method = f"step_{direction}"
    params = {"thread_id": thread} if thread else {}
    try:
        result = _run(port, method, params)
        click.echo(result.get("location", f"Stepped {direction}"))
    except Exception as e:
        raise click.ClickException(str(e))


@main.command("eval")
@click.argument("expression")
@click.option("--lang", type=click.Choice(["swift", "objc", "c++", "c"]), default=None)
@click.option("--frame", type=int, default=0, help="Frame index")
@click.pass_context
def evaluate(ctx, expression, lang, frame):
    """Evaluate an expression"""
    port = ctx.obj["port"]
    _ensure_server(port)

    params = {"expression": expression, "frame_index": frame}
    if lang:
        params["language"] = lang
    try:
        result = _run(port, "evaluate_expression", params)
        if result.get("error"):
            click.echo(f"Error: {result['error']}", err=True)
        else:
            click.echo(f"({result.get('type', '?')}) {result.get('value', '')}")
            if result.get("summary"):
                click.echo(f"  {result['summary']}")
    except Exception as e:
        raise click.ClickException(str(e))


@main.command()
@click.option("--max-frames", type=int, default=None, help="Max frames to show")
@click.option("--thread", type=int, default=None, help="Thread ID")
@click.pass_context
def bt(ctx, max_frames, thread):
    """Show backtrace"""
    port = ctx.obj["port"]
    _ensure_server(port)

    params = {}
    if thread is not None:
        params["thread_id"] = thread
    if max_frames is not None:
        params["max_frames"] = max_frames
    try:
        result = _run(port, "get_backtrace", params)
        frames = result.get("frames", []) if isinstance(result, dict) else result
        if not frames:
            click.echo("No frames")
            return
        for f in frames:
            loc = f.get("function", "?")
            if f.get("file") and f.get("line"):
                loc += f" at {f['file']}:{f['line']}"
            elif f.get("pc"):
                loc += f" at {f['pc']}"
            mod = f" [{f['module']}]" if f.get("module") else ""
            click.echo(f"  #{f['index']}: {loc}{mod}")
    except Exception as e:
        raise click.ClickException(str(e))


@main.command()
@click.option("--frame", type=int, default=0, help="Frame index")
@click.pass_context
def vars(ctx, frame):
    """Show variables in current frame"""
    port = ctx.obj["port"]
    _ensure_server(port)

    try:
        result = _run(port, "get_variables", {"frame_index": frame})
        variables = result.get("variables", []) if isinstance(result, dict) else result
        if not variables:
            click.echo("No variables")
            return
        for v in variables:
            line = f"  {v['name']}: {v.get('type', '?')}"
            if v.get("value"):
                line += f" = {v['value']}"
            click.echo(line)
            if v.get("summary"):
                click.echo(f"    {v['summary']}")
    except Exception as e:
        raise click.ClickException(str(e))


@main.command()
@click.pass_context
def threads(ctx):
    """List all threads"""
    port = ctx.obj["port"]
    _ensure_server(port)

    try:
        result = _run(port, "list_threads", {})
        thread_list = result.get("threads", []) if isinstance(result, dict) else result
        if not thread_list:
            click.echo("No threads")
            return
        for t in thread_list:
            sel = "*" if t.get("is_selected") else " "
            click.echo(f"  {sel} Thread {t['id']}: {t.get('name', '?')} ({t.get('state', '?')})")
            if t.get("stop_reason"):
                click.echo(f"      {t['stop_reason']}")
    except Exception as e:
        raise click.ClickException(str(e))


@main.command()
@click.argument("command", nargs=-1, required=True)
@click.pass_context
def cmd(ctx, command):
    """Execute a raw LLDB command"""
    port = ctx.obj["port"]
    _ensure_server(port)

    cmd_str = " ".join(command)
    try:
        result = _run(port, "execute_command", {"command": cmd_str})
        if result.get("output"):
            click.echo(result["output"], nl=False)
        if result.get("error"):
            click.echo(result["error"], err=True, nl=False)
    except Exception as e:
        raise click.ClickException(str(e))


# ── Breakpoint subgroup ──────────────────────────────────────────

@main.group()
def bp():
    """Breakpoint management"""
    pass


@bp.command("set")
@click.argument("target")
@click.option("--condition", "-c", help="Breakpoint condition")
@click.pass_context
def bp_set(ctx, target, condition):
    """Set a breakpoint (file:line or symbol name)

    Examples:
      appledb bp set main.c:42
      appledb bp set viewDidLoad
      appledb bp set malloc --condition '$arg1 > 1024'
    """
    port = ctx.parent.parent.obj["port"]
    _ensure_server(port)

    params = {}
    if ":" in target:
        parts = target.rsplit(":", 1)
        params["file"] = parts[0]
        try:
            params["line"] = int(parts[1])
        except ValueError:
            raise click.UsageError(f"Invalid line number: {parts[1]}")
    else:
        params["symbol"] = target

    if condition:
        params["condition"] = condition

    try:
        result = _run(port, "set_breakpoint", params)
        click.echo(f"Breakpoint {result['id']} set ({result.get('locations', 0)} locations)")
    except Exception as e:
        raise click.ClickException(str(e))


@bp.command("list")
@click.pass_context
def bp_list(ctx):
    """List all breakpoints"""
    port = ctx.parent.parent.obj["port"]
    _ensure_server(port)

    try:
        result = _run(port, "list_breakpoints", {})
        breakpoints = result.get("breakpoints", []) if isinstance(result, dict) else result
        if not breakpoints:
            click.echo("No breakpoints")
            return
        for bp_info in breakpoints:
            status = "on" if bp_info.get("enabled", True) else "off"
            loc = ""
            if bp_info.get("file") and bp_info.get("line"):
                loc = f"{bp_info['file']}:{bp_info['line']}"
            elif bp_info.get("symbol"):
                loc = bp_info["symbol"]
            click.echo(f"  {bp_info['id']}: {loc} [{status}] hits={bp_info.get('hit_count', 0)}")
    except Exception as e:
        raise click.ClickException(str(e))


@bp.command("delete")
@click.argument("breakpoint_id", type=int)
@click.pass_context
def bp_delete(ctx, breakpoint_id):
    """Delete a breakpoint"""
    port = ctx.parent.parent.obj["port"]
    _ensure_server(port)

    try:
        _run(port, "delete_breakpoint", {"breakpoint_id": breakpoint_id})
        click.echo(f"Breakpoint {breakpoint_id} deleted")
    except Exception as e:
        raise click.ClickException(str(e))


# ── Heap introspection subgroup ──────────────────────────────────

def _ensure_runtime_built() -> str:
    """Ensure AppleDBRuntime framework is built, return absolute path."""
    project_root = Path(__file__).parent.parent.parent
    framework_path = project_root / "frameworks" / "AppleDBRuntime.framework" / "AppleDBRuntime"

    if not framework_path.exists():
        build_script = project_root / "AppleDBRuntime" / "build.sh"
        if not build_script.exists():
            raise click.ClickException(
                f"AppleDBRuntime build script not found at {build_script}. "
                "Clone the full repo or run from the project directory."
            )
        click.echo("Building AppleDBRuntime framework...", err=True)
        result = subprocess.run(
            ["bash", str(build_script)],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode != 0:
            raise click.ClickException(f"Failed to build AppleDBRuntime: {result.stderr}")
        click.echo("AppleDBRuntime built successfully", err=True)

    return str(framework_path)


def _heap_eval(port: int, expression: str) -> Any:
    """Load AppleDBRuntime and evaluate an expression, returning parsed JSON."""
    # Build if needed and load with absolute path
    framework_path = _ensure_runtime_built()
    _run(port, "load_framework", {"framework_path": framework_path})
    # Evaluate expression with long timeout for heap walking
    result = _run(port, "evaluate_expression", {
        "expression": expression,
        "language": "objc",
    })
    summary = (result or {}).get("summary", "") or ""
    if summary.startswith('"') and summary.endswith('"'):
        summary = summary[1:-1]
    summary = summary.replace('\\"', '"').replace('\\\\', '\\')
    if not summary:
        return []
    import json as _json
    return _json.loads(summary)


@main.group()
def heap():
    """Heap introspection (requires AppleDBRuntime framework)"""
    pass


@heap.command("summary")
@click.option("--limit", type=int, default=50, help="Max classes to show")
@click.pass_context
def heap_summary(ctx, limit):
    """Show heap class histogram"""
    port = ctx.parent.parent.obj["port"]
    _ensure_server(port)

    try:
        data = _heap_eval(port, "[AppleDBRuntime heapSummary]")
        if not data:
            click.echo("No heap objects found")
            return
        entries = data[:limit] if isinstance(data, list) else []
        click.echo(f"{'Class':<50} {'Count':>8} {'Size':>12}")
        click.echo("-" * 72)
        for entry in entries:
            cls = entry.get("class", "?")
            count = entry.get("count", 0)
            size = entry.get("totalSize", 0)
            if size >= 1_048_576:
                s = f"{size / 1_048_576:.1f} MB"
            elif size >= 1024:
                s = f"{size / 1024:.1f} KB"
            else:
                s = f"{size} B"
            click.echo(f"{cls:<50} {count:>8} {s:>12}")
    except Exception as e:
        raise click.ClickException(str(e))


@heap.command("instances")
@click.argument("class_name")
@click.pass_context
def heap_instances(ctx, class_name):
    """Find all instances of a class on the heap"""
    port = ctx.parent.parent.obj["port"]
    _ensure_server(port)

    try:
        data = _heap_eval(port, f'[AppleDBRuntime instancesOf:@"{class_name}"]')
        if not data:
            click.echo(f"No instances of '{class_name}' found")
            return
        click.echo(f"{len(data)} instance(s) of '{class_name}':")
        for entry in data:
            click.echo(f"  {entry.get('address', '?')}  ({entry.get('size', 0)} bytes)")
    except Exception as e:
        raise click.ClickException(str(e))


@heap.command("describe")
@click.argument("address")
@click.pass_context
def heap_describe(ctx, address):
    """Describe an object at a memory address"""
    port = ctx.parent.parent.obj["port"]
    _ensure_server(port)

    try:
        addr_int = int(address, 16) if address.startswith("0x") else int(address)
        data = _heap_eval(port, f"[AppleDBRuntime describeAddress:{addr_int}]")
        if isinstance(data, dict) and "error" in data:
            click.echo(f"Error: {data['error']}")
            return
        click.echo(f"Object at {data.get('address', address)}")
        click.echo(f"  Class: {data.get('class', '?')} ({data.get('size', 0)} bytes)")
        supers = data.get("superclasses", [])
        if supers:
            click.echo(f"  Inherits: {' > '.join(supers)}")
        ivars = data.get("ivarValues", data.get("ivars", []))
        if ivars:
            click.echo(f"\n  Ivars ({len(ivars)}):")
            for iv in ivars:
                if "class" in iv:
                    click.echo(f"    .{iv.get('name','?')}: {iv['class']} @ {iv.get('address','?')}")
                elif "value" in iv:
                    click.echo(f"    .{iv.get('name','?')}: {iv['value']}")
    except Exception as e:
        raise click.ClickException(str(e))


@heap.command("refs")
@click.argument("address")
@click.pass_context
def heap_refs(ctx, address):
    """Show outbound references from an object"""
    port = ctx.parent.parent.obj["port"]
    _ensure_server(port)

    try:
        addr_int = int(address, 16) if address.startswith("0x") else int(address)
        data = _heap_eval(port, f"[AppleDBRuntime referencesFrom:{addr_int}]")
        if not data:
            click.echo("No outbound references")
            return
        click.echo(f"{len(data)} reference(s):")
        for ref in data:
            click.echo(f"  .{ref.get('ivar','?')} -> {ref.get('class','?')} @ {ref.get('address','?')}")
    except Exception as e:
        raise click.ClickException(str(e))


@heap.command("cycles")
@click.argument("address")
@click.option("--max-depth", type=int, default=10, help="Max search depth")
@click.pass_context
def heap_cycles(ctx, address, max_depth):
    """Detect retain cycles from an object"""
    port = ctx.parent.parent.obj["port"]
    _ensure_server(port)

    try:
        addr_int = int(address, 16) if address.startswith("0x") else int(address)
        data = _heap_eval(port, f"[AppleDBRuntime retainCyclesFrom:{addr_int} maxDepth:{max_depth}]")
        if not data:
            click.echo("No retain cycles detected")
            return
        click.echo(f"{len(data)} retain cycle(s) found:")
        for i, cycle in enumerate(data, 1):
            nodes = cycle.get("cycle", [])
            click.echo(f"\n  Cycle {i}:")
            for j, node in enumerate(nodes):
                prefix = "  -> " if j > 0 else "  "
                click.echo(f"    {prefix}{node}")
    except Exception as e:
        raise click.ClickException(str(e))
