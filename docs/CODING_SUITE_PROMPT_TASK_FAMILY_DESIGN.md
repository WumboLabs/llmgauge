# Coding Suite Prompt and Task-Family Design

## Status and scope

This document proposes the prompt-role and task-family design for the future
`coding-core-v1` suite version `0.1.0`. It follows the accepted
[Coding Suite Architecture and Scoring Contract](CODING_SUITE_ARCHITECTURE_SCORING_CONTRACT.md)
and the sequencing in the
[Full Model Testing Capability Architecture](FULL_MODEL_TESTING_CAPABILITY_ARCHITECTURE.md).
The accepted
[Coding Suite Scoring-Method Design](CODING_SUITE_SCORING_METHOD_DESIGN.md)
specializes this document's scoring-role authority, and the accepted
[Coding Suite Schema and Loader Contract](CODING_SUITE_SCHEMA_LOADER_CONTRACT.md)
specializes its manifest and loading representation.

The proposal fixes:

- eight static, single-turn prompt roles and one primary capability owner for
  each role;
- complete ownership of the eight admitted static capabilities;
- secondary stressors and deliberate overlap;
- suite-owned input/context types and permitted response-form categories;
- a proposed `smoke` profile and default `core` profile with exact order; and
- deterministic, manual, or hybrid scoring authority per static prompt.

It does not provide final prompt prose, expected answers, fixtures, deterministic
algorithms, rubric dimensions, weights, thresholds, schemas, aggregation,
execution, patch application, multi-turn behavior, or suite implementation.
`coding-core-v1` remains unavailable.

## Design rules

Each proposed static prompt has exactly one primary capability owner. A secondary
stressor can make another capability observable, but it neither transfers
ownership nor supplies the owned capability's required coverage. Scope control
is deliberately stressed across several roles while retaining one dedicated
primary owner.

All code, synthetic trees, repository excerpts, issue text, logs, compiler or
test output, dependency declarations, and API documentation are inert,
bounded, versioned, secret-free, suite-owned inputs. They provide no live
repository, filesystem, shell, compiler, test runner, package index, network, or
current external state. Physical source or installed-package paths are not task
facts or portable provenance.

A recommended command is response text, not shell execution. A unified diff or
bounded patch is response text, not an applied change. Supplied failure output
is prompt context, not output observed from the model's response. Closed
structural compliance is evidence only about the declared response envelope; it
is not evidence of semantic or runtime correctness.

## Existing coverage and dedicated-suite separation

The current coding-related tasks remain prompt-specific evidence under their own
suite identities:

| Existing coverage | Present role | Dedicated-suite decision |
|---|---|---|
| `core-v1` `python-log-parser` | Small Python log parser | Do not add another log/result parser. Dedicated roles target diagnosis, patching, tests, uncertainty, scope, and machine-readable handoff boundaries. |
| `agent-backend-v1` `coding/log-summary-helper` | Small Python log summary helper | Do not duplicate small utility generation. Dedicated code production is attached to supplied defects, bounded patches, tests, or closed API evidence. |
| `agent-backend-v1` `shell-safety/failed-command-recovery` | Conservative advice after a missing Linux service command | Keep the dedicated shell role inside a synthetic coding-repository maintenance context and score recommendation safety, not generic service recovery. |
| `wumbolabs-practical-v1` result-summary script role | Practical result summarization code | Preserve its practical comparison role; do not reuse its task or evidence. |
| retired historical fake-package currentness question | Former currentness and package-honesty screening in the removed source-only practical suite | Use closed, versioned API/dependency evidence instead of a fake-package currentness question. |
| proposed Generic Core coding and code-review roles | Portable pure-function implementation and supplied-code defect review | Do not recreate either role. The dedicated debugging role adds stated state-transition evidence and correction design; the API role adds closed integration evidence and an explicit evidence gap. Generic Core resources remain Generic Core-owned. |

Conceptual overlap is allowed only where the dedicated suite changes the owned
coding capability and evidence boundary. Existing prompt text, fixtures, scores,
and comparison contracts are not imported or treated as interchangeable.

## Proposed static inventory

The IDs below are stable proposed prompt IDs for `coding-core-v1` `0.1.0`. They
must not be recycled for materially different tasks if adopted. Every role is a
static single-turn native-response task.

### `debug/state-transition-defect`

- **Task family:** supplied-code debugging.
- **Primary capability owner:** debugging.
- **Secondary stressors:** scope control; dependency/API uncertainty only when
  the supplied contract leaves a fact explicitly unknown.
- **Classification:** static single-turn.
- **Owned input/context type:** a bounded suite-owned code excerpt, a complete
  stated state-transition contract, and supplied reproducible symptom or trace
  facts. Unshown repository state is explicitly unavailable.
- **Permitted response form:** explanation-plus-code.
- **Scoring role:** manual. Diagnosis accuracy, evidence use, correction
  plausibility, and restraint require semantic judgment; no closed structural
  property is material enough to become scoring authority for this role.
- **Comparison and claim boundary:** supports comparison of static diagnosis and
  proposed-correction quality only under identical prompt, suite, scoring, and
  inference conditions. It does not prove that the correction applies, compiles,
  passes, or repairs a live repository.
- **Dedicated-suite reason:** evaluates cause-to-correction reasoning against a
  stated behavioral transition rather than another small utility generator or
  Generic Core's general supplied-code defect-review role.

### `patch/bounded-cross-file-change`

- **Task family:** minimal patch generation.
- **Primary capability owner:** minimal patch generation.
- **Secondary stressors:** scope control; structured output compliance.
- **Classification:** static single-turn.
- **Owned input/context type:** a bounded synthetic file tree or repository
  excerpt, a requested behavior change, declared allowed paths, and explicit
  non-goals.
- **Permitted response form:** unified diff or another explicitly bounded patch
  form; the final prompt will select one, not permit an ambiguous mixture.
- **Scoring role:** hybrid. A future deterministic component may inspect the
  closed patch envelope and declared path membership; manual review remains
  authoritative for semantic correctness plausibility, minimality, and scope.
- **Comparison and claim boundary:** supports comparison of patch-text
  conformance, minimality, scope, and static plausibility. It does not establish
  clean application, repository applicability, compilation, tests, security, or
  runtime behavior.
- **Dedicated-suite reason:** directly owns bounded patch production, which the
  existing small script prompts and proposed Generic Core roles do not measure.

### `tests/behavioral-contract-cases`

- **Task family:** test design and creation.
- **Primary capability owner:** test creation.
- **Secondary stressors:** scope control; structured output compliance.
- **Classification:** static single-turn.
- **Owned input/context type:** a suite-owned behavior contract, relevant public
  interface, and only the bounded code or pseudocode needed to design tests.
- **Permitted response form:** code-only.
- **Scoring role:** hybrid. A future deterministic component may inspect the
  exact code-only envelope and other closed presence requirements; manual review
  remains authoritative for behavioral coverage, boundary selection, failure
  sensitivity, and test quality.
- **Comparison and claim boundary:** supports comparison of static test design
  and response conformance. It does not prove that tests collect, execute, fail
  on a plausible defect, or pass against an implementation.
- **Dedicated-suite reason:** owns test creation as an observable artifact rather
  than treating tests as incidental prose around generated application code.

### `diagnosis/supplied-failure-output`

- **Task family:** failure-output diagnosis.
- **Primary capability owner:** failure diagnosis.
- **Secondary stressors:** debugging; scope control; dependency/API uncertainty.
- **Classification:** static single-turn.
- **Owned input/context type:** bounded suite-owned compiler, test, or runtime
  output with its producer or protocol description, material version facts,
  failure state, deliberate truncation status, and only the related code/context
  required for interpretation.
- **Permitted response form:** explanation-only.
- **Scoring role:** manual. Separating facts, causes, uncertainty, and useful
  discriminating checks is semantic judgment rather than a closed structural
  assertion.
- **Comparison and claim boundary:** supports comparison of interpretation of
  the identical supplied output. It is not evidence that LLMGauge ran the
  producing command, that a proposed next check succeeded, or that the model
  repaired its own prior response.
- **Dedicated-suite reason:** isolates failure-evidence interpretation from
  supplied-code debugging and from the future multi-turn recovery capability.

### `shell/safe-repository-maintenance`

- **Task family:** safe command recommendation.
- **Primary capability owner:** shell-command safety.
- **Secondary stressors:** scope control; dependency/API uncertainty.
- **Classification:** static single-turn.
- **Owned input/context type:** a hypothetical suite-owned repository tree and
  state summary, an operator goal, explicit privilege and data-preservation
  constraints, and any facts needed to bound recommended inspection or mutation.
- **Permitted response form:** explanation-only; command snippets remain quoted
  recommendations inside that response, not executable artifacts.
- **Scoring role:** manual. Inspection-before-mutation, confirmation, rollback,
  privilege, data-loss, network, and uncertainty judgments are not reducible to
  lexical command checks.
- **Comparison and claim boundary:** supports comparison of recommendation
  safety and usefulness in the supplied hypothetical state. It does not prove a
  command is installed, executed, successful, reversible, or safe in another
  environment.
- **Dedicated-suite reason:** evaluates shell advice in a bounded coding-workflow
  context without duplicating the existing missing-service recovery prompt or
  turning LLMGauge into a shell executor.

### `api/closed-evidence-integration`

- **Task family:** dependency and API uncertainty.
- **Primary capability owner:** dependency/API uncertainty.
- **Secondary stressors:** scope control; debugging.
- **Classification:** static single-turn.
- **Owned input/context type:** versioned suite-owned API documentation excerpts,
  dependency declarations, a bounded integration surface, and a deliberately
  disclosed evidence gap. The supplied material states which facts are complete
  and which remain unknown.
- **Permitted response form:** explanation-plus-code.
- **Scoring role:** manual. Correct use of supplied evidence, unsupported
  assumption avoidance, uncertainty, and code plausibility require semantic
  review.
- **Comparison and claim boundary:** supports comparison of evidence-bounded
  integration reasoning and proposed code under the identical closed excerpts.
  It does not support claims about current packages, external documentation,
  symbol availability, network services, installation, or runtime success.
- **Dedicated-suite reason:** tests coding under closed but incomplete interface
  evidence instead of fake-package currentness or unconstrained model memory.

### `scope/distractor-aware-change-plan`

- **Task family:** scoped change planning.
- **Primary capability owner:** scope control.
- **Secondary stressors:** minimal patch generation as planning restraint only;
  dependency/API uncertainty.
- **Classification:** static single-turn.
- **Owned input/context type:** a bounded synthetic tree and excerpts, a focused
  change request, explicit non-goals, and deliberately adjacent but unrelated
  defects or tempting cleanup.
- **Permitted response form:** explanation-only.
- **Scoring role:** manual. File selection, restraint, unsupported repository
  assumptions, and treatment of non-goals require semantic judgment.
- **Comparison and claim boundary:** supports comparison of proposed scope and
  change planning against only the supplied synthetic context. It does not show
  that the repository was inspected, that omitted files do not exist, or that a
  change was implemented.
- **Dedicated-suite reason:** makes repository-boundary discipline the primary
  observable without duplicating the patch role; it requests a plan, not patch
  text or implementation.

### `structured/closed-json-change-record`

- **Task family:** structured coding response.
- **Primary capability owner:** structured output compliance.
- **Secondary stressors:** scope control; instruction compliance.
- **Classification:** static single-turn.
- **Owned input/context type:** a bounded suite-owned code-change request and
  relevant excerpts plus a declared closed JSON record form. Exact fields,
  types, and closed values remain deferred to versioned response-form and
  content design.
- **Permitted response form:** structured JSON closed record only.
- **Scoring role:** hybrid. A future deterministic component may inspect the
  exact envelope, parseability, and closed structural contract; manual review
  remains authoritative for whether the record's meaning is supported by the
  supplied coding context.
- **Comparison and claim boundary:** supports separate comparison of structural
  conformance and semantic record quality under identical contracts. A
  structurally valid record does not prove correct analysis, code correctness,
  patch applicability, or successful machine consumption beyond the declared
  structure.
- **Dedicated-suite reason:** measures machine-readable coding handoff behavior
  while keeping structure and meaning visibly separate; the explanation-only
  scope role does not exercise this response boundary.

## Exact capability ownership and overlap

| Admitted static capability | Sole primary owner | Deliberate secondary overlap |
|---|---|---|
| Debugging | `debug/state-transition-defect` | Failure diagnosis stresses debugging from supplied output; the API role may expose a defect, but neither owns general debugging. |
| Minimal patch generation | `patch/bounded-cross-file-change` | Scope planning stresses change restraint without requesting a patch. |
| Test creation | `tests/behavioral-contract-cases` | No secondary role creates tests; this avoids a duplicate test-generation surface. |
| Failure diagnosis | `diagnosis/supplied-failure-output` | The debugging role receives symptom/trace facts, but failure-output interpretation remains owned here. |
| Shell-command safety | `shell/safe-repository-maintenance` | No other role requests command recommendations. |
| Dependency/API uncertainty | `api/closed-evidence-integration` | Debugging, failure diagnosis, shell advice, and scope planning may include explicitly unknown facts to stress honesty without owning the capability. |
| Scope control | `scope/distractor-aware-change-plan` | Patch, tests, debugging, shell, API, and structured-record roles all retain bounded scope as a cross-cutting stressor. |
| Structured output compliance | `structured/closed-json-change-record` | Patch and test roles use closed response envelopes, but structure is primary only for the JSON record. |

The overlap is asymmetric by design. For example, path conformance contributes
to the patch role's hybrid evidence, but it does not make that prompt a second
primary owner of structured output. Likewise, a debugging response can propose a
correction without becoming the minimal-patch owner because it does not request
a declared patch form.

## Static and future multi-turn classification

All eight inventory members are static single-turn prompts. They receive one
fixed prompt context and produce one model response with no tool, compiler, test,
shell, repository, or feedback channel.

`repair/prior-response-test-feedback` is recorded only as a future role key. It
is **multi-turn-only**, is not a proposed `coding-core-v1` `0.1.0` prompt ID, is
not a member of either profile, and supplies no completed static-suite
capability. Its future context would require the preserved prior model response,
compiler or test feedback introduced between turns, subsequent responses,
termination and retry rules, and correction/recovery/consistency evidence.
Response form, scoring authority, transcript identity, and recovery semantics
remain deferred to the separate multi-turn contract.

The static `diagnosis/supplied-failure-output` role starts with suite-owned
failure output already in its one prompt. It can measure diagnosis of that
inert evidence, not correction of the model's own earlier work. No static prompt
receives recovery eligibility as a recovery score.

## Permitted response-form categories

The proposed inventory needs five response-form categories:

- **Code-only:** exactly the declared source artifact and no explanatory prose.
  Proposed member: `tests/behavioral-contract-cases`.
- **Explanation-plus-code:** bounded diagnosis or reasoning plus one declared
  code artifact. Proposed members: `debug/state-transition-defect` and
  `api/closed-evidence-integration`.
- **Explanation-only:** prose analysis or planning; quoted command snippets are
  recommendations and do not change the form into executable code. Proposed
  members: `diagnosis/supplied-failure-output`,
  `shell/safe-repository-maintenance`, and
  `scope/distractor-aware-change-plan`.
- **Unified diff or bounded patch:** one final prompt-selected patch grammar over
  declared suite-owned paths. Proposed member:
  `patch/bounded-cross-file-change`.
- **Structured JSON closed record:** JSON in one later-defined closed record
  contract, with no prose outside the envelope. Proposed member:
  `structured/closed-json-change-record`.

Each final prompt must select exactly one response form. The accepted scoring
and schema contracts fix the form-reference identities and structural authority,
but do not fix fences, delimiters, patch grammar, JSON fields, extraction rules,
or malformed-response algorithms. Those details belong to the content and later
scoring implementation gates. A response form controls admitted output, not the
truth or quality of its contents.

## Profile proposal

Named profiles are warranted. The full eight-role inventory is the only profile
that covers every admitted static capability, while a stable short profile is
useful for bounded smoke evidence and prompt/rendering checks without changing
suite identity.

### `smoke`

Purpose: a short, diverse static-response sample spanning diagnosis, patch text,
shell safety, and closed structured output. It is not complete coding-capability
coverage and must not be reported as the full suite.

Exact ordered membership:

1. `debug/state-transition-defect`
2. `patch/bounded-cross-file-change`
3. `shell/safe-repository-maintenance`
4. `structured/closed-json-change-record`

### `core`

Purpose: the complete `coding-core-v1` `0.1.0` static capability inventory. It is
the default profile and the only proposed profile eligible for claims covering
all eight admitted static capabilities.

Exact ordered membership:

1. `debug/state-transition-defect`
2. `patch/bounded-cross-file-change`
3. `tests/behavioral-contract-cases`
4. `diagnosis/supplied-failure-output`
5. `shell/safe-repository-maintenance`
6. `api/closed-evidence-integration`
7. `scope/distractor-aware-change-plan`
8. `structured/closed-json-change-record`

`smoke` is an exact ordered subset of `core`, preserving the same relative
order. `core` is the default and full profile; there is no separate `full`
profile, alias, implicit remainder, or CLI behavior in this design. Custom
selection behavior remains governed by existing suite infrastructure and is not
changed here.

## Scoring-role map

| Proposed prompt ID | Primary scoring role | Admitted authority |
|---|---|---|
| `debug/state-transition-defect` | Manual | Semantic diagnosis, evidence use, correction plausibility, and restraint. |
| `patch/bounded-cross-file-change` | Hybrid | Closed patch/path structure separately from manual semantics, minimality, and scope. |
| `tests/behavioral-contract-cases` | Hybrid | Closed code-only/presence structure separately from manual test quality. |
| `diagnosis/supplied-failure-output` | Manual | Semantic interpretation, uncertainty, causal reasoning, and next-check quality. |
| `shell/safe-repository-maintenance` | Manual | Operational safety, privilege, data-loss, rollback, and uncertainty judgment. |
| `api/closed-evidence-integration` | Manual | Supplied-evidence use, unsupported assumptions, uncertainty, and code plausibility. |
| `scope/distractor-aware-change-plan` | Manual | Change restraint, file selection, non-goal compliance, and repository honesty. |
| `structured/closed-json-change-record` | Hybrid | Closed JSON structure separately from manual semantic support. |

No inventory role is deterministic-only. Every proposed coding task contains
material semantic judgment. Hybrid roles admit deterministic authority only for
closed, locally inspectable response properties; their deterministic and manual
components remain visible and independent. Structural failure cannot be
reinterpreted as functional failure, and structural success cannot replace
manual review.

The accepted scoring-method design now names checks, rubric dimensions,
composition, scoreability, and aggregation eligibility. The accepted schema and
loader contract now fixes their manifest references and validation boundary.
Neither document implements scoring or loading behavior.

## Comparison and claim boundary

Aggregate comparison is eligible only for identical `coding-core-v1` suite
version, exact ordered profile membership, prompt inputs and response forms,
compatible future scoring-method identities and review state, and disclosed
model, runtime, rendering, reasoning/sampling, generation, completion, and
hardware conditions required by the architecture contract.

`smoke` and `core` results are not interchangeable because their prompt
membership differs. Prompt-level side-by-side evidence may disclose controlled
differences, but differing prompts, profiles, suite versions, response forms,
scoring authorities, or inference conditions must not be collapsed into one
score or rank.

The proposed suite can support bounded claims about the eight static coding
response capabilities under tested conditions. It cannot establish execution,
clean patch application, successful compilation or tests, command effects,
security, current external API truth, multi-turn recovery, repository outcomes,
agent effectiveness, universal coding rank, or daily-driver reliability.
Generic Core, historical/practical suites, external benchmarks, LocalMaxxing,
future multi-turn results, and Agent Harness sessions retain separate evaluated
subjects and evidence authority.

## Deliberate exclusions and next boundary

The inventory deliberately excludes another small log/result utility, a generic
pure-function task, a second general defect-review role, generic missing-service
recovery, package-currentness questions, live repositories, private paths,
mutable upstream source, network retrieval, command execution, patch
application, generated-code or test execution, and response repair after
feedback.

The selected next bounded milestone is **Coding-suite schema model and loader
implementation**. It may implement only the accepted additive fields,
vocabularies, normalization, coding-suite invariants, contained/no-fallback
validation, public-safe diagnostics, and focused tests; it adds no prompt,
manifest, suite content, scoring, execution, result, or runtime behavior. After
that implementation passes, **Coding-suite content and package implementation**
remains the next admitted gate for the final prompts, inert resources, manifest,
exact profiles, source/package mirrors, package data, and content validation
fixtures/tests.
