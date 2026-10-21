# Windows lifetime follow-up: delayed teardown observations

**THROWAWAY / OFFLINE ONLY / NOT A TICKET RESOLUTION.**

Decision: [Verify Windows transport lifetime and bounded solver-stop
behavior](https://github.com/GoncaGomes/cst-agentic/issues/14).
This follows the [first eight offline observations](windows-lifetime-offline.md),
whose immediate leave-open sample was inconclusive.

## Authorization and scope

The human separately approved **two additional offline lifetime probes, capped
at three minutes**, to clarify post-teardown timing before native testing.
Exactly two probes ran, in **10.656 seconds** including SDK imports. The previous
eight scenarios were not rerun. No CST access, solver,
provider/model request, production change or dependency change occurred.

The experiment budget is consumed. Native work and further executable probes
need a separately agreed scope; this report is not authorization for either.

## Artifacts

- [Follow-up driver](../../src/cst_agentic/windows_lifetime_followup.py).
- [Machine-readable observations](windows-lifetime-followup-observations.json).
- [Unchanged fake peer and guarded tools/call route](../../src/cst_agentic/windows_lifetime_prototype.py).
- [Unchanged self-bounded fake descendant](../../src/cst_agentic/windows_lifetime_fake_child.ps1).

Both probes used the public MCP stdio/session contexts, entered and exited by
one owner task. The fake tool inventory remained fixed; the only tools/call in
each probe was `begin`, through the existing **fake-only** guarded route.

The new observer used documented, read-only Windows Toolhelp/process APIs to
identify the fake chain, open exact process handles, record creation times and
job-membership flags, and observe termination. It did not query command lines,
environment blocks, SDK private state, or arbitrary process trees. No job handle
was duplicated or retained, which could itself delay kill-on-close cleanup.

The tracked chain in each probe was:

```text
observer Python -> uv.exe -> venv Python launcher -> Python fake peer
                                                    -> PowerShell fake descendant
```

The fake peer self-reported its PID and parent PID. Toolhelp confirmed that
parent chain reached this observer and that the fake child belonged to this
peer. Exact handles were opened before teardown and held throughout observation;
post-teardown results are not PID-name matches vulnerable to subsequent PID reuse.

After the public transport context returned, handles were sampled at requested
10 ms intervals until **all tracked processes were dead or five seconds elapsed**.
An observed terminated process cannot later revive through that same handle,
so the window ended early once all were dead. Scratch-only release/stop flags
were written **after** that observation window, not to produce the result.

## Observed results

| Probe | Transport cleanup | Immediate post-teardown observation | Subsequent observation |
| --- | --- | --- | --- |
| Graceful EOF | 0.547 s total; peer wrote EOF and exit events; peer/launchers exited 0. | Peer/launchers dead; fake descendant still alive. | Fake descendant dead at the next sample. Both samples have the same recorded coarse monotonic timestamp; the sub-tick interval is unresolved, **not zero latency**. All exit codes were 0. |
| Peer stalls after EOF | 2.000 s total; peer wrote EOF but no normal-exit event. | Peer and descendant still alive; uv/venv launcher already dead. | All tracked processes dead by the sample **0.031 s** after transport return. All exit codes were 1. |

The stalled peer deliberately ignored EOF in a self-bounded loop so ordinary
SDK cleanup would escalate. No extra native stop, direct tools/call, external
kill command, private SDK patch or replay was used. Every tracked handle was
terminated before scratch cleanup; none remained alive afterward.

These results explain why an immediate live sample is insufficient: the
public context can return before termination of every tracked descendant is
observable. Coarse timestamps and scheduling also preclude a precise termination
latency guarantee. The five-second window is an observation protocol, not a
new application or solver-stop allowance.

## What this settles, and what it does not

**Settled for these fake chains:** neither graceful EOF nor cleanup escalation
preserved the deliberately continuing fake descendant. An immediate live sample
was not evidence of survival. Installed SDK source's Windows tree-cleanup policy
is consistent with the observed deaths, including the forced case's exit codes.

**Not settled:** exact SDK Job Object membership/ownership. All selected
processes **and the observer** reported membership in some job via
`IsProcessInJob(process, NULL)`. This does not identify the SDK's particular job,
prove nesting or eliminate assignment races. No particular job caused a death
solely because the boolean was true. The report does not invent an exact job ID.

**No CST guarantee:** native automation may have a different ownership chain.
No CST process was launched or attached, no project was created, and no solver
ran. The ticket's precise-attachment prerequisite, live leave-open/authorized
close, solver continuation/stop timings, complete real budgets and whole-app
crash recovery remain unverified. No public CST lifetime strategy is selected;
the ticket remains open and claimed, with no map resolution/index update.

The practical consequence for the pending design is to reject an assumption
that ordinary Windows stdio promises to preserve descendants. A connected,
disposable lifetime observation is still necessary before choosing independent
ownership, a supported alternate transport, or a narrow public SDK change.

## Reproduction and provenance

After obtaining a fresh experiment budget, from an existing provisioned project
environment, run only the follow-up driver (not the eight-scenario driver):

```powershell
uv run --offline --no-sync python .\src\cst_agentic\windows_lifetime_followup.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
```

The recorded run used an absolute path in the throwaway worktree and the
existing `C:\dev\cst-agentic` environment: MCP 2.3.0, Agents 0.24.0, AnyIO 4.15.1.
No source was reformatted or changed after execution. SHA-256:

| Artifact | SHA-256 |
| --- | --- |
| Follow-up driver | `930EDC56D7007856BA33517280924796073E10DDA1C410C04AF0F0F634889BC2` |
| Baseline fake peer/guard | `92E96AB73F31402173EBFF66FC48632FB45DC2FD21DF00AA2BA8F0B1385FBD95` |
| Fake PowerShell child | `82B0B5D9140F76759779D19A05A503D29BD27BB68AA3B3B367B92B2E5EA5733B` |
| Raw observations, copied byte-for-byte | `BE6CA7B65ABECCAD607DDC6E5CE3950932B85DC7765767E82191E1716ACABB78` |

Checks: Ruff lint and format; exactly two executable observations; JSON
completeness/source hashes/exact-copy verification; staged Git whitespace.
Initial lint identified two overlong lines, corrected before the experiment.
No production suite or additional process scenario was run.
