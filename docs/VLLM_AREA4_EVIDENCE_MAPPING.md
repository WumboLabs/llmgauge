# vLLM Area 4 Evidence Mapping

- Status: Accepted implementation record
- Scope: vLLM request evidence mapped into the existing Area 4 representation
- Related:
  - [VLLM_RUNTIME_CONTRACT.md](VLLM_RUNTIME_CONTRACT.md)
  - [RUNTIME_NEUTRAL_METRICS_FAILURE_TAXONOMY_CONTRACT.md](RUNTIME_NEUTRAL_METRICS_FAILURE_TAXONOMY_CONTRACT.md)
  - [VLLM_CROSS_RUNTIME_COMPARISON_METHODOLOGY.md](VLLM_CROSS_RUNTIME_COMPARISON_METHODOLOGY.md)
  - [ARTIFACT_SCHEMAS.md](ARTIFACT_SCHEMAS.md)

## Purpose

This record documents which currently observed vLLM facts honestly satisfy the
accepted Area 4 neutral metric definitions, and how the mapping is
implemented. It is the vLLM counterpart of the native llama.cpp Area 4 slices:
evidence is mapped only where the source boundary genuinely matches the
neutral definition; everything else stays native or deferred.

## Runtime ownership boundary

The vLLM backend remains:

- loopback-only;
- externally/operator-managed (LLMGauge does not start, stop, supervise,
  configure, or recover the server);
- sequential, text-only, with non-streaming as the default and streaming
  SSE evidence an explicit opt-in mode (`--vllm-streaming-evidence`).

Two evidence scopes stay separate and are never merged:

- **Server/model-admission scope**: version, readiness, served model,
  fingerprints. These are API observations only.
- **Per-request scope**: request, response/failure, wall time, usage, finish
  reason, request evidence artifacts.

## Admission table

| Metric | Current source | Boundary match? | Provenance | Admission | Why |
|---|---|---|---|---|---|
| Request wall time | `request_wall_time_seconds` in `request/*.json` | Yes (after timer correction) | `llmgauge_observed` | **ADMITTED** | Monotonic timer spans serialization through receipt and structural validation of the complete response; failure paths preserve honest elapsed intervals. |
| TTFT | `request/*.stream.json`; `time_to_first_token_seconds` in `request/*.json` | Yes (streaming evidence mode) | `llmgauge_observed` | **ADMITTED** (opt-in) | Streaming evidence mode uses the qualified vLLM `return_token_ids=true` SSE transport; TTFT = request start → first generated token ID at the LLMGauge transport boundary. Requires observed vLLM exactly 0.27.1 (V1 qualification); all other versions fail cleanly. Non-streaming requests have no TTFT. |
| Model load time | None | No | — | **UNAVAILABLE** | Operator owns server lifecycle and model admission; request evidence cannot infer load duration. |
| Prefill throughput | None | No | — | **UNAVAILABLE** | Backend `prompt_tokens` exist but no prefill-phase duration is observed; `prompt_tokens / wall_time` is not prefill throughput. |
| Decode generation throughput | `end_to_end_completion_tps` | No | `calculated` (native) | **NATIVE ONLY** | End-to-end completion TPS is not decode-only throughput and is not mapped. |
| Request-window peak VRAM | `request/*.json` evidence; `vram/<prompt>.samples.json` | Yes (request-window boundary) | `calculated` | **ADMITTED** | Bounded concurrent NVIDIA telemetry sampler observes absolute device-used memory during the evaluation request window. The boundary (`request_window_peak_vram_observation`) is distinct from the native llama.cpp process-window boundary. Sampler failure never affects the request outcome. |
| Steady-state VRAM | None | No | — | **DEFERRED** | API readiness does not prove post-load, post-warmup state; no warm-state lifecycle evidence exists. |
| Execution placement | None | No | — | **UNAVAILABLE** | The vLLM API exposes no placement; requested device/readiness never becomes observed placement. |

## Request wall time

The adapter measured wall time from immediately before `http_request` to
response-body receipt, which excluded request serialization and response
validation. The timer boundary was corrected so that:

- the timer starts immediately before request-body serialization
  (`transmit_start`);
- every failure path records the elapsed monotonic time at its failure point;
- the successful path records elapsed time after all structural validation
  (JSON decode, text/usage extraction, fingerprint extraction, served-model
  check) completes.

This matches the accepted Area 4 boundary
(`request_transmit_to_validated_response`) and the vLLM runtime contract's
"receipt and validation" wording. The native `request_wall_time_seconds` field
keeps its name and location; its measured window is now the contracted one.

The Area 4 record is:

```json
{
  "metric_id": "llmgauge.metric.v1.request_wall_time",
  "native_metric_id": "request_wall_time_seconds",
  "value": 2.43,
  "unit": "s",
  "availability": "available",
  "provenance": "llmgauge_observed",
  "boundary": "request_transmit_to_validated_response",
  "equivalence": "unproven",
  "evidence_refs": ["request/p1.json#/request_wall_time_seconds"]
}
```

Provenance is `llmgauge_observed` because LLMGauge itself measures monotonic
elapsed time. Requests that were never transmitted (empty prompt, endpoint
validation failure) have no honest request boundary and map to `unavailable`,
never to a fabricated value.

Failure behavior: a failed response, timeout, or cancellation retains its
honest elapsed wall time with `completion_state=failed` or `timeout`; that is
not successful-request latency. The adapter has no retry behavior, so every
attempt is a single measurement with no retry ancestry.

## Token metrics

Backend `prompt_tokens`, `completion_tokens`, `usage_complete`, and
`end_to_end_completion_tps` remain native evidence under their existing
semantics. `end_to_end_completion_tps` is completion tokens divided by request
wall time and is explicitly not decode-only throughput; it is never mapped to
`llmgauge.metric.v1.decode_generation_throughput`.

## TTFT

Non-streaming chat completions return the complete response at once and have
no first-generated-token event, so TTFT is absent for the non-streaming
default. Under explicit streaming evidence mode, the qualified vLLM SSE
transport (`stream=true`, `return_token_ids=true`,
`stream_options.include_usage=true`) exposes raw generated token IDs, and
`llmgauge.metric.v1.time_to_first_token` is **ADMITTED**:

- boundary: `request_transmit_to_first_generated_token` (same monotonic
  request start as request wall time);
- provenance: `llmgauge_observed`;
- the first event whose `token_ids` array contains at least one generated
  token ID establishes TTFT; the first reasoning token counts (human
  contract), and an empty-decoded token counts when token-ID evidence proves
  it;
- TTFT is recomputable from the preserved private stream evidence artifact
  (`llmgauge.vllm_stream_evidence.v0`, `request/<prompt>.stream.json`), and
  the Area 4 validator recomputes it;
- no token stream, malformed token IDs, or failure before the first token ⇒
  TTFT unavailable; a proven token followed by failure/timeout may retain
  TTFT with a non-completed completion state;
- version-qualified: observed vLLM exactly 0.27.1 (V1 qualification); no TTFT
  is guessed for older, newer, or unknown implementations, and there is no
  automatic fallback to a second non-streaming request.

## VRAM

External vLLM requests now carry request-window peak VRAM evidence:
`llmgauge.metric.v1.peak_vram` records are calculated from a preserved
per-request sample artifact (`vram/<prompt>.samples.json`, schema
`llmgauge.vram.samples.v0`) captured by a bounded concurrent NVIDIA telemetry
sampler that runs only while the evaluation request is in flight.

The observation window is explicit and request-owned:

1. the sampler starts immediately before the request attempt and takes an
   initial probe outside the request wall timer;
2. the request executes (serialization, transmission, server work, response
   receipt, validation) under its own `request_wall_time_seconds` timer;
3. on every terminal path (success, HTTP error, malformed response, timeout,
   transport failure) the sampler stops, takes a final probe, and joins;
4. a sample artifact is preserved only when the request was transmitted.

Request wall time is never measured through the telemetry probe: the two
observations are independent and the telemetry window has its own boundary
(`request_window_peak_vram_observation`), distinct from the native llama.cpp
process-window boundary. The value is the maximum absolute device-used memory
per device; it is not server/model footprint, baseline delta, or a
cross-device sum. `nvidia-smi` absence, timeout, or failure makes the metric
`unavailable` and never changes the request outcome. Sampled peak is not the
guaranteed instantaneous physical maximum. The sampler adds no server
lifecycle operation; the server existed before the request and may continue
after it.

## Placement

The vLLM API exposes no execution placement. Readiness success, a completed
request, GPU availability, or the requested served model never establish
placement, so `execution_placement` stays `{requested: unknown, observed:
unknown}` and the validator rejects any other value for vLLM.

## Cache / warmth

`server_state=ready` means only that the readiness endpoint succeeded and the
requested model was listed. It is not warmth, cache population, or lifecycle
state, so `workload.cache_state` remains `unknown` and no warm/cold label is
inferred.

## Representation

The mapping uses the existing `llmgauge.runtime_neutral_metrics.v1` and
`llmgauge.failure_taxonomy.v1` top-level objects; no new top-level schema or
vLLM-specific neutral metric IDs were introduced. Measurement IDs use the
`vllm-request-{index}` form; execution references use the same `results/{index}`
form as llama.cpp.

The failure taxonomy maps vLLM failure classes to the existing closed
categories:

| vLLM failure class | Taxonomy category |
|---|---|
| `endpoint_unavailable` | `endpoint_failure` |
| `connect_failed` | `endpoint_failure` |
| `request_timeout` | `endpoint_failure` |
| `server_request_error` | `endpoint_failure` |
| `readiness_failure` | `endpoint_failure` |
| `malformed_response` | `malformed_response` |
| `served_model_mismatch` | `runtime_environment_failure` |
| anything else | `unclassified_unknown` |

The classification cites `request/*.json#/failure_class` and never replaces
the native failure detail.

## Fingerprint

vLLM results already carry no run fingerprint when model SHA-256 provenance is
unavailable (the served-model path has no GGUF/directory-model hash), and that
behavior is unchanged. When Area 4 vLLM evidence is present, the existing
fingerprint logic hashes the contained `request/*.json` artifacts as the
authoritative per-prompt evidence; no new fingerprint version was introduced.
Historical fingerprints remain valid.

## Validation

The Area 4 validator now dispatches by backend:

- llama.cpp keeps its existing validation unchanged;
- vLLM results are validated against the preserved `request/*.json` evidence:
  finite non-negative wall time, expected metric identity, boundary,
  provenance, completion state, exact evidence reference, and value equality
  with the native field. Peak-VRAM records are validated against preserved
  `vram/*.samples.json`. For streaming evidence, the validator recomputes
  TTFT from `request/<prompt>.stream.json`: transport/observation-method
  identity, version qualification, `return_token_ids`, first token-bearing
  event, elapsed equality, closed first-token channel vocabulary, no earlier
  token event, and no TTFT for no-token or non-streaming evidence.
  Readiness/`unknown` placement is enforced.

Historical vLLM results without Area 4 evidence remain valid; llama.cpp Area 4
evidence is unchanged.

## Reporting and comparison

The single-run report shows the neutral vLLM wall-time record under
"Runtime-neutral evidence" with provenance, boundary, and completion state,
and keeps backend-native token/throughput evidence separate. The comparison
report shows request wall time with backend and boundary columns and does not
mark values equivalent; a llama.cpp process-window record and a vLLM
request-window record share a metric identity but have different sampling
boundaries, which is disclosed rather than normalized.

## Public export / privacy

No new sensitive fields are introduced. Request evidence files already undergo
endpoint-identity sanitization; the Area 4 objects carry only metric values,
contained relative evidence references, and closed vocabulary states. Export
sanitization rules remain at least as restrictive as before.

## Compatibility

- Historical vLLM results without Area 4 remain valid.
- Historical non-streaming vLLM results remain valid and unchanged; stream
  evidence and TTFT are additive.
- llama.cpp Area 4 evidence (wall time, peak VRAM, timing/placement, failure
  taxonomy) is unchanged.
- vLLM native fields (`request_wall_time_seconds`, `end_to_end_completion_tps`,
  token counts, fingerprints) keep their meanings.
- Multi-turn transcript, Agent Harness, and external-benchmark results remain
  unsupported for Area 4 evidence.

## Outcome

This record documents the honest Area 4 mapping for the vLLM backend:
`llmgauge.metric.v1.request_wall_time` for transmitted requests,
request-window peak VRAM, and — under explicit streaming evidence mode —
`llmgauge.metric.v1.time_to_first_token` with recomputable preserved stream
evidence. Everything else is preserved as native or deferred. No claim is made
that vLLM request wall time is equivalent to llama.cpp process wall time, that
TTFT is equivalent across runtimes, that API readiness implies warmth, that a
completed request implies accelerator placement, or that end-to-end completion
TPS is decode throughput.
