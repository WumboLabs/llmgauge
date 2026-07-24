# General Evaluation Taxonomy

## Status and scope

This document is the accepted architecture contract for classifying general
evaluation work in LLMGauge. It defines evidence authority, scoring, comparison,
and integration boundaries. It does not add suites, prompts, schemas, commands,
importers, exporters, execution adapters, runtimes, agents, or harnesses.

Every evaluation belongs to exactly one primary class. A project may produce
related evaluations in multiple classes, but each evaluation retains its own
identity, authoritative artifacts, scoring semantics, and comparison rules.
Shared presentation must not erase those boundaries.

Current LLMGauge prompt runs, context ladders, batches, Fit Ladders, scoring,
reports, comparisons, and public-export workflows remain **native response**
evaluations. This taxonomy does not reinterpret or invalidate their existing
artifacts or contracts.

## Evaluation classes

### Native response

**Evaluated subject:** a model response produced from an LLMGauge-owned prompt
and disclosed model, runtime, generation settings, and hardware context.

**Authority:** LLMGauge native result artifacts are authoritative according to
[Artifact Schemas](ARTIFACT_SCHEMAS.md). Raw prompts, raw outputs, logs,
failures, result metadata, and applied scoring provenance remain source
evidence. Reports, comparisons, indexes, cleaned output, and public exports keep
their documented derivative roles.

**Execution and evidence:** this class contains the current single-prompt and
suite workflows, context ladders, batches, Fit Ladders, runtime evidence,
manual scoring, deterministic checks, reports, comparisons, and sanitized
exports. Existing practical suites and reviewed practical evidence remain valid
native response evaluations.

**Scoring:** deterministic, manual, or hybrid. Deterministic checks may directly
score objectively specified response properties. Manual scores remain review
metadata under the accepted rubrics. Hybrid scoring combines disclosed
deterministic evidence with an explicit human judgment; it must preserve both
components and must not disguise an automatic draft as reviewed judgment.

**Comparison:** prefer the same suite, suite version, prompt set, scoring mode,
rubric, subject definition, and materially equivalent runtime conditions.
Mixed-suite or mixed-runtime summaries must disclose the mismatch and restrict
claims to comparable fields. Manual score averages are not universal rankings.

### Performance benchmark

**Evaluated subject:** a controlled model, runtime, settings, and hardware
configuration measured under a declared benchmark protocol.

**Authority:** the benchmark's controlled native measurements, execution logs,
protocol identity, and configuration record are authoritative. An LLMGauge
report, comparison, index, or export is a derivative unless LLMGauge owns the
benchmark protocol and native artifact contract.

**Execution and evidence:** controlled throughput, time to first token (TTFT),
tokenization, VRAM use and headroom, context scaling, batch and ubatch behavior,
latency, and hardware testing belong here. The benchmark must define admission,
warmup, repetition, sampling, completion, failure, and aggregation rules.

An ordinary practical prompt run may contain useful speed or VRAM observations,
but it is not automatically a performance benchmark. It is not automatically
eligible for LocalMaxxing export or submission. LocalMaxxing export belongs to
this class and requires a separately accepted contract that maps a qualifying
controlled benchmark to an offline derivative. Network submission is a later,
separate publication milestone and is never implied by export eligibility.

**Scoring:** deterministic benchmark metrics. A human may annotate anomalies or
fitness, but manual judgment must not replace measured values. Hybrid scoring is
permitted only when the protocol defines which deterministic and manual
components remain separate.

**Comparison:** compare only measurements with compatible protocol versions,
metric definitions, workload, completion rules, model/runtime settings, and
disclosed hardware conditions. Runtime-native token counts or throughput are
not equivalent without evidence establishing equivalence. Performance metrics
must not be converted into response-quality scores.

### External text benchmark

**Evaluated subject:** a model and disclosed inference configuration evaluated
under an external benchmark's dataset, prompt construction, harness, and metric
contract.

Examples include IFEval, MMLU-Pro, GPQA, LongBench, RULER, and coding
benchmarks. Inclusion here names the class; it does not admit any particular
benchmark, dataset, license, harness, or implementation.

Static or non-executed function-calling benchmarks that evaluate tool selection,
argument generation, or structured calls under an official dataset and metric
belong here. BFCL is an example only when its specific evaluation mode meets
these criteria; classify other modes by their executed behavior rather than the
benchmark name.

**Authority:** the official dataset, dataset version, harness, native outputs,
and official metric artifacts remain authoritative. LLMGauge imports, validates,
and summarizes those artifacts rather than silently reimplementing the dataset,
prompting, answer extraction, or metric. If multiple upstream implementations
claim authority, a benchmark-specific architecture contract must select and
identify the accepted source before integration.

**Scoring:** official metric. Deterministic validation may confirm artifact
shape, identity, completeness, and internally reproducible calculations, but it
does not create a replacement official result. Manual review may annotate
failures or limitations and must remain separate from the official metric.

**Comparison:** compare results only when benchmark identity and version,
dataset split, harness and metric versions, evaluation subject, inference
settings, completion policy, and material limits are compatible. LLMGauge must
show official metrics with their original units and names. Metrics from
different benchmarks or materially different harness versions are separate
signals, not a shared score.

### Agent-environment

**Evaluated subject:** the complete model, agent policy and implementation,
tools, harness, task environment, verifier, limits, and relevant infrastructure
configuration. Terminal-Bench, SWE-bench, browser, computer-use, OSWorld, and
future agent-drift evaluations belong to this class. Executed tool-use
evaluations also belong here when they include an agent loop, tool actions and
observations, mutable state or environment, and a task verifier.

A result measures this full-stack subject under the recorded configuration. It
must not be attributed solely to the underlying model. Changing the agent loop,
tool definitions, prompts, harness, container or VM image, browser, operating
system, dependencies, network policy, verifier, budget, or retry policy may
change the evaluated subject.

**Authority:** the external environment or harness artifacts are authoritative
when an external authority exists. Preserve task identity and version,
trajectories, tool actions and observations, verifier inputs and results,
resource and action limits, completion state, failures, retries, and environment
provenance. LLMGauge imports and summarizes these artifacts without replacing
them. A future LLMGauge-owned environment requires its own accepted native
artifact contract.

**Scoring:** environment verifier. Deterministic checks may validate artifact
structure and declared invariants. Manual review may assess trajectory quality
or classify failure, but it remains separate from the verifier outcome unless a
versioned benchmark contract explicitly defines a hybrid metric.

**Comparison:** require compatible task sets, harness and environment versions,
verifier, tools, permissions, budgets, retry and completion policies, and
full-stack subject definition. Model-only comparisons are prohibited when any
other material stack component differs. Aggregate success rates are meaningful
only within a compatible benchmark contract; trajectory annotations and
verifier metrics from incompatible environments remain separate.

## Cross-class contract

### Evaluation identity and version

Every evaluation type must have a stable, explicit identity and version. The
identity names the protocol and primary class; the version fixes the material
prompt or dataset selection, execution, completion, scoring, and aggregation
semantics. Suite IDs, benchmark IDs, harness versions, task or dataset splits,
and schema versions are related provenance, not interchangeable substitutes.
A material semantic change requires a new evaluation version.

An imported evaluation also records the upstream authority and its version or
immutable identity where available. Unknown identity is reported as unknown; it
must not be inferred into false precision.

### Subject, runtime, harness, and environment provenance

Record enough provenance to identify what was evaluated and under which
conditions:

- model artifact or served-model identity and available fingerprint evidence;
- runtime, executable or server, resolved settings, and prompt/rendering path;
- harness, dataset, metric, verifier, agent, and tool versions where applicable;
- hardware disclosure mode and available privacy-safe observed hardware facts;
- environment image, dependency, permission, network, resource, and action
  limits where they can affect the outcome.

Provenance identifies bounded evidence; it does not authenticate authorship,
hardware identity, model quality, or equivalence. Missing provenance limits
comparison and claims rather than being silently reconstructed.

### Authority and derivatives

The system that owns the evaluation contract owns its native authoritative
artifacts. For LLMGauge native response evaluations, existing LLMGauge artifact
roles continue to apply. For external benchmarks and agent environments, the
official dataset or harness artifacts remain authoritative. LLMGauge imports,
validates, indexes, summarizes, compares, or sanitizes them as explicitly marked
derivatives.

A derivative records its source identity, transformation, validation result,
and generation time. It never mutates, repairs, supersedes, or hides the source.
Structural validation establishes conformance only; it does not establish
quality, correctness, official acceptance, or publication readiness.

### Requested and observed settings

Preserve requested settings separately from observed behavior. A request for a
context size, batch, runtime mode, tool limit, hardware resource, verifier
configuration, or environment capability is not evidence that it became
effective. Record observed values when available and use `unavailable` or
`unknown` honestly when they are not. Fallbacks and retries remain explicit and
must not be relabeled as the original requested configuration.

### Time, completion, and failure

Record evaluation start and end timestamps or explicitly mark unavailable
values. Define completion at the evaluation-contract level and retain item-level
completion where the protocol exposes it. Preserve nonzero exits, signals,
timeouts, OOMs, verifier failures, partial output, failed attempts, retries,
skips, and terminal state. A derivative must not turn a partial or failed native
run into a completed success.

### Privacy, sanitization, and publication

Canonical evidence remains local and private by default. Do not capture or
publish credentials, unrelated environment secrets, or unnecessary private
machine identity. Public output is a separate sanitized derivative that records
its source and redactions and leaves the canonical evidence unchanged.
Sanitization is not proof that all private data was removed; human review is
required before publication.

Offline import, summary, and export do not authorize network access. Publication,
benchmark submission, leaderboard upload, or other network transfer requires a
separate accepted contract and explicit operator action. Claims remain bounded
to the evaluated subject, protocol, evidence, hardware, scoring state, and
observed conditions.

### Scoring modes

Every result declares one primary scoring mode and its versioned method:

| Mode | Authority and use |
|---|---|
| Deterministic | Versioned local rules or measured metrics for objectively specified properties; preserve inputs and calculations needed for review. |
| Manual | Disclosed human judgment under a named rubric; review metadata, not objective or universal truth. |
| Hybrid | Explicit deterministic evidence plus explicit manual judgment; preserve both components and their combination rule. |
| Official metric | The named external benchmark metric produced under its authoritative dataset and harness contract. |
| Environment verifier | The named task-environment verifier outcome under its authoritative environment and limits. |

Annotations may accompany any mode but do not silently change it. An automatic
scoring draft remains unreviewed triage until a human deliberately reviews and
applies it under the native response scoring contract.

### Comparison eligibility

A comparison must identify which fields are comparable before presenting a
summary. At minimum, check evaluation class, evaluation identity and version,
subject definition, authoritative source and versions, task or prompt coverage,
scoring mode and semantics, completion policy, runtime or harness configuration,
limits, and hardware conditions relevant to the claim.

Direct aggregate comparison is eligible only when the metrics have the same
meaning and compatible protocol. Otherwise LLMGauge may present a
side-by-side evidence inventory with explicit incompatibility, but must not
normalize, average, weight, or combine incompatible response scores,
performance measurements, official metrics, and environment-verifier outcomes
into one aggregate score, model ranking, or universal recommendation. A shared
report is not evidence of metric compatibility.

## Integration sequence

Each new evaluation or external integration follows these separate milestones:

1. **Architecture contract** — accept authority, identity, versioning, subject,
   provenance, scoring, comparison, privacy, lifecycle, and claim boundaries.
2. **Read-only import when an external authority exists** — preserve and import
   authoritative native artifacts without mutation or silent reimplementation.
3. **Deterministic validation** — validate supported versions, identity,
   structure, completeness, references, and closed failure categories without
   claiming answer quality or official acceptance.
4. **Bounded execution adapter** — only after import and validation establish the
   artifact boundary; define lifecycle ownership, structured invocation,
   containment, limits, cancellation, failure preservation, and offline-safe
   defaults.
5. **Reporting and comparison** — add derivatives only after authority and
   eligibility rules are enforceable; retain native metrics and incompatibility
   disclosures.
6. **Publication or network submission separately** — require an explicit later
   contract, sanitization, human review, bounded claims, and operator-controlled
   network action.

A step may be unnecessary when no external authority or execution path exists,
but later steps do not authorize skipping an applicable earlier boundary.
Dependency admission, schema changes, and public CLI changes remain separate
milestones when required by repository policy.
