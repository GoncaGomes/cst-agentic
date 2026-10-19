# Institutional endpoint tool-calling contract

Research date: 2026-10-19. Decision ticket: [#6][ticket]. Planning map: [#4][map].

## Finding

**Keep the OpenAI Agents SDK as the intended integration.** Eight bounded requests to
the existing configured institutional endpoint succeeded through the application's
Chat Completions SDK path. Native function calls, mock-result round trips, preserved
call identifiers, replacement of the current function list with an old function absent,
and a two-call response all worked in this small synthetic trial. This is compatibility
evidence, not an accepted discovery architecture or a CST competence evaluation.

No provider or model was substituted. The probe resolved `SKYNET_BASE_URL`,
`SKYNET_API_KEY`, and `AGENT` using the application's file-first, environment-second
precedence. Only presence booleans were emitted. Endpoint addresses, credential values,
configuration contents, response headers, call identifiers, and free-form model text
are deliberately absent from this artifact. [A2, P1]

## Provenance and evidence classes

- Application baseline: **`2f5d809e3ca82b726fac407cc89ba6ab58de786d`**, main when
  assigned. The original checkout's user changes were not copied, edited, staged, or
  reverted. Research was isolated on `research/controller-endpoint-contract`.
- **Endpoint verified:** observations from the single eight-request live execution below.
- **Installed source:** direct inspection of the installed packages, with byte-for-byte
  comparison against pinned upstream source. These establish SDK behavior, not provider
  conformance for arbitrary requests.
- **OpenAI documentation:** OpenAI platform contracts and SDK guidance. Platform
  guarantees do not automatically extend to this institutional service.
- **Unverified:** explicitly listed gaps. Success with these inputs does not establish
  a tool-count ceiling, broad JSON Schema support, or engineering-task competence.

### Versions and matching sources

The original project's `uv.lock` and installed distribution metadata agree on
`openai-agents==0.24.0` and `openai==3.31.0`. The installed HTTP implementation is
`httpx2==2.13.1`, not the older `httpx` package. OpenAI 3.31.0 imports `httpx2` and
accepts an async HTTP client. [A3, S10, S13, P1]

- Agents SDK tag `v0.24.0` resolves to
  **`17d994bd3045dae71acda676a4ef4762ed8ecd94`**. [S0]
- OpenAI Python tag `v3.31.0` resolves to
  **`86cae50785fb7b7bf2a5d2383370b214b304acd2`**. [S9]
- All 15 installed files used for the source review matched the corresponding pinned
  upstream bytes: Agents `agent.py`, `result.py`, `model_settings.py`, `run_config.py`,
  `strict_schema.py`, `tool.py`, `models/openai_chatcompletions.py`,
  `models/chatcmpl_converter.py`, `run_internal/agent_tool_configuration.py`,
  `run_internal/run_loop.py`, and OpenAI `_client.py`, `_base_client.py`,
  `_constants.py`, `_httpx2.py`, `resources/chat/completions/completions.py`.

Core installed-source SHA-256 fingerprints:

| File | SHA-256 |
| --- | --- |
| Agents `models/openai_chatcompletions.py` | `6b835d1e8fad555145ca29b4b3d7d6fe3eb8f2a5e438768601bab6a00193ac65` |
| Agents `models/chatcmpl_converter.py` | `7dd78990e37748a3ec088a3c6831f9a70d25d00a0bf91d4e8c54644edf293309` |
| Agents `agent.py` | `16dddcf79534fc4d107b6d2a50f10dbefe64743c99b0c537fba407c109c77fe2` |
| Agents `result.py` | `5753f8e3ec90186ebf322416f9a536c873afddbe72de5520c6f1d9c369268d07` |
| OpenAI `_client.py` | `824884031bb2982ed9a9d42ad3ea3d37e9c24d1593f295d2a9512c151d6b9931` |

## Application and installed SDK contract

### Existing application path

`connectivity.py` creates `AsyncOpenAI(base_url=config.base_url,
api_key=config.api_key, timeout=config.request_timeout_s)`, wraps it in
`OpenAIChatCompletionsModel`, and passes a one-tool `Agent` to `Runner.run`.
Its run config sets `tracing_disabled=True` and
`tool_not_found_behavior="return_error_to_model"`. It is a connectivity check,
not an implemented conversational controller. **Do not execute that CLI as an
endpoint-only probe**, because it starts an MCP subprocess. [A1]

The application config defaults the model request timeout to 120 seconds. The client
does not override OpenAI's default two retries. Thus `max_turns` alone is not an actual
HTTP-request budget. The disposable probe explicitly overrides retries to zero and
enforces its own budget at the transport boundary. [A1, A2, S10, S11, S12, P1]

### Function definitions and changing exposure

- The adapter serializes the `tools` argument afresh for each request into Chat
  Completions' nested `{"type":"function","function":{...}}` shape, including
  `parameters` and `strict`. An empty converted list omits `tools`. It sends
  `parallel_tool_calls` only when converted tools are present. [S1, S2]
- `Agent.get_all_tools` evaluates `FunctionTool.is_enabled`, including context-based
  async predicates. The run loop resolves tools for a model turn. The installed SDK
  also detects conflicting `Agent.tools` changes across concurrent runs and recommends
  separate agents or context-based enablement. [S3, S7, S8]
- **Live evidence here used separate sequential `Runner.run` calls with separately
  constructed Agents**, plus `first_result.to_input_list()` for continuation. It did
  not modify `Agent.tools` inside a running discovery handler. Per-turn in-run
  enablement/replacement is source-supported, but that specific lifecycle was not
  live-tested. [S3, S4, S7, S8, P1]
- Tool-result text listing a tool name is not what registers a function. Current
  native definitions come from the request's `tools` list. Execution permission and
  validation still belong in application code. [S1, S2, D1]

### History, identifiers, parsing, and missing tools

- `RunResult.to_input_list()` returns original inputs plus replayable new items.
  Chat response tool-call IDs become SDK function `call_id` values, then serialize
  back as assistant `tool_calls[].id`. Results serialize as `role="tool"` messages
  with the same `tool_call_id`. Unpaired outputs without a call ID cannot be
  converted to this Chat Completions path. [S2, S4]
- The adapter converts the first completion choice into SDK output items. Missing
  choices cause `ModelBehaviorError`. An empty completion terminated with `length`
  also causes a model-behavior error. A successful HTTP status alone therefore does
  not establish a usable SDK response. [S1]
- `tool_not_found_behavior="return_error_to_model"` permits an unresolved function
  call to produce an error result and continue the run. It does not grant permission
  to execute a hidden tool or bound the number of recovery turns. This recovery path
  was configured but not triggered in the live trial. [S5, P1]
- The adapter requires client-carried conversation history. `previous_response_id`,
  `conversation_id`, and reusable Responses prompts are unsupported on this path.
  They are ignored with warnings by default or rejected when strict feature
  validation is enabled. No Responses API migration is required by the verified
  function-list replacement contract. [S1]

### Schemas, choice, and multiple calls

- OpenAI documents strict function schemas as closed objects with all properties
  required, using nullable types for optional values. The SDK has its own strict
  schema normalization and rejection rules. These rules are not proof of this
  endpoint's server-side schema enforcement. [D1, S6]
- The probe used `strict=True` and only a simple object with one required integer
  `value` and `additionalProperties=False`. All returned argument JSON matched the
  exact expected object and was checked locally before mock execution. This verifies
  acceptance and valid generated arguments for that shape, **not** rejection of
  invalid schemas, completeness of strict enforcement, or arbitrary MCP schemas. [P1]
- `ModelSettings.tool_choice` supports `auto`, `required`, `none`, or an ordinary
  function-name string. The converter turns a name into Chat Completions' nested
  named-function selector. `MCPToolChoice` is rejected on this adapter. [S2]
- `Agent.reset_tool_choice=True` defaults to resetting the choice after a tool call.
  The live second requests of the round trips omitted `tool_choice`. They did not
  explicitly send `auto`, though request 7 did. [S3, P1]
- Provider `parallel_tool_calls` and local execution concurrency are separate.
  `ToolExecutionConfig.max_function_tool_concurrency` controls SDK-side concurrency.
  The default starts all function calls emitted in a turn. A model-side false flag
  is not an execution lock or authorization mechanism. [S5, D1]
- Hosted OpenAI tool-search tools and Responses-only tool features must not be
  assumed available here. This adapter's native tool serialization supports
  `FunctionTool` and rejects unsupported tool types/features. The live probe used
  only ordinary functions. [S2, D2]
- No reasoning settings or provider-specific thinking switches were supplied.
  The adapter supports `reasoning.effort` mapping but not Responses-only reasoning
  `mode`/`context`. Neither the configured model name nor these tests establishes
  what reasoning mode the institutional service used. [S1, P1]

## Bounded live methodology

The eight-request budget was announced before probing. **Exactly eight institutional
HTTP requests were dispatched, all returned HTTP 200.** There were no retries,
redirects, errors, or additional institutional requests. Each offline verification run
exercised eight mock transport requests, not institutional requests. [P1]

Safety and bounds:

- Read configuration values in memory from the existing project. Did not copy config
  into the worktree, change environment credentials, or invoke the config loader's
  work-directory creation path.
- Reference scripts `probe_multimodal.py` and `probe_mcp_connection.py` in the
  user-provided sibling project were inspected structurally with AST parsing. Only
  import names, environment-variable names, call names, and keyword/key names were
  printed. Neither script was executed. Their behavior was not treated as evidence
  about this application or endpoint.
- Set `OPENAI_AGENTS_DISABLE_TRACING=1`, called `set_tracing_disabled(True)`, and
  used `RunConfig(tracing_disabled=True, ...)`. Suppressed logging globally before
  SDK imports and disabled model/tool-data logging. No trace export was requested.
- `AsyncOpenAI(max_retries=0, timeout=90.0)`, transport retries zero, redirects off.
  HTTP client constructed with a 15-second connect timeout and 90-second remaining
  phase timeouts. The explicit OpenAI per-request 90-second scalar is passed down
  to the HTTP client and is the operative phase-timeout configuration. Each SDK
  model attempt also had `ModelSettings(timeout=100.0)`. Each Runner invocation had
  an independent 190-second `asyncio.wait_for` bound and `max_turns=2`.
- Output was bounded with `max_tokens=1024`. No temperature, thinking switch,
  reasoning effort, or compatibility-tuning options were tried.
- Custom async transport enforces a hard eight-dispatch ceiling and the configured
  origin and Chat Completions route. It checks strict schema shape, exact synthetic
  argument values, matched historical IDs, and mock result contents in memory.
- Only `probe_alpha`, `probe_beta`, and `probe_gamma` functions were available.
  Their implementations returned constant JSON mock tokens. No CST launch, MCP
  operation, real project mutation, or application connectivity CLI execution occurred.
- Safe diagnostics contain only booleans, counts, status codes, synthetic tool names,
  fixed phase labels, and allowlisted finish reasons. Exception handling does not
  print exception messages, raw provider errors, request dumps, or response headers.
- The first incompatibility would stop the sequence. None occurred. **Do not rerun
  the live script under this already exhausted authorization.** A future run needs
  its own explicit budget.

### Observed request sequence

All listed argument checks passed. Native-call responses had `finish_reason=tool_calls`.
Text-only responses had `finish_reason=stop`. [P1]

| Request | Current visible functions | Choice | Parallel flag | Observed result |
| --- | --- | --- | --- | --- |
| 1 | alpha | `required` | false | One native alpha call with the requested integer argument. Mock handler ran. |
| 2 | alpha | omitted by SDK reset | false | One matched alpha call/result pair retained with the original call ID. Final response contained the mock token. |
| 3 | beta | `required` | false | **Alpha schema absent**, alpha call/result pair still in history with its ID. One native beta call. |
| 4 | beta | omitted by SDK reset | false | Alpha and beta call/result pairs retained with their IDs. Final response contained beta's mock token. |
| 5 | beta | `none` | false | No native call or mock handler invocation. Text response returned. |
| 6 | beta | named beta | false | One beta call. SDK `stop_on_first_tool` returned its mock output without a further model request. |
| 7 | beta, gamma | `auto` | true | Two native calls in **one** response, one per requested function. Both mock handlers ran. |
| 8 | beta, gamma | omitted by SDK reset | true | Both matching result messages were serialized. Text completion ended the run. |

The full function names have the `probe_` prefix. Requests 3 and 4 are positive
evidence that this endpoint **does not require an old function's definition to stay
in the current list for this matched historical call/result case**. Unmatched calls,
partial batches, changed schemas under the same name, long histories, and arbitrary
history pruning were not tested. [P1]

## Narrow implications and remaining decisions

1. There is no demonstrated transport obstacle to the proposed idea of changing
   native function exposure while preserving history through the existing SDK.
   Separate sequential SDK runs with `to_input_list()` are a verified continuation
   seam. Choose and acceptance-test the intended **in-run discovery lifecycle** before
   production implementation. Do not claim this trial validated an in-handler tool-list
   mutation. [S1-S4, S7-S8, P1]
2. Specify when a discovery update takes effect relative to a complete returned
   tool batch. Since multiple calls are demonstrably possible, specify deterministic
   handling of a discovery call mixed with other calls. Decide execution concurrency
   separately from the provider parallel-call flag. [S5, P1]
3. Specify the schema-validation/normalization policy for actual MCP schemas,
   including open dictionaries, optional values, unions, and references. Avoid silently
   narrowing accepted argument values to make a schema appear strict. This trial
   only exercised the simple closed-object case. [S6, D1, P1]
4. Preserve complete call/result pairing and call IDs when exposure changes. Enforce
   the current execution allowlist independently and bound unknown-tool recovery.
   Decide production timeout/retry policy explicitly rather than treating a model
   turn count as an HTTP budget. [S2, S4-S5, S10-S12, P1]

These are narrow inputs to later specification, not new accepted architecture.
The local `docs/CST_Controller_Tool_Discovery_Plan.md` dated 2026-10-16 was read at
its original path as an uncommitted candidate. Its groups, startup inventory, analyst
handoff, and function cap remain proposals. This research selects none of them.
It establishes **no tool-count capacity claim**. [map, ticket]

### Explicit gaps

- No endpoint option was observed failing. There is no evidence-based list of
  additional provider-specific unsupported fields from this successful trial.
- No invalid-schema/invalid-argument adversarial requests or broad JSON Schema sweep.
- No same-name schema replacement, explicit empty tool list, or in-run discovery test.
- No assertion that `parallel_tool_calls=False` is universally enforced. The tested
  requests with false produced one or zero calls, but they requested at most one.
- No streaming, reasoning-content replay, forced malformed output, refusal, truncation,
  timeout, rate-limit, network-failure, or unknown-tool recovery trial.
- No actual model token-capacity, long-history reliability, tool-count scaling,
  engineering-task competence, CST connectivity, or native CST operation validation.
- No provider/model substitution or Responses API availability test.

## Reproduction and checks

Disposable implementation: [probe_endpoint_contract.py][P1]. It defaults to a fully
offline mocked HTTP transport. Run it with the original project's installed environment,
not a newly resolved worktree environment. All Python commands used `uv run --no-sync`.
The live run was identical to the offline Runner path except for configuration and
HTTP transport. An offline-only ninth-dispatch rejection check was added afterward.

```powershell
uv run --no-sync '<research-worktree>\docs\research\probe_endpoint_contract.py'
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
```

The command's working directory must be the existing configured project. Live mode
requires explicit `--live --config-root '<original-project>'` and separate authorization.

Checks performed:

- Offline SDK + mocked HTTP exercise of the same eight-request sequence passed.
- Offline transport test blocked a ninth dispatch before reaching the underlying
  transport, retaining a count of eight.
- Single live SDK sequence passed all phase assertions using eight requests.
- Installed-source comparisons against the two exact upstream commits passed for all
  15 inspected package files.
- Ruff lint/format checks and `git diff --check` performed on the artifact change set.
- Credential-safety review checks only artifact files and compares configured sensitive
  values in memory without emitting them.

No production behavior was changed. Production connectivity and CST execution remain
outside this research's verification scope.

## Primary sources

Application sources:

- [A1: committed connectivity integration][A1], especially `_build_provider` and `Runner.run`.
- [A2: committed config parser][A2], especially `_resolve` and `load_connectivity_config`.
- [A3: committed lockfile][A3].

Pinned SDK sources, all matched to installed bytes:

- [S0: Agents SDK tag resolution][S0].
- [S1: Chat Completions adapter][S1], `get_response`, `_fetch_response`, unsupported-state handlers.
- [S2: Chat Completions converter][S2], `convert_tool_choice`, `message_to_output_items`,
  `items_to_messages`, `tool_to_openai`.
- [S3: Agent][S3], `get_all_tools`, `tool_use_behavior`, `reset_tool_choice`.
- [S4: RunResult][S4], `to_input_list`.
- [S5: RunConfig][S5], `ToolExecutionConfig`, `tool_not_found_behavior`.
- [S6: strict schema implementation][S6], `ensure_strict_json_schema`.
- [S7: tool configuration concurrency guards][S7].
- [S8: Runner turn implementation][S8].
- [S9: OpenAI Python tag resolution][S9].
- [S10: OpenAI async client][S10].
- [S11: OpenAI base client][S11], request timeouts and retry handling.
- [S12: OpenAI constants][S12], default two retries.
- [S13: HTTPX2 integration][S13].
- [S14: Chat Completions resource][S14].
- [S15: FunctionTool implementation][S15].

Official docs, consulted on the research date and not version-pinned API guarantees
for the institutional endpoint:

- [D1: OpenAI function-calling guide][D1], tool choices, parallel calls, strict schemas,
  and application-side call/result flow.
- [D2: OpenAI Agents SDK tools guide][D2], custom function tools and Responses-only hosted search.

[ticket]: https://github.com/GoncaGomes/cst-agentic/issues/6
[map]: https://github.com/GoncaGomes/cst-agentic/issues/4
[P1]: ./probe_endpoint_contract.py
[A1]: https://github.com/GoncaGomes/cst-agentic/blob/2f5d809e3ca82b726fac407cc89ba6ab58de786d/src/cst_agentic/connectivity.py
[A2]: https://github.com/GoncaGomes/cst-agentic/blob/2f5d809e3ca82b726fac407cc89ba6ab58de786d/src/cst_agentic/config.py
[A3]: https://github.com/GoncaGomes/cst-agentic/blob/2f5d809e3ca82b726fac407cc89ba6ab58de786d/uv.lock
[S0]: https://api.github.com/repos/openai/openai-agents-python/commits/v0.24.0
[S1]: https://github.com/openai/openai-agents-python/blob/17d994bd3045dae71acda676a4ef4762ed8ecd94/src/agents/models/openai_chatcompletions.py
[S2]: https://github.com/openai/openai-agents-python/blob/17d994bd3045dae71acda676a4ef4762ed8ecd94/src/agents/models/chatcmpl_converter.py
[S3]: https://github.com/openai/openai-agents-python/blob/17d994bd3045dae71acda676a4ef4762ed8ecd94/src/agents/agent.py
[S4]: https://github.com/openai/openai-agents-python/blob/17d994bd3045dae71acda676a4ef4762ed8ecd94/src/agents/result.py
[S5]: https://github.com/openai/openai-agents-python/blob/17d994bd3045dae71acda676a4ef4762ed8ecd94/src/agents/run_config.py
[S6]: https://github.com/openai/openai-agents-python/blob/17d994bd3045dae71acda676a4ef4762ed8ecd94/src/agents/strict_schema.py
[S7]: https://github.com/openai/openai-agents-python/blob/17d994bd3045dae71acda676a4ef4762ed8ecd94/src/agents/run_internal/agent_tool_configuration.py
[S8]: https://github.com/openai/openai-agents-python/blob/17d994bd3045dae71acda676a4ef4762ed8ecd94/src/agents/run_internal/run_loop.py
[S9]: https://api.github.com/repos/openai/openai-python/commits/v3.31.0
[S10]: https://github.com/openai/openai-python/blob/86cae50785fb7b7bf2a5d2383370b214b304acd2/src/openai/_client.py
[S11]: https://github.com/openai/openai-python/blob/86cae50785fb7b7bf2a5d2383370b214b304acd2/src/openai/_base_client.py
[S12]: https://github.com/openai/openai-python/blob/86cae50785fb7b7bf2a5d2383370b214b304acd2/src/openai/_constants.py
[S13]: https://github.com/openai/openai-python/blob/86cae50785fb7b7bf2a5d2383370b214b304acd2/src/openai/_httpx2.py
[S14]: https://github.com/openai/openai-python/blob/86cae50785fb7b7bf2a5d2383370b214b304acd2/src/openai/resources/chat/completions/completions.py
[S15]: https://github.com/openai/openai-agents-python/blob/17d994bd3045dae71acda676a4ef4762ed8ecd94/src/agents/tool.py
[D1]: https://platform.openai.com/docs/guides/function-calling
[D2]: https://openai.github.io/openai-agents-python/tools/
