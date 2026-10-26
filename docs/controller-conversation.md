# Application-owned conversation coordinator (#19 / #20)

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
Discovery calls never pass through MCP. The catalogue/selection adapter now
implements [#9's final resolution](https://github.com/GoncaGomes/cst-agentic/issues/9#issuecomment-6301794077)
through this same coordinator, not the historical discovery proposal.

The existing SDK output-schema seam carries a small typed `ConversationDecision`
with `text` and nullable `new_objective`. Questions and replies use `text`; only
a validated, nonempty `new_objective` establishes a separate conversational
objective. This is structured response data, not another callable tool. Invalid,
conflicting or duplicate-key decisions pause before effects. Endpoint acceptance
of this response format remains part of #23; production admission stays blocked.

## Progressive discovery

`ToolDiscovery` accepts a detached canonical MCP catalogue. The exact eighteen
operational groups cover seventy-two eligible unique MCP tools. Startup exposes
exactly `cst_connection_status`, `cst_project_info` and application-owned
`discover_tools`. Every selection replaces the entire group set, deduplicates
startup/overlap, and enforces sixteen active unique functions. Invalid arguments,
unknown groups, missing/unsupported canonical schemas or excess counts preserve
the prior selection and return matched, concrete explanations. A discovery batch
must contain one discovery call and nothing else; mixed/multiple-discovery batches
have no effects or selection changes. Accepted definitions activate on the next
internal request, with complete prior paired history and no extra user go-ahead.

`GROUP_CATALOGUE` owns each group's operational purpose and membership together.
The initial and subsequent system instructions include all eighteen identifiers,
membership counts computed from those members, and the approved capability
qualifications. Full canonical argument schemas remain in active function
definitions rather than prompt prose. The reviewed implementation request amends
#9's baseline by adding `cst_delete_parameter` to `parameters` (four members) and
`cst_delete_material` to `materials_basic` (seven members). These are the only
inventory additions. Parameter/material deletion remains hidden until selection
and subject to the same independent visibility, inventory, canonical argument,
authorization, target and uncertainty checks. Discovery grants no permission.
Component/solid deletion remains outside this inventory.

Canonical schemas are passed unchanged with strict conversion disabled. Local
validation supports the reviewed JSON Schema dialects and local JSON-pointer
references. Unsupported assertions, dialects or reference scopes fail activation;
they are never silently removed or narrowed. Endpoint acceptance is a separate gate.
The gateway independently intersects its execution allowlist with the approved
inventory and rechecks originating definitions/inventory at final dispatch
admission. Selection never grants target, consequence or execution permission.

Ordinary follow-ups reach the model unchanged with the relevant history and
current selection. The model interprets continuation, clarification and separate
objectives, and asks a normal conversational question when the boundary is
genuinely ambiguous. The user's answer, including plain `same task` or `new task`,
continues through the model normally. No application-generated boundary question
or pending-message interception precedes the model request.

An established model-led transition updates the conversational objective, resets
selection and task-local discovery tracking, and makes the next internal request
with exactly the startup functions. Calls co-returned with a transition are
rejected as a whole, with matched outcomes retained; none execute or change
selection under stale task state. Missing/conflicting/reused call IDs still pause
without a transition. A model-led transition is allowed only before work on a user
turn and at most once in that turn, preventing autonomous resets of loop guards.
Tool-only replies continue the current objective. The model must announce a new
objective before requesting work for it.

`UserMessage(..., new_objective=False)` and `same task: <clarification>` remain
optional explicit continuation shortcuts; `new_objective=True` and
`new task: <objective>` explicitly reset before the model request. Both transition
routes retain history, authorization records, evidence and unresolved-operation
state. A model's objective label never replaces the retained explicit-request
scope in the permission projection, changes the session's execution task/target,
grants permission or reconciles uncertainty. Dispatch retains its independent
checks; an unresolved current connection blocks further model work/transitions.

Snapshots remain frozen during tasks. A new established objective refreshes through
the injected catalogue loader; `refresh_catalogue(explicitly_authorized=True)` or
terminal `refresh tools` permits a settled explicit refresh without reconnecting.
Busy or unresolved connections refuse refresh. Refresh resets selection, disables
whole optional groups with missing/unfaithful tools, and refuses same-name schema
drift against previously accepted schemas, including removed/reintroduced names.
Unavailable required startup tools block requests rather than shrink startup.
New unapproved server names remain excluded. Production startup requires faithful
startup schemas within the wrapper's complete startup allowance.

Three consecutive rejected selections or a repeated normalized effective group
set without successful non-discovery work pauses with a concrete blocker and asks
for guidance. Accepted selection breaks the rejection streak; only successful
non-discovery work clears cycle tracking. Explicit refresh does not reset these
task-local safeguards. Bare `continue` cannot bypass a discovery pause; guidance
or a new established objective is needed, with ordinary safety gates still intact.

The `tools=` constructor seam remains available for existing controlled callers;
production always supplies `ToolDiscovery`. A custom visible definition never
bypasses the independently approved execution inventory.

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
Until bounded context (#21), configured endpoint
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

Endpoint context counting and compaction, decision memory, native status/stop
interpretation, operation-specific simulation
policy, and the positive isolated-project recovery route remain their owning
tickets' work. #17 still owns integrated recovery acceptance. Production installs
the approved discovery selection, but model requests/dispatch remain gated as above.
The disabled/status-only connectivity
command and its SDK Runner path remain unchanged.

## Verification

Offline checks use `uv run pytest -q`, `uv run pyright`,
`uv run ruff format --check .`, and `uv run ruff check .`.
`tests/test_conversation.py` covers the shared coordinator, thin terminal wiring,
canonical snapshots, malformed batches and ID history, work limits, persistence
refusal, domain/transport/settlement failure, central incident handoff, final
queued admission, abnormal cancellation, and the actual public stdio path.
`tests/test_discovery.py` additionally exercises exact group memberships/counts,
next-request activation, atomic selection/batch rejection, canonical arguments,
model-led questions/transitions, ordinary clarifications, operational prompt
guidance, exact deletion schemas, refresh/drift/startup loss, independent execution gates and
bounded escape. Its stdio case uses actual `tools/list` definitions and refresh
with a controlled local peer, not CST. Protected-client tests also prove that
catalogue reads cannot pass the permanent uncertainty latch.
The deletion fixtures were extracted without executing handlers from the actual
canonical definitions in `GoncaGomes/cst-mcp` at
`a4a177aeb0856dbf0f668f2dc5a8ca06e20ac8c2`; source links accompany the fixture.
They are offline schema evidence, not proof of native deletion behavior.

Evidence categories:

- Offline deterministic/local controlled-peer evidence: automated tests.
- Institutional endpoint probes: not run.
- Configured-model behavioral trials: not run.
- Native CST, solver and live-isolation acceptance: not run.

No connected experiment, native mutation or recovery bypass is authorized or
demonstrated by this implementation.
