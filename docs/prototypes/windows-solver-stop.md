# Windows solver stop: one disposable dipole attempt

**THROWAWAY / LOCAL ONLY / NOT A RESOLUTION / NOT PRODUCTION.**

Decision: [Verify Windows transport lifetime and bounded solver-stop behavior](https://github.com/GoncaGomes/cst-agentic/issues/14), under
[Wayfinding: specify the first usable CST Controller](https://github.com/GoncaGomes/cst-agentic/issues/4).
No PR or merge is intended. No commits, pushes or GitHub changes are authorized.

## Confirmed scope and partial contract revisions

The human confirmed removing the separate mid-task **cancel task** command.
Ordinary task prompts are unavailable until completion or a pause requiring input.
An explicit simulation-stop control is the exception being investigated, not a
new ordinary modeling task. This revises the earlier interruption requirement;
it does not redefine glossary terms or claim the previous cancel interface was tested.

The human accepts the single serialized connection and **no emergency-stop guarantee**.
If stop support proves disproportionately complicated, deferral remains an option
for human review, not an automatically selected conclusion.

The already accepted session-bound lifetime policy remains in
[the native lifetime report](windows-lifetime-native.md#human-confirmed-lifetime-restriction--local-only).
Task completion does not authorize CST closure in the supported application;
this experiment separately authorizes closure of its owned disposable instance.

The human approved the exact operation proposal with **"Yes"**:
[authorization](windows-solver-stop-evidence/authorization.json).
One new CST 2025 instance, exactly
`C:\Users\Lenovo\AppData\Local\Temp\opencode\cst-solver-stop-dipole-01\dipole.cst`.
At most **50 tools/call**, **1,800 seconds total connected experiment time including
cleanup**, one asynchronous launch and at most one stop. No automatic retry,
preexisting-file overwrite, alternate target, endpoint request, watcher,
private SDK preservation hook, attachment or production change.

An initial non-overwriting save creates this owned project, followed by one
ordinary save of that same identified project after setup. This does not authorize
replacing an external file or save-fallback replay. Cleanup may terminate the
disposable CST instance and lose partial results. Uncertainty blocks later tools.

## Construction and provenance

- Reviewed upstream remains clean at `a4a177aeb0856dbf0f668f2dc5a8ca06e20ac8c2`.
- Reuse only the literal model/setup from
  [`run_dipole.py`](https://github.com/GoncaGomes/cst-mcp/blob/a4a177aeb0856dbf0f668f2dc5a8ca06e20ac8c2/capabilities_test/04_antenna_simulation/run_dipole.py).
  Its AST is parsed; the historical runner is never imported/executed. Do not
  inherit its blocking solve, analysis/export phases or process-preservation hooks.
- The fixed dipole uses two 74.8 mm copper arms, 0.15 mm radius, 0.30 mm gap,
  a 50-ohm discrete port, 0.8–1.2 GHz, the original mesh/time-domain setup and
  five original monitors. No workload enlargement is authorized to force overlap.
- Driver -> public MCP stdio -> fixed-target disposable peer -> reviewed upstream
  setup/simulation handlers and official CST API. This is not execution of the
  normal server entry point, its watcher, or the production Controller/client.
- Only fixture connect/create/save/identity/instance-close are custom lifecycle
  tools. New-instance creation and non-overwriting save avoid upstream save retries.
  Upstream session handle slots are populated only with our directly created
  native objects; no existing-instance adoption or private SDK lifetime hooks.
- Native API entry stays on one dedicated worker. Both driver and peer enforce
  the fixed operation sequence. The driver owns both public SDK contexts in one
  task; its one protected tools/call path serializes requests and records durable
  in-flight markers and complete queue-inclusive allowances.
- Stop intent is generated while the wait is pending, but waits for that same
  dispatch lock. It cannot cancel the active wait or bypass uncertainty. Natural
  completion skips stop; no relaunch follows. Up to three start observations and
  three independent termination observations are allowed. No observed startup is
  inconclusive, not permission to close an assumed-settled solver.
- The child gets only SDK-default Windows execution settings and explicit offline,
  CST 2025/manual/fixed work-directory settings. No `.env`, provider, ambient Python
  path override, server stderr or foreign window text is loaded/exported.
  Three fixed setup/readback VBA blocks are admitted, not arbitrary raw VBA input.
- Read-only OS process snapshots and exact handles observe only the owned chain.
  Any-job membership is not exact SDK Job Object ownership. No process kills or
  UI automation are added. Bounded native log evidence is scoped to the owned project.

## Bounds and checks

Complete startup/ordinary operations: 120 s. Launch: 480 s. Five-second native
wait request: 45 s complete. Stop: 60 s including queueing. Transport cleanup:
30 s total. Independent status readback has its own 120 s allowance.
Driver startup is conservatively limited to 100 s, cleanup to 25 s; operation
admission retains 45 s for cleanup, OS observation and finalization/outer headroom.
The outer wrapper measures uv overhead and checks conservative complete allowances.

The connected root and wrapper launch marker are exclusive one-time admissions.
The old lifetime ledgers/targets are untouched. Exact executed sources, fixture,
approval, checked catalogue and guard results are snapshotted at admission.

Native-free checks exercise real upstream schemas, fixed ordering, enlarged-scope
rejection, replay/overwrite/time/call guards, received failure and uncertainty
latching, sequential queued stop, natural-finish skipping, bounded verification,
unobserved-startup refusal, output filtering and logging. They use private
temporary fixture copies; no peer, CST or model is started by checks.

All **17 native-free checks passed**, as did Ruff lint/format and PowerShell 5.1
wrapper parsing. The first lint pass found two long lines (and fixed three import
issues); these were corrected before the checks and native admission. The public
CST 2025 help confirms that `Project.save()` without a path saves the current
filename, `start_solver` is asynchronous and `abort_solver` requests abort.
Two failed help-inspection commands (quoting, then terminal Unicode encoding)
were corrected without importing or executing CST. They consumed no MCP calls.

- [Checked catalogue](windows-solver-stop-evidence/catalogue.json)
- [Native-free results and source identities](windows-solver-stop-evidence/native-free-checks.json)
- [Prior evidence/source fingerprints](windows-solver-stop-evidence/prior-evidence-sha256.json)
- [One-time wrapper source](windows-solver-stop-evidence/wrapper-source/run-dipole-stop-once.ps1)
- [Driver](../../src/cst_agentic/windows_solver_stop.py),
  [peer](../../src/cst_agentic/windows_solver_stop_peer.py),
  [fixed plan](../../src/cst_agentic/windows_solver_stop_plan.py),
  [checks](../../src/cst_agentic/windows_solver_stop_checks.py),
  [read-only process observer](../../src/cst_agentic/windows_solver_stop_processes.py).

## Results

**The single approved attempt completed: stop queued behind active work, returned
before the solver stopped, and separate native readback established idle while CST
remained alive. The owned project's messages include `Solver run aborted.`**

Executed once on 2026-10-21, outer start `2026-10-21T12:30:28.3213409Z`.
New CST 2025 DE PID 30660; no pre-existing DEs were reported. Independent live
filename/sole-project/associated-DE checks matched throughout. Units and the two
copper-arm names/material assignments were independently read back. Other setup
handler responses establish acceptance, not exhaustive applied-state verification.

| Observation | Measured result |
| --- | --- |
| Asynchronous launch request | Received `started` in 0.125 s; subsequent native status reported `running=true`. |
| Configured five-second wait | Complete request 4.156 s; returned `running=true` after three native polls. Five seconds was a requested maximum, not an exact duration. |
| Stop intent while wait pending | Wait remained active when intent arrived; stop waited 4.079 s before dispatch on the same protected connection. |
| Stop request settlement | Received `executed`, command `stop`, 0.015 s after dispatch; 4.094 s including queueing. |
| Independent activity checks after stop response | First and second still reported `running=true`; third reported `running=false`. First idle observation was 4.203 s after the stop response, 8.297 s after intent. |
| Native project messages | `Solver run aborted.`; not a claim of numerical success. |
| CST lifetime before cleanup | Exact owned DE handle remained alive at the idle observation and before authorized instance close. |
| Authorized orderly close / transport cleanup | Close returned in 5.094 s; owned DE and recorded native descendants were already terminated before transport exit. Transport cleanup 0.547 s. |
| Post-cleanup observation | All nine tracked exact process handles were terminated by the 0.062 s observation sample. No current-instance confirmation is pending. |

These are sampled observations, not exact solver termination latency. In
particular, request acceptance did **not** mean immediate termination. The
historical untimestamped `run_info.last_reported_state` changed from `RUNNING`
to `ERROR`; it is not treated as a current numerical verdict. The running flag
and owned-project abort message are the relevant evidence. Activity was observed
during the solver workflow; no claim is made about how far time stepping progressed.
There was no independently recorded UI trace or new human UI-action confirmation.

### Accounting and verification

- **38 of 50 tools/call**: all received; one launch, one wait, one stop, three
  independent post-stop status checks. No failed/uncertain call or replay.
- Driver **37.281 s**; outer uv invocation **39.585719 s**, below 1,800 s.
- Startup **1.875 s**; all measured outer overhead conservatively added gives
  **4.179719 s**, below 120 s. Cleanup with the same conservative treatment is
  **2.851719 s**, below 30 s. Every received complete request met its allowance.
- The 30-minute bound concerns this connected attempt; earlier human discussion
  and native-free harness preparation were not connected experiment time.
- Native-free post-run verification checked call/peer-event agreement, fixed
  ordering, source/fixture/authorization hashes, request bounds, queue overlap,
  independent idle before close, scoped exact-handle terminal observations, and
  byte-exact evidence capture. **65 prior evidence/source files, including the
  consumed lifetime ledger, remained unchanged.** The finalizer's initial lint
  findings were corrected before its one execution; no native effect was replayed.
- No production suite, model/endpoint request or whole-Controller crash test ran.

The project messages also included a high-memory warning, a PML reference-frequency
notice and CAD-processing/healing notifications. This aborted workload does not
establish fixture numerical accuracy, healthy completion or resource headroom.
There is no authorization to tune the fixture or repeat the run to investigate them.

### Evidence

- [Verification, derived metrics and byte hashes](windows-solver-stop-evidence/verification.json)
- [Native observations](windows-solver-stop-evidence/attempt/observations.json)
- [Peer events](windows-solver-stop-evidence/attempt/peer-events.jsonl),
  [settlement audit](windows-solver-stop-evidence/attempt/settlements.jsonl)
- [Owned native messages](windows-solver-stop-evidence/attempt/owned-native-log.json)
- [Outer timing](windows-solver-stop-evidence/attempt/outer-observation.json),
  [one-time wrapper admission](windows-solver-stop-evidence/attempt/wrapper-launch.json),
  [final ledger](windows-solver-stop-evidence/attempt/round.json)
- [Exact executed sources and fixture snapshot](windows-solver-stop-evidence/attempt/sources/)
- [One-time native-free evidence finalizer](windows-solver-stop-evidence/wrapper-source/finalize-dipole-stop-evidence.py)

Raw evidence remains at
`C:\Users\Lenovo\AppData\Local\Temp\opencode\cst-solver-stop-dipole-01`.
Scoped Git attributes preserve captured evidence/source bytes and CRLFs.

## Interpretation and remaining decision

This is positive evidence for a **best-effort bounded stop through the same
serialized connection**, not an emergency-stop guarantee. It supports retaining
that restricted feature rather than deferring it merely because serialization
exists; the human subsequently accepted that restriction below. Do not claim
universal timing from one fixture. The native abort message supports an aborted-run interpretation; sole
causation independent of every possible UI/native event was not isolated.

### Human acceptance — local only

Following review of these results and the recommendation, the human replied
**"I accept"**. The first version will retain simulation stop as a **bounded,
best-effort control through the same protected serialized connection**, with no
emergency-stop guarantee. Queueing, stop-request settlement and independent
termination evidence remain distinct. The accepted contract retains the applicable
authorization/target/uncertainty gates and complete allowances; it does not turn
this fixture's measurements into universal timing guarantees. If stopping cannot
be sent or verified, report the limitation and the possible need to intervene in CST.

The prior removal of mid-task task cancellation remains in force; stop is the
control exception to ordinary task-input blocking. The
[acceptance record](windows-solver-stop-evidence/accepted-stop-contract.json)
captures this partial design decision separately from executed observations.
No additional execution, publication, ticket closure or waiver of the remaining
lifecycle obligations follows from this acceptance.

The test does not exercise stop behind a genuinely long launch or actual native
transport uncertainty, whole-Controller abrupt-exit/restart recovery, partial
native startup/cleanup failure, exact SDK Job Object ownership, or normal server
entry-point/watcher behavior. Existing synthetic checks remain distinctly labelled.
The stop contract is now human-accepted; the remaining lifecycle obligations and
explicit restrictions still need review before resolution of the complete ticket.
Broader acceptance/handoff
remains a separate decision. No issue, map, commit or remote branch was updated.

**This attempt and its wrapper/finalizer are consumed. Do not rerun them, reuse
the project target, fill unused call slots, reset markers or construct a new client
to bypass admission.** New connected work requires new explicit scope and limits.
