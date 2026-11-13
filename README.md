# cst-agentic

Python tooling for exploring the integration of language models such as Qwen
with CST Studio Suite through the Model Context Protocol (MCP).

The project currently provides a single connectivity check:
`uv run cst-agentic verify-connectivity`. It contacts the configured model
through the institutional Skynet OpenAI-compatible endpoint and verifies that
the model can call `cst_connection_status` through `cst-studio-mcp`.

The check runs with CST connectivity disabled. It does not launch CST, edit
projects or run simulations.

## Requirements

- Python 3.12+ and [uv](https://docs.astral.sh/uv/).
- Access to Skynet and a model that supports tool calling.
- An existing `cst-studio-mcp` installation with a runnable executable and
  working directory. This repository does not install the MCP server.

## Quick start

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

`AGENT` is the model ID available at your endpoint. The `.env` file takes
precedence over process environment variables; missing values fall back to
the environment. The command does not modify the file or use an unrelated
`OPENAI_API_KEY`. Keep credentials out of commits and shared diagnostics.

Keep CST closed, then run:

```powershell
uv run cst-agentic verify-connectivity
```

To use a configuration file elsewhere:

```powershell
uv run cst-agentic verify-connectivity --env C:/path/to/.env
```

### Expected result

The MCP server is started with `CST_CONNECT_MODE=disabled`, and only
`cst_connection_status` is exposed to the model. A successful response reports:

```text
mode=offline
project_open=false
```

**Disconnected is the expected result**, not a failure. The check verifies
that the model actually called the tool through MCP and summarized its
response. It prints diagnostics and exits 0 on success or 1 on failure.

This verifies model/MCP connectivity only, not native CST compatibility,
modeling or solver correctness. Offline tests do not establish that a real
Skynet/MCP integration works; validate that separately with the command above.

## Development

Application code lives in `src/cst_agentic/`, with offline tests in `tests/`.

```powershell
uv run cst-agentic --help
uv run --locked pytest
uv run --locked ruff format --check .
uv run --locked ruff check .
uv run --locked pyright
```

Tests use scripted model replies, fake MCP sessions and a disposable local
MCP peer. They do not contact Skynet or launch CST. Windows CI runs the same
checks with locked dependencies.

Further details:

- [MCP client behavior and safety guarantees](docs/protected-mcp-client.md)
- [Source-language convention](docs/project-language.md)
