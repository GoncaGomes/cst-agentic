"""Offline tests for the MCP client: discovery, serialization, and attempt records."""

from __future__ import annotations

import asyncio
import json
import time
import traceback
from pathlib import Path
from typing import Any

import pydantic
import pytest
from mcp.client.extension import UnexpectedClaimedResult
from mcp.types import (
    CallToolResult,
    ImageContent,
    ListToolsResult,
    PaginatedRequestParams,
    TextContent,
    Tool,
)
from pydantic import ValidationError as PydanticValidationError

from cst_agentic.mcp_client import (
    ATTEMPT_NOT_DISPATCHED,
    ATTEMPT_PENDING,
    ATTEMPT_RECEIVED,
    ATTEMPT_UNCERTAIN,
    DIAG_BLOCKED_UNCERTAIN,
    DIAG_CANCELLED_AFTER_DISPATCH,
    DIAG_NOT_READY,
    DIAG_QUEUED_CANCELLED,
    DIAG_QUEUED_TIMEOUT,
    DIAG_RECEIVED,
    DIAG_SDK_VALIDATION_FAILURE,
    DIAG_TIMEOUT,
    DIAG_TRANSPORT_FAILURE,
    CstMcpClient,
    McpCallError,
    McpError,
)


def _tool(name: str) -> Tool:
    return Tool(name=name, description=f"desc {name}", input_schema={"type": "object"})


class FakeListSession:
    """Serves a fixed chain of tools/list pages keyed by cursor."""

    def __init__(self, pages: list[dict[str, Any]]) -> None:
        self._pages = pages
        self._by_cursor: dict[str | None, int] = {None: 0}
        for index, page in enumerate(pages):
            cursor = page.get("next_cursor")
            if cursor is not None:
                self._by_cursor[cursor] = index + 1
        self.requested_cursors: list[str | None] = []

    async def list_tools(self, *, params: PaginatedRequestParams | None = None) -> ListToolsResult:
        cursor = params.cursor if params is not None else None
        self.requested_cursors.append(cursor)
        page = self._pages[self._by_cursor[cursor]]
        return ListToolsResult(tools=page["tools"], next_cursor=page.get("next_cursor"))


def _client(tmp_path: Path, request_timeout_s: float = 1.0) -> CstMcpClient:
    return CstMcpClient(
        executable=tmp_path / "s.exe",
        cwd=tmp_path / "cwd",
        env={},
        startup_timeout_s=1.0,
        shutdown_timeout_s=1.0,
        request_timeout_s=request_timeout_s,
    )


@pytest.mark.asyncio
async def test_discovery_follows_pagination(tmp_path: Path) -> None:
    session = FakeListSession(
        [
            {"tools": [_tool("a"), _tool("b")], "next_cursor": "c1"},
            {"tools": [_tool("c")], "next_cursor": None},
        ]
    )
    client = _client(tmp_path)
    client._session = session
    names = await client.discover_tools()
    assert names == ["a", "b", "c"]
    assert session.requested_cursors == [None, "c1"]


@pytest.mark.asyncio
async def test_discovery_single_page(tmp_path: Path) -> None:
    session = FakeListSession([{"tools": [_tool("only")], "next_cursor": None}])
    client = _client(tmp_path)
    client._session = session
    assert await client.discover_tools() == ["only"]
    assert session.requested_cursors == [None]


@pytest.mark.asyncio
async def test_definition_discovery_preserves_canonical_schemas_across_pages(
    tmp_path: Path,
) -> None:
    schema = {
        "type": "object",
        "properties": {
            "size": {"anyOf": [{"type": "number"}, {"type": "string"}]},
            "material": {"type": ["string", "null"], "default": None},
            "enabled": {"type": "boolean", "default": True},
            "points": {"type": "array", "items": {"type": "integer"}},
        },
        "required": ["size"],
    }
    tool = Tool(
        name="shape",
        description="Canonical description",
        input_schema=schema,
        output_schema={"type": "object"},
    )
    session = FakeListSession(
        [
            {"tools": [tool], "next_cursor": "more"},
            {"tools": [_tool("other"), tool], "next_cursor": None},
        ]
    )
    client = _client(tmp_path)
    client._session = session

    definitions = await client.discover_tool_definitions()

    assert [item.name for item in definitions] == ["shape", "other", "shape"]
    assert definitions[0].input_schema == schema
    assert definitions[0].description == "Canonical description"
    assert definitions[0].output_schema == {"type": "object"}
    assert session.requested_cursors == [None, "more"]
    # The returned catalogue must not alias the SDK's mutable schema objects.
    definitions[0].input_schema["required"].append("material")
    assert tool.input_schema["required"] == ["size"]
    assert definitions[2].input_schema["required"] == ["size"]
    assert await client.discover_tools() == ["shape", "other", "shape"]


class FakeCallSession:
    def __init__(self, result: CallToolResult | Exception) -> None:
        self._result = result
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> CallToolResult:
        self.calls.append((name, dict(arguments or {})))
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


class HangSession:
    """A session whose requests block until cancelled (simulates a hung server)."""

    async def list_tools(self, *, params: PaginatedRequestParams | None = None) -> None:
        await asyncio.sleep(3600)

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> None:
        await asyncio.sleep(3600)


@pytest.mark.asyncio
async def test_uncertain_client_refuses_catalogue_refresh_before_sdk_entry(tmp_path):
    class Peer(FakeCallSession):
        listed = False

        async def list_tools(self, **kwargs):
            self.listed = True
            return ListToolsResult(tools=[_tool("cst_connection_status")])

    peer = Peer(RuntimeError("synthetic-private-transport-error"))
    client = _client(tmp_path)
    client._session = peer
    with pytest.raises(McpCallError):
        await client.call_tool("cst_connection_status", {})
    with pytest.raises(McpError, match="uncertain"):
        await client.discover_tool_definitions()
    assert peer.listed is False


class GateCallSession:
    """A session that holds each call body on an event gate.

    Records SDK entries/exits (and the argument snapshot received) so tests
    can coordinate on events instead of wall-clock sleeps. When
    ``fail_after_gate`` is set, the body raises it once the gate opens,
    simulating a post-dispatch failure.
    """

    def __init__(self, result: CallToolResult, *, fail_after_gate: Exception | None = None) -> None:
        self._result = result
        self._fail_after_gate = fail_after_gate
        self.gate = asyncio.Event()
        self.entered: list[str] = []
        self.exited: list[str] = []
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> CallToolResult:
        self.entered.append(name)
        self.calls.append((name, dict(arguments or {})))
        await self.gate.wait()
        if self._fail_after_gate is not None:
            raise self._fail_after_gate
        self.exited.append(name)
        return self._result


async def _wait_until(predicate, timeout: float = 2.0) -> None:
    """Yield control until predicate() is true (event coordination, no sleeps)."""
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() >= deadline:
            raise AssertionError("timed out waiting for test condition")
        await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_discovery_page_timeout_is_bounded_error(tmp_path: Path) -> None:
    client = _client(tmp_path, request_timeout_s=0.05)
    client._session = HangSession()
    with pytest.raises(McpError, match="timed out"):
        await client.discover_tools()


@pytest.mark.asyncio
async def test_call_tool_timeout_is_bounded_error(tmp_path: Path) -> None:
    bound = 0.05
    client = _client(tmp_path, request_timeout_s=bound)
    client._session = HangSession()
    with pytest.raises(McpCallError, match="timed out") as excinfo:
        await client.call_tool("cst_connection_status", {})
    # The timeout is identified without echoing the configured bound.
    assert f"{bound:g}" not in str(excinfo.value)
    # A timed-out call is not recorded as a call.
    assert client.calls == []
    (attempt,) = client.attempts
    assert attempt.state == ATTEMPT_UNCERTAIN
    assert attempt.diagnostic == DIAG_TIMEOUT
    assert attempt.dispatched is True
    # The client is latched: later dispatches are blocked before the SDK.
    with pytest.raises(McpCallError, match="uncertain"):
        await client.call_tool("cst_connection_status", {})
    assert client.attempts[1].state == ATTEMPT_NOT_DISPATCHED
    assert client.attempts[1].diagnostic == DIAG_BLOCKED_UNCERTAIN


def _text_result(payload: dict[str, Any], is_error: bool = False) -> CallToolResult:
    return CallToolResult(
        content=[TextContent(type="text", text=json.dumps(payload))], is_error=is_error
    )


@pytest.mark.asyncio
async def test_call_tool_records_success(tmp_path: Path) -> None:
    session = FakeCallSession(_text_result({"mode": "offline", "project_open": False}))
    client = _client(tmp_path)
    client._session = session
    record = await client.call_tool("cst_connection_status", {})
    assert record.name == "cst_connection_status"
    assert record.arguments == {}
    assert record.is_error is False
    assert record.payload == {"mode": "offline", "project_open": False}
    assert client.calls == [record]
    assert session.calls == [("cst_connection_status", {})]
    (attempt,) = client.attempts
    assert attempt.state == ATTEMPT_RECEIVED
    assert attempt.diagnostic == DIAG_RECEIVED
    assert attempt.dispatched is True
    assert attempt.result is record
    assert attempt.ended_monotonic is not None
    assert attempt.started_monotonic <= attempt.ended_monotonic


@pytest.mark.asyncio
async def test_call_retains_all_content_and_structured_evidence(tmp_path: Path) -> None:
    result = CallToolResult(
        content=[
            TextContent(type="text", text='{"status": "updated"}'),
            TextContent(type="text", text="Rebuild failed after results were deleted."),
            ImageContent(type="image", data="AA==", mime_type="image/png"),
        ],
        structured_content={"deleted_results": True, "rebuilt": False},
        is_error=True,
    )
    client = _client(tmp_path)
    client._session = FakeCallSession(result)

    record = await client.call_tool("edit", {})

    assert record.text == '{"status": "updated"}'
    assert record.payload == {"status": "updated"}
    assert record.is_error is True
    assert record.content == result.content
    assert record.structured_content == {"deleted_results": True, "rebuilt": False}
    assert record.evidence_complete is True
    second = result.content[1]
    assert isinstance(second, TextContent)
    second.text = "changed"
    result.structured_content["deleted_results"] = False
    recorded_second = record.content[1]
    assert isinstance(recorded_second, TextContent)
    assert recorded_second.text == "Rebuild failed after results were deleted."
    assert record.structured_content is not None
    assert record.structured_content["deleted_results"] is True
    assert client.attempts[0].state == ATTEMPT_RECEIVED


@pytest.mark.asyncio
async def test_call_tool_records_payload_error_without_raising(tmp_path: Path) -> None:
    session = FakeCallSession(_text_result({"status": "error", "message": "no"}, is_error=True))
    client = _client(tmp_path)
    client._session = session
    record = await client.call_tool("cst_connection_status", {})
    assert record.is_error is True
    assert record.payload == {"status": "error", "message": "no"}
    assert len(client.calls) == 1
    # A received error response is not uncertainty: the client stays usable.
    assert client.attempts[0].state == ATTEMPT_RECEIVED
    assert client.attempts[0].result is record
    second = await client.call_tool("cst_connection_status", {})
    assert second.is_error is True
    assert len(client.attempts) == 2
    assert all(a.state == ATTEMPT_RECEIVED for a in client.attempts)


@pytest.mark.asyncio
async def test_call_tool_transport_failure_raises(tmp_path: Path) -> None:
    session = FakeCallSession(RuntimeError("boom"))
    client = _client(tmp_path)
    client._session = session
    with pytest.raises(McpCallError):
        await client.call_tool("cst_connection_status", {})
    # A transport failure is not recorded as a successful call.
    assert client.calls == []
    (attempt,) = client.attempts
    assert attempt.state == ATTEMPT_UNCERTAIN
    assert attempt.diagnostic == DIAG_TRANSPORT_FAILURE
    assert attempt.dispatched is True


@pytest.mark.asyncio
async def test_call_tool_without_session_is_not_dispatched_and_keeps_client_usable(
    tmp_path: Path,
) -> None:
    client = _client(tmp_path)
    assert client._session is None
    with pytest.raises(McpCallError, match="no active MCP session"):
        await client.call_tool("first", {})

    (attempt,) = client.attempts
    assert attempt.state == ATTEMPT_NOT_DISPATCHED
    assert attempt.diagnostic == DIAG_NOT_READY
    assert attempt.dispatched is False
    assert attempt.result is None
    assert client.calls == []

    # Pre-session use is not uncertainty: the client is not poisoned, and a
    # later legitimate call with a live session is dispatched normally.
    client._session = FakeCallSession(_text_result({"ok": True}))
    record = await client.call_tool("second", {})
    assert record.name == "second"
    assert [a.state for a in client.attempts] == [
        ATTEMPT_NOT_DISPATCHED,
        ATTEMPT_RECEIVED,
    ]


@pytest.mark.asyncio
async def test_call_tool_serializes_concurrent_calls(tmp_path: Path) -> None:
    session = GateCallSession(_text_result({"ok": True}))
    client = _client(tmp_path, request_timeout_s=5.0)
    client._session = session

    first = asyncio.create_task(client.call_tool("first", {}))
    await _wait_until(lambda: session.entered == ["first"])
    second = asyncio.create_task(client.call_tool("second", {}))
    await _wait_until(
        lambda: len(client.attempts) == 2 and client.attempts[1].state == ATTEMPT_PENDING
    )
    # The queued caller must not reach the SDK while the first call is active.
    assert session.entered == ["first"]
    session.gate.set()
    records = await asyncio.gather(first, second)

    assert [r.name for r in records] == ["first", "second"]
    assert session.entered == ["first", "second"]
    assert session.exited == ["first", "second"]
    assert client.calls == records
    for attempt, record in zip(client.attempts, records, strict=True):
        assert attempt.state == ATTEMPT_RECEIVED
        assert attempt.diagnostic == DIAG_RECEIVED
        assert attempt.result is record


@pytest.mark.asyncio
async def test_call_tool_queue_timeout_records_not_dispatched_and_stays_usable(
    tmp_path: Path,
) -> None:
    session = GateCallSession(_text_result({"ok": True}))
    client = _client(tmp_path, request_timeout_s=5.0)
    client._session = session

    first = asyncio.create_task(client.call_tool("first", {}))
    await _wait_until(lambda: session.entered == ["first"])
    # Shrink the bound before the queued caller enters: its deadline then
    # expires while the first call still holds the lock.
    client.request_timeout_s = 0.1
    second = asyncio.create_task(client.call_tool("second", {}))
    with pytest.raises(McpCallError, match="not dispatched"):
        await second

    second_attempt = client.attempts[1]
    assert second_attempt.state == ATTEMPT_NOT_DISPATCHED
    assert second_attempt.diagnostic == DIAG_QUEUED_TIMEOUT
    assert second_attempt.dispatched is False
    assert second_attempt.result is None
    assert session.entered == ["first"]

    # No uncertainty was introduced: the client remains usable.
    session.gate.set()
    await first
    client.request_timeout_s = 5.0
    record = await client.call_tool("third", {})
    assert record.name == "third"
    assert [a.state for a in client.attempts] == [
        ATTEMPT_RECEIVED,
        ATTEMPT_NOT_DISPATCHED,
        ATTEMPT_RECEIVED,
    ]


@pytest.mark.asyncio
async def test_per_call_allowance_expires_in_queue_without_cancelling_active_call(
    tmp_path: Path,
) -> None:
    session = GateCallSession(_text_result({"ok": True}))
    client = _client(tmp_path, request_timeout_s=5.0)
    client._session = session
    first = asyncio.create_task(client.call_tool("launch", {}))
    await _wait_until(lambda: session.entered == ["launch"])
    try:
        with pytest.raises(McpCallError, match="not dispatched"):
            await client.call_tool("stop", {}, timeout_s=0.05)
        assert not first.done()
        assert session.entered == ["launch"]
        assert client.request_timeout_s == 5.0
        assert client.attempts[1].state == ATTEMPT_NOT_DISPATCHED
        assert client.attempts[1].diagnostic == DIAG_QUEUED_TIMEOUT
    finally:
        session.gate.set()
        await first
    assert (await client.call_tool("status", {})).payload == {"ok": True}


@pytest.mark.asyncio
async def test_final_guard_rechecks_changed_prerequisites_after_queueing(tmp_path: Path) -> None:
    session = GateCallSession(_text_result({"ok": True}))
    client = _client(tmp_path, request_timeout_s=5.0)
    client._session = session
    target_current = True
    observations: list[bool] = []

    def guard() -> bool:
        observations.append(target_current)
        return target_current

    first = asyncio.create_task(client.call_tool("first", {}))
    await _wait_until(lambda: session.entered == ["first"])
    queued = asyncio.create_task(client.call_tool("edit", {}, dispatch_guard=guard))
    try:
        await _wait_until(lambda: len(client.attempts) == 2)
        assert observations == []
        target_current = False
        session.gate.set()
        await first
        with pytest.raises(McpCallError, match="guard"):
            await queued
    finally:
        session.gate.set()
        await asyncio.gather(first, queued, return_exceptions=True)

    assert observations == [False]
    assert session.entered == ["first"]
    assert client.attempts[1].state == ATTEMPT_NOT_DISPATCHED
    assert client.attempts[1].diagnostic == "guard_rejected"
    assert client.attempts[1].dispatched is False
    target_current = True
    assert (await client.call_tool("edit", {}, dispatch_guard=guard)).payload == {"ok": True}


@pytest.mark.asyncio
async def test_call_tool_queue_cancellation_records_not_dispatched_and_stays_usable(
    tmp_path: Path,
) -> None:
    session = GateCallSession(_text_result({"ok": True}))
    client = _client(tmp_path, request_timeout_s=5.0)
    client._session = session

    first = asyncio.create_task(client.call_tool("first", {}))
    await _wait_until(lambda: session.entered == ["first"])
    second = asyncio.create_task(client.call_tool("second", {}))
    await _wait_until(
        lambda: len(client.attempts) == 2 and client.attempts[1].state == ATTEMPT_PENDING
    )

    second.cancel()
    with pytest.raises(asyncio.CancelledError):
        await second

    assert client.attempts[1].state == ATTEMPT_NOT_DISPATCHED
    assert client.attempts[1].diagnostic == DIAG_QUEUED_CANCELLED
    assert client.attempts[1].dispatched is False
    assert session.entered == ["first"]

    # Cancellation in the queue does not poison the client.
    session.gate.set()
    await first
    record = await client.call_tool("third", {})
    assert record.name == "third"
    assert [a.state for a in client.attempts] == [
        ATTEMPT_RECEIVED,
        ATTEMPT_NOT_DISPATCHED,
        ATTEMPT_RECEIVED,
    ]


@pytest.mark.asyncio
async def test_call_tool_cancellation_after_dispatch_is_uncertain_and_blocks_later_calls(
    tmp_path: Path,
) -> None:
    session = GateCallSession(_text_result({"ok": True}))
    client = _client(tmp_path, request_timeout_s=5.0)
    client._session = session

    task = asyncio.create_task(client.call_tool("first", {}))
    await _wait_until(lambda: session.entered == ["first"])
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    (attempt,) = client.attempts
    assert attempt.state == ATTEMPT_UNCERTAIN
    assert attempt.diagnostic == DIAG_CANCELLED_AFTER_DISPATCH
    assert attempt.dispatched is True
    assert client.calls == []

    with pytest.raises(McpCallError, match="uncertain"):
        await client.call_tool("second", {})
    assert client.attempts[1].state == ATTEMPT_NOT_DISPATCHED
    assert client.attempts[1].diagnostic == DIAG_BLOCKED_UNCERTAIN
    assert session.entered == ["first"]


@pytest.mark.asyncio
async def test_uncertain_attempt_blocks_caller_already_queued(tmp_path: Path) -> None:
    session = GateCallSession(_text_result({"ok": True}), fail_after_gate=RuntimeError("boom"))
    client = _client(tmp_path, request_timeout_s=5.0)
    client._session = session

    first = asyncio.create_task(client.call_tool("first", {}))
    await _wait_until(lambda: session.entered == ["first"])
    second = asyncio.create_task(client.call_tool("second", {}))
    await _wait_until(
        lambda: len(client.attempts) == 2 and client.attempts[1].state == ATTEMPT_PENDING
    )
    session.gate.set()
    with pytest.raises(McpCallError):
        await first
    with pytest.raises(McpCallError, match="uncertain"):
        await second

    assert client.attempts[0].state == ATTEMPT_UNCERTAIN
    assert client.attempts[0].diagnostic == DIAG_TRANSPORT_FAILURE
    assert client.attempts[1].state == ATTEMPT_NOT_DISPATCHED
    assert client.attempts[1].diagnostic == DIAG_BLOCKED_UNCERTAIN
    # The blocked queued caller never touched the SDK.
    assert session.entered == ["first"]
    assert client.calls == []


@pytest.mark.asyncio
async def test_call_tool_transport_failure_is_not_replayed(tmp_path: Path) -> None:
    session = FakeCallSession(RuntimeError("boom"))
    client = _client(tmp_path)
    client._session = session
    with pytest.raises(McpCallError):
        await client.call_tool("first", {})

    # Exactly one underlying invocation; no replay occurs.
    assert session.calls == [("first", {})]
    with pytest.raises(McpCallError, match="uncertain"):
        await client.call_tool("second", {})
    assert session.calls == [("first", {})]
    assert client.attempts[1].state == ATTEMPT_NOT_DISPATCHED
    assert client.attempts[1].diagnostic == DIAG_BLOCKED_UNCERTAIN
    assert client.calls == []


# A deliberately fake sensitive value used to prove that failure output never
# carries the raw SDK exception text. It is not a real credential or endpoint.
# It stays under pydantic's input truncation window so it appears verbatim in
# the formatted ValidationError text (keeping the leak test meaningful).
_FAKE_SENSITIVE = "https://fake-sentinel.example/t=FAKE-9f3d"


def _assert_not_leaked(text: str) -> None:
    # The failure message does not echo the sentinel, so a failing check does
    # not print it either.
    assert _FAKE_SENSITIVE not in text, "the fake sensitive sentinel leaked into failure output"


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["discover_tools", "discover_tool_definitions"])
async def test_catalogue_failure_does_not_expose_raw_sdk_error(tmp_path: Path, method: str) -> None:
    class FailingListSession:
        async def list_tools(self, *, params: PaginatedRequestParams | None = None) -> None:
            raise RuntimeError(_FAKE_SENSITIVE)

    client = _client(tmp_path)
    client._session = FailingListSession()
    with pytest.raises(McpError):
        try:
            await getattr(client, method)()
        except McpError:
            _assert_not_leaked(traceback.format_exc())
            raise


def _pydantic_validation_error(value: Any = "not-an-int") -> PydanticValidationError:
    class _Strict(pydantic.BaseModel):
        value: int

    try:
        _Strict(value=value)
    except PydanticValidationError as exc:
        return exc
    raise AssertionError("expected a pydantic ValidationError")


@pytest.mark.asyncio
async def test_call_tool_sdk_validation_failure_is_uncertain(tmp_path: Path) -> None:
    session = FakeCallSession(_pydantic_validation_error())
    client = _client(tmp_path)
    client._session = session
    with pytest.raises(McpCallError):
        await client.call_tool("first", {})
    (attempt,) = client.attempts
    assert attempt.state == ATTEMPT_UNCERTAIN
    assert attempt.diagnostic == DIAG_SDK_VALIDATION_FAILURE
    assert client.calls == []


@pytest.mark.asyncio
async def test_call_tool_claimed_result_is_sdk_validation_failure(tmp_path: Path) -> None:
    claimed = UnexpectedClaimedResult(CallToolResult(content=[], is_error=False))
    session = FakeCallSession(claimed)
    client = _client(tmp_path)
    client._session = session
    with pytest.raises(McpCallError):
        await client.call_tool("first", {})
    (attempt,) = client.attempts
    assert attempt.state == ATTEMPT_UNCERTAIN
    assert attempt.diagnostic == DIAG_SDK_VALIDATION_FAILURE


@pytest.mark.asyncio
async def test_call_tool_transport_failure_does_not_leak_raw_exception(tmp_path: Path) -> None:
    session = FakeCallSession(RuntimeError(f"connect failed at {_FAKE_SENSITIVE}"))
    client = _client(tmp_path)
    client._session = session
    try:
        await client.call_tool("first", {})
        raise AssertionError("expected McpCallError")
    except McpCallError as error:
        _assert_not_leaked(str(error))
        # An ordinary formatted traceback must not carry the original
        # exception text either.
        _assert_not_leaked(traceback.format_exc())

    (attempt,) = client.attempts
    assert attempt.state == ATTEMPT_UNCERTAIN
    assert attempt.diagnostic == DIAG_TRANSPORT_FAILURE
    assert client.calls == []


@pytest.mark.asyncio
async def test_call_tool_sdk_validation_failure_does_not_leak_raw_exception(
    tmp_path: Path,
) -> None:
    original = _pydantic_validation_error(_FAKE_SENSITIVE)
    # Precondition: the test is meaningful only if the original exception
    # text really contains the sentinel.
    assert _FAKE_SENSITIVE in str(original)
    session = FakeCallSession(original)
    client = _client(tmp_path)
    client._session = session
    try:
        await client.call_tool("first", {})
        raise AssertionError("expected McpCallError")
    except McpCallError as error:
        _assert_not_leaked(str(error))
        _assert_not_leaked(traceback.format_exc())

    (attempt,) = client.attempts
    assert attempt.state == ATTEMPT_UNCERTAIN
    assert attempt.diagnostic == DIAG_SDK_VALIDATION_FAILURE
    assert client.calls == []


@pytest.mark.asyncio
async def test_call_tool_arguments_are_snapshotted_before_await(tmp_path: Path) -> None:
    session = GateCallSession(_text_result({"ok": True}))
    client = _client(tmp_path, request_timeout_s=5.0)
    client._session = session
    arguments = {"tool": "first", "count": 1}
    task = asyncio.create_task(client.call_tool("first", arguments))
    await _wait_until(lambda: session.entered == ["first"])

    # Mutate the caller's mapping while the call is in flight.
    arguments["tool"] = "mutated"
    arguments["extra"] = 99
    session.gate.set()
    record = await task

    assert record.arguments == {"tool": "first", "count": 1}
    assert client.attempts[0].arguments == {"tool": "first", "count": 1}
    # The SDK received the snapshot, not the later mutation.
    assert session.calls == [("first", {"tool": "first", "count": 1})]


@pytest.mark.asyncio
async def test_call_tool_freezes_nested_arguments_against_queued_mutation(
    tmp_path: Path,
) -> None:
    session = GateCallSession(_text_result({"ok": True}))
    client = _client(tmp_path, request_timeout_s=5.0)
    client._session = session
    arguments = {
        "top": "original",
        "nested": {"inner": "original", "count": 1},
        "items": ["a", "b"],
    }
    task = asyncio.create_task(client.call_tool("first", arguments))
    await _wait_until(lambda: session.entered == ["first"])

    # Mutate the caller's arguments at every depth after admission, while the
    # call is in flight.
    arguments["top"] = "mutated"
    arguments["nested"]["inner"] = "mutated"
    arguments["nested"]["count"] = 99
    arguments["items"][0] = "z"
    arguments["items"].append("extra")
    session.gate.set()
    record = await task

    admitted = {
        "top": "original",
        "nested": {"inner": "original", "count": 1},
        "items": ["a", "b"],
    }
    assert record.arguments == admitted
    assert client.attempts[0].arguments == admitted
    # The SDK received the admitted frozen values, not the later mutation.
    assert session.calls == [("first", admitted)]
    # The caller's own mapping is fully mutated.
    assert arguments["top"] == "mutated"
    assert arguments["nested"] == {"inner": "mutated", "count": 99}
    assert arguments["items"] == ["z", "b", "extra"]


@pytest.mark.asyncio
async def test_call_tool_rejects_invalid_bound_before_dispatch(tmp_path: Path) -> None:
    session = FakeCallSession(_text_result({"ok": True}))
    client = _client(tmp_path)
    client._session = session
    client.request_timeout_s = 0.0
    with pytest.raises(ValueError):
        await client.call_tool("first", {})
    client.request_timeout_s = float("inf")
    with pytest.raises(ValueError):
        await client.call_tool("first", {})
    assert client.attempts == []
    assert session.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("bound", [0, -1, float("inf"), float("nan"), True, "120"])
async def test_invalid_per_call_allowance_is_rejected_before_admission(
    tmp_path: Path,
    bound: Any,
) -> None:
    session = FakeCallSession(_text_result({"ok": True}))
    client = _client(tmp_path)
    client._session = session
    with pytest.raises(ValueError):
        await client.call_tool("edit", {}, timeout_s=bound)
    assert client.attempts == []
    assert session.calls == []


@pytest.mark.asyncio
async def test_final_guard_does_not_yield_before_dispatch_marker(tmp_path: Path) -> None:
    client = _client(tmp_path)
    client._session = FakeCallSession(_text_result({"ok": True}))
    observations: list[bool] = []

    def guard() -> bool:
        asyncio.get_running_loop().call_soon(
            lambda: observations.append(client.attempts[0].dispatched)
        )
        return True

    await client.call_tool("edit", {}, dispatch_guard=guard)
    await asyncio.sleep(0)
    assert observations == [True]


@pytest.mark.asyncio
@pytest.mark.parametrize("behavior", ["exception", "async", "truthy"])
async def test_failed_or_invalid_guard_fails_closed_without_poisoning_client(
    tmp_path: Path,
    behavior: str,
) -> None:
    session = FakeCallSession(_text_result({"ok": True}))
    client = _client(tmp_path)
    client._session = session

    async def async_guard() -> bool:
        raise AssertionError("an asynchronous guard must not run")

    def guard() -> Any:
        if behavior == "exception":
            raise RuntimeError(_FAKE_SENSITIVE)
        if behavior == "async":
            return async_guard()
        return "yes"

    with pytest.raises(McpCallError, match="guard"):
        try:
            await client.call_tool("edit", {}, dispatch_guard=guard)
        except McpCallError:
            _assert_not_leaked(traceback.format_exc())
            raise
    assert session.calls == []
    assert client.attempts[0].state == ATTEMPT_NOT_DISPATCHED
    assert client.attempts[0].diagnostic == "guard_failed"
    assert (await client.call_tool("status", {})).payload == {"ok": True}


@pytest.mark.asyncio
async def test_guard_time_counts_against_allowance_before_sdk_entry(tmp_path: Path) -> None:
    session = FakeCallSession(_text_result({"ok": True}))
    client = _client(tmp_path)
    client._session = session

    def guard() -> bool:
        time.sleep(0.06)
        return True

    with pytest.raises(McpCallError, match="not dispatched"):
        await client.call_tool("edit", {}, timeout_s=0.03, dispatch_guard=guard)
    assert session.calls == []
    assert client.attempts[0].diagnostic == DIAG_QUEUED_TIMEOUT
    assert (await client.call_tool("status", {})).payload == {"ok": True}


@pytest.mark.asyncio
@pytest.mark.parametrize("name", ["cst_connection_status", "cst_stop_simulation"])
async def test_new_call_options_cannot_bypass_uncertainty(tmp_path: Path, name: str) -> None:
    session = FakeCallSession(RuntimeError("transport failed"))
    client = _client(tmp_path)
    client._session = session
    with pytest.raises(McpCallError):
        await client.call_tool("edit", {})
    guard_ran = False

    def guard() -> bool:
        nonlocal guard_ran
        guard_ran = True
        return True

    with pytest.raises(McpCallError, match="uncertain"):
        await client.call_tool(name, {}, timeout_s=10, dispatch_guard=guard)
    assert guard_ran is False
    assert session.calls == [("edit", {})]
    assert client.attempts[-1].diagnostic == DIAG_BLOCKED_UNCERTAIN


def test_client_rejects_invalid_request_bound_at_construction(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        _client(tmp_path, request_timeout_s=-1.0)
    with pytest.raises(ValueError):
        _client(tmp_path, request_timeout_s=float("inf"))
