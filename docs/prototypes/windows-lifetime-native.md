# Windows lifetime: disposable native blank-project round

**THROWAWAY / NOT PRODUCTION / NOT A TICKET RESOLUTION.**

Artifact branch: `prototype/windows-transport-lifetime`. No PR or merge is intended.

**Local-only repeat addendum:** the human subsequently authorized one further
leave-open case at a new fixed target, raising the cumulative call ceiling to 13
while retaining 900 seconds and adding a 300-second case cap. The repeat result
is included below. These changes/evidence are **not committed, pushed or posted
to GitHub**, as explicitly requested. The earlier two-case sections remain a
historical record; the repeat section supplies the current ledger and sources.
Following review, the human accepted the session-bound lifetime restriction
recorded below. That partial design decision is also local only, not a ticket
resolution or permission for additional experiments.

Decision: [Verify Windows transport lifetime and bounded solver-stop behavior](https://github.com/GoncaGomes/cst-agentic/issues/14).
Prior evidence: [offline round](windows-lifetime-offline.md) and
[delayed-teardown follow-up](windows-lifetime-followup.md).

## Human-approved scope

Two newly launched disposable CST instances, no existing-instance attachment:

- `C:\Users\Lenovo\AppData\Local\Temp\opencode\cst-lifetime-native\leave-open.cst`:
  create/save one blank MWS project, inspect live status, release handles without
  requesting native close, then tear down the ordinary public stdio transport.
- `C:\Users\Lenovo\AppData\Local\Temp\opencode\cst-lifetime-native\authorized-close.cst`:
  create/save one blank MWS project, inspect live status, explicitly close its
  new Design Environment, then tear down the ordinary public stdio transport.

Maximum **12 tools/call and 900 active experiment seconds including cleanup**,
across both cases. Cases are executed separately so inconclusive end-of-case
observations can be reconciled with the human before continuing. No solver,
model/endpoint request, arbitrary attachment, overwrite, save retry, production
change, dependency change, or private SDK preservation hook is authorized.
Transport teardown may terminate either disposable instance.

The human additionally approved a minimal throwaway MCP peer after source review
found that the existing server's creation handler retries failed saves at a
timestamp-suffixed path and its close-project tool does not close the instance.
This does **not** authorize production server changes or validate those handlers.

## Public contracts and experiment construction

- Reviewed server source is `GoncaGomes/cst-mcp` at
  `a4a177aeb0856dbf0f668f2dc5a8ca06e20ac8c2`, locally clean when inspected.
  [Project creation/save fallback](https://github.com/GoncaGomes/cst-mcp/blob/a4a177aeb0856dbf0f668f2dc5a8ca06e20ac8c2/src/cst_mcp/session.py#L337-L392)
  and [disconnect/project close](https://github.com/GoncaGomes/cst-mcp/blob/a4a177aeb0856dbf0f668f2dc5a8ca06e20ac8c2/src/cst_mcp/session.py#L309-L319)
  are source findings, not newly executed server evidence.
- Installed CST 2025 help, `Online Help/Python/source/cst.interface.html`, documents
  `DesignEnvironment.new`, `pid`, `is_connected`, `list_open_projects`, `close`,
  `new_mws`, and `Project.filename`, `design_environment`, and
  `save(..., allow_overwrite=False)`. Project close and instance close are distinct.
- The [peer](../../src/cst_agentic/windows_lifetime_native_peer.py) uses those
  official APIs through a single dedicated worker, with no attach-to-any route.
  It uses the reviewed server's public `CSTConfig`, `ToolRegistry`, `CSTWorker`,
  and `protocol_output` helpers without modifying them. No server auto-connect,
  built-in project-save fallback, dialog-clicking watcher, or raw VBA is used.
- The [driver](../../src/cst_agentic/windows_lifetime_native.py) enters/exits
  public `stdio_client` and `ClientSession` contexts in one lifecycle-owner task.
  A single protected dispatch path validates the fixed schema/operation plan,
  serializes calls, records queue-inclusive 120-second deadlines, persists an
  in-flight marker before SDK entry, and halts on uncertainty or received failure.
  It does not reuse the fake-only dispatch drivers or change the production client.
- Each peer admits only connect-new, one create/save, live status, and the
  case-specific exit action. Fresh PID/ProcessInfo agreement, no initial projects,
  live filename, sole open-project path, and project-associated DE PID are checked
  before dependent operations. Save failure is not replayed or followed by cleanup
  tools. The close case calls `DesignEnvironment.close()` once, not project close.
- Startup includes transport, initialization, and catalogue (120 seconds).
  Cleanup is measured as one total allowance (30 seconds). Per-call admission
  reserves time for cleanup and the post-teardown observation. The durable round
  ledger prevents replay and carries the 12-call/900-second ceiling across cases.
- Read-only Windows Toolhelp, process-time, process-handle, and scoped window
  APIs observe only the selected chain and newly identified instance. No command
  lines, environments, raw window titles, screenshots, arbitrary process kills,
  job-handle duplication, or private SDK job registry access are used.
  `IsProcessInJob(handle, NULL)` means **some job**, not the SDK's exact job.
- The post-teardown window is at most five seconds, ending early if every
  tracked process terminates. A matching visible project title and an exact live
  DE process handle support a time-bounded open-instance observation. File
  existence or disconnect acceptance alone cannot establish that it remains open.
  Inconclusive observations require manual confirmation, recorded as human evidence.

The child environment uses only the SDK-default Windows execution variables,
offline uv, explicitly selected CST 2025/manual/work-directory settings, and
the existing provisioned server environment. No `.env`, provider client, ambient
Python-path override, or credential-bearing configuration is loaded or printed.
Server stderr is discarded. Errors are recorded by bounded type/category only.

## Results

**The corrected harness completed both authorized cases. The tested leave-open
path did not preserve CST; explicit instance close was independently observed
before transport teardown. This is not a ticket resolution.**

| Case / attempt | Observed outcome | Qualification |
| --- | --- | --- |
| Leave-open, initial logging failure | Initialize/catalogue completed. The first `tools/call`, `native_connect`, returned a received `TypeError` in 0.016 s; driver duration 3.890 s. | Failed before native API entry. No launch identity, tracked CST handle or project file. The human later reported no CST window. This attempt supports no native lifetime conclusion. |
| Leave-open, explicitly approved logging-fix retry | A fresh CST 2025 DE (PID 15732) created/saved the exact blank target. Independent live filename, project association and expected project window matched. DE remained alive after `native_disconnect` and at the first post-teardown sample; its exact process handle was terminated at the sample 0.125 s after transport return. All six tracked processes had terminated then. | Four received successful calls; one save; no explicit instance-close call. Ordinary reference release plus public stdio teardown did **not** preserve this instance. The sample brackets termination, not its precise latency or causal mechanism. |
| Authorized close | A second fresh DE (PID 14736) created/saved the other exact target. The expected live project/window matched. `DesignEnvironment.close()` was called once; its exact DE process handle and DB storage descendant were already terminated immediately after the close response, before session/transport exit. All tracked processes had terminated at the 0.062 s post-teardown sample. | Four received successful calls; one save. This distinguishes native instance close from project close, disconnect acceptance and later transport cleanup. |
| Additional authorized leave-open repeat, local only | A fresh DE (PID 11548) created/saved `leave-open-repeat.cst`; live filename, sole project, associated DE and expected window matched. DE was alive after disconnect and at 0.063 s after transport return, then its exact handle was terminated at the 0.125 s sample. All six tracked processes were terminated then. | Four received successful calls; one save; no explicit instance close. Same observed end-state pattern as the first successful leave-open case. The human subsequently confirmed only license-dialog dismissal, not manual CST closure; this is human-provided evidence, not an independent UI trace. |

All three successful native cases established the end state using exact process
handles and scoped window observations. None required manual confirmation. No
unexpected project was adopted; each connect recorded zero pre-existing DEs.
All tracked processes reported membership in **some** job; this does not identify
the SDK's exact Job Object, ownership or nesting.

There was no explicit native close in leave-open. Reference-release/native
finalization effects were not isolated from transport cleanup. The observation
therefore rejects the **tested combined path** as evidence of leave-open support;
it is not a proof that a particular Job Object alone caused termination.

### Evidence pointers

- Initial failure, unchanged: [observations](windows-lifetime-native-evidence/leave-open-observations.json),
  [peer events](windows-lifetime-native-evidence/leave-open-peer-events.jsonl),
  [peer identity](windows-lifetime-native-evidence/leave-open-peer-identity.json),
  [recovery marker](windows-lifetime-native-evidence/leave-open-recovery.json),
  [initial one-call ledger](windows-lifetime-native-evidence/round.json).
- Leave-open retry: [observations](windows-lifetime-native-evidence/leave-open-logging-fix-1/observations.json),
  [peer events](windows-lifetime-native-evidence/leave-open-logging-fix-1/peer-events.jsonl),
  [outer timing](windows-lifetime-native-evidence/leave-open-logging-fix-1/outer-observation.json),
  [wrapper admission/source identity](windows-lifetime-native-evidence/leave-open-logging-fix-1/wrapper-start.json),
  [post-case ledger](windows-lifetime-native-evidence/leave-open-logging-fix-1/round-after-case.json).
- Explicit close: [observations](windows-lifetime-native-evidence/authorized-close/observations.json),
  [peer events](windows-lifetime-native-evidence/authorized-close/peer-events.jsonl),
  [outer timing](windows-lifetime-native-evidence/authorized-close/outer-observation.json),
  [wrapper admission/source identity](windows-lifetime-native-evidence/authorized-close/wrapper-start.json),
  [post-case ledger](windows-lifetime-native-evidence/authorized-close/round-after-case.json).
- [Final conservative ledger](windows-lifetime-native-evidence/round-after-accounting.json)
  and [native-free evidence/accounting verification](windows-lifetime-native-evidence/native-evidence-verification.json).

## Failure diagnosis and approved continuation

The logging helper was defined as `event(self, name, **facts)` but called as
`event("operation_entered", name=name)`. A standalone
`inspect.signature(...).bind(...)` check reproduced the duplicate binding without
starting a peer or importing CST. Executed source places this failure before the
first native API invocation. The human observation, "No cst window appeared,"
is retained as **human-provided evidence**, not independent process evidence or
the original authorization to retry.

After an explanation and a specific proposal to fix only the disposable harness,
retain the failed call and limits, and cautiously resume the same cases, the
human explicitly replied **"Go ahead."** The
[continuation record](windows-lifetime-native-evidence/logging-fix-source/logging-fix-continuation.json)
records that scope, the fixed targets and conditional manual-confirmation rule.
The authenticated developer and ticket claim were rechecked: the decision was
OPEN, `wayfinder:prototype`, assigned to `GoncaGomes`, matching `gh api user`.

Before correction, the failed executed driver/peer were hash-verified and
[archived](windows-lifetime-native-evidence/failed-attempt-source/). The helper's
first parameter was renamed to `event_type`. A native-free check then validated
all eight event call sites and an actual log write. Focused guard checks proved
that missing authorization, ordinary replay, a second retry, premature second
case and inconclusive first-case status remain blocked. They started no peer and
made no native calls. The later deterministic version uses the preserved initial
ledger only in its own temporary fixture, never resets the live ledger.

The driver admits exactly one `--resume-approved-logging-fix` continuation of the
received, proven-pre-native failure. It retains the failed ledger inside the
continuation record and leaves the original failure directory/recovery marker
unchanged. The retry has a new exclusive evidence directory and a new marker;
this is not a reset of a latched client or a replay of an uncertain effect.
The old peer/launcher PIDs were absent at preflight; their original exit times
remain unknown. Each native invocation also has an exclusive outer launch record.
Both cases are now completed and further ordinary invocation is refused.

## Timing and accounting — original two-case round

- Total MCP calls: **9 of 12**, comprising the received failed call plus four
  successful calls in each case. No native operation was automatically retried.
- Successful leave-open retry: native connect **103.468 s**, create/save
  **7.172 s**, status **0.031 s**, disconnect **0.031 s**; public cleanup
  **0.375 s**. Driver **114.328 s**; measured outer uv invocation **114.887478 s**.
- Explicit-close case: connect **8.219 s**, create/save **4.579 s**, status
  **0.015 s**, close **5.047 s**; public cleanup **0.344 s**. Driver **20.375 s**;
  measured outer uv invocation **20.820878 s**.
- Each call includes queueing and settlement and was below 120 s. Catalogue/
  transport startup was **3.110 s** and **2.094 s**, respectively. Startup and
  cleanup also remain below 120/30 s when conservatively adding *all* measured
  outer uv overhead to each. Both outer processes returned exit code zero;
  no cleanup exception was suppressed and counted as success.

The initial failed path measured only 3.890 driver seconds. Outer uv overhead,
exact process exit and separately completed cleanup were **not** captured then.
It is charged **180 s conservatively** (120 startup + 30 cleanup + 30 overhead
reserve), not advertised as a retrospectively measured upper bound. A further
30 s reserve was charged before each successful case; inner cleanup was limited
to 25 s to leave exit headroom within the 30 s total allowance.

The wrapper initially used `[Math]::Max(0, delta)`, which selected an integer
overload and reported the first overhead as 1 s instead of about 0.559478 s.
Its raw timers and reserved accounting were intact. A native-free check
reproduced the rounding and exercised the actual corrected double-precision
assignment. The initial wrapper/evidence were preserved; only the wrapper
calculation was corrected before the second case. The
[derived correction](windows-lifetime-native-evidence/accounting-correction-check.json)
recomputes the first upper bounds without replaying CST: startup about 3.669478 s,
cleanup about 0.934478 s. The second wrapper measured overhead about 0.445878 s.

After both cases, evidence review also charged the entire **146.542152 s** gap
between invocations, including the accounting correction/review while no MCP
connection was open. The preserved raw per-case ledger charge was 374.703 s;
the final ledger, retaining both wrapper reserves and adding this gap, charges
**521.245152 of 900 s**. Second-case admissions would still satisfy the 155 s
reserve with that gap included. Wrapper-start UTC timestamps plus outer timing
give a new-round elapsed envelope of approximately **282.250508 s**, including
the inter-case gap. This cross-invocation envelope is not independently protected
against wall-clock adjustment. Evidence-writing time is covered by retained
reserves rather than separately measured. Do not claim an exact remaining budget
or retrospective complete-budget validation for the original failed path.

## Executed-source snapshots

| Execution | Driver SHA-256 | Peer SHA-256 |
| --- | --- | --- |
| Initial failure | `5A921EAB5C98EDF2FAE2BFB1FD99BB8E07D6D0D3E70C03253F2EB2FE6E40D7FD` | `D2B06784B27B9AFF33E8BE9D8CD85090130231B2E37725BE1289B1ECB6416446` |
| Original two successful cases | `64299B19BDCDCA80CB357B8A4BE4A0ECC71F52979A10B460FF56FBF22BB3CFCE` | `8368E88FC856767E4F197CF9BE732A41912B4B3EBB1D2801373ED89AAF20E8E5` |
| Additional leave-open repeat, local only | `AB3F2B110C8E2B44D9195D10B8F44A4B1B352F782B5202D2D2565FD23097ECB2` | `0E67D2AF6EACA4241744F19B616E17F36435A414ABB90365E6BF0CB470C88379` |

The active Python sources now match the repeat's executed versions; the original
two successful cases' sources remain unchanged in their snapshots. Preserve the
source groups:

- [Initial failed sources](windows-lifetime-native-evidence/failed-attempt-source/).
- [Logging fix, first executed wrapper and checks](windows-lifetime-native-evidence/logging-fix-source/),
  with [check results/source manifest](windows-lifetime-native-evidence/logging-fix-static-checks.json).
- [Corrected second-case wrapper, deterministic guard check and native-free finalizer](windows-lifetime-native-evidence/accounting-correction-source/).
- [Additional repeat sources, authorization, pre-repeat ledger and checks — local only](windows-lifetime-native-evidence/leave-open-repeat-source/).

## Additional leave-open repeat — local only

The human reported that the previous native round presented an educational-
license dialog which they acknowledged manually, and said the normal MCP server
has a threading-based popup closer. The full statement is retained as
**human-provided evidence** in the repeat authorization, without independently
attributing the click or its duration to a specific prior case. The disposable
peer does not include that automatic dialog watcher; none was added for the
repeat. Before execution, the human was asked to acknowledge only the license
dialog and leave the main CST window untouched. After the run, the human confirmed:
**"Yes, I only dismissed the license dialog."** This supplements the evidence as
a human-provided report of no manual main-window closure, not an independent UI
trace or proof of which shutdown mechanism terminated CST.

After an explicit proposal, the human replied **"Yes you may"**, approving:

- A newly launched instance and exactly
  `C:\Users\Lenovo\AppData\Local\Temp\opencode\cst-lifetime-native\leave-open-repeat.cst`.
- The same disposable MCP peer and four operations: connect-new, create/save
  once without overwrite, live status, release handles without an explicit close.
- **13 cumulative MCP calls**, the unchanged **900-second cumulative ceiling**,
  and a **300-second repeat cap including cleanup**. No reset of prior accounting.
- Manual license-dialog dismissal if needed; manual lifetime confirmation only
  when process/window evidence is inconclusive.
- **No commits, pushes or GitHub comments.** All new material remains local.

The ticket was read-only rechecked as OPEN, `wayfinder:prototype`, with its
assignee matching `gh api user`. The admission guard requires the exact completed
prior ledger, prior conclusive terminal process observations, the explicit new
authorization and an absent new target. It preserves the old cases/markers,
records the pre-authorization ledger, raises only the call ceiling, and uses a
new exclusive attempt directory. The guarded operation order ends in
`native_disconnect`, never `native_close`. Native-free checks exercised the
actual admission and budget functions, refusal of replay/wrong scope/overwrite,
all eight event bindings and a real log write. No peer or CST was started by
those checks. The original two-case snapshots remain byte-identical.

The four successful call durations were connect **19.000 s**, create/save
**6.579 s**, status **0.015 s**, and disconnect **0.016 s**. Startup was
**2.500 s**, public cleanup **0.406 s**, inner driver **28.656 s** and measured
outer uv invocation **29.270096 s**. Both startup and cleanup remain within their
120/30-second complete allowances even with all measured outer overhead added
to each. The new case was below its 300-second ceiling, with no cleanup exception
suppressed. All tracked processes terminated, so no manual lifetime check was
required. This does not establish the cause of native process termination or
verify the normal server's handlers/watcher.

The ledger now records **13 of 13 calls**, including the original failed call,
and approximately **579.901152 of 900 seconds charged**, retaining all earlier
timing qualifications. That adds the repeat's 28.656 driver seconds and a 30-second
outer/evidence reserve to the preserved 521.245152-second charge. Human waiting
between the completed original round and this newly authorized case is not
charged as active experiment time. There is no authorization for more native
calls, regardless of unspent time.

Local-only evidence:

- [Repeat observations](windows-lifetime-native-evidence/leave-open-repeat/observations.json),
  [peer events](windows-lifetime-native-evidence/leave-open-repeat/peer-events.jsonl),
  [outer timing](windows-lifetime-native-evidence/leave-open-repeat/outer-observation.json),
  [wrapper admission](windows-lifetime-native-evidence/leave-open-repeat/wrapper-start.json).
- [Pre-authorization ledger](windows-lifetime-native-evidence/leave-open-repeat/ledger-before-authorization.json),
  [post-repeat ledger](windows-lifetime-native-evidence/leave-open-repeat/round-after-repeat.json),
  [evidence verification](windows-lifetime-native-evidence/leave-open-repeat/verification.json).
- [Subsequent human UI confirmation](windows-lifetime-native-evidence/leave-open-repeat/human-confirmation.json).
  The earlier verification JSON is preserved as recorded before this confirmation.
- [Executed sources/authorization/checks](windows-lifetime-native-evidence/leave-open-repeat-source/).

No production code, normal server handler, SDK, dependency, existing CST instance,
solver or model endpoint was changed or exercised by this repeat. At completion
of the repeat, no strategy selection, ticket resolution, tracker modification,
commit or push had been performed. The subsequent partial policy decision below
does not resolve the complete ticket.
The fixed `native-lifetime-run-repeat.ps1` wrapper was executed exactly once and
is now consumed; it must not be replayed.

## Human-confirmed lifetime restriction — local only

After reviewing the repeat, the human accepted both scoped recommendations with
**"Yes and yes"**. The
[local decision record](windows-lifetime-native-evidence/session-bound-lifetime-decision.json)
distinguishes this design choice from native observations:

- A **Controller session** means one run of the Controller, potentially spanning
  multiple user tasks. Finishing a task/batch or interrupting a task is not
  application exit and does not by itself authorize closing CST.
- **Controller-launched CST instances are session-bound.** There is no promise
  of CST survival after either normal Controller exit or an unexpected crash.
  This explicitly relaxes the earlier default-leave-open/survival requirement
  for those instances. Failed survival alone no longer blocks this restricted
  first-version lifetime policy.
- Normal exit must still warn about unsaved work and active simulations and
  retain the applicable authorization/confirmation flow and bounded orderly
  cleanup attempts. Accepting crash/exit coupling does not authorize silent
  destructive exit or establish graceful solver stop.
- Permission applies **only to instances newly launched by the Controller**.
  Existing-instance attachment remains blocked until precise attachment and
  its lifetime consequences are established; it must not endanger pre-existing
  CST work under this policy.

This accepts a lifecycle consequence, not a finding that MCP the protocol
requires CST termination or that the exact cause is solely an MCP-side defect.
The Controller-session term was added to the primary `GLOSSARY.md`, without
putting implementation policy into the glossary or replacing existing entries.

The restriction is a partial revision of the prior runtime leave-open contract,
not a complete transport/lifecycle resolution. Bounded solver-stop behavior,
uncertainty restrictions and other unverified ticket obligations remain in force.
No production implementation or additional native/endpoint execution is
authorized. The record remains local: no commits, pushes, tracker comments,
issue closure or map-index updates are made.

## Checks and limitations

Ruff lint/format, the binding check, actual event-write check, focused
continuation guards and PowerShell wrapper parsing passed before native work.
The arithmetic correction passed its actual-expression check before the second
case. Final native-free verification checked received-call counts/deadlines,
one save per case, close-event counts, exact-handle terminal states, source
hashes and unchanged original failure/marker bytes. The evidence finalizer's
initial lint findings were fixed before it ran. No production test suite ran.

Raw Windows evidence retains its original CRLF bytes. Scoped Git attributes
disable EOL conversion and recognize CR at EOL while retaining the default
whitespace checks; a separate content-line check rejects trailing spaces/tabs.
Staged blob hashes are checked against working-copy bytes before capture.

Native-observed behavior, source contracts, synthetic/native-free checks,
human-provided observations and the confirmed design restriction remain distinct.
The evidence does not establish a general survival guarantee or complete viable
public lifetime/solver-stop strategy; the narrower session-bound policy above
was accepted by the human rather than inferred from harness completion.
No long-term process-survival claim follows from the bounded observation window.
It does not establish solver continuation/stop, simulation launch/wait/stop
allowances, exact SDK job ownership, precise existing-instance attachment,
whole-Controller crash recovery or existing server-handler behavior. No private
SDK preservation hooks, production changes, dependency changes, model/endpoint
requests, solver work or existing-instance attachment were used.

This iteration does not resolve or close the ticket. The confirmed lifetime
restriction settles only part of its question; further work needs a separately
agreed fixture and budget, especially for bounded solver stop. No map
Decisions-so-far update is justified by the blank-project cases alone.

## Reproduction cautions

**All three approved targets and the one-time continuation are consumed. Do not
rerun either native driver/wrapper or reset the ledger/markers.** No budget
remaining in a counter authorizes extra cases. Reproduction needs a newly agreed
disposable scope, targets and budget; do not silently rename the existing targets.

Historical commands, executed from `C:\dev\cst-agentic`, were the initial direct
driver `leave-open` invocation, then the two separately reviewed wrapper cases:

```powershell
# Historical record only; NOT instructions or permission to replay.
& 'C:\Users\Lenovo\AppData\Local\Temp\opencode\native-lifetime-run-case.ps1' -Case 'leave-open'
& 'C:\Users\Lenovo\AppData\Local\Temp\opencode\native-lifetime-run-case.ps1' -Case 'authorized-close'
```

The first wrapper supplied `--resume-approved-logging-fix`; the second did not.
Use the corresponding immutable wrapper snapshot, not whichever scratch copy
exists later, when interpreting each observation. The evidence finalizer is also
single-use and must not be rerun against the finalized live ledger.

All Python invocations use `uv run --offline --no-sync` with already provisioned
environments. The driver uses the primary application's environment; the child
explicitly selects `C:\dev\cst-studio-mcp`. No worktree environment is created or
synchronized. The native-free binding/guard checks can be inspected or run without
CST, but are not new authorization to start a peer or replay native work.
