# Final native-free lifecycle round: stopped during the first scenario

**THROWAWAY / LOCAL ONLY / NOT A RESOLUTION / NOT PRODUCTION.**

Decision: [Verify Windows transport lifetime and bounded solver-stop behavior](https://github.com/GoncaGomes/cst-agentic/issues/14),
under [Wayfinding: specify the first usable CST Controller](https://github.com/GoncaGomes/cst-agentic/issues/4).

## Outcome

**The round did not complete and does not establish the remaining lifecycle
requirements.** It stopped during the crash phase of the first scenario after
**4.322156 seconds including outer uv invocation and containment**. The supervisor
recorded `RuntimeError`; all seven held exact fake-process handles were subsequently
observed terminated. There is no current fake-process intervention pending.

A confirmed observer defect is sufficient to explain the early stop: the
pre-crash peer-liveness guard continues to execute after crash permission has
already been issued. Expected post-crash peer termination can therefore raise a
misleading pre-crash error. However, the original runtime recorded only the
exception type, not its fixed failure category. The precise original throw site
is **not independently proven**. Do not relabel this as either a passed lifecycle
test or a proven product/SDK failure.

The accepted session-bound lifetime policy, simplified task interaction and
bounded best-effort simulation-stop contract remain unchanged. No publication,
resolution, closure, map update, commit or push was performed in this round.

## Human-approved scope and containment

The human authorized the proposal with **"I authorize it."**:
[authorization](windows-lifecycle-final-evidence/authorization.json).
At most four scenarios, five minutes including cleanup, no retries:

1. Crash during a protected fake operation, then fresh-process restart blocking.
2. Partial startup failure during initialization.
3. Startup timeout with separately measured cleanup.
4. A peer refusing orderly shutdown, preserving the primary application failure.

Only new disposable Python application/peer processes were eligible to run.
Every Python process invocation used `uv run --offline --no-sync` with the existing
project environment. The child environment contained SDK-default Windows execution
settings and explicit offline/virtual-environment/UTF-8 settings, not provider
configuration. No dotenv, provider SDK/client, CST API, solver, normal CST MCP server
entry point or production Controller/client was imported or executed.

The fake application used public installed MCP `stdio_client` and `ClientSession`
contexts entered by one task, with one serialized protected `tools/call` site.
The fake peer used fixed synthetic JSON-RPC messages and a scratch-only target.
All process snapshots were read-only; only the observed new application/peer
ancestry, executable basenames, creation times and exact-handle liveness were
retained. No command lines, environment dumps or unrelated window text were read.
Server stderr was discarded; SDK log capture retained only logger names/levels.

Each fake peer had a 35-second self-exit watchdog; each disposable application
had a 42-second watchdog. Exact scratch release flags provided additional
self-exit containment. No arbitrary external PID/tree kill or private SDK Job
Object access was added. The public SDK still owns its ordinary fake-server
shutdown behavior. The main supervisor reserved a 270-second internal bound plus
outer invocation headroom within the approved 300 seconds.

The experiment root and wrapper admission are exclusive and consumed:

- `C:\Users\Lenovo\AppData\Local\Temp\opencode\cst-lifecycle-final-01`
- `C:\Users\Lenovo\AppData\Local\Temp\opencode\cst-lifecycle-final-01-launch.json`

No previous native/offline driver, wrapper or finalizer was replayed. No existing
project, marker, ledger or source snapshot was reset. The in-flight recovery marker
from this failed attempt is deliberately retained.

## What actually ran

Installed MCP **2.3.0**, AnyIO **4.15.1**; exact installed transport/Windows utility
source hashes are in [static preparation](windows-lifecycle-final-evidence/preparation.json).

| Stage | Observation | Limit |
| --- | --- | --- |
| Static preparation | Both new source files passed Ruff lint/format and AST/compile checks. Wrapper parsed without execution. Exactly one guarded `call_tool` site. 106 prior files fingerprinted. | No scenario, peer, application or model execution during preparation. |
| Context entry | Transport and session entered with the same recorded task ID. | Abrupt exit does not exercise orderly context unwinding. |
| Before dispatch | Application flushed/fsynced and replaced the central in-flight marker, then logged the pre-dispatch event at monotonic 256071.890. | Controlled process-crash evidence, not a power-loss/disk-failure guarantee. |
| Fake operation | Peer independently read the marker before accepting work; recorded work entry at 256071.906. | One synthetic `tools/call`, not a CST operation. |
| Before crash permission | External observer held all seven exact process handles alive and recorded the marker. | Any-process liveness does not isolate SDK Job Object membership/ownership. |
| Crash point | Application recorded deliberate abrupt-exit event at 256071.953 immediately before its `os._exit(23)` call. | Supervisor did not reach exit-code recording; do not present exit code 23 as independently observed. |
| Supervisor stop | `RuntimeError`, before restart launch or case verification. | Coarse error recording does not independently identify its throw site. |
| Containment | All seven exact handles recorded not alive after the scratch release phase. | The supervisor did not record the pre-release post-exit window. Do not attribute termination exclusively to SDK cleanup or claim the release flags were unnecessary. |

The round driver recorded **2.656 s** from its own measurement point; the outer
wrapper recorded **4.322156 s**, below 300 s. Only **one of four scenarios was
admitted**, and that scenario remained incomplete. No retries occurred.

### Not run

- The fresh-process restart portion of scenario 1.
- Scenario 2: partial startup failure.
- Scenario 3: startup timeout.
- Scenario 4: uncooperative shutdown.

Unused scenario slots and time do **not** authorize automatic continuation or a
replacement round. No additional execution was performed after the supervisor
stopped; only saved-file analysis, evidence capture and documentation checks ran.

## Read-only diagnosis of the harness defect

The diagnosis did not import the harness or create SDK contexts/processes. The
analysis extracted the actual observer conditional from the byte-exact executed
source AST and evaluated it against a recorded post-permission, dead-peer state.
It raises the fixed `peer_exact_handle_not_established_before_crash` error even
though `crash-permitted.flag` already exists. A proposed additional predicate that
disables that pre-crash condition after permission avoids the false rejection in
this isolated trace check. This proposed change was evaluated **in memory only**;
the consumed source was not edited or rerun.

Ranked explanations considered: (1) post-permission liveness recheck, (2) a
process-snapshot/observation race, (3) an unexpected application exit. The trace
check confirms defect (1); the deliberately logged crash sequence supports it as
an explanation. Because the original exception lacked a category, it does not
eliminate every alternative throw site. Any future harness should record fixed,
credential-safe failure categories in addition to exception types.

Dynamic reproduction, retries and full regression execution were deliberately
not attempted: the one-time round is consumed and its no-retry limit takes
precedence over an open-ended debugging loop.

## Evidence and checks

- [Verification: capture integrity passed; planned lifecycle checks did not](windows-lifecycle-final-evidence/verification.json).
- [Round observations](windows-lifecycle-final-evidence/attempt/observations.json),
  [ledger](windows-lifecycle-final-evidence/attempt/round.json),
  [outer timing](windows-lifecycle-final-evidence/attempt/outer-observation.json).
- [App events](windows-lifecycle-final-evidence/attempt/crash_restart/app-events.jsonl),
  [peer events](windows-lifecycle-final-evidence/attempt/crash_restart/peer-events.jsonl).
- [Pre-crash exact-handle observation](windows-lifecycle-final-evidence/attempt/crash_restart/observer-precrash.json),
  [final handle observation](windows-lifecycle-final-evidence/attempt/crash_restart/app-observer.json),
  [retained central recovery marker](windows-lifecycle-final-evidence/attempt/crash_restart/central-recovery.json).
- [Byte-exact executed sources](windows-lifecycle-final-evidence/attempt/sources/),
  [one-time wrapper and read-only analysis/capture scripts](windows-lifecycle-final-evidence/wrapper-source/).
- [Captured-conditional analysis](windows-lifecycle-final-evidence/trace-analysis.json).
- [Prior fingerprints](windows-lifecycle-final-evidence/prior-evidence-sha256.json):
  all **106** prior source/evidence files, including consumed native ledgers,
  remained unchanged. All captured attempt files matched their originals.

Initial lint findings in new files and the analysis/capture helpers were corrected
before their respective executions. This did not replay any scenario. Post-run
capture is successful **as evidence preservation**, not as lifecycle validation.

## Decision status

**Keep the ticket open.** The intended pre-dispatch recovery record demonstrably
existed before fake work and remains after the deliberate crash point, but this
round did not demonstrate a fresh process refusing further tools. Failed-startup
and cleanup requirements still have only their earlier partial synthetic evidence.
The production client's wrapper remains unvalidated by these experiments.

Exact SDK Job Object ownership remains **unisolated**. Native failure recovery,
stop responsiveness behind a genuinely long launch, actual native transport
uncertainty, and normal-server-entry-point behavior remain unverified. No broader
acceptance/handoff, universal timing, power-loss durability, concurrent-session
lease, or recovery-clearance procedure is established.

Recommended next action for human review: correct the observer's phase gating and
safe failure-category recording, then agree a fresh bounded replacement round if
the human wants executable evidence. This report does not authorize that work,
publication, resolution, closure or any waiver of the remaining requirements.
