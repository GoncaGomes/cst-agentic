# THROWAWAY: progressive CST tool discovery

Question: can the configured institutional Qwen endpoint make useful, trustworthy
progress with small, explicitly selected tool groups?

**Partial prototype, not production. No CST/server was launched or attached.**
Two initial scenarios reached the model, followed by an endpoint timeout. The
human-authorized restart received HTTP 429 on its first request. No comparison
verdict is available. `REPORT.md` is current; `FINDINGS.md` retains initial detail.

## Review without installing anything

Double-click `review.html`. It is self-contained and makes no network calls.

- **Free play** illustrates selection replacement, next-request activation,
  atomic rejection, missing tools, and the uncertainty block.
- **Conversations** replay the actual model responses, visible-tool sets, token
  usage and mock results. These are evidence of model/schema behavior only.
- `offline_lifecycle.json` separately demonstrates two SDK batch edge cases with
  a local mock HTTP transport. It is **not endpoint evidence**.
- See `REPORT.md` for observations, limitations and pending human feedback.

## Artifact contents

- `trial.py`: bounded endpoint harness, Agents SDK Chat Completions adapter.
- `schemas.json`: 73 source-evaluated upstream Tool declarations and annotations,
  grouped using the local proposal. Not a running MCP `tools/list` snapshot.
- `extract_schemas.py`: evaluates only reviewed declarations/helpers/enums;
  does not import upstream CST code or run handlers.
- `transcripts.json`: credential-scrubbed synthetic conversations and mock states.
- `continued_transcripts.json`: separately preserved HTTP-429 restart.
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

The human approved **48 new HTTP requests for the originating session**. Exactly
nine were dispatched: eight initially, then one after explicit restart approval.
Execution stopped on timeout and, on restart, HTTP 429; no retry was made. The
ledger is outside the branch; unused capacity is not a standing authorization
for arbitrary future runs. Agree continuation and preserve the cumulative ledger.
The current harness writes `continued_transcripts.json`; choose a fresh evidence
destination before another run rather than overwriting the retained restart.

The live invocation shape is documented only for reproducibility:

```powershell
uv run --no-sync python <prototype-directory>/trial.py --live --config-root <configured-repo> --budget-ledger <session-ledger.json>
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
