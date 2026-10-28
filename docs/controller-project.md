# Model-led working projects (#24)

## Interpretation and interaction

[The approved model-led decision](https://github.com/GoncaGomes/cst-agentic/issues/11#issuecomment-6472025069)
assigns interpretation of ordinary requests and agreed consequences to Qwen.
The application passes original messages unchanged, coordinates discovery/calls
and retains conversation context. It does not parse consent, classify intent or
require a separate permission response or exact-call manifest. Instruction-following
must be evaluated as model behavior, separately from technical safeguards.

Start with CST closed. Use one Controller session, one Controller-launched instance
and one selected project, without concurrent manual edits. Starting the application
and manual MCP transport does not launch or attach to CST. These ordinary messages
may arrive separately, with clarification between them, or as a combined request:

```text
Open CST.
Create project C:\Projects\Example\Example.cst.
Inspect this project.
Save the project.
```

Qwen discovers tools, probes protocol support using `cst_connection_status`, and
requests `cst_connect(mode="new")`. Launch requires no project path. The resulting
connection-only state admits connection checks but no project-dependent work.
Qwen then chooses create/open with the exact absolute path. “Connect to project”
means opening that file in this owned instance, never attaching to another instance.
Healthy follow-up tasks retain the verified binding and recheck it before dispatch.
Conversational objective labels do not invalidate it or require semantic renewal.

Qwen must ask about additional saving, overwriting, discarding, deletion and solver
consequences not already agreed. A complete request needs no per-tool approval.
Controlled operation adapters can test task integration without claiming delivery
of geometry, units, parameter editing, setup or simulation from their owning issues.

`establish_task(TaskPermission)` and terminal `task: <JSON>` remain legacy local
setup interfaces, not prerequisites of ordinary conversation. Their old operation
and consequence fields are not application-enforced semantic grants or single-use
tokens. Prefer normal conversation; no model-visible intent function was added.

## Technical safeguards and server contract

`WorkingProject` records stage, connection, exact selected destination, immutable
live binding, readback order/provenance, validity and generation. Model assertions,
requested-path echoes, notes and historical responses cannot establish native facts.
The model context explicitly reports uninspected geometry/units/setup/results.

`ControllerSession` and the real protected client's final synchronous guard recheck
target/connection/generation, canonical arguments, filesystem identity, lifecycle,
inventory, budgets and central incidents **after queueing**, before durable dispatch
preparation. The server rechecks its held API objects immediately before handlers
and reads `held_project.filename()` afterward. Missing or mismatched readback blocks
dependent work. Detected conflicting instances are refused, never silently closed.
This is not exhaustive process accounting or continuous external-change detection.

The companion source inspected is `GoncaGomes/cst-mcp` main at `94906b8` (PR #5).
Its opt-in MCP `_meta.cst_controller` version-1 protocol already supports launch
without a path and expected-target enforcement. No companion changes are needed
for these routes. Source inspection is not deployed/native acceptance evidence.
The inventory remains eighteen groups, seventy-two eligible MCP tools and sixteen
active functions, with three startup functions including application discovery.
No tool schema or group was added or rewritten.

Create/open and supported saves require one distinct `.cst` per existing dedicated
directory. Actual canonical arguments and supported Windows identities/aliases are
checked. Existing create destinations, hard-link conflicts, unknown identities and
cross-project Save As are refused. No suffix, directory creation, move or overwrite
fallback occurs. Save without a path uses the checked live destination in the server.
Canonical creation arguments, including optional `project_type`, are preserved.
After affirmative not-dispatched selection failure, only that pending selection is
released so the model/user can choose another exact destination. Received/uncertain
selection failures never restore connection-only admission or clear incidents.

CAD and structure-view exports now admit explicit safe **new** output destinations.
Both application and server check actual output paths, parents, aliases, format
extensions and existing-file conflicts. Existing-output replacement is not exposed
by the canonical schemas: choose an unused destination; replacement remains an
explicit unsupported route, not inferred consent. Runtime settlement checks matching
response paths and nonempty artifacts, not CAD/image correctness or native fidelity.

## Rejections, recovery and remaining evidence

Recoverable technical rejections return to Qwen in paired call/result history.
One automatic correction is allowed per autonomous user work period, conservatively
shared across calls: changing names/arguments or successful intermediate work cannot
reset it. Only affirmative not-dispatched evidence qualifies here. Received errors
without a reviewed no-effect interpreter remain unresolved; error text never proves
rollback. Rich no-effect/partial-effect interpretation and correction ownership
remain coordinated with #25. Missing operation interpreters pause dependent work.

Manual intervention invalidates evidence and requires a pause and renewed relevant
inspection in a fresh session. Uncertainty permanently blocks every old-client call.
All unresolved central incidents block new A/B work and replacement transport until
explicit local human reconciliation (#17/#25), then a fresh session/task with normal
prerequisites. Dedicated directories do not prove isolation. The
[old isolation investigation](controller-isolation-evidence.md) is historical.

## Acceptance trace and evidence limits

| #24 criteria | Offline evidence |
| --- | --- |
| Unchanged input; no intent/manifest stage; discovery | `tests/test_model_led_project.py` |
| Launch without path; separate/combined selection; clarification; healthy tasks/save | Same coordinator tests, using real session/gateway/client and typed external peers |
| Exact targets/readback, destination conflicts and instance conflicts | Same tests plus `tests/test_working_project.py` |
| Queued technical invalidation; lifecycle, serialization and uncertainty | Working-project, conversation, protected-client and actual-wrapper tests |
| CAD/view safe outputs and honest settlement | Model-led coordinator tests with artifact-producing controlled peers |
| Recovery integration without isolated-B bypass | Existing conversation/recovery/runtime regressions; remaining #17 acceptance stays open |

Offline scripted models prove application integration, **not** real Qwen understanding.
The create/open/save schema fixtures are copied from the pinned companion source;
their optional fields/defaults are not narrowed to simplified path-only schemas.
Production `request_admission=None` still blocks model requests pending #23; no
unconditional adapter was installed. Endpoint probes, configured-Qwen behavioral
trials and native destination/effect acceptance (#37) were not run. Full #17/#25
recovery delivery and downstream modeling capabilities are not claimed here.
