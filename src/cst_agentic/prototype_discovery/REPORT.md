# Qwen progressive-discovery trial report

Historical restart report. See [the latest follow-up](REPORT_NO_REPLY_CAP.md).
Observations and counters below describe this earlier run only.

2026-10-19 · [Try progressive discovery with the configured Qwen model](https://github.com/GoncaGomes/cst-agentic/issues/8)

## Outcome

**The restart reached the institutional endpoint but was refused with HTTP 429.**
The comparison remains incomplete. There is insufficient evidence to select a
grouping, approve the engineering-assistant role, or require its narrower fallback.

The user's VPN hypothesis is recorded, not confirmed. Receiving HTTP 429 shows
reachability at restart; it does not diagnose the earlier timeout. No retry,
cooldown loop, provider substitution or further probe followed.

## Runs and budget

| Run | Dispatches | Result |
| --- | ---: | --- |
| Initial | 8 | Seven successful responses, then `APITimeoutError` |
| Human-authorized restart | 1 | HTTP 429 after 0.218 s; no model response or tool call |
| Cumulative | **9 / 48** | Seven successes, one timeout, one HTTP 429 |

The human authorized continuation within the original budget after suggesting
the VPN might have been off. The restart used fresh synthetic conversations,
retained the cumulative transport ledger, and did not replay the interrupted
conversation. **39 requests were unused**, not authorization for an unattended
future retry campaign. Credentials, endpoint and model were unchanged. Retries,
redirects, tracing/export and ordinary provider logs remained disabled. Bounds:
90-second requests, 3,072 output tokens, finite scenario turn/time limits.

All CST outcomes were mocked. No MCP server launch, CST attachment, project
mutation, native verification, production implementation, PR or merge occurred.
Existing main working-copy changes were preserved.

## Actual model evidence

1. **Narrow in-run activation worked.** Inside one Agents SDK Runner invocation,
   discovery activated source-derived primitive schemas on the next request,
   retaining paired historical calls/results. Visible counts were 2, 7 and 13.
   This does not validate the 18-function cap or arbitrary replacement/batching.
2. **Clarification needs review.** “Create a cylinder” produced questions about
   dimensions, axis, center and material and reused supplied mock target/units.
   However, “PEC by default” and “defaults can fill the rest” suggest unapproved
   choices might be used. No such values were executed in that clarification.
   It also asked about incidental names rather than generating them.
3. **Ordering and evidence language were weak.** For the fully specified cylinder,
   Qwen selected relevant groups but tried creation before the instructed library
   load. After a synthetic no-effect refusal it loaded PEC, obtained mock creation
   acceptance, then described material assignment as confirmation. Assignment is
   an action, not independent material-property verification. No final summary
   was received.
4. **Harness coverage confounded progress.** Assignment was exposed but initially
   unimplemented. That block is a harness gap, not an endpoint failure. The mock
   guard requiring PEC loading is likewise not a new native CST requirement.

All six observed tool calls had valid JSON-schema arguments; this does not establish
semantic correctness or native effects. Seven successful responses reported
**28,152 prompt + 2,034 completion = 30,186 tokens**. Their observed latency was
**3.266–14.453 s**, sum **43.749 s**. Failed requests supplied no usage; the timeout's
measured duration was not retained. No repeated discovery cycle was observed.

## Restart preparation and evidence separation

The mock gained explicit assignment, bundled-material lookup, numeric discrete-port,
solver/mesh-fixture and log responses. Mutation acceptance remains distinct from
native verification; numeric ports report no preserved parameter dependencies.
Edge scenarios were moved ahead of lengthy construction cases. The system
instruction and two candidate configurations were retained; no provider swap or
post-success prompt tuning occurred. Turn allocations fit the remaining budget.

**No repaired handler received a model-generated call:** the restart's first
request returned 429. The initial `transcripts.json` is unchanged;
`continued_transcripts.json` preserves the restart separately. Exact initial source:
`b2a96130032bfb1d746dd87e251ca0d0c81f5bfe`.

## Offline evidence and verification

- Evaluated 73 pinned upstream Tool declarations and registry annotations across
  19 proposal groups, preserving optional fields, number/string unions and untyped
  parameter values. This is source-derived, not running MCP catalogue evidence.
- Local MockTransport SDK replay demonstrated next-request replacement, paired
  history, an old-visible tool executing in a mixed batch, and a new-hidden tool
  not executing prematurely. **Not institutional endpoint evidence or final policy.**
- The self-contained HTML replays observed conversations and provides deterministic
  free play for activation/rejection/uncertainty. Free play does not replace trials.
- Python compilation/core Ruff checks, generator semantic/import checks,
  JavaScript syntax/state smoke checks, exact configured-key/endpoint scans and
  staged whitespace checks were performed. Browser rendering, application tests
  and native execution remain unverified.

## Recommendations and remaining work

- Retain explicit group replacement as a **candidate**, not a settled contract.
- Enforce active tools, budgets, history pairing and uncertainty in the host,
  independently of model prose.
- Present engineering suggestions for agreement; do not silently adopt tool
  defaults. Do not describe material assignment as readback.
- Cover all relevant exposed operations in mocks; distinguish artificial guards
  and missing handlers from model/provider failures.
- Address endpoint availability/rate-limit handling and agree bounded continuation
  before resuming. Restarting this mocked trial says nothing about replay safety
  for native mutations.

Still untested live: inspection-first variant, parameterized construction/edit/rerun,
replacement after an already active capability, mixed batches, over-budget and
missing-tool recovery, unsupported edits, injected mutation uncertainty, stop
semantics, material absence, numeric-port dependency disclosure and engineering
proposals/trade-offs. The restarted over-budget scenario did not reach the model
and therefore **does not count as an exercised rejection case**.

The human requested a restart/report but has not judged the behavioral transcripts.
**The decision remains open and claimed.** No resolution or map Decisions-so-far
entry is justified. Existing discovery/state/safety/runtime/acceptance tickets
remain the homes for those decisions; no distinct new question requires duplication.

## Assets

- `review.html`: double-click offline; initial/restarted conversations labelled.
- `transcripts.json` / `continued_transcripts.json`: retained safe evidence.
- `measurements.json`: derived observations, not acceptance verdicts.
- `FINDINGS.md`: historical initial-run detail.
- `README.md`: artifact boundaries and reproduction instructions.
