# Selected working project and task authorization (#24)

## Scope and explicit entry

Start with CST closed. Use one Controller session, one Controller-launched CST
instance and one selected project; no concurrent manual edits are supported.
Starting the application/MCP transport still does not launch or attach to CST.
Existing-instance attachment, connect-to-any, active/first-project adoption,
silent filename suffixes and cross-project Save As are not supported.

The shared coordinator exposes `establish_task(TaskPermission)` to trusted local
adapters, and the terminal accepts the equivalent **explicit human** instruction
`task: <JSON>`. This is not a model tool or a parser of model-generated permission.
For example (illustrative only; not permission to execute):

```text
task: {"path":"C:/projects/example/example.cst","action":"create","launch_new":true,"outcome":"Create an empty project, then save it once","changes":"Empty MWS project only","consequences":["save"],"operations":[{"name":"cst_save_project","arguments":{}}]}
```

The dedicated parent directory must already exist. `action` is `create` or `open`.
Open requires an existing regular file; create refuses an existing destination.
No automatic directory/file reorganization, replacement or fallback occurs.
The complete instruction authorizes initial launch/create/open without duplicate
approval. Each exact listed operation is a single-use grant, including its exact
arguments; it is not permission to repeat work. Distinct consequences are `save`,
`overwrite`, `discard`, `delete_results` and `run_simulation`. A consequence alone
does not authorize an operation. Creating a file is not permission for later saves.
Cross-project overwrite/Save As remains unsupported even with a consequence grant.
CAD export and structure-view export execution are also refused pending a reviewed
output/overwrite destination route, even with `overwrite` permission. Their
discovery membership is unchanged; visibility is not execution support.

This first adapter requires structured exact scope rather than inferring choices
or permission from prose. Normal conversation does not create execution permission.
A new conversational objective invalidates the previous task's execution evidence.
A fresh launch task currently requires a fresh Controller session; same-instance
follow-on task rebinding is not implemented. The generic conversational loop remains
independently blocked by missing #23 endpoint admission, even when local
working-project prerequisites succeed.

## Dispatch and live evidence

The runtime installs `WorkingProject` into `ControllerSession`. Setup uses that
same recovery-aware session and protected client; model operations additionally
pass through `ConversationGateway` visibility and canonical-schema checks.
The real client's final synchronous guard rechecks exact task permission,
task/generation, canonical arguments/destination, filesystem identity, central
incidents and session state **after queueing**. Initial launch receives the existing
480-second queue-inclusive allowance; ordinary work is capped at 120 seconds.

The paired server change is in `C:/dev/cst-studio-mcp`, branch
`feat/24-live-target-enforcement`, based on `a4a177a`. It uses public MCP request
`_meta.cst_controller` version 1, outside model tool arguments. No function, group,
schema or count changes: eighteen groups, seventy-two eligible MCP tools, three
startup functions including application discovery, sixteen active functions.
An existing read-only status call probes protocol support **before launch**.
Missing support refuses dependent work. This implementation supports MCP SDK v2;
an old server/v1 path without metadata support fails the probe, not open.

The server checks actual held API objects on its existing CST worker immediately
before the handler, and reads `held_project.filename()` after selection/operations.
Connection/project tokens, acquisition sequence and provenance are checked and
retained in an immutable application binding. Cached paths, offline scripts and
response echoes cannot establish that binding. A supported CST instance-list
check refuses detected pre-existing/additional instances and unavailable checks;
it does not inventory helpers/services or prove multi-instance isolation.
No unrelated instance is closed automatically. No generic execution tool is added.
Model request context includes this binding's provenance/validity and the exact
remaining operation grants, outcome, agreed changes and consequence permissions.
Context accounting includes that full application-owned state; it is not summarized
into a model-created permission claim.

Create/open and every supported save validate the actual canonical destination in
both application and server. Save without a path uses the checked live destination,
not the legacy cached path. Filesystem device/inode identities, resolved directory
aliases and casing checks are used; hard-linked project destinations and ambiguous
Windows names are refused. Unknown identity refuses rather than guessing.
These checks are not filesystem locking or continuous external-change detection.

Existing-project setup reports overview gaps: geometry, units, parameters, solver
setup and results are uninspected. A valid binding proves a target, not these facts.
`manual intervention` invalidates evidence and pauses automation; a fresh session,
task and relevant inspections are required. No automatic evidence restoration.
Runtime settlement is narrowly supplied for save responses and project-info; other
operations without a reviewed outcome interpreter pause with a retained incident.
Native destination/effect validation remains #37, not a response-success claim.

## Recovery and evidence limits

Every unresolved central incident blocks new A/B work and replacement transport
until explicit local human reconciliation under #17/#25. The old uncertain client
remains permanently blocked. The old `isolation_check` constructor argument is
compatibility-only and cannot bypass admission. Dedicated directories organize
destinations; they do not establish isolation. The earlier
[isolation investigation](controller-isolation-evidence.md) is historical.

Tests use the terminal-shared coordinator, real gateway/protected-client guard,
isolated filesystem/state and controlled peers. Server tests use actual
registry/project/connection wrappers with controlled API objects. These are
**offline behavioral tests**, not endpoint acceptance, configured-model behavior,
native CST success or native recovery evidence. No consumed native campaign is
replayed; no CST instance or provider request is needed for these tests.
