# CST-Agentic Plan

## Objective and boundaries

Build a reliable CST chatbot using Python >=3.12, the OpenAI Agents SDK, and institutional Qwen inference (`SKYNET_BASE_URL`), initially `qwen3.8-27b`. Run Python through `uv run`.

Focus solely on the Controller: conversation, supported project inspection/modification, simulation configuration/execution, completion verification, and saving projects and expected results. No scientific analysis or reports.

Build bottom-up: restricted execution, a prepared-project demonstration, prescribed construction, then broader tool exposure. Prefer reliable completion over catalogue coverage.

Reuse capabilities from the read-only MCP repository at `C:\dev\cst-studio-mcp`. This application owns conversation, tool restrictions, records, and outcome handling, not duplicate CST automation. Use client-owned workspaces and preserve reference artifacts.

## Milestones

Use one branch per milestone and one commit per task on that branch. Start milestone work on its branch, not `main`. M2's branch exists. M3-M5 branches are not created. Link tasks when prepared with approval.

1. **M1: Verify model and MCP connectivity**
   - Branch: `feat/model-mcp-connectivity`. Dependencies: none. Task: [T001](docs/tasks/T001-verify-model-mcp-connectivity.md).
   - Contract: model-selected `cst_connection_status` through MCP with CST disabled, bounded failures, and no credential exposure. This does not verify native CST operations.
2. **M2: Reliable execution foundation**
   - Branch: `feat/controller-execution-foundation`. Depends on M1. Task: [T003](docs/tasks/T003-record-and-serialize-mcp-attempts.md).
   - Contract: sequential MCP calls, enforced allowlists, explicit project targets, execution records, bounded requests, and uncertain-outcome handling. Verify independently of model decisions. Never automatically replay uncertain mutations.
3. **M3: Minimal Controller runs an existing project**
   - Branch: `feat/controller-existing-project`. Depends on M2. Tasks: not prepared.
   - Contract: terminal conversation identifies a preconfigured project, launches one simulation, follows bounded waits to a confirmed outcome, saves, and verifies expected saved results. Use minimal tools. No geometry construction.
4. **M4: Prescribed patch construction and simulation**
   - Branch: `feat/controller-patch-demo`. Depends on M3. Tasks: not prepared.
   - Contract: individual model-selected calls follow phases A-D of the reference [patch script](../cst-studio-mcp/capabilities_test/04_antenna_simulation/run_patch.py), preserving its settings. Verify native completion and saved S11/farfield availability. Record deviations. No composite helpers or application-performed modeling sequence.
5. **M5: Expand Controller tool exposure**
   - Branch: `feat/controller-tool-discovery`. Depends on M4. Tasks: not prepared.
   - Contract: evaluate progressive exposure against the restricted baseline for concrete tasks. Measure schema tokens, invalid calls, discovery overhead, latency, and completion before adopting groups or limits.

## Current work

| Milestone | Implementation | Verification | Independent review | Integration |
| --- | --- | --- | --- | --- |
| M1 | Recorded in T001 | Offline and disabled-mode runs recorded | No final report recorded in T001 | Connectivity merge `9d40a51` is in `main` history |
| M2 | T003 implemented, M2 partial | 49 prior full, 39 final targeted | T003: R1-R5 resolved | Not integrated |
| M3-M5 | Not started | Not run | Not reviewed | Not integrated |

Git handoff checkpoint: `feat/controller-execution-foundation` at `d591d20`, index empty. All eight pending paths are reviewed with no blockers. Two commits are authorized: planning/guidance, then T003. Commit receipts belong in the delivery handoff, not a claim that M2 is integrated.

## Next steps

1. Complete the two authorized commits, then continue M2 subplanning. M2 remains incomplete after T003.
2. Obtain scope and approach approval for further tasks before implementation.
3. Resolve M3's fixture, exact tools, completion evidence, and saved-result contract before implementation.
4. Connected CST validation requires explicit authorization. Separate model instruction-following evidence from native execution evidence.

## Decisions and blockers

- The local, intentionally untracked `docs/CST_Controller_Tool_Discovery_Plan.md` proposes 73 tools, 19 groups, and an 18-function limit. It is not an implementation commitment or a required checkout artifact.
- Application checks are independent of model judgment. Idle solver state or saving alone does not prove successful simulation and saved results.
- Resolve timeouts, waiting budgets, failure states, workspace ownership, records, and disabled external trace export during affected planning.
- Establish units before dimension-sensitive construction. Prior patch planning considered three fixed VBA blocks. Discovery excludes VBA. Resolve this conflict before affected tasks.
- T001 uses provider defaults. Reasoning configuration/behavior remains deferred and unverified. Configuration and launcher references: T001 and [README](README.md).

## Deferred work

Retain the future two-agent architecture. The Results agent, its tools, reports, and delegation are on hold. No `analyze_results` placeholder. Persistent session restoration and optimization are also deferred.

## Completed work and evidence

- T001 records 34 passing offline tests after timeout corrections and passing institutional-endpoint/MCP connectivity with CST disabled. These historical checks did not exercise CST attachment or simulations.
- Git history includes connectivity merge `9d40a51` and workflow merge `d591d20`. Integration evidence does not supply missing review reports.
- The user approved the roadmap, T003, M2 branch creation, and two commits of the pending work, including the user's updated maintainer profile. Live CST operations, push, merge, and agent-performed permission changes remain unauthorized.
