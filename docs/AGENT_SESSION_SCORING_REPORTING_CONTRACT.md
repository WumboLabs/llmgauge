# Agent-session Scoring and Reporting Contract

## Status and scope

Status: accepted contract design for Full Model Testing order 3c. It specializes
[General Evaluation Taxonomy](GENERAL_EVALUATION_TAXONOMY.md), [Full Model
Testing Capability Architecture](FULL_MODEL_TESTING_CAPABILITY_ARCHITECTURE.md),
and the [Agent Harness Import Contract](AGENT_HARNESS_IMPORT_CONTRACT.md). It
adds no schema, importer, validator, score, report generator, comparison,
export-index, public export, CLI, or execution behavior.

A later, separately human-gated implementation milestone may specialize scoring
and reporting only within this contract. It must not reopen source authority,
state, claim, compatibility, or publication decisions made here.

## Preserved evidence identity and authority

This contract preserves exactly the imported identity established by the import
contract:

| Concept | Required value |
| --- | --- |
| Evidence schema | `llmgauge.agent_harness_evidence.v0` |
| Evidence contract | `0.1.0` |
| Evaluation class | `external_agent_environment` |
| Source type | `wumbolabs_omp_session` |
| Source format | `wumbolabs.omp.session_jsonl` version `3` |
| Source producer | `wumbolabs.omp` |
| Source authority | WumboLabs OMP v3 contained canonical source package |

One result continues to represent one imported session through one contained,
normalized evidence package. The package remains canonical private source
evidence; `evidence.json` is the normalized mapping to its contained source
members. This contract creates no second session, conversational view, native
prompt result, or reconstruction of the imported record. In particular, it
MUST NOT convert, use as, or merge with `llmgauge.transcript.v0`.

The source session, source task outcome, source verifier, source tool and
repository observations, and source provenance remain harness-owned facts.
LLMGauge structural validation and every future scoring, review, report,
comparison, and publication record are derivatives. They cite source identities
and references but never repair, replace, suppress, or promote mutable
derivative content into source authority.

## Separate authorities and non-implications

The following decisions are independent. An implementation MUST preserve their
separate provenance and MUST NOT infer one from another.

| Concept | Authority | What it establishes | What it does not establish |
| --- | --- | --- | --- |
| Import outcome | LLMGauge import transaction | Whether a contained package was published | Source task success, evidence quality, review, or publication readiness |
| Structural validation | LLMGauge validator | Represented structure, containment, integrity, and consistency | Repository correctness, action execution beyond represented evidence, task success, quality, safety, scoreability, or publication readiness |
| Evidence completeness | Source-backed import mapping | Whether required source members and lifecycle relationships are retained; `complete` or explicit `partial` | Semantic correctness, source outcome, or reviewability by itself |
| Source session/task outcome | OMP source | The source-backed terminal outcome | LLMGauge score, model-only success, or verifier authority beyond its source meaning |
| Source harness verifier outcome | OMP source verifier | The named verifier's observed outcome under its represented source conditions | An LLMGauge score, semantic review, publication readiness, or model-only quality |
| Evidence-derived observation | Versioned LLMGauge method | A narrowly declared fact calculated only from preserved evidence | Unobserved execution, repository correctness, task success, or model quality |
| Human reviewer judgment | Named human reviewer under a versioned rubric | Reviewer judgment with rationale and cited evidence | Objective truth, verifier replacement, or universal model quality |
| Scoreability and review state | This contract's state model | Whether a defined review can be performed and its progress | Source success or publication readiness |
| Publication readiness | Future publication contract and human review | Nothing in 3c; it remains unassessed | Any inference from import, validation, completeness, verifier, review, or report |

A source verifier result MUST retain its source verifier identity, available
version/configuration, exact source references, availability, and native
outcome. It is an `environment_verifier` source fact under the taxonomy, not an
LLMGauge manual, deterministic, hybrid, or numeric score. A source score-like
field receives the same treatment.

## Bounded scoring and review methods

No universal agent score, agent leaderboard score, model-quality aggregate, or
reinterpretation of native `results[].score` is admitted. Existing native score
files, rubric IDs, summaries, and score statuses retain their meanings and MUST
NOT be reused for imported Agent Harness sessions.

The first future human-review representation is a separate method:

| Field | Required value |
| --- | --- |
| Method ID | `agent-session-review-v0` |
| Method version | `0.1.0` |
| Primary mode | `manual` |
| Authority | Human reviewer judgment |
| Subject | The recorded full-stack session, bounded by the attribution record |
| Aggregate | None admitted |

This method has two closed finding kinds: `judgment` and `annotation`. A finding
MUST name exactly one target from this authority table. The target defines the
permitted review subject; it does not grant the reviewer authority to replace
the named source fact.

| Target | Review authority and boundary |
| --- | --- |
| `task_completion_evidence` | Human judgment about preserved evidence for the source task outcome; never a replacement outcome. |
| `instruction_adherence_evidence` | Human judgment about adherence demonstrable from preserved task/session evidence. |
| `tool_use_evidence` | Human judgment about recorded tool requests, observations, and lifecycle evidence; never unrecorded tool execution. |
| `recovery_evidence` | Human judgment about an admitted source-backed recovery relation and preserved outcome evidence. |
| `repository_change_evidence` | Human judgment about preserved repository-state, diff, patch, snapshot, manifest, or verifier evidence; never live repository correctness. |
| `final_response_evidence` | Human judgment about the preserved final response in its recorded session context. |
| `attribution_boundary` | Annotation of applicable attribution components, uncertainty, or claim limits under this contract. |
| `evidence_limitation` | Annotation of missing, redacted, unavailable, partial, or otherwise insufficient evidence. |

A `judgment` finding MUST use one of the first six targets. An `annotation`
finding MUST use `attribution_boundary` or `evidence_limitation`; it does not
silently become a judgment.

A `judgment` finding MUST use exactly one closed `judgment_outcome`:
`favorable`, `mixed`, `unfavorable`, or `not_assessable`. These are qualitative
reviewer judgments about the named target only; they do not mean source task
success/failure, verifier pass/fail, model quality, or a score on a shared
scale. An `annotation` finding has no `judgment_outcome`. A
`not_assessable` judgment or an `evidence_limitation` annotation MUST state the
missing, redacted, unavailable, or insufficient evidence and its source
reference or explicit unavailable state.

Every finding MUST retain its finding kind, target, reviewer, method
identity/version, review time, evidence-completeness state, source references,
rationale, attribution record, and limitations. A rationale explains the
relationship between the cited evidence and the judgment or annotation; it
MUST NOT supply an uncited source fact. A `favorable`, `mixed`, or
`unfavorable` judgment requires evidence sufficient for that declared target.
It may assess only preserved evidence, MUST label the result as reviewer
judgment, and cannot overwrite a source outcome or verifier result.

An implementation MAY add the separate, non-scoring method
`agent-session-evidence-observation-v0` version `0.1.0` only for repeatable,
source-preserved facts: reference availability and capture state, source event
ordering/lifecycle facts, recorded source terminal and verifier fields, and
source-backed recovery links. Its record MUST retain inputs/source references,
method version, outcome, and errors. It MAY NOT execute commands, tools, tests,
or verifiers; inspect a repository; infer that an unrecorded command succeeded;
or establish repository correctness, task success, semantic quality, safety, or
model quality. Structural validation remains its own authority rather than a
score produced by this method.

No hybrid composition is admitted by this contract. A later contract is required
before combining manual judgment, source verifier outcomes, or evidence-derived
observations into any metric.

## Attribution and claim boundary

The evaluated subject is the recorded full stack, never the model alone. Future
review/report records MUST contain a source-referenced attribution record for
each material observation or finding. It has these closed values:

- `model_behavior`;
- `harness_agent_policy`;
- `tool_behavior`;
- `repository_environment`;
- `verifier_behavior`;
- `runtime_provider`;
- `operator_control`; and
- `missing_or_incomplete_evidence`.

A record may identify multiple applicable values. It MUST also retain an
`attribution_state` of `observed`, `reviewer_inference`, `unavailable`, or
`unknown`. `observed` requires source evidence of the stated component's
behavior; `reviewer_inference` requires a rationale and cannot be rendered as a
proven causal fact. `unavailable` and `unknown` preserve the gap. An observation
that is only full-stack evidence MUST use every material applicable component or
`unknown`; it MUST NOT be rendered as model-only evidence.

Attribution does not establish causation merely because an event occurred after
another event. Missing model, harness, tool, repository, verifier, runtime,
provider, limit, permission, or operator provenance narrows claims and can make
a review unscoreable or a comparison ineligible.

## Recovery and source sequence

Recovery is source-backed sequence evidence, not a final Boolean. Source
ordering MAY be retained only as contextual sequence evidence. It MUST NOT by
itself establish feedback association, correction, feedback consumption, or a
recovery relationship. A future record MAY identify a recovery episode only
through an admitted source-backed relationship represented by the Agent Harness
evidence model, with its authority and source references preserved. Each episode
retains, where available:

- the initial failure, defect, or incomplete state and its source reference;
- the later corrective or recovery attempt and its source reference;
- tool, repository, environment, and verifier feedback linked through that
  admitted source-backed relationship;
- the later terminal outcome or verifier observation;
- interruption, timeout, denial, abandonment, or unknown state; and
- evidence-completeness and availability limits for every linked item.

A later success MUST NOT erase an earlier failure, and an earlier failure MUST
NOT prevent representation of a later recovery. Message shape, source ordering,
temporal proximity, or polished final text alone MUST NOT establish a correction
relationship, feedback consumption, or successful recovery. Where an admitted
relation is absent, retain separate events and state `unknown` rather than
inventing a recovery narrative.

## Scoreability and review-state model

The import contract's `complete` and `partial` evidence-completeness values,
source terminal outcome, and validation outcome remain unchanged. Future
Agent Harness scoring/reporting uses the following closed, versioned derivative
states; they are not native `summary.scoring_status` values.

| State field | Closed values | Meaning |
| --- | --- | --- |
| `scoreability` | `not_assessed`, `scoreable`, `unscoreable`, `not_applicable` | Whether `agent-session-review-v0` can evaluate a declared review target from preserved evidence. `not_applicable` requires a stated target/method mismatch. |
| `review_state` | `not_started`, `awaiting_review`, `in_review`, `reviewed`, `incomplete_review`, `unavailable`, `not_applicable` | Human-review progress. `reviewed` requires the method's required findings/rationale; `incomplete_review` preserves started but insufficient review. |
| `publication_state` | `not_assessed`, `ineligible` | 3c admits no positive publication state. `ineligible` records a known contractual blocker only; absence of that value is not readiness. |
| `comparison_state` | `not_assessed`, `eligible`, `ineligible`, `unavailable` | Eligibility for a specifically named later compatibility decision, never a generic ranking permission. |

A scoreability decision MUST cite the declared review target, method/version,
required evidence categories, structural-validation state, evidence-completeness
state, and missing or unavailable evidence. It MUST NOT be inferred solely from
import success, validation success, source outcome, verifier outcome, or
completeness. A complete package may remain unscoreable because a target,
rubric, provenance, or necessary source reference is absent. A partial package
may be scoreable for a narrower explicitly declared observation; its partial
state remains visible.

`awaiting_review` means scoreable evidence is awaiting a human. `reviewed` is
human review metadata, not an objective score. `unavailable` is for a review
that cannot proceed because necessary evidence or the declared method is
unavailable. `not_applicable` is not a synonym for missing evidence.

The following scoreability/review-state pairs are the only legal combinations:

| `scoreability` | Legal `review_state` |
| --- | --- |
| `not_assessed` | `not_started` |
| `scoreable` | `awaiting_review`, `in_review`, `reviewed`, `incomplete_review` |
| `unscoreable` | `incomplete_review`, `unavailable` |
| `not_applicable` | `not_applicable` |

`incomplete_review` under `unscoreable` records that a review began before
required evidence was found insufficient. A later scoreability reassessment is
a new derivative decision; it MUST retain the earlier incomplete review rather
than rewriting its state. All other pairs are invalid, including `reviewed`
with `unscoreable` or `not_applicable`, and `unavailable` with `scoreable`.

## Derivative report contract

A future Agent Harness human report is a derivative review aid, never canonical
source authority and never a reconstructed transcript. It MUST cite the
canonical evidence ID, imported session ID, source package identity, and source
run fingerprint where represented; record its generator identity/version and
generation time; and describe its transformation and omissions.

The report has these required sections, using `unavailable`, `unknown`, or
`not_assessed` rather than placeholders when source support is absent:

1. **Report scope and claim limits** — derivative status, evaluated full-stack
   subject, non-model-only boundary, and excluded claims.
2. **Evaluation and evidence identity** — evaluation/evidence contract identity,
   source/session identity, source/harness identity and available versions,
   canonical source references, and structural-validation state.
3. **Evidence and terminal summary** — evidence completeness; source terminal
   session/task outcome; source verifier outcome(s); available limits and
   missing, redacted, unavailable, or unknown evidence.
4. **Scoring and review** — source verifier separated from evidence-derived
   observations and human judgment; method identities/versions; scoreability;
   review state; reviewer rationale/annotations; and no aggregate unless a later
   accepted method defines one.
5. **Recovery and attribution** — source-backed recovery episodes, incomplete
   or interrupted recovery, feedback references, and per-finding attribution
   values/states.
6. **Comparison and publication boundary** — comparison state and compatibility
   basis; private-evidence status; publication state; required later gates.
7. **Source references** — bounded references sufficient to audit claims without
   duplicating the trajectory, raw command output, private repository contents,
   or a reconstructed session.

The report MAY summarize source facts with explicit citations. It MUST NOT add,
mutate, hide, or replace contained source evidence, source verifier results, or
run-fingerprint identity. Reviewer notes, report content, comparison decisions,
and publication decisions remain mutable derivatives.

## Comparison eligibility

No Agent Harness comparison is implemented or generally authorized. A future
comparison decision may set `eligible` only for the named claim when all
material conditions are established and compatible:

- the `external_agent_environment` evaluation class and this evidence/contract
  identity and version;
- source/harness identity, supported source format, available implementation
  version, and source semantics;
- task identity/material and verifier identity, configuration, and semantics;
- the model plus agent-policy/full-stack subject definition, including material
  prompts and agent implementation;
- tools, tool versions, permissions, network policy, and material environment
  conditions;
- repository/environment basis and available state identity;
- runtime/provider, model, settings, and observed/requested conditions where
  material to the claim;
- action, time, resource, context, retry, recovery, and completion policies;
- evidence completeness, structural-validation state, and source outcome
  semantics; and
- the same review method/version, review target, scoreability/review state, and
  any later admitted metric or aggregation semantics.

Unknown or unavailable material provenance makes aggregate comparison
`unavailable` or `ineligible`, according to whether the compatibility decision
cannot be made or a known mismatch exists. Incompatible sessions may be shown
only as separate evidence inventories with the mismatch stated; they MUST NOT
be normalized, averaged, weighted, ranked, or attributed to models alone.
Verifier outcomes and reviewer annotations from incompatible full stacks remain
separate.

## Publication and fingerprint boundaries

Imported Agent Harness evidence remains canonical private evidence. Import
completion, validation, complete evidence, verifier success, human review, or
report generation does not establish publication readiness. This contract admits
no Agent Harness public export, sanitization, publication workflow, network
submission, or positive publication state. A future publication contract must
define source-preserving sanitization, redaction summary, derivative provenance,
claim limits, human review, and explicit operator publication action.

The existing immutable imported-source/run fingerprint is unchanged. It covers
canonical source identity and mapping, including source terminal and completeness
facts, but excludes reports, reviewer notes, manual scores, deterministic
observation derivatives, comparisons, export indexes, sanitized exports, and
publication decisions. A future derivative MAY have its own identity/provenance
record containing its method/generator identity, source run fingerprint, source
references, and generation time. It MUST NOT alter, extend, or authenticate
transformed bytes with the imported-source fingerprint.

## Native consumer and implementation gates

Current native single-turn scoring, native transcript scoring, generic native
comparison, current native `report.md`, public export, and export-index behavior
continue to fail closed for imported Agent Harness evidence. This contract does
not authorize their reinterpretation or extension.

A later 3c implementation may add only an Agent Harness-specific derivative
scoring/review representation and human report that enforce this contract. It
remains separately gated from any comparison implementation, public-export or
sanitization implementation, export-index expansion, source-identity change,
importer/validator/fingerprint change, runtime-neutral metric work, session
replay, repository inspection, command/tool/test execution, or model/provider
execution.
