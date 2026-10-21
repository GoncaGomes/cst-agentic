# Windows transport lifetime: offline prototype, first round

**THROWAWAY / NOT A RESOLUTION / NOT PRODUCTION.**

Later, separately authorized evidence: [two follow-up lifetime probes](windows-lifetime-followup.md)
observed delayed fake-descendant termination after both normal and escalated
cleanup. The first-round observations below are retained unchanged as history.

Question: which public Windows transport/lifetime strategy can preserve CST on
leave-open exit while retaining bounded, guarded interruption and solver-stop
behavior?

Decision ticket: [Verify Windows transport lifetime and bounded solver-stop
behavior](https://github.com/GoncaGomes/cst-agentic/issues/14).
Runtime contract: [Choose controller runtime boundaries and conversation
lifecycle](https://github.com/GoncaGomes/cst-agentic/issues/12#issuecomment-6304790260).

## Human-agreed scope

The human chose **Offline first**: at most eight local fake-server/process
scenarios, at most 15 minutes of experiment execution, no CST access, solver, or
institutional endpoint requests. Exactly eight scenarios ran in **8.906 seconds**
according to the driver's monotonic clock. No connected follow-up is authorized
by this round. Do not rerun the driver as an implicit extension of that budget.

The application working copy had existing user changes. All prototype artifacts
are isolated on throwaway branch `prototype/windows-transport-lifetime`, based
on `2f5d809e3ca82b726fac407cc89ba6ab58de786d`. No production files were changed,
no dependency was changed, and no PR/merge is intended.

## Artifacts and reproduction

- [Offline observation driver](../../src/cst_agentic/windows_lifetime_prototype.py).
- [Disposable PowerShell descendant](../../src/cst_agentic/windows_lifetime_fake_child.ps1).
- [Double-clickable discussion sketch](../../src/cst_agentic/windows_lifetime_prototype.html).
- [Machine-readable observations](windows-lifetime-observations.json).

After obtaining a fresh experiment budget, from a checkout with the installed
project environment, run one command in PowerShell:

```powershell
uv run --offline --no-sync python .\src\cst_agentic\windows_lifetime_prototype.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
```

The recorded run used the existing environment at `C:\dev\cst-agentic` and an
absolute driver path in the separate worktree. `uv --offline --no-sync` prevents
dependency resolution/downloads or environment changes. A clean checkout needs
dependencies provisioned separately; this is not a self-installing executable.

The driver has no CST executable setting, does not load `.env`, and uses a fixed
synthetic tool inventory and empty argument schemas. Every synthetic tools/call
uses the same guarded serialized route. The fake model implements the Agents
SDK's public `Model.get_response`; it never constructs a provider client or uses
Runner. Global tracing and per-response tracing are disabled. Child environments
contain only the SDK-default Windows execution variables and the existing uv
environment selection. Fake-server stderr is discarded rather than forwarded.

The fake child is PowerShell, not CST or a numerical solver. It self-exits within
60 seconds if its stop flag or transport teardown does not stop it. The crash
helper writes a synthetic marker and calls `os._exit(23)` on **itself only**.
There are no arbitrary PID/tree termination commands. The driver holds an exact
Windows process handle while observing each fake child; it does not identify a
process by a reused PID during teardown.

The HTML is an in-memory explanatory state model with free play and walkthroughs.
It neither reproduces SDK behavior nor counts as connected evidence. It has not
been visually reviewed by the human yet.

## Observed results: synthetic only

| Scenario | Observation | Qualification |
| --- | --- | --- |
| Leave-open teardown | Child alive before transport exit; immediate post-exit sample also alive. Cleanup 0.016 s. Child reported membership in some Job Object. | **Inconclusive lifetime result.** No post-exit survival window, exact SDK Job Object identification, or owned-server process-exit measurement. |
| Authorized close | Fake close was received and its specific child had exited before transport teardown. Cleanup 0.015 s. | Synthetic flag-based graceful close, not `cst_disconnect`, CST close, or solver behavior. |
| Partial startup cancellation | Initialization exceeded the synthetic 1.5 s startup allowance; same-owner scope cancellation returned after startup plus cleanup in 2.250 s; no tools/call reached the server. | Startup and cleanup are not timed separately here; absence of leaked server/uv descendants was not independently established. |
| Cancel active batch | Cancel intent arrived while first work was active. First call settled received in 0.609 s; second was not dispatched. Server saw one `work`. Matched output IDs `fake-0`, `fake-1` retained. | No active-call cancellation or Ctrl+C. Fixed synthetic schemas/IDs, not full real-catalogue validation. |
| Stop after short wait | Stop waited 0.500 s before dispatch; accepted in the same recorded clock tick; separate exact-handle termination observation followed 0.063 s later. A subsequent fake status reported not running. | Acceptance, dispatch delay and termination are distinct. Clock resolution rounds sub-tick durations; zero does not establish zero latency. |
| Stop behind launch | With a synthetic 0.250 s total stop allowance, stop expired in the queue after 0.266 s; launch settled in 0.922 s. Server saw only `launch`. | Scheduling can overrun a nominal timer. No stop dispatch, automatic retry, allowance increase, or emergency-stop promise. |
| Uncertain operation | Work exceeded 0.150 s; uncertainty latched. Subsequent status and stop were not dispatched; server saw only work. Recovery marker retained. | Demonstrates the fake guard, not a new exception to the real client's latch. |
| Crash marker / restart | Disposable helper exited 23 after fsync + replace of its marker. A newly constructed guard found the marker and refused status. Server saw no tools/call. | Abrupt exit of a marker-writing helper, not a whole Controller crash during native dispatch. No power-loss durability, per-user lease, corrupt-marker or real application startup claim. |

Normal fake startup (initialize plus catalogue) ranged from 0.141 to 0.188 s;
normal cleanup ranged from 0.015 to 0.515 s. The driver used public
`stdio_client`, `ClientSession` and AnyIO scopes with entry and exit in **one
owner task**, including startup timeout. No cleanup exception was caught and
reported as success. Worker control tasks do not enter or exit SDK contexts.

This is a prototype of that public ownership pattern, **not execution of the
existing `CstMcpClient` context wrapper**. That wrapper's use of `asyncio.wait_for`
around context exits and suppressed cleanup exceptions is not validated by this
run, nor changed here.

## Source-derived constraints, not native observations

Host: **Microsoft Windows NT 10.0.26300.0**. Inspected installed MCP SDK
**2.3.0**, OpenAI Agents SDK **0.24.0**, AnyIO **4.15.1**.
The installed Windows transport source creates a kill-on-close Job Object and
closes it after its normal shutdown sequence, even if the server exited
gracefully. Its public stdio parameters expose no preserve-descendants switch.
The same source notes a spawn-to-job-assignment race: children created before
assignment do not retroactively join the job.

The fake child's `IsProcessInJob(current_process, NULL)` result establishes only
membership in **some** job, not this SDK job, its ownership, inherited nesting,
or successful assignment of the uv/Python process chain. The immediate live
sample does not distinguish delayed job termination from genuine survival.
An intermediate uv process and host job membership must not be silently ignored.
**Neither the SDK source nor this sample settles CST survival.**

Before another run, improve the observation protocol: record the known spawned
chain and exact handle lifetimes, observe process exit/survival over an agreed
window with timestamps, and identify specific job ownership using supported OS
interfaces or explicitly report that evidence unavailable. Do not read or alter
SDK private job registries and do not call an OS `any job` result exact membership.
This is an observation gap, not permission to claim that disabling tree cleanup
is safe or to adopt the capability runner's private patches.

Installed source SHA-256 (source read, not modified):

| File | SHA-256 |
| --- | --- |
| `mcp/client/stdio.py` | `C4A9DE7119F35366037DBF8D51AB5CB6438E15E120730F65F32CDACDEEA9328A` |
| `mcp/os/win32/utilities.py` | `98E87C776A14CF326E63F8DA007119156D3AD643AE7FBF27E9B6E6EF1DC534BF` |

Executed artifact SHA-256:

| File | SHA-256 |
| --- | --- |
| `windows_lifetime_prototype.py` | `6CF1A0A7C3463DB1B3E93C4844BF6EEFD7DD1F768C4E8921F8F144DEDB4A9173` |
| `windows_lifetime_fake_child.ps1` | `82B0B5D9140F76759779D19A05A503D29BD27BB68AA3B3B367B92B2E5EA5733B` |
| Raw `observations.json` (copied byte-for-byte) | `31E39741BCB245BB4EAE68002AADBC70BDF06DB30D351AFD3C5FB3AE36FD8EAD` |

After the round, the driver received whitespace-only formatting to pass the
repository formatter. An independent AST comparison confirmed the captured
driver has the identical executable AST to the executed source; no scenario was
rerun. Captured driver SHA-256:
`92E96AB73F31402173EBFF66FC48632FB45DC2FD21DF00AA2BA8F0B1385FBD95`.

## What remains undecided / unverified

No public CST lifetime strategy is selected. Possibilities to evaluate, not
decisions: independently owned hosting through a supported public transport;
or a narrow public SDK lifetime-policy change if ordinary stdio cannot satisfy
preservation. Actual server support and both normal/crash lifetime behavior
would need evidence before either could be selected.

The ticket stays **open and claimed**. No map resolution/index entry is due.
The following cannot be inferred from this round:

- CST instance ownership or exact job membership; live leave-open survival;
  authorized CST/project close; unsaved-work handling; solver continuation.
- Precise existing-instance attachment. It remains a blocked case until its
  public prerequisite exists; `any` is not a fallback.
- Native wait/launch/stop latency, independent solver termination evidence, or
  observed behavior when a native request becomes uncertain.
- The complete provisional real allowances: startup/model/ordinary 120 s,
  launch 480 s, short wait 45 s, stop 60 s, cleanup 30 s total. Scaled fake
  delays are counterexamples/logic evidence, not native performance validation.
- Complete Controller crash/restart recovery, durable production state, lease,
  partial failures, provider cleanup, or physical power-failure durability.
- Browser interaction/visual review of the HTML; actual institutional model
  tool calling or the broader acceptance/handoff decision.

Checks in this round: Python artifact Ruff lint and format checks; JavaScript
syntax check with `node --check`; post-format Python AST equivalence; eight
offline executable scenarios; observation JSON parse/completeness and exact-copy
fingerprint; staged Git whitespace check. The initial format check failed;
whitespace was corrected and the check passed. No production correctness is
claimed, and the production test suite was not run.
