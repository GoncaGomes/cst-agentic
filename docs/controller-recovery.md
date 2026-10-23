# Controller recovery safety slice (#17)

This implements a recovery-aware application seam, not the complete conversational
Controller or a live CST release. `ControllerSession` is separate from the existing
disabled/status-only `verify-connectivity` command. No new model-visible tools,
inventory groups, provider requests or native CST operations are introduced.

Authority: [#17](https://github.com/GoncaGomes/cst-agentic/issues/17), including its
[project-isolation amendment](https://github.com/GoncaGomes/cst-agentic/issues/17#issuecomment-6366676070)
and [dedicated-folder/storage requirement](https://github.com/GoncaGomes/cst-agentic/issues/17#issuecomment-6367032475).

## Storage

Default central state is `%LOCALAPPDATA%\CST-Agentic\`:

- `session.lock`: OS byte-range lease on Windows, held through transport cleanup.
  Its persistent version header also marks that a recovery ledger is expected.
- `recovery.json`: versioned authoritative incident ledger. One atomically
  replaced ledger avoids cross-file incident/index update windows. The issue's
  suggested `recovery/<project-id>.json` layout was illustrative, not required.

Each incident has a unique ID, task ID, bounded operation identifier, known
canonical project/directory and filesystem identity, known non-secret exact
instance identifier, outcome category and human reconciliation flags. Unknown
targets are representable. Raw arguments, tool responses, credentials, raw errors
and human conversation are not saved. Detailed in-memory client attempts remain
separate from durable minimal metadata.

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

The terminal/model coordinator should use `ControllerSession` as its only
Controller dispatch route. It accepts dependencies for controlled testing:

1. Enter the session to acquire the central lease and validate recovery state.
2. Submit a fresh explicit request with `start_task(project_path, request)`.
   Recovery/isolation admission precedes even client construction.
3. Dispatch through `dispatch(...)`. The real protected client's synchronous
   final guard rechecks directory/target/authorization after queueing and writes
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
6. Reconciliation records explicit human findings about project identification,
   resolved effects and resolved activity. It never resets an old client latch,
   dispatches anything or unpauses the old task. An affected project needs a
   fresh task/session after complete reconciliation.

Trusted integration dependencies are deliberately **not model tools**:

- The approved inventory is application-owned and independently checked.
- `dispatch_check` must validate the actual arguments, task authorization and
  independent live target/state prerequisites. It returns typed `DispatchEvidence`,
  including an exact instance identifier that distinguishes PID reuse. Operations
  whose impact is not safely project-scoped, such as an uncertain instance launch,
  must use `project_scoped=False`; their incident cannot be bypassed by selecting
  a different project. A callback returning `None` refuses dispatch.
- `isolation_check` must establish the proposed new-instance route's independence
  from every remaining incident, including continuing activity and affected files.
  It runs before transport startup and again at dispatch. Without this dependency,
  any other unresolved incident refuses admission. Known overlapping files,
  directories, unknown targets/instances and shared instance identity cannot be
  overridden merely by returning `True`.
- Save operations must supply the actual typed save destination and verify it
  against the canonical arguments in `dispatch_check`. This slice refuses Save As
  to a different file instead of inventing an unsupported lifecycle/overwrite
  route. File inspection alone cannot authorize saving or overwriting.
- `settled` must interpret retained response/domain evidence, not model confidence
  or a bare transport receipt. Failing interpretation retains the incident.
- An explicitly reviewed read-only subset can permit one bounded action-relevant
  `readback(...)` after a received partial-effect failure through the healthy
  client. It does not settle that failure or resume dependent work. No readback,
  status or stop exception exists after uncertainty.

There are **no production live identity/isolation adapters in this checkout**.
Do not wire arbitrary `True` callbacks into a live Controller. The tests use
controlled synthetic evidence; missing typed server readbacks remain affected
capability blockers. JSON records tell us about recorded incidents, not which
project is actually loaded or whether CST is idle. No automatic recovery/replay,
existing-instance attachment or new native authorization is provided.

`ControllerMcpClient` uses public SDK contexts entered/exited in the owning task,
complete startup (including catalogue) and one total cleanup allowance. It captures
server stderr in a local temporary stream rather than forwarding it. Cleanup
failures remain visible alongside the primary error. SDK-shielded cleanup may
overshoot; this is reported rather than described as hard real-time behavior.
The [manual-session production factory](controller-session.md) now supplies
separately validated manual-mode, credential-safe child settings and uses this
central lease/admission before transport construction. It refuses unresolved
routes until production typed isolation evidence is available; this does not
complete #17 or its allowed isolated B-route requirement.
It admits ordinary calls up to 120 seconds; launch/wait/stop-specific runtime
policy and interactive exit warnings belong to the remaining Controller runtime,
not an implicit live route supplied by these helpers. Newly owned CST instances
remain session-bound; no exit/crash survival promise is made.

## Verification

```powershell
uv run pytest -q
uv run ruff format --check .
uv run ruff check .
uv run pyright
```

Tests exercise actual isolated filesystem writes and OS leases, the protected
client's last-moment guard, write/settlement failures, no-replay/reconciliation,
independent-project admission and unsafe-route refusal. Controlled public-stdio
peers exercise the new lifecycle wrapper, startup refusal/timeout, cleanup error
retention and an EOF-refusing peer. A disposable whole-application subprocess
exits abruptly after SDK delivery and durable marker observation; a separate
fresh process refuses restart before client construction. Lease contention is
also checked from a fresh process. These are new test peers, not replays of the
consumed #14 prototype/native campaigns.

Evidence categories remain separate:

- **Offline deterministic and controlled subprocess evidence:** automated tests.
- **Endpoint probes:** not run.
- **Configured-model behavioral trials:** not run.
- **Native CST/isolation/solver acceptance:** not run; live adapters unavailable.

Flush/fsync and atomic replacement are tested for controlled process crashes and
injected write refusal. No power-loss, physical disk-failure, native failure
recovery, universal process-kill, or numerical solver guarantee is established.
