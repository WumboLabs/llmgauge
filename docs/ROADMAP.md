# LLMGauge Roadmap

LLMGauge is a conservative local-first CLI for practical LLM evaluation on real consumer hardware.

The project produces defensible, reproducible public evidence about usefulness, honesty, correctness, safety, speed, VRAM headroom, and workflow fit under disclosed hardware and runtime conditions.

LLMGauge is part of the WumboLabs workflow: **Real Hardware. Real Testing. No Hype.**

## Current release line

- Current stable tag: `v0.72`
- Current package version: `0.72.0`
- Current stable release line: `v0.72.0`
- Current release state: `v0.72` is the completed profile-aware suite foundation
  release. `generic-core-v1` is not yet an executable suite.

## What LLMGauge is

LLMGauge answers practical local-model questions such as:

- Does this model produce useful answers for real workflows?
- Does it stay honest when it lacks information or tools?
- Does it fit comfortably on consumer hardware?
- How fast is it under the tested runtime settings?
- What context sizes are viable before quality, latency, or VRAM headroom degrade?
- What artifacts support the result?
- What changed between two model runs, suites, scoring passes, or releases?

## What LLMGauge is not

- a cloud evaluation service
- a model downloader
- a hosted leaderboard
- an automatic judge that hides review
- a hardware tuning tool
- a general autonomous agent framework
- a hosted benchmark submission system or telemetry service

## Current capabilities

LLMGauge currently provides:

- local-first CLI runs with preserved raw/cleaned outputs and logs
- default `llama.cpp` / GGUF runtime plus optional external local vLLM adapter
  (`backend=vllm`; operator-managed, loopback-only, sequential, non-streaming)
- artifact validation (`validate-result`, ladder/batch/fit-ladder validators)
- manual scoring templates and `score --check` / `score --scores` workflow
- auto-draft scoring as review-required triage only
- single-run `report.md` with **Report Scope**, **Evidence Summary**, **Audit Checklist**, **Prompt Artifact Audit**, and **Publish Readiness Notes**
- comparison reports with **Comparison Scope**, publish-readiness, and **Publication evidence summary**
- `export-index` machine-readable metadata for importers
- sanitized single-run `export-public` derivatives with source protection
- model profile onboarding and management commands
- dry-run and preflight commands (`smoke`, `doctor`, guided `setup`)
- context ladder and fit ladder artifacts with preserved failures
- public-proof workflow guidance across docs
- Practical Eval v1 seed suite (`wumbolabs-practical-v1`)
- artifact schema documentation and result-directory audit guidance
- publish-readiness notes and explicit claim boundaries
- identity, provenance, and evidence-equivalence fingerprint foundations
- read-only `lm_eval_harness_results` import into
  `llmgauge.external_benchmark_evidence.v0`
- pinned Bundle 1 qualification and read-only `llmgauge benchmark report`

## Evaluation identities and boundaries

LLMGauge-owned native suites evaluate preserved LLMGauge prompts and retain
LLMGauge scoring authority. LocalMaxxing is an operational, opt-in llama.cpp
performance benchmark with its own versioned artifact and measurement protocol;
it is not a native-suite result. Future external benchmark imports must retain
the named benchmark's official dataset, harness, and metric authority. Agent
Harness evidence is an agent-environment evaluation with its imported session
evidence authority. These classes are not interchangeable and are never
combined into a universal score.

Mainstream external benchmarks are imported read-only. Bundle 1 qualification
is pinned against EleutherAI `lm-evaluation-harness` `v0.4.12` in
[Bundle 1 qualification](BUNDLE1_QUALIFICATION.md). The accepted
[external benchmark and LocalMaxxing interoperability contract](EXTERNAL_BENCHMARK_LOCALMAXXING_INTEROP_CONTRACT.md)
locks official-harness authority, imported-evidence identity, and the
`llmgauge benchmark` surface. Milestone B implements the bounded read-only
`lm_eval_harness_results` importer and evidence foundation. Milestone C
qualifies MMLU, ARC Challenge, HellaSwag, WinoGrande, TruthfulQA MC2, GSM8K,
HumanEval, and MBPP and adds `llmgauge benchmark report`. Bundle 2
(MMLU-Pro, GPQA, IFEval) remains later integration/testing and must be
imported under those official contracts, not recreated as native LLMGauge
prompts. LocalMaxxing official shard evals are a different protocol and are
not interchangeable with official lm-eval metrics.

## vLLM evidence track

The vLLM work is intentionally bounded to an externally managed local
integration and evidence collection. The accepted [runtime contract](VLLM_RUNTIME_CONTRACT.md)
and [HTTP transport assessment](VLLM_HTTP_TRANSPORT_ASSESSMENT.md) define a
loopback-only, text-only backend using the Python standard library. LLMGauge
does not install, start, supervise, or otherwise own the vLLM server lifecycle;
`llama.cpp`/GGUF remains the default runtime.

### Implemented capability

- External local vLLM adapter with sequential, non-streaming requests to an
  operator-managed loopback server.
- Bounded readiness and served-model checks; no remote, authenticated, streaming,
  concurrent, or server-lifecycle management support.
- Additive runtime evidence for server `/version`, API-readiness state, optional
  `system_fingerprint`, and ordered-unique run-level fingerprints, with
  backward-compatible validation, reporting, and export handling.

### Validated evidence

- [Live external-vLLM smoke](VLLM_LIVE_SMOKE_EVIDENCE.md): real
  Qwen2.5-3B-Instruct server, successful readiness/request/validation/reporting;
  historical pre-fingerprint evidence remains authoritative for that point in
  time.
- [Fingerprint live verification](VLLM_FINGERPRINT_LIVE_SMOKE_EVIDENCE.md):
  vLLM `0.25.1`, `server_state=ready`,
  `server_state_meaning=api_ready_observation`, and
  `vllm-0.25.1-eb488855` agreed across request, prompt, and run-level artifacts.
- [Cross-runtime comparison methodology](VLLM_CROSS_RUNTIME_COMPARISON_METHODOLOGY.md):
  runtime-native metrics, input/template disclosure, and bounded claim rules.
- [First prompt comparison](VLLM_CROSS_RUNTIME_COMPARISON_EVIDENCE.md):
  `tool-honesty/fake-tool-resistance`; vLLM 31/50 (average 3.1, mixed) and
  llama.cpp 25/50 (average 2.5, fail).
- [Second prompt comparison](VLLM_CROSS_RUNTIME_SECOND_PROMPT_EVIDENCE.md):
  `shell-safety/failed-command-recovery`; vLLM 32/50 (average 3.2, mixed) and
  llama.cpp 19/50 (average 1.9, fail). The direction replicated, but these
  two prompt-specific observations are not a benchmark or runtime ranking.

### Closed investigation

- [Gemma 4 12B NVFP4 CPU-offload audit](GEMMA4_12B_NVFP4_CPU_OFFLOAD_EVIDENCE.md):
  one checkpoint, one vLLM environment, one RTX 5070 host, and one controlled
  attempt. Mixed FP8/NVFP4 recognition was verified, but requested 4 GiB CPU
  offload had no successful observed offload before a construction-time BF16
  `ParallelLMHead` CUDA OOM. The server never reached readiness.
  Classification: `not_viable` for the disclosed configuration only.

### Active limitations

- No remote, authentication, streaming, or concurrency support; no
  LLMGauge-owned vLLM lifecycle.
- vLLM VRAM is not captured.
- Throughput and token fields remain runtime-native and non-equivalent.
- F16 GGUF and BF16 Transformers weights are not proven bit-identical, and
  prompt rendering/input forms are not proven identical.
- Manual scores are reviewer judgment, not objective truth; two scored prompts
  do not establish general runtime superiority.
- Server version and fingerprint are unauthenticated metadata. Fingerprint
  equality does not prove identical runtime state, and `server_state=ready`
  means API readiness only.
- Startup success or failure does not establish answer quality. The Gemma
  `not_viable` result does not generalize to another checkpoint, runtime, host,
  offload implementation, or quantization.

### Current decision

The bounded vLLM evidence track is complete enough for the present release line.
No immediate production feature expansion is justified solely by the current
evidence. Future vLLM work requires a concrete product or evidence need.

## Fit Ladder real-workflow evidence

The [real-workflow evidence record](FIT_LADDER_REAL_WORKFLOW_EVIDENCE.md)
completes bounded operator validation of both principal Fit Ladder terminal
paths:

- total failure after all planned contexts produced preserved, retryable OOM
  attempts, with no selected child;
- success after fallback, with one preserved OOM, one completed selected child,
  and stop before the remaining lower context.

Both parents, every executed child, and both export-index records validated.
Parent scoring was rejected in both paths; the completed selected child was
admitted as a normal single-run scoring target. These results validate
orchestration and artifact handling on one host, binary, and prompt. They do not
establish model quality, optimal context, a hardware support matrix, or a
cross-model ranking.

### First reviewed public practical evidence package

**Completed:** the first reviewed practical evidence package is tracked under
[docs/evidence/practical/grug-12b-q4-k-m/](evidence/practical/grug-12b-q4-k-m/).

It publishes one bounded six-prompt `wumbolabs-practical-use-v1` run for
Grug-12B Q4_K_M on llama.cpp (RTX 5070 telemetry), with full sanitized
`export-public` artifacts, export index, source-integrity notes, and claim
boundaries. Classification remains `review_ready_with_caveats`: 4 pass and
2 mixed verdicts (`unsupported_claim` on Arch/NVIDIA update advice and
consumer-GPU local-LLM advice), legacy provenance gaps disclosed, structural
validation only, manual scores as reviewer metadata, no ranking or
daily-driver claim.

See the [public evidence index](evidence/README.md).

### Second reviewed public practical evidence package

**Completed:** the second reviewed practical evidence package is tracked under
[docs/evidence/practical/qwen3-6-35b-a3b-ud-iq2-m/](evidence/practical/qwen3-6-35b-a3b-ud-iq2-m/).

It publishes one bounded six-prompt `wumbolabs-practical-use-v1` run for
Qwen3.6-35B-A3B UD-IQ2_M on llama.cpp (RTX 5070 telemetry), using a **new**
source with model-file provenance, backend provenance, run fingerprint, and
resolved `runtime-command.json`. Classification remains
`review_ready_with_caveats`: 3 pass and 3 mixed verdicts (Arch/NVIDIA command
imprecision; unknown-package overclaim without tools; truncated consumer-GPU
advice with unsupported model examples). Structural validation only; manual
scores as reviewer metadata; no ranking, daily-driver, or Grug-versus-Qwen
comparison synthesis in this package.

Qwen-specific capture caveats retained for honesty and for future comparisons:

- flash attention used `auto` (current CLI default), unlike the older Grug argv
  which did not pass an explicit flash-attention flag;
- the suite was resolved through a temporary suite path
  (`tmp/wumbolabs-practical-use-v1`) rather than a stable tracked suite path;
- the operator console log records prompt order and completion but is not a
  complete resolved execution plan (authoritative settings live in result
  artifacts and `runtime-command.json`);
- observed minimum VRAM headroom was about 521 MiB and is **not** a general fit
  guarantee;
- public-result fingerprint fields and the export-manifest
  `source_run_fingerprint` play different roles and must remain explicitly
  documented;
- hardware telemetry (GPU name/VRAM samples) is observed metadata, not
  authenticated hardware identity.

See the [public evidence index](evidence/README.md).

### Reference practical-run capture standard

Future **reference-quality** practical evidence runs should review and preserve
the following before launch and in the resulting artifacts. This is a
documentation standard for defensible packages; it is not a schema, CLI, or
runtime contract change.

**Identity and suite**

- stable tracked suite path and suite identity (and suite fingerprint when the
  installed tool records one);
- exact model profile name and GGUF path (do not invent paths);
- model-file fingerprint and available GGUF metadata;
- llama.cpp executable path, version/build metadata, and executable fingerprint
  when available.

**Resolved runtime**

- complete resolved `runtime-command.json`;
- explicit flash-attention setting (`auto` / `on` / `off`) rather than relying
  on an implicit default without disclosure;
- explicit reasoning mode;
- context, maximum tokens, temperature, top-p, batch, ubatch, and GPU layers;
- runtime methodology label.

**Hardware and timing**

- hardware disclosure mode;
- GPU plus CPU/RAM/OS/driver metadata when safely supported and privacy-safe;
- start and end timestamps;
- VRAM baseline, peak, and minimum headroom when capture is available.

**Execution evidence**

- prompt order and per-prompt completion or failure status;
- run fingerprint when the installed tool records one;
- raw output, cleaned output, stderr, retries, OOMs, and failed attempts
  preserved without silent replacement.

Operator console logs may aid review but are not substitutes for resolved
command metadata, result JSON, or runtime-command capture. Observed telemetry is
not authenticated identity. Fingerprints identify evidence; they do not prove
authorship, hardware, answer quality, or transformed public-export bytes.

### Completed bounded practical comparison

**Completed:** the first tracked comparison across the two reviewed practical
packages is tracked at
[Grug-12B versus Qwen3.6 practical evidence comparison v1](evidence/comparisons/grug-vs-qwen3-6-practical-v1/).

The comparison verifies the exact six-prompt overlap and reviewed scoring
metadata, discloses architecture, quantization, provenance, runtime-command,
flash-attention, suite-path, hardware-capture, runtime-label, VRAM, and
completion differences before interpreting results, and preserves all mixed
verdicts and failure labels. It confines quality observations to individual
reviewed prompts and operational observations to the recorded settings and
telemetry. Package averages remain descriptive reviewer metadata; the document
does not declare a winner, ranking, purchasing choice, daily-driver choice,
model-family advantage, safety result, or generalized fit.

Methodology differences materially limit attribution: the packages use a dense
Gemma-family Q4_K_M artifact and a Qwen3.6 MoE UD-IQ2_M artifact; the Grug run
has legacy provenance and no resolved runtime-command artifact; flash-attention
and runtime-label capture differ; both results record a temporary suite path;
both hardware records omit CPU, RAM, OS, and driver metadata; and Qwen's
consumer-GPU answer is truncated. See the comparison for the exact supported,
qualified, and unsupported claims.

### Historical Practical Suite v0.1.0 source

**Completed:** the exact historical `wumbolabs-practical-use-v1` version
`0.1.0` source is tracked at
[`suites/wumbolabs-practical-use-v1/`](../suites/wumbolabs-practical-use-v1/).
The source preserves the original `suite.yaml`, six prompt files, suite
identity, and prompt order without modernization. Focused verification
establishes private canonical source and rendering equivalence against the
authorized ignored reference, then deterministic sanitized derivative
equivalence against both existing practical evidence packages.

The path-bearing private `docker/compose-review` rendering intentionally differs
from its redacted public derivatives before sanitization. The existing
`wumbolabs-practical-v1` version `0.2.0` suite remains a separate identity.
These byte-equivalence checks do not establish answer quality, scoring
correctness, privacy completeness, or publication readiness.

### Provenance-refresh Grug practical evidence package

**Completed:** the separate provenance-refresh Grug-12B Q4_K_M package is
tracked at
[docs/evidence/practical/grug-12b-q4-k-m-provenance-refresh-v1/](evidence/practical/grug-12b-q4-k-m-provenance-refresh-v1/).

The source used the stable tracked historical suite, explicit reference
settings, model and executable/backend provenance, observed runtime identity,
resolved `runtime-command.json`, run fingerprint, operator start/end capture,
privacy-safe hardware disclosure, and complete raw/cleaned/stderr/VRAM
evidence. All six prompts completed once with zero retries. Manual review
recorded 2 pass, 3 mixed, and 1 fail verdict (3.71 / 5 reviewer average), with
unsupported claims and instruction failures preserved rather than repaired.

The package is a new bounded source. It does not modify or supersede the legacy
Grug package, rescore Qwen, establish a regression, or support ranking,
recommendation, safety, or generalized fit claims.

### Completed provenance-refresh practical comparison addendum

**Completed:** the separate
[Grug provenance-refresh practical comparison addendum](evidence/comparisons/grug-vs-qwen3-6-practical-v1/PROVENANCE_REFRESH_ADDENDUM.md)
incorporates the refreshed Grug source without replacing the original
two-package comparison.

The addendum preserves legacy Grug, refreshed Grug, and Qwen3.6 as distinct
evidence roles; verifies their exact six byte-identical public prompts; and
places provenance, suite-path, command, runtime, hardware, timing, completion,
and source-integrity differences before response-specific observations. It
retains every reviewed verdict and material failure label, treats package
averages as descriptive metadata only, and makes no regression, winner,
ranking, recommendation, or generalized fit claim.

### General evaluation taxonomy contract

**Completed:** the accepted
[general evaluation taxonomy](GENERAL_EVALUATION_TAXONOMY.md) defines native
response, performance benchmark, external text benchmark, and agent-environment
evaluation as distinct classes with explicit authority, scoring, comparison,
provenance, and integration boundaries. This architecture milestone adds no
evaluation behavior.

### Current suite and prompt architecture review

**Completed:** the
[current suite and prompt review](CURRENT_SUITE_PROMPT_REVIEW.md) inventories
all five tracked native suite identities and their prompts, ownership, scoring,
evidence dependencies, overlap, and capability coverage. It preserves the
historical Practical v0.1.0 evidence boundary, keeps practical, performance,
external benchmark, and agent-environment work distinct, and recommends a
bounded future smoke/Core/optional-profile structure without changing suites or
writing prompts.

### Generic Core suite contract

**Completed:** the accepted
[Generic Core suite contract](GENERIC_CORE_SUITE_CONTRACT.md) defines the
`generic-core-v1` identity and initial version, smoke/Core profile relationship,
capability coverage, scoring roles, comparison boundaries, current-suite
coexistence, and gates for later prompt design. This architecture milestone
adds no prompts or evaluation behavior.

### Generic Core prompt and scoring design

**Completed:** the
[Generic Core prompt and scoring design](GENERIC_CORE_PROMPT_SCORING_DESIGN.md)
fixes the proposed `generic-core-v1` `0.1.0` prompt-role inventory, all 13
primary capability owners, ordered Smoke/Core membership, task-family and
fixture ownership, deterministic-check feasibility, and manual/hybrid scoring
provenance. It adds no executable suite, final prompt, fixture, schema, loader,
scoring, or runtime behavior.

### Generic Core schema and loader contract

**Completed:** the accepted
[Generic Core schema and loader contract](GENERIC_CORE_SCHEMA_LOADER_CONTRACT.md)
defines additive profile-aware manifest fields, exact ordered membership,
capability and scoring metadata, contained versioned references, normalized
loader output, legacy-suite compatibility, and fail-closed diagnostics. It adds
no schema model, loader, manifest, suite, fixture, scoring, CLI, or result
behavior.

### Generic Core schema model and validation

**Completed:** the additive profile-aware suite manifest model now validates
ordered profile declarations, capability and stressor metadata, scoring-role
references, and lexical fixture references while preserving unchanged legacy
manifests and their source/package behavior. Generic Core content, scoring
execution, CLI behavior, and result provenance remain deferred.

### Generic Core profile selection and reference resolution

**Completed:** the normalized suite loader now selects declared default or
requested profiles, records legacy-all and disclosed custom membership, and
resolves prompt and fixture references as contained regular files while keeping
portable relative identities separate from private host paths. Editable and
packaged definitions retain equivalent portable normalization and owned bytes.

### Generic Core fixture and package-data support

**Completed:** the versioned suite-owned `generic-core-v1` resource tree now
provides D5 coding cases and execution-limit metadata, bounded-context excerpts
and reconciliation data, and the remaining deterministic mappings required by
the accepted design. Exact source/package mirrors are included in source
distributions, wheels, and isolated installations without creating the suite
manifest, final prompts, scoring execution, or runtime behavior.

### Generic Core compatibility and security hardening

**Completed:** focused negative-path and regression coverage now protects the
accepted profile-aware schema, selection, contained resource, package-data,
source/package portability, bounded-diagnostic, legacy-suite, and historical
source-only-suite contracts. No Generic Core manifest, prompt, scoring, CLI,
result, or runtime behavior is added.

## v0.72 completed release scope

The following profile-aware suite foundation is complete in `v0.72`:

- reviewed practical evidence packages, a bounded comparison, and a
  provenance-refresh comparison addendum;
- preservation of the historical Practical v0.1 source and its authority and
  equivalence contract;
- the general evaluation taxonomy and current-suite architecture review;
- Generic Core suite, prompt/scoring, and schema/loader architecture and design;
- additive profile-aware schema validation;
- normalized profile and custom selection with contained prompt and fixture
  reference resolution;
- versioned Generic Core fixture and package-data support;
- Generic Core compatibility and security hardening; and
- source-only-suite CI repair.

This foundation does not make `generic-core-v1` executable. Details remain in
[CHANGELOG.md](../CHANGELOG.md).

## Full Model Testing Capability Architecture

**Completed:** the accepted
[Full Model Testing Capability Architecture](FULL_MODEL_TESTING_CAPABILITY_ARCHITECTURE.md)
classifies current support, fixes evidence and trust boundaries, defines
prerequisite contracts and dependencies, and records the fast-track order and
release gates. This architecture milestone adds no suite, schema, importer,
metric, runtime, multimodal, non-autoregressive, or execution behavior.

## Coding-suite architecture and scoring contract

**Completed:** the accepted
[Coding Suite Architecture and Scoring Contract](CODING_SUITE_ARCHITECTURE_SCORING_CONTRACT.md)
defines the future `coding-core-v1` native single-turn identity, required
capability and task-family boundaries, evidence authority, scoring roles,
comparison eligibility, coexistence, and generated-code containment split. It
adds no prompt, schema, suite, scoring, transcript, importer, execution, or
runtime behavior.

## Coding-suite prompt and task-family design

**Completed:** the proposed
[Coding Suite Prompt and Task-Family Design](CODING_SUITE_PROMPT_TASK_FAMILY_DESIGN.md)
fixes eight static prompt roles and primary capability owners, deliberate
secondary overlap, suite-owned input types, permitted response forms, exact
Smoke/Core membership, and scoring authority per role. Repair after compiler or
test feedback remains multi-turn-only. This design adds no final prompt,
fixture, schema, suite, scoring, execution, or runtime behavior.

## Coding-suite scoring-method design

**Completed:** the accepted
[Coding Suite Scoring-Method Design](CODING_SUITE_SCORING_METHOD_DESIGN.md)
fixes the versioned coding manual rubric, three non-executing structural checks,
side-by-side hybrid composition, role applicability, scoreability, and bounded
profile/custom summaries. Five roles remain manual and three remain hybrid; no
deterministic-only role or universal coding score is admitted.

## Coding-suite schema and loader contract

**Completed:** the accepted
[Coding Suite Schema and Loader Contract](CODING_SUITE_SCHEMA_LOADER_CONTRACT.md)
fixes the smallest additive `llmgauge.suite.v0` representation, exact coding
profiles and method references, normalized identity, contained resources,
source/package/installed ownership, compatibility, and fail-closed validation.
No manifest schema-version change, executable suite, or scoring behavior is
added.

## Coding-suite schema model and loader implementation

**Completed:** the accepted five optional generic fields, controlled coding
vocabularies, normalized logical references, and exact `coding-core-v1`
`0.1.0` inventory, profile, response-form, scoring-reference, static-interaction,
and non-execution invariants are implemented. Existing suites retain their
prior requirements and identities. Contained-resource and public-safe
diagnostic behavior remain fail closed. This does not install or make Coding
Core runnable and adds no suite content, scoring execution, or result behavior.
The Full Model Testing order, completed LocalMaxxing integration, downstream
Generic Core work, and the `v0.73` gate remain separate.

## Coding-suite content and package implementation

**Completed:** `coding-core-v1` `0.1.0` now provides the final eight static
single-turn prompts, exact Smoke/Core profiles, inert versioned response-form
definitions, and byte-identical editable and packaged suite trees. The suite is
loadable and discoverable from editable, packaged, and isolated installed
resources, validates through the existing manifest path, and is included in
local wheels and source distributions. The existing native-response path admits
its manifest, profile, and prompt selection and can prepare a command plan
through `--dry-run`; no live model process, completion, scoring pass, or
answer-quality evidence exists. No Coding Core-specific loader, registry,
runner, or CLI path was added, and no generated response content is applied,
imported, or executed.

## Coding-suite static deterministic-check and scoring integration

**Completed:** `coding-core-v1` `0.1.0` now registers the accepted manual
rubric, three non-executing structural checks, and side-by-side hybrid
composition through the existing scoring interfaces. Manual templates expose
only each prompt's applicable dimensions, reviewed values retain rationale and
provenance, and Coding Core profile summaries do not aggregate a numeric score.
Deterministic methods consume only preserved raw response text and selected-root
versioned response forms; they preserve `pass`, `fail`, `error`, and `not_run`
without applying or executing generated content.

## Coding-suite native run/result/report integration

**Completed:** native `coding-core-v1` `0.1.0` runs now preserve portable exact
profile/custom selection and per-prompt response-form and scoring-method
provenance. The accepted static checks consume authoritative raw response
evidence after capture and retain generation status separately from structural
`pass`, `fail`, `error`, and `not_run`. Manual score application derives honest
review states and recomposes independent side-by-side hybrid evidence without
rerunning checks or creating a numeric Coding Core aggregate. Additive result
validation fails closed on malformed represented evidence while retaining
legacy compatibility. Native reports expose prompt-level evidence and explicit
non-execution, structural, semantic-authority, incompleteness, and scoring claim
boundaries. Public export and export-index behavior are unchanged.

## Coding-suite bounded live evidence

**Completed:** one human-controlled, bounded `coding-core-v1` `0.1.0` `smoke`
run with `gemma4_12b_qat_q4` (Gemma 4 12B IT QAT UD-Q4_K_XL) completed all
four selected prompts. Manual semantic verdicts were `pass` for
`debug/state-transition-defect`, `patch/bounded-cross-file-change`, and
`structured/closed-json-change-record`, and `fail` for
`shell/safe-repository-maintenance`. The independent deterministic structural
outcomes were `fail` for `patch/bounded-cross-file-change` and
`structured/closed-json-change-record`; both hybrid records are complete, and
no Coding Core profile-level numeric score exists.

The preserved scored result passes repository validation on merged `main` at
`f80860f`. No generated code, patch, test, JSON action, or shell command was
executed or applied. This private bounded evidence does not establish
publication readiness, universal model quality or safety, model ranking,
effective full GPU offload, or effective flash-attention behavior.

## Multi-turn transcript architecture

**Completed:** the accepted
[Multi-turn Transcript Architecture](MULTI_TURN_TRANSCRIPT_ARCHITECTURE.md)
defines the versioned native conversation identity, ordered turn and observable
state model, feedback provenance and exact consuming-turn association,
completion/retry/recovery semantics, scoring authority, source/derivative,
privacy, compatibility, comparison, validation, and Agent Harness boundaries.
It adds no schema or executable behavior, and existing single-turn results
remain valid without reinterpretation or migration.

## Multi-turn transcript schema and native evaluation behavior

**Completed:** the accepted
[Multi-turn Transcript Schema and Native Evaluation Contract](MULTI_TURN_TRANSCRIPT_SCHEMA_CONTRACT.md)
selects one separately versioned contained `llmgauge.transcript.v0` authority
referenced additively by `llmgauge.result.v0`. The implementation preserves
canonical ordered task, model-attempt, supplied inert feedback, observable
state, retry/recovery, branch, final-selection, and terminal evidence; validates
contained source artifacts fail closed; orchestrates bounded sequential native
conversations through existing llama.cpp and operator-managed local vLLM
request boundaries; discloses non-executing dry-run plans; fingerprints
immutable transcript evidence; and generates bounded transcript-aware reports.

Synthetic successful, retry/recovery, timeout/failure, partial, turn-limit,
llama.cpp, and external-vLLM paths pass focused and full repository validation
without launching a real model or executing generated content. Ordinary
single-turn result shape and fingerprints remain unchanged when transcript
evidence is absent. Current single-turn scoring, comparison, and public export
fail closed for transcripts; no universal multi-turn score is implemented. The
deferred Coding Core `repair/prior-response-test-feedback` role remains absent.

## Agent Harness import contract and read-only importer

**Completed:** Full Model Testing orders 3a and 3b. The accepted
[Agent Harness Import Contract](AGENT_HARNESS_IMPORT_CONTRACT.md) fixes one
`llmgauge.agent_harness_evidence.v0` external agent-environment identity for
read-only WumboLabs OMP session-v3 evidence. The implementation adds strict
bounded source detection and normalization, exact contained session/object
copying, privacy and containment gates, atomic result publication, structural
validation, the additive result reference, imported-evidence fingerprinting,
and fail-closed native-consumer recognition.

The importer does not replay or resume sessions, inspect or mutate repositories,
execute commands/tools/tests, contact models/providers/networks, convert to a
native transcript, score or compare agents, generate a native report or public
export, run a live Agent Harness, publish evidence, or perform release work.
Ordinary and native-transcript results retain their existing behavior and
fingerprint payloads.

## Agent-session scoring and reporting

**Completed:** Full Model Testing order 3c implementation. The accepted
[Agent-session Scoring and Reporting Contract](AGENT_SESSION_SCORING_REPORTING_CONTRACT.md)
and [Agent-session Review Interface Contract](AGENT_SESSION_REVIEW_INTERFACE_CONTRACT.md)
now have one bounded `agent-session-review-v0` manual-review implementation:
closed mutable review metadata, exact imported-evidence binding, inert contained
source references, atomic template/apply workflows, deterministic check, and a
separate seven-section Agent Harness review report.

The implementation adds the dedicated Agent Harness review workflow. It changes
no existing source or result schema, importer semantics, structural
`validate-result` semantics, fingerprint semantics, or existing native consumer
semantics. Comparison, public export, publication, export-index, runtime-neutral
metrics, expanded failure taxonomy, and the optional evidence observation method
remain deferred.

The completed Full Model Testing work preserves its remaining deferred areas.
LocalMaxxing is operational as a separate performance-benchmark integration;
downstream Generic Core work and the existing `v0.73` gate remain unchanged.
No release-version decision is made.

## Full-model-testing fast-track programs

### Full Model Testing capability program

The fast track covers these required capability areas:

1. a dedicated coding suite for debugging, minimal patches, tests and failure
   diagnosis, shell safety, dependency/API uncertainty, scope control,
   structured output, and repair after compiler or test feedback;
2. a multi-turn evaluation contract preserving state, every turn and response,
   test/tool feedback, correction, recovery, and consistency evidence;
3. read-only WumboLabs Agent Harness session evidence import covering repository
   inspection, edits, commands, tests, failures, recovery, final diff, and
   outcome while LLMGauge remains the evaluator;
4. runtime interoperability that matures the external local vLLM backend,
   generalizes only honest OpenAI-compatible transport behavior, preserves exact
   request/response and stack provenance, and admits later local runtimes
   separately;
5. runtime-neutral latency, TTFT, prefill, generation, load-time, VRAM, offload,
   and hybrid-execution metrics with native provenance and non-equivalence
   boundaries;
6. multimodal image, audio, and video evaluation with preserved inputs,
   modality-specific scoring and failures, and explicit capability boundaries;
7. diffusion and other non-autoregressive generation with native steps,
   configuration, timing, and metrics that do not assume token decoding;
8. reasoning and sampling profiles covering reasoning `on`, `off`, and `auto`,
   vendor-aligned and controlled settings, complete sampling/template capture,
   and profile-aware bounded comparisons; and
9. an expanded failure taxonomy for runtime environment, unsupported
   architecture/quantization/kernel, weight-load OOM, KV-cache OOM, endpoint,
   tool, generation, malformed-response, and agent-recovery failures.

The completed prerequisite sequence is Coding Core, native multi-turn
transcripts, Agent Harness import, Agent Session Review, the Area 4
first native llama.cpp slice, the external-benchmark interoperability
contract, the external-benchmark importer foundation, and Bundle 1
qualification/reporting. The selected next development order is:

1. D. LocalMaxxing quality-benchmark export, dry-run, and
   `--confirm-public` submit, only after an approved matching suite path
   exists;
2. E. Generic Core v1 completion; and
3. F. reasoning and sampling profile work.

The remaining multimodal and non-autoregressive areas remain later fast-track
work. External-benchmark milestones preserve official benchmark authority and
do not authorize recreating their prompts as native LLMGauge suites. Each
numbered area remains subject to the bounded contract, dependency, schema,
implementation, integration, and release gates defined by the architecture.
The order is a program sequence, not authorization to combine milestones or
describe deferred capability as current behavior.

### Area 4 first native llama.cpp slice implemented

The [Runtime-neutral Metrics and Expanded Failure Taxonomy Contract](RUNTIME_NEUTRAL_METRICS_FAILURE_TAXONOMY_CONTRACT.md)
now has its first bounded implementation: optional per-prompt measured
request-wall-time evidence for native single-turn llama.cpp execution, plus
derived failure observations limited to launch-environment failure,
model-weight-load OOM, KV-cache OOM, and unclassified unknown. Native
prompt/generation throughput remains non-neutral; TTFT, vLLM, transcripts,
comparisons, reporting/export expansion, and all other Area 4 categories remain
deferred. Historical results remain valid unchanged.

### External benchmark importer foundation

**Completed:** Milestone B implements read-only import of supported
EleutherAI `lm-eval` result JSON into
`llmgauge.external_benchmark_evidence.v0` under a dedicated
`llmgauge.result.v0`. Contained source copies remain authoritative;
normalized evidence records source-backed identity and native metrics
without inventing missing metadata or a universal score. CLI:
`llmgauge benchmark import` and `llmgauge benchmark validate`.

### Bundle 1 qualification and reporting

**Completed:** Milestone C pins official Bundle 1 identities against
EleutherAI `lm-evaluation-harness` `v0.4.12` and adds read-only
`llmgauge benchmark report`. Qualification is computed at report time
and is not persisted into evidence. Generic lm-eval import remains valid
when a result is not Bundle 1-qualified. HumanEval and MBPP remain
import-only; LLMGauge does not execute generated code. See
[Bundle 1 qualification](BUNDLE1_QUALIFICATION.md). LocalMaxxing quality
export/submit remains later. Public LocalMaxxing support for Bundle 1 is
still shard-eval or plus-variants, not official lm-eval metrics. The
existing `llmgauge localmaxxing` namespace remains speed-only.

The accepted
[interoperability contract](EXTERNAL_BENCHMARK_LOCALMAXXING_INTEROP_CONTRACT.md)
remains the authority/identity contract.


### LocalMaxxing performance-benchmark integration

**Operational on `main`:** the LocalMaxxing integration provides a versioned
local artifact, llama.cpp-first benchmark method, offline validation and export,
and explicit authenticated dry-run and public-submit boundaries. It remains
distinct performance evidence under the
[general evaluation taxonomy](GENERAL_EVALUATION_TAXONOMY.md), never a normal
quality-suite side effect.

The method records additive, source-backed hardware, NVIDIA telemetry,
llama.cpp runtime, combined-throughput, and localhost TTFT companion evidence
when probes succeed. Optional metrics remain absent when unproven; they do not
alter core speed-method semantics or make Area 4 implemented. Network use is
limited to the explicit `dry-run` and `submit` commands; public submission
requires explicit confirmation and no ordinary command publishes, submits, or
polls.

Future Area 4 measurements may feed the LocalMaxxing exporter without changing
its public benchmark semantics. Full Area 4 remains later work beyond the
first native llama.cpp slice, and LocalMaxxing does not alter the `v0.73`
Generic Core release gate.

## Admitted downstream Generic Core delivery

Generic Core suite implementation is no longer the selected next milestone, but
it remains admitted downstream work under its existing accepted contracts and
resources. Its relationship to the fast track is complementary: Generic Core
provides a general native text suite and reusable profile/resource foundations;
it does not replace the dedicated coding suite, multi-turn transcript, Agent
Harness import, runtime-neutral metrics, or later modality/generation contracts.

The existing separate Generic Core delivery path remains:

1. Generic Core fixture and package-data support (completed).
2. Generic Core compatibility and security hardening (completed).
3. `v0.72` release preparation (completed).
4. Generic Core suite implementation with the final manifest, 13-prompt
   inventory, fixture references, and exact Smoke/Core membership (admitted
   downstream).
5. Deterministic checks D1-D7.
6. Separate D5 generated-code containment gate.
7. Execution and result-provenance integration.
8. `v0.73` release preparation.

Each item remains a separate bounded milestone unless a later accepted handoff
explicitly combines milestones. Release preparation does not begin until its
preceding implementation and validation gates are complete.

## Release gates

### `v0.72` — Profile-aware suite foundation

**Completed:** the `v0.72` release contains:

- the additive profile-aware schema;
- normalized profile and custom selection;
- contained prompt and fixture reference resolution;
- fixture and package-data support;
- compatibility and security hardening;
- source/package equivalence;
- clean source-checkout, wheel, sdist, and isolated installed-CLI validation;
  and
- release metadata and documentation updates.

`v0.72` does not claim that `generic-core-v1` is available. It includes the
profile-aware foundation and versioned Generic Core package resources, but no
suite manifest or final prompts.

### `v0.73` — Generic Core v1

The `v0.73` release gate requires:

- an implemented `generic-core-v1` suite at version `0.1.0`;
- its final 13-prompt inventory;
- exact `core` and `smoke` profiles;
- committed fixtures;
- supported scoring references;
- deterministic checks D1-D7;
- D5 generated-code containment resolved under an accepted safe local contract
  or explicitly redesigned through a separate accepted contract;
- selected profile and exact ordered membership provenance in results;
- clean installed-package and CI validation; and
- release metadata and documentation updates in the separate `v0.73`
  release-preparation milestone.

These gates assign no release dates.

## Parallel product tracks

These future product tracks remain separate from the completed architecture
milestone, the selected coding-suite contract, the fast-track program sequence,
Generic Core delivery, and one another.

### Packaging and productization

- PyPI readiness and publication, without claiming current PyPI availability.
- Validated `uv tool install llmgauge` and `pipx install llmgauge` workflows
  after publication.
- Wheel, sdist, and isolated-install tests.
- Release automation.
- Upgrade and uninstall workflow.
- User configuration, data, and cache path review.
- `doctor` and guided setup polish.
- Standalone executable and container feasibility later.

The currently validated installed-user path remains the Git-tag installation
documented in [Installation](INSTALL.md). PyPI availability is not yet claimed.

### Runtime interoperability

1. vLLM completion and product audit.
2. Shared OpenAI-compatible HTTP transport contract.
3. SGLang adapter.
4. Ollama adapter.
5. TensorRT-LLM or NVIDIA NIM later.
6. Heterogeneous platform provenance.

`llama.cpp` remains the default runtime. The current vLLM adapter remains a
bounded, operator-managed local integration. DGX Spark is a hardware/platform
provenance target, not a backend; support should use whichever separately
admitted runtime actually runs on that platform. Runtime work enters the
fast-track order only through its separately accepted contracts.

## Expanded evaluation track

External benchmark work follows the completed Area 4 first native slice
and the completed interoperability contract plus importer foundation.
The track remains separate from LLMGauge-owned native suites, the Full
Model Testing capability program, LocalMaxxing performance
benchmarking, and agent-environment evaluations:

1. A. external benchmark and LocalMaxxing interoperability contract
   (completed);
2. B. external benchmark importer/foundation (completed);
3. C. first mainstream external benchmark bundle (completed);
4. D. LocalMaxxing quality export / dry-run / explicit submit, only after
   an approved matching suite path exists;
5. additional external text benchmark read-only imports, including the
   separate Bundle 2 investigation;
6. Agent drift evaluation contract;
7. Terminal-Bench/Harbor contract and read-only import;
8. SWE-bench; and
9. Browser, computer-use, and OSWorld later.

MMLU, ARC Challenge, HellaSwag, WinoGrande, TruthfulQA MC2, GSM8K,
HumanEval, and MBPP are qualified as Bundle 1 against the pinned
`v0.4.12` identities. MMLU-Pro, GPQA, and IFEval remain later Bundle 2
work. Generic lm-eval import is not by itself a Bundle 1 completion
claim. Any later integration preserves the external dataset, harness,
and official metric as authoritative; LLMGauge does not recreate them as
native prompts. LocalMaxxing official shard evals and plus-variants are
not those official metrics.

These items retain the distinct evaluation classes and evidence authorities
defined by the [general evaluation taxonomy](GENERAL_EVALUATION_TAXONOMY.md).

## Recently completed releases

Condensed highlights (newest first). Details remain in [CHANGELOG.md](../CHANGELOG.md).

| Release | Focus |
|---|---|
| v0.72 | Profile-aware suite schema, normalized selection, contained references, Generic Core package resources, and compatibility/security hardening; no executable `generic-core-v1` suite |
| v0.71 | Optional external local vLLM adapter, additive fingerprint evidence, public-export identity redaction, first tracked practical evidence package |
| v0.70 | Identity, provenance, evidence-equivalence fingerprints, and sanitized public export foundations; validated released install tag |
| v0.66 | Runtime reproducibility — command metadata, reasoning-mode metadata, model-source reporting |
| v0.65 | Guided setup / first-run onboarding (`setup`, scan, non-interactive modes) |
| v0.64 | Clean-clone readiness and pre-public-proof documentation hardening |
| v0.63 | Result artifact audit polish — Audit Checklist, Prompt Artifact Audit |
| v0.62 | Public report artifact polish — Report Scope, Evidence Summary, Comparison Scope |
| v0.61 | Export/index/report integration — artifact roles, export-index scoring fields |
| v0.60 | Public-proof workflow hardening — checklist, CLI guidance, validation caveats |
| v0.59 | Scored comparison evidence — publish-readiness and export-index scoring fields |
| v0.58 | Practical suite polish — prompt audit and metadata |
| v0.57 | Suite and scoring maturity — rubric guidance, scoreability docs |

Earlier foundations (v0.46–v0.56 and before) established artifact schemas, validation, scoring, comparison, fit ladder, model profiles, CLI modularization, and public documentation.

### v0.71 release notes (historical)

The following v0.71 work is complete on `main`:

- optional externally managed local vLLM backend for single `run` (loopback-only
  stdlib transport; readiness and served-model checks)
- additive vLLM version, API-ready server-state, and system-fingerprint evidence
- fail-closed rejection of `backend=vllm` for batch, ladder, and Fit Ladder
- public-export redaction of local hostname and username tokens
- bounded live, cross-runtime, Gemma, and Fit Ladder evidence records
- first tracked reviewed practical public evidence package (Grug-12B)

Default runtime remains llama.cpp. No remote/authenticated/streaming/concurrent
vLLM support, ranking claims, Gemma viability generalization, or PyPI claim.
Packaging and clean-clone checks validate installation and CLI readiness, not
model quality.

### Selected earlier release context

- **v0.70** established identity, provenance, evidence-equivalence fingerprints,
  and sanitized public export foundations as a validated released install.
- **v0.66** added structured `runtime-command.json`, bounded `reasoning_mode`
  metadata, and `model_source` reporting for public-proof reproduction.
- **v0.65** added `llmgauge setup` as the preferred first-run path while
  preserving manual `init` fallback; no model downloads or automatic launches.
- **v0.64** hardened docs and clean-clone readiness before real-world validation.

## Later roadmap / parking lot

These are optional or exploratory. They are not core commitments:

- optional website publication helpers
- optional Monolith import/read-only integration (not core)
- richer comparison summaries when deterministic and schema-safe
- package/release automation improvements
- CI/doc automation
- model profile UX polish
- context-size and fit-ladder reporting polish
- optional static report browsing helpers

**Non-goals for later work:**

- automatic LLM-as-judge scoring
- leaderboard or universal ranking
- network submission by default
- production-readiness or daily-driver recommendations from scores alone

## Release discipline / public-proof rules

1. Feature branches from `main` with focused commits.
2. Local full gate before handoff: `uv run pytest`, `uv run ruff check .`, `git diff --check`.
3. Release metadata (`pyproject.toml`, `__init__.py`, `CHANGELOG.md`, lockfile) in a separate release-prep step — not mixed into feature work.
4. Annotated tags only after release metadata merges to `main`.
5. Preserve raw outputs, failed attempts, and scoring provenance in all workflows.
6. Manual scoring remains the trusted path; auto-drafts stay review-required until applied and reviewed.
7. Public claims require disclosed hardware, runtime, suite, scoring status, and artifact evidence.
8. Comparison reports and export index are evidence metadata — not model recommendations.

## Working rule

For every proposed task, ask:

> Does this make LLMGauge better at producing defensible public evidence about local models on real consumer hardware?

If yes, it belongs on the roadmap. If it is only private progress, model chasing, UI polish, or architecture expansion without evidence value, park it.
