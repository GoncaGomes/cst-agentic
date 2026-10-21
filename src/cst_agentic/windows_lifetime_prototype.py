"""THROWAWAY, OFFLINE ONLY. Eight observations; no CST/provider configuration.

Run with uv run --offline --no-sync python <this-file>.
Companion HTML is a hand-driven illustration, not evidence of native behavior.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

HERE = Path(__file__).resolve()
PROJECT = Path.cwd()
UV = shutil.which("uv")
NAMES = ("begin", "work", "wait", "launch", "stop", "status", "close")
SCHEMA = {"type": "object", "properties": {}, "additionalProperties": False}


def durable_write(path: Path, value: dict) -> None:
    temporary = path.with_suffix(".writing")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(value, stream)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def fake_server(scratch: Path, mode: str) -> None:
    """Tiny, deliberately synchronous JSON-RPC peer; all payloads are synthetic."""
    child = None
    for line in sys.stdin:
        request = json.loads(line)
        method = request.get("method")
        if "id" not in request:
            continue
        if method == "initialize":
            if mode == "startup_timeout":
                time.sleep(2)
            result = {
                "protocolVersion": request["params"]["protocolVersion"],
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "OFFLINE-LIFETIME-PROTOTYPE", "version": "0"},
            }
        elif method == "tools/list":
            result = {
                "tools": [
                    {"name": name, "description": "Synthetic only", "inputSchema": SCHEMA}
                    for name in NAMES
                ]
            }
        elif method == "tools/call":
            name = request["params"]["name"]
            with (scratch / "server-calls.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(json.dumps({"name": name}) + "\n")
            value = {"synthetic": True, "name": name}
            if name == "begin":
                child = subprocess.Popen(
                    [
                        "powershell.exe",
                        "-NoProfile",
                        "-NonInteractive",
                        "-File",
                        str(HERE.with_name("windows_lifetime_fake_child.ps1")),
                        str(scratch),
                    ],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                deadline = time.monotonic() + 8
                while not (scratch / "child-ready.json").exists():
                    if child.poll() is not None or time.monotonic() >= deadline:
                        raise RuntimeError("fake_child_startup_failed")
                    time.sleep(0.02)
                # The child closes the file before this parse; retry no operation.
                value.update(json.loads((scratch / "child-ready.json").read_text("utf-8-sig")))
            elif name in ("work", "wait", "launch"):
                time.sleep({"work": 0.6, "wait": 0.6, "launch": 0.9}[name])
            elif name in ("stop", "close"):
                (scratch / "child-stop.flag").touch()
                value["request_accepted"] = True
                # Stop acceptance deliberately does not wait for termination.
                if name == "close" and child:
                    child.wait(timeout=3)
            elif name == "status":
                value["child_running"] = child is not None and child.poll() is None
            else:
                raise RuntimeError("unknown_fake_tool")
            result = {"content": [{"type": "text", "text": json.dumps(value)}], "isError": False}
        elif method == "ping":
            result = {}
        else:
            raise RuntimeError("unexpected_fake_method")
        print(json.dumps({"jsonrpc": "2.0", "id": request["id"], "result": result}), flush=True)


if len(sys.argv) > 1 and sys.argv[1] == "--server":
    fake_server(Path(sys.argv[2]), sys.argv[3])
    sys.exit(0)
if len(sys.argv) > 1 and sys.argv[1] == "--crash-marker":
    durable_write(Path(sys.argv[2]), {"state": "in_flight", "target": "synthetic-only"})
    os._exit(23)  # Deliberately exits ONLY this disposable helper.

import anyio  # noqa: E402
import win32api  # noqa: E402
import win32con  # noqa: E402
import win32event  # noqa: E402
from agents import FunctionTool, ItemHelpers, ModelSettings, set_tracing_disabled  # noqa: E402
from agents.items import ModelResponse  # noqa: E402
from agents.models.interface import Model, ModelTracing  # noqa: E402
from agents.usage import Usage  # noqa: E402
from mcp import ClientSession, StdioServerParameters  # noqa: E402
from mcp.client.stdio import get_default_environment, stdio_client  # noqa: E402
from openai.types.responses import ResponseFunctionToolCall  # noqa: E402

set_tracing_disabled(True)
# A fake peer cannot emit secrets; nevertheless never forward SDK/server errors.
logging.disable(logging.CRITICAL)


def uv_command(*args: str) -> list[str]:
    if UV is None:
        raise RuntimeError("uv_missing")
    return [
        UV,
        "run",
        "--offline",
        "--no-sync",
        "--project",
        str(PROJECT),
        "python",
        str(HERE),
        *args,
    ]


def child_environment() -> dict[str, str]:
    # Only SDK-default Windows execution variables plus the existing venv.
    # No .env loading, arbitrary inherited variables, or provider initialization.
    return get_default_environment() | {"UV_PROJECT_ENVIRONMENT": sys.prefix, "UV_OFFLINE": "1"}


def process_handle(pid: int):
    # Hold a handle to this exact fake child across teardown; PID reuse is irrelevant.
    return win32api.OpenProcess(win32con.SYNCHRONIZE, False, pid)


def is_running(handle) -> bool:
    return win32event.WaitForSingleObject(handle, 0) == win32event.WAIT_TIMEOUT


class ScriptedModel(Model):
    async def get_response(self, **kwargs):
        if kwargs["tracing"] != ModelTracing.DISABLED:
            raise RuntimeError("tracing_must_be_disabled")
        return ModelResponse(
            output=[
                ResponseFunctionToolCall(
                    type="function_call",
                    name="work",
                    arguments="{}",
                    call_id=f"fake-{i}",
                )
                for i in range(2)
            ],
            usage=Usage(),
            response_id=None,
        )

    def stream_response(self, *args, **kwargs):
        raise NotImplementedError("offline_nonstreaming_only")


class GuardedFakeDispatch:
    """Only tools/call path. Not a replacement for the real protected client.

    Fixed fake inventory + empty schemas, synthetic target only, same-task SDK
    ownership, serialized dispatch, last-moment authorization, persistent marker,
    queue-inclusive deadline and permanent uncertainty latch. No real-tool support.
    """

    def __init__(self, session, scratch):
        self.session = session
        self.scratch = scratch
        self.marker = scratch / "central-recovery.json"
        self.recovery_required = self.marker.exists()
        self.lock = anyio.Lock()
        self.authorized = True
        self.uncertain = False
        self.dispatched = anyio.Event()
        self.attempts = []

    async def call(self, name, allowance=4):
        attempt = {"name": name, "admitted": time.monotonic(), "state": "not_dispatched"}
        self.attempts.append(attempt)
        entered = False
        try:
            with anyio.fail_after(allowance):
                async with self.lock:
                    if self.uncertain or self.recovery_required:
                        attempt["reason"] = "reconciliation_required"
                        return attempt
                    if name not in NAMES or (not self.authorized and name != "stop"):
                        attempt["reason"] = "permission_or_inventory"
                        return attempt
                    durable_write(
                        self.marker,
                        {"state": "in_flight", "operation": name, "target": "synthetic-only"},
                    )
                    # No await between final guard/marker and SDK entry.
                    entered = True
                    attempt["dispatch"] = time.monotonic()
                    self.dispatched.set()
                    response = await self.session.call_tool(name, {})
                    attempt["value"] = json.loads(response.content[0].text)
                    attempt["state"] = "received"
                    durable_write(self.marker, {"state": "settled", "operation": name})
                    self.marker.unlink()
        except BaseException as error:
            if entered:
                self.uncertain = True
                attempt["state"] = "uncertain"
            attempt["reason"] = type(error).__name__
            if not isinstance(error, TimeoutError):
                raise
        finally:
            attempt["settled"] = time.monotonic()
            attempt["total_s"] = round(attempt["settled"] - attempt["admitted"], 4)
            if "dispatch" in attempt:
                attempt["queue_s"] = round(attempt["dispatch"] - attempt["admitted"], 4)
        return attempt


async def forbidden_automatic_execution(*args):
    raise RuntimeError("automatic_sdk_execution_forbidden")


async def observe_case(name: str, root: Path) -> dict:
    scratch = root / name
    scratch.mkdir()
    observation = {"name": name, "synthetic_only": True}
    handle = None
    start = time.monotonic()
    cleanup_start = None
    command = uv_command("--server", str(scratch), name)
    params = StdioServerParameters(command=command[0], args=command[1:], env=child_environment())
    # This scope is OUTSIDE both SDK task groups and is entered/exited by their
    # single owner task. Never wrap __aenter__/__aexit__ in asyncio.wait_for.
    startup_budget = 1.5 if name == "startup_timeout" else 15
    try:
        with anyio.fail_after(startup_budget) as lifecycle:
            with open(os.devnull, "w") as stderr:
                async with stdio_client(params, errlog=stderr) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        catalogue = await session.list_tools()
                        observation["startup_s"] = round(time.monotonic() - start, 4)
                        lifecycle.deadline = float("inf")
                        gateway = GuardedFakeDispatch(session, scratch)
                        try:
                            if name in ("leave_open", "authorized_close", "stop_after_wait"):
                                child = await gateway.call("begin")
                                handle = process_handle(child["value"]["pid"])
                                observation["in_any_job"] = child["value"]["in_any_job"]
                                observation["child_alive_before"] = is_running(handle)
                            if name == "authorized_close":
                                await gateway.call("close")
                                observation["child_alive_before_teardown"] = is_running(handle)
                            elif name == "cancel_batch":
                                model = ScriptedModel()
                                tools = [
                                    FunctionTool(
                                        name=tool.name,
                                        description=tool.description or "",
                                        params_json_schema=tool.input_schema,
                                        on_invoke_tool=forbidden_automatic_execution,
                                        strict_json_schema=False,
                                    )
                                    for tool in catalogue.tools
                                ]
                                response = await model.get_response(
                                    system_instructions="OFFLINE ONLY",
                                    input=[],
                                    model_settings=ModelSettings(),
                                    tools=tools,
                                    output_schema=None,
                                    handoffs=[],
                                    tracing=ModelTracing.DISABLED,
                                    previous_response_id=None,
                                    conversation_id=None,
                                    prompt=None,
                                )
                                replay = response.to_input_items()

                                async def cancel_command():
                                    await gateway.dispatched.wait()
                                    await anyio.sleep(0.1)
                                    gateway.authorized = False
                                    observation["cancel_received"] = time.monotonic()

                                async with anyio.create_task_group() as controls:
                                    controls.start_soon(cancel_command)
                                    # Frozen synthetic batch preflight, before any dispatch.
                                    if len({c.call_id for c in response.output}) != 2 or any(
                                        c.name not in NAMES or c.arguments != "{}"
                                        for c in response.output
                                    ):
                                        raise RuntimeError("fake_batch_invalid")
                                    for call in response.output:
                                        outcome = await gateway.call(call.name)
                                        replay.append(
                                            ItemHelpers.tool_call_output_item(
                                                call,
                                                json.dumps({"state": outcome["state"]}),
                                            )
                                        )
                                observation["matched_output_ids"] = [
                                    item["call_id"]
                                    for item in replay
                                    if item.get("type") == "function_call_output"
                                ]
                            elif name in ("stop_after_wait", "stop_budget_exhausted"):
                                gateway.dispatched = anyio.Event()
                                current = "wait" if name == "stop_after_wait" else "launch"

                                async def stop_command():
                                    await gateway.dispatched.wait()
                                    await anyio.sleep(0.1)
                                    observation["stop_intent"] = time.monotonic()
                                    # Explicit stop intent, never inferred from cancel.
                                    await gateway.call(
                                        "stop", allowance=(2 if name == "stop_after_wait" else 0.25)
                                    )

                                async with anyio.create_task_group() as controls:
                                    controls.start_soon(stop_command)
                                    await gateway.call(current)
                                if name == "stop_after_wait":
                                    # Independent OS-handle observation is NOT stop acceptance.
                                    with anyio.fail_after(3):
                                        while is_running(handle):
                                            await anyio.sleep(0.01)
                                    observation["termination_observed"] = time.monotonic()
                                    observation["status_after_stop"] = (
                                        await gateway.call("status")
                                    )["value"]
                            elif name == "uncertain_latch":
                                await gateway.call("work", allowance=0.15)
                                await gateway.call("status")
                                await gateway.call("stop")
                                observation["recovery_marker_retained"] = gateway.marker.exists()
                            elif name == "crash_restart":
                                completed = await anyio.run_process(
                                    uv_command("--crash-marker", str(gateway.marker)),
                                    env=child_environment(),
                                    check=False,
                                )
                                observation["helper_exit"] = completed.returncode
                                if completed.returncode != 23:
                                    raise RuntimeError("unexpected_crash_helper_exit")
                                gateway = GuardedFakeDispatch(session, scratch)
                                observation["restart_recovery_required"] = gateway.recovery_required
                                await gateway.call("status")
                            observation["attempts"] = gateway.attempts
                        finally:
                            cleanup_start = time.monotonic()
                            # One total allowance, with both context exits in owner task.
                            lifecycle.deadline = cleanup_start + 30
        observation["startup_cancelled"] = False
    except TimeoutError:
        if name != "startup_timeout":
            raise
        observation["startup_cancelled"] = True
        observation["startup_and_cleanup_s"] = round(time.monotonic() - start, 4)
    finally:
        observation["total_s"] = round(time.monotonic() - start, 4)
        if cleanup_start is not None:
            observation["cleanup_s"] = round(time.monotonic() - cleanup_start, 4)
        if handle:
            observation["child_alive_after_teardown"] = is_running(handle)
            handle.Close()
        calls = scratch / "server-calls.jsonl"
        observation["actual_server_calls"] = (
            [json.loads(line)["name"] for line in calls.read_text("utf-8").splitlines()]
            if calls.exists()
            else []
        )
    return observation


async def main():
    from importlib.metadata import version

    root = Path(r"C:\Users\Lenovo\AppData\Local\Temp\opencode") / (
        "cst-lifetime-evidence-" + uuid.uuid4().hex[:8]
    )
    root.mkdir()
    report = {
        "scope": "OFFLINE ONLY: no CST, solver, provider or endpoint requests",
        "versions": {name: version(name) for name in ("mcp", "openai-agents", "anyio")},
        "cases": [],
    }
    names = (
        "leave_open",
        "authorized_close",
        "startup_timeout",
        "cancel_batch",
        "stop_after_wait",
        "stop_budget_exhausted",
        "uncertain_latch",
        "crash_restart",
    )
    started = time.monotonic()
    try:
        with anyio.fail_after(15 * 60):
            for name in names:
                try:
                    result = await observe_case(name, root)
                except BaseException as error:
                    # No raw exceptions or suppressed cleanup success; stop this round.
                    report["cases"].append({"name": name, "error_type": type(error).__name__})
                    raise
                report["cases"].append(result)
                print(json.dumps(result), flush=True)
    finally:
        report["elapsed_s"] = round(time.monotonic() - started, 4)
        durable_write(root / "observations.json", report)
        print("Evidence: " + str(root / "observations.json"), flush=True)


if __name__ == "__main__":
    try:
        anyio.run(main)
    except BaseException as error:
        print("Round stopped: " + type(error).__name__, flush=True)
        sys.exit(1)
