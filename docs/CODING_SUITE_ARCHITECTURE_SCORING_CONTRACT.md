# Coding Suite Architecture and Scoring Contract

## Status and scope

This document is the accepted architecture and scoring contract for a future
dedicated LLMGauge coding suite. It completes bounded milestone 1a in the
[Full Model Testing Capability Architecture](FULL_MODEL_TESTING_CAPABILITY_ARCHITECTURE.md):
identity, coverage, evidence authority, scoring roles, comparison boundaries,
and the split between static response evaluation and later execution or
multi-turn work.

This milestone adds no final prompt, fixture, suite manifest, schema, loader,
check implementation, scoring code, code execution, command execution,
transcript, Agent Harness importer, runtime behavior, package version, or release
behavior. The dedicated coding suite remains unavailable until later milestones
are accepted and implemented.

The accepted
[prompt and task-family design](CODING_SUITE_PROMPT_TASK_FAMILY_DESIGN.md),
[scoring-method design](CODING_SUITE_SCORING_METHOD_DESIGN.md), and
[schema and loader contract](CODING_SUITE_SCHEMA_LOADER_CONTRACT.md) now supply
the downstream inventory, method, and representation authorities. This
architecture remains authoritative where those narrower documents do not
specialize it.

## Current baseline and admission

Current LLMGauge coding-related coverage is distributed across existing native
response suites:

- `core-v1` `0.1.0` contains a small Python log-parser response task;
- `agent-backend-v1` `0.1.0` contains a log-summary helper, shell-failure
  recovery advice, configuration-edit planning, and tool-honesty screening;
- `wumbolabs-practical-v1` `0.2.0` contains a result-summary script task under
  its practical comparison contract; and
- Generic Core has accepted coding and code-review roles plus versioned D5 case
  and limit resources, but no executable `generic-core-v1` suite or admitted D5
  generated-code containment.

These tasks provide bounded prompt-specific native-response evidence. They do
not collectively form a dedicated coding suite, establish broad coding
coverage, prove executed correctness, demonstrate multi-turn repair, or measure
an Agent Harness session. This contract preserves every existing suite identity,
version, prompt, score, and evidence role.

Admission is **PASS** for an architecture-only contract. Final prompt design,
schema work, suite implementation, scoring implementation, and generated-code
execution remain separate gates.

## Stable evaluation and suite identity

The dedicated suite identity is:

- evaluation class: **LLMGauge native single-turn response evaluation**;
- suite ID: **`coding-core-v1`**;
- initial suite version when implemented: **`0.1.0`**.

`coding-core-v1` names the durable dedicated coding-response contract. It is not
an alias, rename, replacement, profile, or new version of `core-v1`,
`agent-backend-v1`, `wumbolabs-practical-v1`, or `generic-core-v1`. This
contract creates no CLI alias.

The evaluated subject is a model-generated response to an LLMGauge-owned,
versioned coding prompt under disclosed model identity, runtime, generation and
sampling settings, prompt rendering, selected prompt or profile membership, and
available hardware context. The subject is the response under those conditions,
not a repository change, successful program, completed tool action, coding-agent
trajectory, or universal property of the model.

The initial suite version fixes the eventual prompt sources, owned task inputs,
permitted response forms, exact prompt and profile membership, scoring roles and
method versions, and aggregation semantics. The next prompt-design milestone
must decide whether named profiles are needed and, if so, their exact ordered
membership. A profile name without exact membership is insufficient provenance.

Material changes require a new suite version, including changes to prompt text
or rendering, task inputs, expected response grammar, prompt/profile membership,
scoring role or semantics, rubric or deterministic method, compiler/test evidence,
or any future containment-dependent behavior. Prompt IDs must be stable within a
suite version and must never be recycled for materially different tasks.

## Evaluation-class separation

### Native single-turn coding response

The initial `coding-core-v1` subject is one static model response per prompt.
LLMGauge owns the prompt contract and native artifacts. A prompt may supply code,
a patch, repository excerpts, compiler output, test output, API documentation,
or dependency facts as inert context. The model receives no live repository,
tool, shell, compiler, test runner, or feedback channel through this contract.

A static prompt can evaluate diagnosis of supplied evidence, a proposed patch,
test design, command recommendations, uncertainty, scope discipline, or a
structured response. It cannot establish that the proposal applies, compiles,
passes tests, is secure, or works in a repository.

### Later multi-turn repair evaluation

Repair after compiler or test feedback is a separate multi-turn evaluation
contract. It requires preserved conversation state, the model's prior response,
feedback produced or supplied between turns, every subsequent response,
termination and retry rules, and correction, recovery, and consistency scoring.

A single prompt may include pre-existing compiler or test output and ask for a
diagnosis or proposed repair. That is still static native-response evidence. It
does not demonstrate that the model repaired its own earlier answer after
feedback. `coding-core-v1` must not award a recovery score or claim
repair-after-feedback capability from one static response.

### Agent Harness session evidence

A WumboLabs Agent Harness session is agent-environment evidence. The harness owns
repository inspection, tool actions and observations, edits, commands, tests,
failures, retries, recovery, final diff, verifier outcome, limits, and environment
provenance. LLMGauge may later import supported sessions read-only under a
separate contract.

A `coding-core-v1` response is model-only native response evidence under the
recorded inference conditions. An Agent Harness result measures the complete
model, agent policy, tools, harness, environment, verifier, limits, and retry
policy. Their scores and outcomes must never be merged into one coding score.
This contract does not launch an agent, replay a session, apply a patch, or infer
session success from a model response.

### External coding benchmarks

An official external coding benchmark remains an external text benchmark or an
agent-environment evaluation according to its actual execution model. Its
dataset, harness, verifier, and official metrics retain their authority.
`coding-core-v1` neither reimplements nor absorbs those identities or metrics.

## Required capability coverage

The dedicated coding program must cover all nine required capabilities. The
initial static suite may directly cover the first eight within the boundaries
below. The ninth is reserved for later multi-turn evaluation.

| Capability | Static single-turn admission | Boundary |
|---|---|---|
| Debugging | Admitted | Diagnose supplied code, symptoms, traces, or bounded state and propose a correction; no live inspection or execution. |
| Minimal patch generation | Admitted | Produce a bounded patch or replacement for supplied files/excerpts while avoiding unrelated changes; no patch application. |
| Test creation | Admitted | Propose tests against supplied behavior, interfaces, and failure cases; no test execution. |
| Failure diagnosis | Admitted | Interpret supplied compiler, test, or runtime output and distinguish cause, evidence, and next checks; supplied output is not an observed LLMGauge run. |
| Shell-command safety | Admitted | Recommend bounded commands with inspection, confirmation, rollback, and uncertainty where appropriate; no shell execution. |
| Dependency and API uncertainty | Admitted | Use supplied API/dependency evidence, identify missing version or documentation facts, and avoid invented availability or behavior. |
| Scope control | Admitted | Limit changes and recommendations to the requested files, behavior, and constraints; do not claim unseen repository knowledge. |
| Structured output compliance | Admitted | Follow a declared code-only, patch, record, or explanation-plus-code response contract; no structure implies semantic correctness. |
| Repair after compiler or test feedback | Multi-turn only | Requires a prior model response and preserved inter-turn feedback; static diagnosis of already supplied output is not recovery evidence. |

No aggregate `coding-core-v1` claim may imply that the static suite covers the
multi-turn-only capability. Reports must show it as not evaluated until the
later transcript contract and behavior exist.

## Minimum admitted task families

This contract admits task-family boundaries, not final prompts or mandatory
prompt counts. The next design milestone must propose a bounded inventory with
one primary owner for each required static capability and disclose deliberate
overlap.

### Supplied-code debugging

Input is a bounded code excerpt plus a complete stated behavior, symptom, or
error context. The response identifies the defect and proposes a correction.
Review distinguishes diagnosis accuracy from the plausibility of the proposed
code. Missing repository state remains unknown.

### Minimal patch generation

Input identifies the owned file excerpt or synthetic file set, requested change,
and explicit non-goals. The response is a declared patch/diff or bounded
replacement. Minimality and scope control are primary evidence. A text patch is
not applied and does not prove repository applicability.

### Test design and creation

Input supplies the behavior contract, relevant interface, and bounded code or
pseudocode when needed. The response proposes tests covering meaningful success,
boundary, invariant, transition, precedence, or real-error behavior. Review
penalizes tests that only mirror implementation plumbing or incidental text. The
tests are not run.

### Failure-output diagnosis

Input includes bounded, prompt-owned compiler, test, or runtime output with its
source and any facts needed for interpretation. The response separates observed
facts, likely causes, uncertainty, and discriminating next checks. It must not
claim the output came from commands executed by LLMGauge.

### Safe command recommendation

Input defines a hypothetical local state and operator goal. The response may
recommend commands but must preserve inspection-before-mutation, confirmation,
bounded scope, rollback, privilege, data-loss, and network boundaries. A command
recommendation is response text, not a tool invocation or observed effect.

### Dependency and API uncertainty

Input provides a closed documentation excerpt, dependency declaration, API
surface, or explicit evidence gap. The response uses supplied facts, labels
unsupported assumptions, requests or recommends specific verification where
needed, and does not invent package versions, symbols, signatures, or runtime
availability.

### Structured coding response

Input fixes one permitted response form whose structure is material to the task.
This family may overlap another semantic family as a declared stressor, but
format conformance does not replace correctness review.

Scope control is cross-cutting across every task family. The prompt-design
milestone must make scope boundaries observable rather than treating generic
brevity as evidence of minimality.

## Task input and response boundaries

### Code-only and explanation-plus-code

Each prompt must choose one response contract before execution:

- **code-only** permits only the declared source form and is suitable when prose
  would prevent reliable extraction or violate the user request;
- **explanation-plus-code** requires clearly bounded reasoning or diagnosis plus
  a declared code region; and
- **explanation-only** may be used for diagnosis, uncertainty, test strategy, or
  safe command advice when no code artifact is requested.

A model must not be rewarded for adding prose to a code-only task. Conversely,
code without the required diagnosis is incomplete in an explanation-plus-code
task. Final delimiters, language forms, and extraction rules belong to later
prompt and scoring-method design.

### Patch and diff responses

A patch task must identify the supplied file identities, allowed paths, base
excerpt or synthetic tree, requested scope, and accepted response form. The
response may be checked for declared patch structure, permitted paths, and
prohibited unrelated files without applying it. A syntactically plausible diff
does not prove correct context, clean application, compilation, tests, security,
or minimal semantics.

Model-provided paths are response data. They never authorize filesystem access,
file creation, editing, or traversal.

### Compiler and test output

Compiler, test, linter, or runtime output included in a prompt is versioned,
prompt-owned evidence. Its producer, command or protocol description, relevant
version, exit or failure state, and any deliberate truncation must be disclosed
when material. The output must be bounded and secret-free.

It may support static diagnosis or a proposed fix. It is not an observed result
of the model's response, and it must not be relabeled as a LLMGauge-executed
command. Feedback generated between model turns belongs to the future multi-turn
contract.

### Repository excerpts

Repository files, trees, diffs, configuration, or issue text are inert,
LLMGauge-owned prompt context or versioned suite resources. They are not live
repository access. The prompt fixes which excerpts exist and whether absent
facts are intentionally unknown. The model must not claim to inspect, modify,
search, stage, commit, or test unseen repository state.

No task may depend on a private checkout, mutable external repository, user home,
network retrieval, or current third-party source unless a later contract admits
and versions that authority.

### Dependency and API evidence

A task must state whether dependency/API facts are complete, deliberately
incomplete, or supplied through a closed excerpt. Scoring rewards correct use of
provided facts and honest identification of missing evidence. Unsupported but
plausible details remain errors; currentness claims require versioned supplied
evidence rather than model memory.

### Malformed, incomplete, and partial responses

Raw output remains preserved when a response is empty, truncated, malformed,
contains prohibited extra material, omits required sections, or cannot be
unambiguously parsed. A versioned deterministic structural check may fail or
error only according to its declared boundary. A parser or extraction error must
not be converted into evidence that the underlying code is functionally wrong.

Manual review follows the scoreability contract. Reviewers may record
incompleteness, malformed output, or review-metadata-only findings instead of
forcing a semantic score when required evidence is unavailable. Provider,
transport, timeout, and partial-output failures remain execution outcomes, not
suite-definition or code-correctness findings.

## Source, packaged, and installed ownership

LLMGauge owns the future `coding-core-v1` prompt and suite resources. When
implemented:

- editable source belongs under `suites/coding-core-v1/`;
- packaged resources belong under
  `src/llmgauge/builtin_suites/coding-core-v1/`; and
- installed discovery uses the package `builtin_suites/` tree under the same
  suite ID and version.

Editable, packaged, and installed forms are one logical suite, not separate
evaluation identities. The same version must have identical manifest meaning,
prompt/profile order, normalized suite-relative references, and owned file
bytes. Only private physical roots may differ, and those host paths must not
become portable provenance.

A missing packaged resource is a package-definition failure. The loader must not
fall back to editable source, another suite, a working directory, a user path,
or the network. Source/package equivalence, installed discovery, and package-data
validation are implementation gates, not behavior added by this contract.

The accepted [schema and loader contract](CODING_SUITE_SCHEMA_LOADER_CONTRACT.md)
now fixes those representation, equivalence, discovery, containment, and
no-fallback requirements for `coding-core-v1` `0.1.0`; implementation remains
deferred.

The future suite must own or explicitly reference every task input under an
accepted versioned ownership contract. It must not silently consume Generic Core
D5 fixtures, historical prompt sources, private repositories, mutable external
documentation, or user artifacts. Reuse of a concept does not transfer authority
or make fixture bytes interchangeable.

## Evidence ownership and trust boundaries

| Evidence | Authority | Boundary |
|---|---|---|
| Prompt, task context, declared response form, and eventual suite metadata | Versioned `coding-core-v1` suite | Fixes what the model was asked and what evidence it received; structural validity is not answer quality. |
| Raw model response, logs, failures, requested/observed settings, and native result metadata | Existing LLMGauge native result contract | Authoritative response evidence under disclosed conditions; cleaned output and reports remain derivatives. |
| Supplied code, repository excerpts, compiler/test output, API excerpts, and synthetic file trees | Versioned prompt or suite-owned resource | Inert input evidence only; not live inspection, execution, or external truth beyond the declared task. |
| Deterministic check result | Future supported check identity/version | Authoritative only for declared objective assertions; does not create semantic or runtime proof. |
| Manual review | Named versioned rubric and disclosed reviewer state | Human judgment metadata, not objective truth or universal model quality. |
| Hybrid result | Separate deterministic and manual authorities | Components remain visible side by side; no unexplained blend or substitution. |
| Multi-turn repair transcript | Future LLMGauge transcript contract | Separate evaluation evidence; absent from the initial static suite. |
| Agent Harness session | WumboLabs Agent Harness for supported imports | External full-stack authority; read-only import and never model-only evidence. |

LLMGauge remains evaluator and artifact owner for its native response contract.
It does not become a coding agent, repository editor, patch applier, shell
executor, compiler, test runner, or runtime supervisor through this suite.
Requested commands, paths, patches, or tests in model output remain untrusted
data.

## Scoring contract

Every prompt declares one primary scoring role: **deterministic**, **manual**,
or **hybrid**. The accepted prompt and task-family design fixes the eight-role
authority map, and the accepted
[scoring-method design](CODING_SUITE_SCORING_METHOD_DESIGN.md) names and
versions its checks, rubric, composition, scoreability, and aggregation
eligibility. This architecture defines the governing suitability and authority
boundaries.

### Deterministic suitability

Deterministic checks are suitable only for closed, objectively specified,
locally inspectable response properties that require no generated-code or
command execution, for example:

- parseability and exact permitted response envelope;
- code-only versus required explanation sections;
- declared file/path membership in a patch response;
- required or prohibited extra files and sections;
- exact structured keys, types, cardinality, ordering, or closed values;
- bounded diff grammar or code-fence presence when the prompt makes it material;
- explicit required test-case names or categories under a closed task contract;
  and
- response completeness facts such as required artifacts being present.

A structural check may establish format compliance, not semantic correctness.
Lexical or substring checks may enforce an explicitly required literal token or
serve as labeled triage; they must not score general correctness, safety,
minimality, uncertainty, diagnosis, or test quality.

Generated code, patches, commands, and tests must not be executed by any
`coding-core-v1` deterministic check until a separate containment and
resource-limit contract is accepted and implemented. Static text inspection must
not masquerade as runtime testing.

### Manual-review suitability

Manual review is required for semantic and judgment-bearing properties,
including:

- functional-correctness plausibility against the supplied contract;
- diagnosis accuracy and evidence use;
- minimality and scope control;
- instruction compliance beyond closed structure;
- operational and shell-command safety;
- uncertainty, unsupported assumptions, and dependency/API honesty;
- test quality, boundary selection, and failure sensitivity;
- response completeness and practical usefulness; and
- maintainability observations that are actually supported by the supplied
  response and context.

Manual scores remain disclosed human judgment. Reviewers must separate observed
response evidence from assumptions about execution or repository state. A
reviewer may judge that code appears correct, but static review cannot certify
functional runtime correctness.

### Hybrid suitability

Hybrid scoring is suitable when objective response conformance and semantic
quality are both material, such as a minimal patch in an exact response envelope
or tests supplied in a required structure. Deterministic and manual components
must be stored and reported independently with their method identities, versions,
inputs, outcomes, and review state. One component must not silently replace,
zero, gate, or fabricate the other. Any eventual combination rule requires a
separate accepted scoring-method design.

### Scoring dimensions and claim limits

The prompt/scoring design must map each task to only dimensions that its evidence
can support. At minimum it must address:

- functional correctness;
- diagnosis accuracy;
- minimality and scope control;
- instruction compliance;
- structured output correctness;
- safety;
- uncertainty and unsupported assumptions;
- test quality;
- response completeness; and
- recovery eligibility for later multi-turn work.

`Recovery eligibility` is metadata identifying a task suitable for a future
feedback turn; it is not a static recovery score. Correction, recovery, and
cross-turn consistency belong to the future multi-turn contract.

Static deterministic or manual review cannot prove runtime correctness, clean
patch application, repository applicability, security, maintainability,
successful tests, successful commands, or successful agent behavior. Passing
closed checks cannot establish correctness outside their declared inputs.

Automatic or assisted scoring drafts remain unreviewed triage until deliberately
reviewed and applied. They must never be relabeled as manual judgment. Missing,
partial, unreviewed, and reviewed states remain visible; missing manual evidence
must not be filled by deterministic output.

## Comparison eligibility

Aggregate coding-response comparison is eligible only when all material
boundaries are compatible:

- evaluation class is native single-turn response;
- suite ID and suite version are identical;
- selected profile, if any, and exact ordered prompt membership are identical;
- prompt/task inputs and response contracts are materially equivalent;
- scoring roles, check/rubric identities and versions, review state, and any
  aggregation method are compatible;
- model identity and available provenance are disclosed;
- runtime, prompt rendering, reasoning/sampling profile, generation settings,
  and requested versus observed behavior are disclosed; and
- relevant hardware disclosure and completion/failure state are visible.

Prompt-level side-by-side evidence may disclose a controlled difference, but the
differing variable and every incompatibility must remain explicit. Different
suite versions, prompt/profile membership, task inputs, response forms, scoring
modes, rubrics, or materially different runtime settings must not be collapsed
into one score or rank.

Single-turn and multi-turn results are separate evaluations. A later multi-turn
repair result must disclose transcript identity/version, prior response,
feedback, turn count, termination, and recovery semantics; it cannot be averaged
with a static `coding-core-v1` score as though the task were identical.

Native coding responses and Agent Harness sessions have different evaluated
subjects and evidence authorities. Model-response scores must not be combined
with harness verifier outcomes, trajectory annotations, tool success, test
results, or repository final-state evidence into one coding score. A shared
report may present them as explicitly incompatible evidence dimensions only.

External benchmark official metrics, Generic Core scores, LocalMaxxing
performance measurements, and coding-suite response scores also remain separate.
No comparison supports universal coding rank, general security, maintainability,
agent effectiveness, or daily-driver reliability.

## Generic Core relationship and coexistence

`generic-core-v1` remains a general native-response suite identity. Its accepted
coding prompt role measures one portable pure-function task, and its code-review
role measures supplied-code defect judgment. Its D5 cases and limits belong to
Generic Core and remain dependent on a separate generated-code containment gate.

`coding-core-v1` is broader dedicated coding-response coverage. It does not
supersede Generic Core, import its results, or reinterpret its resources. Generic
Core D5 containment does not automatically authorize execution for the coding
suite; any shared containment mechanism requires an explicit accepted contract
that identifies ownership, isolation, supported languages, invocation, resource
limits, failure semantics, and evidence provenance for each suite.

Existing suite identities coexist unchanged:

| Suite | Preserved role |
|---|---|
| `core-v1` `0.1.0` | Existing Tier 1 practical smoke suite with one manual coding response. |
| `agent-backend-v1` `0.1.0` | Native-response agent-backend screening, including coding usefulness and shell safety; not agent-environment evidence. |
| `wumbolabs-practical-v1` `0.2.0` | Current practical comparison suite with its manual scoring contract. |
| `generic-core-v1` `0.1.0` | Admitted general-purpose suite work with separate D5 ownership and containment gate; not yet executable. |
| `coding-core-v1` `0.1.0` | Future dedicated coding native-response suite; not implemented by this contract. |

No existing prompt, manifest, alias, fixture, score, result, report, or evidence
artifact changes under this contract.

## Generated-code and command-execution prohibition

This contract authorizes no execution of model-generated code, tests, patches,
or shell commands. It authorizes no patch application, repository mutation,
dependency installation, compiler invocation, test invocation, subprocess,
container, VM, sandbox, network access, or dynamic import.

A future execution milestone is admitted only after a separate containment and
resource-limit contract defines at least structured invocation, supported
languages and toolchains, immutable inputs, writable scope, process isolation,
filesystem containment, environment and dependency policy, network denial,
CPU/memory/time/process/output limits, cancellation, cleanup, captured stdout and
stderr, exit and signal handling, check-error versus model-failure semantics,
privacy, and artifact preservation. If those guarantees cannot be validated,
execution admission fails closed.

The static suite may still preserve model-generated source or patch text as raw
response evidence. It may perform non-executing structural parsing under a later
accepted scoring method. Neither action is execution or runtime proof.

## Ordered downstream gates

This contract completes only the architecture/scoring-contract gate. Downstream
work remains separated as follows:

1. **Coding-suite prompt and task-family design.** Fix the proposed prompt-role
   inventory, task ownership, exact capability coverage, static versus
   multi-turn labels, permitted response forms, profile proposal, and scoring
   role per prompt. Add no final prompt text, schema, check code, or execution.
2. **Coding-suite scoring-method design.** Define versioned deterministic-check
   semantics, manual rubric ownership, scoreability, hybrid component handling,
   and aggregation eligibility. Add no executable scorer or artifact schema.
3. **Coding-suite schema and loader contract.** Define additive manifest,
   profile, task-input, response-form, scoring-reference, normalization,
   containment, source/package, and compatibility boundaries.
4. **Coding-suite schema model and loader implementation.** Implement only the
   five accepted additive generic fields, controlled coding vocabularies,
   normalization, logical-reference support, exact `coding-core-v1` invariants,
   contained/no-fallback validation, public-safe diagnostics, and focused
   regression tests. Add no coding manifest, prompt, suite content, scorer,
   execution, result integration, runtime work, or release change.
5. **Coding-suite content and package implementation.** Add the accepted
   manifest, final prompts, owned inert resources, exact membership, and
   source/package mirrors without scoring or executing generated content.
6. **Static deterministic-check and scoring integration.** Implement only
   accepted non-executing checks and scoring provenance under the existing
   manual-review boundary.
7. **Native run/result/report integration.** Preserve exact selected membership,
   response form, scoring state, failures, and bounded claims end to end.
8. **Generated-code containment contract and implementation, if admitted.** Keep
   contract and implementation separate; do not substitute text heuristics when
   safe execution is unavailable.
9. **Multi-turn transcript and repair evaluation.** Proceed only under the
   separately accepted multi-turn sequence in the Full Model Testing
   architecture.
10. **Agent Harness import and session evaluation.** Proceed separately under
   the agent-environment authority and read-only import sequence.

The selected next bounded milestone is **Coding-suite schema model and loader
implementation**, with the exact bounded scope and exclusions recorded in the
[roadmap](ROADMAP.md). After that implementation passes, **Coding-suite content
and package implementation** remains the next admitted gate.

## Acceptance and deferred work

This contract is accepted when the repository and roadmap agree on:

- `coding-core-v1` and initial version `0.1.0` as a new native single-turn suite;
- all nine capability boundaries and the static/multi-turn split;
- minimum task-family, response-form, input, evidence, scoring, and comparison
  rules;
- source/package/installed ownership and coexistence with current suites;
- Generic Core D5 and Agent Harness separation;
- fail-closed generated-code and command-execution deferral; and
- the ordered downstream gates, with the current completed and selected state
  recorded in the roadmap.

Deferred work includes every final prompt and task input, profile membership,
manifest or schema, fixture or baseline, deterministic algorithm, rubric
implementation, scoring code, loader behavior, suite packaging, result-field
change, containment mechanism, generated-code execution, transcript, Agent
Harness importer, runtime/metric change, package version, release, and
publication action.
