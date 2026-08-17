# External Benchmark and LocalMaxxing Interoperability Contract

## Status and admission

Status: accepted architecture and interoperability contract. It is design
only. It adds no importer, schema code, CLI, runner, dataset, model
execution, LocalMaxxing request, suite registration, or release behavior.

It specializes the accepted
[general evaluation taxonomy](GENERAL_EVALUATION_TAXONOMY.md) and
[Full Model Testing Capability Architecture](FULL_MODEL_TESTING_CAPABILITY_ARCHITECTURE.md).
The operational speed integration remains the
[LocalMaxxing integration contract](LOCALMAXXING_INTEGRATION_CONTRACT.md).
Current result artifacts remain under
[Artifact Schemas](ARTIFACT_SCHEMAS.md) until a later implementation
milestone updates them additively.

Admission is **PASS** for one future external-text-benchmark evidence
model plus optional LocalMaxxing quality-benchmark interoperability.
LLMGauge remains the read-only evidence, provenance, validation,
reporting, and interoperability layer. The authoritative harness,
dataset, and scorer remain authoritative.

## Evaluation class and authority

Imported external benchmarks are **external text benchmark** evaluations.
They are never:

- LLMGauge-owned native response suites;
- LocalMaxxing performance/speed benchmarks;
- Agent Harness / agent-environment evidence;
- runtime-neutral Area 4 measurements.

LLMGauge MUST NOT recreate MMLU, ARC Challenge, HellaSwag, WinoGrande,
TruthfulQA, GSM8K, HumanEval, MBPP, or their variants as native prompts
and call them those benchmarks.

Authority is layered:

1. The official dataset, dataset revision, harness, native outputs, and
   official metric artifacts are the provenance origin.
2. After atomic import, digest-bound contained copies are the private
   canonical source for the imported result. Later validation reads only
   those copies.
3. Normalized `evidence.json` is authoritative for LLMGauge identity,
   source mapping, availability, and validation state. It does not
   replace or repair source facts.
4. Reports, comparisons, indexes, public exports, and LocalMaxxing
   payloads are derivatives. They never mutate the contained source.

Importing MUST never mutate, repair, rescore, or reinterpret the
authoritative source result. Structural validation is not official
acceptance, answer quality, or publication readiness.

## Evidence flow

The accepted future flow is:

```text
authoritative harness result
    -> immutable preserved source evidence
    -> LLMGauge read-only import
    -> normalized benchmark evidence + provenance
    -> validation / reporting
    -> optional LocalMaxxing export
    -> authenticated dry-run
    -> explicit confirmed public submit
    -> separate submission receipt
```

Rules:

- Offline import, validation, reporting, and export never contact a
  network service.
- Dry-run and submit are later, explicit online commands. They are not
  implied by import eligibility.
- Public submit requires `--confirm-public`, dry-runs first, and writes a
  separate receipt. It never mutates imported evidence.
- Failed submit writes no success receipt.
- A LocalMaxxing shard-eval, Wilson-CI leaderboard, or community suite
  score is not the official harness metric.

## Imported-evidence contract

### Identities

The first implementation MUST use these closed identities unless a later
accepted contract replaces them:

| Concept | Exact identity |
|---|---|
| Evidence `schema_version` | `llmgauge.external_benchmark_evidence.v0` |
| Evidence `contract_version` | `0.1.0` |
| Evaluation class | `external_text_benchmark` |
| First admitted source type | `lm_eval_harness_results` |
| Importer | `llmgauge.external_benchmark_importer` |
| Owning result schema | `llmgauge.result.v0` |

A containing result represents exactly one imported source package and
may carry exactly one optional top-level
`external_benchmark_evidence` reference. That result is a dedicated
external-benchmark import result: it has no native prompt results, no
`transcript` reference, and no `agent_harness_evidence` reference.
Multiple source packages require separate results.

A material change to source semantics, normalized meaning, or authority
requires a new evidence schema or contract version. A new harness family
requires a separately accepted source identity.

### Contained source package

The importer copies every admitted source byte needed by the imported
claim into the owning result. A mutable external path is never the sole
long-term authority.

Fixed layout:

```text
external-benchmark/
  evidence.json
  source/
    <original source members, exact bytes>
    objects/
      sha256/
        <64-lowercase-hex-digest>
```

Every unique copied file records contained relative path, role, byte
count, and `sha256` as 64 lowercase hexadecimal characters.
`source_package_sha256` is computed over a canonical JSON array of those
entries, sorted by contained path. Canonical JSON is UTF-8, recursively
sorted object keys, `,` and `:` separators without insignificant
whitespace, and no trailing newline.

The first admitted source type is an EleutherAI
`lm-evaluation-harness` result tree or equivalent documented
`lm_eval` output JSON plus any accompanying config/logs the source
presents as part of that result. LocalMaxxing shard-eval traces,
EvalPlus-only reports, and other harness families are not this source
type.

### Required normalized fields

Normalized evidence records the following. Missing facts use the closed
availability vocabulary; they are never invented.

| Field group | Rule |
|---|---|
| Schema and contract identity | Required exact identities above. |
| Source artifact integrity | Contained path inventory, per-file SHA-256, byte counts, and `source_package_sha256`. |
| Benchmark suite/task identity | Official suite or task IDs exactly as named by the admitted harness. Do not alias `mmlu` to `mmlu_pro`, `humaneval` to `humaneval-plus`, or LocalMaxxing shard slugs to lm-eval task names. |
| Harness identity | Harness family, version, and commit when the source provides them. Otherwise availability is `absent`, `unknown`, or `unavailable`. |
| Dataset/config/revision | Dataset name, config, split, and revision when represented. Filename inference is not dataset identity. |
| Few-shot and task configuration | `n_shot`, task list, and harness config exactly as represented. |
| Seeds and generation settings | Recorded only when the source represents them. |
| Model identity | Model/checkpoint identity and available fingerprint evidence. A Hugging Face ID is recorded when present; it is not invented from a local filename. |
| Runtime/hardware provenance | Runtime, engine, quantization, and privacy-safe hardware facts when honestly available. |
| Native metrics | Native metric names, values, units, and higher-is-better or lower-is-better direction as represented. |
| Native aggregation | Harness-native group, subgroup, and suite aggregation. LLMGauge does not invent a replacement aggregate. |
| Sample/denominator | `n_samples`, filter counts, and other denominators when available. |
| Import provenance | Importer identity, installed LLMGauge version, and import timestamp. Timestamp is mutable metadata, not fingerprint input. |
| Validation state | Closed structural validation outcome. Validators do not repair source bytes. |
| Unsupported/unknown semantics | Explicit availability. Unsupported optional source extensions do not fail the whole import unless they collide with required identity. |

### Availability vocabulary

| State | Meaning |
|---|---|
| `available` | The admitted source directly carries the value or exact bytes. |
| `absent` | The supported source format permits omission and no value is present. |
| `unknown` | No authoritative value can be established from the complete admitted source. |
| `unavailable` | The source says evidence existed, but its value or bytes were not retained. |
| `redacted` | The source explicitly removed the value or bytes. |
| `unsupported` | An optional source representation is present but this evidence version assigns it no semantics. |

An availability state is not a value. Empty output is not absent output.

### Validation and containment

Validation is deterministic and fail-closed:

- check schema, contract, and source-type identities;
- recompute contained hashes and the source-package digest;
- reject path escape, absolute host paths as source authority, and
  mixed evaluation-class references;
- confirm represented task keys, metric names, and sample counts are
  internally consistent with the admitted source;
- never execute generated code, never call a model, and never fetch
  datasets.

HumanEval, MBPP, HumanEval+, and MBPP+ retain their native execution
boundaries. LLMGauge may import harness-produced pass/fail or pass@k
evidence. It MUST NOT execute, apply, or sandbox generated code to
recreate those metrics.

### Fingerprint participation

Implementation MUST add an additive fingerprint payload version for
results that contain this evidence. Historical
`llmgauge.run_fingerprint.v0` and Area 4
`llmgauge.run_fingerprint.v1` payloads remain valid and are not
recomputed.

The new payload includes:

- evidence schema and contract versions;
- evaluation class and source type;
- source package SHA-256;
- immutable normalized identity and metric projection;
- hashes of referenced contained source members.

Excluded from the fingerprint: import timestamp, external locator,
review notes, reports, comparisons, public exports, and LocalMaxxing
payloads or receipts. Fingerprints identify evidence. They do not prove
model quality, official leaderboard acceptance, or transformed export
bytes.

## Native metric semantics

Do not flatten unlike benchmark metrics into one generic score.

| Benchmark | Native identity to preserve |
|---|---|
| MMLU | Official `mmlu` group accuracy and subject-level accuracies. Not a universal knowledge score. |
| ARC Challenge | Official `arc_challenge` metric. Not LocalMaxxing Wilson-CI shard accuracy. |
| HellaSwag | Official `hellaswag` metric, including `acc` versus `acc_norm` when the source distinguishes them. |
| WinoGrande | Official `winogrande` metric. |
| TruthfulQA MC2 | Official `truthfulqa_mc2` metric. Not MC1 and not a generic truthfulness score. |
| GSM8K | Official `gsm8k` exact-match or harness-declared equivalent. Not LocalMaxxing pooled shard pass rate. |
| HumanEval | Official pass@k evidence. Distinct from HumanEval+ and from native Coding Core checks. |
| MBPP | Official pass@k evidence. Distinct from MBPP+. |

Task and suite aggregation MUST preserve the authoritative harness
semantics. No universal benchmark score or cross-benchmark ranking is
admitted.

Comparison is eligible only when evaluation class, suite/task identity,
dataset split and revision, harness and metric versions, few-shot or
equivalent configuration, subject, generation settings, completion
policy, and material limits are compatible. Otherwise LLMGauge may show
a side-by-side inventory with explicit incompatibility.

## Future CLI surface

Preferred conceptual commands, matching the existing typer sub-app
pattern used by `llmgauge localmaxxing`:

```text
llmgauge benchmark import
llmgauge benchmark validate
llmgauge benchmark report
llmgauge benchmark localmaxxing export
llmgauge benchmark localmaxxing dry-run
llmgauge benchmark localmaxxing submit --confirm-public
```

Rationale: quality-benchmark work is a distinct evaluation class. It
MUST NOT reuse the existing `llmgauge localmaxxing` namespace, which
remains the llama.cpp speed/performance integration
(`run`, `validate`, `export`, `dry-run`, `submit`).

Exact flag names are an implementation detail. Required product rules:

- `import`, `validate`, `report`, and `export` are offline;
- `dry-run` and `submit` are the only network commands in this family;
- `submit` requires `--confirm-public`;
- authentication uses the same explicit environment-key pattern as the
  speed integration and never persists, logs, or exports secrets;
- no ordinary native `run`, score, report, or export command invokes
  this path.
- future quality export maps imported official metrics onto an approved
  `LM_EVAL_HARNESS` suite's task keys; it does not submit shard traces
  or ask LocalMaxxing to execute a harness.

## Observed LocalMaxxing quality API

Observation date: **2026-08-16**. Sources: `GET /api/agent-context`,
`GET /api/openapi.json` (OpenAPI **1.6.0**), `GET /api/benchmarks/suites`,
public `/en/benchmarks` pages, and official API docs. These facts can
change; implementation MUST re-fetch before locking payload mapping.

### Documented quality-benchmark API

Agent-context `_meta` and OpenAPI 1.6.0 document a quality-benchmark
surface distinct from speed tests:

| Role | Observed endpoint |
|---|---|
| Suite discovery | `GET /api/benchmarks/suites` |
| Suite document | `GET /api/benchmarks/suites/{slug}` |
| Authenticated run bundle | `GET /api/benchmarks/suites/{slug}/run-bundle` |
| Dry-run | `POST /api/benchmarks/runs/dry-run` |
| Public submit | `POST /api/benchmarks/runs` |
| Suite registration | `POST /api/benchmarks/suites` |
| Server-side custom execute | `POST /api/benchmarks/execute` |
| Artifact storage | `/api/benchmarks/storage/upload-url`, `complete`, `download-url` |

Auth is `Authorization: Bearer bhk_<40 hex chars>`. Quality submissions
are rate-limited to 30 per rolling hour per key (300 for Pro). Submitted
runs start **PENDING** and appear publicly only after admin approval.

Documented `LM_EVAL_HARNESS` submit fields: required `suiteSlug`,
`hfId`, `hardware`, and `results` map of every suite `taskKey` to a
score or `{score, nShots, nSamples}`. Optional fields include
`runnerVersion`, `runConfig`, `quantization`, `artifacts`, and
`artifactBundle`. Unknown or missing task keys are rejected.

Agent-context says existing `lm_eval` output can be parsed from
`localmaxxing-eval-results.json` after
`lm_eval ... --output_path localmaxxing-eval-results.json`. That is
not a claim that an arbitrary upstream result file is accepted without
an approved suite document and full task-key coverage.

`POST /api/benchmarks/suites` can register a suite. It starts
**PENDING** and requires admin approval before runs can be submitted.
This milestone does not register suites.

LLMGauge MUST NOT call `POST /api/benchmarks/execute`, MUST NOT submit
shard traces, and MUST NOT treat `/api/benchmarks/shard-runs` as the
documented quality-submit path. Those endpoints are LocalMaxxing-owned
execution or shard protocols, not official-harness import interoperability.

### Observed live catalog gap

On 2026-08-16:

- `GET /api/benchmarks/suites` returned `{suites: [], total: 0}` with
  default and `official=true` filters.
- `GET /api/benchmarks/suites/{slug}` returned 404 for `mmlu`,
  `mmlu-5shot`, `hellaswag`, `gsm8k`, and `arc-challenge`.
- OpenAPI examples still use slugs such as `mmlu-5shot` and
  agent-context examples use `hellaswag` / `mmlu`. Those examples are
  not live approved suite documents.

The public website simultaneously lists official **shard eval** suites
that are not discoverable through the documented public suites API:

| Public slug | Observed protocol |
|---|---|
| `gsm8k` | Official shard eval; `openai/gsm8k/main:test`; 1,319 questions; 13 shards |
| `hellaswag` | Official shard eval; `Rowan/hellaswag:validation`; 10,042 questions |
| `arc-challenge` | Official shard eval; `ai2_arc/ARC-Challenge:test`; 1,172 questions |
| `humaneval-plus` | Official shard eval; `evalplus/humanevalplus:test`; 164 questions |
| `mbpp-plus` | Official shard eval; `evalplus/mbppplus:test`; 378 questions |
| `crud-bench`, `terminal-bench-2-1` | Official agentic shard evals; not this contract's class |

Those pages instruct `lmx eval shard <slug> ... --dry-run|--submit`.
Scores are pooled by unique `question_id` and ranked by Wilson 95%
lower bound. HumanEval+ and MBPP+ traces show sandbox execution. OpenAPI
1.6.0 contains **no** `shard-runs` schema or path, although the website
exposes `/api/benchmarks/shard-runs/{id}/traces`.

Consequence: LocalMaxxing official shard suites are a LocalMaxxing-owned
evaluation protocol. They are not official EleutherAI lm-eval results
and MUST NOT be treated as interchangeable with Bundle 1 native metrics.

## Bundle 1

Intended first mainstream import bundle, subject to harness and
LocalMaxxing compatibility. No item is currently integrated.

Authoritative harness for this bundle is EleutherAI
`lm-evaluation-harness` (`lm_eval`), observed 2026-08-16 from the
upstream task READMEs. The implementation milestone MUST pin exact task
IDs, splits, few-shot, metric names, and harness version/commit. This
contract does not invent unpublished defaults.

| Benchmark | Authoritative path | LocalMaxxing as of 2026-08-16 | Special bounds |
|---|---|---|---|
| MMLU | lm-eval group `mmlu` (original Hendrycks multiple-choice). Distinct from `mmlu_continuation` and `mmlu_generative`. | **Unconfirmed.** No public suite page or approved API suite. OpenAPI example slug `mmlu-5shot` 404s. | Preserve subject-level accuracies. Do not flatten to one generic score. |
| ARC Challenge | lm-eval `arc_challenge`. | **Confirmed LocalMaxxing shard suite only.** Public `/en/benchmarks/arc-challenge` exists; not an approved `LM_EVAL_HARNESS` suite via the public API. | Shard Wilson-CI pass rate is not official `arc_challenge` accuracy. |
| HellaSwag | lm-eval `hellaswag`. | **Confirmed LocalMaxxing shard suite only.** Public `/en/benchmarks/hellaswag`. | Preserve `acc` / `acc_norm` if the source distinguishes them. |
| WinoGrande | lm-eval `winogrande`. | **Unsupported** on the public catalog and suite pages. | No LocalMaxxing export until an approved matching suite exists. |
| TruthfulQA MC2 | lm-eval `truthfulqa_mc2`. | **Unsupported** publicly (`/en/benchmarks/truthfulqa` 404). | Do not substitute MC1 or a generic honesty score. |
| GSM8K | lm-eval `gsm8k`. | **Confirmed LocalMaxxing shard suite only.** Public `/en/benchmarks/gsm8k`. | Shard pooled pass rate is not official GSM8K exact-match. |
| HumanEval | lm-eval `humaneval` pass@1; `humaneval_64` is a distinct pass@64 variant. | **Unsupported** as original HumanEval. Official public suite is **HumanEval+**. `/en/benchmarks/humaneval` 404s. | Code execution stays in the harness. LLMGauge does not execute generated code. HumanEval+ is not HumanEval. |
| MBPP | lm-eval `mbpp` pass@k. | **Unsupported** as original MBPP. Official public suite is **MBPP+**. | Same execution/safety split as HumanEval. MBPP+ is not MBPP. |

LocalMaxxing export of Bundle 1 official metrics is therefore **not
currently available** through the documented approved
`LM_EVAL_HARNESS` catalog. Future export requires one of:

1. LocalMaxxing publishing approved `LM_EVAL_HARNESS` suites whose task
   keys and metrics match the imported official result; or
2. a later accepted contract for a separately identified LocalMaxxing
   shard protocol, which MUST remain a different evaluation identity.

Suite registration may become an interoperability path if a later
milestone explicitly authorizes it. This contract does not authorize
registration.

## Bundle 2 investigation

Separate later investigation. Not admitted for implementation here.

| Benchmark | Authoritative path | LocalMaxxing as of 2026-08-16 |
|---|---|---|
| MMLU-Pro | lm-eval `mmlu_pro` family. Distinct from `mmlu`. | **Unsupported** publicly (`/en/benchmarks/mmlu-pro` 404). OpenAPI `EvalSuiteCreate` example slug is `mmlu-pro-5shot`; that is an example, not a live suite. |
| GPQA | lm-eval `gpqa_{main,diamond,extended}_{zeroshot,n_shot,...}`. Dataset is gated on Hugging Face. | **Unsupported** publicly (`/en/benchmarks/gpqa` 404). |
| IFEval | lm-eval `ifeval`. | **Unsupported** publicly (`/en/benchmarks/ifeval` 404). |

Do not invent a workaround that recreates these as native prompts or
maps them onto unrelated LocalMaxxing shard suites.

## Development order

Selected order after the completed Area 4 native llama.cpp slice:

| Step | Milestone | Bound |
|---|---|---|
| A | This interoperability contract | Complete when this document is accepted. |
| B | External benchmark importer/foundation | Schema, contained import, validation, fingerprint participation. No live benchmarks and no LocalMaxxing quality submit. |
| C | First mainstream benchmark bundle | Admit exact Bundle 1 task/metric pins and import fixtures. No native recreation. |
| D | LocalMaxxing quality export / dry-run / `--confirm-public` submit | Only after an approved matching suite path exists or a later contract admits a different LocalMaxxing protocol. |
| E | Generic Core v1 completion | Unchanged admitted downstream work. |
| F | Reasoning and sampling profiles | Unchanged later fast-track work. |

D MAY be combined with B or C later only if the then-current LocalMaxxing
catalog makes that genuinely bounded and safe. As of 2026-08-16 it is
not: the public `LM_EVAL_HARNESS` catalog is empty.

The completed Area 4 native llama.cpp slice remains implemented
capability. Future Area 4 expansion is not this track and is not
implied by this contract.

## Speed-result field investigation

Retain a separate investigation, outside this quality-benchmark track
and without changing the current speed integration.

During the Qwen3.8 installed public-run validation, LLMGauge captured
CPU, total RAM, GPU utilization, GPU temperature, peak power, and split
mode locally, but the public LocalMaxxing UI did not expose them.

OpenAPI 1.6.0 inspection on 2026-08-16, not a storage or UI proof:

| Captured field | Schema observation | Residual question |
|---|---|---|
| CPU | `hardware.cpu` exists on discrete-GPU hardware. | Schema admits it; gap is likely storage or public UI. |
| Total RAM | `hardware.ramGb` exists. | Schema admits it; gap is likely storage or public UI. |
| Split mode | `engineFlags.splitMode` exists. | Exported locally; public UI did not show it. |
| Peak power | `gpuPowerWatts[]` and `hardware.powerWatts` exist. UI showed mean power, not peak. | Likely UI/aggregation, not a missing power field. |
| GPU utilization | No compute-utilization field. `engineFlags.gpuMemUtil` is memory utilization in `[0,1]`. | Likely submission-schema gap. |
| GPU temperature | No temperature field. `engineFlags.temperature` is sampling temperature. | Likely submission-schema gap. |

The investigation MUST classify each gap as schema, storage/API, or
public UI before any speed-integration change.

## Privacy, publication, and claims

Canonical imported evidence remains local and private by default. Public
export is a separate sanitized derivative and never mutates the source.
Sanitization is not proof that all private data was removed.

Claims remain bounded to the imported harness identity, dataset, metric,
model, runtime, hardware, and scoring state actually represented.
Importing or submitting does not establish daily-driver quality, safety,
or universal rank.

## Non-goals

This contract does not admit:

- Python, schema, or CLI implementation;
- benchmark, model, or dataset execution or download;
- LocalMaxxing authenticated requests, submissions, or suite
  registration;
- Generic Core implementation;
- changes to the existing LocalMaxxing speed integration;
- release or version metadata changes;
- a universal benchmark score.

## Next implementation gate

The next implementation milestone is **B**: the bounded read-only
importer and `llmgauge.external_benchmark_evidence.v0` foundation for
`lm_eval_harness_results` only. It MUST NOT submit to LocalMaxxing or
treat official shard suites as lm-eval results.
