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
- non-streaming, sequential, text-only.

Two evidence scopes stay separate and are never merged:

- **Server/model-admission scope**: version, readiness, served model,
  fingerprints. These are API observations only.
- **Per-request scope**: request, response/failure, wall time, usage, finish
  reason, request evidence artifacts.

## Admission table

| Metric | Current source | Boundary match? | Provenance | Admission | Why |
|---|---|---|---|---|---|
| Request wall time | `request_wall_time_seconds` in `request/*.json` | Yes (after timer correction) | `llmgauge_observed` | **ADMITTED** | Monotonic timer spans serialization through receipt and structural validation of the complete response; failure paths preserve honest elapsed intervals. |
| TTFT | None | No | — | **DEFERRED** | Non-streaming transport exposes no first-token boundary. |
| Model load time | None | No | — | **UNAVAILABLE** | Operator owns server lifecycle and model admission; request evidence cannot infer load duration. |
| Prefill throughput | None | No | — | **UNAVAILABLE** | Backend `prompt_tokens` exist but no prefill-phase duration is observed; `prompt_tokens / wall_time` is not prefill throughput. |
| Decode generation throughput | `end_to_end_completion_tps` | No | `calculated` (native) | **NATIVE ONLY** | End-to-end completion TPS is not decode-only throughput and is not mapped. |
| Request-window peak VRAM | None | — | — | **DEFERRED** | No vLLM VRAM sampler exists; adding one is a separate telemetry milestone. |
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

Non-streaming chat completions return the complete response at once. There is
no first-generated-token event at the LLMGauge transport boundary, so
`llmgauge.metric.v1.time_to_first_token` is **DEFERRED** under this adapter.
No value is derived from wall time, completion tokens, server timing, first
JSON byte, or connection time.

## VRAM

The current vLLM path collects no `nvidia-smi` samples. The llama.cpp sampler
is coupled to the process-per-request lifecycle and is not reused. Admitted
request-window peak VRAM would require a concurrent telemetry sampler with an
explicit request-owned sampling window, failure/timeout cleanup, and no server
lifecycle involvement; that is deferred to a separate milestone. The
`vram`/`vram_samples_path` fields stay absent, and no
`llmgauge.metric.v1.peak_vram` record is emitted for vLLM.

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
  with the native field. Peak-VRAM records are rejected for vLLM in this
  slice (no sampler). Readiness/`unknown` placement is enforced.

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
- llama.cpp Area 4 evidence (wall time, peak VRAM, timing/placement, failure
  taxonomy) is unchanged.
- vLLM native fields (`request_wall_time_seconds`, `end_to_end_completion_tps`,
  token counts, fingerprints) keep their meanings.
- Multi-turn transcript, Agent Harness, and external-benchmark results remain
  unsupported for Area 4 evidence.

## Outcome

This milestone implements the smallest honest Area 4 mapping for the vLLM
backend: `llmgauge.metric.v1.request_wall_time` for transmitted requests, with
everything else preserved as native or deferred. No claim is made that vLLM
request wall time is equivalent to llama.cpp process wall time, that API
readiness implies warmth, that a completed request implies accelerator
placement, or that end-to-end completion TPS is decode throughput.
