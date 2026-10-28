"""Recovery-aware Controller seam, separate from the connectivity command.

This is the safety/lifecycle slice, not a conversational model loop. Trusted
application adapters supply reviewed inventory, technical live-target checks
and outcome interpretation. Missing live support refuses work;
model text, project notes and recovery JSON cannot implement these checks.
"""

from __future__ import annotations

import asyncio
import sys
import tempfile
import uuid
from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TextIO, cast

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import Tool

from .mcp_client import CstMcpClient, McpAttempt, McpStartupError, McpToolCall, _validate_timeout
from .project_storage import ProjectLocation
from .recovery import RecoveryError, RecoveryStore
from .working_project import WorkingProject


@dataclass(frozen=True)
class DispatchEvidence:
    """Trusted checks established scope and a non-secret session instance identity.

    ``instance_id`` is connection-bound, not a cross-restart Windows identity proof.
    Unknown-scope operations such as launching an instance use project_scoped=False.
    This data comes from a trusted typed adapter, never model/user assertions.
    """

    instance_id: str | None
    project_scoped: bool = True


@dataclass
class ControllerMcpClient(CstMcpClient):
    """Public SDK contexts enter/exit in one owner task, with visible failures.

    Startup includes stdio, session, initialize and complete catalogue discovery.
    Cleanup has one total allowance, not a fresh budget for each context. SDK
    shielded cleanup may overshoot; report that instead of claiming hard real
    time. The legacy connectivity lifecycle remains unchanged.
    """

    catalogue_admission: Callable[[list[Tool]], None] | None = None
    cleanup_deadline: float | None = None

    async def __aenter__(self) -> ControllerMcpClient:
        _validate_timeout(self.startup_timeout_s)
        _validate_timeout(self.shutdown_timeout_s)
        self._owner = asyncio.current_task()
        # On Windows tempfile annotates its file-like wrapper separately, but
        # it implements the text stream/fileno interface the public SDK needs.
        self._stderr = cast(TextIO, tempfile.TemporaryFile(mode="w+", encoding="utf-8"))
        params = StdioServerParameters(
            command=str(self.executable), args=[], env=dict(self.env), cwd=str(self.cwd)
        )
        try:
            async with asyncio.timeout(self.startup_timeout_s):
                transport = stdio_client(params, errlog=self._stderr)
                read, write = await transport.__aenter__()
                self._stdio_cm = transport
                session = ClientSession(read, write)
                self._session = await session.__aenter__()
                self._session_cm = session
                init = await self._session.initialize()
                self.server_name = init.server_info.name
                self.server_version = init.server_info.version
                self.instructions = init.instructions
                self.catalogue = await self.discover_tool_definitions()
                if self.catalogue_admission is not None:
                    self.catalogue_admission(self.catalogue)
        except BaseException as error:
            primary = (
                error
                if isinstance(error, asyncio.CancelledError)
                else McpStartupError("Controller startup failed or exceeded its allowance.")
            )
            try:
                await self._aclose()
            except BaseException as cleanup:
                raise BaseExceptionGroup(
                    "Controller startup and cleanup failed", [primary, cleanup]
                ) from None
            raise primary from None
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        try:
            await self._aclose()
        except BaseException as cleanup:
            if exc is not None:
                raise BaseExceptionGroup(
                    "Controller work and cleanup failed", [exc, cleanup]
                ) from None
            raise
        return False

    async def _aclose(self) -> None:
        if asyncio.current_task() is not self._owner:
            raise RecoveryError("Controller transport must close in its lifecycle owner task.")
        errors: list[BaseException] = []
        loop = asyncio.get_running_loop()
        deadline = (
            self.cleanup_deadline
            if self.cleanup_deadline is not None
            else loop.time() + self.shutdown_timeout_s
        )
        for attribute in ("_session_cm", "_stdio_cm"):
            context = getattr(self, attribute)
            if context is not None:
                try:
                    # Do not inject native asyncio cancellation into public SDK
                    # context unwinding. In particular an already-expired timer
                    # can interrupt ClientSession's cancel-scope exit and leave
                    # the outer stdio exit hung. The SDK bounds its own process
                    # shutdown waits; report a shared-allowance overrun below.
                    await context.__aexit__(None, None, None)
                except BaseException:
                    errors.append(RecoveryError("Controller SDK context cleanup failed."))
                finally:
                    setattr(self, attribute, None)
        self._session = None
        self._stderr.close()
        if loop.time() > deadline:
            errors.append(RecoveryError("Controller total cleanup allowance exceeded."))
        if errors:
            raise BaseExceptionGroup("Controller cleanup failed", errors)


class ControllerSession:
    """Explicit tasks, one lifecycle owner, no restoration or automatic replay.

    An uncertain client requires a fresh session after reconciliation. The store's
    OS lease outlives the transport, so competing sessions cannot enter while
    startup/dispatch/cleanup is pending. In production the client factory must
    construct a manual-mode ControllerMcpClient with reviewed child settings.

    Every unresolved central incident blocks new work/replacement transport.
    """

    def __init__(
        self,
        store: RecoveryStore,
        client_factory: Callable[[], CstMcpClient],
        *,
        inventory: frozenset[str],
        dispatch_check: Callable[
            [ProjectLocation | None, str, Mapping[str, Any]], DispatchEvidence | None
        ],
        readback_inventory: frozenset[str] = frozenset(),
        working_project: WorkingProject | None = None,
    ) -> None:
        self.store = store
        self._factory = client_factory
        self._inventory = inventory
        self._dispatch_check = dispatch_check
        self.working_project = working_project
        if not readback_inventory <= inventory:
            raise RecoveryError("Readback operations must belong to the approved inventory.")
        self._readback_inventory = readback_inventory
        self._readback_used = False
        self._client: CstMcpClient | None = None
        self._project: ProjectLocation | None = None
        self._task_id: str | None = None
        self._task_complete = False
        self._entered = False
        self._spent = False
        self._paused = False
        self._closing = False
        self._dispatch_lock = asyncio.Lock()

    async def __aenter__(self) -> ControllerSession:
        if self._entered or self._spent:
            raise RecoveryError("Start a fresh Controller session for a fresh task.")
        self._lease_context = self.store.session()
        self._lease_context.__enter__()
        self._entered = True
        self._owner = asyncio.current_task()
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        if asyncio.current_task() is not self._owner:
            raise RecoveryError("Controller session must exit in its lifecycle owner task.")
        self._closing = True
        try:
            async with self._dispatch_lock:
                if self._client is not None:
                    await self._client.__aexit__(exc_type, exc, tb)
        finally:
            self._entered = False
            self._spent = True
            # If transport cleanup raised an aggregate, retain that aggregate
            # (not just the original body exception) through lease cleanup too.
            current = sys.exception()
            self._lease_context.__exit__(
                type(current) if current is not None else exc_type,
                current if current is not None else exc,
                current.__traceback__ if current is not None else tb,
            )
        return False

    def _check_route(self, *, readback: bool = False) -> None:
        incidents = tuple(
            record
            for record in self.store.incidents(unresolved_only=True)
            if not (
                readback
                and record.task_id == self._task_id
                and record.state == "received_unresolved"
            )
        )
        if incidents:
            raise RecoveryError("Unresolved central incident requires local human reconciliation.")

    async def start_task(self, project_path: Path, explicit_request: str) -> None:
        """Called only for a fresh explicit human request; never restored prose.

        Directory inspection is not a live CST readback. Dispatch still requires
        an independent technical target check at actual SDK admission.
        """
        if (
            not self._entered
            or self._closing
            or (self._task_id is not None and not self._task_complete)
            or asyncio.current_task() is not self._owner
        ):
            raise RecoveryError("A fresh task in the lifecycle owner is required.")
        if not isinstance(explicit_request, str) or not explicit_request.strip():
            raise RecoveryError("A fresh explicit task is required.")
        project = ProjectLocation.inspect(project_path)
        self._check_route()  # Must precede even construction of a transport.
        if (
            self._client is not None
            and self._project is not None
            and (
                project.path != self._project.path
                or project.directory_id != self._project.directory_id
            )
        ):
            raise RecoveryError("A different instance/project route requires a fresh session.")
        self._task_id = str(uuid.uuid4())
        self._task_complete = False
        self._readback_used = False
        self._project = project
        await self._open_client()

    async def _open_client(self) -> None:
        if self._client is None:
            client = self._factory()
            await client.__aenter__()
            self._client = client

    async def open_manual_transport(self) -> None:
        """Open a disconnected manual session, without inventing a project route.

        This route refuses every unresolved incident before constructing the client.
        No task or dispatch authorization is created by opening the transport.
        """
        if not self._entered or self._closing or asyncio.current_task() is not self._owner:
            raise RecoveryError("Manual startup requires the active lifecycle owner.")
        if self.store.incidents(unresolved_only=True):
            raise RecoveryError("Unresolved recovery requires explicit local human reconciliation.")
        await self._open_client()

    def begin_cleanup(self, deadline: float) -> None:
        """Revoke new work and share the provider's deadline without exposing SDK dispatch."""
        if (
            not self._entered
            or asyncio.current_task() is not self._owner
            or not isinstance(self._client, ControllerMcpClient)
        ):
            raise RecoveryError("Cleanup requires the active Controller lifecycle owner.")
        self._closing = True
        self._client.cleanup_deadline = deadline

    def finish_task(self) -> None:
        """Completion does not close CST, release the lease or start another task."""
        if (
            not self._entered
            or self._task_id is None
            or self._paused
            or self._dispatch_lock.locked()
            or any(r.task_id == self._task_id for r in self.store.incidents(unresolved_only=True))
        ):
            raise RecoveryError("Task cannot complete with pending or unresolved work.")
        self._task_complete = True

    @property
    def attempts(self) -> tuple[McpAttempt, ...]:
        """Detached admission/receipt evidence, without exposing a dispatch bypass."""
        return tuple(deepcopy(self._client.attempts)) if self._client is not None else ()

    @property
    def catalogue(self) -> tuple[Tool, ...]:
        """Detached canonical startup definitions, never a dispatch handle."""
        return tuple(deepcopy(self._client.catalogue)) if self._client is not None else ()

    async def refresh_catalogue(self) -> tuple[Tool, ...]:
        """Read definitions only at a settled, healthy lifecycle-owner boundary."""
        if (
            not self._entered
            or self._closing
            or self._paused
            or self._client is None
            or self._dispatch_lock.locked()
            or asyncio.current_task() is not self._owner
        ):
            raise RecoveryError("Catalogue refresh requires a settled healthy lifecycle owner.")
        async with self._dispatch_lock:
            async with asyncio.timeout(120):
                tools = await self._client.discover_tool_definitions()
            self._client.catalogue = deepcopy(tools)
            return tuple(deepcopy(tools))

    @property
    def paused(self) -> bool:
        """A received unresolved outcome or uncertain attempt requires a handoff."""
        return self._paused

    async def dispatch(
        self,
        name: str,
        arguments: Mapping[str, Any] | None,
        *,
        timeout_s: float = 120,
        settled: Callable[[McpToolCall], bool] | None = None,
        save_destination: Path | None = None,
        admission_check: Callable[[], bool] | None = None,
    ) -> McpToolCall:
        """Dispatch through the real protected client's final synchronous guard.

        ``settled`` is trusted application interpretation, never a model claim.
        Without it even a received response remains unresolved. Errors/partial
        effects are not transport uncertainty; they pause this task. Save routes
        retain technical destination checks; Qwen owns user agreement. No raw
        arguments enter the recovery ledger.
        """
        return await self._dispatch(
            name,
            arguments,
            timeout_s=timeout_s,
            settled=settled,
            save_destination=save_destination,
            readback=False,
            admission_check=admission_check,
        )

    async def readback(
        self,
        name: str,
        arguments: Mapping[str, Any] | None,
        *,
        settled: Callable[[McpToolCall], bool],
        timeout_s: float = 120,
    ) -> McpToolCall:
        """One bounded observation after a received, possibly partial failure.

        Only independently reviewed read-only operations qualify. This never
        resolves the failed operation, resumes dependent work or bypasses an
        uncertain client. Further recovery needs human guidance.
        """
        return await self._dispatch(
            name,
            arguments,
            timeout_s=timeout_s,
            settled=settled,
            save_destination=None,
            readback=True,
            admission_check=None,
        )

    async def _dispatch(
        self,
        name: str,
        arguments: Mapping[str, Any] | None,
        *,
        timeout_s: float,
        settled: Callable[[McpToolCall], bool] | None,
        save_destination: Path | None,
        readback: bool,
        admission_check: Callable[[], bool] | None,
    ) -> McpToolCall:
        if self.working_project is not None and self.working_project.stage == "unselected":
            if name != "cst_connection_status" or arguments:
                raise RecoveryError("Check connection status before explicit new-instance launch.")
            if not self._entered or self._closing or self._paused:
                raise RecoveryError("A healthy active Controller session is required.")
            self._check_route()
            self.working_project.launch()
            self._task_id = str(uuid.uuid4())
            self._task_complete = False
            await self._open_client()
        if (
            self.working_project is not None
            and name in {"cst_create_project", "cst_open_project"}
            and self.working_project.stage == "connection"
        ):
            if self._dispatch_lock.locked() or self._paused or self._closing:
                raise RecoveryError("Project selection requires a settled healthy session.")
            self._check_route()
            self._project = self.working_project.select(name, dict(arguments or {}))
        if (
            not self._entered
            or self._closing
            or self._client is None
            or self._task_id is None
            or self._task_complete
        ):
            raise RecoveryError("No explicit Controller task is ready.")
        if name not in self._inventory:
            raise RecoveryError("Operation is outside the approved Controller inventory.")
        _validate_timeout(timeout_s)
        maximum = (
            480
            if self.working_project is not None
            and self.working_project.stage == "launch"
            and name == "cst_connect"
            else 120
        )
        if timeout_s > maximum:
            raise RecoveryError(
                "This safety slice only admits ordinary allowances up to 120 seconds."
            )
        client, project, task_id = self._client, self._project, self._task_id
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout_s
        frozen_arguments = deepcopy(dict(arguments or {}))
        metadata = self.working_project.metadata() if self.working_project is not None else None
        try:
            async with asyncio.timeout_at(deadline):
                await self._dispatch_lock.acquire()
        except TimeoutError:
            raise RecoveryError(
                "Operation was not dispatched: queue-inclusive allowance expired."
            ) from None
        try:
            if self._task_id != task_id or self._task_complete or self._closing:
                raise RecoveryError("Queued operation no longer belongs to an active task.")
            if readback:
                own = tuple(
                    r for r in self.store.incidents(unresolved_only=True) if r.task_id == task_id
                )
                if (
                    not self._paused
                    or self._readback_used
                    or name not in self._readback_inventory
                    or not own
                    or any(r.state != "received_unresolved" for r in own)
                ):
                    raise RecoveryError("Bounded healthy-client readback is unavailable.")
                self._readback_used = True
            elif self._paused:
                raise RecoveryError(
                    "Task is paused; reconciliation requires a fresh explicit task."
                )
            incident_id: str | None = None

            def guard() -> bool:
                nonlocal incident_id
                if self._closing or not self._entered or name not in self._inventory:
                    return False
                if admission_check is not None and admission_check() is not True:
                    return False
                if self._task_id != task_id or self._task_complete or self._client is not client:
                    return False
                if self.working_project is not None and not self.working_project.admits(
                    project, name, frozen_arguments, metadata
                ):
                    return False
                current = ProjectLocation.inspect(Path(project.path)) if project else None
                if project is not None and current is not None:
                    if current.directory_id != project.directory_id or (
                        project.file_id is not None and current.file_id != project.file_id
                    ):
                        return False
                self._check_route(readback=readback)
                if save_destination is not None:
                    destination = ProjectLocation.inspect(save_destination)
                    if current is None or destination.path != current.path:
                        # Cross-project Save As needs its own reviewed route; never
                        # silently turn a save into a second project or overwrite.
                        return False
                evidence = self._dispatch_check(current, name, deepcopy(frozen_arguments))
                if (
                    not isinstance(evidence, DispatchEvidence)
                    or type(evidence.project_scoped) is not bool
                ):
                    return False
                if any(
                    record.instance_id == evidence.instance_id
                    and record.instance_id is not None
                    and not (
                        readback
                        and record.task_id == task_id
                        and record.state == "received_unresolved"
                    )
                    for record in self.store.incidents(unresolved_only=True)
                ):
                    return False
                incident_id = self.store.prepare(
                    task_id,
                    name,
                    current if evidence.project_scoped else None,
                    evidence.instance_id,
                )
                return True

            attempt_index = len(client.attempts)
            try:
                remaining = deadline - loop.time()
                if remaining <= 0:
                    raise RecoveryError("Operation was not dispatched: allowance expired.")
                result = await client.call_tool(
                    name,
                    frozen_arguments,
                    timeout_s=remaining,
                    dispatch_guard=guard,
                    controller_metadata=metadata,
                )
            except BaseException as primary:
                attempt = (
                    client.attempts[attempt_index] if len(client.attempts) > attempt_index else None
                )
                if incident_id is not None:
                    assert attempt is not None
                    self._paused = readback or attempt.dispatched
                    try:
                        self.store.finish(
                            incident_id, "uncertain" if attempt.dispatched else "settled"
                        )
                    except BaseException as persistence:
                        raise BaseExceptionGroup(
                            "Dispatch and recovery persistence failed", [primary, persistence]
                        ) from None
                if (
                    attempt is not None
                    and attempt.state == "not_dispatched"
                    and self.working_project is not None
                    and self.working_project.selection_not_dispatched(metadata)
                ):
                    self._project = None
                raise
            if incident_id is None:
                raise RecoveryError("Client did not enforce durable dispatch admission.")
            # First persist receipt, retaining the requirement if interpretation
            # raises, returns false, or process death happens during settlement.
            self._paused = True
            self.store.finish(incident_id, "received_unresolved")
            target_valid = self.working_project is None or self.working_project.accept(result)
            if target_valid and settled is not None and settled(result) is True:
                self.store.finish(incident_id, "settled")
                self._paused = readback
            return result
        finally:
            self._dispatch_lock.release()
