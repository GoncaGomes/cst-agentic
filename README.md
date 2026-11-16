# cst-agentic

`cst-agentic` is a Python CLI for testing how a language model interacts with
`cst-studio-mcp` through the Model Context Protocol (MCP). It provides
connectivity and tool discovery checks with `CST_CONNECT_MODE=disabled`.

## Requirements

- Python 3.12 or later and [uv](https://docs.astral.sh/uv/).
- Access to the OpenAI-compatible Skynet endpoint and a model that supports tool calling.
- An existing `cst-studio-mcp` installation with an executable and a working directory.

## Quick start

Install the locked dependencies from the repository root.

```powershell
uv sync --locked
```

Create a `.env` file in the repository root and replace the placeholders with
your Skynet and MCP server settings.

```dotenv
SKYNET_BASE_URL=https://your-skynet-endpoint.example/v1
SKYNET_API_KEY=replace-with-your-key
AGENT=your-model-id
CST_MCP_SERVER_EXECUTABLE=C:/path/to/cst-studio-mcp.exe
CST_MCP_SERVER_CWD=C:/path/to/server-directory
```

`AGENT` is the model ID available on your Skynet endpoint. Values in `.env`
take precedence over environment variables. Keep `.env` out of version control.

Run either check.

```powershell
uv run cst-agentic verify-connectivity
uv run cst-agentic discover-tools
```

Both commands accept `--env` to specify a different configuration file.

```powershell
uv run cst-agentic discover-tools --env C:/path/to/.env
```

## Checks

### Connectivity

`verify-connectivity` starts the MCP server with `CST_TOOLSETS=core` and
exposes only `cst_connection_status` to the model. The check verifies that the
model calls it through MCP and correctly reports an offline connection with no
open project (`mode: offline`, `project_open: false`).

### Tool discovery

`discover-tools` starts the MCP server with `CST_TOOLSETS=all` and loads its
tool catalog. The model receives one callable function,
`discover_tools(groups)`, which looks up definitions in the 18 configured
[tool groups](src/cst_agentic/tool_groups.py).

In a single agent run, the model must look up each group once and name all the
tools it finds. The check requires every group to return its full set of MCP
definitions. The run allows up to 24 agent turns and makes zero MCP tool
execution requests. The report lists each tool found once.

### Reports

Both checks print a summary and exit with status `0` on success or `1` on
failure. The JSON reports contain the recorded calls, validation checks, and
the model's final response.

| Command | JSON report |
| --- | --- |
| `verify-connectivity` | `tests/reports/connectivity.json` |
| `discover-tools` | `tests/reports/one_call_tool_discovery.json` |

## Development

Run the formatter check, linter, type checker, and test suite with the same
locked dependencies as Windows CI.

```powershell
uv sync --locked --dev
uv run --no-sync ruff format --check .
uv run --no-sync ruff check .
uv run --no-sync pyright
uv run --no-sync pytest -q
```

The offline tests use scripted model replies, fake MCP sessions, and a local
MCP test server.

- [MCP client behavior](docs/protected-mcp-client.md)
- [Project language conventions](docs/project-language.md)
