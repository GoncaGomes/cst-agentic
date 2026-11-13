# Protected MCP client

The base MCP client supports the connectivity check without enabling native CST
operations. The check's gateway exposes and allows only `cst_connection_status`.

## Catalogue and responses

- `await client.discover_tools()` returns names in discovery order, including
  duplicates, following every pagination cursor.
- `await client.discover_tool_definitions()` returns detached SDK `Tool` objects
  with canonical input/output schemas and metadata, without strict-schema
  conversion. Catalogue access does not grant execution permission.
- Catalogue pages share the dispatch lock, include queueing in each page's
  request allowance, and refuse access after permanent client uncertainty.
- `McpToolCall.text` and `.payload` describe the first text block. `.content`
  retains all returned blocks; `.structured_content` retains structured data.
  These are detached from the SDK response.
- Client-created records set `.evidence_complete=True`: the client omitted no
  returned blocks or structured data. Legacy manually created records default
  to `False`. Neither value proves native execution success or absence of
  partial effects.

## Dispatch and attempt records

`await client.call_tool(name, arguments)` serializes calls per client. Optional
`timeout_s` overrides the request allowance for one call; optional
`dispatch_guard` is a synchronous no-argument callback that must return exactly
`True` before dispatch. False, invalid/async results or exceptions refuse
dispatch without latching uncertainty. Guard exception text is not exposed.
Keep guards short: synchronous code cannot be preempted safely.

Allowances must be finite positive numbers, not booleans. Queueing, the guard
and SDK execution consume one allowance. Arguments are deep-copied before the
first await. Every admitted call produces a `McpAttempt` in `.attempts`, with
timings, dispatch state, terminal outcome and a returned record if available.
Only returned responses appear in `.calls`.

- `not_dispatched`: queue expiry, guard refusal, cancellation before dispatch,
  a missing session or an already uncertain client. No SDK call was made.
- `received`: a response returned, possibly a tool error or partial effects.
- `uncertain`: timeout, cancellation or SDK/transport failure after dispatch.
  All subsequent calls and catalogue requests on that client are blocked.

Attempt diagnostics use bounded categories rather than raw exception text.
There is no automatic replay; replacing a client does not establish what an
uncertain operation did. The client supplies transport guards, not application
authorization or durable recovery.

## Verification boundary

Offline tests use fake SDK sessions and the real SDK/stdio wrapper with a
disposable local JSON-RPC peer. They cover pagination, response handling,
serialization, request bounds, uncertainty and normal cleanup. They do not
certify crash durability, native CST behavior, endpoint schema acceptance or
solver behavior. No CST or institutional endpoint request is part of the tests.
