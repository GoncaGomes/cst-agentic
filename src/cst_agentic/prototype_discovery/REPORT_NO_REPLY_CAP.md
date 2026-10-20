# Uncapped follow-up: final answers returned, engineering blockers remain

2026-10-20. Supporting evidence for
[Try progressive discovery with the configured Qwen model](https://github.com/GoncaGomes/cst-agentic/issues/8).
**THROWAWAY, MOCK CST ONLY. The decision ticket remains open.**

## Outcome

All three previously truncated scenarios returned final answers after removal of
the client-side 3,072-token reply cap. None hit a turn limit, output-length stop,
timeout or HTTP error. Returning a final answer is not the same as completing a
build: both construction conversations ended with explicit blockers.

The human requested removal of the cap, then limited the rerun to the unfinished
scenarios. This follow-up used **21 requests** on the same revised ledger, moving
usage from **30/200 to 51/200**, leaving 149 unused. Original usage remains 45/48
on its separate ledger. Nothing is running and no additional requests are planned.

## Experiment boundary

- Removed `max_tokens=3072` from `ModelSettings`. The client now leaves the
  reply-token limit unspecified. Provider defaults, context and output limits may
  still apply. This is not an unrestricted model run.
- Repeated only unsupported edit and both construction variants, each as a fresh
  conversation. Repeatable `--scenario` selects these without replaying other tests.
- Kept the same scenario prompts, mock handlers, source-derived schemas, model,
  group mappings, task/table instructions, 30-turn limits and 18-function cap.
- Kept the request-budget and timeout safeguards, sequential execution, disabled
  tracing and no automatic retries. No real CST imports or operations occurred.
- Preserved all previous evidence. `no_reply_cap_transcripts.json` is the new
  source artifact, including exact instructions, visible tools and mock results.

## What the model did

| Scenario | Requests | Observed outcome |
| --- | ---: | --- |
| Unsupported edit, proposal-style | 2 | Discovered geometry schemas, reported no supported identity-preserving dimension-edit route under the constraints, and asked about alternatives. No CST operation dispatched. |
| Construction, proposal-style | 11 | Created the mock project, eight parameters, PEC ground and patch. Failed to load the requested substrate material because it tried the wrong names. Substrate creation was refused. Asked for material help and a port revision. |
| Construction, inspection-first | 8 | Listed available material names, loaded exact PEC and Rogers RT-duroid 5870 (loss free), created all three mock solids with named expressions, then asked for a port revision. |

### Unsupported edit: useful limitation answer, not complete capability proof

The final response respected the no-replace/no-scale/no-run constraints and did
not attempt a mutation. It proposed boolean extension or explicit relaxation of
the constraints, rather than silently substituting a rebuild.

It inspected geometry creation schemas but did not activate `solid_operations`
before making broader claims about that group's capabilities. Its suggested
project-tree property inspection is not demonstrated by this trace. Treat the
answer as a qualified model explanation, not verified native identity semantics
or proof that all potential edit paths were inspected.

### Proposal-style build: material mistake, not genuine catalogue absence

The prompt requested **Rogers RT-duroid 5870 (loss free)**. The model instead tried
`Rogers RT-duroid 5870`, `Rogers RT5870` and `RT5870`. All three were refused by
the mock. It consulted bundled material info, which supplied no numeric properties,
then tried a substrate using the unloaded wrong name. That operation was refused.

Its final claim that the requested material was unavailable is misleading: the
exact requested entry exists in the fixture and the inspection-first run loaded
it. This is a name-selection failure in this trace, not native library evidence.
It did not invent dielectric properties, save or run a simulation. It recovered
from one over-budget group selection by dropping unnecessary tools.

### Inspection-first build: useful progress and the intended clarification

The model used the available material-name listing before loading the exact
entries. All three brick calls used named parameter expressions. Mock success
does not validate native expression retention or actual geometry.

Both variants inspected the discrete-port schema and recognized that coordinates
are numeric-only. Both withheld port creation rather than silently freezing
`feed_x`, `feed_y` and `substrate_h`, as required by the scenario. Both asked for
a revised requirement or explicit acceptance of frozen coordinates. Neither saved,
configured a solver or ran a simulation.

Some final wording still overstates project state: e.g. the focused response says
the original project remains "selected-hold" after creating the new project.
Cached mock connection state and fixture assertions are not independent evidence
that a real prior project was preserved or remains selected.

## Measurements, this follow-up only

| Measure | Observed |
| --- | ---: |
| Requests / HTTP 200 responses | 21 / 21 |
| Prompt / completion tokens | 116,770 / 23,375 |
| Sum / range of HTTP latencies | 271.558 s / 1.031–76.297 s |
| Recorded tool invocations / discovery calls | 43 / 9 |
| Largest visible function set | 16 |
| Discovery rejections | One over-budget |
| Model errors / output-length stops / turn-cap stops | 0 / 0 / 0 |

Completion-token accounting may include non-visible provider work. No hidden
reasoning is exposed or inferred. Unsupported edit used 10,166 completion tokens
across its two replies. Per-scenario measurements are in `measurements.json` under
`no reply-token cap`, with `reply_token_cap: null`. Earlier rows retain 3072.

## Interpretation and pending decision

Removing the reply cap eliminated the previous truncation in these three fresh
samples. It allowed the tests to expose actual behavioral differences and the port
schema limitation. It does not prove unrestricted reliability or that output length
was the only influence: these are sampled fresh conversations, not identical replay.

Inspection-first made better material progress with fewer requests in this build
sample, consistent with the earlier cylinder result. Grouping changes remain a
bundle, not an isolated causal comparison or final grouping verdict.

Human review is still needed on the transcripts, explanations and acceptable
controller behavior. No ticket resolution, production implementation, native CST
acceptance or map decision is implied. Keep the issue open. No PR or merge.

## Published artifacts and checks

`review.html` includes the latest three conversations labelled `no reply-token cap`
and displays revised cumulative usage as 51/200 separately from original 45/48.
The README points here as the current report. Previous reports remain historical.

Publication checks cover Ruff, Python compilation, regenerated measurement and
walkthrough consistency, embedded JavaScript syntax and selection-state smoke
checks, credential/endpoint-value scanning, and Git whitespace. No browser-rendering
check, full application test suite or native CST validation is claimed.
