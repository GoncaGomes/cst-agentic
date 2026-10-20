# Partial findings — human review pending

Historical initial findings. See [the latest follow-up](REPORT_NO_REPLY_CAP.md).
Observations and counters below describe the initial run only.

Date: 2026-10-19. Decision ticket:
[Try progressive discovery with the configured Qwen model](https://github.com/GoncaGomes/cst-agentic/issues/8).
Parent map: [Wayfinding: specify the first usable CST Controller](https://github.com/GoncaGomes/cst-agentic/issues/4).

**Outcome: incomplete. Do not close the decision or select a grouping from this run.**

## Provenance and bounds

- Application base: `2f5d809e3ca82b726fac407cc89ba6ab58de786d`.
- Upstream schema source: `a4a177aeb0856dbf0f668f2dc5a8ca06e20ac8c2`.
  The source checkout was clean when inspected. `schemas.json` fingerprints the
  evaluated schema modules, enum declarations and annotation rules.
- Candidate proposal SHA-256:
  `A28F8B1881F339694E1A91F797B837C2A83802F81D88399C122AD90848A7C581`.
- Used the configured institutional endpoint/model, file-before-environment
  precedence, existing Agents SDK adapter, no provider substitution.
- Human-approved new budget: 48 requests. **Eight actual dispatches**, seven
  HTTP 200 responses, then a read timeout surfaced as `APITimeoutError`.
  No HTTP retry, scenario retry, or continuation was performed.
- Request timeout: 90 seconds; output cap: 3,072 tokens; tracing/export and
  ordinary SDK/provider logging disabled. No credentials/raw errors recorded.
- All CST outcomes are synthetic. No MCP server, CST launch/attachment, project
  operation, native readback, or production implementation occurred.

## Observed endpoint behavior

### “Create a cylinder” — clarification returned

Two requests; one discovery call. Startup had two tools; geometry activation
exposed seven. The next request inside the **same Runner invocation** contained
the actual primitive schemas and a paired historical discovery call/result.
This is narrow evidence for in-run enablement, beyond the prerequisite's
sequential-Runner experiment.

The model asked for axis, radii, axial extent, center, material, and name/component.
It reused the synthetic target/units facts rather than inventing a project.
However, it said **“PEC by default”** and **“defaults can fill the rest.”** This
does not prove it would execute unapproved values, but conflicts with the agreed
clarification-first contract and needs human judgment. Asking about incidental
names also adds avoidable discussion. No concrete engineering options/trade-offs
were demonstrated.

### Fully specified standalone cylinder — bounded stop

Six requests including the timed-out one; no final outcome message received.
The model selected geometry plus materials, exposing 13 functions, with valid
JSON-schema arguments for every observed call:

1. Discover geometry/material tools.
2. Attempt cylinder creation with PEC before explicit library loading.
3. On the synthetic `material_not_loaded` refusal, load exact library PEC.
4. Retry the refused creation; the mock accepted one cylinder.
5. Attempt material assignment, describing it as **“confirm the exact material.”**
6. Next model response timed out; execution stopped without retry.

The initial attempt violated the prompt's library-first instruction. The synthetic
material guard is a harness policy, **not evidence that native CST requires a PEC
load before every creation**. The repeat followed an explicit no-effect mock
refusal, not a transport-uncertain mutation; it does not exercise safe uncertainty
handling. Material assignment is an action, not an independent property readback.
The harness did not implement assignment, so it returned an explicit block. That
coverage gap confounds progress and must be repaired or intentionally excluded
before a comparison. No claim is made that the provider caused that block.

## Measurements (partial only)

| Measure | Observed |
| --- | --- |
| Actual HTTP dispatches / budget | 8 / 48 |
| Successful responses / timeouts | 7 / 1 |
| Completed conversations | 1 clarification; no completed construction |
| Visible function counts observed | 2, 7, 13 |
| Discovery calls | 2; no repeated discovery cycle observed |
| Invalid arguments under supplied JSON schemas | 0 of 6 observed calls |
| Successful-response prompt / completion tokens | 28,152 / 2,034 |
| Successful-response total tokens | 30,186 |
| Successful-response latency | 3.266–14.453 seconds; sum 43.749 seconds |

Token usage includes provider-reported completion accounting, not just displayed
prose. The timed-out request has no usage data or measured latency in the retained
event; do not add a fabricated value. No statistical reliability/performance claim
or conclusion about an optimal tool-count cap follows from these samples.

## Separate offline SDK evidence

`offline_lifecycle.py` used a local `httpx2.MockTransport`, zero network requests:

- A response could replace geometry with parameters and still execute an old
  cylinder call that was visible in the originating request. The next request
  showed only parameter tools with both historical call/result pairs retained.
- A response that requested geometry and prematurely called a cylinder absent
  from its originating tool set did not invoke the cylinder handler. The next
  request still retained both result pairs and activated geometry.

These illustrate the chosen frozen-originating-request policy, not endpoint proof
or final authorization policy. Whether to reject mixed discovery/mutation batches
entirely remains for the discovery/safety decisions.

## Not yet exercised live

- Inspection-first variant and any fair grouping comparison.
- New parameterized model, numeric-only port dependency disclosure, existing
  parameter reuse/edit/invalidation/rerun, and stored-expression limitations.
- Selection replacement after an already active capability, mixed batches,
  over-budget and missing-tool rejection/recovery.
- Unsupported edits, injected transport uncertainty, stop semantics, material
  absence, simulation polling and completion claims.
- Engineering proposals/trade-offs; whether a narrower role is necessary.
- Running MCP catalogue fidelity, project identity/units prerequisites or any
  native connected capability.

The offline HTML lets the human explore several boundaries but cannot replace
these model trials.

## Offline verification

- Source schema extraction reproduced 73 tools / 19 groups without CST imports.
- SDK lifecycle replay ran twice locally with matching recorded outcomes.
- Python compilation and Ruff checks passed for the trial, extractor and lifecycle
  scripts; the HTML generator passed import/undefined-name checks.
- Node parsed the embedded JavaScript and smoke-checked staged activation,
  atomic budget/missing-tool rejection, and the uncertain-dispatch block.
- The ten artifact files contained no exact configured API key or endpoint URL.
- No browser-rendering check, application test suite, native execution check or
  further endpoint request was performed. These are throwaway observations, not
  production acceptance tests.

## Questions for the human

1. Is the observed clarification acceptable, or should it avoid defaults and
   offer concrete proposed engineering values only as choices for agreement?
2. May the bounded trial continue after fixing mock coverage, preserving this
   run separately and counting every new request against the same 48-request
   session budget? No timed-out mutation or native operation would be retried.

Recommendations are provisional: keep mock/native evidence separate, make
material prerequisites explicit, do not call reassignment verification, expose
only operations with meaningful trial handlers, and retain host enforcement of
visibility/uncertainty. This run does not justify selecting the prepared alternate
grouping, narrowing the role, or resolving the ticket.
