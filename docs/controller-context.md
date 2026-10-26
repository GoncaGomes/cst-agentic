# Bounded Controller context (#21)

The authoritative contracts remain the final resolutions of
[#10](https://github.com/GoncaGomes/cst-agentic/issues/10#issuecomment-6302432267),
[#12](https://github.com/GoncaGomes/cst-agentic/issues/12#issuecomment-6304790260) and
[#13](https://github.com/GoncaGomes/cst-agentic/issues/13#issuecomment-6318605504),
with their explicit supersessions. This documents implementation, not a new
capacity decision or endpoint/native acceptance evidence.

## Admission and validation configuration

Every coordinator request requires a `ContextBudget`, independently of the
existing request-admission callback. Neither a permissive callback nor a familiar
model name supplies capacity. Missing/unvalidated capacity emits `context_pause`
and sends no model request. Other schema, dispatch, authorization and recovery
gates remain independent; configuring context does not enable production work.

The optional Controller-only `CST_CONTROLLER_CONTEXT_VALIDATION_FILE` points to a
small credential-free UTF-8 JSON record. A missing setting leaves model admission
blocked but permits manual/status-only startup. Invalid/mismatched records fail
configuration without echoing their contents. This setting is never forwarded to
the MCP child. The connectivity command is unchanged.

Record shape (deliberately **invalid/unvalidated**, not operational defaults):

```json
{
  "method": "logical-json-utf8-v1",
  "input_capacity": null,
  "headroom": null,
  "endpoint": "<exact configured credential-free base URL>",
  "model": "<exact configured model ID>",
  "adapter": "<exact installed adapter identity>",
  "validated": false,
  "validation_reference": "<reviewed endpoint-validation evidence reference>"
}
```

Capacity/headroom must be positive integers, with headroom smaller than capacity.
Endpoint/model must match configuration exactly. Adapter identity includes both
installed SDK versions and the accounting method; upgrades require revalidation.
To obtain only that non-secret identity:

```powershell
uv run python -c "from cst_agentic.context_budget import adapter_identity; print(adapter_identity())"
```

An operator-reviewed record is an attestation, not cryptographic proof or an
automatic probe. Set `validated` only after the separate bounded endpoint campaign
establishes capacity, accounting and headroom for this adapter/model. Do not infer
these from model naming, an advertised maximum or offline tests. No real record
or endpoint capacity was established by this implementation.

## Reproducible accounting

`logical-json-utf8-v1` charges each UTF-8 byte of canonical logical-request JSON
as one estimated input token: `ensure_ascii=False`, sorted keys, compact separators,
and rejection of nonfinite numbers. The reported sections are:

- trusted instructions (including discovery guidance);
- all accepted active native function definitions, without schema narrowing;
- complete input, including objective, scoped permission, evidence/gaps, notes,
  discussion omission summary, user exchanges and paired tool history;
- the structured conversational response schema;
- fixed request options, including disabled parallel calls and empty handoffs.

The estimate plus explicit headroom must not exceed the validated input capacity.
Headroom must cover actual tokenizer/wire-framing/SDK conversion differences in
the endpoint evidence. This is **not** a universal byte/token bound or an exact
provider usage calculation. `context_accounting` contains only method, section
counts, capacity and headroom, never request contents or validation-file contents.
Future decision memory must be projected into this counted input; this slice does
not implement decision-note storage or approval.

No `max_tokens` or other blanket output-token cap is introduced. Provider defaults
remain unchanged. A failed count or essential overflow pauses before the next
request instead of trusting provider-side truncation.

## Settled compaction and provenance

Only fully settled history batches enter the compaction ledger. A tool batch
contains the entire received response and **all** matched outcomes, including
skipped/rejected calls. It is removed whole, never one call/result at a time.
Compaction occurs before model admission, never during native dispatch.

Within the current objective, all conversational exchanges are conservatively
essential, including unanswered questions and discussion co-returned with calls.
The four most recent settled batches are also retained. Older tool-only batches
may be removed under pressure; earlier-objective batches may be removed even if
recent, since current scope is projected independently. If protected content
still cannot fit, `context_pause` explains the blocker. A smaller explicit new
task can retire oversized earlier-task discussion; it grants no new native target
or execution permission.

Compaction emits `context_compacted`, counts omitted batches/observations and
retains a bounded discussion-context omission summary, explicitly **not verified
facts or authority**. Observation references whose supporting pairs were removed
are removed too, with an unknown/unavailable evidence gap. Retained observations
carry time/order, originating objective and response provenance, never an inferred
live target. They remain historical received responses, not independent verified
native facts; task/target changes cannot promote them. Typed current native facts
still require the independent evidence prerequisites. Any reinspection requires
ordinary authorization, visibility, target and uncertainty checks.

Model-facing outcomes have a 16,384-byte allowance. Oversized payloads are omitted
as whole fields with explicit original size, omitted block/selection indicators
and unavailable support. No clipped JSON/text is presented as complete evidence.
Bounded observation copies also account for legacy text/payload/argument fields.
Complete protected-client attempt records remain separate in-memory evidence;
this is not a universal process-memory cap or automatic transcript persistence.
Canonical instructions, schemas, permissions, call arguments and recent pairs are
not silently truncated to make a request fit.

## Verification status

Deterministic tests use the shared `ConversationCoordinator.submit` seam with
explicitly synthetic context attestations. They cover missing validation,
accounting/headroom, safe overflow pauses, batch pairing, evidence-support loss,
large outcomes/discovery rejections, unanswered questions, changed objectives and
requested targets. Production-factory/configuration tests check attestation
binding and continued independent acceptance gates with a controlled stdio peer.

- Offline deterministic/local-wrapper evidence: automated tests.
- Actual institutional endpoint context/schema validation: **not run**.
- Configured-model behavioral trials: **not run**.
- Native CST/live-target/solver evidence: **not run**.

No model/native campaign budget is consumed and no connected mutation is
authorized by this change.
