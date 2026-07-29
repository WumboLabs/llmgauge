# Full Model Testing Capability Architecture

## Status and scope

This document is the accepted architecture and sequencing contract for expanding
LLMGauge toward broader full-model testing. It classifies the current system,
defines authority and trust boundaries, names the contracts required before
implementation, and orders bounded implementation milestones. It adds no suite,
prompt, schema, importer, metric, failure class, benchmark runner, offline
exporter, network submission, leaderboard, runtime, multimodal path, or
execution behavior.

The [general evaluation taxonomy](GENERAL_EVALUATION_TAXONOMY.md) remains the
authority for evaluation-class boundaries. The [artifact schemas](ARTIFACT_SCHEMAS.md)
remain the authority for current result artifacts. Accepted Generic Core
contracts and resources remain admitted downstream work; this program neither
reopens them nor makes `generic-core-v1` executable.

## System boundary

LLMGauge remains a local-first evaluator, evidence importer, validator, and
report generator. It may own bounded native prompts and evaluation contracts,
and it may import evidence produced by an external harness. It is not a coding
agent, an agent loop, a model downloader, or a general runtime supervisor.

In particular:

- LLMGauge may ask a model to produce a response or a patch as evaluation
  output, but it does not autonomously inspect a repository, choose edits, run
  arbitrary commands, or continue an agent loop.
- A coding harness owns repository interaction, tool execution, containment,
  retries, and session lifecycle. LLMGauge may read supported session artifacts
  without mutating them.
- An operator owns external runtime installation, startup, shutdown, model
  loading, and host configuration unless a later, separately accepted contract
  assigns a narrower lifecycle action. The current vLLM boundary remains
  externally managed and loopback-only.
- Imported and runtime-native evidence stays authoritative at its source.
  LLMGauge-derived validation, scoring, comparison, and reporting never repair,
  replace, or silently reinterpret that source.

## Capability classes and current support

`Implemented` means current product behavior exists and has an accepted evidence
contract. `Partial` means a bounded foundation or related behavior exists but
not the complete capability described here. `Missing` means no current product
contract and behavior satisfy the capability.

| Capability class | Current support | Current boundary |
|---|---|---|
| Native single-turn response evaluation | Implemented | Current prompt and suite runs preserve LLMGauge-owned prompts, raw and cleaned model output, logs, settings, failures, scoring provenance, reports, comparisons, and exports. Historical suites retain their existing identities and authority. |
| Multi-turn evaluation | Missing | Current single-prompt artifacts do not constitute a conversation transcript and do not contractually preserve inter-turn tool or test feedback. |
| Dedicated coding evaluation | Missing | Existing shell-safety, tool-honesty, and coding-related material, including Generic Core D5 resources, is not a dedicated coding suite and does not supply compiler/test-feedback repair evaluation. |
| Agent-session evidence | Missing | The accepted agent-environment taxonomy defines authority boundaries, but there is no WumboLabs Agent Harness session importer. |
| Runtime interoperability | Partial | `llama.cpp`/GGUF is the default runtime. The external local vLLM adapter is implemented but bounded to operator-managed, loopback-only, sequential, non-streaming text requests. No generalized shared transport contract is accepted. |
| Runtime-neutral metrics | Partial | Current runs can retain runtime evidence, speed observations, and hardware facts, but vLLM VRAM is not captured and runtime-native token and throughput values are explicitly non-equivalent. There is no cross-runtime metric contract covering the full required set. |
| LocalMaxxing performance benchmark | Missing (architecture lane only) | This document and the general evaluation taxonomy accept the performance-benchmark boundary and fast-track lane, but no benchmark identity/version contract, artifact mapping, execution path, offline exporter, or validator is implemented. |
| Reasoning and sampling profiles | Partial | Generation settings and some requested runtime modes are recorded, but there is no complete profile contract for reasoning `on`, `off`, and `auto`, vendor-aligned versus controlled profiles, or profile-aware comparison eligibility. |
| Expanded failure taxonomy | Partial | Current artifacts preserve failures such as nonzero exits, timeouts, signals, startup failures, and OOM evidence, but the required closed model/runtime/tool/agent categories are not all represented by an accepted taxonomy. |
| Multimodal evaluation | Missing | Current native and vLLM paths are text-only; image, audio, and video input authority, preservation, scoring, and failure contracts do not exist. |
| Non-autoregressive generation | Missing | Current evaluation and performance concepts do not define diffusion steps, generation configuration, or timing that avoids token-by-token assumptions. |

These classes are not aliases:

- **Native single-turn response evaluation** evaluates one model response to one
  LLMGauge-owned prompt under the existing native artifact authority.
- **Multi-turn evaluation** evaluates a versioned conversation protocol with
  preserved state and feedback across turns.
- **Coding evaluation** is a task-domain contract. A non-executed coding prompt
  may remain native response evaluation; an official external coding benchmark
  remains an external text benchmark; an executed repository task with an agent
  loop is agent-environment evaluation.
- **Agent-session evidence** describes an imported full-stack session produced
  by a harness. Its outcome is not attributable to the model alone.
- **LocalMaxxing** is a controlled performance benchmark, not native-response,
  coding, multi-turn, agent-environment, multimodal, or non-autoregressive
  evaluation. Its benchmark protocol and native measurements define the
  evaluated subject and evidence authority.
- **Multimodal evaluation** includes one or more non-text input modalities and
  requires modality-specific evidence and scoring boundaries.
- **Non-autoregressive generation** covers generation whose work and completion
  cannot honestly be modeled as sequential output-token decoding.

## Evidence ownership and trust boundaries

| Class | Authoritative evidence owner | Minimum source evidence | LLMGauge role and trust limit |
|---|---|---|---|
| Native single-turn response | LLMGauge native result contract | Prompt, raw response, logs, requested and observed settings, failures, scoring provenance | Own, validate, score, and summarize under existing contracts. Derived reports and cleaned output do not replace raw evidence. |
| Multi-turn native evaluation | Future versioned LLMGauge conversation contract | Initial state, every ordered turn and response, inter-turn feedback, state transitions, completion/failure state, scoring provenance | May own the protocol and artifacts after contract acceptance. A transcript assembled from missing turns is not valid evidence. |
| Coding native response | LLMGauge suite contract | Task and fixture identity, model response or patch, declared non-execution or bounded checker evidence, feedback when applicable | Evaluate model output; do not become an autonomous repository-editing agent. Execution requires a separate containment contract. |
| External coding benchmark | Official dataset and harness | Dataset/split, harness and metric versions, native outputs, official metric artifacts, inference configuration | Import and summarize without reimplementing or relabeling official metrics. |
| Agent-session evidence | WumboLabs Agent Harness for supported imports | Session identity, repository state, trajectory, edits, commands, tool observations, tests and failures, recovery, final diff, verifier/outcome, limits, harness provenance | Read-only import, validate, annotate, and summarize. Never mutate the source session or claim the harness outcome as model-only quality. |
| Runtime-neutral performance | The declared benchmark protocol and runtime-native sources | Workload, warmup/repetition/completion rules, timing sources, native counters, hardware conditions, requested/observed settings, failures | Normalize only metrics whose semantics are contractually equivalent; retain native values, units, source, and incompatibility labels. |
| LocalMaxxing performance benchmark | Future versioned LocalMaxxing benchmark protocol | Benchmark identity/version, controlled workload and completion record, benchmark-native measurements, failures, model/runtime/quantization/settings/hardware/platform provenance | Deterministically validate and create explicitly marked offline annotations or export derivatives. Never replace native measurements or infer export eligibility from an ordinary prompt run. |
| Multimodal | Future LLMGauge protocol or named external authority | Original input artifacts, modality and transforms, prompt, outputs, timing, failures, scoring provenance | Preserve source bytes or immutable references according to the accepted contract; derivatives cannot replace inputs. |
| Non-autoregressive | Future generation protocol and runtime-native evidence | Input, generation configuration and steps, timing phases, outputs, runtime failures, provenance | Report work in protocol-native units; never synthesize token throughput where token decoding is not the process. |

All classes inherit these rules:

1. Requested behavior is separate from observed behavior.
2. Missing facts remain `unknown` or `unavailable`; filenames and requests do not
   prove effective runtime behavior.
3. Raw source evidence is authoritative. Validation establishes structure, not
   answer quality, official acceptance, or publication readiness.
4. Imports are read-only and offline by default. Publication and network
   submission remain separate human-controlled work.
5. Comparisons require compatible evaluation identity, subject, evidence
   authority, settings, completion rules, scoring state, and metric semantics.

## Provenance layers

Every future contract must keep the following concepts separate:

- **Runtime:** the inference implementation and version that loads or executes
  the model, such as `llama.cpp`, vLLM, Transformers, or a vendor fork.
- **Transport:** the request/response protocol between LLMGauge and a runtime,
  such as a local process interface or a bounded OpenAI-compatible HTTP surface.
  A shared transport does not make runtime behavior equivalent.
- **Model:** the model/checkpoint identity, architecture, weights, and available
  full fingerprint evidence.
- **Quantization:** the weight, activation, cache, and kernel-relevant numeric
  representation actually requested and, where observable, used. A filename or
  marketing label is not sufficient observation.
- **Hardware:** privacy-bounded devices and resources used for the run, including
  CPU, accelerators, memory, and observed placement or offload facts.
- **Platform:** the host operating system, driver and accelerator stack,
  architecture, and appliance class. A platform such as DGX Spark is not a
  runtime or transport.

Template and tokenizer identity, generation settings, kernels, environment, and
harness versions are additional provenance. They attach to the relevant layer;
they must not be collapsed into a single backend label.

## Capability contracts required before implementation

### Dedicated coding suite

Accept a suite contract that fixes task identity/version, prompt and fixture
ownership, permitted response forms, scoring authority, comparison eligibility,
and failure preservation. Coverage must include debugging, minimal patch
generation, test creation and failure diagnosis, shell-command safety,
dependency and API uncertainty, scope control, structured output compliance,
and repair after compiler or test feedback.

Non-executed tasks may use deterministic response checks and manual review.
Any generated-code or command execution requires a separate accepted
containment contract covering structured invocation, filesystem scope, resource
limits, timeouts, network policy, process cleanup, captured output, and failure
preservation. The existing Generic Core D5 containment gate remains separate.

### Multi-turn transcript

Accept a conversation identity/version and contracts for ordered turns,
preserved conversation state, every model response, feedback provenance,
termination, partial completion, retries, privacy, and source/derivative roles.
Test, tool, compiler, or harness feedback inserted between turns must retain its
origin and exact association with the turn that consumed it.

Scoring must keep correction, recovery, and cross-turn consistency distinct
from single-response quality. The contract must state whether feedback is
LLMGauge-owned deterministic evidence or imported external evidence.

### Agent Harness evidence import

Accept the supported WumboLabs Agent Harness session identity/version,
authoritative artifact inventory, repository-state identity, path containment,
privacy/redaction boundaries, unsupported-version behavior, completeness rules,
and source immutability checks. Import must preserve repository inspection,
edits and commands, tool results, tests and failures, recovery attempts, final
diff, verifier result, terminal state, and harness/model/tool/environment
provenance when available.

The importer is read-only. It must not replay commands, apply patches, repair a
session, launch an agent, or infer a successful outcome from a polished final
message. LLMGauge remains the evaluator of preserved evidence, not another
coding agent.

### Runtime-neutral metrics and failure taxonomy

Accept metric definitions, units, clock and measurement boundaries, warmup and
aggregation rules, missing-data behavior, and equivalence tests for:

- request latency;
- time to first token;
- prompt or prefill throughput;
- generation throughput;
- model-load time;
- peak and steady-state VRAM; and
- CPU offload and hybrid execution metadata.

Every metric must identify whether it is directly observed by LLMGauge,
reported by a backend, calculated from preserved evidence, or unavailable.
Backend-native metric names and units remain available even when no neutral
mapping is valid. Non-equivalent tokenizers, templates, batching, cache state,
workloads, and runtime counters block cross-runtime aggregation rather than
being averaged together.

Accept a closed, extensible failure taxonomy that distinguishes at least:

- runtime environment failure;
- unsupported architecture;
- unsupported quantization or kernel;
- model-weight-load OOM;
- KV-cache OOM;
- endpoint failure;
- tool failure;
- generation failure;
- malformed response; and
- agent recovery failure.

The contract must define evidence needed to assign each category, precedence
when multiple failures occur, terminal versus recoverable state, and honest
fallback/retry representation. Unknown failures remain unclassified; a generic
provider error is not silently mapped to a more specific cause.

### vLLM audit and shared OpenAI-compatible transport

Audit the current external local vLLM backend against its accepted contract and
preserve its operator-managed lifecycle. Before sharing transport code, accept
a transport contract for bounded endpoints, request/response byte authority,
streaming status, timeout and cancellation behavior, content-type and protocol
errors, exact raw evidence retention, privacy, and runtime-specific extensions.

Shared transport may remove duplicated protocol machinery only where semantics
are genuinely common. Runtime, model, quantization, template, kernel, and
request/response provenance remain explicit. Transformers, vendor forks, and
other local runtimes each require their own lifecycle, capability, failure, and
provenance contract; an OpenAI-compatible surface alone does not admit them.

### Reasoning and sampling profiles

Accept profile identity/version, precedence, requested-versus-observed behavior,
and comparison rules for reasoning `on`, `off`, and `auto`; vendor-aligned
profiles; and controlled profiles. Preserve temperature, top-p, penalties,
seed, template, and any runtime-native reasoning controls that materially affect
the request.

A vendor-aligned profile measures the disclosed vendor-intended configuration.
A controlled profile holds accepted variables constant. Neither is inherently
more correct, and profile-aware comparisons do not support universal-quality
claims. Unknown effective reasoning mode blocks claims that depend on that mode.

### Multimodal evaluation

Accept modality-specific input identity, preservation, decoding and transform
provenance, limits, prompt association, scoring authority, failure labels,
privacy, and comparison contracts for image, audio, and video. Preserve original
inputs or contractually immutable references plus every derived transform used
for inference. Text-only, image-capable, audio-capable, and video-capable
subjects must be labeled explicitly; unsupported modality is not answer-quality
failure.

Each modality needs its own admission and scoring rules. A common container does
not make preprocessing, timing, or quality metrics equivalent across modalities.

### Diffusion and non-autoregressive generation

Accept a generation identity/version, work-unit definition, diffusion steps and
configuration, seed/randomness rules, phase timing, completion, output artifact,
and runtime-failure contract. Metrics must describe runtime-native work and
must not assume time to first token or token-by-token decode throughput. Where a
runtime emits staged previews or iterative outputs, the contract must define
which are authoritative evidence and which constitute completion.

## Parallel LocalMaxxing performance-benchmark lane

LocalMaxxing is a distinct **performance benchmark** evaluation class. Current
support is **missing (architecture lane only)**: this document accepts the
class boundary, required contracts, and bounded sequence, but no
LocalMaxxing-specific benchmark identity/version contract, artifact mapping,
runner, exporter, validator, automatic submission, or leaderboard behavior
exists.

This lane is parallel to the eight-step Full Model Testing capability program.
It depends on the accepted performance-benchmark taxonomy and shared provenance,
evidence, privacy, and failure principles; it does not depend on completing
coding, multi-turn, Agent Harness, multimodal, or non-autoregressive evaluation.
A roadmap may select a LocalMaxxing milestone only through a later explicit
human gate.

### Architecture and offline-export contract

Before implementation, accept a LocalMaxxing-specific contract that fixes:

- benchmark identity and version;
- controlled workload, admission, warmup, repetition, sampling, completion,
  failure, and aggregation rules;
- model, runtime, quantization, generation and runtime settings, hardware, and
  platform provenance, with requested and observed facts kept separate;
- admitted prompt or prefill throughput, generation throughput, request
  latency, time to first token where applicable, model-load time, peak and
  steady-state VRAM, CPU offload or hybrid execution, and failure evidence;
- the measurement source, unit, clock boundary, calculation, missing-data
  behavior, and comparability rule for every admitted metric;
- benchmark-native artifact authority, deterministic validation scope,
  LLMGauge-derived annotation roles, and offline derivative ownership; and
- privacy, compatibility, comparison, publication, and network boundaries.

The protocol need not admit every possible metric for every runtime. An omitted
or unavailable metric remains explicit; it is not reconstructed from a
non-equivalent counter. Runtime-native measurements retain their native names,
units, and provenance unless the contract establishes an equivalent neutral
mapping.

### Evidence ownership and deterministic validation

The versioned LocalMaxxing benchmark protocol owns its controlled workload,
completion state, native measurements, execution logs, configuration record,
and failure evidence. LLMGauge annotations, validation results, summaries, and
offline exports are derivatives. They must identify their authoritative source,
transformation, generation time, and validation result and must not mutate,
repair, supersede, or hide benchmark-native evidence.

Deterministic validation may check supported identity/version, artifact shape,
required references, workload and completion records, provenance completeness,
metric units and calculations, failure preservation, and internal consistency.
It does not prove model quality, measurement equivalence, official acceptance,
publication readiness, or leaderboard eligibility.

An offline LocalMaxxing export is a separate derivative owned by its accepted
export contract. Export generation remains local and offline. It must never
automatically submit results, upload to a leaderboard, contact a network
service, or imply operator approval. Any network submission or leaderboard
upload requires a later, separately accepted human-approved publication
milestone and explicit operator action.

### Compatibility and comparison

Comparison requires compatible benchmark identity/version, workload, admission,
warmup, repetition, completion, failure and aggregation rules, metric
definitions, model and quantization identity, runtime/settings/template path,
and disclosed hardware/platform conditions. Backend-native measurements remain
separate where equivalence is not demonstrated. An ordinary native-response
run, coding task, transcript, Agent Harness session, multimodal run, or
non-autoregressive run does not become LocalMaxxing evidence merely because it
contains latency, throughput, or memory observations.

LocalMaxxing contracts and derivatives must remain additive. Existing native
results, performance observations, historical suites, and external benchmark or
agent-environment evidence retain their original authority and are not migrated
or relabeled.

### Bounded LocalMaxxing milestones

Each item is a separate milestone:

1. **LocalMaxxing architecture and offline-export contract.** Accept identity,
   workload, completion, measurement, authority, derivative, comparison,
   privacy, and network boundaries; add no schema or behavior.
2. **Artifact/schema mapping and provenance contract.** Define supported native
   inputs and additive mapping rules before fields, loaders, or exporters are
   implemented.
3. **Offline benchmark execution/export implementation.** Implement only the
   separately accepted bounded local execution and offline derivative path,
   preserving native evidence and failures; admit no network submission.
4. **Validation, compatibility, and publication-boundary hardening.** Prove
   deterministic validation, supported-version handling, legacy compatibility,
   source immutability, offline behavior, and fail-closed publication gates.

Reporting, comparison presentation, release preparation, publication, and any
network submission remain separately admitted later milestones.

## Blocking scope

### Blocks conventional text and coding model testing

The fast-track program treats these as blockers for defensible broader text and
coding claims:

1. the dedicated coding suite contract and content;
2. the multi-turn transcript contract for feedback and repair tasks;
3. the Agent Harness read-only evidence contract and importer for full coding
   sessions;
4. runtime-neutral metric definitions and the expanded failure taxonomy;
5. the vLLM audit and honest shared-transport boundary; and
6. reasoning and sampling profile completion.

Not every single-turn text run requires all six. They block the named expansion:
credible coding breadth, cross-turn recovery, imported agent evidence, and
cross-runtime/profile comparison. Current native single-turn evaluation remains
valid within its existing limits while this work is incomplete.

### Blocks only multimodal or non-autoregressive testing

Multimodal input contracts and behavior block image, audio, and video testing;
they do not block text/coding milestones. Diffusion and non-autoregressive
contracts block those generation classes; they do not block autoregressive text
or coding evaluation. These later capabilities still depend on the common
provenance, failure, evidence-authority, and metric principles established by
the earlier work.

## Fast-track implementation order

The required initial order is retained without adjustment:

1. **Coding-oriented text suite.** Establish useful coding breadth first without
   confusing response evaluation with an agent session.
2. **Multi-turn transcript contract.** Define state and feedback evidence before
   implementing repair loops or multi-turn scoring.
3. **Agent Harness evidence importer.** Import complete external coding sessions
   only after their relationship to coding and multi-turn evidence is explicit.
4. **Runtime-neutral metrics and expanded failure taxonomy.** Establish common
   measurement and failure semantics before broader backend comparison.
5. **Existing vLLM audit and shared OpenAI-compatible transport generalization.**
   Generalize only after the neutral evidence boundaries are accepted.
6. **Reasoning and sampling profile completion.** Make profile identity and
   comparison eligibility explicit across the mature text paths.
7. **Multimodal support.** Add preserved modality inputs and modality-specific
   scoring after the text/runtime foundations are stable.
8. **Diffusion and non-autoregressive support.** Add generation-native work and
   timing semantics without inheriting autoregressive assumptions.

This program order does not collapse milestones. Contract, dependency admission,
schema work, implementation, integration, presentation, and release preparation
remain separate when required by repository policy.

The LocalMaxxing performance-benchmark lane runs in parallel under its own
bounded sequence. It does not add, remove, or reorder any item in this
eight-step capability program.

## Bounded milestones and dependencies

| Order | Bounded milestone | Depends on | Completion boundary |
|---|---|---|---|
| 1a | Coding-suite architecture and scoring contract | Existing evaluation taxonomy; accepted Generic Core coexistence boundaries | Accepted identity, coverage, evidence, scoring, comparison, and containment split; no prompts or behavior |
| 1b | Coding-oriented text suite content and loader admission | 1a; any separately admitted schema needs | Versioned suite content and deterministic/manual checks that do not execute generated code |
| 1c | Coding execution containment, if admitted | 1a; existing separate D5 gate | Bounded local checker contract and preserved failures; not an agent loop |
| 2a | Multi-turn transcript architecture | 1a for coding feedback use cases | Accepted state, turn, feedback, completion, scoring, privacy, and compatibility contracts |
| 2b | Multi-turn schema and native evaluation behavior | 2a; separate schema milestone | Backward-compatible transcript capture and focused end-to-end validation |
| 3a | Agent Harness import contract | 1a and 2a; general evaluation taxonomy | Supported source identity, authority, completeness, privacy, containment, and immutability rules |
| 3b | Read-only importer and validation | 3a; separate dependency admission if needed | Offline import without command replay or source mutation |
| 3c | Agent-session scoring and reporting | 3b | Verifier outcome, recovery annotations, and model-versus-stack claim boundaries remain visible |
| 4a | Runtime-neutral metric contract | Existing runtime evidence and performance-benchmark taxonomy | Metric semantics, provenance, equivalence, missing values, and aggregation accepted |
| 4b | Expanded failure taxonomy contract | Existing preserved failures; 2a and 3a for turn/agent failures | Closed categories, evidence requirements, precedence, and recovery semantics accepted |
| 4c | Metrics and failure implementation | 4a and 4b; separate schema milestone | Additive capture/validation with legacy artifacts still valid |
| 5a | Existing vLLM product and evidence audit | 4a and 4b; current vLLM contracts | Documented conformance, gaps, and bounded corrective milestones |
| 5b | Shared transport architecture | 5a | Common versus runtime-specific protocol behavior accepted; no new runtime admitted |
| 5c | Transport refactor and later runtime contracts | 5b; one contract per runtime | Current behavior preserved; exact evidence and runtime-specific failures retained |
| 6a | Reasoning/sampling profile contract | Stable text transports; existing profile foundations | Profile identity, precedence, capture, and comparison eligibility accepted |
| 6b | Profile implementation and comparison presentation | 6a; separate schema/integration milestones | Requested/observed profile evidence visible without universal claims |
| 7 | Modality-specific contracts, then implementations | Common evidence/failure foundations; one modality at a time | Original inputs preserved; capability, scoring, and failures explicit |
| 8 | Non-autoregressive contract, then implementations | Common provenance/failure foundations; accepted runtime need | Native generation units and timing; no token-decoding assumptions |

Generic Core suite implementation remains admitted downstream work under its
existing contracts. It can proceed as a separate bounded suite milestone, and
its D1-D7 deterministic checks, separate D5 generated-code containment gate,
execution/result-provenance integration, and `v0.73` release preparation remain
separate. Generic Core does not substitute for the dedicated coding suite,
multi-turn contract, or Agent Harness importer; its accepted resources and
coexistence rules are inputs to those later decisions.

## Release gates

No date is assigned to any gate.

1. **Architecture gate:** this document and the roadmap must agree on scope,
   capability classification, order, dependencies, authority, and non-goals.
   No implementation capability is claimed by passing this gate.
2. **Per-contract gate:** each milestone above must have an accepted focused
   contract before schema, dependency, public CLI, execution, or importer work.
3. **Compatibility gate:** current v0.x native results, historical suites,
   reviewed practical evidence, and Generic Core resources remain valid and
   retain their original authority. Additive work must tolerate unknown optional
   fields and valid legacy artifacts.
4. **Evidence gate:** each implementation must preserve raw source evidence,
   failures, requested versus observed behavior, and source/derivative roles.
5. **Comparison gate:** cross-runtime, cross-profile, cross-harness, cross-modal,
   or cross-generation summaries require explicit eligibility checks and show
   non-equivalence rather than forcing a shared score.
6. **Operator gate:** runtime lifecycle, live model use, network access,
   publication, and destructive repository actions remain explicit
   human-controlled operations.
7. **Release-preparation gate:** version, package, changelog release section,
   tag, installation, and publication changes occur only in a separate release
   milestone after the applicable implementation gates pass.

The existing `v0.73` Generic Core gate remains unchanged by this architecture.
A later human-approved roadmap correction is required only if a future accepted
contract demonstrates a material conflict; this document identifies no such
conflict.

## Historical authority and compatibility

This program is additive. It does not reinterpret current native single-turn
results as transcripts, coding-agent sessions, multimodal results, controlled
performance benchmarks, or non-autoregressive runs. Existing suite identities,
raw artifacts, manual scores, reviewed practical evidence, vLLM evidence, and
published comparisons remain authoritative for their disclosed historical
contracts and conditions.

Generic Core contracts and versioned resources remain accepted. The absent
`generic-core-v1` executable suite remains absent until its separate
implementation milestone passes. New capability contracts must coexist with
historical suites rather than migrating or silently relabeling them.

## Deferred implementation

Everything beyond this architecture and roadmap decision is deferred: suite and
prompt authoring; transcript and result schema changes; harness import;
LocalMaxxing identity/workload and artifact-mapping contracts, execution,
offline export, and validation; runtime or transport edits; metric and failure
implementation; reasoning-profile behavior; multimodal ingestion; diffusion
execution; package/version changes; and release, publication, leaderboard, or
network-submission work.
