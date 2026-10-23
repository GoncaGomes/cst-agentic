# Application-owned conversation coordinator (#19)

`ConversationCoordinator.submit(...)` is the shared interface for terminal input
and deterministic tests. It accepts text, `UserMessage` (including explicit new
objectives) and `ControlIntent`, and returns a settled reply or input pause with
progress/outcome/incident events. The terminal preserves message casing and owns
only input/output and abnormal-input cleanup. Help, historical status, continue,
stop-simulation intent and exit confirmation are coordinator behavior. There is
no separate mid-task cancel command. Ctrl+C remains abnormal interruption.

## Model requests and execution

Dependencies are the SDK `Model`, recovery-aware `ControllerSession`, the same
authoritative `RecoveryStore`, reviewed canonical tool definitions, independent
execution allowlist, trusted response interpreters, request-admission adapter and
monotonic clock. Tests substitute the external model/peer/clock boundaries while
using the actual session, protected client and isolated durable store.

The coordinator directly calls public `Model.get_response` with
`ModelTracing.DISABLED`; no Runner executes tools. Every request explicitly
includes trusted instructions, current requested scope, provenance-labelled
historical response evidence and paired history. Tool descriptions/results,
model prose and future remembered choices do not grant authority. Native
`FunctionTool` definitions retain canonical optionality/defaults/unions/nullability
with strict conversion disabled. Their SDK invoke handler refuses execution.

Complete responses retain a detached originating schema snapshot. The sole
conversation gateway preflights the whole batch: completed calls, nonempty unique
unreused call identifiers, originating visibility, independent allowlist, strict
JSON object parsing and canonical JSON Schema validation. Invalid batches have
no effects. Trustworthy IDs receive matched rejected/skipped outcomes; missing,
conflicting or reused IDs cause a protocol pause without replaying broken output
or inventing IDs. Unsupported/incomplete output never enters replay history.
Discovery calls never pass through MCP; their dedicated adapter belongs to #20,
and discovery batches remain refused until it is implemented.

Ordinary calls execute sequentially only via `ControllerSession.dispatch`.
The session's final synchronous guard rechecks admission after queueing, along
with the existing target/authorization/recovery checks and durable preparation.
Missing trusted interpretation, domain failure, transport uncertainty and durable
settlement failure pause dependent work. Earlier effects and all trustworthy
call/result pairs survive. Full received content blocks and structured content
remain detached in memory, including when settlement persistence fails. No
error category implies rollback. Abnormal caller cancellation retains uncertain
and skipped pairs and then propagates to lifecycle cleanup, preserving any
simultaneous persistence failure in its original exception aggregate. Malformed
response projections produce matched bounded failure data while keeping full
received evidence in memory and pausing dependent work. Repetition comparison
normalizes JSON object key order.

Scoped admission remains the session's responsibility. An unresolved incident in
A does not impose a second global gate over an independently admitted isolated B
route. Controlled tests retain A's incident while admitting synthetic B evidence;
production still has no isolation adapter and remains blocked.

Each complete model request is bounded by at most 120 seconds (a smaller injected
allowance is supported). The production provider retains `max_retries=0`.
Autonomous admission stops after 30 requests, 20 minutes, or three repeated
non-monitoring operation/results without progress. Admission is rechecked at
actual dispatch; admitted native work is allowed to settle. Waiting at a user
prompt is excluded, and explicit user continuation starts a new work period.
These bounds neither authorize a retry after uncertainty nor stop a solver.

## Production prerequisites remain blocked

The production factory now supplies this same coordinator. It does **not** install
unconditional request-admission, target-evidence or outcome-settlement callbacks.
Until reviewed discovery (#20), bounded context (#21), configured endpoint
validation (#23) and live target support (#24) are available, the terminal reports
the missing prerequisites before a model request or tool dispatch. It still
starts the manual-mode transport under the existing lease and recovery admission,
so running the production command is not an offline validation command.

The narrower scripted status conversation uses explicitly controlled schemas,
synthetic typed target evidence and an interpreter for the controlled peer's
offline response. This proves coordinator integration, not live target identity,
native capability or readiness of the complete Controller. The actual public
stdio wrapper is also exercised with a separate local peer that never imports
CST or requests the institutional endpoint.

Progressive selection/reset/refresh, endpoint context counting and compaction,
decision memory, native status/stop interpretation, operation-specific simulation
policy, and the positive isolated-project recovery route remain their owning
tickets' work. #17 still owns integrated recovery acceptance. No new model-visible
inventory/group is activated in production. The disabled/status-only connectivity
command and its SDK Runner path remain unchanged.

## Verification

Offline checks use `uv run pytest -q`, `uv run pyright`,
`uv run ruff format --check .`, and `uv run ruff check .`.
`tests/test_conversation.py` covers the shared coordinator, thin terminal wiring,
canonical snapshots, malformed batches and ID history, work limits, persistence
refusal, domain/transport/settlement failure, central incident handoff, final
queued admission, abnormal cancellation, and the actual public stdio path.

Evidence categories:

- Offline deterministic/local controlled-peer evidence: automated tests.
- Institutional endpoint probes: not run.
- Configured-model behavioral trials: not run.
- Native CST, solver and live-isolation acceptance: not run.

No connected experiment, native mutation or recovery bypass is authorized or
demonstrated by this implementation.
