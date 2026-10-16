# T003: Record and serialize MCP attempts

## Status

- Milestone: M2, reliable execution foundation.
- Specification and implementation: authorized in this conversation after presentation of this scope and the conservative block-all-calls policy. Implementation and both correction rounds are complete and independently reviewed.
- Actual checkout: `feat/controller-execution-foundation`. Review comparison base remains `main` at `d591d20467531457a61e32dbc2be3f9b49d815f7`.
- Milestone delivery branch: created and switched to at the reviewed base. Branch setup is confirmed. Authorized task commits run only on this milestone branch.
- Verification: recorded under Implementation evidence (offline only). Independent review: no blocking findings, R1-R5 and F1/F2 resolved. Supplemental profile review also found no blockers. Delivery: authorized on the milestone branch, with confirmed Git receipts supplied through the maintainer handoff. M2 integration remains pending.
- Proposed commit subject: `feat(mcp): serialize calls and record uncertain execution attempts`

## Objective

Serialize individual MCP tool calls per client instance and retain explicit evidence of uncertain outcomes without changing the connectivity command.

## Context and dependencies

- Depends on the existing M1 client and offline fixtures, not T002.
- Relevant references: `src/cst_agentic/mcp_client.py` (`CstMcpClient.call_tool`, `McpToolCall`), `tool_gateway.py` (`ToolGateway.dispatch`), `connectivity.py` (consumption of `.calls`), and `tests/test_mcp_client.py`.
- Read-only inspection confirmed installed MCP 2.3.0 and OpenAI Agents 0.24.0. MCP `ClientSession.call_tool` in `mcp/client/session.py` sends one request and then validates its response. `JSONRPCDispatcher.send_raw_request` in `mcp/shared/jsonrpc_dispatcher.py` does not replay requests. Cancellation can follow delivery, sends only a courtesy cancellation, and drops late responses. A missing usable response cannot prove that CST performed no operation.

## Scope

Modify `src/cst_agentic/mcp_client.py`, `tests/test_mcp_client.py`, and `README.md`. Update this task's implementation evidence during execution.

Include instance-level sequential `tools/call` dispatch, separate in-memory attempt records, a finite queue-inclusive deadline, cancellation propagation, and conservative blocking after uncertainty.

Exclude new tools, gateway policy expansion, project-target policy, persistent records, retries, reset/reconnect/recovery APIs, deterministic construction, model/CST execution, and external integration. Preserve existing unrelated changes.

## Constraints

Preserve `McpToolCall`, the response-only meaning of `.calls`, and successful `call_tool` return behavior. Keep `verify-connectivity` unchanged. No new dependencies, credential reads, Git mutations, or live validation.

## Acceptance criteria

1. At most one `tools/call` is active per client. Other callers queue within their own finite deadline.
2. Every admitted invocation has an ordered attempt record containing copied arguments, monotonic timing, dispatch state, terminal outcome, and optional returned `McpToolCall`.
3. Terminal outcomes distinguish not dispatched, response received, and uncertain. A received response is not proof of successful CST execution or absence of partial effects.
4. Timeout, transport/SDK-validation failure, or cancellation after SDK entry records uncertainty. Caller cancellation propagates.
5. Queue timeout/cancellation before SDK entry records not dispatched and does not poison an otherwise usable client.
6. Any uncertain attempt blocks ALL subsequent tool dispatches on that instance, including callers already queued. No replay occurs. New client construction is not reconciliation.
7. Existing connectivity regressions pass. Arguments are snapshots. Diagnostics use bounded categories without raw exception messages, configuration values, or secrets.

## Implementation approach

1. Add a separate attempt dataclass and `.attempts` collection. Use explicit pending and terminal states, optional result, and stable bounded diagnostic categories. Snapshot JSON-compatible arguments before awaiting. Do not add argument logging or persistent export.
2. Use an instance-owned asynchronous lock. Start the deadline at invocation entry and cover lock acquisition plus SDK execution with the remaining budget. Reject non-finite or non-positive request bounds before dispatch. Keep initialization compatible with existing fake subclasses.
3. Check the uncertain-state latch after acquiring the lock. Record blocked callers as not dispatched without touching the SDK. Mark dispatch started immediately before SDK entry. Missing usable responses after that point are conservatively uncertain, including SDK response-validation exceptions.
4. Finalize records synchronously on cancellation before re-raising. Set the uncertainty latch before releasing the lock and always release the lock. Retain existing `McpCallError` compatibility for non-cancellation request failures. Do not catch cancellation as ordinary success or failure.
5. Append only returned responses to `.calls`. Preserve received error responses and malformed application payloads for caller interpretation rather than treating them as transport uncertainty. Do not add application success classification.
6. Add event-controlled fake-session tests for serialization, queue expiry/cancellation, active cancellation, timeout, transport and SDK-validation exceptions, fail-closed queued/later callers, argument snapshots, error responses, and exactly one underlying invocation with no replay. Document record semantics and blocking limits in README. Closing or replacing the client does not prove an uncertain operation stopped.

## Verification

Offline only. Run from the repository root and check `$LASTEXITCODE` after each command, stopping on failure:

```powershell
uv run --no-sync pytest tests/test_mcp_client.py tests/test_tool_gateway.py tests/test_connectivity.py
uv run --no-sync pytest
uv run --no-sync ruff check src/cst_agentic tests
uv run --no-sync ruff format --check src/cst_agentic tests
```

Use deterministic event coordination rather than timing-sensitive sleeps where possible. No real MCP subprocess, inference, CST attachment, or native operation is authorized.

## Implementation evidence

Implemented per the approved approach; no material deviations.

- `src/cst_agentic/mcp_client.py`:
  - New `McpAttempt` dataclass (name, shallow argument snapshot copied before the first await, `time.monotonic()` start/end, `dispatched` flag, terminal state, bounded diagnostic, optional `McpToolCall` result) and an admission-ordered `CstMcpClient.attempts` collection.
  - `call_tool` now: validates `request_timeout_s` (finite and positive; `ValueError` before dispatch, also enforced in `__post_init__`); appends the attempt before any SDK work; acquires an instance `asyncio.Lock` under a queue-inclusive deadline (set at invocation entry); checks the uncertainty latch after acquiring the lock and records blocked callers not dispatched without touching the SDK; marks dispatch started immediately before SDK entry; sets the latch and finalizes the record synchronously before re-raising on post-entry timeout, transport/SDK-validation failure, or caller cancellation (which propagates); always releases the lock. `.calls` keeps its response-only meaning, and `McpToolCall` is unchanged.
  - Post-entry failures map to bounded diagnostics: `pydantic.ValidationError` and `mcp.client.extension.UnexpectedClaimedResult` are `sdk_validation_failure` (verified against the installed mcp 2.3.0 `send_request`/`call_tool` exception surface); all other post-entry failures are `transport_failure`. No replay, no recovery/reset API, no persistent export, no argument logging.
- `tests/test_mcp_client.py`: added event-coordinated fakes (`GateCallSession`, `_wait_until`) and coverage for serialization order, queue timeout (deterministic via bound shrink), queue cancellation, active cancellation, fail-closed queued and later callers, transport and SDK-validation exceptions (including `UnexpectedClaimedResult`), exactly one underlying invocation with no replay, argument snapshots, error responses staying received and usable, and bound rejection at construction and at entry. Existing connectivity and gateway regressions are unchanged.
- `README.md`: new "Call serialization and attempt records" subsection (record semantics, outcomes, blocking limits, and that closing or replacing the client is not reconciliation) plus clarified per-request bound wording (queueing included) and an updated offline-test coverage list.

Checks (all offline, run from the repository root under PowerShell 5.1; `$LASTEXITCODE` checked after each, stopped on first failure):

- `uv run --no-sync pytest tests/test_mcp_client.py tests/test_tool_gateway.py tests/test_connectivity.py` → 35 passed, exit 0.
- `uv run --no-sync pytest` → 45 passed, exit 0.
- `uv run --no-sync ruff check src/cst_agentic tests` → All checks passed, exit 0 (one auto-fixed import order in the test file, then re-checked).
- `uv run --no-sync ruff format --check src/cst_agentic tests` → 11 files already formatted, exit 0.

Verification category: offline unit tests against fake sessions only; no real MCP subprocess, no inference, no CST attachment or native operation. Acceptance criteria 1-7 are covered by the targeted client tests plus the unchanged gateway/connectivity regression suites.

Local decisions (within the approved approach): bound validation also runs in `__post_init__` (fail-fast at construction, still before dispatch); post-entry `RuntimeError` (for example from SDK structured-content validation) is classified `transport_failure`, not `sdk_validation_failure`, because the type is not specific enough to separate safely; argument snapshots are shallow dict copies, matching the existing `McpToolCall.arguments` semantics (this decision is superseded by correction round 1, which freezes nested JSON-compatible values; see below).

### Correction round 1 (R1-R4)

Addresses the primary disposition and correction handoff recorded under Review outcome. The initial evidence above is retained as history.

- R3 (blocking): nested argument values are now frozen at admission. New module helpers `_freeze_arguments` and `_freeze_value` deep-copy the top-level mapping and every nested mapping or sequence before the first await; JSON scalars pass through as-is, and values that are not JSON-compatible are retained by reference. The `McpAttempt` record, the SDK call, and the `McpToolCall` all use the frozen values, so later caller mutation at any depth cannot alter them. This supersedes the shallow-snapshot decision above. New event-controlled regression `test_call_tool_freezes_nested_arguments_against_queued_mutation` mutates a nested dict and list after admission while the call is in flight and asserts the admitted values in the SDK entry, the record, and the attempt. The `McpAttempt` and `call_tool` docstrings and the README now describe the frozen copy.
- R4 (low, required before delivery): post-entry failures surface only the bounded category. The `McpCallError` message uses the `_diagnose_sdk_failure` category (`transport_failure` or `sdk_validation_failure`) instead of `_describe(exc)`, and the raise is `from None`, so the original SDK exception is neither described nor chained. The `McpCallError` type and the other bounded messages (timeout, queued, blocked, no session) are unchanged, and `_describe` is retained only for the out-of-scope startup/discovery paths. New tests `test_call_tool_transport_failure_does_not_leak_raw_exception` and `test_call_tool_sdk_validation_failure_does_not_leak_raw_exception` embed a fake sensitive URL sentinel in a `RuntimeError` and a `pydantic.ValidationError` (the sentinel is kept under 45 characters so it appears verbatim in pydantic's truncated `input_value`, keeping the test meaningful) and assert that neither `str(error)` nor `traceback.format_exc()` contains it; assertion messages do not echo the sentinel.
- R1 (low, corrected per primary): `call_tool` on a client with no active session (`_session is None`, before `__aenter__` or after close) now finalizes the attempt as `not_dispatched` with the new bounded diagnostic `not_ready` and raises `McpCallError` with a bounded message. The uncertainty latch is not set, so a later call with a live session dispatches normally; no recovery or reset API was added. New regression `test_call_tool_without_session_is_not_dispatched_and_keeps_client_usable`, including later legitimate fake-session use.
- R2 (informational, doc correction): finalization promises are narrowed to the handled outcomes (a returned response, or a timeout, transport/SDK-validation failure, or cancellation). The `McpAttempt` and `finalize` docstrings now state that unhandled process-exit exceptions are not caught and may leave the record `pending`; the `CstMcpClient.attempts` attribute description was narrowed to match. Process-exit handling was not expanded.

Checks (all offline, run from the repository root under PowerShell 5.1; `$LASTEXITCODE` checked after each, stopped on first failure):

- `uv run --no-sync pytest tests/test_mcp_client.py tests/test_tool_gateway.py tests/test_connectivity.py` → 39 passed, exit 0.
- `uv run --no-sync pytest` → 49 passed, exit 0.
- `uv run --no-sync ruff check .` → All checks passed, exit 0.
- `uv run --no-sync ruff format --check .` → 28 files already formatted, exit 0.

Verification category: offline unit tests against fake sessions only; no real MCP subprocess, no inference, no CST attachment or native operation. The leak tests verify public exception output (`str` and ordinary formatted traceback) at the fake-session level only.

### Correction round 2 (R5)

Addresses the primary disposition of R5 recorded under Review outcome. The evidence above is retained as history.

- R5 (low, non-blocking): the `tools/call` timeout `McpCallError` no longer echoes the configured bound. The message is now "tools/call '<name>' timed out: no response within the request budget." (same `McpCallError` type, keeps the "timed out" identification, no configuration value). The unrelated startup and `tools/list` timeout messages are unchanged, per scope. The README sentence claiming that every failed `McpCallError` carries only the two failure categories is narrowed to the transport/SDK-validation paths, and the timeout and not-dispatched messages are now described accurately. `test_call_tool_timeout_is_bounded_error` also asserts that the configured bound (formatted `:g`) does not appear in the error message, establishing the corrected message contract; the existing connectivity hung-call report test still matches the message through the real report path.

Checks (all offline, run from the repository root under PowerShell 5.1; `$LASTEXITCODE` checked after each, stopped on first failure):

- `uv run --no-sync ruff format --check src/cst_agentic/mcp_client.py tests/test_mcp_client.py` → 2 files already formatted, exit 0 (first run reported one reformat for the timeout string, applied, then re-checked).
- `uv run --no-sync ruff check src/cst_agentic/mcp_client.py tests/test_mcp_client.py` → All checks passed, exit 0.
- `uv run --no-sync pytest tests/test_mcp_client.py tests/test_tool_gateway.py tests/test_connectivity.py` → 39 passed, exit 0.

Verification category: message- and documentation-only change verified offline against fake sessions. The already-green full suite was not repeated because the change affects only the tool-call timeout message, its test, and README wording. No change to the uncertainty policy, attempt records, or blocking behaviour.

## Review outcome

### Initial independent review

- Source: reviewer session `ses_eba1dfc71ffe3cxHB1Dg4R21ue`, read-only report to primary.
- Scope/base: working-tree changes to `src/cst_agentic/mcp_client.py`, `tests/test_mcp_client.py`, `README.md`, and this task against `main` at `d591d20467531457a61e32dbc2be3f9b49d815f7`. Excluded `.gitignore`, `AGENTS.md`, and `PLAN.md`.
- Actual verdict: **No blocking findings.** Reviewer reported all seven acceptance criteria met, with two open non-blocking findings. This is not integration approval.
- R1, low, open: calling without an active session records uncertainty and permanently blocks the instance although no SDK entry was possible. Reviewer treated async-context-manager misuse as a non-blocking conservative edge. Primary disposition pending.
- R2, informational, open: docstrings promise terminal finalization even for uncaught `BaseException`. Reviewer assessed this as a documentation overclaim for terminating-process cases. Primary disposition pending.
- Reviewer independently ran targeted tests (35 passed), full tests (45 passed), Ruff lint/format checks, a controlled no-session reproduction, and targeted installed-SDK inspection.
- Limitations: offline only. Queue timeout tested through bound shrink. Shallow snapshots and raw exception wording were disclosed and regarded by the initial reviewer as compatible with the base. No real MCP/CST timing verification or integration authorization.

### Primary follow-up

The primary requested targeted reassessment before Git handoff. These are primary concerns, not invented reviewer findings or a replacement for the initial verdict:

- P1: reassessment confirmed the defect and assigned blocking R3 below.
- P2: reassessment confirmed raw emission and assigned conditional non-blocking R4 below. Primary adjudication follows separately.

### Targeted independent reassessment

- Source: same reviewer session, unchanged source/test scope and comparison base. No broad checks rerun because implementation was unchanged.
- Revised actual verdict: **One blocking finding remains, R3.** R1/R2 remain open and non-blocking. R4 is low, non-blocking under the reviewer's narrow interpretation of record diagnostics, pending primary adjudication.
- R3, medium, blocking, open: event-controlled reproduction proved nested caller mutation after admission changes both queued SDK arguments and recorded evidence. Matching the base's shallow copy does not satisfy snapshot criteria in the newly queued design. Required correction: freeze nested arguments at admission, update documentation, and add a queued nested-mutation regression.
- R4, low, conditional, open: controlled fake sensitive text/URL appears in `str(McpCallError)` and ordinary formatted traceback through `_describe(exc)` and `from exc`. Record diagnostic labels remain clean. The reviewer classified this as unchanged legacy emission unless the primary applies the diagnostic requirement to public exceptions too.
- Checks: targeted `uv run --no-sync` reproductions for nested mutation and fake diagnostic emission, plus read-only scope/base checks. No secrets or raw sensitive reproduction output were printed. No live MCP/CST verification.

### Primary disposition and correction handoff

- R3: correction required as reported.
- R4: correction required before delivery under AGENTS.md credential handling and the approved diagnostic-safety requirement. Apply it to T003's public tool-call exceptions, including ordinary formatted tracebacks. Existing exception text/chaining is not a required interface. Preserve `McpCallError` compatibility. Unrelated startup/discovery cleanup is outside this task.
- R1: correct the no-session pre-dispatch case without poisoning the client. This is evidence-integrity correction, not a recovery API.
- R2: narrow documentation claims to supported exception/cancellation paths rather than expanding process-exit handling.
- Correction round 1 was supplied by implementer session `ses_eba43baaaffeUiJHVETwZXQBZk`, claiming R1-R4 addressed and 49 offline tests passing. Findings remain open pending reassessment by the same reviewer. No Git preparation before that review.

### Independent re-review of correction round 1

- Source: reviewer session `ses_eba1dfc71ffe3cxHB1Dg4R21ue`, same four-file scope against `main` at `d591d20467531457a61e32dbc2be3f9b49d815f7`. Exclusions remain `.gitignore`, `AGENTS.md`, and `PLAN.md`.
- Actual verdict: **No blocking findings remain.** R1, R2, R3, and R4 are resolved against actual corrections. New R5 is low, non-blocking, open for primary disposition. This is not integration approval.
- R1 resolved: no-session calls record `not_dispatched`/`not_ready`, do not set the latch, and allow later legitimate fake-session use.
- R2 resolved: finalization promises now explicitly exclude unhandled process-exit exceptions.
- R3 resolved: reviewer independently reproduced the original queued nested-mutation case and verified admitted values reach the SDK and records unchanged. The in-repository regression covers in-flight rather than queued mutation. Custom non-JSON values remain referenced as documented.
- R4 resolved against required scope: fake transport and pydantic sentinels do not appear in public messages or ordinary formatted tracebacks. Original exceptions remain programmatically reachable through suppressed `__context__`. Unrelated startup/discovery formatting remains outside scope.
- R5, low, non-blocking, open: timeout messages echo the configured request bound. README overstates bounded category messages as applying to every failed call rather than transport/SDK-validation failures. Reviewer requested primary disposition.
- Reviewer checks: targeted tests (39 passed), full tests (49 passed), Ruff lint/format, read-only scope/base checks, and five controlled fake-session reproductions. No real MCP/CST/inference or secret reads. Live timing remains unverified.

### Primary disposition of R5

Require a small consistency correction before Git preparation: remove the configured bound from the tool-call timeout message and narrow README wording to the failure paths actually carrying categories. Preserve `McpCallError` and useful timeout identification. This does not expand scope or change the uncertainty policy. Return to implementer for correction round 2, then targeted re-review. R1-R4 stay resolved unless relevant changes reopen them.

### Final targeted re-review of correction round 2

- Source: reviewer session `ses_eba1dfc71ffe3cxHB1Dg4R21ue`, same four-file scope against `main` at `d591d20467531457a61e32dbc2be3f9b49d815f7`. Excluded `.gitignore`, `AGENTS.md`, and `PLAN.md`.
- Actual final verdict: **No blocking findings. All findings R1-R5 are resolved.** No new findings. This is review outcome only, not integration authorization or live verification.
- R5 resolved: tool-call timeout retains `McpCallError` and timeout identification without the configured bound. Its strengthened regression fails against the old message. README distinguishes actual message paths without conflating cancellation outcomes with emitted errors.
- R1-R4 remain resolved: reviewer confirmed no collateral changes to no-session handling, supported finalization claims, argument freezing, sanitized exception output, cancellation propagation, or uncertainty blocking.
- Reviewer personally ran final targeted tests (39 passed) and Ruff lint/format checks. Full-suite evidence remains the prior 49 passing tests, not repeated for the final message/documentation-only change. Read-only base/scope checks confirmed unchanged HEAD and expected files.
- Limitations: offline fake sessions only. No new reproductions needed for the message-only correction. Unrelated startup/discovery diagnostics retain legacy wording outside this task. No real MCP/CST/inference or credential access.

### Supplemental independent review of planning/guidance

- Source: reviewer session `ses_eba1dfc71ffe3cxHB1Dg4R21ue`, read-only supplemental report. Exact scope: `.gitignore`, `AGENTS.md`, and `PLAN.md` against `main` at `d591d20467531457a61e32dbc2be3f9b49d815f7`. The four T003 files were not re-reviewed. R1-R5 remain resolved.
- Actual verdict: **No blocking findings.** Two non-blocking findings were open for primary disposition. This is not integration approval.
- F1, informational, non-blocking: the local ignored discovery document had a Markdown link that would dangle in a fresh clone. Reviewer allowed acceptance or explicit local/untracked wording.
- F2, low, non-blocking: three roadmap approval-state lines predated the user's authorization and omitted the companion commit. Reviewer allowed correction or explicit acceptance.
- Primary disposition: F1 corrected by labeling the proposal local and intentionally untracked without a Markdown link. F2 reconciled to the user's actual branch/two-commit instruction. These are owner wording/status corrections, not an invented independent re-review verdict.
- Reviewer checked the complete three-file diff, known seven-path worktree and base, Git history, `.gitignore`, cited proposal status/counts, and T001 evidence. `.env` remains ignored. Credential guidance only strengthens the existing restriction. No Python/tests, credential reads, or live MCP/inference/CST.
- Limitations: local proposal checked only for cited figures/status. Line-ending warning is cosmetic. The explicit two-commit instruction governs the companion planning commit. No source/test behavior was changed by the supplemental scope.

### Supplemental review of updated maintainer profile

- Source: reviewer session `ses_eba1dfc71ffe3cxHB1Dg4R21ue`. Exact additional scope: `.opencode/agents/maintainer_git.md` against `d591d20467531457a61e32dbc2be3f9b49d815f7`, plus verification of the owner F1/F2 corrections in `PLAN.md`. Prior `.gitignore`/`AGENTS.md` coverage carries because their diffs are unchanged.
- Actual verdict: **No blocking findings, no new findings.** F1 and F2 are resolved. R1-R5 remain resolved. Review is not integration approval.
- Profile adds only `ask` rules for `git branch *` and `git switch *`. Existing edit restrictions, model/provider selection, staging/commit asks, and explicit-authorization boundaries are unchanged. No credentials or accidental privilege regression were found.
- Checks: complete profile/diff inspection, roadmap reconciliation checks, read-only Git branch/base/index/eight-path scope verification. No Python/tests or credential reads. Runtime permission diagnosis was not repeated because authorized branch creation/switch had already succeeded.
- Limitations: cosmetic roadmap line-ending warning. The user-performed profile edits are distinct from unauthorized agent-performed permission changes. Ignored discovery document remains untracked and outside staging scope.

### Delivery state

Ready for maintainer Git preparation for `mcp_client.py`, its tests, `README.md`, and this task. Primary-owned roadmap changes and pre-existing `.gitignore`/`AGENTS.md` changes remain excluded from the intended T003 commit. No staging, commit, branch operation, or integration is authorized yet. M2 remains incomplete after T003.

Maintainer session `ses_eb9dbe065ffeO1yx470LP105f3` completed initial read-only preparation with no scope or review blockers, verifying `main` at the comparison base and an empty index. The proposed commit on `main` was rejected by the user before any Git mutation. That approval request is superseded.

The user confirmed one branch per milestone and one commit per task. Correct target: create M2's `feat/controller-execution-foundation` from the reviewed base, then place T003 as one commit on it. Later M2 tasks use the same milestone branch. Exact task scope remains four files, excluding `.gitignore`, `AGENTS.md`, and `PLAN.md`. Subject remains `feat(mcp): serialize calls and record uncertain execution attempts`. Only review/delivery metadata changed after final technical review. Corrected branch-creation and staging/commit authorization must be requested together. No Git mutation is authorized yet. Push and merge remain separate.

The same maintainer completed corrected read-only preparation: branch/base, empty index, and known worktree state remain unchanged. Review coverage is sufficient and no scope blockers were found. Execution risk: branch creation may be denied by tool permissions. On denial, stop and report without bypass, permission changes, or a commit on `main`. The corrected request covers only creation/switch to the named M2 branch from the reviewed base and one exact four-file T003 commit. User authorization remains pending.

### Expanded delivery request

The user subsequently instructed: "I want everything included so create the branch and the commits" after discussion of two focused commits on the M2 branch. Carry this actual instruction to the maintainer. Known expanded scope is seven paths: the four T003 files, plus `.gitignore`, `AGENTS.md`, and `PLAN.md` in a companion planning/guidance commit. The prior exclusions are superseded for this expanded request. Do not interpret "everything" as permission to add ignored artifacts, credentials, or unknown files. Supplemental independent review of the three added paths found no blockers. No push, merge, or permission-configuration changes were requested. Git execution has not yet occurred.

### Confirmed branch-execution result

Maintainer session `ses_eb9dbe065ffeO1yx470LP105f3` attempted the authorized `git switch -c feat/controller-execution-foundation d591d20467531457a61e32dbc2be3f9b49d815f7`. The shell permission layer rejected it. The maintainer stopped without fallback, bypass, main commit, or permission edits. Post-denial check confirmed `main` at the same base, empty index, and unchanged known worktree. No branch, staging, or commit occurred. The user's branch-creation authorization stands, but execution requires a permitted path or manual user creation.

The maintainer prepared companion subject `docs: align roadmap and agent guidance with milestone branch policy` for `.gitignore`, `AGENTS.md`, and `PLAN.md`. This concrete subject was not yet presented for user approval. The second T003 subject/scope remain as previously presented. No additional execution is implied by preparing that draft.

### Confirmed result after maintainer permission update

The user updated the maintainer and explicitly renewed the instruction to use it for branch creation and commits. Fresh maintainer session `ses_eb9becfa8ffePyjm1pLN40NJvr` picked up the updated profile. Prechecks confirmed the base, empty index, absent target ref, and eight known paths, including the newly modified `.opencode/agents/maintainer_git.md`.

Authorized `git branch feat/controller-execution-foundation d591d20467531457a61e32dbc2be3f9b49d815f7` succeeded with exit 0. The subsequent `git switch feat/controller-execution-foundation` was denied. The maintainer stopped without fallback or permission edits. Postcheck confirmed the branch exists at the reviewed base, checkout remains `main`, index is empty, and all eight worktree paths are preserved. No staging or commit occurred. Do not recreate the branch. Switching authorization stands, but a permitted execution path is still required. The newly edited profile needs its own scope/review check before inclusion in a commit.

### Confirmed switch and resumed commit authorization

After the user added the switch permission and said "Done", maintainer session `ses_eb9becfa8ffePyjm1pLN40NJvr` successfully ran `git switch feat/controller-execution-foundation`, exit 0. It confirmed the branch and HEAD at the reviewed base, empty index, and all eight paths preserved. No staging, commit, push, merge, permission edit, or file edit occurred in that dispatch.

The companion subject was presented to the user before the user renewed the instruction to use the updated maintainer for "branch creation and commits". Carry that actual renewed authorization for the unchanged two-commit grouping and presented subjects, without requesting the same approval again. Account for the user's newly edited maintainer profile in the planning/guidance commit after supplemental review. The eight-path scope excludes ignored local drafts, secrets, generated files, and unknown paths. Planning/guidance goes first, T003 second. No push or merge is authorized.

### Confirmed first commit and final task-commit checkpoint

Maintainer session `ses_eb9becfa8ffePyjm1pLN40NJvr` confirmed commit `a6734efeb553cd100f7568aa023f366185fc1b15`, subject `docs: align roadmap and agent guidance with milestone branch policy`, on `feat/controller-execution-foundation`, parent `d591d20467531457a61e32dbc2be3f9b49d815f7`. It inspected the staged diff and verified exactly `.gitignore`, `.opencode/agents/maintainer_git.md`, `AGENTS.md`, and `PLAN.md` in the commit. No hooks failed or were bypassed.

At this checkpoint only the four T003 paths remain pending: `README.md`, `src/cst_agentic/mcp_client.py`, `tests/test_mcp_client.py`, and this task. The second user-authorized commit uses `feat(mcp): serialize calls and record uncertain execution attempts`. Review coverage remains valid because no source, test, or README content changed after final review. Only primary-owned review/delivery records changed in this task. The maintainer must verify the exact four-file index and report the resulting task-commit receipt through the primary. No extra metadata commit, amend, push, or merge is authorized. M2 remains incomplete and unmerged.

## Remaining limitations

- Verified only with offline fake sessions and the installed mcp 2.3.0 exception surface; behaviour against a real `cst-studio-mcp` subprocess (delivery timing versus local timeout, courtesy cancellation after dispatch) remains unverified.
- A queue timeout of a queued caller can only occur when the shared bound changes between entries or the event loop is starved (an in-flight holder always has the earlier deadline), so the test covers it via bound shrink; the cancellation-in-queue path is event-deterministic.
- Post-entry `RuntimeError` (for example from SDK structured-content validation) is classified `transport_failure` rather than `sdk_validation_failure`; both map to the same uncertain outcome and blocking.
- Argument freezing is deep for JSON-compatible values (mappings and sequences at every depth). Values that are not JSON-compatible (for example custom objects) are retained by reference and remain shared with the caller's mapping.
- This task alone does not complete M2 or provide reconciliation, mutation approval, project targeting, or native completion verification.
