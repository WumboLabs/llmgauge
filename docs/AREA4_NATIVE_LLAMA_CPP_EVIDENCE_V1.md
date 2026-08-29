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
