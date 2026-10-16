# CST-Agentic Plan

## Objective and boundaries

Build a Python chatbot using the OpenAI Agents SDK and the institutional Qwen endpoint (`SKYNET_BASE_URL`), initially with `qwen3.8-27b`.

The intended application has two agents:

- **CST Controller:** interprets user requests and controls CST through an explicitly allowed subset of MCP tools. The model selects individual calls, observes their responses, and continues the conversation.
- **Result Analyst:** produces reports when requested, using separately assigned result-reading, analysis, and reporting tools. Modeling and simulation control remain with the Controller.

The existing `C:\dev\cst-studio-mcp` repository supplies CST execution capabilities and remains read-only reference material. CST-Agentic owns conversation, agent orchestration, tool access, execution records, and outcome handling. Reuse server capabilities rather than duplicating CST automation in the client.

Develop the Controller first. Keep implementation simple and incremental. The first demonstration evaluates prescribed tool use and simulation execution; autonomous design optimization and report generation are outside its scope.

## Milestones

1. **Verify model and MCP connectivity**
   - Load configuration from `.env` without exposing credentials.
   - Verify model access and tool calling through the institutional endpoint using provider defaults, without explicit reasoning overrides.
   - Connect to the existing MCP server and discover tools with CST connection disabled.

2. **Implement the minimal Controller chatbot**
   - Provide a terminal conversation interface with conversation context.
   - Expose an explicit tool allowlist and execute calls sequentially, returning responses to the model.
   - Record conversation and tool execution evidence, including arguments, responses, timestamps, and project or simulation identifiers when available.
   - Handle failures and uncertain execution states explicitly; do not automatically replay uncertain mutations.

3. **Demonstrate prescribed patch construction and simulation**
   - Derive an instructional prompt from phases A-D of the reference [patch script](../cst-studio-mcp/capabilities_test/04_antenna_simulation/run_patch.py).
   - Have the LLM issue individual MCP calls in the prescribed order. Do not expose composite antenna workflow helpers or use Python to perform the modeling sequence on the model's behalf.
   - Preserve the reference geometry, materials, solver, mesh, and monitor settings. Use a client-owned workspace without modifying the server repository or its reference artifacts.
   - Start one simulation, use repeated bounded waits, save, and discover the expected results.
   - Require native status and expected saved S11 and farfield results; idle solver state alone does not establish success.
   - Compare actual model-selected calls, arguments, and outcomes with the prescribed sequence. Record deviations explicitly.
   - Keep the reference script's later numerical assessments, plots, exports, and reporting outside this demonstration.

4. **Introduce the Result Analyst**
   - Delegate reporting when the user requests it, using dedicated analysis and reporting tools.
   - Pass explicit project and simulation identifiers and relevant design history.
   - Reuse suitable MCP result capabilities and build additional analysis tools as needed.

5. **Add persistent session memory**
   - Restore conversation and relevant project context across sessions.
   - Preserve the tool history and design changes that led to the final model.
   - Make that evidence available to subsequent reports.

## Current work

Milestone 1 ([T001: Verify model and MCP connectivity](docs/tasks/T001-verify-model-mcp-connectivity.md)) is implemented and verified: the offline suite passes and the disabled-mode integration check against the institutional endpoint and the real MCP server succeeded. Evidence is recorded in the task file.

The next actionable step is milestone 2: the minimal Controller chatbot.

## Next steps

1. Implement the minimal chatbot, restricted tool access, and execution record (milestone 2).
2. Prepare and review the patch prompt, exact tool allowlist, and demonstration acceptance criteria.
3. Perform live validation only after explicit authorization. Record instruction-following results separately from native execution evidence.

## Decisions and blockers

Established direction:

- Python >=3.12; run Python commands through `uv run`.
- OpenAI Agents SDK with institutional Qwen inference and initial model `qwen3.8-27b`.
- Endpoint tool-calling is verified in CST-Agentic: the model called `cst_connection_status` through MCP using an OpenAI SDK client with a configurable `base_url` (T001).
- T001 uses provider defaults without explicit reasoning or thinking overrides. The effective reasoning behavior is unverified; explicit configuration and its validation are deferred and do not block T001.
- Confirmed configuration variable names are `SKYNET_BASE_URL`, `SKYNET_API_KEY`, `AGENT`, `CST_MCP_SERVER_EXECUTABLE`, and `CST_MCP_SERVER_CWD`. The corrected MCP launcher is `.venv/Scripts/cst-studio-mcp.exe` in the reference checkout, invoked without additional arguments. The executable and configured working directory exist; credentials have not been displayed.
- The first example uses individual MCP calls selected by the LLM from an explicit patch prompt, with sequential execution and an enforced allowlist.
- Controller first; the reporting agent and persistent session restoration follow later. Initial conversation context and execution logging support those later capabilities.

To verify or finalize:

- Exact demonstration prompt and tool allowlist, including restriction of `cst_execute_vba` to the three fixed reference blocks for units setup, units readback, and shape enumeration.
- Proposed local execution logging and disabled OpenAI trace export.
- Model-turn limits, overall simulation waiting budget, failure handling, and owned-workspace lifecycle.
- The chosen patch scenario's behavior through the new agent client. Existing server tools and reference procedures do not establish that the new integration works.

No planning blocker remains for milestone 2.

## Completed work and evidence

- Inspected [repository instructions](AGENTS.md), [README](README.md), [application scaffold](main.py), and [project metadata](pyproject.toml). At inspection, the application printed a greeting and declared Ruff as its only dependency; `PLAN.md` was empty.
- Reviewed the MCP server's [README](../cst-studio-mcp/README.md), [agent setup guide](../cst-studio-mcp/docs/AGENT_SETUP.md), relevant implementation, and [patch scenario documentation](../cst-studio-mcp/capabilities_test/04_antenna_simulation/README.md#rectangular-patch-scenario).
- Established the client/server responsibility boundary and first-demonstrator direction through discussion. The user approved writing the roadmap to `PLAN.md`.

- Created the T001 specification, confirmed the corrected MCP launcher against its installed entry point, and deferred explicit reasoning configuration with user approval. No connectivity check has been executed.

- Implemented and verified T001 (milestone 1): the `verify-connectivity` command, the `cst_agentic` package, the offline test suite (30 passing), and a passing disabled-mode integration run; see the [task file](docs/tasks/T001-verify-model-mcp-connectivity.md) for evidence.

The earlier items are planning and inspection outcomes. Milestone 1 is complete as recorded above; no CST session or simulation was started at any point.
