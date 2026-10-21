# Corrected native-free lifecycle checks: four supported design observations

**THROWAWAY / LOCAL ONLY / NOT PRODUCTION / NOT A TICKET RESOLUTION.**

Decision: [Verify Windows transport lifetime and bounded solver-stop behavior](https://github.com/GoncaGomes/cst-agentic/issues/14),
under [Wayfinding: specify the first usable CST Controller](https://github.com/GoncaGomes/cst-agentic/issues/4).

## Outcome

**All four missing lifecycle checks now have supporting synthetic evidence.**
Four unique scenarios executed once each, in **22.530238 seconds cumulatively**
including outer uv invocation and cleanup, within the authorized 300 seconds.
One verifier defect required saved-evidence re-verification and continuation to
the two untouched cases; **no scenario was repeated**. The raw blocked ledger
remains unchanged, distinct from the independently derived successful verification.

No CST, solver or model endpoint ran. No production Controller/client or normal
CST MCP server entry point was executed or changed. All 31 tracked process-handle
observations ended in termination **before** the corresponding scratch containment
release, with no handle-open coverage gaps recorded. No manual intervention is
pending. All **203** files in the continuation's prior-evidence baseline remained
unchanged, including the earlier failed round and both native ledgers.

## Authorization and what changed

The human said **"Fix it and rerun the missing lifecycle cheks"**. The stated scope
was a fresh native-free replacement, four scenarios and five minutes including
cleanup, preserving all consumed targets and evidence. See
[authorization](windows-lifecycle-retry-evidence/authorization.json).

New disposable code only:

- [Replacement driver](../../src/cst_agentic/windows_lifecycle_retry.py): gates the
  pre-crash liveness check on absence of crash permission. Expected post-crash
  termination no longer causes a false pre-crash failure. Records fixed authored
  failure categories, source locations and exception types, never raw error values.
- [Six in-memory regressions](../../src/cst_agentic/windows_lifecycle_retry_checks.py):
  the actual observer condition failed on the unmodified copy, then passed after
  the fix. Pre-crash liveness remains required; permission/snapshot is not duplicated;
  restart is not granted crash permission; external error text is not retained.
- [Continuation driver](../../src/cst_agentic/windows_lifecycle_remaining.py): admits
  only the two cases not yet run and charges their execution against the same
  cumulative 300-second budget. Resolves the public exception name using
  `mcp.MCPError.__name__`, rather than guessing its capitalization.
- [Saved-evidence regression](../../src/cst_agentic/windows_lifecycle_remaining_checks.py):
  the actual verifier failed on the old spelling and passed with the public SDK
  class name, against unchanged captured startup-refusal evidence. No application,
  peer or SDK context was started by this check.
- The [read-only process observer](../../src/cst_agentic/windows_lifecycle_final_processes.py)
  was reused unchanged. Neither the failed driver nor any consumed source was edited.

All Python invocations used `uv run --offline --no-sync` and the existing project
environment. Installed MCP **2.3.0**, AnyIO **4.15.1**. Child environments contained
SDK-default Windows execution settings and explicit offline/virtual-environment/
UTF-8 settings only. No dotenv/provider client, ambient credential configuration,
server stderr or unrelated window content was loaded/exported. Process evidence
contains only the selected fake ancestry, basenames, creation times and exact-handle
observations, not environment blocks or command lines.

## Results

| Scenario | Supported observation | Measured application cleanup |
| --- | --- | --- |
| Crash/restart | In-flight marker persisted before protected fake work; peer independently checked it. Whole disposable application exited with observed code **23**. A fresh process refused **work, status and stop** before opening an SDK transport. Marker remained; no settlement or operation replay. | Abrupt crash: orderly cleanup not applicable. Seven application/peer-chain handles and three restart-chain handles terminated. |
| Partial startup failure | Peer refused initialization. Public **`MCPError`** remained visible through both context exits and final nested exception groups. Application reported failure, not success; no tool dispatched. | **0.375 s** |
| Startup timeout | Peer deliberately stalled initialization. Requested 3-second startup timeout was observed after **3.063 s**, with `TimeoutError` retained through final failure reporting. No tool dispatched. | **2.031 s** |
| Uncooperative shutdown | Peer received stdin EOF and explicitly refused normal exit. Public transport teardown completed; peer/launcher chain terminated without a normal-exit event. The deliberately raised `SyntheticTaskFailure` was preserved, not reported as success. No tool dispatched. | **2.047 s** |

For each of the three unwinding scenarios, both SDK contexts entered and exited
in the same owning task. The final exception-group leaves retained the primary
failure without an additional observed cleanup exception. This does **not** mean
that an SDK cleanup exception was deliberately induced and tested.

The 3-second timeout overshot by approximately **63 ms**. This is recorded, not
hidden or used to enlarge the deadline. A scheduled timeout is not an exact
wall-clock completion guarantee. The separate 10-second experimental cleanup
allowance was met in all three cases.

Conservatively charging all per-case overhead plus outer invocation overhead to
each phase separately produced the following bounds (these are not summed):

| Case | Startup upper bound | Cleanup upper bound |
| --- | ---: | ---: |
| Startup refusal | 4.566 s | 3.801 s |
| Startup timeout | 6.605 s | 5.573 s |
| Shutdown refusal | 4.527 s | 5.371 s |

These synthetic measurements fit the provisional 120-second startup and
30-second total cleanup allowances; they are not native CST performance guarantees.

## Verifier correction and execution accounting

The replacement's first segment (`final-02`) executed crash/restart successfully,
then the initialization-refusal case. Its verifier incorrectly expected
**`McpError`**; the installed SDK's exported class is **`MCPError`**. The actual
error was preserved, cleanup completed in 0.375 s and all seven tracked handles
were dead, but the spelling mismatch caused a recorded verifier stop.

That stop and its source remain intact. A corrected verifier using the public
class name was checked against the saved evidence; it retained all original
failure, owner-task, zero-dispatch, budget and process-termination conditions.
It did not suppress the original error or rerun either executed scenario.

Only the untouched timeout and shutdown-refusal cases were executed in the
continuation (`final-03`). Its admission rejects repeated case names and subtracts
the earlier execution from the same budget. These are two execution segments of
the same four-case authorization, not another four-case round or a new time budget.

- Segment 02: **9.144360 s**, two scenarios, raw status `blocked_review_required`.
- Segment 03: **13.385878 s**, remaining two scenarios, raw status
  `completed_synthetic_observations`.
- Cumulative: **22.530238 s / 300 s**, **four unique cases**, **zero scenario retries**.
- One synthetic tools/call total, in the crash case. Restart admitted no tools.
- In-memory regressions, static preparation, saved-file verification and report
  writing are not scenario execution and did not start peers or SDK contexts.

## Evidence and verification

- [Combined independent verification, metrics and file hashes](windows-lifecycle-retry-evidence/verification.json).
- Segment 02: [raw observations](windows-lifecycle-retry-evidence/attempt/observations.json),
  [unchanged blocked ledger](windows-lifecycle-retry-evidence/attempt/round.json),
  [exact executed sources](windows-lifecycle-retry-evidence/attempt/sources/).
- Crash case: [pre-crash observation](windows-lifecycle-retry-evidence/attempt/crash_restart/observer-precrash.json),
  [restart refusal](windows-lifecycle-retry-evidence/attempt/crash_restart/restart-result.json),
  [retained recovery marker](windows-lifecycle-retry-evidence/attempt/crash_restart/central-recovery.json).
- [Startup-refusal application outcome](windows-lifecycle-retry-evidence/attempt/partial_startup_failure/app-result.json).
- Segment 03: [raw observations](windows-lifecycle-retry-evidence/continuation/attempt/observations.json),
  [exact executed sources](windows-lifecycle-retry-evidence/continuation/attempt/sources/),
  [cumulative outer timing](windows-lifecycle-retry-evidence/continuation/attempt/outer-observation.json).
- [Timeout outcome](windows-lifecycle-retry-evidence/continuation/attempt/startup_timeout/app-result.json),
  [shutdown-refusal outcome](windows-lifecycle-retry-evidence/continuation/attempt/stalled_shutdown/app-result.json),
  [EOF/refusal events](windows-lifecycle-retry-evidence/continuation/attempt/stalled_shutdown/peer-events.jsonl).
- Observer regression [red](windows-lifecycle-retry-evidence/regression-red.json) /
  [green](windows-lifecycle-retry-evidence/regression-green.json).
- Saved-evidence verifier [red](windows-lifecycle-retry-evidence/continuation/regression-red.json) /
  [green](windows-lifecycle-retry-evidence/continuation/regression-green.json).
- [One-time wrappers and combined capture script](windows-lifecycle-retry-evidence/wrapper-source/),
  [continuation wrapper](windows-lifecycle-retry-evidence/continuation/wrapper-source/).
- Earlier failed attempt remains [unchanged history](windows-lifecycle-final.md).

Ruff lint/format, AST/compile preparation and PowerShell wrapper parsing passed.
Import-order and long-line findings in new helpers were corrected before their
respective executions. Byte-exact capture and independent checks passed, including
source identities, marker/work/crash order, observed exit codes, fresh-process
blocking, expected exception leaves, task ownership, all observed chain exits,
four unique admissions, cumulative time and 203 unchanged baseline files.
No production test suite was run. Capture scripts and execution targets are consumed.

## What remains for human review

This is now positive evidence for the **proposed public-SDK lifecycle design**:
persist before dispatch, retain unresolved state through process death, refuse
tools on restart before transport startup, keep context ownership in one task,
and preserve failures through bounded observed cleanup.

Review the remaining evidence limits before a resolution:

1. **Exact SDK Job Object ownership remains unisolated.** Observed process exits
   do not identify the termination mechanism or establish preservation behavior.
2. These are fake-peer/disposable-application observations, **not production
   implementation or native CST failure-recovery validation**. The existing
   production client's wrapper has not been validated or changed by these tests.
3. No power-loss/disk-failure durability, concurrent-session lease, recovery-marker
   clearance procedure, induced SDK cleanup exception or unkillable-process case
   was tested. Measured timing is not a universal guarantee.
4. Earlier native limits remain: normal-server-entry-point behavior, long native
   launch stop latency and actual native transport uncertainty were not established.
   The already accepted session-bound/serialized best-effort-stop restrictions
   remain unchanged; this round does not expand them.

No new native experiment is proposed by this report. The next step is **human
review of this evidence and the explicit limits**, not automatic production work
or another test round. Issue #14 remains open; nothing was published, committed,
pushed or closed. Broader implementation acceptance/handoff remains separate.
