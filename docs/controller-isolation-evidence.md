# Historical investigation: superseded Controller isolation requirement

**Historical, not a current delivery prerequisite.** The
[2026-10-27 single-instance/manual-recovery decision](https://github.com/GoncaGomes/cst-agentic/issues/17#issuecomment-6446214034)
supersedes the B-while-A-unresolved requirement investigated below. Complete
multi-instance isolation, independent Windows observers and cross-restart process
continuity are not required for this prototype. All remaining sections describe
the earlier investigation, not current requirements. Current implementation and
limits are in [working-project authorization](controller-project.md).

Research date: 2026-10-26. **Design evidence only; #24 remains incomplete.**
The user selected evidence-source design before implementation. No production
source establishing the complete isolation contract was found in the reviewed
sources. Windows supplies useful identity/accounting primitives, not a CST
containment guarantee. No implementation or new tests were added. Research used
source/documentation reads, not server, endpoint, or CST execution.
Configuration/environment values were not read. Existing offline checks ran
separately; their results do not validate this proposed evidence source.

## Required result

[#24] requires independent application-owned evidence **before opening a
replacement transport**, refreshed after queueing at the final SDK guard. B may
proceed while A's incident stays recorded and A stays blocked, but only when
every incident's instance, effects/files, and potentially continuing activity
are accounted for. Same-instance switching, existing-instance attachment,
shared/aliased routes, unknown launch impact, and missing/stale evidence refuse.
This note proposes a narrow candidate, not a replacement for those requirements.

## Reviewed application facts

- [`controller.py`](../src/cst_agentic/controller.py), `start_task` and
  `_check_route`: route admission precedes client construction; isolation is
  presently a boolean callback, with overlapping/unknown incident routes refused.
  `open_manual_transport` refuses all unresolved incidents; it cannot investigate
  A to obtain the evidence needed to admit its own startup.
- `controller.py`, `DispatchEvidence` and `_dispatch.guard`: the application asks
  for project scope and an instance string, rechecks the route, and rejects an
  instance matching an unresolved incident. These seams do not supply a real
  production evidence source.
- [`mcp_client.py`](../src/cst_agentic/mcp_client.py), `call_tool`: the synchronous
  guard runs after serialization and before the SDK dispatch marker. This is a
  suitable recheck boundary, not a Windows-wide atomic transaction or protection
  against independent target/file changes during subsequent SDK/server work.
- [`recovery.py`](../src/cst_agentic/recovery.py), `Incident` and `prepare`: the
  ledger retains one project location, instance string, operation name, state,
  and human flags, **not the operation's complete effect/activity footprint**.
  Saved `activity_resolved`/`effects_resolved` flags are not independent live proof.
  `reconcile` records human findings; it does not acquire native observations.
- [`project_storage.py`](../src/cst_agentic/project_storage.py), `inspect` and
  `overlaps`: present checks use resolved names and `stat` device/inode identity,
  reject multiple `.cst` entries, and compare equal directories/files. They do
  not enumerate companion effects or establish arbitrary ancestor/descendant
  footprint exclusion. No reviewed equivalence to Windows `FILE_ID_INFO` is
  assumed. [Recovery documentation](controller-recovery.md) explicitly records
  the absence of production identity/isolation adapters.

## Reviewed server facts (source-only, pinned)

Reviewed local Git objects in `C:/dev/cst-studio-mcp`, commit
`a4a177aeb0856dbf0f668f2dc5a8ca06e20ac8c2`; corresponding pinned links below.
These prove wrapper behavior, **not the vendor implementation's guarantees**.

1. [`tools/connection.py`][connection] preserves an already connected session
   even for `mode="new"`. An error-free response is therefore not evidence of
   this request creating a new instance. Its default `any` route is unsuitable.
2. [`session.py`, `connect`][session] calls `DesignEnvironment.new` when exposed,
   otherwise its constructor; `ProcessInfo.pid` supports an observer, while
   returned identity uses `de.pid()`. `newly_started=True` is assigned by the
   wrapper's selected branch. No exact Windows process handle, creation-time
   binding, full activity account, or isolation attestation is returned.
3. The same `connect` implementation adopts an active/first open project when
   the returned environment lists projects. A requested `new` mode and reported
   PID/path do not independently prove exclusive ownership or correct target.
4. `session.py`, `new_project`, silently chooses timestamp-suffixed destinations
   when the target exists or saving fails. `open_project` caches its requested
   path; `save_project` updates that cache. These are not independent verification
   of the actual live project/file or preauthorized fallback destinations.
5. `session.py`, `disconnect`, forgets API references without closing CST; solver
   state uses the CST API and may be unknown. Neither disconnection nor a solver
   idle flag accounts for every possible continuing operation/service.
6. [`tools/project.py`][project] delegates create/open/save and offers offline
   references/scripts. Its project-info result comes from client status, not an
   independent live Windows/project binding. It cannot establish pretransport A
   isolation. Narrow expected-target server support would still be needed.

## What the Windows sources establish—and do not

| Primitive | Reviewed fact | Boundary |
| --- | --- | --- |
| Exact process handle | Creation returns handles valid until closed, even after process exit; a PID is valid only for that process lifetime. [Handles] | A server-reported PID or later PID lookup is not the original handle or proof of launch ownership. |
| `GetProcessTimes` | Queries creation time through a process handle with appropriate access; exit time is undefined while still running. [Times] | PID plus creation time helps distinguish reuse; it does not bind a CST project or inventory other activity. |
| `GetFileInformationByHandleEx(FileIdInfo)` | Returns `FILE_ID_INFO`; compare volume serial plus 128-bit file ID for two open handles on one computer. [File API], [File ID] | Identity is not exclusive access, a complete effect set, a cross-host identity, or a perpetual historical identifier. |
| Job Objects | Group associated processes; ordinary `CreateProcess` children normally join, but breakaway and `Win32_Process.Create` exceptions exist. [Jobs] | **Not filesystem isolation.** No guarantee that work requested through RPC, external services, remote solvers, or already running processes belongs to this job. |
| Job query / process exit | Query accounting includes associated activity; process termination signals that process object and does not terminate its children. [Job query], [Accounting], [Exit] | An empty job or exited DE covers only the independently established membership/scope, not all CST effects. |

The RPC/service limitation is a scope inference from [Jobs], not a claim that
CST necessarily uses a particular escape mechanism. No reviewed vendor source
establishes that all allowed launch/create/open activity remains in descendants,
or identifies every shared file/service touched. Job completion notifications
are not universally guaranteed; [Jobs] also gives specific job-signaling rules,
so do not equate an arbitrary job wait/absence with complete quiescence.

## Candidate evidence source (proposal, not implemented)

Prefer **application-owned admission of a tiny typed operation set**, with a
reviewed effect declaration and independently acquired Windows observations.
Do not add a general broker, unrestricted code execution, or a recovery MCP
channel. The proposed evidence owner would:

1. Establish ownership from the supported new-instance creation path, retaining
   the exact process handle and querying creation time itself. Associate each
   admitted operation with its instance, live project binding, frozen canonical
   arguments, authorization, and conservative effect/activity footprint.
2. Review footprints per supported vendor/version/operation: launch resources,
   project/companion files and directories, temporary/autosave/result/export
   locations, shared resources, and any workers/services/deferred work. Unknown
   effects remain unknown; an allowlist or type annotation cannot prove absence.
3. Acquire file/directory identity through Windows handles, preserve observations
   with provenance, and retain lifecycle/operation generation and acquisition
   order. The source must be independent of the model, user assertions, saved
   recovery flags, and responses from the uncertain transport.
4. Use a job only if supported creation can establish membership **before work
   can escape**, with reviewed breakaway/nesting settings and explicit failures.
   A later snapshot/assignment cannot account retroactively for earlier work.
   A returned `ProcessInfo.pid` alone does not establish such a launch boundary.
5. Treat the durable ledger as an index of obligations, not proof. Existing
   records lack full footprints/provenance; do not invent them from operation
   names or upgrade restored flags into evidence. Missing coverage refuses B.

**Missing source:** the reviewed wrapper exposes no supported atomic creation /
exact-handle ownership contract, independently bound live project identity,
complete effect footprint, or complete activity accounting. The Windows APIs
above cannot supply these vendor facts. No implementable production source is
claimed here, even for this narrow proposal.

## Narrow quiescent-A route: conditional candidate

This may avoid proving safe concurrency with a *still-running* A: prove that
**all independently accounted A activity has terminated**, while its effects
remain unresolved and its incident remains blocking A. It is a candidate only
if the accounting was complete before uncertainty and includes external or
deferred work, or supported vendor guarantees exclude such work for the subset.

- Obtain positive termination observations for retained exact process objects;
  process termination can be asynchronous and pending I/O must finish/cancel.
  A successful termination request is not completion. [Termination]
- For a verified, closed membership scope, query the retained exact job and
  account for members/externally delegated work; prevent new admissions or
  later external assignment. Zero associated active processes alone is not a
  universal no-work-remains certificate. [Jobs], [Job query], [Accounting]
- Missing PID, failed `OpenProcess`, a different creation time, missing/recreated
  job name, or disappearance of the application/server proves **neither complete
  termination nor footprint closure**. Loss of handles/continuity fails closed.
- Application/host/boot epochs must invalidate stale observations. A timestamp
  or stored PID is not boot identity. No supported boot-identity/reacquisition
  source was established in this research; restart recovery stays unsupported
  until its source and continuity semantics are reviewed.
- Remaining unresolved A effects must be disjoint from B's entire launch and
  operation footprint, not merely B's `.cst` pathname. Shared companion state
  or unknown historical effects still block B, even after A has exited.

Thus quiescent A is a safer **next design target**, not an available positive B
route. Terminating A is not authorized by this note and does not settle effects.

## Admission and alias requirements (proposal)

Before any replacement transport, compare every incident's independently known
footprint/activity against B's reviewed **launch plan**, including transport
startup effects. B's future process identity cannot already be observed: first
justify launch impact independently, then bind the actual newly created process
before project mutations. Unknown launch/target impact refuses before startup.
Never open B's transport to inspect A or let it adopt an existing instance.

At the real final SDK guard, recheck evidence provenance, continuity, generation,
freshness, authorization and actual canonical arguments against every incident;
persist required obligations before dispatch. Server-side expected-target checks
must cover the live destination and lifecycle race after the application guard.
Any target/lifecycle/manual change invalidates relevant evidence; reinspection
must not silently broaden permission or substitute another file/instance.

Identity comparisons must reject same-file aliases (hard links included),
reparse/junction aliases, equal directories, nested footprint directories, and
shared companion/temp/output files even across different parent directories.
Path inequality and dedicated folders alone prove none of this. For nonexistent
destinations, validate the identified parent and exact authorized name; creation,
replacement, rename, or reparse changes require renewed identity checks. Retained
handles identify objects, not an immutable mapping from paths to those objects.
Unsupported filesystem/volume/network identity and unclosed race windows refuse;
do not silently weaken `FILE_ID_INFO` to path equality. [File API], [File ID]

## Safest next decision and outstanding validation

Review an **explicit-new + blank MWS creation, quiescent-A-only candidate** first.
Use an exact new destination, with no attachment, filename fallback, existing-file
overwrite, or external project imports. This is a proposed initial source-review
scope, not permission to omit named-project opening or active-A isolation from
#24's delivery. A quiescent-A operating restriction needs explicit human review;
it is not accepted by choosing to investigate the evidence source.

Obtain first-party vendor documentation/source for creation ownership,
live target binding, launch side effects, companion/shared files, and complete
worker/service/deferred-work scope. If any cannot be bounded, reject that subset
and report the missing guarantee; do not manufacture proof with a supervisor.

Separately validate Windows handle rights/lifetime, job assignment timing and
nesting, file IDs/reparse/race behavior on the supported Windows/filesystem, and
restart/boot provenance. Native CST validation needs separate target-specific
authorization; Windows documentation and typed fixtures cannot establish it.
Later tests at the three user-approved seams should cover:

1. Terminal-shared `ConversationCoordinator` with controlled typed adapters:
   authorization, provenance and positive/refused routes, not native CST behavior.
2. `ControllerSession` plus the real protected-client final guard: queued
   target/permission changes, canonical destinations, invalidation and legacy
   incidents without footprints, not native isolation.
3. Narrow typed server handlers with fake vendor bindings: new-only launch,
   destination verification and expected-target enforcement, not vendor behavior.

No new tests were written for this design-only step. Documentation research does
not deliver #24's positive
production B route or its other authorization/dedicated-directory criteria.

## Primary sources

[#24]: https://github.com/GoncaGomes/cst-agentic/issues/24
[connection]: https://github.com/GoncaGomes/cst-mcp/blob/a4a177aeb0856dbf0f668f2dc5a8ca06e20ac8c2/src/cst_mcp/tools/connection.py
[session]: https://github.com/GoncaGomes/cst-mcp/blob/a4a177aeb0856dbf0f668f2dc5a8ca06e20ac8c2/src/cst_mcp/session.py
[project]: https://github.com/GoncaGomes/cst-mcp/blob/a4a177aeb0856dbf0f668f2dc5a8ca06e20ac8c2/src/cst_mcp/tools/project.py
[Handles]: https://learn.microsoft.com/en-us/windows/win32/procthread/process-handles-and-identifiers
[Times]: https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-getprocesstimes
[File API]: https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-getfileinformationbyhandleex
[File ID]: https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_id_info
[Jobs]: https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects
[Job query]: https://learn.microsoft.com/en-us/windows/win32/api/jobapi2/nf-jobapi2-queryinformationjobobject
[Accounting]: https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_basic_accounting_information
[Exit]: https://learn.microsoft.com/en-us/windows/win32/procthread/terminating-a-process
[Termination]: https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-terminateprocess
