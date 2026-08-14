# Runtime-neutral Metrics and Expanded Failure Taxonomy Contract

## Status and authority

This is the accepted Area 4 implementation contract for Full Model Testing. It
is design only: it adds no collector, runner, transport, result serializer,
validator, comparison, reporter, exporter, runtime, or execution behavior.

It refines the runtime-neutral-metrics and expanded-failure-taxonomy prerequisites
in [Full Model Testing Capability Architecture](FULL_MODEL_TESTING_CAPABILITY_ARCHITECTURE.md).
[Result Schema v0](RESULT_SCHEMA_V0.md), [Artifact Schemas](ARTIFACT_SCHEMAS.md),
and [Result Validation v0](RESULT_VALIDATION_V0.md) remain the authority for
current artifacts until a separately admitted implementation updates them.
Historical `llmgauge.result.v0` directories remain valid. Nothing here
renames, backfills, or reinterprets their fields.

Runtime, transport, model, quantization, hardware, platform, requested settings,
and observed settings remain separate provenance layers. Requested behavior is
not observation. Missing evidence is unknown or unavailable, never inferred
from filenames, flags, or expected backend behavior.

## Future additive representation

The first implementation adds two optional top-level objects to a future
`llmgauge.result.v0` line. Their absence is valid for every historical result.
When finalized, they are immutable canonical run records owned by that result.
A future fingerprint payload version includes their canonical JSON and referenced
authoritative artifact hashes, pinning those recorded bytes and their owning run
identity. Fingerprint inclusion does not make every represented fact source
authority, prove a diagnosis, or replace referenced native/source evidence. It
does not alter historical v0 fingerprint payloads or recompute historical
fingerprints.

```json
{
  "runtime_neutral_metrics": {
    "schema_version": "llmgauge.runtime_neutral_metrics.v1",
    "measurements": []
  },
  "failure_taxonomy": {
    "schema_version": "llmgauge.failure_taxonomy.v1",
    "observations": [],
    "primary_by_execution": []
  }
}
```

### Finalization, provenance, and source authority

Finalization establishes the canonical bytes of an LLMGauge-owned result record;
it is separate from authority over each fact represented in that record.
Per-metric authority remains its `provenance`: LLMGauge observes only
`llmgauge_observed` facts, `backend_reported` facts remain backend-owned,
`calculated` values remain LLMGauge-derived calculations over cited evidence,
and `unavailable` records establish no observed fact. `failure_taxonomy` is a
deterministic LLMGauge-derived classification layer. Its cited source/native exit
status, signal, timeout, backend evidence, transcript terminal state, and Agent
Harness terminal, tool, verifier, and recovery facts retain authority under
their existing contracts. Classification can cite but cannot replace or upgrade
those facts; a fingerprint covering it does not convert it into source truth.

Later classifier logic MUST NOT silently reclassify an already-finalized result
in place. Any intentional reclassification requires an explicitly identified
new finalized result record and fingerprint under a separately admitted
compatibility decision.

A `measurement` is one execution attempt, not an aggregate. Its required
identity is `measurement_id` (unique in the result), `execution_ref` (a bounded
reference to the prompt result, transcript attempt, or admitted imported source
event), `attempt_id`, and non-negative `attempt_sequence`. It has:

- `kind`: closed `warmup` or `measured`;
- `retry_of_attempt_id`: nullable backward reference; no fallback is implied by
  its presence;
- `completion_state`: closed `completed`, `partial`, `failed`, `timeout`,
  `cancelled`, or `unknown`;
- `workload`: exact evaluation/workload identity and version, request/input-form
  identity, generation limits, batching identity, tokenizer identity and version
  when token metrics are present, template identity and version when relevant,
  cache state (`cold`, `warm`, `unknown`), and requested/observed runtime-setting
  references;
- `execution_placement` described below; and
- `metrics`, an array of metric records.

A metric record has the closed structure:

```json
{
  "metric_id": "llmgauge.metric.v1.request_wall_time",
  "native_metric_id": "request_wall_time_seconds",
  "value": 1.25,
  "unit": "s",
  "availability": "available",
  "provenance": "llmgauge_observed",
  "boundary": "request_transmit_to_validated_response",
  "equivalence": "unproven",
  "evidence_refs": ["request/p1.json#request_wall_time_seconds"]
}
```

`metric_id` is the neutral identity; `native_metric_id` is nullable and names
only the preserved backend-native field or counter. `value` is numeric only
when `availability` is `available`; otherwise it is null. `unit`, `boundary`,
`provenance`, `equivalence`, and `evidence_refs` are required. Values may not
be represented as zero merely because they are missing. `evidence_refs` are
bounded relative artifact paths plus field/event identifiers, never raw payloads,
paths outside the result, command lines, credentials, unrestricted URLs, or
environment variables.

The closed initial provenance vocabulary is `llmgauge_observed`,
`backend_reported`, `calculated`, and `unavailable`. `calculated` records name
all input references and a versioned calculation string in
`calculation_semantics`; storing a backend-reported number does not make it
observed. The closed availability vocabulary is `available`, `unavailable`,
`unknown`, and `unsupported`. `unavailable` means the admitted observation was
attempted but absent; `unknown` means no admissible determination exists;
`unsupported` requires documented backend/capability evidence, not one failed
observation. `provenance=unavailable` is required whenever availability is not
`available`.

The closed equivalence vocabulary is `equivalent`, `not_equivalent`,
`unproven`, and `unavailable`. `equivalent` is allowed only after the checks in
[Equivalence and comparison](#equivalence-and-comparison); `unavailable` is
used only with a non-available metric.

Backend-native fields remain untouched and preserved even where no neutral
mapping is valid. In particular, llama.cpp `prompt_eval_tps` and
`generation_tps`, current peak VRAM/headroom fields, vLLM
`request_wall_time_seconds`, vLLM `end_to_end_completion_tps`, and all existing
backend evidence retain their current meanings.

## Neutral metric definitions

All durations use SI seconds (`s`); throughputs use `token/s`; memory uses
mebibytes (`MiB`). A metric record uses exactly the applicable identifier and
boundary below.

### Request wall time

`llmgauge.metric.v1.request_wall_time` measures complete request wall time from
immediately before LLMGauge transmits an admitted request to completion of
response receipt and admitted response validation. It includes local request
serialization after the start boundary, connection, transport, server queueing,
model work, response transfer, and validation. LLMGauge-observed timing MUST
use a monotonic clock. It is not model-compute latency.

A timeout, cancellation, or failed response may preserve elapsed wall time with
`completion_state` and failure evidence; it is not a successful-completion
metric. Each retry is a separate measurement. Existing native wall-time evidence
is preserved independently and may map only when its recorded boundary is this
boundary.

### Time to first token

`llmgauge.metric.v1.time_to_first_token` measures seconds from the request start
boundary above to availability of the first generated output token at the
LLMGauge transport boundary. It requires a streaming or equivalent admitted
observation that identifies that moment. A non-streaming request/response does
not fabricate TTFT from total duration. A backend-reported TTFT maps only when
its documented boundary is proven identical.

Empty completed generation, error before the first token, timeout before the
first token, and non-streaming transport make TTFT unavailable, not zero.
Cache state is recorded in the measurement workload; cold and warm observations
are not equivalent. Retries are independent measurements.

### Prompt/prefill throughput

`llmgauge.metric.v1.prefill_throughput` is authoritative prompt-token count
divided by prefill-phase elapsed seconds (`token/s`). The phase starts when the
runtime begins admitted prompt/prefill processing and ends when it completes
that phase, before decode/first-token work. The record names the prompt-token
authority and tokenizer/template identities in `workload`. A backend-reported
counter may map only if its numerator and phase boundary meet this definition.

Different tokenizers, template rendering, batching, cache reuse, or counters
including excluded work block equivalence. llama.cpp prompt-eval values remain
native evidence under their current semantics; their mapping is unavailable
unless preserved evidence proves the complete neutral requirements.

### Decode generation throughput

`llmgauge.metric.v1.decode_generation_throughput` measures only output tokens
generated after the first output token divided by the elapsed decode interval
after that first token becomes available (`token/s`). The interval starts at
first output-token availability and ends when generation completes; request,
transport, prompt/prefill, and TTFT remain excluded. When the authoritative
generated-token counter includes the first output token, the neutral numerator
is that admitted count minus one. EOS follows the authoritative counter's
already-recorded EOS-counting policy.

No post-first-token output token, or a zero, negative, missing, or otherwise
inadmissible post-first-token interval, makes this metric unavailable rather
than zero or infinity. The generated-token authority, tokenizer identity, EOS
policy, interval boundary, and completion state are required workload/evidence
facts. A failed partial completion may retain a value only when both this
numerator and denominator are valid and `completion_state=partial`; it cannot
support completed-workload comparison. A backend-native decode TPS may map only
when its numerator and interval have these same semantics.

llama.cpp `generation_tps` remains native decode/generation evidence. vLLM
`end_to_end_completion_tps` is end-to-end completion throughput, not decode-only
throughput, and MUST NOT map to this neutral metric without preserved evidence
proving the required phase semantics.

### Model-load time

`llmgauge.metric.v1.model_load_time` measures seconds from runtime start of
model-weight loading to completion of model readiness for admitted inference.
It requires evidence for both boundaries. It cannot be inferred from process
startup, first-request latency, filenames, or unrecorded operator action. An
operator-managed reused vLLM process legitimately has unavailable load time;
a backend-compatible load interval may map when captured. `workload.cache_state`
records cold versus reused process state.

### VRAM

`llmgauge.metric.v1.peak_vram` is the maximum absolute used memory in `MiB` for
one identified device among samples captured from the declared sampling start to
end boundary. It is not a baseline delta. `llmgauge.metric.v1.steady_state_vram`
is the median absolute used memory in `MiB` for that same device over an explicit
post-load, post-warmup steady interval; it is unavailable without that interval
and at least one valid sample. Each record names probe/backend source, device
identity scope, sample count, sampling interval or unknown interval, and exact
sampling boundaries.

Initial representation is per device: `execution_placement.device_scope` names
one observed device. Multi-device runs carry one record per device; no total,
mean, or cross-device peak is synthesized. A report may list those records but
MUST NOT sum or compare differing device scopes. Missing backend VRAM evidence
is unavailable. Existing `vram/*` samples and current native summaries remain
preserved under their original semantics.

### CPU offload and hybrid execution

`execution_placement` is observed execution metadata, not a score. It contains
separate `requested` and `observed` closed states: `full_accelerator`,
`hybrid_accelerator_cpu`, `cpu_only`, `unknown`, or `unavailable`; `observed`
requires direct/backend evidence. It may also carry bounded native layer/byte
references without normalizing counts across backends. Requested `-ngl`, a
filename, configured value, or expectation never establishes observed placement.

## Warmup, repetition, aggregation, and comparison

Warmups are `kind=warmup`; measured observations are `kind=measured`. Warmups
never enter measured aggregates. No warmup record means the run is not described
as warmed. Failures during either kind remain measurements and failure
observations. Repetitions use distinct attempt IDs and preserve retry ancestry;
a later success never deletes an earlier failure.

Aggregation is legal only for measured, completed observations sharing metric
identity/version, workload identity, runtime semantics, tokenizer/template where
applicable, requested and observed settings, cache/warmup state, hardware/device
scope, and completion state. Initial summaries are `count`, `minimum`, `maximum`,
and arithmetic `mean`; each stores its ordered contributing measurement IDs.
With one valid observation all four equal that value. Failed, partial, timed-out,
or cancelled repetitions are reported as excluded with their IDs and reasons,
not silently removed. No global performance score is admitted.

Two metric records are `equivalent` only when their neutral definition/version
and every applicable compatibility input above match. Matching units alone do
not suffice. Tokenizer/template, batching, cache state, workload, timing
boundary, backend-counter, device-scope, requested/observed-setting, or material
incomplete/failed-execution mismatch makes them `not_equivalent`; absent evidence
is `unproven`. Cross-runtime comparison then permits only side-by-side disclosure
until equivalence is established. Current generic comparison behavior is
unchanged.

## Failure taxonomy representation

`failure_taxonomy.observations` is an additive, LLMGauge-derived classification
layer. It never replaces native exit status, signal, timeout, backend error
evidence, transcript terminal state, or Agent Harness source terminal/tool
lifecycle facts. Every record has unique `failure_observation_id`,
`execution_ref`, `attempt_id` where the source admits one, nullable backward
`retry_of_attempt_id`, `category`, `source_fact_refs`, structured
`evidence_basis`, and `execution_state`.

`category` is closed for v1:

- `runtime_environment_failure`
- `unsupported_architecture`
- `unsupported_quantization_or_kernel`
- `model_weight_load_oom`
- `kv_cache_oom`
- `endpoint_failure`
- `tool_failure`
- `generation_failure`
- `malformed_response`
- `agent_recovery_failure`
- `unclassified_unknown`

`execution_state` is closed: `terminal`, `recoverable`, `recovered`, or
`unknown`. Its authority is the referenced source terminal/lifecycle state; a
derived classification cannot upgrade it. `primary_by_execution` maps an
execution reference to a nullable primary observation ID and state
`classified`, `none`, or `ambiguous`. Multiple observations are retained. When
two supported, equally specific causes cannot be causally ordered, state is
`ambiguous` and no sole primary is emitted; `unclassified_unknown` is used only
when no specific category is evidenced.

### Evidence and precedence

Classification uses structured phase/lifecycle evidence before bounded normalized
error codes or messages. Substring matching alone cannot establish a specific
cause when stronger structural evidence is absent.

| Category | Minimum assignment evidence | Priority rule |
|---|---|---|
| `model_weight_load_oom` | OOM evidence plus an admitted model/weight-load phase | Beats generic environment/load failure. |
| `kv_cache_oom` | OOM evidence explicitly attributed to KV/cache allocation or context expansion | Beats generic environment/generation failure. |
| `unsupported_architecture` | Runtime evidence identifying an architecture incompatibility | Beats generic load/environment failure; generic load failure is insufficient. |
| `unsupported_quantization_or_kernel` | Explicit unsupported quantization format or kernel/capability incompatibility | Beats generic load/environment failure; OOM is not this category. |
| `endpoint_failure` | Connect, endpoint availability, transport, or protocol-access failure | Beats generic runtime only for the endpoint scope; malformed successful response instead uses `malformed_response`. |
| `malformed_response` | Received response bytes/structure violate the admitted response contract | Beats endpoint failure after a successful transport response; bad semantic answer is not malformed. |
| `generation_failure` | Generation began, or generation-specific runtime failure is evidenced | Beats generic runtime failure only for the generation phase. |
| `runtime_environment_failure` | Process/runtime environment cannot execute correctly and no more specific category is evidenced | Generic fallback, never hides a supported diagnosis. |
| `tool_failure` | Authoritative tool lifecycle evidence for an evaluation class that owns tools | Does not apply to native prompt results; preserved alongside a source-backed recovery classification. |
| `agent_recovery_failure` | Admitted Agent Harness source-backed recovery relationship plus evidence that that recovery failed | If both apply to the same recovery episode, this is primary over antecedent `tool_failure`; ordering alone is insufficient. |
| `unclassified_unknown` | A preserved failure fact with no supported specific diagnosis | Never substitutes for a specific diagnosis. |

The precedence table applies only among observations for the same execution and
causal phase. `model_weight_load_oom` and `kv_cache_oom` are both specific but
are not ordered without phase evidence; that conflict is ambiguous. A process
or transport failure after generation has begun does not erase the
`generation_failure` observation; use phase evidence to select it over generic
runtime failure. Secondary source facts always remain referenced.

## Retry, recovery, source authority, and legacy compatibility

Every retry/fallback is represented by distinct attempt and observation IDs with
backward ancestry. Fallback requires an explicit preserved source/settings
relationship; it is never inferred from changed output. A later successful retry
sets the earlier failure observation state to `recovered` only when its linked
source contract declares that recovery; otherwise it remains `recoverable` or
`unknown`. It does not erase the earlier failure or make a terminal source event
non-terminal. Final run success follows the owning execution contract, not the
presence of a derived classification.

Imported Agent Harness terminal, tool, repository, verifier, and recovery facts
remain source-owned. A future LLMGauge classification cites contained source
references and cannot replace that source outcome. `agent_recovery_failure`
requires the admitted source-backed relationship. Native and transcript results
retain their existing LLMGauge-owned evidence contracts; external vLLM/backend
and transport facts remain backend/transport evidence. Generic provider or HTTP
text is not enough for architecture, kernel, or OOM diagnosis.

Existing vLLM `failure_class`/`failure_detail`, native failures, Fit Ladder
classes, transcript attempt state, Agent Harness lifecycle state, exit status,
signal, and timeout fields retain their historical authority and semantics. The
new layer is additive; older results without it remain valid and are not
retroactively classified.

## Failure and metric boundaries

A failure before first token makes TTFT unavailable, never zero. Weight-load OOM
makes generation throughput unavailable. Partial generation may preserve elapsed
wall time or native counters only with `completion_state=partial` and the linked
failure; metric presence is not evidence of successful completion. Failed
repetitions remain records and cannot be silently excluded from reporting.

Future structural validation may check closed identifiers/vocabularies, field
types, units, availability/value consistency, provenance and calculation shape,
evidence-reference containment, legal category/state combinations, ancestry
ordering, and equivalence-state consistency. It MUST NOT infer a failure from
arbitrary prose, claim runtime equivalence, run a runtime/model, probe a service,
inspect live repository state, or treat a metric as quality or success.

Future reporting shows neutral and native values separately with unit,
provenance, availability, equivalence limits, source references, primary and
secondary failures, and retry/recovery history. It must show unavailable/unknown
without substitution. It cannot produce a universal performance score, universal
model-quality conclusion, or publication-readiness decision from these records.

## First implementation milestone

The first admitted implementation is a bounded native single-turn, llama.cpp
only slice: add the optional top-level `runtime_neutral_metrics` and
`failure_taxonomy` v1 representations for one measured attempt per existing
prompt result; map only monotonic LLMGauge-observed request wall time when its
boundary is captured, retain llama.cpp native prompt/eval metrics without neutral
throughput mapping unless all required evidence is captured, and derive only
`runtime_environment_failure`, `model_weight_load_oom`, `kv_cache_oom`, and
`unclassified_unknown` from structured existing native evidence. It adds
additive serialization, structural validation, future fingerprint integration,
and focused fixtures/tests for availability, evidence references, failure
precedence, legacy absence, and fingerprint stability.

That milestone may adapt the existing llama.cpp runner, metric parser, native
result builder, result validator, and fingerprint builder. It does not adapt
vLLM transport, streaming, Agent Harness import, transcript execution,
comparisons, reporters/exporters, VRAM collection, repetitions, or Area 5 shared
transport. Those remain separately gated.
