# THROWAWAY: progressive CST tool discovery

Question: can the configured institutional Qwen endpoint make useful, trustworthy
progress with small, explicitly selected tool groups?

**Partial prototype, not production. No CST/server was launched or attached.**
The revised task-guidance/table run attempted all nine scenarios: **30 / 200 new
requests used**, all HTTP 200. Some behavior improved, but three cases exhausted
the unchanged per-reply output-token cap. `REPORT_REVISED_30_TURNS.md` is current.
Earlier reports/evidence remain historical; original budget usage stays **45 / 48**.
No final grouping/role verdict is adopted.

## Review without installing anything

Double-click `review.html`. It is self-contained and makes no network calls.

- **Free play** illustrates selection replacement, next-request activation,
  atomic rejection, missing tools, and the uncertainty block.
- **Conversations** replay the actual model responses, visible-tool sets, token
  usage and mock results. These are evidence of model/schema behavior only.
- `offline_lifecycle.json` separately demonstrates two SDK batch edge cases with
  a local mock HTTP transport. It is **not endpoint evidence**.
- See `REPORT_REVISED_30_TURNS.md` for observations, limitations and pending human feedback.

## Artifact contents

- `trial.py`: bounded endpoint harness, Agents SDK Chat Completions adapter.
- `schemas.json`: 73 source-evaluated upstream Tool declarations and annotations,
  grouped using the local proposal. Not a running MCP `tools/list` snapshot.
- `extract_schemas.py`: evaluates only reviewed declarations/helpers/enums;
  does not import upstream CST code or run handlers.
- `transcripts.json`: credential-scrubbed synthetic conversations and mock states.
- `continued_transcripts.json`: separately preserved HTTP-429 restart.
- `retry_2026_10_20_transcripts.json`: subsequent 36-response retry.
- `revised_30turns*_transcripts.json`: three preserved parts of the revised run,
  sharing one fresh 200-request ledger. Exact system instructions included.
- `measurements.json`: observations derived from both evidence files.
- `make_review.py`: embeds evidence in the offline HTML.
- `offline_lifecycle.py`: deterministic local SDK demonstration.

The proposal-style configuration has two startup functions (status/discovery),
not the proposal's unimplemented analyst handoff. The prepared inspection-first
variant adds project-info at startup, reduces project-context to tree inspection,
and reduces materials to native loading plus bundled-name listing. This is a
bundled exploratory variant, not a controlled single-variable experiment. Both
use the provisional 18-function cap. Neither the alternate grouping nor that cap
has been evaluated adequately.

## Reproduce offline artifacts

From the original configured application checkout, using its existing uv environment:

```powershell
uv run --no-sync python <prototype-directory>/offline_lifecycle.py
uv run --no-sync python <prototype-directory>/make_review.py
```

The HTML needs neither command. Offline lifecycle replay requires the project's
locked dependencies but neither credentials nor a CST installation. No new tests
or production interfaces were added.

## Live execution is not automatically authorized

Two separately approved allowances: original **45/48**, revised **30/200**. The
revised run uses max_turns=30 and task/table instructions; other model/tool/mock
settings remain unchanged. No automatic failed-scenario retries occurred.
Ledgers live outside the branch. Unused capacity is not standing authorization
for arbitrary future runs. Agree continuation and preserve the appropriate ledger.
The harness requires an explicit, nonexisting `--evidence-file` and an existing
budget ledger; it refuses to overwrite evidence. Optional `--start-index` starts
at a later independent scenario, not a replay of a failed conversation.

The live invocation shape is documented only for reproducibility:

```powershell
uv run --no-sync python <prototype-directory>/trial.py --live --config-root <configured-repo> --budget-ledger <session-ledger.json> --evidence-file <new-evidence.json>
```

Credentials are resolved with the application's file-before-environment precedence;
only variable presence is printed. The harness disables tracing/logging, restricts
HTTP origin/path, disables redirects/retries, counts at the transport boundary,
uses 90-second request and 600-second scenario bounds, and limits output to 3,072
tokens per response. It never runs upstream handlers. Do not publish `.env`, ledger
configuration, raw HTTP errors, or raw provider traces.

## Deliberate limitations

Mocks are not native execution emulators. They do not validate physics, expressions,
all semantic argument constraints, real project identity, units, authorization,
partial mutation, interruption, or transport teardown. Exposed operations without
a mock handler return an explicit block. That gap affected material assignment
in the recorded cylinder attempt and must not be attributed to the model/provider.

The fixture's identity/unit assertions and simplified tool result envelopes are
synthetic harness inputs, not new MCP capabilities. Parameter reads deliberately
do not invent stored-expression readback. Uncertain-mutation injection is prepared
but was not reached live. The free-play rules are illustrative, not an implementation
of the final authorization/discovery policy.

No PR or merge is intended. This artifact captures evidence for a decision ticket;
human feedback and broader trials remain necessary before resolution.
