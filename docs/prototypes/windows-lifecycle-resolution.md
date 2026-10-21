# Accepted Windows Controller lifecycle design

**Design resolution for [issue #14](https://github.com/GoncaGomes/cst-agentic/issues/14).
Disposable evidence, not production implementation or readiness certification.**

This document is the current decision summary. Earlier reports remain historical
records. Their local-only notices and publication flags describe their recording
time, not the later publication authorization below. Consumed sources and evidence
are preserved, including failed attempts and the stopped verifier ledger.

## Human acceptance and publication authorization

After reviewing the recommendation to stop experimenting and resolve a restricted
lifecycle design, the human replied **"Do it, I agree with you"**. This accepts the
remaining evidence limits and authorizes artifact publication, a qualified issue
resolution, the parent-map update and closure of issue #14. It does not authorize
a merge, production implementation, further experiments or closure of the separate
acceptance/handoff ticket. See the
[acceptance record](windows-lifecycle-resolution-evidence/accepted-resolution.json).

## Selected design

1. **Retain the installed public MCP stdio transport and SDK.** No private lifetime
   patches, custom preservation hooks or dependency change are selected. The
   application owns the SDK loop, one serialized protected dispatch path and both
   SDK context lifetimes. Enter and exit each context in its owning task.
2. **Support only newly Controller-launched CST instances for this route.** They
   are session-bound. There is no survival promise after normal application exit
   or a crash. Existing-instance attachment remains blocked until precise targeting
   and its lifetime consequences are established. Connect-to-any is not a fallback.
3. **Task completion does not authorize closing CST.** A Controller session can
   contain multiple tasks. Normal application exit still requires warnings about
   unsaved work and active simulations, applicable authorization/confirmation, and
   a bounded orderly cleanup attempt. Session-bound lifetime is not permission for
   a silent destructive exit or a claim of graceful solver shutdown on a crash.
4. **Use the accepted simplified task interaction.** Ordinary prompts wait until
   completion or a pause requiring input. The separate mid-task cancel-task command
   is removed. Explicit simulation stop remains a distinct control, not permission
   for another modeling task or cancellation of already-dispatched work.
5. **Keep bounded, best-effort simulation stop on the same serialized connection.**
   Distinguish intent, queueing, request settlement and independently observed solver
   termination. Stop cannot bypass authorization, target checks, active dispatch or
   uncertainty. It is not an emergency stop and has no universal latency guarantee.
6. **Persist central recovery state before dispatch.** Failure to persist must
   prevent dispatch. Retain unresolved state through process death. Check it on
   startup before opening a transport or admitting tools. A fresh client is not a
   bypass. No automatic operation replay or marker clearing substitutes for human
   reconciliation. This is a production requirement supported by a fixed-location
   disposable demonstration, not an implemented general recovery store.
7. **Keep bounded cleanup and visible failures.** Preserve primary errors through
   context unwinding. Do not suppress cleanup exceptions or report uncertain
   cleanup as success. Budget breaches are evidence requiring review, not permission
   to enlarge allowances or retry. Where solver activity or cleanup is uncertain,
   report that CST may still need direct human intervention.

The provisional complete allowances remain startup/model/ordinary request **120 s**,
launch **480 s**, short wait **45 s**, stop **60 s including queueing**, and total
transport cleanup **30 s**. Termination readback is separately bounded under its
status allowance. Queueing, native preflights/final checks and transport overhead
count. A five-second native wait is not a five-second complete-response guarantee.
These are operating limits with breach handling, not hard real-time guarantees.

The task-interaction and session-bound restrictions explicitly revise the earlier
cancel/leave-open expectations in
[task authorization](https://github.com/GoncaGomes/cst-agentic/issues/11#issuecomment-6303542004)
and [runtime lifecycle](https://github.com/GoncaGomes/cst-agentic/issues/12#issuecomment-6304790260).
Other authorization, targeting, uncertainty and bounded-work safeguards remain.

## Evidence and its strength

| Evidence | Supported conclusion | Qualification |
| --- | --- | --- |
| [Earlier fake-server rounds](windows-lifetime-offline.md), [follow-up](windows-lifetime-followup.md) | Public context ownership, serialized dispatch and several interruption/uncertainty counterexamples are feasible to investigate without CST. | Synthetic observations, not production or native behavior. Historical task-cancel behavior is superseded by the accepted interaction revision. |
| [Native lifetime report and leave-open repeat](windows-lifetime-native.md) | The tested new CST instance did not survive the tested handle-release/public-stdio exit path. Session-bound lifetime is the accepted restriction. | Exact termination mechanism and Job Object ownership were not isolated. This is not a claim that MCP requires CST termination. |
| [One native dipole stop attempt](windows-solver-stop.md) | Stop queued 4.079 s, settled 0.015 s after dispatch, then independent idle was observed 4.203 s later while CST remained alive. Native messages included `Solver run aborted.` | One aborted fixture, not numerical success, exact termination latency or worst-case responsiveness. 38/50 calls and 39.586/1,800 s, no retry. |
| [Failed first lifecycle round](windows-lifecycle-final.md) | Preserved an incomplete attempt and exposed an observer race. | It is not relabeled as a passed round. |
| [Corrected lifecycle checks](windows-lifecycle-retry.md) | Controlled whole-application exit with pre-dispatch persistence, fresh-process restart blocking, partial-startup failure, timeout and uncooperative-shutdown observations. | Four unique synthetic cases, 22.530238 s cumulative, no scenario retry. The startup-refusal verifier spelling error was corrected from saved evidence. The raw stopped ledger is retained. |

The corrected checks observed all 31 held process handles terminated before their
scratch release phase. Expected primary failures remained visible through context
exits. Cleanup measured 0.375 s, 2.031 s and 2.047 s. The three-second startup timer
was observed after 3.063 s. The scheduling overshoot is recorded, not hidden.
No new CST, solver or model endpoint execution occurred in those lifecycle checks.

Source inspection of the installed Windows SDK describes kill-on-close Job Object
handling and an assignment race. This is **source-derived**, not identification
of the exact SDK job governing a particular observed CST process.

## Accepted evidence limits

- **Exact SDK Job Object ownership remains unknown.** The resolution preserves
  that limitation rather than claiming the original isolation requirement passed.
  The accepted session-bound route makes no preservation guarantee that depends
  on proving a particular job mechanism.
- Fake-peer lifecycle results do not validate native CST failure recovery, the
  normal server entry point/watcher or the production Controller/client wrapper.
  Production implementation must validate its actual wrapper and safety path.
- No power-loss/disk-failure durability, concurrent-session lease, general recovery
  clearance procedure, induced SDK cleanup exception or unkillable-process behavior
  was established. Cleanup measurements are not universal guarantees.
- Stop behind a genuinely long native launch and actual native transport
  uncertainty remain unverified. The accepted serialized best-effort restriction
  applies. An uncertain client admits no further status or stop calls.
- The dipole attempt does not establish numerical accuracy, successful completion,
  resource headroom or the exact stage reached in solver time stepping.

These limits are human-accepted restrictions on this design decision. They do not
turn missing evidence into verification. No further experiment is required by this
resolution. New implementation or acceptance work must not silently broaden them.

## Handoff boundary

Issue #14 is resolved as the selection of a restricted public transport/lifecycle
design with linked disposable evidence. This is not a claim that the Controller
has been implemented or that the whole planning map is complete.
[Acceptance gates and implementation handoff](https://github.com/GoncaGomes/cst-agentic/issues/13)
remain separate. No PR or merge is intended for this artifact branch.

All native targets, wrappers, finalizers and live scenario drivers are consumed.
Publishing source for auditability does not authorize replay, resetting ledgers,
reusing targets, filling unused counters or bypassing recovery gates.
