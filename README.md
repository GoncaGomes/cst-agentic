# cst-agentic

A focused model/MCP connectivity check. The only application command is
`uv run cst-agentic verify-connectivity`.

The command contacts the configured model through the institutional Skynet
OpenAI-compatible endpoint and asks it to call `cst_connection_status` through
the configured `cst-studio-mcp` server. The MCP subprocess runs with
`CST_CONNECT_MODE=disabled`: **`mode=offline` and `project_open=false` are the
expected successful results**, not failures. Keep CST closed for this check.
It does not verify native modeling, simulation or solver correctness.

## Setup

Requirements:

- Python 3.12+ and [uv](https://docs.astral.sh/uv/).
- Access to the Skynet endpoint and the desired model (for example Qwen).
- A runnable `cst-studio-mcp` executable and its working directory. Configure
  the existing server installation; this repository does not install it or
  require launching CST.

From the repository root:

```powershell
uv sync --locked
```

Create a local `.env` file with these settings, replacing the placeholders:

```dotenv
SKYNET_BASE_URL=https://your-skynet-endpoint.example/v1
SKYNET_API_KEY=replace-with-your-key
AGENT=your-qwen-model-id
CST_MCP_SERVER_EXECUTABLE=C:/path/to/cst-studio-mcp.exe
CST_MCP_SERVER_CWD=C:/path/to/server-directory
```

| Variable | Meaning |
| --- | --- |
| `SKYNET_BASE_URL` | Base URL of the OpenAI-compatible Skynet endpoint |
| `SKYNET_API_KEY` | API key for that endpoint |
| `AGENT` | Model ID available at that endpoint |
| `CST_MCP_SERVER_EXECUTABLE` | Existing runnable MCP server executable |
| `CST_MCP_SERVER_CWD` | Existing working directory for the MCP subprocess |
| `CST_MCP_WORK_DIR` | Optional client-owned work directory; defaults to `cst-agentic/work` under Python's temporary directory |

The `.env` file takes precedence over process environment variables and is
never modified by the command. Missing values fall back to the process
environment. `.env` is ignored by Git; keep credentials out of commits and
shared diagnostics. An unrelated `OPENAI_API_KEY` is not used.

## Run

```powershell
uv run cst-agentic verify-connectivity
```

To use a configuration file elsewhere:

```powershell
uv run cst-agentic verify-connectivity --env C:/path/to/.env
```

The check runs only when explicitly invoked; importing the package does not
start a model request or MCP subprocess. It:

1. Starts the configured MCP subprocess with `CST_CONNECT_MODE=disabled`,
   `CST_TOOLSETS=core` and `CST_WORK_DIR` pinned to the client-owned directory.
   Credential-bearing variables are removed from the child environment. It
   does not launch or attach to CST.
2. Initializes MCP and discovers the tool catalogue, following pagination.
3. Exposes and allows only `cst_connection_status`, regardless of other tools
   advertised by the server.
4. Contacts the configured model and runs a bounded tool-call loop.
5. Checks that the model actually called the tool through MCP with `{}`, the
   MCP response has no tool error, the payload reports `mode=offline` and
   `project_open=false`, and the final answer summarizes the disconnected
   status. Partial success fails the check.

Success prints a diagnostic summary and exits 0; failure prints diagnostics
and exits 1. The summary includes server identity, discovered/exposed tools,
recorded calls, status, final answer and individual checks. Review diagnostics
before sharing them.

Bounds are 6 agent turns, 120 seconds per model request, 60 seconds for MCP
initialization, 30 seconds per MCP request (including queueing), and 15 seconds
for MCP shutdown. Model provider defaults are used without explicit reasoning
parameters; OpenAI trace export is disabled. See the
[base MCP client](docs/protected-mcp-client.md) for serialization and uncertainty
semantics.

## Development and verification

Application code is in `src/cst_agentic/`; tests and controlled peers are in
`tests/`. First-party source and documentation use
[English](docs/project-language.md).

```powershell
uv run cst-agentic --help
uv run --locked pytest
uv run --locked ruff format --check .
uv run --locked ruff check .
uv run --locked pyright
```

Tests are offline: scripted model replies, fake MCP sessions and a disposable
local MCP peer do not contact Skynet or launch CST. Windows CI runs these
checks with locked dependencies.

**Pending manual validation:** run `verify-connectivity` against real Skynet
and the configured MCP installation on the maintainer's PC, keeping CST
closed. Offline tests are not evidence of that integration passing.
