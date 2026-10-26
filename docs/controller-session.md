# Manual Controller session (#18)

This builds on local recovery foundation `b02d6b1`, not a replacement for it.
The production lifecycle factory is `create_controller_session`; the terminal
uses that same factory. The [conversation coordinator](controller-conversation.md)
now owns terminal policy and the offline-tested model/tool loop (#19). Live target
support (#24), production isolation evidence and native acceptance remain unavailable.

## Configuration and entry

The separate command is:

```powershell
uv run cst-agentic controller --env .env
```

Running it starts the configured MCP server, so it is **not** an offline test
command or permission to perform connected experiments. No real-server or
institutional endpoint run was used to verify this change.

Configuration uses the existing `SKYNET_BASE_URL`, `SKYNET_API_KEY`, `AGENT`,
`CST_MCP_SERVER_EXECUTABLE` and `CST_MCP_SERVER_CWD` variable names. The configured
institutional HTTPS endpoint and Qwen model are retained, without fallback to an
unrelated OpenAI credential/model. Add `CST_CONTROLLER_WORK_DIR`, an explicit
absolute writable work directory. Executable and server working directory must
also be absolute existing paths. Configuration file values take precedence over
ambient values; dotenv interpolation is disabled. Errors name variables or safe
categories, not their values. The existing connectivity configuration is unchanged.

The public SDK child uses forced `CST_CONNECT_MODE=manual`, the explicit
`CST_WORK_DIR`, and the fixed category superset in `CONTROLLER_TOOLSETS`:
connection, official, project, geometry, boolean, transforms, materials, ports,
boundaries, mesh, solvers, simulation, results, import_export, parameters,
diagnostics, pcb and workflows. Category spellings/membership were inspected at
server `a4a177aeb0856dbf0f668f2dc5a8ca06e20ac8c2`; no server rewrite is needed.
Some categories advertise excluded functions; only the exact approved inventory
can be activated or dispatched. Server toolsets are availability, not authority.
Only reviewed OS/runtime
environment names are forwarded. Model credentials, Python environment overrides
and arbitrary token/config variables are excluded. Because the SDK merges its
own default environment, its inherited-name list is checked against the reviewed
allowlist before construction; expansion fails closed pending review. OS paths
are operational configuration, not a sandbox or filesystem-access restriction.

Startup acquires the central per-Windows-user lease and validates recovery state
before client construction. Any unresolved incident refuses this manual route
before transport startup: production pre-transport isolation evidence is not yet
available from #24. Missing/corrupt expected state likewise blocks admission.
The lease remains held through provider and transport cleanup.

Public stdio, SDK session, initialization, paginated catalogue discovery and
bootstrap catalogue admission run in one lifecycle-owner task within the complete
120-second MCP startup allowance. Bootstrap checks block missing, duplicate or
unfaithful required status/project-info schemas; affected optional groups are
disabled. The coordinator installs the approved startup/discovery selection
described in [the conversation documentation](controller-conversation.md).
Neither bootstrap admission nor schema availability grants attachment authority.

The configured provider client and OpenAI Agents SDK model are initialized without
making model requests. Global tracing/export processors are disabled and the
prepared SDK `RunConfig` disables tracing. The shared coordinator uses direct
model requests with `ModelTracing.DISABLED` only after request admission; production
admission remains blocked pending validated context/endpoint prerequisites.
Server stderr is captured in a local temporary stream from process startup,
never automatically forwarded, and discarded on cleanup.

## Interaction and exit

`help`, historical `status`, `continue`, stop-simulation intent and exit confirmation
are handled by the shared coordinator. Production work requests report the missing
context/endpoint/target prerequisites; no native launch, attachment, status, stop,
save, disconnect or close route is activated. Existing-instance attachment remains excluded.

`quit`/`exit` warns about unsaved work, active simulations and unknown live state;
the user must type `exit` again to confirm. Declining keeps the session open.
These are conservative warnings, not live dirty/run-state readbacks. The production
runtime cannot own a CST instance while dispatch prerequisites are blocked. Future native task
integration must add target-specific applicable save/run confirmations; this
generic confirmation cannot authorize saving, stopping or closing native work.
Task completion in the inherited session still leaves transport/CST alone.

EOF reports missing confirmation and attempts local cleanup with a nonzero exit.
Interruptions are abnormal exits, not task-cancel or emergency-stop controls.
The default reader polls a Windows console without executor input threads, so
blocked input cannot delay executor shutdown after Ctrl+C. Redirected stdin and
non-Windows terminals are unsupported and take the EOF path.
Controller-launched instances are session-bound: no survival promise is made for
normal exit, interrupted exit or crash. Check CST directly when needed.

Provider and transport cleanup share one 30-second allowance; provider cleanup
uses that deadline and the transport receives the **same** deadline. Primary and
cleanup failures remain together, with sanitized diagnostics at the terminal.
SDK context exits must not be interrupted by an already-expired native asyncio
timer: that was observed to corrupt context unwinding and hang stdio cleanup.
Public SDK process-shutdown waits supply their own bounds; transport cleanup is
allowed to unwind and reports any total-allowance overrun. This is best-effort
orderly cleanup, not a hard real-time bound, universal process-kill guarantee, or
permission to retry native work. No private SDK lifetime hooks are used.

## Verification and remaining gates

`tests/test_controller_runtime.py` exercises the actual production factory and
terminal with newly controlled peers: environment filtering after SDK merging,
no dispatch on entry/exit, recovery refusal, exclusive lease, startup refusal,
initialization/catalogue timeout, catalogue rejection, primary plus public-SDK
and provider cleanup failures, shared deadline exhaustion, and exit confirmation.
These peers never import CST or request the institutional endpoint. This is not
a replay of the consumed #14 experiments.

Run offline checks with `uv run pytest -q`, `uv run ruff format --check .`,
`uv run ruff check .`, and `uv run pyright`.

**#17 remains open, with all requirements intact.** In particular, this refusal
does not demonstrate its allowed isolated B route. Production typed isolation,
production dispatch/settlement/reconciliation acceptance, additional abrupt-death
windows and the persistence-plus-temporary-cleanup compound-error regression
remain outstanding. Coordinator-level dispatch and compound cancellation/persistence
are tested offline as described in the conversation document. The permanent client latch and no-replay rules are
unchanged. No endpoint, configured-model behavioral, native CST/isolation or
power-loss evidence is supplied, and no connected experiment is authorized.
