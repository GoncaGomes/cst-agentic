# Controller crash/restart recovery (#17)

Recovery is integrated with the manual runtime, terminal-shared conversation
coordinator, working-project adapter and protected dispatch client. This is offline
implementation evidence, not a complete Controller or live CST release.
`ControllerSession` is separate from the existing
disabled/status-only `verify-connectivity` command. No new model-visible tools,
inventory groups, provider requests or native CST operations are introduced.

Authority: [#17](https://github.com/GoncaGomes/cst-agentic/issues/17), including its
[single-instance/manual-recovery decision](https://github.com/GoncaGomes/cst-agentic/issues/17#issuecomment-6446214034)
and [dedicated-folder/storage requirement](https://github.com/GoncaGomes/cst-agentic/issues/17#issuecomment-6367032475).

## Storage

Default central state is `%LOCALAPPDATA%\CST-Agentic\`:

- `session.lock`: OS byte-range lease on Windows, held through transport cleanup.
  Exclusive first creation and its persistent version header mark that a recovery
  ledger is expected. An existing empty file is incomplete initialization, not first use.
- `recovery.json`: versioned authoritative incident ledger. One atomically
  replaced ledger avoids cross-file incident/index update windows. The issue's
  suggested `recovery/<project-id>.json` layout was illustrative, not required.

Each incident has a unique ID, task ID, bounded operation identifier, known
canonical project/directory and filesystem identity, known non-secret exact
instance identifier, outcome category and human reconciliation findings. Unknown
targets are representable. Raw arguments, tool responses, credentials, raw errors
and human conversation are not saved. Detailed in-memory client attempts remain
separate from durable minimal metadata.

Ledger version 2 retains successive bounded human findings (affected work
identified, effects addressed, continuing activity resolved, previous instance
closed), with `local_human` provenance and `not_independently_verified` limitations.
There is no persisted user prose or editable safety `ok` switch. Version 1 records
remain readable: settled operations stay settled; legacy reconciled records become
pending because they lack instance-closure evidence. The next update writes v2.

Project-local `Project.cst.agentic.json` is reserved for approved decision notes;
this slice neither writes notes nor treats them as safety status or authority.
Different projects may have different parent directories/drives, but each must
have a dedicated existing directory. Creation/opening routes inspect that
directory before transport startup and again before dispatch. Save destinations
are inspected at dispatch. Multiple `.cst` files cause refusal, not automatic
file reorganization. Canonical paths, directory identity and existing file
identity catch casing, directory aliases, movement and hard links.

Moving/deleting notes or moving a directory cannot clear its central incident.
Missing/corrupt expected state and incomplete initialization block admission.
Normal operations must not delete the state directory. Complete external deletion
of all central state cannot be distinguished from first use by this local store;
there is no anti-tamper/backup or power-loss guarantee.

## Application integration

The terminal/model coordinator uses `ControllerSession` as its only Controller
dispatch route. It accepts dependencies for controlled testing:

1. Enter the session to acquire the central lease and validate recovery state.
2. Submit a fresh explicit request with `start_task(project_path, request)`.
   Central recovery admission precedes even client construction. Production
   working-project setup uses [the explicit task adapter](controller-project.md).
3. Dispatch through `dispatch(...)`. The real protected client's synchronous
    final guard rechecks directory/target/technical prerequisites after queueing and writes
   an `in_flight` record with file flush/fsync and atomic replacement. If any
   required check/write fails, no SDK call is made.
4. A trustworthy received response first becomes `received_unresolved`. Only a
   trusted application outcome interpreter returning literal `True` finalizes
   it as `settled`. A received domain failure is not transport uncertainty and
   never establishes rollback merely by its error label. Missing/failed outcome
   interpretation leaves the task paused. SDK failures retain `uncertain` state;
   crashes retain the last unresolved record. Evidence that SDK entry never
   happened permits settlement without claiming a native effect.
5. After healthy settled task completion, `finish_task()` leaves the transport
   and CST alone. Another explicit task for the same project can re-establish
   prerequisites using that healthy connection. Completion does not close CST.
   Switching instance/project routes requires a fresh session in this slice;
   no same-instance project-switch recovery shortcut is implemented.
6. Reconciliation records explicit human findings about affected work identification,
    addressed effects, resolved activity and previous-instance closure. It never resets an old client latch,
   dispatches anything or unpauses the old task. An affected project needs a
   fresh task/session after complete reconciliation.

Trusted integration dependencies are deliberately **not model tools**:

- The approved inventory is application-owned and independently checked.
- `dispatch_check` must validate the actual arguments and
   live target/state prerequisites. It returns typed `DispatchEvidence`,
   including a connection-bound instance identifier, not a cross-restart process proof. Operations
  whose impact is not safely project-scoped, such as an uncertain instance launch,
  must use `project_scoped=False`; their incident cannot be bypassed by selecting
  a different project. A callback returning `None` refuses dispatch.
- No callback can bypass an unresolved central incident.
  New A/B work and replacement transport require explicit local
  human reconciliation, followed by a fresh session/task. The former isolated-B
  exception is superseded; directory separation is not isolation evidence.
- Save operations must supply the actual typed save destination and verify it
    against the canonical arguments in `dispatch_check`. This route refuses Save As
  to a different file instead of inventing an unsupported lifecycle/overwrite
    route. Qwen interprets the fresh request and agreed consequences; recovery
    admission adds no independent semantic consent test.
- `settled` must interpret retained response/domain evidence, not model confidence
  or a bare transport receipt. Failing interpretation retains the incident.
- An explicitly reviewed read-only subset can permit one bounded action-relevant
  `readback(...)` after a received partial-effect failure through the healthy
  client. It does not settle that failure or resume dependent work. No readback,
  status or stop exception exists after uncertainty.

The [working-project adapter](controller-project.md) supplies connection-bound
live target support through a paired typed server protocol. The
[earlier isolation investigation](controller-isolation-evidence.md) is historical,
not an unresolved prerequisite. Missing protocol support still blocks affected
operations. JSON records describe incidents, not the loaded project or solver
state. No automatic recovery/replay, existing-instance attachment or native
experiment authorization is provided.

`ControllerMcpClient` uses public SDK contexts entered/exited in the owning task,
complete startup (including catalogue) and one total cleanup allowance. It captures
server stderr in a local temporary stream rather than forwarding it. Cleanup
failures remain visible alongside the primary error. SDK-shielded cleanup may
overshoot; this is reported rather than described as hard real-time behavior.
The [manual-session production factory](controller-session.md) now supplies
separately validated manual-mode, credential-safe child settings and uses this
central lease/admission before transport construction. It refuses unresolved
incidents until explicit local human reconciliation. Ordinary calls are capped at 120 seconds and the explicit
#24 new-instance launch at 480 seconds. Wait/stop-specific runtime
policy and interactive exit warnings belong to the remaining Controller runtime,
not an implicit live route supplied by these helpers. Newly owned CST instances
remain session-bound; no exit/crash survival promise is made.

## Local reporting and human reconciliation

Exit the old Controller first so it releases the central lease. These commands do
not load endpoint/server configuration, construct transport, call tools or invoke
the model, and are usable while normal Controller startup is blocked:

```powershell
uv run cst-agentic recovery status
uv run cst-agentic recovery reconcile <incident-id>
```

`status` reports retained incidents, known affected project/instance and bounded
human findings, not live CST status. `reconcile` asks four explicit yes/no questions.
Inspect affected work locally, address partial effects, resolve continuing solver
activity, and close the previous CST instance before answering yes. Unknown means
no. Negative findings are recorded and keep admission blocked; interrupted input
does not commit new findings. Repeat for every pending incident. Closing CST or
restarting Windows alone is insufficient. No automatic instance close, file move,
deletion, plan restoration, or tool replay occurs.

After all incidents are reconciled, start a **fresh Controller session** and give
an **explicit new task** with CST initially closed. Normal typed instance-conflict,
exact destination and live-target checks still apply. The old uncertainty latch
is never reset. Missing/corrupt expected central state is not repaired or deleted
by these commands; it remains a storage blocker requiring investigation, not a
way to assert a clean native state. Complete external deletion and hostile edits
are outside this local ledger's anti-tamper guarantees.

## Verification

```powershell
uv run pytest -q
uv run ruff format --check .
uv run ruff check .
uv run pyright
```

Tests exercise actual isolated filesystem writes and OS leases, the protected
client's last-moment guard, write/settlement failures, no-replay/reconciliation,
central A/B refusal and unsafe-route refusal. Controlled public-stdio
peers exercise the new lifecycle wrapper, startup refusal/timeout, cleanup error
retention and an EOF-refusing peer. A disposable whole-application subprocess
exits abruptly after SDK delivery and durable marker observation. A further 22
whole-process abrupt-death cases exercise the actual wrapper with controlled
filesystem/public-SDK boundary instrumentation (`os._exit`, no context unwinding).
Each is followed by a fresh-process admission check and absence-of-replay check:

| Crash window | Restart result |
| --- | --- |
| Exclusive lease creation; header before/after fsync | Blocked: incomplete expected state |
| Initial ledger before/after fsync, before replacement | Blocked: expected ledger missing |
| Initial ledger after replacement | Clean ledger, no replay |
| Preparation before/after fsync, before replacement | Prior clean ledger; no possible SDK entry |
| Preparation after replacement; SDK admission | Blocked: `in_flight` |
| SDK response received; receipt before/after fsync, before replacement | Blocked: `in_flight` |
| Receipt after replacement; trusted interpretation | Blocked: `received_unresolved` |
| Settlement before/after fsync, before final replacement | Blocked: `received_unresolved` |
| Trusted settlement after final replacement | Settled, no replay |

The shared coordinator transition test uses `WorkingProject`'s typed technical
checks and real protected client, not unconditional target-admission callbacks.
It proves uncertainty handoff, old-client refusal, A/B pre-transport refusal,
transport-free partial/complete human findings, fresh explicit setup and no replay.
Focused compound-failure regressions retain the persistence primary plus safe
temporary-file cleanup error, including through the protected guard. Lease contention is
also checked from a fresh process. These are new test peers, not replays of the
consumed #14 prototype/native campaigns.

Evidence categories remain separate:

- **Offline deterministic and controlled subprocess evidence:** automated tests.
- **Endpoint probes:** not run.
- **Configured-model behavioral trials:** not run.
- **Native CST/solver acceptance:** not run; no native recovery claim.

Flush/fsync and atomic replacement are tested for controlled process crashes and
injected write refusal. No power-loss, physical disk-failure, native failure
recovery, universal process-kill, or numerical solver guarantee is established.
