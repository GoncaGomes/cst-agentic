# CST MCP capability and evidence baseline

Date: 2026-10-19. Research for [ticket 7](https://github.com/GoncaGomes/cst-agentic/issues/7), under [map 4](https://github.com/GoncaGomes/cst-agentic/issues/4).

## Findings that constrain the first Controller

1. **The catalogue remains 192 tools**, including all 73 MCP names in the candidate Controller inventory. This is a static source count, not an effective running catalogue or 192 validated capabilities. Server category filtering and application model exposure are different mechanisms. [S1][S2][S3]
2. **Unit and parameter inspection have gaps.** There is no dedicated unit getter/setter. Geometry and frequency setters do not establish or convert project units. Successful fixtures explicitly set or read mm/GHz/ns using controlled raw VBA. Parameter get/list also return evaluated numbers, not the stored expressions their descriptions promise. Existing-project work needs to account for both limitations. [S9][S10][S18][S33][S39]
3. **Existing-instance selection is ambiguous.** `any` can launch CST and adopt an arbitrary existing instance/project. `new` is only effective while disconnected. There is no public PID-targeted or existing-only connection contract. Project-info paths are cached session state, not independent live filename verification. [S5][S6][S7][S32]
4. **A later query through the same application client cannot reconcile a transport-uncertain call.** The committed client serializes calls and permanently blocks *all* subsequent tool dispatch after uncertainty, including status and stop. Reconnecting is not reconciliation. The proposal's timeout recovery wording therefore requires a separate decision. [A1]
5. **Source changed beneath documentation.** Solver/mesh queries now use no-history capture, despite stale mutation annotations. Port listing is captured without its nominal `MsgBox` popup, but still lacks structured port attributes. Broad dialog recovery remains genuinely mutating and is not project-scoped. [S12][S13][S14][S15]
6. **Real connected evidence exists, with bounded claims.** Six parameter fixtures and boolean fixtures have native readbacks. Local antenna evidence includes a successful blocking dipole study, an async patch workflow with a failed directivity diagnostic, and an async WR-90 workflow with an incomplete overall assessment. These are earlier runs, often dirty-source runs, not a clean connected acceptance of the pinned revision. Sections 7 and 8 preserve the distinctions.

This report does **not** choose the final Controller allowlist, approve autonomous recovery, implement prerequisites, or establish a Results Analyst.

## 1. Scope, pins and method

### Reviewed source

| Item | Exact basis |
| --- | --- |
| Upstream | `GoncaGomes/cst-mcp`, **`a4a177aeb0856dbf0f668f2dc5a8ca06e20ac8c2`**, commit dated 2026-10-19T10:29:05+01:00, “Add antenna simulation capability tests and fix CST integration (#4)” |
| Local upstream checkout | `C:\dev\cst-studio-mcp`. Tracked/untracked status was clean. `git ls-remote origin HEAD refs/heads/main` matched this SHA. Ignored generated evidence still exists locally and is not committed source. |
| Application | **`2f5d809e3ca82b726fac407cc89ba6ab58de786d`**, matching `origin/main` when the isolated research worktree was created |
| Candidate proposal | Local `C:\dev\cst-agentic\docs\CST_Controller_Tool_Discovery_Plan.md`, dated 2026-10-16. SHA-256 **`A28F8B1881F339694E1A91F797B837C2A83802F81D88399C122AD90848A7C581`**. It is not in the application baseline. Local line references below refer to these exact bytes, not an invented committed URL. |

Primary sources were committed tool schemas, handlers, session code, capability runners/reviews, and existing generated capability reports. GitHub CLI supplied the complete ticket and map. The main worktree's current agent instructions and glossary were read without modifying them. No relevant committed research naming convention existed in this baseline, so this report uses a dated file under `docs/research/`.

**Safety:** no server was started, no upstream package imported, no catalogue endpoint called, no CST process attached/launched, no project opened or modified, and no model endpoint invoked. Temporary Python scripts used `uv run --python 3.12 --no-project python` and standard-library AST/JSON/hash inspection only. Credential-bearing configuration was not inspected. Evidence extraction selected known capability paths and provenance fields, not environment dumps or provider/chat logs.

Evidence vocabulary:

- **Source contract:** behavior traced in this pinned implementation, not a new runtime observation.
- **Recorded native evidence:** a retained earlier live run with separate effect readback and stated limits.
- **Acceptance only:** a returned tool success or input echo, insufficient to prove the requested native state.
- **Unknown/restriction:** absent readback, untested route, known rejection or incomplete/failed assessment.

## 2. Startup, runtime and catalogue contract

### Catalogue without automatic CST launch

`create_server` constructs a session and registers tools. `run_server` calls `connect` only for `connect_on_startup`, which is true only in `auto`. Default `manual` leaves connection explicit. `disabled` prevents connection, including a later `cst_connect`. Configuration can discover installation directories, modify the server process's Python search path and create its work directory. Thus “no CST attach/launch” is supported by source, but “no filesystem/process effects at all” is not. `auto` attempts connection **before** serving stdio and can delay the handshake. Protocol stdout isolation starts before client construction. [S3][S4]

No dynamic catalogue acquisition was necessary here. A future manual-mode initialize/list check can be targeted separately. Do not run a live capability runner just to count tools, as its ordinary route launches CST and constructs an owned project. [S18][S21]

### Runtime is version-specific

The package advertises Python >=3.10, CST 2024–2026 and `mcp>=1.29,<3`. That does not establish vendor ABI compatibility. Existing connected evidence is for **Windows CST 2025, Python 3.12.13**, with MCP SDK 2.3.0 in the inspected parameter/antenna records. The documented 2025 binary binding is `cp312-win_amd64`. The source configuration default version is **2026**, not the proven 2025 installation. Do not infer installed runtime or CST version from server version `1.1.0` or the configured version string returned by status. [S4][S7][S17][S18][S21]

### Canonical schemas and filtering

All 26 registered modules were statically examined, including the four `official.py` declarations built through its `tool(...)` helper. There are **192 unique names**, no duplicates, and no unit tool name. Counts by module:

```text
official 4, connection 2, project 8, geometry 13, boolean 4,
transforms 4, materials 15, ports 8, boundaries 6, mesh 8,
solvers 8, simulation 7, results 22, import_export 5,
parameters 11, optimization 3, diagnostics 7, antenna_templates 13,
arrays 8, pcb 13, matching 8, vba 3, workflows 8,
drawing 1, figures_1d 1, figures_3d 2
```

The SHA-256 of sorted unique names joined with LF, without a trailing LF, is `af377bba47789f3b7a03f57ff26c73d1150bdd1d67a1dc76e6332c613d43874b`. This is a **names digest**, not a canonical schema digest. The AST method reads declarations and never evaluates schema comprehensions or imports handlers. [S1][S2][S16]

The canonical wire catalogue comes from MCP `tools/list`, not Markdown or a function signature reconstructed by the Controller. Registry startup validates JSON/object/required/schema structure, adds name-derived annotations, and supports SDK 1 and SDK 2 field aliases. SDK 2 request registration explicitly validates inputs. Declared schemas are heterogeneous: selected geometry fields use number/string unions and schema comprehensions, `cst_set_parameter.value` has no schema type, and many tools omit `additionalProperties:false`. Successful payloads with declared output schemas are validated. Recognized JSON `error`, `busy`, and `timeout` statuses become MCP `isError`; structured content mirrors usable JSON objects. Transport receipt still does not establish native success. [S2][S9][S10]

`CST_TOOLSETS` is parsed at server startup and captured at registry binding. Categories remove tools from listing **and reject their dispatch**. Connection/status tools are always enabled. Blank/all means all tools. Unknown categories are ignored, and an entirely invalid selection **falls back to all**, so this is not a fail-closed role policy. `core` does not include geometry/material/solver/mesh setup families needed to build the reference tasks. Application allowlists must not be inferred from this convenience filter. [S2][S4]

There is no runtime category-switching or catalogue-change notification mechanism in the inspected registry. It closes over the bound list. Retained WR-90 initialization reports `tools.listChanged:false`. Re-list on a new server session is meaningful. Refresh “when notified” is conditional future integration, not an upstream notification currently evidenced. The application `discover_tools()` follows pagination but returns **names only**, discarding schemas. Canonical schema retention and per-request exposure remain downstream application work. [S2][A1]

## 3. Connection and project identity

| Operation | Source-level contract and constraint |
| --- | --- |
| `cst_connect(mode="any")` | Default. Uses `connect_to_any_or_new`, or a fallback selecting the first running DE. May attach to the user's DE or launch a new one. Reports PID, whether newly started when knowable, prior PIDs and open paths. These can be unknown. |
| `cst_connect(mode="new")` | Starts a new DE only while disconnected. When already connected, returns “Already connected”, preserving the current session. On Windows the new-instance path can run a bounded, targeted education-notice watcher using the new PID. It is not a guarantee of no dialog automation. |
| Adopted project | Prefers DE active project, otherwise first open project. Handles or path references are normalized. There is no public argument to select a DE by PID or attach only if an existing instance is available. |
| `cst_disconnect` | Forgets local handles, cached path and pending-solve record. Does not call DE close or stop CST/solver. This also loses local async-run correlation. |
| `cst_create_project(path,type)` | Connected mode creates through a type-specific factory and saves. An existing target, or an initial save failure, may cause a timestamp-suffixed alternate path. Follow the response's actual path. Creation is not overwrite-at-exact-path assurance. Offline mode does not create the project. |
| `cst_open_project(path)` | Connected mode calls DE open and caches the **requested** path. Offline mode records only a path and returns `offline`. Repeating open is not idempotent and may open another copy. |
| `cst_save_project(path?)` | Saves the held project and updates cached path on success. Save As can overwrite a destination. No independent filename readback is returned. |
| `cst_close_project` | Checks solver idleness before closing the held project, then clears handles/path/pending solve. No save argument or automatic unsaved-change policy is exposed. |
| `cst_project_info` / `cst_connection_status` | Distinguish offline path reference from a held connected project using `mode` and `project_open`. `project_path` is `_project_path`, not a fresh `project.filename()` query. Connection status also queries solver activity when a project is held. `cst_version` is configured, not measured binary identity. |

Sources: connection schemas/handler [S5], session connection [S6], lifecycle [S7], status [S32], annotation warning about open duplication [S12].

The public identity evidence is therefore **not** a stable unique project/execution identity. There is no mutation precondition such as expected PID, expected project ID, model revision or parameter fingerprint. Most operations act on the held project without a target argument. A user changing the GUI, multiple instances/projects, unsaved projects and stale cached identity require explicit downstream handling. These are not problems solved by passing a path in chat or observing `running:false` when no project is open. [S6][S7][S32]

`cst_project_tree` is a bounded ResultTree traversal through no-history output capture, with depth 0–10 and an internal 2,000-item cap. Its returned items/truncation are evidence only for that traversal. Offline mode returns explicitly labeled defaults, not an actual model inventory. It does not provide a complete typed solid/material/port configuration readback. [S8]

## 4. Units, expressions and modeling capabilities

### Unit prerequisite

No dedicated getter/setter is in the registered catalogue. `cst_set_frequency_range` says GHz but emits `Solver.FrequencyRange` with the numbers unchanged. Geometry builders similarly forward dimensions. Port schemas label coordinates mm, while solver-info labels frequency as “project frequency unit (as set by cst_set_units)”. **`cst_set_units` does not exist in this catalogue.** None of these strings independently establishes actual active units or conversion. [S10][S13][S14][S34][S36]

Templates/workflows can embed unit setup, but they also build/configure larger models and are not a general unit-inspection capability. Existing fixtures used fixed `Units.SetUnit` and `Units.GetUnit` blocks through `cst_execute_vba`, or inherited units from a controlled source copy and queried them. Raw VBA is disabled by default in connected mode and its denylist is explicitly **not a sandbox**. Existing tests' narrowly permitted VBA is not permission to expose arbitrary VBA to the Controller. [S18][S20][S21]

Consequently, supported parameter arithmetic alone does not make dimension-sensitive work safe. Resolve effective length/frequency/time units and how they are established **before** numeric construction or edits that depend on them. This is operation-specific, not a reason to block independent saved-result reading or help lookup. Which dedicated prerequisite or human-verified boundary to use remains undecided.

### Parameter and geometry contracts

| Family | Actual supported contract |
| --- | --- |
| Parameters | `cst_set_parameter(name,value,description?,rebuild=true,delete_results=false)` creates or changes stored values outside history, then optionally rebuilds. On solved models it refuses unless deletion is requested. If rebuild fails after storage, it can return `parameters_changed:true`. No transactional rollback is promised. **Get/list descriptions overpromise:** get uses `RestoreParameter` into a Double and prints its numeric value, while list prints `GetParameterName` and `GetParameterNValue`. Neither builder returns the stored expression or structured expression/value records. |
| Brick | `component`, `name`, six bounds required, material defaults PEC. Each bound accepts finite number or nonempty single-line CST expression. Creation explicitly does not edit an existing solid. |
| Cylinder/cone/sphere/elliptical cylinder/torus | Selected radii, centers and axial ranges accept numbers or CST expressions. Axis/name/material/segments retain their individual types. Torus uses axis-to-outer-surface and axis-to-inner-surface radii, **not** major/tube radii. |
| Polygon3D and analytical curve | Polygon coordinates accept numbers/expressions. Analytical coordinate laws remain strings, and parameter bounds `t_min/t_max` accept numbers/expressions. Curve closure/count does not measure every point or length. |
| Extrusions | Height, profile/hole coordinates and **active-axis offset only** accept expressions. Inactive offsets must be absent or numeric zero. Native `Evaluate` preserves symbolic dependence in history. Axis/direction/winding rules are contract-specific. Returned endpoints are predictions, not measured bounds. |
| Face/loft | Face takes exactly one qualified `curvegroup:curveitem` reference and creates a planar sheet with Vacuum default. Loft requires at least two explicit 3D profiles, each at least three vertices, uses capped LoftCurves and collision-protected auxiliary groups. Legacy 2D profile spacing is not inferred. |
| Wire/ports/transforms | Expression support is not universal. Wire endpoints/radius, ordinary port coordinates and transform numeric fields keep numeric schemas. Evaluating a parameter once and submitting a number does not create an ongoing parametric association. |
| Booleans | Two validated solid references. Add/Subtract/Intersect consume the second operand. Recorded Insert removes its overlap from the first operand while retaining the second and the first's material. |

Canonical declarations/builders: [S9][S10][S14][S33][S35][S36][S39]. Native fixture coverage and limits: [S19][S23], section 7 below.

Parameter reads are still useful independent native **evaluated-value** checks, but cannot reconstruct the original expression or prove which geometry feature references it. The fixture clients compare known intended values and use separate native geometry queries. The first existing-parameterized-project workflow cannot assume its typed inspection tools expose the model's dependency structure. [S33][S39][S19]

This supports parameter-based editing of **already parameterized** models, creation, material reassignment, transforms and booleans. There is no general typed solid-delete, solid-rename, feature-history editor or arbitrary nonparametric dimension-edit tool in the full inspected names. `cst_delete_parameter` and material/port deletion are separate capabilities, not general CAD editing. No creation or raw-VBA fallback should be represented as an established arbitrary edit contract. [S1][S9][S10][S22]

### Materials, setup, ports and solver configuration

- `cst_create_material` and `cst_create_lossy_metal` generate history commands from explicit properties. Their echoed properties are not independent project EM-property measurements. `cst_assign_material` requires `Component:Solid`. `cst_list_materials` / `cst_get_material_info` read the **bundled database**, not the project's materials or installed native library. [S11]
- `cst_load_material(name,library_name,library_path?)` reads an exact native `.mtd` from a selected library directory, parses one Definition section and serializes a Material block with the chosen alias. The parser requires supported quoted-argument syntax, terminal Create and no Rename/Delete. Loading is not blanket support for every material definition/model. [S11][S24]
- Boundary/background/symmetry setters emit history VBA. Frequency range must be ordered and positive per validation. Setup checks cannot infer that the applied solver, geometry and units match the supplied intent. [S34][S25]
- Waveguide ports default `port_on_bound:true`; `false` preserves the internal normal coordinate. `mode_number` means **number of calculated modes**, not selection of an arbitrary mode index. `Free`, `Full`, and `Picks` have different placement assumptions. Discrete-port coordinates are numeric, impedance defaults 50 ohms. Listing gives textual port IDs/count, not extents, material contact, impedance or mode identity. [S14]
- Lumped elements expose a single `value`. For RLC serial/parallel the implementation uses it as R and sets L=C=0. This is not independent R/L/C configuration. [S14]
- Time-domain configuration writes native steady-state limit/stimulation/normalization settings. `max_time_steps` is **not applied**, and non-Gaussian `excitation_type` is **not applied** as a solver signal setting. Notes must not be dropped while echoed requested fields are mistaken for verified configuration. Power-loss monitoring has explicit field/farfield/extra-frequency controls. [S13]
- Frequency-domain configuration selects Hex/Tet method and native sweep mode, resets sample intervals, applies accuracy/adaptation, monitor sampling and normalization. Interpolated fast-reduced-order mode requires Tet. `adaptive_mesh` changes both interval and mesh adaptation. TD and FD code use different normalization flag mappings, making independent reference metadata important. [S13]
- Mesh type maps Hexahedral to native PBA. Density selects a **Hex/Tet settings map**, with ratio limit only on Hex. Local refinement is relative, not proof of resolved feed gaps or substrate thickness. `cst_set_adaptive_mesh` is the **time-domain** adaptation path. Use FD configuration for its own adaptation. [S15]
- Field monitors are mutations in the `results` module and must precede solving when required. Their availability depends on enabling that server category, not Controller role naming. No catalogue membership proves a monitor produced usable data. [S1][S26]

## 5. Nominal reads and operational side effects

| Tool/path | Pinned behavior, not just name/annotation |
| --- | --- |
| Solver info / mesh info / mesh quality | Current handlers use `query_values`, then silent VBA capture with `history_fallback=False`. Mesh reads do not call Mesh.Update or trigger meshing. Partial field failures are retained as `unavailable`. Their central annotations still say not-read-only because of old history behavior. Source therefore contradicts the annotation rationale. No new connected history-delta experiment was run here. [S12][S13][S15] |
| Port list | Handler builds a `MsgBox` query, but `execute_vba` detects the line-start MsgBox and redirects to capture, whose rewrite uses file output and reports `popup:false`. Local antenna evidence agrees. The README warning about a popup is stale for this path. The text still does not verify port attributes. [S14][S27][S37] |
| Project tree / parameter queries | No-history capture. This still performs native API calls and temporary work-file I/O, and uses a 5-second idle probe plus bounded silent execution. “Read” is not “instant” or “no host I/O”. [S8][S9][S27] |
| Status/project info | Can make several native solver-status calls when a project is held. Not a free local cache lookup. A returned configured CST version is not binary inspection. [S32][S28] |
| Help search | Does not start CST, but builds/caches an installed help index in memory and possibly `<work_dir>/.cst_mcp_cache`. Name-derived read-only annotations omit this file-write detail. [S16] |
| Farfield getters/metrics | Can select/reset GUI plot state and write exports. Not equivalent to saved complex-curve reads. Plots/exports create or overwrite files and may alter selection/view state. [S12] |
| `cst_check_model_setup` | Pure check of supplied boundaries, ports, bbox and monitor-frequency information. Sends **nothing** to CST. `status:ok` and inner `ok:false` can coexist. It does not inspect the actual project, mesh resolution or all solver settings. [S25] |
| Dialog dismissal/watcher | Can accept defaults and affect dialogs belonging to other CST windows. Broad helpers receive no target project/PID argument. Quiet mode is not dialog suppression. A narrow new-instance education watcher is distinct from starting the broad watcher. [S6][S29][S38] |

Canonical annotations remain useful hints, not authorization, side-effect proofs, retry permissions or connected validation. Also distinguish source timeout/error responses from no-effect assurances. A mutation can partially complete before returning an error. [S12][S27][S28]

## 6. Simulation lifecycle, uncertainty and result validity

### Launch and status

`cst_run_simulation_async(solver_type?,timeout_s=30)` performs preflight status, optionally selects solver by **history** `ChangeSolverType`, then calls native `start_solver`. It is not a 30-second end-to-end guarantee: status can comprise multiple native calls, solver selection has its own guard/history timeouts, and the start call has its own timeout. Explicit solver selection may be refused on an already solved model by the history results guard. A rerun using an explicit solver type and existing results therefore needs targeted validation, not assumed support from one successful fresh-project run. [S26][S28]

On start success the server stores only a process-local pending record `{t0,seen_running:false}`. No durable execution ID, idempotency key, model revision or persisted operation journal is created. Full status queries can make up to three native calls, **each** with `timeout_s` (default 30), so a 30-second application budget is not adequate for worst-case full status. Run-info state lacking timestamps is exposed as `last_reported_state`, not current solver success. [S26][S28]

`cst_wait_for_simulation(max_wait_s=45)` has schema range **0–55**. Intermediate polls query only the running flag about every 2 seconds, with native query budget cut to remaining time and a 1-second floor. Final details are best effort. Documented bound is approximately **max_wait_s + 2 seconds**, plus vendor timeout-enforcement latency and transport/queue overhead. Zero is a bounded one-check route, not zero-time execution. [S26]

| Wait response | Meaning |
| --- | --- |
| `starting` | A pending async launch has not been observed running and is within the 15-second grace period. Do not launch again. |
| `running` | Budget expired while running. Another bounded wait is possible in a healthy session. It is not a timeout-error verdict. |
| `finished,confirmed:true` | This server started the pending solve and observed running before idle. This confirms an activity transition, **not** numerical correctness or successful production of expected results. |
| `finished,confirmed:false` | No pending launch, or never observed running after grace. A fast finish and failure to start remain ambiguous. Warning fields explain this. |
| `error` / unknown running | Do not equate with idle. Native and transport uncertainty must remain distinct. |

The first finished wait clears the pending record. Repeated waits after that can return unconfirmed idle. Disconnect/new server loses it too. Logs, exact discovered result paths/run IDs, saved model context and expected data must supplement activity status. No supported percentage-progress contract was found. [S26][S28]

### Stop is not cancellation

`cst_stop_simulation(timeout_s=30)` maps to native `abort_solver`. A successful command clears the pending record, but the response does not independently prove final idleness, intact partial results or resumability. Pause/resume are separate tools. Request cancellation cancels a yielding handler at an await, but cannot interrupt a blocking native call already running. The worker loop permits interleaving while handlers yield and is not a cross-process lock. A blocking solve prevents later native calls from executing on that thread until it returns. [S2][S26][S28]

Application implications at the committed baseline:

- `CstMcpClient` serializes every tools/call. Its deadline starts at invocation and includes queue time. A stop submitted behind a wait cannot overtake it. Cancelling that wait after SDK dispatch poisons the client rather than freeing a trusted stop channel. [A1]
- After SDK entry, timeout, cancellation, transport failure or SDK response-validation failure records `uncertain` and permanently blocks **every later tools/call**, including `cst_connection_status`, get-status, read-log, disconnect and stop. A queued timeout before dispatch is instead `not_dispatched`. [A1]
- A received server `timeout`/`error` payload is still a **received response** in this client, not automatic terminal transport uncertainty. Upstream native `execution_state:unknown`, `running:null`, partial-change flags and tool errors need their own downstream classification. The server does not globally poison itself after an uncertain history call. [A1][S27][S28]
- `discover_tools()` lists schemas' names but does not reconcile CST state, and constructing a new client explicitly does not reconcile the old attempt. No automatic mutation replay, second launch or arbitrary new-instance recovery is justified. [A1]

The current connectivity check forces disabled mode and `core` toolsets. Changing it to manual mode would change that existing public safety contract. The Controller needs its own specified runtime path without silently altering the check. [A2]

### Subprocess lifetime is a separate prerequisite

The upstream capability clients use a special preserving stdio helper. Their source documents that inspected Windows MCP SDK transports can place descendants in a kill-on-close Job Object. The helper scopes private hooks to avoid that object and limits escalation to the Python server PID. **This preservation policy does not apply automatically to the application**, which imports the ordinary SDK `stdio_client`. This research did not test the application's installed SDK shutdown behavior. “Disconnect does not close CST” must not be strengthened to “any application transport teardown leaves CST alive”. [S18][S30][A1]

### Result invalidation and saved snapshots

History mutations first require idle state. If `results_present()` is **True**, they refuse with `results_exist` to avoid CST's modal incompatible-results dialog. That probe can return **None** and `run_history` only checks `is True`, so it is not a universal fail-closed results-validity guard. Parameter changes are stricter: unknown results state returns `results_state_unknown`; confirmed existing results require `delete_results:true` or prior explicit deletion. Deletion happens **before** parameter storage/rebuild and is not rolled back if later work fails. `rebuild:false` also means changed values need not yet be reflected in geometry. [S33][S27][S28]

The Controller needs to distinguish model state, rebuild state and the state that produced results. Neither an old run ID nor existence of S11 proves a solve reflects current geometry. There is no automatic upstream model/result generation counter. In particular, fresh-project studies do not validate editing an already solved project with result preservation/invalidation. [S7][S9][S26]

Saved-result tools take explicit `project_path`, exact `tree_path`, and discovered `run_id`. Listing paginates with `offset/limit` and returns `next_offset`. Saved reads default to 200-point previews, with `max_points:0` for full samples. They use `cst.results.ProjectFile` and describe data as **last saved project results, excluding unsaved GUI changes**. Native axis labels determine frequency units. 0D scalars preserve absent x axes instead of inventing coordinates. These tools require `manual` rather than `disabled` mode, despite not needing a GUI connection. These are result-reading contracts, not model-state validation. [S16][S31]

An own-project path match permits interactive results access after calling the idle check. **That ownership test compares cached paths only, without requiring a connected project handle.** An offline `cst_open_project` can set that path, and `is_solver_running` returns false with no held project. Source therefore permits this offline reference to select `allow_interactive:true` without proving live ownership/idleness. This edge was not exercised here. For another file, there is likewise no general cross-instance busy-state oracle. Completed/unpacked saved data, sidecars, vendor access restrictions and exact run selection matter. Do not assume a standalone `.cst`, an offline reference, or a path held by another solving process is a safe result snapshot. [S7][S16][S28][S31]

## 7. Existing connected validation: what is actually retained

All paths in this section are relative to **`C:\dev\cst-studio-mcp\`**. Generated reports are ignored local files, not remotely published immutable evidence. Their hashes in section 8 identify the bytes reviewed. Current source/review citations describe procedures and limits, but are not URLs to those generated files.

### Modeling campaign

For parameter fixtures, directory shorthand `P/<scenario>` means `capabilities_test/02_parameters/artifacts/<scenario>`. Each owns `project.cst`, with `metadata.json`, `summary.json`, `summary.md` and invocation-tagged call records. All six inspected summaries report actual live execution, completed scenario and exit 0. Their metadata records a repository HEAD and runner hash, **not complete server-source cleanliness or a server-tree digest**. Therefore the recorded HEAD is attribution, not proof that every native call used exactly that committed tree. [S19]

| Fixture and local evidence | UTC start and invocation | Recorded repository revision | Native evidence and limit |
| --- | --- | --- | --- |
| `P/01_brick` | 2026-10-08T16:19:22.653Z, `ac6192097edc4a1d935c3880b8ab5c3c` | `59b52b7f9673b7932b981f2ee45bf2541b9fbd96` | Copied owned existing project, parameter storage/query, named brick/material, volume/area across parameter change, rebuild and reopen. Not every bound/expression association measured. |
| `P/02_primitives` | 2026-10-12T18:59:19.847Z, `09d0c7cda07c4760bd073b8e7d166d2e` | `ef98514306f4b1ca605851b8c5a6d139459c504d` | Selected primitive volumes/smooth areas and polygon closure/count, rebuild and reopen. Not every coordinate or elliptical-cylinder area independently measured. |
| `P/03_extrusions` | 2026-10-09T10:33:52.055Z, `04e4fcb1bb404bde9d5570ad77ff85d8` | `6d34392a4c117c68481696beac78b4456f0b1b80` | Both extrusion routes, holes, parameters and volume/area persistence. Aggregate quantities do not independently prove direction/winding/offset branches. |
| `P/04_analytical_curve` | 2026-10-09T11:08:07.847Z, `c24aaee2eaa147cc9db486e1a3c4f66b` | `fdd4ea10d52f9340979eb5d73cb24d17dcc77e15` | Parameter/unit readback, named closure and maximum-point count. Endpoints/length not automatically measured. |
| `P/05_face_from_curves` | 2026-10-09T12:14:48.422Z, `320827ff532b48359219c1244f60c363` | `b8627b38879be0ba4d9968d6bf6775d3e536cf73` | Qualified closed curve to named Vacuum sheet, type/faces and raw area persistence. One-sided planar-area convention unestablished. |
| `P/06_loft` | 2026-10-12T19:00:28.128Z, `41ed40cb03ed464a92848ebf8390c638` | `ef98514306f4b1ca605851b8c5a6d139459c504d` | Explicit 3D rectangular/prismatic fixture, parameters/type/material/volume/area and reopen. Not arbitrary loft topology. |

The committed parameter review records **earlier** primitives/loft invocation IDs. The current local summaries above are later invocations. The review also records user confirmation of agreed manual inspections, separately from automatic measurements. That record does not manufacture absent coordinates, endpoint lengths or sheet counting conventions. [S19]

Boolean operation evidence is preserved in `capabilities_test/03_booleans/artifacts/01_operations/metadata.jsonl` **lines 7–12** and invocation-tagged call logs for **`54fa1e64b7f14d8bb9c0d4095a4593cd`**, starting **2026-10-09T14:15:20.343Z**, recorded revision **`dbad81d6251e08e429a8c5a2b28b54a16e60297c`**, ending 14:15:50.862Z with exit 0. The committed assessment records **617 passing checks**, parametric shift 2→3, geometry membership/materials/volumes/areas/selected points, witness preservation and save/reopen. The owned target was `.../01_operations/project.cst`. Its latest summary is instead **preflight** invocation `b07debb60edb4a7db0d6c7839d4fab50`, and must not be substituted for live evidence. [S23]

The current boolean errors summary is a later live invocation **`4b12bfe3c3bd4790ab3f2ee2ba9b7e0e`**, **2026-10-12T18:54:47.115Z**, recorded revision **`ef98514306f4b1ca605851b8c5a6d139459c504d`**, exit 0. Each case owned `capabilities_test/03_booleans/artifacts/02_errors/<case>/project.cst`. All nine schema/argument/native rejection cases passed with integrity readbacks and normal closure. This is later than the errors ID in the committed review. The errors stage does not add reopen coverage, and unchanged geometry does not prove history absence. [S23]

Batch 01 has both older failed assessments and a later local exit-0 run, **`run_20261012T190754_564640Z_13d9bdf963`**, start **2026-10-12T19:07:54.567Z**, recorded revision **`ef98514306f4b1ca605851b8c5a6d139459c504d`** with **dirty runner files**. Evidence lives under `capabilities_test/01_project_geometry_materials/runs/<run-id>/`, including its owned `project.cst`. It records new-instance connection, create/save/reopen, effective units and primitive/extrusion/wire solid names, material reassignment and persistence. It does not independently establish EM properties or every dimension. Its table retains outdated face/loft/torus limitation wording despite accepted responses. Prefer dedicated later fixtures for those capability claims. The committed “Batch 01 exit 1” assessment is a historical run, not a summary of every later local invocation. [S18][S19]

### Antenna campaign: execution success differs from scientific acceptance

All three use owned `capabilities_test/04_antenna_simulation/<name>/project/<name>.cst`. Primary reports are `<name>/reports/validation.md`, supported by `<name>/results/{metadata,validation}.json` and numbered MCP response records. They used explicit units and solid/material enumeration VBA, not just the proposed typed inventory. They are deterministic clients, **not LLM conversation trials**. [S21]

| Run | Provenance | Recorded native operations and outcome |
| --- | --- | --- |
| Dipole | **2026-10-13T13:33:54.405Z**, HEAD `ccdf0efc2b760dcebe7caad6164fb544104fabcd`, **dirty** session/curves/boundaries/materials/mesh/results/import-export files, plus untracked library/runner sources | Native copper load, cylinders/discrete port, ordinary TD/domain/mesh/monitor setup, **one blocking solve**, full saved/live S11, Touchstone consistency, radiation/power criteria and persistence. Exit **0**, 228 passed, 3 unsupported, 44 inconclusive. Does not validate async dipole launch, local gap resolution or mesh convergence. |
| Patch | **2026-10-14T07:58:35.743Z**, HEAD `917009abfddf3c58a271e132aca8c384f8f8a215`, **dirty** `tools/solvers.py`, runner/common/docs | Native library PEC/RT-duroid, four bricks/Insert/discrete port, Tet FD setup and monitors, async call 44, bounded waits 45–66, finished `confirmed:true`, main S11/run 0 and requested farfields, 24 samples, save/close/reopen. Workflow reached phase I, but exit **1**, failed **patch directivity diagnostic**. Impedance-zero-crossing resonance 2.37418 GHz is not blanket physical validation. A local reassessment at 08:22:05.754Z made no native calls/solve and corrected an export assessment. |
| WR-90 | **2026-10-14T18:52:46.325Z**, HEAD `917009abfddf3c58a271e132aca8c384f8f8a215`, **dirty** `tools/ports.py`, `tools/solvers.py`, runner/common/docs | Native library PEC, bricks/add/subtract, internal waveguide port, Hex/TD/domain/monitor setup, async call 43, waits 44–45, finished `confirmed:true`, full 1,001-point modal S11 and persistence. Later reassessment after call 131 and an approved scalar reader correction made additional reads, **no new solve**. Cutoff about 6.55550 GHz and common-reference Touchstone comparison passed. Overall exit **2**, incomplete. Modal field exports lacked numeric rows, loss data/power balance and visible figures retain limitations. |

Specific call/effect distinctions are retained in those reports. Patch port listing returned `popup:false`, total/ID text only. Solver info read back fmin/fmax/port count but not all FD residual/adaptation settings. Mesh readbacks provide counts/edges and unavailable Hex-only fields on Tet, not proof of feed/substrate resolution. Fresh results and a completed solve do not imply theoretical agreement or convergence. None of these runs exercised stop/abort, transport cancellation recovery, or editing/re-solving an arbitrary user's already solved project. [S21]

**Revision limitation:** current upstream is clean at `a4a177...`, but these runs predate it and explicitly record dirty sources for the antenna campaign. A later commit containing fixes does not retroactively establish a clean-revision rerun. Installed-library source hashes and geometry/material names are provenance and association evidence, not independent EM-property measurement. No blanket connected pass of the current 192-tool catalogue is supported.

## 8. Local evidence fingerprints

These SHA-256 values were computed during read-only review. They identify local evidence, **not** CST project integrity or reproducibility of an unrecorded dirty server tree. Paths use the section 7 root. Full logs, project binaries and all numerical exports were not copied into this report.

| Evidence file | SHA-256 |
| --- | --- |
| `02_parameters/artifacts/01_brick/summary.json` under `capabilities_test/` | `e4229708a45f91990ccdf11ab23d889faa614e0148ca2dcf97b9cf5740263d04` |
| `02_parameters/artifacts/02_primitives/summary.json` | `94a4d3a873bba121172d30a70b8908fa2343fdee5ded56b9807087c58628317c` |
| `02_parameters/artifacts/03_extrusions/summary.json` | `90f9f58b2d097ab88c43aa88cb0fc194ab22e68c91c0cf2312676861020ac695` |
| `02_parameters/artifacts/04_analytical_curve/summary.json` | `2248239109751f01a7c2729d04a8920e6565318c754fb10ddb959d6a50eebc06` |
| `02_parameters/artifacts/05_face_from_curves/summary.json` | `5205d3c51f509f587b28e6d43274881eae8487a806e17cfed5cc2fc1dbfe3a5f` |
| `02_parameters/artifacts/06_loft/summary.json` | `d584ba2990ed981feff05d33e75d51a8654b5de02af398a0640a63b1be2c9b9b` |
| `03_booleans/artifacts/01_operations/summary.json` (**preflight**) | `15190615da40ff0864fafc4dbb6ad418c8ca10734c64408bb4194e4a5655197d` |
| `03_booleans/artifacts/01_operations/metadata.jsonl` (**includes live history**) | `d36001a5b6bb0fda97ddec212cd0800c42d1bdee3e76ae086daa34858c9ca710` |
| `03_booleans/artifacts/02_errors/summary.json` | `495d339e2bb5639930ec520a85865267a82bd7cf8096409288321f9974d2bcc1` |
| `01_project_geometry_materials/runs/run_20261012T190754_564640Z_13d9bdf963/summary.json` | `bba3d0d699b5643c902c5bb0a81f5391fd500e38939fc3a645f9449c6143b671` |
| `04_antenna_simulation/dipole/results/metadata.json` | `a2b8e247324cacded8e5a1eea2736cb29c265d6bcaf3520b81d514e3f020e1d6` |
| `04_antenna_simulation/dipole/reports/validation.md` | `4b4ac7891426848f756379ed418a437cc8672348f5f6a3bb397508a41c81bdae` |
| `04_antenna_simulation/patch/results/metadata.json` | `c36ba4dd0d1ece12de80517a43b329f9f3c5ff0677c6381849fccf240147d64d` |
| `04_antenna_simulation/patch/reports/validation.md` | `f1dca28060575621fd363f65da7cd50fef795e967f5dbef8b507a6be3161e689` |
| `04_antenna_simulation/wr90/results/metadata.json` | `0c9b078218d4def8ed2ac7a9d89f0a6d3673da8e90290897dcd2681b78ce7e39` |
| `04_antenna_simulation/wr90/reports/validation.md` | `fa0cdddbbf68353ffa5a04738d55aeee832338c498bbb20102d8be93bb24eda6` |

All rows after the first also use the `capabilities_test/` prefix. Exact timestamps, project paths and recorded revisions come from sibling metadata or the invocation-tagged boolean metadata history, not inferred filesystem mtimes.

## 9. Comparison with the local candidate proposal

| Candidate lines | Research result |
| --- | --- |
| 13–17, 109–320 | Recount confirms 192 total, 72 unique group tools plus status = 73 MCP tools. All selected names exist. Nineteen groups are an application proposal, not upstream categories or connected acceptance. |
| 30–55 | Manual startup and offline-open distinction match source. Add already-connected `new` no-op, adoption fallback, cached identity and unit prerequisites. |
| 83–107, 429–435 | Canonical-schema activation is sensible as an unimplemented contract. Baseline discovery only returns names. Server categories are startup-bound and typo fallback can expose all. No current catalogue-change notifications were found. |
| 145–147, 348–360, 441–447 | Parameter/rebuild and unsupported arbitrary edits are correctly bounded. **Get/list do not actually return stored expressions despite descriptions and proposal claims.** Preserve per-field expression limits and destructive deletion semantics. Unit gap remains real, including misleading `cst_set_units` text upstream. |
| 151–160, 223–225, 370 | Bundled material/setup-check limits and RLC restriction are confirmed. Native material library loading has a stricter local-file parser. Port list does not prove applied feed geometry. |
| 234, 243, 255, 386 | Mutation **annotations** still exist, but handlers now use no-history capture. Do not perpetuate annotation rationale as current implementation fact. Validate history delta if that property becomes an acceptance requirement. |
| 372–380, 484 | Async/bounded waiting matches source, but a native timeout parameter is not the end-to-end budget. Most importantly, after transport uncertainty **the same committed client cannot issue the proposed state check**. No new-client reconciliation procedure is established. |
| 382–388 | Broad dialog tools can choose actions across CST windows. Do not confuse them with the targeted startup notice watcher. |
| 390–408, 467, 480 | Results Analyst and `analyze_results` are unimplemented and outside map scope. Saved-result tools exist independently. The map explicitly rejects exposing a nonfunctional analyst handoff. |
| 431 | `all` makes tools available, not safe to dispatch. `core` in the existing connectivity path is insufficient for construction. Role enforcement is separate. |
| 451–457 | State/provenance tracking remains application work. Cached path and pending solve are not durable IDs or current-result proof. Include subprocess survival and terminal uncertainty, not just model history. |
| 475–486 | Useful candidate scenarios, not acceptance already achieved. Existing deterministic runs partly overlap but do not validate Qwen conversations, the proposed 18-function limit, Controller discovery or arbitrary existing-project edits. |

The three-tool startup, 18-function cap, selected inventory and analyst handoff are **not adopted by this research**. The map's current scope supersedes the proposal's analyst implementation route.

## 10. Narrow downstream questions and prerequisites

These are specifiable follow-ups, not decisions or authorization to run them now.

1. **Unit interface prerequisite:** what minimal typed read/configure contract establishes effective units for a fresh and an existing project without general raw VBA? Must changing units be allowed, and how are existing geometry/results affected? Target a controlled non-mm/non-GHz fixture to expose conversion errors. Until resolved, define exactly what human-established unit evidence dimension-sensitive work can accept.
2. **Existing-target identity prerequisite:** is existing-only/PID-targeted attachment required for initial user intents, or is the current ambiguity an explicitly reported unsupported route? What independent live project identity and expected-target precondition are needed before mutation, especially with multiple projects or GUI switching? For saved reads, should interactive access require a real held project rather than cached offline path equality?
3. **Uncertainty and stop/runtime boundary:** how does the Controller halt and explain an uncertain attempt when same-client queries/stop are prohibited? If separate reconciliation is ever supported, what trusted target evidence and no-replay protocol makes it valid? Separately prototype Windows subprocess teardown survival, and bounded stop responsiveness behind a wait, on an agreed disposable target. Do not first create uncertainty merely to discover that the safety path is undefined.
4. **Solved-parameter edit lifecycle:** on an agreed copy with known results, validate inspect→authorized invalidation→parameter change→rebuild→save→async re-solve→new-result evidence. Include rebuild failure, `rebuild:false`, unknown result probe and explicit solver selection with old results. Existing unsolved parameter fixtures and fresh antenna runs do not cover this whole chain.
5. **Schema/exposure prototype:** retain the exact effective canonical schemas, descriptions and annotations and test their conversion through the actual endpoint/SDK. Include number/string unions, permissive parameter value, optional fields and missing filtered tools. Establish atomic group replacement and execution enforcement without assuming the candidate cap or categories are final.
6. **Validation provenance refresh:** which smallest representative native runs must be repeated on a clean pinned upstream, recording vendor ABI/version, complete server-source identity, owned project, units, observed effects and model/result linkage? Reuse existing evidence rather than rerunning all 192 tools. Keep the patch directivity failure and incomplete WR-90 assessment separate from successful Controller-level execution.
7. **Readback gaps and annotations:** what minimal stored-parameter-expression readback is required to inspect existing parameterized projects without substituting numeric values for unknown dependency expressions? Are no-history solver/mesh reads, actual port attributes and material properties necessary for the first acceptance criteria? Specify and verify the exact readbacks rather than widening raw VBA. Correcting stale docs/annotations is a separate narrow upstream task, not work done here.

Missing connected evidence remains explicit for stop/pause/resume, strict existing-instance targeting, ambiguous recovery, non-mm unit handling, general transforms/CAD import/export across arbitrary models, broad dialog recovery safety, arbitrary existing-project mutation and Controller conversations. Catalogue membership alone fills none of these gaps.

## 11. Checks performed and remaining limits

- Confirmed Git pins and source cleanliness, and matched upstream remote main/HEAD using Git.
- Read full GitHub ticket/map requirements via GitHub CLI, with no issue writes.
- Parsed upstream source with AST without importing it. Counted 192 unique registered tool names, verified the proposal's 72-group/73-with-status inventory and absence of dedicated unit names. The initial direct-`Tool` count omitted the `official.tool` helper and was corrected before reporting.
- Inspected relevant schemas, handlers, worker/session behavior and the exact application baseline. Read retained modeling/antenna summaries and selected metadata, including historical boolean invocation records. Computed proposal, catalogue-names and evidence hashes.
- Documentation scope/whitespace and source-permalink line ranges were checked before commit. No native or endpoint tests were run. No upstream test/preflight suite was executed because source/evidence-only review did not require server execution.

Limits: this is not exhaustive numerical reanalysis, visual CAD inspection, a CST-vendor API compatibility certification, or a new connected test campaign. Local ignored evidence may be replaced by future runs and is not available in a clean clone. Earlier revisions/dirty states cannot be promoted to current clean-revision validation. Source docs and local latest reports disagree in places, and those differences are preserved rather than silently reconciled into a stronger claim.

## Primary-source permalinks

All `S` links pin upstream `a4a177aeb0856dbf0f668f2dc5a8ca06e20ac8c2`. `A` links pin application `2f5d809e3ca82b726fac407cc89ba6ab58de786d`.

[S1]: https://github.com/GoncaGomes/cst-mcp/blob/a4a177aeb0856dbf0f668f2dc5a8ca06e20ac8c2/src/cst_mcp/tools/__init__.py#L7-L78
[S2]: https://github.com/GoncaGomes/cst-mcp/blob/a4a177aeb0856dbf0f668f2dc5a8ca06e20ac8c2/src/cst_mcp/tools/registry.py#L38-L440
[S3]: https://github.com/GoncaGomes/cst-mcp/blob/a4a177aeb0856dbf0f668f2dc5a8ca06e20ac8c2/src/cst_mcp/server.py#L24-L92
[S4]: https://github.com/GoncaGomes/cst-mcp/blob/a4a177aeb0856dbf0f668f2dc5a8ca06e20ac8c2/src/cst_mcp/config.py#L19-L202
[S5]: https://github.com/GoncaGomes/cst-mcp/blob/a4a177aeb0856dbf0f668f2dc5a8ca06e20ac8c2/src/cst_mcp/tools/connection.py#L9-L74
[S6]: https://github.com/GoncaGomes/cst-mcp/blob/a4a177aeb0856dbf0f668f2dc5a8ca06e20ac8c2/src/cst_mcp/session.py#L93-L319
[S7]: https://github.com/GoncaGomes/cst-mcp/blob/a4a177aeb0856dbf0f668f2dc5a8ca06e20ac8c2/src/cst_mcp/session.py#L337-L433
[S8]: https://github.com/GoncaGomes/cst-mcp/blob/a4a177aeb0856dbf0f668f2dc5a8ca06e20ac8c2/src/cst_mcp/tools/project.py#L280-L610
[S9]: https://github.com/GoncaGomes/cst-mcp/blob/a4a177aeb0856dbf0f668f2dc5a8ca06e20ac8c2/src/cst_mcp/tools/parameters.py#L26-L132
[S10]: https://github.com/GoncaGomes/cst-mcp/blob/a4a177aeb0856dbf0f668f2dc5a8ca06e20ac8c2/src/cst_mcp/tools/geometry.py#L27-L486
[S11]: https://github.com/GoncaGomes/cst-mcp/blob/a4a177aeb0856dbf0f668f2dc5a8ca06e20ac8c2/src/cst_mcp/tools/materials.py#L634-L925
[S12]: https://github.com/GoncaGomes/cst-mcp/blob/a4a177aeb0856dbf0f668f2dc5a8ca06e20ac8c2/src/cst_mcp/tools/annotations.py#L24-L178
[S13]: https://github.com/GoncaGomes/cst-mcp/blob/a4a177aeb0856dbf0f668f2dc5a8ca06e20ac8c2/src/cst_mcp/tools/solvers.py#L391-L744
[S14]: https://github.com/GoncaGomes/cst-mcp/blob/a4a177aeb0856dbf0f668f2dc5a8ca06e20ac8c2/src/cst_mcp/tools/ports.py#L25-L681
[S15]: https://github.com/GoncaGomes/cst-mcp/blob/a4a177aeb0856dbf0f668f2dc5a8ca06e20ac8c2/src/cst_mcp/tools/mesh.py#L264-L479
[S16]: https://github.com/GoncaGomes/cst-mcp/blob/a4a177aeb0856dbf0f668f2dc5a8ca06e20ac8c2/src/cst_mcp/tools/official.py#L21-L388
[S17]: https://github.com/GoncaGomes/cst-mcp/blob/a4a177aeb0856dbf0f668f2dc5a8ca06e20ac8c2/pyproject.toml#L5-L46
[S18]: https://github.com/GoncaGomes/cst-mcp/blob/a4a177aeb0856dbf0f668f2dc5a8ca06e20ac8c2/capabilities_test/01_project_geometry_materials/README.md#L7-L214
[S19]: https://github.com/GoncaGomes/cst-mcp/blob/a4a177aeb0856dbf0f668f2dc5a8ca06e20ac8c2/capabilities_test/02_parameters/REVIEW.md#L6-L122
[S20]: https://github.com/GoncaGomes/cst-mcp/blob/a4a177aeb0856dbf0f668f2dc5a8ca06e20ac8c2/src/cst_mcp/tools/vba.py#L29-L58
[S21]: https://github.com/GoncaGomes/cst-mcp/blob/a4a177aeb0856dbf0f668f2dc5a8ca06e20ac8c2/capabilities_test/04_antenna_simulation/README.md#L138-L745
[S22]: https://github.com/GoncaGomes/cst-mcp/blob/a4a177aeb0856dbf0f668f2dc5a8ca06e20ac8c2/docs/API_REVIEW.md#L9-L88
[S23]: https://github.com/GoncaGomes/cst-mcp/blob/a4a177aeb0856dbf0f668f2dc5a8ca06e20ac8c2/capabilities_test/03_booleans/REVIEW.md#L6-L109
[S24]: https://github.com/GoncaGomes/cst-mcp/blob/a4a177aeb0856dbf0f668f2dc5a8ca06e20ac8c2/src/cst_mcp/material_library.py#L18-L185
[S25]: https://github.com/GoncaGomes/cst-mcp/blob/a4a177aeb0856dbf0f668f2dc5a8ca06e20ac8c2/src/cst_mcp/tools/diagnostics.py#L182-L244
[S26]: https://github.com/GoncaGomes/cst-mcp/blob/a4a177aeb0856dbf0f668f2dc5a8ca06e20ac8c2/src/cst_mcp/tools/simulation.py#L19-L589
[S27]: https://github.com/GoncaGomes/cst-mcp/blob/a4a177aeb0856dbf0f668f2dc5a8ca06e20ac8c2/src/cst_mcp/session.py#L439-L839
[S28]: https://github.com/GoncaGomes/cst-mcp/blob/a4a177aeb0856dbf0f668f2dc5a8ca06e20ac8c2/src/cst_mcp/session.py#L847-L1070
[S29]: https://github.com/GoncaGomes/cst-mcp/blob/a4a177aeb0856dbf0f668f2dc5a8ca06e20ac8c2/src/cst_mcp/cst_client.py#L164-L205
[S30]: https://github.com/GoncaGomes/cst-mcp/blob/a4a177aeb0856dbf0f668f2dc5a8ca06e20ac8c2/docs/RELIABILITY_REVIEW.md#L49-L134
[S31]: https://github.com/GoncaGomes/cst-mcp/blob/a4a177aeb0856dbf0f668f2dc5a8ca06e20ac8c2/src/cst_mcp/execution/curves.py#L15-L64
[S32]: https://github.com/GoncaGomes/cst-mcp/blob/a4a177aeb0856dbf0f668f2dc5a8ca06e20ac8c2/src/cst_mcp/session.py#L1899-L1936
[S33]: https://github.com/GoncaGomes/cst-mcp/blob/a4a177aeb0856dbf0f668f2dc5a8ca06e20ac8c2/src/cst_mcp/tools/parameters.py#L645-L936
[S34]: https://github.com/GoncaGomes/cst-mcp/blob/a4a177aeb0856dbf0f668f2dc5a8ca06e20ac8c2/src/cst_mcp/tools/boundaries.py#L239-L379
[S35]: https://github.com/GoncaGomes/cst-mcp/blob/a4a177aeb0856dbf0f668f2dc5a8ca06e20ac8c2/src/cst_mcp/tools/transforms.py#L25-L163
[S36]: https://github.com/GoncaGomes/cst-mcp/blob/a4a177aeb0856dbf0f668f2dc5a8ca06e20ac8c2/src/cst_mcp/tools/geometry.py#L542-L1176
[S37]: https://github.com/GoncaGomes/cst-mcp/blob/a4a177aeb0856dbf0f668f2dc5a8ca06e20ac8c2/src/cst_mcp/cst_client.py#L38-L100
[S38]: https://github.com/GoncaGomes/cst-mcp/blob/a4a177aeb0856dbf0f668f2dc5a8ca06e20ac8c2/src/cst_mcp/dialog_handler.py#L292-L455
[S39]: https://github.com/GoncaGomes/cst-mcp/blob/a4a177aeb0856dbf0f668f2dc5a8ca06e20ac8c2/src/cst_mcp/tools/parameters.py#L1045-L1107
[A1]: https://github.com/GoncaGomes/cst-agentic/blob/2f5d809e3ca82b726fac407cc89ba6ab58de786d/src/cst_agentic/mcp_client.py#L1-L440
[A2]: https://github.com/GoncaGomes/cst-agentic/blob/2f5d809e3ca82b726fac407cc89ba6ab58de786d/src/cst_agentic/config.py#L63-L77
