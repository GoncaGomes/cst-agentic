# T001: Verify model and MCP connectivity

Status: implemented and verified (offline suite plus disabled-mode integration run); in review — the MCP per-request timeout fix is pending re-review. Explicit reasoning configuration is deferred.

## Objective

Provide an explicit command that verifies the OpenAI Agents SDK can use institutional Qwen inference to call `cst_connection_status` through the existing MCP server, with CST connection disabled.

## Context and dependencies

- Implements milestone 1 of [PLAN.md](../../PLAN.md).
- At planning time, [main.py](../../main.py) only prints a greeting and [pyproject.toml](../../pyproject.toml) declares Ruff as its only dependency. No application tests or connectivity command exist.
- Confirmed `.env` variable names are `SKYNET_BASE_URL`, `SKYNET_API_KEY`, `AGENT`, `CST_MCP_SERVER_EXECUTABLE`, and `CST_MCP_SERVER_CWD`. The configured MCP executable is `C:\dev\cst-studio-mcp\.venv\Scripts\cst-studio-mcp.exe`, invoked without additional arguments, with working directory `C:\dev\cst-studio-mcp`. Its installed entry point is `cst_mcp.server:main`. Both paths exist. Credentials were not displayed, and no network or MCP connection was attempted.
- Use the configured institutional model; the agreed initial model is `qwen3.8-27b`. The user reports that the endpoint supports tool calls and an OpenAI Python SDK client with configurable `base_url`. These capabilities have not been verified through this application.
- Use provider defaults without explicit reasoning or thinking overrides. This does not establish whether reasoning is enabled or disabled internally. Explicit reasoning configuration and validation are deferred and do not block this task.
- Follow the reference server's [disabled-mode acceptance procedure](../../../cst-studio-mcp/docs/AGENT_SETUP.md#disabled-mode-acceptance) and [client configuration instructions](../../../cst-studio-mcp/README.md#mcp-client-setup).
- Consult the official [SDK model/provider guidance](https://developers.openai.com/api/docs/guides/agents/models) and [SDK MCP integration guidance](https://developers.openai.com/api/docs/guides/agents/integrations-observability) when selecting compatible client dependencies and wiring.
- External verification requires access to the institutional endpoint and an installed, runnable MCP server. Neither endpoint reachability nor server startup has been checked.

## Scope

Included:

- Load and validate the relevant configuration without modifying `.env`.
- Add the necessary client dependencies and update the lockfile through the project package manager.
- Configure institutional inference through the OpenAI Agents SDK.
- Start the configured MCP subprocess with `CST_CONNECT_MODE=disabled`, initialize MCP, and discover its tools, following pagination.
- Expose only `cst_connection_status` to the model, regardless of other tools in the discovered catalog.
- Ask the model to obtain and summarize the disconnected status using that tool.
- Produce a concise diagnostic outcome and document configuration, the explicit command, prerequisites, and verification in [README.md](../../README.md).
- Introduce focused offline tests for the connectivity behavior.

Excluded:

- Interactive chatbot, antenna prompt, geometry construction, and simulations.
- Reporting agent, persistent session memory, and general execution-history infrastructure.
- Explicit reasoning or thinking controls and validation of internal reasoning behavior.
- Changes to the MCP repository, credentials, or unrelated configuration.

## Constraints

- Use Python >=3.12 and run Python commands through `uv run`.
- Use the configured institutional endpoint and `SKYNET_API_KEY` explicitly. An unrelated `OPENAI_API_KEY` must not silently select OpenAI inference.
- Do not add explicit reasoning or thinking request parameters for this task. Document use of provider defaults without claiming an enabled or disabled reasoning mode.
- Disable OpenAI trace export for this check.
- Keep credentials out of output, stored evidence, and MCP child configuration.
- Enforce the tool allowlist in application code; prompt instructions alone are insufficient.
- Force disabled connection mode in the MCP child even if the parent environment specifies another mode. Never call connection, mutation, or simulation tools.
- Use bounded model turns and finite request, startup, and shutdown timeouts, with their behavior documented.
- Keep server-generated files within a client-owned work directory. Treat `C:\dev\cst-studio-mcp` as read-only reference material.
- Preserve existing interfaces unless a change is explicitly necessary for the documented connectivity command. Keep the implementation proportional to this check.

## Acceptance criteria

1. An explicit connectivity command is documented and runnable. Starting the check is intentional rather than an import-time side effect.
2. Missing or empty required configuration and invalid executable or working-directory paths produce actionable failures without exposing credentials.
3. MCP initialization and complete tool discovery succeed; evidence identifies the server version and discovered tool names.
4. The model actually requests `cst_connection_status` with an empty argument object. The SDK executes the request through MCP and returns the response to the model; a fabricated response or a direct application-only status call does not satisfy this criterion.
5. The response has no MCP error and establishes `mode=offline` and `project_open=false`. A tool payload error must not be counted as success.
6. The final model answer accurately summarizes the observed disconnected status.
7. No other MCP tool executes, and CST is never started. Tool calls outside the allowlist are rejected before dispatch.
8. Authentication errors, endpoint or MCP unavailability, malformed responses, timeouts, missing expected tool calls, and model-turn exhaustion produce an unsuccessful command outcome with useful diagnostics. Partial success is not reported as complete verification.
9. The check releases its model client and MCP subprocess resources on completion or failure. Offline status is not presented as evidence of CST library compatibility, native modeling, or solver correctness.

## Verification

All checks below are planned; none were executed while writing this task.

Introduce focused offline tests for configuration loading and precedence, provider request construction, MCP child settings, paginated discovery, tool restriction, response handling, and resource cleanup. Include representative failures and verify that diagnostics do not expose test credentials. Do not require tests of provider-specific reasoning controls or internal reasoning behavior.

Use mocks or local substitutes for offline tests. They must not require credentials, access the institutional endpoint, or launch CST. Ensure tests exercise the model tool-call/response cycle rather than only a direct MCP call.

Planned commands, run from the repository root:

```powershell
uv run ruff format --check .
uv run ruff check .
uv run pytest
```

Ruff is already declared. The test runner and application tests must be introduced as part of implementation. Apply any necessary formatting during implementation, keep changes within the task's scope, and inspect the resulting diff before running the non-mutating checks above.

Also perform an explicitly invoked integration check using the institutional endpoint, configured model, and real MCP server with CST disabled. Define and document its exact command during implementation. Record actual tool calls, the returned status, final response, and command outcome without credentials. Keep integration evidence separate from mocked test results.

If external prerequisites prevent integration verification, record the cause and next action. Passing offline tests alone does not complete the connectivity acceptance criteria.

## Implementation evidence

<!-- Implementer: record changes, commands actually executed, outcomes, and evidence references. -->

Implemented on branch `feat/model-mcp-connectivity` (2026-10-15).

### Changes

- New package `src/cst_agentic/` (moved from root `cst_agentic/` during layout cleanup):
  - `config.py` — `.env`-based configuration (precedence: explicit override > `.env` file >
    process environment), validation (including `mcp_request_timeout_s`, default 30 s), and
    the MCP child environment (credential-bearing variables removed;
    `CST_CONNECT_MODE=disabled` forced; `CST_WORK_DIR` pinned to a client-owned temp dir;
    `CST_TOOLSETS=core`).
  - `mcp_client.py` — stdio MCP client: startup with bounded timeout, initialization,
    paginated `tools/list` discovery (with a safety bound), and recording of every
    `tools/call` (name, arguments, `is_error`, JSON payload). Every `tools/list` page and
    every `tools/call` is bounded by the per-request timeout; a timeout raises
    `McpError`/`McpCallError` with a diagnostic instead of hanging.
  - `tool_gateway.py` — allowlist (`cst_connection_status` only) and the function tool the
    model can invoke; dispatch goes through the MCP client. The tool is registered with
    `failure_error_function=None` so a tool failure (for example an MCP timeout) propagates
    out of the run and fails the check, instead of being returned to the model as a
    generic error message.
  - `connectivity.py` — `run_connectivity_check` orchestration and the structured
    `ConnectivityReport` (12 verification checks; always releases the model client and MCP
    subprocess).
- `main.py` — rewritten to provide the `verify-connectivity` subcommand (no import-time
  side effects); exit code 0 on pass, 1 on failure or configuration error.
- `pyproject.toml` — added dependencies (`mcp`, `openai-agents`, `python-dotenv`, `ruff`;
  dev group `pytest`, `pytest-asyncio`), a `hatchling` build system so `uv sync` installs
  the package, and pytest/ruff configuration. Lockfile updated via `uv`.
- `tests/` — offline tests: `fakes.py` (scripted model + fake MCP client that subclasses
  the real client so the same bounded request paths run against a fake session, including
  hang injection), `test_config.py`, `test_mcp_client.py`, `test_tool_gateway.py`,
  `test_connectivity.py`. The orchestration tests drive the real `run_connectivity_check`
  with a scripted model so the model tool-call/response cycle is exercised, not just a
  direct MCP call.
- Review fix (blocking finding: unbounded `tools/list` and `tools/call`): per-request
  timeout added to `CstMcpClient` and `ConnectivityConfig`; new offline tests
  `test_discovery_page_timeout_is_bounded_error`, `test_call_tool_timeout_is_bounded_error`
  (unit) and `test_hung_discovery_times_out_and_cleans`,
  `test_hung_tool_call_times_out_and_cleans` (orchestration: unsuccessful report, timeout
  diagnostic, cleanup).
- `README.md` — documents configuration, the explicit command, prerequisites, behaviour,
  and verification.

### Commands executed (from the repository root)

| Command | Outcome |
| --- | --- |
| `uv sync` | Resolved and installed dependencies plus the project package. |
| `uv run pytest` | 30 passed (initial); 34 passed after the timeout fix. |
| `uv run ruff format cst_agentic main.py tests` | Formatting applied. |
| `uv run ruff check cst_agentic main.py tests` | All checks passed. |
| `uv run ruff format --check .` / `uv run ruff check .` | Clean (re-run after the timeout fix). |
| `uv run python main.py verify-connectivity` | PASSED (live integration run, evidence below; re-run after the timeout fix). |

### Integration evidence (institutional endpoint, real MCP server, CST disabled)

Live run of `uv run python main.py verify-connectivity` (2026-10-15, exit code 0;
first run 6.50 s, re-run 5.88 s after the per-request timeout fix; credentials redacted
by design and not reproduced here):

- Server: `cst-studio-mcp` version `1.1.0`, started in disabled mode
  (`cst-studio-mcp 1.1.0 start: disabled mode`); 69 of 192 tools discovered
  (`CST_TOOLSETS=core`).
- Exposed to model: `cst_connection_status` only.
- Model tool call: `cst_connection_status` with `args={}` (1 call; no other tools called).
- MCP tool call: `cst_connection_status` with `args={}`, `is_error=False`.
- Status payload: `mode='offline'`, `project_open=False`, `cst_version='2026'`.
- Final answer: summarizes the offline/disconnected status (mode offline, no project open,
  version 2026, install path and work directory as reported by the tool).
- All 12 checks passed: `mcp_initialized`, `tools_discovered`, `status_tool_discovered`,
  `status_tool_exposed`, `model_requested_status_tool`, `no_other_model_tool_calls`,
  `mcp_executed_status_call`, `mcp_no_error`, `payload_offline`,
  `payload_project_closed`, `payload_no_error_status`, `final_answer_summarizes`.

### Src layout cleanup (2026-10-15; pending review)

- Moved the existing application package to `src/cst_agentic/` without changing its
  contents (SHA-256 hashes matched for all 10 moved files, including cached bytecode).
  Package imports remain `cst_agentic` and the distribution remains `cst-agentic`.
- Kept `tests/` and the existing thin root `main.py` unchanged. Configured Hatchling's
  wheel target with `packages = ["src/cst_agentic"]`; no path workarounds were added.
- Confirmed `src/cst-agentic/` contained no entries, including hidden entries, before
  removing that empty directory.
- Updated `AGENTS.md` with the layout convention and `README.md` with installation and
  directory guidance. Preserved existing uncommitted work; `.env` and the MCP repository
  were not modified. Changes remain uncommitted and pending review.

Verification category: offline checks only, without inference, a real MCP subprocess,
or CST. All commands below ran from `C:\dev\cst-agentic`:

| Command | Outcome |
| --- | --- |
| `uv sync` | Initial sandbox attempt could not access uv's cache; approved retry rebuilt and installed `cst-agentic==0.1.0` successfully. |
| `uv run pytest` | 34 passed in 2.81 s; existing configuration, model/MCP fake-cycle, timeout, allowlist, and cleanup coverage passed after the move. |
| `uv run ruff check .` | All checks passed. |
| `uv run ruff format --check .` | 25 files already formatted. |
| `uv lock --check` | Passed; resolved 50 packages. |
| `uv run python main.py --help` | Exit 0; existing `verify-connectivity` subcommand listed without running it. |
| `git diff --check` | Reported pre-existing trailing whitespace in `.agents/skills/plan-keeper/SKILL.md:58`; unrelated user work left unchanged. |

Installed-package smoke check (exit 0):

```powershell
uv run python -I -c "from pathlib import Path; from importlib.metadata import version; import cst_agentic; expected = Path('src/cst_agentic/__init__.py').resolve(); actual = Path(cst_agentic.__file__).resolve(); assert actual == expected, actual; assert version('cst-agentic') == cst_agentic.__version__; print(actual); print('Installed distribution version:', version('cst-agentic'))"
```

This resolved `cst_agentic` to `C:\dev\cst-agentic\src\cst_agentic\__init__.py`
and confirmed installed version `0.1.0`. Isolated Python mode excludes the working
directory and ambient Python path settings, verifying the installed package works
without path overrides. The documented CLI help and installation were exercised;
the live connectivity example was intentionally not rerun.

## Remaining limitations

<!-- Implementer: record limitations confirmed during implementation. -->

- The src layout cleanup was verified offline only. Live inference, real MCP
  integration, and CST operations were not rerun, as requested; the integration
  evidence above predates this move. Independent review remains pending.
- Repository-wide diff whitespace checking still reports an unrelated existing issue
  in `.agents/skills/plan-keeper/SKILL.md:58`; it does not block layout verification.
- Explicit reasoning configuration is deferred per the task: the model runs with provider
  defaults and no claim is made about internal reasoning mode.
- Integration verification was performed on the author's Windows machine with the
  configured endpoint and model (`qwen3.8-27b`), including a re-run after the per-request
  timeout fix; it is not a repeatable CI check, and behaviour on other endpoints or models
  is unverified.
- Hung/stalled MCP server behaviour was verified offline via an injected blocking fake
  session; it has not been exercised against a real stalled server process.
- The MCP server still exposes the always-enabled session tools and the `core` toolset on
  the wire; the restriction to `cst_connection_status` is enforced client-side by
  registering only that tool with the agent, so no other tool can be dispatched.
- The check verifies model/MCP connectivity only. Disabled-mode offline status is not
  evidence of CST library compatibility, native modeling, or solver correctness.
