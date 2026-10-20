# Revised prototype: clearer instructions helped, reply cap still blocks cases

2026-10-20 · [Try progressive discovery with the configured Qwen model](https://github.com/GoncaGomes/cst-agentic/issues/8)

## Simple summary

All nine scenarios were attempted with the requested changes. **30 of the new
200-request allowance used.** No HTTP 429 or timeout occurred. Nothing is running.

Several behaviors improved: the AI no longer waited for an extra “go” before the
uncertainty test; it inspected the existing parameter and kept the current solver;
the inspection-first cylinder loaded its material before creation.

Three scenarios failed because a **single reply exhausted its 3,072-token output
allowance before producing any visible text or tool call**. The SDK rejected the
empty, truncated response as `ModelBehaviorError`. This is not a server connection
failure, a native CST error, or exhaustion of the 30-turn allowance.

**More turns allow more replies; they do not make each reply longer.** The output
cap was deliberately unchanged. It was not raised or automatically retried.

All CST results remain mocked. No real project change, CST connection or native
simulation occurred. This is evidence for a decision, not a production controller.

## Exactly what changed

The human requested and approved:

1. `max_turns=30` for every scenario, equal for both configurations.
2. Explicit task decomposition and discovery guidance: split work into tasks,
   use suitable available tools, discover/inspect a group when needed, continue
   within existing authorization without a second user “go.”
3. A simple tool-group table in the system instructions. For example:
   `session_project (8): Manage CST sessions and the lifecycle of working projects.`
   All 19 groups appear; counts are variant-specific and exclude startup tools.
   Instructions explain overlapping groups and host deduplication.
4. A **fresh 200-request total budget**, explicitly approved after the earlier
   allowance had only three requests remaining. This does not reset or rewrite
   the original 45/48 usage; the new run used 30/200, leaving 170 unused.

Same nine scenario prompts, order, group mappings, schemas, mocks, endpoint/model,
18-function exposure cap, 3,072 output-token cap, 90-second HTTP bounds and
600-second scenario bounds. Retries/redirects/tracing/export remained disabled.
Scenarios still use separate fresh conversations, executed sequentially.

The system instructions are now retained inside each scenario record and shown
in the offline walkthrough, rather than requiring readers to reconstruct them
from source. No hidden reasoning transcript is claimed or published.

## Results — observed behavior, not a blanket pass count

| Scenario | Requests | Observation |
| --- | ---: | --- |
| Over-budget tools | 3 | Correct rejection of 20 functions; selected the instructed nine-function fallback. No CST operation. |
| Missing tool | 2 | Correct missing-cylinder report and atomic rejection; no substitution or retry. Final prose misspelled the fixture path as `.csl`, so target reporting still needs care. |
| Uncertain mutation | 3 | Actually called the mock cylinder, received the injected unknown outcome, then stopped. No retry, status check or reconnect after injection. |
| Unsupported edit | 4 | Recovered from an oversized selection, changed groups again, then output-length failure. No mutation or completed unsupported-edit answer. |
| Proposal-style cylinder | 5 | Mock cylinder and final summary completed. Still attempted creation before instructed library loading; recovered from the artificial no-effect refusal. |
| Inspection-first cylinder | 4 | Loaded exact library PEC first, then created mock cylinder and returned a qualified summary. No unnecessary extra setup. |
| Existing parameter edit/rerun | 7 | Checked mock connection and `patch_l=29`; edited existing parameter with consented deletion, launched using `{}` (preserve configured solver), monitored and summarized. |
| Proposal-style construction | 1 | First response consumed 3,072 output tokens, empty visible response, `finish_reason=length`; no tool call or project creation. |
| Inspection-first construction | 1 | Same first-response output-length failure; no tool call or project creation. |

Six scenarios returned final responses; three stopped on `ModelBehaviorError`.
**No scenario hit `MaxTurnsExceeded`.** The unsupported edit made three discovery
calls before its fourth response failed; both construction cases failed before
discovery. Neither a larger total request budget nor 30 turns was the binding limit.

## What improved — and remaining caveats

### Uncertainty handling reached the intended boundary

Previously, the model stopped after discovery and asked for “go,” so no failure
injection occurred. Now it called the cylinder without another approval and
reported the injected unknown outcome correctly. The trace showed no subsequent
CST dispatch. This is positive evidence for **one injected trace**, not native
transport-recovery validation.

Its suggested recovery wording still said it could proceed after the user reports
the outcome. That has not been tested and does not resolve the permanent poisoned-
client/reconciliation policy. Human confirmation alone is not a demonstrated
mechanism for unblocking the existing client.

### Existing-model work no longer invented a solver

Compared with the prior run, it now listed parameters before editing and called
`cst_run_simulation_async` with empty arguments, preserving the configured solver
instead of specifying Time Domain. The final answer separated synthetic activity
completion from numerical validation. It also explicitly planned work as tasks.

This is still a simplified fixture. The connection path is cached; independent
identity/units/dependency facts were supplied externally as mock context. There
was no independent post-edit numeric readback or native geometry verification.
The wait again used 55 seconds: schema-valid, but no real transport/queue deadline
or interruption responsiveness was established because the mock returned immediately.

### Smaller cylinder surface helped in this sample

With equal 30-turn caps, proposal-style took five requests and inspection-first
took four. Inspection-first also followed the library-first ordering. Prompt tokens
were 25,506 versus 17,225. This is one sample, not a statistically established
grouping winner. Proposal-style's synthetic refusal/recovery remains a policy-order
weakness, not evidence native CST always needs an explicit PEC load.

The three requested changes were applied together. Improved behavior cannot be
attributed separately to the task sentence, table, turn allocation or sampling.

### Output cap is now a concrete blocker

All three failing responses had HTTP 200, `finish_reason="length"`, 3,072 completion
tokens, empty text, and no tool calls. Inspected installed SDK code in
`agents/models/openai_chatcompletions.py` explicitly raises `ModelBehaviorError`
for this condition. No raw provider exception was exposed.

This supports output/token-budget exhaustion, potentially including provider
reasoning accounting; the retained trace does **not** expose hidden reasoning or
prove what consumed it. It does not demonstrate that the model cannot solve the
construction tasks with a different output budget. Raising output limits would
be a separate agreed experiment, not something silently done for this report.

## Process and evidence preservation

The runner stopped at the first model error. To finish the independent scenario
list without replaying failures, remaining scenarios started in new runner
processes at indices 4 and 8. A mechanical `--start-index` option was added; prompts,
limits and mock behavior were not altered. No failed scenario was retried.

Three evidence files share the **same new ledger**; their cumulative counters are
12, 29 and 30. These are not three separate 200-request allowances:

- `revised_30turns_transcripts.json`: first four scenarios, including failed edit.
- `revised_30turns_remaining_transcripts.json`: next four, including failed proposal construction.
- `revised_30turns_final_transcripts.json`: final failed inspection-first construction.

Original evidence remains unchanged. `review.html` labels the revised conversations
and displays original/revised budgets separately. Expand “System instructions and
tool-group table” to inspect the exact revised prompt. `measurements.json` includes
per-scenario turn limits and budget labels.

## Measurements — revised run only

| Measure | Observed |
| --- | ---: |
| Requests / HTTP 200 responses | 30 / 30 |
| New allowance used / limit | 30 / 200 |
| Prompt / completion tokens | 113,825 / 16,851 |
| Total reported tokens | 130,676 |
| Sum / range of HTTP latencies | 208.488 s / 1.047–37.063 s |
| Recorded tool invocations / discovery calls | 22 / 10 |
| Discovery rejections | Two over-budget; one missing-tool |
| Largest visible function set | 14 |
| Argument-schema/JSON rejection | None recorded |
| Injected uncertain mutation / later CST dispatch | 1 / 0 |
| Empty output-length failures / turn-cap failures | 3 / 0 |

Completion-token usage is provider accounting, not just visible prose. The new
run's lower request count does not establish overall efficiency: the two build
attempts stopped immediately instead of making the earlier partial progress.

## Recommendation and status

Keep the clearer task guidance and explicit table as promising candidates for
human review. Do not claim readiness, a final group inventory/count cap, native
safety, or a justified role downgrade. Retain host allowlists, budgets, atomic
selection, paired history and uncertainty enforcement independently of prose.

Before more endpoint work, agree whether to run a narrowly bounded output-cap
experiment for the three truncated scenarios. Keep this run intact and preserve
comparison limits. No further requests are planned automatically despite the
170 unused allowance.

Human judgment is still required for acceptable reporting, engineering initiative,
uncertainty/recovery language and the final discovery choice. Full construction,
port parameterization limits, unsupported-edit closure, stop semantics and native
acceptance remain unresolved. This issue stays open and claimed; no map decision
entry or production implementation is created.

## Verification

Preflight confirmed nine scenarios, all max-turn limits 30, budget 200 and 19
instruction-table rows. Python compilation/core Ruff checks, generator semantic
checks, embedded-JavaScript syntax/state smoke checks, exact configured-key/endpoint
scanning and staged whitespace checks accompany publication. No browser-rendering
check, application test suite, native CST execution, PR or merge. Main working-copy
changes remain untouched.
