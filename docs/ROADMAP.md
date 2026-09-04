# LLMGauge Roadmap

LLMGauge is a conservative local-first CLI for practical LLM evaluation on real consumer hardware.

The project produces defensible, reproducible public evidence about usefulness, honesty, correctness, safety, speed, VRAM headroom, and workflow fit under disclosed hardware and runtime conditions.

LLMGauge is part of the WumboLabs workflow: **Real Hardware. Real Testing. No Hype.**

## Current release line

- Current stable tag: `v0.78` (published)
- Current package version: `0.78.0`
- Current stable release line: `v0.78.0`
- Current release state: `v0.78` is the Area 4 evidence-integrity and
  qualification hardening release (published to production PyPI as
  `llmgauge` 0.78.0): qualified current llama.cpp native-diagnostics
  capture admitted by a frozen upstream runtime-lineage manifest, and
  vLLM streaming TTFT validator hardening that recomputes the first-token
  channel from preserved raw stream evidence. Production PyPI publication
  completed through the human annotated-tag / protected `pypi` gate.
  v0.77 remains the previous Area 4 runtime-evidence stabilization
  release (published as `llmgauge` 0.77.0). v0.76 remains the multi-turn
  transcript comparison and safe public derivative release (published as
  `llmgauge` 0.76.0), and v0.75 remains the reasoning/sampling profile
  release (published as `llmgauge` 0.75.0).

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
  (`backend=vllm`; operator-managed, loopback-only, sequential; non-streaming
  by default, with an opt-in streaming SSE evidence mode)
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
- pinned Bundle 2 read-only import qualification (`llmgauge.bundle2.v0`)
- named/versioned reasoning and sampling profiles via `--sampling-profile`
  with deterministic content identity, result/fingerprint persistence, and
  comparison provenance disclosure
- four primary-source-qualified vendor-aligned built-in profiles plus the
  neutral `controlled-deterministic-v1` profile
- offline profile discovery and introspection (`llmgauge profiles list`,
  `llmgauge profiles show PROFILE_ID`)
- requested `--min-p` sampler capture across run metadata and comparison scope
- derived device-scoped peak VRAM evidence for native llama.cpp results
- Area 4 runtime-neutral request-wall-time mapping for external vLLM results
  (request transmitted → validated response boundary; TTFT, prefill/decode
  throughput, and placement remain deferred under the non-streaming default)
- opt-in vLLM streaming evidence mode (`--vllm-streaming-evidence`) using the
  vLLM-specific `return_token_ids=true` SSE extension: runtime-neutral TTFT
  (`llmgauge.metric.v1.time_to_first_token`) measured from the first
  backend-generated token ID at the LLMGauge transport boundary, with preserved
  private per-request stream evidence; reasoning tokens count under the
  resolved human contract; the non-streaming default is unchanged
- Area 4 request-window peak VRAM evidence for external vLLM results:
  `llmgauge.metric.v1.peak_vram` calculated from a bounded concurrent
  NVIDIA telemetry sampler active only during the LLMGauge evaluation
  request window (absolute device-used memory, not server/model
  footprint; distinct from the llama.cpp process-window boundary)
- bounded structural comparison of all-transcript result sets via
  `llmgauge compare` with explicit eligibility, three-way structural
  classification, role/order-preserving listings, and recorded review-hook
  disclosure
- content-default-deny public transcript comparison derivative
  (`llmgauge export-public-comparison`, schema
  `llmgauge.public_transcript_comparison.v0`)
- content-default-deny public single-transcript derivative
  (`llmgauge export-public-transcript`, schema
  `llmgauge.public_transcript.v0`)

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
HumanEval, and MBPP and adds `llmgauge benchmark report`. Bundle 2
(MMLU-Pro, GPQA, IFEval) qualification is now complete as read-only
`llmgauge.bundle2.v0` import qualification (see Bundle 2 qualification below);
both bundles must be imported under those official contracts, not recreated
as native LLMGauge prompts. LocalMaxxing official shard evals are a different
protocol and are not interchangeable with official lm-eval metrics.

## vLLM evidence track

The vLLM work is intentionally bounded to an externally managed local
integration and evidence collection. The accepted [runtime contract](VLLM_RUNTIME_CONTRACT.md)
and [HTTP transport assessment](VLLM_HTTP_TRANSPORT_ASSESSMENT.md) define a
loopback-only, text-only backend using the Python standard library. LLMGauge
does not install, start, supervise, or otherwise own the vLLM server lifecycle;
`llama.cpp`/GGUF remains the default runtime.

This bounded external-server integration is the current state, not the target:
the accepted
[first-class multi-runtime architecture contract](FIRST_CLASS_RUNTIME_ARCHITECTURE.md)
defines the program that matures vLLM, ExLlamaV3 (and later SGLang) to
first-class runtime and native directory-checkpoint support, including
managed-local server lifecycle.

### Implemented capability

- External local vLLM adapter with sequential requests to an operator-managed
  loopback server; non-streaming is the default, and streaming SSE evidence is
  an explicit opt-in mode.
- Bounded readiness and served-model checks; no remote, authenticated,
  concurrent, or server-lifecycle management support.
- Additive runtime evidence for server `/version`, API-readiness state, optional
  `system_fingerprint`, and ordered-unique run-level fingerprints, with
  backward-compatible validation, reporting, and export handling.
- Area 4 runtime-neutral request-wall-time mapping for transmitted requests:
  `llmgauge.metric.v1.request_wall_time` with explicit boundary, provenance,
  equivalence, and evidence references. Prefill/decode throughput,
  model-load time, steady-state VRAM, and execution placement remain
  unavailable or deferred.
- Area 4 runtime-neutral TTFT for streaming evidence mode:
  `llmgauge.metric.v1.time_to_first_token` measured from the same request
  start boundary to the first backend-generated token ID exposed in an
  admitted completion-stream event (first reasoning token counts; first
  final-answer content token counts when no earlier generated token occurred;
  empty-decoded tokens count when token-ID evidence proves them). Preserved
  private per-request stream evidence makes TTFT recomputable; the validator
  cross-checks the represented record against that evidence.

### Validated behavior and methodology

The adapter's real-runtime behavior was exercised by bounded operator-local
smoke runs (readiness, request, validation, reporting, and server
`/version`/fingerprint capture). Those run records were evaluation artifacts
and are not tracked in this repository; historical statements about them are
preserved in the changelog. Durable claim boundaries live in
[VLLM_RUNTIME_CONTRACT.md](VLLM_RUNTIME_CONTRACT.md).

- [Cross-runtime comparison methodology](VLLM_CROSS_RUNTIME_COMPARISON_METHODOLOGY.md):
  runtime-native metrics, input/template disclosure, and bounded claim rules.

### Active limitations

- No remote, authentication, or concurrency support; no LLMGauge-owned vLLM
  lifecycle. Streaming is an explicit opt-in evidence mode, never the default.
- vLLM request-window peak VRAM is captured via a bounded concurrent NVIDIA
  telemetry sampler; the value is absolute device-used memory, not server or
  model footprint, and the observation boundary is distinct from the native
  llama.cpp process-window boundary.
- Streaming TTFT V1 is implemented for backend=vllm under
  `--vllm-streaming-evidence` with the vLLM-specific `return_token_ids=true`
  extension; it is version-qualified (admitted for observed vLLM 0.27.1 only;
  V1 admits exactly the qualified version, not a range) and never fallbacks to
  a second non-streaming request. Reasoning tokens count as generated-token
  TTFT events when exposed by the backend; canonical generated
  answer text remains final `content` only. Prefill/decode throughput,
  model-load time, and steady-state VRAM remain deferred; execution placement
  is not exposed by the vLLM API; cache state remains unknown (API readiness
  does not imply warm or cold).
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

The bounded vLLM evidence track includes opt-in streaming TTFT evidence and its
public-projection privacy boundary. Single-run public derivatives omit all
known TTFT aliases/refs, private stream/token and reasoning evidence, and local
endpoint identity while retaining admitted coarse transport disclosure. v0.77
is published; post-v0.77 `main` reaffirmed the exact-version-only streaming
TTFT qualification (vLLM 0.27.1), validated the reasoning-first TTFT path on
real vLLM 0.27.1 evidence (Qwen3-0.6B), and hardened the Area 4 validator to
recompute the first-token channel from preserved raw stream evidence.
Prefill/decode throughput, model-load time, steady-state VRAM, warm/cold
lifecycle evidence, and observed execution placement remain deferred; Area 4
overall is not marked complete. The planned WumboJets
normal-published-package multi-model validation remains a separate
outside-development-environment campaign.

## Fit Ladder terminal-path validation

Both principal Fit Ladder terminal paths — total failure after all planned
contexts, and success after fallback — were validated by bounded operator-local
runs. Those run records were evaluation artifacts and are not tracked in this
repository; historical statements about them are preserved in the changelog.
The sanitized statement of those validated terminal behaviors lives in
[FIT_LADDER.md](FIT_LADDER.md).

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

### Historical Practical Suite v0.1.0 source

**Completed (later retired):** the historical `wumbolabs-practical-use-v1`
version `0.1.0` source was formerly tracked at `suites/` with its original
`suite.yaml`, six prompt files, suite identity, and prompt order preserved
without modernization, pinned by SHA-256 in a source-only mirror test. After all
tracked real-model evaluation artifacts were removed from this repository, the
source-only suite no longer served a current product purpose and was removed;
the sanitizer product invariant it exercised remains covered by synthetic
tests.

The existing `wumbolabs-practical-v1` version `0.2.0` suite remains a separate
identity. Historical byte-equivalence checks never established answer quality,
scoring correctness, privacy completeness, or publication readiness.

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
manifests and their source/package behavior. Generic Core deterministic
evidence now evaluates preserved raw response artifacts; D5 remains explicitly
non-executing.

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

### Generic Core suite content and discovery

**Completed:** `generic-core-v1` version `0.1.0` is now a real native suite
with the accepted 13-prompt Core inventory, exact Smoke subset, final portable
prompt wording, versioned fixture and scoring references, D1-D7 preserved-raw
deterministic evidence, and source/package discovery through the existing
profile-aware loader. D5 generated-code execution and the `v0.73`
release-preparation milestone remain deferred.

### Generic Core result-provenance integration

**Completed:** Generic Core results now carry fail-closed selection provenance
and full manual-review workflow support. Result validation rejects
inconsistent `generic-core-v1` suite identity, exact ordered profile or custom
membership, invocation metadata, or missing per-prompt evidence, while
replaying deterministic checks against authoritative raw responses. Native
reports expose selected profile/custom membership, scoring roles, check/rubric
identities and versions, deterministic/manual/hybrid component states, and D5's
explicit non-execution without inventing a numeric aggregate. Score templates
and applied scores use per-prompt applicable dimensions under
`default-manual-v0` `0.1.0`, require reviewed provenance, and recompose
side-by-side hybrid evidence without rerunning checks.

Executable generated-code evaluation remains deferred to a future Generic Core
suite version behind a separate accepted containment and resource-limit
contract; it is intentional `0.1.0` behavior, not outstanding `v0.73` work,
and the `v0.73` release gate no longer depends on it.

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

This foundation did not by itself make Generic Core scoring complete. Since
`v0.72`, unreleased `generic-core-v1` `0.1.0` content and D1-D7 evidence are
implemented with D5 deliberately `not_run`; executable generated-code
evaluation is deferred to a future suite version, not `v0.73` work. Details
remain in [CHANGELOG.md](../CHANGELOG.md).

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
evidence is absent. Current single-turn scoring and public export fail closed
for transcripts; no universal multi-turn score is implemented. Comparison has
a separate accepted bounded structural contract (next section). The
deferred Coding Core `repair/prior-response-test-feedback` role remains absent.

## Bounded transcript comparison and review presentation (completed in v0.76)

**Completed:** the accepted
[Transcript Comparison and Review Contract](TRANSCRIPT_COMPARISON_REVIEW_CONTRACT.md)
admits one bounded structural comparison surface: `llmgauge compare` routes an
all-transcript result set to eligibility classification over exact identity
fields (protocol, task, initial state and its SHA-256, suite, effective
limits), a three-way structural classification (identical structure,
structurally comparable, structurally incomparable with stated completion
asymmetry), side-by-side represented structural facts, role- and
order-preserving event listings, and recorded review hooks presented exactly
as stored. Mixed transcript/single-turn comparison fails closed. No session
aggregate, ranking, or winner claim exists; transcript-bearing public export
is a separately admitted export slice (next section).

## Transcript comparison public export (completed in v0.76)

**Completed:** the accepted
[Transcript Comparison Public Export Contract](TRANSCRIPT_COMPARISON_PUBLIC_EXPORT_CONTRACT.md)
admits one content-default-deny public derivative of a bounded transcript
comparison: `llmgauge export-public-comparison RUN_A RUN_B --out DIR` writes
exactly `transcript-comparison.json` (schema
`llmgauge.public_transcript_comparison.v0`) and `report.md`. The projection is
a closed allowlist of structural facts — eligibility booleans and identity
field names, three-way classification, sanitized model labels, integers,
closed vocabularies, and sequence-number-only event/state/attempt skeletons.
No content, private identifiers, or full hashes are projected; a closed-world
validator rejects any unexpected key or disallowed string. Admission is
fail-closed for non-pairs, non-transcript, mixed, imported-evidence,
malformed, or hash-mismatched sources and unsafe destinations; sources are
never modified and the write is staged. No aggregate, winner, or quality
verdict exists, and every artifact states that human review is required
before publication. The single-run `export-public` path keeps rejecting
transcript-bearing runs.

## Native single-transcript public derivative (completed in v0.76)

**Completed:** the accepted
[Native Single-Transcript Public Derivative Contract](NATIVE_TRANSCRIPT_PUBLIC_DERIVATIVE_CONTRACT.md)
admits one content-default-deny public derivative of a single
transcript-bearing run: `llmgauge export-public-transcript RUN --out DIR`
writes exactly `transcript-summary.json` (schema
`llmgauge.public_transcript.v0`) and `report.md`. The per-run structural
projection reuses the comparison derivative's primitives, so the same private
fact maps to the same public interpretation (slot label `run`, fallback model
label `Model`), plus closed protocol identity, the producer's numeric release
version, and declared/effective limits. No content, private identifiers, or
full hashes are projected; a closed-world validator rejects any unexpected key
or disallowed string. Admission is fail-closed for missing, non-transcript,
imported-evidence, malformed, or hash-mismatched sources and unsafe
destinations; sources are never modified and the write is staged. No score,
aggregate, or quality verdict exists, and every artifact states that human
review is required before publication. The single-run `export-public` path
keeps rejecting transcript-bearing runs.

## Deferred transcript work (not part of v0.76)

The v0.76 transcript layer is structural evidence only. The following remain
open and require separately accepted contracts before any implementation:

- publication of reviewed and deliberately redacted transcript text (raw
  prompt/response content remains excluded from every derivative);
- aggregate or session-level transcript scoring and any rubric-defined
  transcript score;
- statistical model comparison;
- richer transcript visualization;
- publication attestations or signatures for derivatives;
- semantic or LLM-based transcript judging.

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
native llama.cpp slices (request-wall time, peak VRAM, backend timing and
placement, current-diagnostics capture, runtime lineage qualification and
manifest), the external-benchmark interoperability contract, the
external-benchmark importer foundation, Bundle 1 and Bundle 2
qualification/reporting, Generic Core v1, and the reasoning/sampling
profile first slice. The leading admitted next development milestone is:

1. D. LocalMaxxing quality-benchmark export, dry-run, and
   `--confirm-public` submit, only after an approved matching suite path
   exists (the approved `LM_EVAL_HARNESS` suite path is not yet admitted;
   see the expanded-evaluation track).

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

A second bounded Area 4 slice adds optional device-scoped
`llmgauge.metric.v1.peak_vram` evidence for native llama.cpp results:
one record per observed GPU, computed (calculated provenance) from the
preserved per-prompt `nvidia-smi` samples with a versioned calculation
semantics, unavailable-not-zero fallback, and validator recomputation
against the preserved evidence. No cross-runtime VRAM equivalence is claimed.

A third bounded Area 4 slice preserves backend-native llama.cpp timing
(load, prompt-eval, eval/generation, total) and observed execution placement
from llama.cpp-owned diagnostics. Requested GPU layers never become observed
placement. N/N offload is recorded as native counts with observed `unknown`,
not `full_accelerator`. Neutral mappings for model-load time, prefill
throughput, decode throughput, and TTFT remain deferred. Steady-state VRAM,
vLLM Area 4, and cross-runtime equivalence remain deferred.

A fourth bounded Area 4 architecture milestone
([LLAMACPP_TTFT_OBSERVATION_ARCHITECTURE.md](LLAMACPP_TTFT_OBSERVATION_ARCHITECTURE.md))
qualified the TTFT observation question: neutral TTFT remains deferred under
the native llama.cpp CLI because the native `llama-cli` interface exposes only
decoded-text UI rendering on stdout with no machine-readable generated-token
boundary, an unconditional prompt echo, and no reliable generated-output
ownership. A proven token boundary is available only through the embedded
`llama-server` HTTP streaming interface, which would require a separate
server-backed runtime architecture; it is recorded as deferred and not
implemented. No TTFT implementation is admitted.

A fifth bounded Area 4 architecture milestone
([LLAMACPP_STEADY_STATE_VRAM_FEASIBILITY.md](LLAMACPP_STEADY_STATE_VRAM_FEASIBILITY.md))
qualified the neutral steady-state VRAM question: `llmgauge.metric.v1.steady_state_vram`
remains deferred because the current process-per-request native `llama-cli`
execution preserves no defensible post-load boundary, performs no warmup in
the same process, preserves no pre-teardown end boundary aligned to the VRAM
sample clock, and bridges no wall-clock/monotonic relationship between the
device-scoped samples and the process lifecycle. llama.cpp's printed `load
time` is proven (primary source) to end at first evaluation, not model
readiness, and is unanchored to the sample stream. No stability heuristic may
substitute for a semantic interval, so no neutral steady-state VRAM record is
admitted. Peak VRAM and native timing/placement evidence are unchanged.

A sixth bounded Area 4 implementation milestone
([VLLM_AREA4_EVIDENCE_MAPPING.md](VLLM_AREA4_EVIDENCE_MAPPING.md))
maps the current vLLM request evidence into the existing Area 4 representation:
the request-wall-time timer boundary was corrected to include request
serialization and response validation (matching the accepted contract), and
`llmgauge.metric.v1.request_wall_time` is now emitted for transmitted vLLM
requests alongside the preserved native `request_wall_time_seconds`. TTFT,
prefill/decode throughput, model-load time, steady-state VRAM, request-window
peak VRAM, and execution placement remain unavailable or deferred for vLLM:
the non-streaming adapter exposes no first-token boundary, the operator owns
server lifecycle and model admission, the vLLM API exposes no placement, and
no VRAM sampler is added. Readiness remains an API-observation only; it never
sets cache state. The validator, reporter, comparison, fingerprint (when model
provenance is available), and public-export paths are extended to handle vLLM
Area 4 evidence. Historical vLLM results without Area 4 remain valid, and
llama.cpp Area 4 evidence is unchanged.

A seventh bounded Area 4 architecture milestone
([VLLM_STREAMING_TTFT_ARCHITECTURE.md](VLLM_STREAMING_TTFT_ARCHITECTURE.md))
qualified the vLLM streaming TTFT question, and the human resolved the
reasoning-token contract: **the first backend-generated token counts for
neutral TTFT, including reasoning tokens**. vLLM's OpenAI-compatible streaming
interface, with the vLLM-specific `return_token_ids=true` request option,
exposes a genuine first-generated-token boundary (raw backend token IDs in
`choices[0].token_ids`). The first SSE event is role-only (no token), and the
first chunk whose `token_ids` is non-empty carries the first generated token
ID(s). One chunk may contain multiple token IDs (engine merging under load,
speculative decode), so TTFT is timestamped at chunk arrival — the first
token's transport-boundary availability — with token count recorded per event.
The architecture is now implemented as opt-in streaming evidence mode:
`--vllm-streaming-evidence` uses the qualified vLLM SSE transport, preserves
private per-request stream evidence (`llmgauge.vllm_stream_evidence.v0`,
`request/<prompt>.stream.json`), and emits the neutral TTFT metric with
validator recomputation. The non-streaming default is unchanged.

Post-v0.77 Area 4 continuation on `main`: runtime lineage qualification
selected `LLAMA_RUNTIME_LINEAGE_POLICY = UPSTREAM_IDENTITY_ALLOWLIST` and a
frozen, packaged upstream identity manifest
(`src/llmgauge/data/llama_runtime_lineage.json`, 912 placement identities,
builds 9538..10449, of which 44 also admit slot timing) replaced the exact
10449/`0d9ceae1e` native-diagnostics gate with fail-closed exact
identity-pair admission and independent per-source flags. The vLLM
streaming-TTFT qualification was reaffirmed as exact vLLM 0.27.1 only
(`VLLM_STREAMING_TTFT_QUALIFICATION = EXACT_VERSION_ONLY`). Real vLLM
0.27.1 reasoning-first TTFT evidence (Qwen3-0.6B) validated the
reasoning-token contract on a real reasoning channel, and the Area 4
validator now independently recomputes the first-token channel from the
preserved raw stream payload, rejecting consistent two-artifact
reclassification. Native neutral TTFT (llama-cli), model-load time,
prefill/decode throughput, steady-state VRAM, and cross-runtime
equivalence remain deferred under the accepted contracts.

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
import-only; LLMGauge does not execute generated code. Isolated official
`v0.4.12` writer artifacts confirmed the MMLU nested group layout,
ordinary-task metric names, and the HumanEval/MBPP execution gate. See
[Bundle 1 qualification](BUNDLE1_QUALIFICATION.md). LocalMaxxing quality
export/submit remains later. Public LocalMaxxing support for Bundle 1 is
still shard-eval or plus-variants, not official lm-eval metrics. The
existing `llmgauge localmaxxing` namespace remains speed-only.

The accepted
[interoperability contract](EXTERNAL_BENCHMARK_LOCALMAXXING_INTEROP_CONTRACT.md)
remains the authority/identity contract.


### Bundle 2 qualification (completed)

Milestone D extends the external-benchmark qualification to Bundle 2
(`llmgauge.bundle2.v0`): read-only qualification for MMLU-Pro (group of 14
subjects with mandatory `custom-extract` filter), GPQA n-shot
(`gpqa_{main,diamond,extended}_n_shot` with gated-dataset disclosure), and
IFEval (all four strict/loose metrics), all at the shared
`lm-evaluation-harness` `v0.4.12` pin. It mirrors the Bundle 1 engine,
remains import-only, and never executes generated code. Report rendering of
Bundle 2 alongside Bundle 1 in `llmgauge benchmark report` is a separate
presentation decision.


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

### Reasoning and sampling profile identity (completed first slice)

Comparison reports account for captured reasoning/sampling/control settings
(reasoning mode and effort/budget, temperature, top-p, top-k, min-p, seed,
cache types, fit, reasoning-preservation, speculative type). The accepted
[reasoning and sampling profile identity contract](REASONING_SAMPLING_PROFILE_CONTRACT.md)
now adds the first reusable local substrate: `--sampling-profile`, one neutral
controlled built-in profile, closed custom config definitions, deterministic
content identity, additive result evidence and V5 fingerprints, validation, and
comparison provenance disclosure. Selected profiles record requested controls
only; they do not prove semantic reasoning behavior or vendor endorsement.

The first vendor-aligned content qualification slice is complete: four
offline builtins (`qwen3-thinking-v1`, `qwen3-nonthinking-v1`,
`gemma-4-instruct-v1`, `deepseek-r1-v1`) plus
[VENDOR_ALIGNED_SAMPLING_PROFILES.md](VENDOR_ALIGNED_SAMPLING_PROFILES.md).
Installed CLI discovery and introspection are now complete through
`llmgauge profiles list` and `llmgauge profiles show PROFILE_ID`; both use the
shipped registry and resolver without remote lookup. Broader family
qualification, custom profile UX and definitions, filesystem discovery, and
deeper vendor reasoning-mode mappings remain separate reviewable milestones.



Generic Core suite implementation is no longer the selected next milestone, but
it remains admitted downstream work under its existing accepted contracts and
resources. Its relationship to the fast track is complementary: Generic Core
provides a general native text suite and reusable profile/resource foundations;
it does not replace the dedicated coding suite, multi-turn transcript, Agent
Harness import, runtime-neutral metrics, or later modality/generation contracts.

The Generic Core delivery path is now:

1. Generic Core fixture and package-data support (completed).
2. Generic Core compatibility and security hardening (completed).
3. `v0.72` release preparation (completed).
4. Generic Core suite implementation with the final manifest, 13-prompt
   inventory, fixture references, and exact Smoke/Core membership (completed).
5. Deterministic checks D1-D7, with D5 deliberately and reproducibly
   `not_run` (completed).
6. Execution and result-provenance integration (completed).
7. `v0.73` release preparation (completed).
8. A future executable-D5 Generic Core suite version behind a separately
   accepted containment and resource-limit contract (separate future track).

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
suite manifest or final prompts. Unreleased work after `v0.72` implements the
`0.1.0` suite content, D1-D7 evidence, and result provenance without
completing the `v0.73` release gate.

### `v0.73` — Generic Core v1

**Completed:** the `v0.73` release contains:

- packaged, discoverable `generic-core-v1` `0.1.0` content: the final
  13-prompt inventory, exact ordered `core` and `smoke` profiles, committed
  fixtures, and supported scoring references;
- D1-D7 deterministic evidence behavior implemented according to `0.1.0`
  semantics;
- D5 explicitly and reproducibly `not_run`: generated code is not executed,
  the authorization resource remains false, and unexpected authorization
  values fail closed;
- complete result, profile, and scoring provenance in results;
- the completed manual and hybrid review workflow, with hybrid components
  composed side-by-side;
- reporting that exposes component state and the D5 non-execution boundary;
- validated package, wheel, sdist, and installed-resource behavior with
  byte-identical source/package mirrors;
- completed clean-clone validation; and
- internally consistent version and release metadata.

Generated-code execution is not part of `v0.73`. Executable D5 evaluation
belongs to a future Generic Core suite version behind a separately accepted
containment and resource-limit contract; enabling it would change the prompt
promise, authorization, deterministic-check behavior, evidence meaning,
security boundary, and comparability, so it must not silently change
`0.1.0`. No Generic Core profile aggregate score exists.

### `v0.74` — Distribution and installation (published)

**Completed and published to production PyPI as `llmgauge` 0.74.0:**

- PyPI-grade package metadata: explicit version, `uv_build>=0.12.6,<0.13`,
  LICENSE carried in wheel/sdist, declared project URLs;
- Trusted Publishing release workflow with build-once/publish-exact-artifacts
  architecture, immutable Action SHA pinning, and fail-closed tag/version,
  annotated-tag, and exact-commit guards;
- exact distribution-content validation;
- proven TestPyPI publication of 0.73.0 with independent fresh-installation
  validation;
- configured production pending publisher and protected GitHub `pypi`
  environment (required reviewer, `v*`-only deployment restriction);
- canonical `uv tool install llmgauge` installation UX with pipx/pip/pinned
  alternatives, tagged Git source as pinned-source/fallback, and clone +
  `uv sync` for contributors; and
- consistent version, changelog, README, installation, release-process, and
  roadmap metadata for the first production PyPI listing.

Production PyPI publication occurred when the human pushed annotated tag
`v0.74` and approved the `pypi` environment deployment.

### `v0.75` — Reasoning/sampling profiles and evidence (published)

**Completed and published to production PyPI as `llmgauge` 0.75.0:**

- named/versioned reasoning and sampling profiles (`--sampling-profile`)
  with deterministic content identity, result/fingerprint persistence, and
  comparison provenance disclosure;
- the neutral `controlled-deterministic-v1` profile plus four
  primary-source-qualified vendor-aligned builtins, documented in
  [VENDOR_ALIGNED_SAMPLING_PROFILES.md](VENDOR_ALIGNED_SAMPLING_PROFILES.md);
- offline installed-CLI profile discovery and introspection
  (`llmgauge profiles list`, `llmgauge profiles show PROFILE_ID`);
- requested `--min-p` capture across run metadata and comparison scope;
- derived device-scoped `llmgauge.metric.v1.peak_vram` evidence for native
  llama.cpp results with validator recomputation;
- pinned Bundle 2 read-only import qualification (`llmgauge.bundle2.v0`)
  for MMLU-Pro, GPQA, and IFEval at `lm-evaluation-harness` `v0.4.12`;
- reasoning/sampling and `min_p` disclosure in comparison scope; and
- consistent version, changelog, README, installation, release-process, and
  roadmap metadata.

Production PyPI publication occurred when the human pushed annotated tag
`v0.75` and approved the `pypi` environment deployment.

### `v0.76` — Multi-turn transcript comparison and safe public derivatives (published)

**Completed and published to production PyPI as `llmgauge` 0.76.0:**

- bounded structural comparison of all-transcript result sets via
  `llmgauge compare`: exact-identity eligibility, three-way structural
  classification, role/order-preserving listings, recorded review-hook
  disclosure, fail-closed mixed-set rejection;
- `llmgauge export-public-comparison`: content-default-deny public
  comparison derivative (`llmgauge.public_transcript_comparison.v0`) with
  closed-world validation, adversarial canary coverage, staged atomic
  writes, and human-review-required artifacts;
- `llmgauge export-public-transcript`: content-default-deny public
  single-transcript derivative (`llmgauge.public_transcript.v0`) reusing
  the same sanitization primitives plus closed protocol identity and
  producer release version;
- unchanged canonical `llmgauge.result.v0` / `llmgauge.transcript.v0`
  schemas, fingerprints, and single-turn behavior;
- consistent version, changelog, README, installation, release-process, and
  roadmap metadata.

No session aggregate score, ranking, winner, statistical, or semantic
judgment claim exists; transcript text publication remains excluded.
Production PyPI publication occurred when the human pushed annotated tag
`v0.76` and approved the `pypi` environment deployment.

### `v0.77` — Area 4 runtime-evidence stabilization (published)

**Completed and published to production PyPI as `llmgauge` 0.77.0:**

- opt-in vLLM streaming evidence mode (`--vllm-streaming-evidence`) using
  the qualified vLLM token-ID SSE transport (`return_token_ids=true`),
  with runtime-neutral TTFT (`llmgauge.metric.v1.time_to_first_token`),
  preserved private per-request stream evidence
  (`llmgauge.vllm_stream_evidence.v0`), and exact vLLM 0.27.1 version
  qualification; the non-streaming default is unchanged;
- Area 4 request-wall-time mapping for transmitted external vLLM requests
  (`llmgauge.metric.v1.request_wall_time`) and request-window peak-VRAM
  evidence (`llmgauge.metric.v1.peak_vram`) from a bounded concurrent
  NVIDIA telemetry sampler;
- native llama.cpp backend-owned timing and observed execution placement
  with conservative Area 4 provenance (no neutral load/prefill/decode/TTFT
  mappings, no full-accelerator-residency claim);
- runtime-evidence transport consistency hardening: result, runtime
  evidence, request and stream evidence, reports, and comparisons agree on
  streaming state, and `validate-result` rejects represented
  contradictions;
- public-export privacy/integrity hardening: TTFT, stream/token evidence,
  generated reasoning, and local endpoint identity omitted while exact
  API-route prose and transport disclosure remain;
- unchanged canonical schemas and historical fingerprints.

Production PyPI publication of v0.77 occurred when the human pushed
annotated tag `v0.77` and approved the `pypi` environment deployment.
Post-v0.77 Area 4 qualification and evidence-integrity work was consolidated
into v0.78.0 below and is now published.

### `v0.78` — Area 4 evidence-integrity and qualification hardening (published)

**Completed and published to production PyPI as `llmgauge` 0.78.0:**

- frozen upstream llama.cpp runtime-lineage manifest
  (`LLAMA_RUNTIME_LINEAGE_POLICY = UPSTREAM_IDENTITY_ALLOWLIST`): fail-closed
  exact build+commit identity admission against the packaged
  `src/llmgauge/data/llama_runtime_lineage.json` (912 qualified placement
  identities, builds 9538..10449; 44 also qualify slot timing, builds
  10406..10449), replacing the exact `10449 / 0d9ceae1e` gate;
- qualified current llama.cpp native-diagnostics capture: the renamed
  `load_tensors:` placement line and the request-final `slot_print_timing:`
  block with deterministic `--verbosity 4` capture and conservative
  placement classification (N=0 `cpu_only`, 0<N<M
  `hybrid_accelerator_cpu`, N=M `unknown`; no full-accelerator claim);
- source-aware Area 4 validation: native timing/placement projections and
  slot timing recomputed from preserved diagnostic lines, with lineage
  qualification recomputed from persisted provenance plus the manifest;
- vLLM streaming TTFT validator hardening: the first-token channel is
  recomputed from the preserved raw SSE payload instead of trusting stored
  labels; exact-0.27.1 `EXACT_VERSION_ONLY` qualification reaffirmed
  (no 0.28.0 or range support);
- unchanged canonical result schemas, historical fingerprints, and
  previously valid v0.77 results; no new material dependencies.

Production PyPI publication of v0.78 occurred when the human pushed
annotated tag `v0.78` and approved the `pypi` environment deployment.

## Parallel product tracks

These future product tracks remain separate from the completed architecture
milestone, the selected coding-suite contract, the fast-track program sequence,
Generic Core delivery, and one another.

### Packaging and productization

**Completed for v0.74 (published):**

- Distribution metadata hardening for PyPI-grade artifacts (`v0.74`
  Milestone A): explicit version, `uv_build>=0.12.6,<0.13` compatibility,
  LICENSE in wheel/sdist, project URLs, and version-consistency regression.
- Repository release-workflow readiness (`v0.74` Milestone B): tag-gated
  Trusted Publishing workflow, manual TestPyPI gate, release tag/version
  guard, and exact distribution-content validation per
  [PYPI_RELEASE_PROCESS.md](PYPI_RELEASE_PROCESS.md).
- Live TestPyPI proof: first manual publication of llmgauge 0.73.0 succeeded,
  an independent fresh-environment TestPyPI installation succeeded, and
  installed resources validated.
- Production configuration: pending Trusted Publisher registered on PyPI and
  the protected GitHub `pypi` environment configured (required reviewer,
  `v*`-only deployment restriction). Publication remains behind the human
  annotated-tag/approval gate.
- Canonical installed-user UX: documented `uv tool install llmgauge`,
  `pipx`, `pip`, pinned-version, pinned-Git-source, and contributor paths;
  upgrade/uninstall workflow; explicit runtime-boundary language.

**Optional future work (demand-driven, separate from any current release):**

- COPR/Fedora packaging after PyPI, only on demonstrated demand.
- Standalone executable/container feasibility later.
- Additional distribution channels (Homebrew/AUR/Nix/Debian) only when value
  justifies maintenance cost.
- GitHub Release attachments, SBOM/signing beyond PyPI attestations: not
  currently required.

### Runtime interoperability

The strategic target is **first-class multi-runtime model evaluation**, defined
by the accepted
[first-class multi-runtime architecture contract](FIRST_CLASS_RUNTIME_ARCHITECTURE.md).
Runtime interoperability no longer means only "audit vLLM, add a generic HTTP
transport, then SGLang/Ollama adapters": the principal runtime families are

- `llama.cpp` / GGUF (first-class runtime and representation, default),
- vLLM / native Hugging Face-Transformers-style directory checkpoints
  (first-class runtime and representation target),
- SGLang / native Hugging Face-Transformers-style directory checkpoints
  (first-class runtime and representation target), and
- ExLlamaV3 / EXL3 (plus supported native FP16/BF16 directory checkpoints),
  served through the official TabbyAPI OpenAI-compatible server (accepted
  fourth first-class runtime family per the
  [EXL qualification contract](EXL_RUNTIME_QUALIFICATION.md)),

each with runtime-specific lifecycle, evidence, and capability disclosure
preserved honestly rather than collapsed into a fake generic OpenAI backend.
The accepted program is eleven bounded implementation milestones plus the
completed M2.5 qualification: model-representation and profile contract (M1),
directory-model provenance (M2), EXL/ExLlama runtime qualification (M2.5),
vLLM identity (M3), vLLM managed lifecycle (M4), vLLM workflow parity (M5),
EXL checkpoint-manifest v1 plus
`model_format` identity (M8), ExLlamaV3 external adapter (M9), ExLlamaV3
managed lifecycle/parity (M10), EXL2/ExLlamaV2 pinned compatibility lane
(M11), shared transport plus SGLang external adapter (M6), and SGLang
lifecycle/parity with cross-runtime identity hardening across all four
families (M7).
Milestone M1 (runtime-neutral model representation and profile contract) is
implemented: profiles carry an optional `source_kind` discriminator
(`gguf_file` / `checkpoint_directory` / `served_model_reference`) with legacy
GGUF and bounded external-vLLM profiles unchanged; representation does not
yet mean execution, and unsupported source-kind/backend combinations fail
closed before any runner. Milestone M2 (directory-model provenance collection
and fingerprint eligibility) is implemented: checkpoint directories now have
bounded local identity — a versioned canonical manifest, an identity-validated
separate cache, tokenizer/chat-template identity, checkpoint-declared
quantization evidence, additive `model.provenance` validation/report/export
handling, and the new `llmgauge.run_fingerprint.v6` payload for manifest
identity — with every existing GGUF fingerprint version and behavior frozen.
Directory provenance is still not executable through any runtime. The
selected next implementation milestone is M3, vLLM first-class model identity.

EXL support is a real product target with two distinct lanes: **EXL3 /
ExLlamaV3 is the strategic current path** (principal runtime family, full
first-class obligations), while **EXL2 / ExLlamaV2 is a compatibility lane**
(upstream ExLlamaV2 is archived and TabbyAPI `main` no longer serves it; the
preserved TabbyAPI `exl2-checkpoint` branch pins the legacy execution path).
EXL2 checkpoints still receive full first-class representation identity —
`model_format` detection, provenance, validation, reporting, export — and
remain supported models, not deprecated artifacts. The frozen
`checkpoint_directory_manifest.v0` is `COMPLETE` for EXL2 and `PARTIAL` for
sharded EXL3 (out-of-index `ngram_embedding.safetensors`); the accepted fix
is the versioned manifest v1 union rule in M8, never a silent v0 allowlist
expansion. No EXL release date or version number is promised.

Later runtime possibilities (Ollama, TensorRT-LLM, NVIDIA NIM) remain
admissible through the same first-class acceptance contract, with no promised
version or date. Heterogeneous platform provenance remains a later track.

`llama.cpp` remains the default runtime. The current vLLM adapter remains a
bounded, operator-managed local integration until its first-class milestones
land. DGX Spark is a hardware/platform provenance target, not a backend;
support should use whichever separately admitted runtime actually runs on that
platform. Runtime work enters the fast-track order only through its separately
accepted contracts.

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
4. Bundle 2 qualification (completed as read-only `llmgauge.bundle2.v0`
   import qualification);
5. LocalMaxxing quality export / dry-run / explicit submit, only after
   an approved matching suite path exists;
6. additional external text benchmark read-only imports;
7. Agent drift evaluation contract;
8. Terminal-Bench/Harbor contract and read-only import;
9. SWE-bench; and
10. Browser, computer-use, and OSWorld later.

MMLU, ARC Challenge, HellaSwag, WinoGrande, TruthfulQA MC2, GSM8K,
HumanEval, and MBPP are qualified as Bundle 1 against the pinned
`v0.4.12` identities; MMLU-Pro, GPQA, and IFEval are qualified as Bundle 2
(`llmgauge.bundle2.v0`) at the same pin. Generic lm-eval import is not by
itself a Bundle 1 or Bundle 2 completion claim.
Any later integration preserves the external dataset, harness,
and official metric as authoritative; LLMGauge does not recreate them as
native prompts. LocalMaxxing official shard evals and plus-variants are
not those official metrics.

These items retain the distinct evaluation classes and evidence authorities
defined by the [general evaluation taxonomy](GENERAL_EVALUATION_TAXONOMY.md).

## Recently completed releases

Condensed highlights (newest first). Details remain in [CHANGELOG.md](../CHANGELOG.md).

| Release | Focus |
|---|---|
| v0.76 | Multi-turn transcript comparison release (published to production PyPI as 0.76.0): all-transcript `compare` structural comparison, `export-public-comparison` (`llmgauge.public_transcript_comparison.v0`), `export-public-transcript` (`llmgauge.public_transcript.v0`), content-default-deny public derivatives with human review required; no aggregate/ranking/semantic claims |
| v0.75 | Reasoning/sampling profile release (published to production PyPI as 0.75.0): named/versioned profiles (`--sampling-profile`), `controlled-deterministic-v1` plus four vendor-aligned builtins, offline `profiles list`/`profiles show`, `--min-p` capture, derived peak-VRAM metric evidence, Bundle 2 (`llmgauge.bundle2.v0`) import qualification, comparison reasoning/sampling disclosure |
| v0.74 | Distribution/installation release (published to production PyPI as 0.74.0): PyPI-grade metadata, Trusted Publishing workflow, proven TestPyPI path, configured production publisher/environment, canonical `uv tool install llmgauge` UX |
| v0.73 | Packaged `generic-core-v1` `0.1.0`: 13-prompt Core / 4-prompt Smoke profiles, D1-D7 deterministic evidence with D5 `not_run`, result/profile/scoring provenance, manual and hybrid review, no profile aggregate; plus Coding Core, runtime evidence controls, lm-eval import, multi-turn and agent-session review, and LocalMaxxing integration |
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
