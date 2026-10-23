# cst-agentic

> Agentic System responsible for CST control and result analysis

`cst-agentic` is a Python-based agentic workflow designed to bridge Large Language Models with CST Studio Suite. It enables autonomous agents to interact with electromagnetic simulations by separating the physical execution from data analysis.

## Architecture

The planned architecture will contain:
1. **The CST Controller:** Handles the mechanical interaction with a MCP-server. It updates parameters, rebuilds meshes, and triggers the solver.
2. **The Result Analyst:** Extracts simulation results (e.g., S-parameters, radiation patterns, mismatch efficiency), compiles the simulation results and generates a report.

## Prerequisites
- Python 3.12+
- `uv` (Package manager)
- CST Studio Suite 2025 (Windows environment for COM object interaction)

## Project layout and installation

Application code lives in `src/cst_agentic/`, offline tests and helpers in `tests/`, and the thin CLI entry point in root `src/cst_agentic/cli.py`. The distribution is named `cst-agentic`; Python imports use `cst_agentic`.

Run `uv sync` from the repository root to install dependencies and the application package. Hatchling explicitly packages `src/cst_agentic`; imports use the installed package without path overrides.

## Connectivity check (milestone 1)

The separate [Controller recovery safety slice](docs/controller-recovery.md)
provides central incident storage, a per-user session lease and guarded dispatch
for future Controller integration. It does not enable a conversational/live CST
command or change this connectivity check.

An explicit command verifies that the OpenAI Agents SDK can use the institutional Qwen
endpoint to call `cst_connection_status` through the `cst-studio-mcp` MCP server, with the
CST connection forced to disabled (offline) mode. A disconnected status is the *expected*
result of this check. The check verifies connectivity only; it is not evidence of CST
library compatibility, native modeling, or solver correctness.

### Configuration

Settings are read from a `.env` file in the repository root (the file is never modified),
falling back to process environment variables. The `.env` file wins over the process
environment so that unrelated ambient variables (for example a generic `AGENT`) cannot
select a different model or endpoint.

| Variable | Meaning |
| --- | --- |
| `SKYNET_BASE_URL` | Base URL of the institutional OpenAI-compatible endpoint |
| `SKYNET_API_KEY` | API key for the institutional endpoint |
| `AGENT` | Model ID (initially `qwen3.8-27b`) |
| `CST_MCP_SERVER_EXECUTABLE` | Path to the runnable `cst-studio-mcp` executable |
| `CST_MCP_SERVER_CWD` | Working directory for the MCP server process |

An unrelated `OPENAI_API_KEY` is never used for this check; the institutional
endpoint and `SKYNET_API_KEY` are always used explicitly.

### Command

Run from the repository root (after `uv sync`):

```powershell
uv run cst-agentic verify-connectivity
```

The check starts only when the subcommand is invoked; importing the project has no side effects. It:

1. Starts the configured MCP subprocess with `CST_CONNECT_MODE=disabled` forced,
   `CST_WORK_DIR` pinned to a client-owned work directory
   (`%TEMP%\opencode\cst-agentic\work`), and `CST_TOOLSETS=core`. Credential-bearing
   variables are removed from the child environment, and the CST application itself is
   never started.
2. Initializes MCP and discovers the tool catalog, following pagination.
3. Exposes only `cst_connection_status` to the model. The allowlist is enforced in code
   (only that tool is registered with the agent), so no other tool can be dispatched.
4. Runs a bounded agent loop and asks the model to obtain and summarize the connection
   status using the tool.
5. Verifies that the model actually called the tool through MCP with an empty argument
   object, that the MCP call had no error, that the payload reports `mode=offline` and
   `project_open=false`, and that the final answer summarizes the disconnected status.
   A partial success is reported as a failure.

The model is configured with provider defaults; no explicit reasoning or thinking
parameters are sent, so no claim is made about internal reasoning mode. OpenAI trace
export is disabled for the check. Bounds: 6 agent turns, 120 s model request timeout,
60 s MCP startup timeout, 30 s per MCP request (each `tools/list` page, and each
`tools/call` including its time queued behind a concurrent call), and 15 s MCP shutdown
timeout. A timed-out MCP request fails the check with a diagnostic rather than hanging.

On success the command prints a diagnostic summary (server identity, discovered tools,
recorded model and MCP tool calls, status payload, final answer, per-check results) and
exits 0. On failure it prints the same summary with the failing checks and error and
exits 1. Credentials never appear in the output.

### Call serialization and attempt records

The MCP client serializes `tools/call` dispatch per client instance: at most one call
is active at a time, and concurrent callers queue until the configured per-request
budget expires. The budget starts at each call's entry and covers queueing plus SDK
execution, so a queued caller cannot wait indefinitely. Every admitted call produces an
attempt record in `CstMcpClient.attempts`: the tool name, a frozen copy of the
arguments taken before the first await (the top-level mapping and every nested mapping
or sequence are detached, so later caller mutation at any depth cannot alter the
admitted values or the values actually sent), monotonic start and end times, whether
dispatch started, a terminal outcome, and the returned call record when one exists.
Only returned responses are appended to `CstMcpClient.calls`, so its response-only
meaning is unchanged.

Terminal outcomes are `received` (a response was returned; this is not proof that CST
executed the operation successfully or that partial effects are absent), `not_dispatched`
(the request never reached the SDK: the caller queued past its budget or was cancelled
in the queue, the client was already blocked, or no active MCP session existed; the
session case is not uncertainty and does not block the client), and `uncertain` (a
timeout, transport or SDK-validation failure, or caller cancellation after dispatch; the
request may already have reached the server). Any uncertain attempt permanently blocks
further tool
dispatches on that client, including callers already queued, and no replay occurs.
Closing or replacing the client does not prove an uncertain operation stopped, and
constructing a new client is not reconciliation. Attempt diagnostics are bounded
categories only: never raw exception messages, configuration values, or secrets. The
`McpCallError` for a transport or SDK-validation failure carries only that bounded
category, never the text of the original SDK exception. The timeout error identifies
the timeout without echoing the configured bound, and the not-dispatched errors
(queued past the budget, cancelled in the queue, already blocked, or no active
session) carry equally bounded messages.

### Verification

Offline tests (no network, no real MCP subprocess, no CST) cover configuration loading
and precedence, provider request construction, MCP child environment settings, paginated
discovery, tool restriction, call serialization and attempt records, response handling,
resource cleanup, and representative failures:

```powershell
uv run pytest
```

Static checks:

```powershell
uv run ruff format --check .
uv run ruff check .
```

The `verify-connectivity` command above is the explicitly invoked integration check
against the institutional endpoint, the configured model, and the real MCP server; its
evidence is recorded in the task file and kept separate from the mocked test results.

