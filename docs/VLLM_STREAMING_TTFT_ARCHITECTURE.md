# vLLM Streaming TTFT Architecture and Feasibility

## Status

**IMPLEMENTED — V1 COMPLETE**

The architecture described below is implemented as opt-in streaming evidence
mode (`--vllm-streaming-evidence`) with the qualified vLLM SSE transport
(`return_token_ids=true`). The reasoning-token contract question is RESOLVED
by human decision: the first backend-generated token counts for neutral TTFT,
including reasoning tokens. See [Implementation status](#implementation-status)
below for the reconciliation with this document's original text.

The token boundary is a raw backend token ID carried in a stream chunk, not a
text, role, or metadata event. The non-streaming default is unchanged.

## Current non-streaming boundary

The accepted vLLM backend is `src/llmgauge/runners/vllm_external.py`
(`run_chat_completion`) over `src/llmgauge/runners/vllm_http.py`
(`http_request`), per
[VLLM_RUNTIME_CONTRACT.md](VLLM_RUNTIME_CONTRACT.md) and
[VLLM_HTTP_TRANSPORT_ASSESSMENT.md](VLLM_HTTP_TRANSPORT_ASSESSMENT.md).

Current request construction:

1. `transmit_start = time.monotonic()` immediately before request-body
   serialization — the Area 4 request wall-time origin
   (`request_transmit_to_validated_response`).
2. JSON body: `model`, `messages` (system+user), `max_tokens`,
   `temperature`, `top_p`, `stream: False`. Compact separators, UTF-8.
3. `http_request` validates the loopback endpoint, resolves to loopback-only
   addresses, connects via `socket.create_connection` with a bounded connect
   timeout, sends fixed headers (`Host`, `Accept`, `Content-Type`,
   `Content-Length`, `Connection: close`) over `http.client.HTTPConnection`.
4. Whole-request deadline from `transmit_start`; every read enforces the
   remaining monotonic budget.
5. Response body read in bounded 64 KiB chunks with `max_response_bytes`
   (2,000,000 default); JSON decoded from the bounded buffer only.
6. Structural validation: `choices[0].message.content` string, `finish_reason`,
   `usage` (`prompt_tokens`, `completion_tokens`), optional
   `system_fingerprint`, served-model match.
7. Wall time recorded after all validation completes; every failure path
   records elapsed time at its failure point.
8. Evidence written to `request/<prompt_id>.json`
   (`llmgauge.vllm_request_evidence.v0`, `"streaming": False`) and fingerprinted
   through the request-evidence artifact hash.

The request wall-time definition is complete-response timing (serialization →
validated non-streaming response). This must remain conceptually stable under
any future streaming design: request start is unchanged, and the end boundary
becomes complete stream receipt + terminal validation.

## TTFT authority

`llmgauge.metric.v1.time_to_first_token` per
[RUNTIME_NEUTRAL_METRICS_FAILURE_TAXONOMY_CONTRACT.md](RUNTIME_NEUTRAL_METRICS_FAILURE_TAXONOMY_CONTRACT.md):

> seconds from the request start boundary above to availability of the first
> generated output token at the LLMGauge transport boundary. It requires a
> streaming or equivalent admitted observation that identifies that moment.

Required: monotonic timing; one request attempt; exact request-start
relationship; genuine generated-token boundary; no token ⇒ unavailable;
timeout before token ⇒ unavailable; missing evidence ⇒ unavailable; no derived
approximation. The neutral definition does not distinguish reasoning tokens
from final-answer tokens (see [Reasoning-content semantics](#reasoning-content-semantics)).

## vLLM streaming protocol evidence

All source findings are from the operator's installed vLLM environment:

- Environment: `/home/cheez/Projects/local-llm/vllm-env/` (Python 3.12
  virtualenv)
- Version: `vllm 0.27.1` (`vllm-0.27.1.dist-info`, `vllm.__version__`
  import probe, and `vllm-admission-evidence/version.json`)
- Source package:
  `/home/cheez/Projects/local-llm/vllm-env/lib/python3.12/site-packages/vllm/`
- Relevant files (installed source, not network copies):
  - `entrypoints/openai/chat_completion/serving.py`
    (`chat_completion_stream_generator`)
  - `entrypoints/openai/chat_completion/protocol.py`
    (`ChatCompletionRequest`, `ChatCompletionStreamResponse`,
    `ChatCompletionResponseStreamChoice`)
  - `entrypoints/openai/chat_completion/api_router.py` (SSE
    `StreamingResponse`, `text/event-stream`)
  - `entrypoints/openai/engine/protocol.py` (`StreamOptions`,
    `DeltaMessage`, `PerRequestTimingMetrics`)
  - `entrypoints/generate/base/serving.py`
    (`build_per_request_timing_metrics`)
  - `entrypoints/serve/utils/api_utils.py` (`should_include_usage`)
  - `v1/engine/output_processor.py`, `v1/engine/detokenizer.py`
    (`RequestOutputKind.DELTA`, delta text/token_ids)
  - `outputs.py` (`CompletionOutput`, `RequestOutput.add` merge semantics)

Version lineage: `return_token_ids` was verified absent in upstream v0.14.0 and
present in v0.15.1 (raw GitHub protocol source), and is present in installed
0.27.1. The operator's `vllm-admission-evidence/requirements.freeze.txt` pins
`vllm==0.27.1`. Field availability observed since 0.15.1 is not protocol
qualification for every `>= 0.15.1` runtime: the V1 implementation admits the
exact qualified vLLM 0.27.1 only, because detailed SSE token/event semantics
were inspected end-to-end against that runtime. Future versions require a
separately reviewed qualification before admission.

### `/v1/chat/completions` with `stream=true`

- `ChatCompletionRequest.stream: bool | None = False`. When true, the router
  returns `StreamingResponse(content=generator,
  media_type="text/event-stream")` (HTTP/1.1 chunked transfer, no gzip
  middleware in `api_server.py`).
- `stream_options` (`include_usage`, `continuous_usage_stats`) is validated to
  require `stream=true`.
- Sampling params select `RequestOutputKind.DELTA`: the engine emits
  incremental deltas (`output.text` = new decoded text since the last output;
  `output.token_ids` = new token IDs in this step) instead of a final-only
  aggregate.
- `system_fingerprint` is stamped only on terminal chunks (or the trailing
  usage chunk when `include_usage` is on).

### Exact SSE object sequence

1. **First chunk per choice**: `choices[0].delta = {role, content: ""}` —
   role-only, empty content, no logprobs, no finish_reason. Optionally
   carries vLLM-specific top-level `prompt_token_ids` (when
   `return_token_ids=true`) and `prompt_text` (when `return_prompt_text=true`).
   This event is **never** a generated-token boundary.
2. Optional echo chunk when `echo` / `continue_final_message` is set and the
   last conversation message belongs to the response role (LLMGauge does not
   use these options).
3. **Per-engine-step chunks** (see below for token mapping).
4. Finish chunk carrying `finish_reason` (+ `stop_reason`).
5. If `stream_options.include_usage=true`: final **usage-only chunk** with
   `choices=[]` and `usage` (prompt/completion/total tokens), optionally
   `metrics` (`PerRequestTimingMetrics`).
6. **Always** `data: [DONE]`, even after an error chunk.

Error handling: request-time errors before streaming return a normal JSON
`ErrorResponse`; mid-stream engine errors are emitted as
`data: {error-object}` followed by `data: [DONE]` (never a bare HTTP 500
mid-stream).

### First-event contents

The first event can contain **role only, with empty content**, plus optional
vLLM-specific `prompt_token_ids`/`prompt_text`. It cannot contain generated
text or generated token IDs. Empty delta chunks during chunked prefill are
suppressed by the serving loop (`if not delta_text and not output.token_ids
and not previous_num_tokens[i]: continue`), so an empty-content chunk before
any token is not emitted. A token that decodes to empty text (special/control
token) still produces a chunk with `token_ids` (when `return_token_ids=true`)
and empty `delta.content`; it is a token event, not a text event.

## SSE event anatomy

Each SSE event is a single `data:` line containing a JSON
`ChatCompletionStreamResponse`:

```json
{
  "id": "chatcmpl-...",
  "object": "chat.completion.chunk",
  "created": 1720000000,
  "model": "served-model",
  "choices": [{
    "index": 0,
    "delta": {"content": "Hello"},
    "logprobs": null,
    "finish_reason": null
  }]
}
```

With `return_token_ids=true`, the choice additionally carries
`token_ids: [<int>]` — the raw generated token IDs for that chunk. The delta
may instead carry `reasoning` (vLLM-specific field; renamed from
`reasoning_content` in this version family) or `tool_calls`.

## Token / chunk / content distinction

Central finding: **an SSE chunk is a transport event, not necessarily one
token.** The vLLM serving loop emits one chunk per engine `RequestOutput`
per choice, and an engine step can contain one or more token IDs:

- Normal decode, consumer keeping pace: one step ≈ one token ⇒ one chunk ≈
  one token. This is the common case, but it is **not guaranteed**.
- `RequestOutputCollector` (DELTA mode) **merges outputs when the producer
  outruns the consumer**: `CompletionOutput.text` is concatenated and
  `token_ids` extended, so one chunk can carry several tokens.
- Speculative decoding / multi-token prediction can put multiple `new_token_ids`
  in one engine step and therefore one chunk.
- A token that decodes to empty text yields a chunk with empty `delta.content`
  but non-empty `token_ids`.

Therefore:

| Observable | Is it a token boundary? |
|---|---|
| First HTTP byte / headers | No |
| First SSE frame | No (role-only) |
| First non-empty `delta.content` | **No** — a decoded text piece; can be empty for a real token, can coalesce several tokens, and (with a parser) may exclude control tokens |
| First non-empty `choices[0].token_ids` (`return_token_ids=true`) | **Yes** — raw backend token IDs, ordered, one chunk-boundary arrival |
| First `logprobs.content[]` entry (`logprobs=true`) | Per-token record in the same chunk, but requires engine logprob computation; secondary/corroborating |
| Backend-reported `metrics.time_to_first_token_ms` | Server-reported latency with a **different boundary** (engine-scheduled → first token); not the LLMGauge request-start boundary |

`delta.content` alone is a decoded text delta and is explicitly insufficient
for the neutral definition. The provable token boundary requires
`return_token_ids=true`.

### Multi-token chunk semantics

When a chunk carries several token IDs, the first element of `token_ids` is
the first generated token of that chunk, and the chunk arrival at the
LLMGauge transport boundary is the availability moment for that first token —
the chunk is received as one bounded unit and LLMGauge cannot observe
intra-chunk token timing. TTFT is therefore the elapsed time to arrival of
the **first chunk containing at least one generated token ID**. This is
honest transport-boundary timing: the first token became available at the
boundary when its chunk arrived. No per-token intra-chunk timestamp is
claimed.

## Reasoning-content semantics

- `DeltaMessage` has a vLLM-specific `reasoning` field. With a reasoning
  parser active and `include_reasoning=true` (the default), reasoning tokens
  are streamed as `delta.reasoning` before `delta.content`.
- With `return_token_ids=true`, reasoning tokens are also visible as raw
  token IDs in the same chunks; the first generated token of a reasoning
  model is a reasoning token.
- The current vLLM request evidence is text-only: `_extract_chat_text` reads
  only `message.content`, and the non-streaming adapter does not admit
  reasoning deltas at all. The accepted neutral TTFT definition says "first
  generated output token" without excluding reasoning tokens.
- **Resolved contract:** the first backend-generated token triggers neutral
  TTFT, including a reasoning token. The first final-answer content token
  triggers TTFT only when no earlier generated token occurred. The implemented
  rule and excluded event kinds are stated under
  [Resolved contract: reasoning tokens](#resolved-contract-reasoning-tokens).

## Logprobs / token identity

- `ChatCompletionRequest.logprobs` (`bool`, default false) plus
  `top_logprobs` (default `0`, i.e. sampled token only) or the vLLM extension
  `logprob_token_ids` (a fixed label set) enables `choices[0].logprobs`.
- `_create_chat_logprobs` emits one `ChatCompletionLogProbsContent` per token
  in the chunk, in order, in the **same** chunk as the text delta. Entries
  carry `token` (decoded text, or `token_id:{id}` with
  `return_tokens_as_token_ids`), `logprob`, `bytes`, and optional
  `top_logprobs`.
- Raw token IDs are **not** in standard OpenAI logprobs; they appear only via
  the vLLM extensions `return_token_ids` (per-chunk `token_ids` lists) or
  `return_tokens_as_token_ids` (logprob token strings).
- `return_token_ids=true` is the cheapest token-identity mechanism: it does
  not change sampling parameters or require logprob computation — it only
  adds serialization of token IDs the engine already has. Enabling
  `logprobs=true` changes engine logprob computation and is a material
  architectural cost; it is a corroborating option, not the primary signal.
- Both mechanisms are version-qualified vLLM extensions, not OpenAI-spec
  fields; the observation method must record the vLLM version and the exact
  request option used.

## Client observation mechanics

- `http.client` + `socket` on the existing loopback stack can read an SSE
  stream incrementally: `HTTPResponse.readline()` over a chunked
  transfer-encoding body returns lines as the server flushes them, and the
  existing monotonic deadline wrapper can re-arm the socket timeout between
  reads.
- The synthetic loopback experiment (`tmp/vllm-streaming-ttft-feasibility/`,
  ignored) proves: incremental per-event reads; monotonic per-event
  timestamps; raw-byte preservation; `[DONE]` detection; usage-only final
  chunk capture; finish-reason capture; bounded event/body size enforcement;
  fail-closed handling of malformed JSON, truncated streams, HTTP errors,
  timeout-before-token, and timeout-after-token; deterministic socket
  cleanup on every terminal path. 22/22 assertions pass.
- Synthetic SSE mechanics do **not** prove vLLM token semantics; those come
  from the primary-source analysis above.
- vLLM's server has no gzip middleware and streams over loopback; HTTP
  buffering is the normal chunked-transfer path. A TCP/proxy/compression
  layer between server and client could delay visibility — the loopback
  direct connection reduces but does not eliminate scheduling jitter. Event
  timing is observable at line/frame receipt; no per-token claim is made
  inside a chunk.

## Request-start boundary

The existing origin must be reused unchanged:

```python
transmit_start = time.monotonic()   # immediately before request serialization
```

This remains valid with `stream=true`: serialization, connection, headers,
request transmission, first event, token events, terminal validation, and
`[DONE]` all fall after it. TTFT and request wall time share this origin;
they remain separate metrics.

## Complete-response wall-time preservation

Future request wall time keeps its Area 4 meaning: request start → **complete
stream receipt + terminal validation**. Under streaming the completion point
is: `[DONE]` received (and, when requested, the usage-only final chunk
validated), assembled output structurally valid, finish reason and usage
extracted. TTFT is not subtracted and does not become the wall-time end.
The existing `request_transmit_to_validated_response` boundary label may
require a versioned observation-method qualifier, but its semantics do not
change.

## Raw stream evidence

A future streaming implementation must preserve at least as much evidence as
the non-streaming path:

- exact request JSON (already preserved in `request/*.json`);
- **raw SSE bytes or normalized exact event records** — new, and mandatory:
  a neutral TTFT needs authoritative preserved observation evidence, not just
  the final text;
- assembled generated text (existing raw output);
- backend metadata: finish reason, usage, optional `system_fingerprint`;
- terminal markers and error objects seen in the stream;
- the failed-attempt record when the stream fails (never replaced by a later
  success).

## Failure / timeout semantics

| Case | TTFT | Completion state |
|---|---|---|
| Connection failure before stream | unavailable | failed |
| HTTP error (4xx/5xx) | unavailable | failed |
| Timeout before first event | unavailable | timeout |
| Timeout after metadata, before token | unavailable | timeout |
| Timeout after first token | may remain available | timeout / partial |
| Malformed SSE before first token | unavailable | failed / malformed |
| Malformed SSE after first token | may remain available | failed / malformed / partial |
| Premature EOF before first token | unavailable | failed |
| Premature EOF after first token | may remain available | failed / partial |
| `[DONE]` without any token | unavailable | completed-empty / partial |
| Empty successful generation | unavailable | completed |
| Cancellation | no fabricated event | cancelled |
| Server error object mid-stream | per above (before/after first token) | failed |

A proven token followed by later failure preserves the TTFT value with a
non-completed completion state; partial stream success is never converted
into completed inference.

## Transport identity

Streaming is a deliberate extension of the accepted non-streaming contract,
not a silent reinterpretation. Implemented evidence records:

- `streaming: true` and
  `transport_mode: "openai_compatible_sse"`;
- the request options that produce token identity (`return_token_ids=true`)
  and their exact vLLM version qualification;
- the observation-method identity (`llmgauge.vllm_stream_evidence.v0`).

Canonical runtime evidence records the resolved streaming selection. Result,
request, stream, and Area 4 evidence must agree with it.

## Fingerprint / result implications

- vLLM results currently carry no run fingerprint when model SHA-256
  provenance is unavailable. Where the existing Area 4 fingerprint payload
  applies, request and stream evidence artifacts are included in its
  authoritative per-prompt artifact hashes.
- Streaming state and transport already use represented runtime/request/stream
  fields. No fingerprint schema or payload version changed; historical
  fingerprints remain valid.

## Comparison boundary

Current TTFT comparison discloses backend/runtime, transport observation
method/version, streaming state, workload identity, completion state, request
settings, and hardware evidence where represented. Matching
`llmgauge.metric.v1.time_to_first_token` IDs alone never implies equivalence;
transport and observation differences remain explicit, with no winner or
ranking.

## Security / privacy

- Loopback-only endpoint, no authentication, no arbitrary headers, no
  credentials — unchanged from the accepted transport.
- Bounded response size and bounded event size; no gzip; `Connection: close`.
- The stream artifact can multiply sensitive data: raw SSE events contain
  generated content (and, with `return_token_ids`, token IDs). It stays a
  **private source artifact**; the sanitizer must remain default-deny and must
  not project raw stream events into public exports. TTFT values may later be
  public-safe; stream content is not.
- No new server lifecycle, no model launches, no remote endpoints, no
  authentication, no concurrency.

## Performance / observer effect

- Streaming changes the backend path (DELTA output kind, per-token detokenizer
  deltas, SSE framing) and client behavior (incremental reads, per-event
  timestamps, raw-byte buffering). It is not performance-neutral by default;
  do not claim it is.
- `return_token_ids=true` adds per-chunk serialization of token ID lists but
  does not change sampling or engine logprob computation. Logprobs options do
  add engine work.
- Request wall time under streaming includes the same components plus stream
  transfer; the metric boundary is documented, not assumed equivalent to
  non-streaming wall time.
- Current evidence records `transport_mode: "openai_compatible_sse"` and the
  observation-method identity so timing differences remain attributable.

## Feasibility decision

**VLLM_STREAMING_TTFT = FEASIBLE AND IMPLEMENTED** for exactly qualified vLLM
0.27.1.

Evidence for each required element:

1. **Primary-source proof of token boundary** — `return_token_ids=true`
   yields `choices[0].token_ids` (raw generated token IDs) per chunk in
   installed vLLM 0.27.1 source; present since v0.15.x. ✓
2. **First token distinguishable from role/metadata/empty events** — first
   chunk is role-only with no `token_ids`; chunked-prefill empty chunks are
   suppressed; the first chunk with non-empty `token_ids` is the first
   generated-token boundary. ✓
3. **Host can timestamp incrementally** — proven by the synthetic loopback
   experiment (stdlib only). ✓
4. **Event evidence preservable** — raw SSE bytes / normalized event records
   as a contained artifact. ✓
5. **Request wall-time semantics intact** — same `transmit_start` origin;
   complete-stream receipt + terminal validation end boundary. ✓
6. **Malformed/failure handling fail-closed** — failure table above; no
   partial success presented as completion. ✓
7. **No material dependency required** — stdlib `http.client`/`socket`
   suffices; no new dependency needed. ✓
8. **Transport-mode identity representable** — `streaming`, transport method,
   and observation-method version fields. ✓
9. **Privacy/evidence boundaries tractable** — private stream artifact,
   default-deny sanitizer, no remote/auth/concurrency expansion. ✓

The reasoning-token contract is resolved below and no longer blocks the
implemented transport.

## Implemented acceptance gates

1. First generated-token boundary proven: the first chunk whose
   `choices[0].token_ids` is non-empty, with `return_token_ids=true`.
2. Role/metadata chunks (role-only first chunk, prompt_token_ids,
   prompt_text, usage-only chunk) can never trigger TTFT.
3. Empty events (empty `delta.content` with no `token_ids`) can never trigger
   TTFT.
4. Reasoning semantics explicitly resolved: the first backend-generated token,
   including a reasoning token, triggers neutral TTFT and the channel is
   recorded in evidence.
5. Token/logprob representation version-qualified (vLLM version +
   `return_token_ids`/`return_tokens_as_token_ids` + stream evidence schema
   version).
6. Monotonic per-event timestamps; TTFT = elapsed to the first token-bearing
   chunk.
7. Request-start boundary unchanged (`transmit_start` immediately before
   serialization).
8. Complete stream still validates: status, framing, JSON, choice/index,
   served model, finish reason, terminal marker, usage.
9. Request wall time remains complete-response timing; TTFT separate.
10. Exact output assembly from deltas (content; reasoning where admitted),
    byte-stable for synthetic fixtures.
11. Raw stream evidence preserved (raw bytes or exact normalized event
    records), not just final text.
12. Malformed SSE fails closed; error objects in stream classified.
13. Premature EOF handled per the failure table.
14. Timeout before first token ⇒ TTFT unavailable.
15. Timeout after first token can preserve TTFT with failed/partial state.
16. Synthetic fixtures cover coalesced/multi-token chunks and per-token
    `token_ids` lists.
17. Bounded event size and total stream size enforced.
18. No remote endpoints, authentication, arbitrary headers, or concurrency.
19. Transport mode persisted in evidence (`streaming`, method, options).
20. Comparison discloses streaming mode and observation-method version.
21. Historical non-streaming results remain valid; stream evidence is
    additive.
22. Public export does not leak raw stream events (default-deny).
23. No new material dependency without explicit approval.
24. Real-vLLM validation only under later human authorization.

## Implementation status

V1 is implemented and synthetically validated (no real vLLM in this
milestone):

- **Transport**: `src/llmgauge/runners/vllm_http.py::http_request_stream`
  reads bounded SSE events over the existing loopback stdlib stack
  (`http.client` + `socket`), enforcing per-line, per-event, total-body, and
  event-count bounds, a whole-request monotonic deadline, loopback-only
  validation, proxy bypass, no redirects, and deterministic connection
  cleanup. No new dependency.
- **Adapter**: `src/llmgauge/runners/vllm_external.py::run_chat_completion_stream`
  sends `stream=true`, `return_token_ids=true`, and
  `stream_options.include_usage=true`, assembles canonical final content from
  `delta.content` only (reasoning stays private stream evidence), and records
  the first-token channel (`reasoning` / `content` / `other_generated`).
- **Selection surface**: `--vllm-streaming-evidence` (CLI, config
  `runtime.vllm_streaming_evidence`, profile `vllm_streaming_evidence`);
  default remains non-streaming.
- **Version qualification**: V1 admits exactly the qualified vLLM 0.27.1
  runtime, because the detailed SSE token/event semantics were inspected
  end-to-end only against that version. `return_token_ids` field availability
  since 0.15.1 (accepted primary-source evidence) is historical evidence, not
  protocol qualification: older, newer, suffixed, and unknown versions fail
  cleanly with one unsupported-capability result; no automatic second
  non-streaming request. Future versions require a separately reviewed
  qualification before admission.
- **Stream evidence**: `request/<prompt>.stream.json`,
  `llmgauge.vllm_stream_evidence.v0`, private, with ordered per-event elapsed
  seconds, token counts, TTFT trigger marker, first-token channel, version
  qualification, and terminal state.
- **Neutral metric**: `llmgauge.metric.v1.time_to_first_token` in
  `runtime_neutral_metrics` with boundary
  `request_transmit_to_first_generated_token`, provenance
  `llmgauge_observed`, and contained evidence refs. The validator recomputes
  TTFT from preserved stream evidence.
- **Failure table** implemented per this document (see
  [Failure / timeout semantics](#failure--timeout-semantics)).
- **Privacy**: stream evidence, TTFT values, and reasoning text are private;
  public export strips them while keeping transport-mode disclosure.

### Resolved contract: reasoning tokens

`llmgauge.metric.v1.time_to_first_token` means elapsed time from the admitted
request-start boundary to the first backend-generated token exposed at the
LLMGauge transport boundary. Therefore the first reasoning token counts, the
first final-answer content token counts when no earlier generated token
occurred, and a generated token whose decoded text is empty counts when raw
token-ID evidence proves it. Role-only, metadata-only, usage-only,
finish-only, prompt-token-ID, empty-delta, `[DONE]`, HTTP-header, and
text-without-proven-token-identity events never count. This milestone does
not redefine TTFT as user-visible-final-answer latency; a distinct future
first-final-answer-token metric is separate.

## Related documents

- [VLLM_RUNTIME_CONTRACT.md](VLLM_RUNTIME_CONTRACT.md)
- [VLLM_HTTP_TRANSPORT_ASSESSMENT.md](VLLM_HTTP_TRANSPORT_ASSESSMENT.md)
- [VLLM_AREA4_EVIDENCE_MAPPING.md](VLLM_AREA4_EVIDENCE_MAPPING.md)
- [RUNTIME_NEUTRAL_METRICS_FAILURE_TAXONOMY_CONTRACT.md](RUNTIME_NEUTRAL_METRICS_FAILURE_TAXONOMY_CONTRACT.md)
- [LLAMACPP_TTFT_OBSERVATION_ARCHITECTURE.md](LLAMACPP_TTFT_OBSERVATION_ARCHITECTURE.md)
- [ARTIFACT_SCHEMAS.md](ARTIFACT_SCHEMAS.md)
