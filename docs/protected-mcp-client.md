# Protected MCP client integration

Issue [#16](https://github.com/GoncaGomes/cst-agentic/issues/16) extends the existing
client without enabling connected Controller behavior in the connectivity command.

## Catalogue and outcomes

- `await client.discover_tools()` still returns names in discovery order,
  including duplicates.
- `await client.discover_tool_definitions()` returns detached SDK `Tool` objects
  across all pages. Input/output schemas and metadata are canonical, not converted
   into stricter schemas. Catalogue access does not grant execution permission.
  Catalogue pages share the dispatch serialization lock, include queueing in each
  page allowance, and refuse access after permanent client uncertainty. The
  Controller session further restricts refresh to settled lifecycle-owner points.
- `McpToolCall.text` and `.payload` retain their first-text-block meanings.
  `.content` retains **all** returned content blocks; `.structured_content` retains
  the returned structured data. These are detached from the SDK response.
- Client-created records set `.evidence_complete=True`: no returned blocks or
  structured content were omitted/truncated by the client. Legacy manually created
  records default to `False`. This is not proof that the server reported every
  effect, that a rebuild succeeded, or that the native operation had no partial
  effects. A future bounded model-facing projection must identify its omissions.

## Dispatch

```python
outcome = await client.call_tool(
    tool_name,
    arguments,
    timeout_s=operation_allowance_s,
    dispatch_guard=check_current_prerequisites,
)
```

Both keyword arguments are optional; existing two-argument callers are unchanged.
Allowances must be finite positive numbers, not booleans. The explicit allowance
does not mutate `client.request_timeout_s`. Queueing, the guard and SDK execution
consume one allowance; waiting does not earn a new execution budget.

The execution gateway supplies a synchronous `() -> bool` guard. It must return
exactly `True` after checking current authorization, target and prerequisites.
It can also require successful synchronous recovery-marker persistence before
approving. There is no await between approval and the dispatch marker. Keep the
guard short: synchronous code cannot be force-timed-out safely. Its elapsed time
is checked before dispatch. False, invalid/async results or exceptions refuse
dispatch without latching uncertainty; exception text is not exposed.

The client does **not** choose policy maxima, implement a recovery store, validate
task authorization itself, or provide a new direct SDK dispatch route. Those are
Controller integration responsibilities. The agreed maxima remain ordinary/status
120 s, launch 480 s, short wait 45 s and stop 60 s. They are not native timeout
settings or hard real-time guarantees.

## Safety and evidence boundary

Queue expiry and guard refusal are `not_dispatched`. A returned domain/tool error
is `received`, possibly with partial effects. Post-dispatch timeout, cancellation
or SDK exception is `uncertain`: it permanently blocks **all** subsequent tool
calls on that client, including status and stop. No retry, reconnect or new client
proves reconciliation. Simulation stop uses the same serialized connection and
cannot overtake active work.

Offline tests use fake SDK sessions and the actual public SDK/stdio wrapper with
a disposable local JSON-RPC peer. The latter checks pagination, response handling,
SDK validation uncertainty, received domain failures and normal context cleanup.
It does not certify failed cleanup, crash durability, native CST behavior, endpoint
schema acceptance or solver-stop latency. Existing lifecycle implementation and
connectivity configuration remain unchanged. No CST or institutional endpoint
request is part of these tests.
