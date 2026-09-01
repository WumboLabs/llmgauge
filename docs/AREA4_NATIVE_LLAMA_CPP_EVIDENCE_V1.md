# Area 4 native llama.cpp evidence v1

This addendum fixes the persisted interface for the first implemented Area 4
slice. It supplements the accepted
[Runtime-neutral Metrics and Expanded Failure Taxonomy Contract](RUNTIME_NEUTRAL_METRICS_FAILURE_TAXONOMY_CONTRACT.md);
it does not broaden that contract.

## Scope

Only ordinary native single-turn `llama.cpp` results create this evidence. One
`kind: measured` measurement is emitted for each `results` entry. There are no
warmups, retries, transcripts, vLLM records, comparisons, or exporter changes
in this slice.

The optional top-level objects are:

```yaml
runtime_neutral_metrics:
  schema_version: llmgauge.runtime_neutral_metrics.v1
  measurements: []
failure_taxonomy:
  schema_version: llmgauge.failure_taxonomy.v1
  observations: []
  primary_by_execution: []
```

Their absence remains valid for historical results.

## Execution and evidence references

For prompt-result index `N`, `execution_ref` is `results/N`. Its one measurement
has `measurement_id: native-single-turn-N` and `attempt_id: attempt-0`; both
are unique only within their owning result/execution respectively. The attempt
sequence is `0`, and `retry_of_attempt_id` is `null`.

The runner writes a contained evidence artifact at
`native/<prompt-id-with-slashes-replaced>.execution.json`, schema
`llmgauge.native_llama_cpp_execution_evidence.v1`. A prompt result references
it through `native_execution_evidence_path`. Metric and failure references use
that relative artifact plus a JSON-pointer fragment, for example
`native/prompt.execution.json#/request_wall_time_seconds`. References never
contain command arguments, absolute paths, or raw output.

The artifact records the LLMGauge-observed monotonic interval beginning
immediately before native process creation and ending after `communicate()` has
received its terminal output. It records `request_wall_time_seconds` only when
that finite non-negative interval was captured. This is the admitted native
single-turn request boundary: process launch through terminal output receipt
and exit-status observation. It does not establish TTFT, prefill, decode, load,
VRAM, or cross-runtime equivalence.

Each measurement records that boundary as
`request_transmit_to_validated_response`, `unit: s`,
`provenance: llmgauge_observed`, and `equivalence: unproven` when available.
When capture is unavailable, `value` is `null`, `availability` is
`unavailable`, `provenance` is `unavailable`, and `equivalence` is
`unavailable`. No zero replacement is allowed. The workload is the exact
single-turn prompt identity plus suite, generation limit, batching, unknown
cache state, and references to requested runtime settings. Requested execution
placement remains `unknown` because `--n-gpu-layers` is not observation.

## Backend-native llama.cpp timing and observed placement

The same native artifact may also preserve backend-owned diagnostic facts
parsed only from llama.cpp-prefixed lines
(`llama_perf_context_print:` / `llama_print_timings:` for timing;
`llm_load_tensors:` offload counts for placement). Unprefixed model text is
ignored. Conflicting duplicate values leave the field absent. Missing values
are null, never zero.

Preserved timing fields, when present: `load_time_seconds`,
`prompt_eval_time_seconds`, `prompt_eval_token_count`, `prompt_eval_tps`,
`eval_time_seconds`, `eval_token_count`, `generation_tps`,
`total_time_seconds`. These remain backend-native. They are not mapped to
`llmgauge.metric.v1.model_load_time`, `prefill_throughput`,
`decode_generation_throughput`, or `time_to_first_token`. TTFT stays
unavailable on the non-streaming native CLI transport.

Observed placement uses only the `offloaded N/M layers to GPU` diagnostic:
`cpu_only` when N is 0 and M is positive; `hybrid_accelerator_cpu` when
0 < N < M; `unavailable` when no supported line exists; `unknown` when N = M
or the counts are otherwise insufficient. N/N does not prove
`full_accelerator` because embeddings, output, or other execution may remain
CPU-resident. Native layer counts may be copied onto `execution_placement`
without changing that conservative observed state.


## Peak VRAM evidence

When a prompt captured VRAM samples, the runner additionally persists
`vram/<prompt-id-with-slashes-replaced>.samples.json`
(`llmgauge.vram.samples.v0`) and the measurement carries one extra metric
record per observed device (`gpu_index` plus `gpu_name`):
`llmgauge.metric.v1.peak_vram`. The value is the maximum absolute used memory
in `MiB` among that device's valid samples inside the sampling window that
spans process launch to post-completion capture; it is never a baseline delta,
a cross-device aggregate, or a per-device total. `provenance` is `calculated`
with `calculation_semantics: llmgauge.area4.peak_used_mib_by_device.v1`,
`sampling_interval` is `unknown`, `equivalence` is `unproven`, and
`evidence_refs` cite the contained samples artifact. Samples are polled at
an operator-chosen interval; timestamps stay in the cited artifact and the
neutral record stores only the count and device scope. A persisted samples
artifact containing no valid samples yields one record with
`availability: unavailable`, `provenance: unavailable`, `value: null`,
`device_scope: null`, and `sample_count: 0`; zero is never substituted.
When capture was not attempted, or no sample artifact was persisted, no
peak VRAM record exists. Validators recompute the expected records from
the persisted samples artifact and reject any divergence. This record does
not establish cross-runtime VRAM equivalence, placement observation, or
steady-state behavior.

## Native classification evidence

The native artifact has a structured `failure` object only for a non-completed
attempt. It contains `exit_status`, `timed_out`, optional bounded
`launch_error: process_launch_failed`, and optional `phase` and `oom` facts.
`phase` is emitted only when a llama.cpp component marker identifies
`model_weight_load` or `kv_cache`; `oom` is emitted only when a bounded OOM
marker occurs in the same native diagnostic. The raw stdout and stderr remain
the authoritative preserved artifacts.

The derived classifier emits one observation for each failed execution:

- `model_weight_load_oom` requires `phase: model_weight_load` and `oom: true`.
- `kv_cache_oom` requires `phase: kv_cache` and `oom: true`.
- `runtime_environment_failure` requires `launch_error: process_launch_failed`.
- `unclassified_unknown` covers every other preserved native failure fact.

The first two specific categories take precedence over the generic categories.
These records are LLMGauge-derived classifications, not authority over the
source diagnostics. Completed executions have no observation and a
`primary_by_execution` record with `primary_observation_id: null` and
`state: none`. Failed executions have one primary observation and
`state: classified`.

## Fingerprints

Existing `llmgauge.run_fingerprint.v0` values continue to use the unchanged
v0 payload and verify unchanged. Results that represent either Area 4 object
use `llmgauge.run_fingerprint.v1` and
`llmgauge.run_fingerprint_payload.v1`. The v1 payload retains all v0 evidence,
adds canonical JSON for both Area 4 top-level objects, and adds SHA-256 hashes
for every referenced native execution artifact. It does not hash
`llmgauge-result.json`, avoiding a self-referential fingerprint.

## Current llama-cli diagnostic prefix qualification (v1 addendum)

This section qualifies two diagnostic forms emitted by the current
`llama-cli` runtime family (inspected build 10449 / commit `0d9ceae1e`,
source tree `llama.cpp-sm120-upgrade`). It records a contract decision only.
No parser or capture path is implemented here, and no existing provenance
identity is redefined.

### `load_tensors:` offload line — placement

Producer: `llama_model_base::load_tensors`, `src/llama-model.cpp`, the
`offloaded %d/%d layers to GPU` `LLAMA_LOG_INFO`. The prefix is `__func__`.
This is the same function previously named `llm_load_tensors`; the historical
`llm_load_tensors:` prefix and the current `load_tensors:` prefix are one
producer renamed (upstream commit `994118a18`, 2026-05-04). The reported
formula is unchanged: `N = min(n_gpu_layers, n_layer_all + 1)` and
`M = n_layer_all + 1`, where `n_layer_all` is the GGUF `block_count` and the
`+ 1` is the logical output layer.

`N`/`M` count logical model layers (repeating transformer layers plus the
output layer). They are not tensor counts, graph-node counts, or a
backend-specific subset. The input/embedding layer is always assigned to the
CPU and is excluded from `M`. The line is emitted only when
`llama_supports_gpu_offload()` is true, once per model load.

`N` reflects the requested `--n-gpu-layers` clamped to model capacity; it is
not proof that buffer allocation stayed on the accelerator, because the GPU
buffer-type list carries a CPU fallback and allocation may silently land on
CPU. This requested-versus-effective caveat is identical to the historical
`llm_load_tensors:` diagnostic and does not change the classification rules.

Decision: `CURRENT_LOAD_TENSORS_PLACEMENT = ADMIT_EXISTING_SEMANTICS`. The
current prefix is semantically equivalent to the already-supported historical
placement diagnostic for every classification LLMGauge emits:

- `N = 0` with `M > 0` → `cpu_only` (every layer, including output, is
  assigned to the CPU device).
- `0 < N < M` → `hybrid_accelerator_cpu`.
- `N = M` → `unknown`. `N/N` still does not prove `full_accelerator`: the
  always-CPU input layer, the CPU buffer fallback, and possible non-layer
  CPU execution remain.
- no supported line → `unavailable`.

Admission is conditional on provenance honesty: the persisted
`placement_source` must record the actual prefix observed
(`load_tensors` versus `llm_load_tensors`) so the runtime family that
produced the evidence stays distinguishable. Multiple GPUs do not change the
classification: `N`/`M` are model-wide layer counts and the split across
devices is orthogonal to the `cpu_only` / `hybrid` / `unknown` decision. If
conflicting `offloaded N/M` lines appear in one captured stream (for example
multiple model loads), the existing conflict rule applies and the field is
left absent.

### `slot print_timing:` lines — timing

Producer: `server_slot::print_timings`, `tools/server/server-context.cpp`,
emitted through the `SLT_INF` macro. The `print_timing` prefix is `%12.*s` of
`__func__` (`print_timings`, 13 characters) truncated to 12. `llama-cli`
reaches this code because it is a client over an embedded
OpenAI-compatible server; each prompt is one `/v1/chat/completions` request
onto a slot.

These lines are server-slot request accounting, not `libllama`
context-level performance counters. They are not equivalent to
`llama_perf_context_print:` / `llama_print_timings:` and must not be merged
into those provenance identities. Material differences proven from source:

- The `print_timing` prefix is shared by three functions: the request-final
  `print_timings()` block, the `print_timings_pp()` prompt-progress line
  (emitted only when prompt time exceeds 3 s), and the `print_timings_tg()`
  generation-progress line (emitted only when `n_gen >= 100`). A prefix match
  alone cannot separate them; only the request-final block carries the
  `prompt eval time` / `eval time` / `total time` field text.
- Slot counters reset per request: `stats = {}` runs in `reset()` on slot
  release, and `n_gen` is zeroed when the prompt completes. Repeated requests
  on one slot report independent prompt/gen counts (confirmed by direct
  runs).
- `prompt eval time` token count is `n_prompt_processed`, which excludes
  KV-cache-reused prompt tokens (`n_prompt_cached`). This differs from
  `llama_perf` `n_p_eval`, which has no cache concept.
- `eval time` displays `n_gen` tokens but computes ms-per-token and tokens
  per second over `n_gen - 1` decode steps (the first token is "free" from
  the prompt logits). The displayed count and the rate denominator differ by
  one, unlike `llama_perf` `eval time`, whose count and rate share `n_eval`.
- `total time` is `t_prompt_ms + t_gen_ms`, i.e. prompt-start through last
  generated token. It excludes model load and any queue/HTTP/tokenization
  time before the slot began processing. This is a narrower boundary than
  the existing `total_time_seconds`, which for `llama_perf` spans from
  context creation.
- `graphs reused` is read from `llama_perf_context(ctx_tgt).n_reused`, a
  server-global cumulative counter that the server never resets. It is not
  request-local (confirmed monotonic across turns in direct runs).
- Under continuous batching (`--parallel > 1`) a slot's wall-clock interval
  includes co-resident slots' compute between its own batches, so per-slot
  timings are not isolated. Only `--parallel 1` single-turn yields a clean
  request-local boundary.
- Sampling time is inside the slot prompt/gen wall intervals; speculative
  decoding adds a separate `draft acceptance` line and changes the
  step/token relationship.

Decision: `SLOT_PRINT_TIMING = PARTIAL_ADMISSION`. Only the request-final
block, under `--parallel 1` single-turn, is trustworthy, and only as a new
distinct source identity (`slot_print_timing`). It must never populate the
existing `llama_perf`-derived native timing fields, because the meanings
differ. Per-field status:

- `prompt_eval_time_seconds`: admitted as distinct (prompt-start to first
  token; excludes load and queue).
- `prompt_eval_token_count`: admitted as distinct, meaning non-cached
  processed tokens only.
- `prompt_eval_tps`: admitted as distinct.
- `eval_time_seconds`: admitted as distinct (generation wall time).
- `eval_token_count`: admitted as distinct, with the `n_gen` versus
  `n_gen - 1` denominator caveat recorded.
- `generation_tps`: admitted as distinct (over decode steps).
- `total_time_seconds`: rejected. Boundary excludes load and pre-slot queue;
  not the existing total meaning.
- `load_time_seconds`: rejected. No load line is emitted by this source.
- `graphs reused`: rejected as evidence. Server-global, not request-local.
- progress lines (`print_timings_pp` / `print_timings_tg`): rejected. Prefix
  collision and non-final partial values.

Unavailable stays unavailable; missing is null, never zero. The compact
stdout UI trailer remains generic throughput evidence only and is not
relabeled.

### Logging requirement (identified, not enabled)

`slot print_timing:` requires verbosity >= 3 (`LOG_INF` maps directly to
`LOG_LEVEL_INFO`). `load_tensors:` requires verbosity >= 4 (libllama
`LLAMA_LOG_INFO` maps to `LOG_LEVEL_TRACE` through
`common_log_default_callback`). A future capture milestone would need
verbosity 4 for placement and only 3 for timing. Captured lines carry a
default timestamp prefix and may contain absolute model paths; any selective
capture must strip timestamps, avoid retaining unrelated verbose output,
preserve command/runtime provenance, and keep private paths out of public
artifacts. No logging policy is enabled by this contract.

Implementation status (capture milestone): the capture milestone admitted by
this addendum is implemented. For the exact qualified runtime only, LLMGauge
invokes `llama-cli` with `--verbosity 4` (the narrowest deterministic control
covering both sources), records the effective verbosity in
`runtime-command.json` and result runtime provenance, parses current-prefix
evidence from stderr only, and on successful runs persists only admitted
diagnostic lines plus warning/error output to `logs/` instead of the full
verbosity-4 trace. Failed runs retain the full stderr for diagnosis. This
note records enablement; it does not alter any decision above.
