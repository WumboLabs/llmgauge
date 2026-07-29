# Coding Suite Scoring-Method Design

## Status and scope

Status: accepted scoring-method design for `coding-core-v1` version `0.1.0`.

This document fixes the proposed scoring identities, manual dimensions,
deterministic structural authority, hybrid composition, scoreability, and
comparison rules for the eight static roles accepted by the
[Coding Suite Prompt and Task-Family Design](CODING_SUITE_PROMPT_TASK_FAMILY_DESIGN.md).
The [Coding Suite Architecture and Scoring Contract](CODING_SUITE_ARCHITECTURE_SCORING_CONTRACT.md)
remains authoritative for the evaluated subject and claim boundaries. The
[Coding Suite Schema and Loader Contract](CODING_SUITE_SCHEMA_LOADER_CONTRACT.md)
defines how a future manifest represents these decisions.

This is a design contract, not scoring implementation. It adds no prompt,
fixture, response-form definition, manifest, rubric file, check code, score or
result schema, execution, patch application, test run, multi-turn behavior, or
runtime integration. `coding-core-v1` remains unavailable.

## Authority and method identities

Every scoring and form reference is a stable lowercase logical ID paired with a
semantic version. A materially changed rubric dimension, check meaning,
composition rule, or response-form contract requires a new method or form
version; an ID is never silently reinterpreted.

| Kind | Logical ID | Version | Authority |
|---|---|---:|---|
| Manual rubric | `coding-core-manual-v0` | `0.1.0` | Role-applicable semantic review for all eight prompts |
| Deterministic check | `coding-core-bounded-patch-envelope-v0` | `0.1.0` | Closed patch envelope, declared path membership, and declared structural requirements only |
| Deterministic check | `coding-core-code-only-tests-envelope-v0` | `0.1.0` | Closed code-only test artifact envelope and declared structural requirements only |
| Deterministic check | `coding-core-closed-json-record-v0` | `0.1.0` | Closed JSON envelope, parsing, and declared record structure only |
| Hybrid composition | `coding-core-side-by-side-v0` | `0.1.0` | Independent deterministic and manual components with no blend or gate |

No deterministic-only coding role is admitted. No profile-level numeric
aggregation method is admitted for `0.1.0`: the role-specific dimensions and
structural outcomes are not commensurate. The existing
`manual_score_average`, if present in result presentation, is not a
`coding-core-v1` capability score and must not be promoted to one.

The future content milestone must bind each prompt to one of these versioned
response-form definitions. Their categories are fixed here; delimiters,
extraction rules, patch grammar, JSON fields, and source-language details remain
deferred.

| Category | Logical form ID | Version | Prompt roles |
|---|---|---:|---|
| `explanation-plus-code` | `coding-core-explanation-plus-code-form-v0` | `0.1.0` | `debug/state-transition-defect`, `api/closed-evidence-integration` |
| `bounded-patch` | `coding-core-bounded-patch-form-v0` | `0.1.0` | `patch/bounded-cross-file-change` |
| `code-only` | `coding-core-code-only-tests-form-v0` | `0.1.0` | `tests/behavioral-contract-cases` |
| `explanation-only` | `coding-core-explanation-only-form-v0` | `0.1.0` | `diagnosis/supplied-failure-output`, `shell/safe-repository-maintenance`, `scope/distractor-aware-change-plan` |
| `closed-json-record` | `coding-core-closed-json-record-form-v0` | `0.1.0` | `structured/closed-json-change-record` |

A form reference specifies the expected response boundary. It does not establish
semantic quality, authorize extraction from malformed output, or authorize use
of model-produced paths.

## Exact role-to-method map

The inventory and order below are fixed. Each role appears exactly once.

| Order | Prompt ID | Primary authority | Manual rubric | Deterministic check | Hybrid composition | Response form |
|---:|---|---|---|---|---|---|
| 1 | `debug/state-transition-defect` | Manual | `coding-core-manual-v0` `0.1.0` | none | none | `coding-core-explanation-plus-code-form-v0` `0.1.0` |
| 2 | `patch/bounded-cross-file-change` | Hybrid | `coding-core-manual-v0` `0.1.0` | `coding-core-bounded-patch-envelope-v0` `0.1.0` | `coding-core-side-by-side-v0` `0.1.0` | `coding-core-bounded-patch-form-v0` `0.1.0` |
| 3 | `tests/behavioral-contract-cases` | Hybrid | `coding-core-manual-v0` `0.1.0` | `coding-core-code-only-tests-envelope-v0` `0.1.0` | `coding-core-side-by-side-v0` `0.1.0` | `coding-core-code-only-tests-form-v0` `0.1.0` |
| 4 | `diagnosis/supplied-failure-output` | Manual | `coding-core-manual-v0` `0.1.0` | none | none | `coding-core-explanation-only-form-v0` `0.1.0` |
| 5 | `shell/safe-repository-maintenance` | Manual | `coding-core-manual-v0` `0.1.0` | none | none | `coding-core-explanation-only-form-v0` `0.1.0` |
| 6 | `api/closed-evidence-integration` | Manual | `coding-core-manual-v0` `0.1.0` | none | none | `coding-core-explanation-plus-code-form-v0` `0.1.0` |
| 7 | `scope/distractor-aware-change-plan` | Manual | `coding-core-manual-v0` `0.1.0` | none | none | `coding-core-explanation-only-form-v0` `0.1.0` |
| 8 | `structured/closed-json-change-record` | Hybrid | `coding-core-manual-v0` `0.1.0` | `coding-core-closed-json-record-v0` `0.1.0` | `coding-core-side-by-side-v0` `0.1.0` | `coding-core-closed-json-record-form-v0` `0.1.0` |

This is five manual roles and three hybrid roles. Deterministic methods apply
only to the three hybrid roles and only to their closed structural properties.

## Manual rubric contract

### Scale, verdict, and provenance

`coding-core-manual-v0` uses the repository's existing `0` through `5` scale:

- `5`: excellent for the supplied prompt and bounded workflow;
- `4`: good, with minor caveats;
- `3`: usable but meaningfully incomplete or risky;
- `2`: weak, unreliable, or missing important constraints;
- `1`: mostly unusable, unsafe, or substantially incorrect; and
- `0`: severe failure, dangerous output, or central unsupported invention.

`null` means a dimension was not scored. A numeric zero is an observed severe
failure, never a substitute for missing evidence, absent review, truncation, or
a check error.

The reviewer records one of `pass`, `mixed`, `fail`, or `needs_review` when a
verdict is assigned. Verdict is a reasoned overall judgment, not a thresholded
average and not inferred from deterministic status. Before review, verdict may
remain empty under existing score-file conventions. Every reviewed verdict and
every non-null dimension requires prompt-specific rationale citing preserved
prompt/output evidence. Reviewer identity, rubric ID/version, review state,
`reviewed`, scoring mode, scorer identity/version where applicable, evidence,
warnings, override status, and review time must remain attributable through the
existing manual-score provenance boundary. Assisted or drafted values remain
unreviewed until a human deliberately reviews and applies them.

### Dimensions

The rubric has a shared versioned vocabulary but a strict applicability map;
reviewers must not score irrelevant dimensions.

| Dimension | Meaning |
|---|---|
| `diagnosis_accuracy` | Identifies the supplied failure or state-transition cause accurately, distinguishes cause from symptom, and proposes discriminating reasoning supported by the record. |
| `supplied_evidence_use` | Uses material facts actually supplied, reconciles relevant excerpts, and does not substitute imagined repository, runtime, or external state. |
| `correction_code_plausibility` | Proposed correction, patch, or code is technically coherent against the stated interface and behavior, without claiming execution proof. |
| `minimality_scope_control` | Selects only necessary files, changes, commands, or claims; respects allowed paths and explicit non-goals; avoids unrelated cleanup. |
| `instruction_compliance` | Follows the requested task and semantic response requirements. Structural envelope facts remain owned by any applicable deterministic check. |
| `response_completeness` | Supplies every material explanation, artifact, caveat, or next step required to judge the requested response without padding. |
| `shell_operational_safety` | Uses inspection before mutation, least privilege, confirmation and preservation controls, bounded rollback, and honest treatment of data-loss, network, and environment risk. |
| `uncertainty_unsupported_assumptions` | Separates supplied fact from inference and unknown state, avoids invented execution or environment claims, and calibrates uncertainty. |
| `dependency_api_honesty` | Uses only the versioned API/dependency evidence supplied, identifies disclosed gaps, and avoids claims about current or external availability. |
| `test_quality_failure_sensitivity` | Chooses behaviorally meaningful boundaries and invariants and proposes tests capable of failing on plausible defects rather than merely exercising plumbing. |
| `semantic_record_support` | Ensures each structured-record assertion and requested action is semantically supported by the supplied coding context. JSON shape remains deterministic authority. |

### Exact applicability

`required` means the dimension must receive a score for a fully reviewed,
scoreable response. `not applicable` means it must remain `null`.

| Prompt ID | Required manual dimensions |
|---|---|
| `debug/state-transition-defect` | `diagnosis_accuracy`, `supplied_evidence_use`, `correction_code_plausibility`, `minimality_scope_control`, `instruction_compliance`, `response_completeness`, `uncertainty_unsupported_assumptions` |
| `patch/bounded-cross-file-change` | `supplied_evidence_use`, `correction_code_plausibility`, `minimality_scope_control`, `instruction_compliance`, `response_completeness`, `uncertainty_unsupported_assumptions` |
| `tests/behavioral-contract-cases` | `supplied_evidence_use`, `minimality_scope_control`, `instruction_compliance`, `response_completeness`, `uncertainty_unsupported_assumptions`, `test_quality_failure_sensitivity` |
| `diagnosis/supplied-failure-output` | `diagnosis_accuracy`, `supplied_evidence_use`, `instruction_compliance`, `response_completeness`, `uncertainty_unsupported_assumptions` |
| `shell/safe-repository-maintenance` | `supplied_evidence_use`, `minimality_scope_control`, `instruction_compliance`, `response_completeness`, `shell_operational_safety`, `uncertainty_unsupported_assumptions` |
| `api/closed-evidence-integration` | `supplied_evidence_use`, `correction_code_plausibility`, `minimality_scope_control`, `instruction_compliance`, `response_completeness`, `uncertainty_unsupported_assumptions`, `dependency_api_honesty` |
| `scope/distractor-aware-change-plan` | `supplied_evidence_use`, `minimality_scope_control`, `instruction_compliance`, `response_completeness`, `uncertainty_unsupported_assumptions` |
| `structured/closed-json-change-record` | `supplied_evidence_use`, `minimality_scope_control`, `instruction_compliance`, `response_completeness`, `uncertainty_unsupported_assumptions`, `semantic_record_support` |

Format failure in a hybrid response does not automatically make semantic
dimensions unscoreable. If the preserved response still exposes enough
unambiguous content, a reviewer may score supported dimensions and explain the
scope of review. Conversely, structurally valid text may remain semantically
unscoreable.

### Scoreability and review states

Manual review consumes the exact rendered prompt, suite-owned referenced input,
raw response, cleaned response only as a derived aid, generation completion and
failure metadata, applicable rubric version, and any deterministic result only
as separate context. Raw evidence remains authoritative.

A prompt is fully scoreable when the complete required prompt/input and enough
of the response are preserved to judge every applicable dimension with specific
rationale. Its manual state is `reviewed` only when all applicable dimensions
and a verdict have been deliberately reviewed.

A prompt is partially scoreable when evidence supports some, but not all,
applicable dimensions. Supported dimensions may be scored; unsupported ones
remain `null`; verdict is `needs_review`; state is `partial`; rationale names the
missing or ambiguous evidence. Partial values are not treated as a complete
prompt score.

A prompt is unscoreable when the prompt or required owned input is missing or
malformed, no response evidence exists, truncation removes the material needed
to judge any dimension, or preserved artifacts conflict so the evaluated text
cannot be identified. All dimensions remain `null`, verdict is `needs_review`,
and the reason is preserved. `missing` means no manual review record exists;
`unreviewed` means a record or draft exists but no human review is complete.
Neither state implies failure or zero.

Generation failure and truncated output remain execution evidence. Reviewers may
score only what is actually preserved and must not infer omitted content,
intended completion, successful patching, compilation, tests, command effects,
external API facts, or repository state. A refusal may be scored when complete
enough to judge against the task; failure metadata itself is not a semantic
score.

## Deterministic structural methods

### Common boundary and outcomes

Each deterministic method consumes only the preserved raw response, generation
completion/failure metadata, the exact versioned response-form definition, and
the closed prompt declarations needed by that definition. It performs bounded,
local, non-executing parsing. Cleaned output is not substituted for raw output.

The outcome vocabulary is:

- `pass`: every property owned by the check is observed to conform;
- `fail`: the response is available and one or more owned structural properties
  are observed not to conform;
- `error`: the check itself could not evaluate a validly declared input because
  of an internal, unsupported, or resource-bounded check failure; and
- `not_run`: no check attempt occurred, including when required response evidence
  is absent after a generation failure.

Each result preserves check ID/version, outcome, bounded property-level evidence,
input/form identities, and error classification when applicable. `error` is not
model-response failure. `not_run` and `error` never become `fail`, zero, or a
manual verdict. A malformed, extra, or truncated model response is `fail` only
when the check ran and directly observed nonconformance within its authority.

No check executes or applies code, patches, commands, or tests; compiles;
dynamically imports; evaluates templates; accesses the network; resolves a
model-produced path; or reads outside declared suite-owned inputs. No lexical or
substring rule may claim safety, minimality, diagnosis, semantic correctness,
test quality, dependency truth, or functional success.

### `coding-core-bounded-patch-envelope-v0` `0.1.0`

This check applies only to `patch/bounded-cross-file-change`. It may establish:

1. conformance to the one selected `coding-core-bounded-patch-form-v0` envelope;
2. successful structural parsing under that versioned form definition;
3. absence of prohibited prose or undeclared artifacts outside the envelope;
4. membership of every patch-declared path in the prompt's closed allowed-path
   set, using normalized logical paths only; and
5. required artifact count and ordering only where the form definition and
   prompt declare them explicitly.

It does not apply the patch, inspect a live tree, infer whether context lines
match, evaluate minimality, determine semantic correctness, compile, run tests,
or claim safety. An undeclared path is structural nonconformance; it is not proof
that any filesystem write occurred.

### `coding-core-code-only-tests-envelope-v0` `0.1.0`

This check applies only to `tests/behavioral-contract-cases`. It may establish:

1. conformance to the one selected `coding-core-code-only-tests-form-v0`
   envelope;
2. successful structural extraction or parsing required by that versioned form;
3. absence of prohibited explanatory prose or extra artifacts; and
4. presence, count, type, and order of artifacts only where explicitly declared
   by the form definition and prompt.

It does not collect, import, compile, or execute tests or application code. It
cannot establish behavioral coverage, failure sensitivity, assertion quality,
compatibility, or whether the source would run. Those facts remain manual or
future execution authority.

### `coding-core-closed-json-record-v0` `0.1.0`

This check applies only to `structured/closed-json-change-record`. It may
establish:

1. exactly one permitted JSON envelope with no extra prose;
2. successful parsing as one JSON object;
3. exact closed key membership;
4. declared key types, closed enum values, required values, and cardinalities;
   and
5. ordering only where the versioned form definition explicitly makes array or
   member order material.

The future form definition supplies the actual fields and values; this milestone
does not finalize them. The check does not infer semantic support from keyword
matches, trust paths or actions in the object, execute anything, or claim that a
consumer accepted the record. Semantic support remains manual authority.

## Per-role scoring behavior

| Prompt ID | Evidence and valid outcome | Scoreability and failure handling | Claim and aggregation boundary |
|---|---|---|---|
| `debug/state-transition-defect` | Manual rubric over supplied transition contract, symptom/trace, code excerpt, and response; manual states `missing`, `unreviewed`, `partial`, `reviewed` with nullable dimensions and allowed verdicts | Missing/malformed input or unusable output is unscoreable; truncation may permit partial review; generation failure stays separate | Static diagnosis and correction plausibility only; eligible only for prompt-level reviewed comparison or coverage summaries |
| `patch/bounded-cross-file-change` | Independent patch check `pass`/`fail`/`error`/`not_run` plus manual rubric over supplied tree, behavior, paths, non-goals, and response | Structural failure does not force manual failure; malformed/truncated envelope may fail the check while semantics remain partial; check error is not response failure | Patch-text structure and reviewed plausibility/scope only; no application, compile, test, or repository claim |
| `tests/behavioral-contract-cases` | Independent code-only check plus manual rubric over behavior contract, interface, bounded context, and response | Missing response produces check `not_run` and manual missing/unscoreable as applicable; structural success does not establish test quality | Static test design and response conformance only; no collection, execution, pass, or defect-detection claim |
| `diagnosis/supplied-failure-output` | Manual rubric over supplied output, producer/protocol facts, truncation status, related context, and response | Review must honor declared source truncation separately from model-output truncation; absent causal evidence cannot be invented | Interpretation of identical supplied failure evidence only; no command run, repair, or multi-turn recovery claim |
| `shell/safe-repository-maintenance` | Manual rubric over hypothetical tree/state, operator goal, safety constraints, and recommendation | A dangerous complete answer is scoreable and may receive zero; absent environment facts require uncertainty, not invented validation | Recommendation quality under the supplied hypothetical state only; no execution, availability, rollback, or external safety claim |
| `api/closed-evidence-integration` | Manual rubric over versioned closed excerpts, declarations, disclosed gap, bounded surface, and response | External/current facts are prohibited inference; missing owned evidence makes affected dimensions unscoreable rather than guessed | Evidence-bounded integration reasoning and code plausibility only; no package, symbol, install, network, or runtime claim |
| `scope/distractor-aware-change-plan` | Manual rubric over synthetic tree/excerpts, request, non-goals, distractors, and plan | Review cannot infer unshown files or repository inspection; incomplete plan may be partial or scored low only when enough evidence remains | Proposed scope and planning against supplied context only; no implementation or repository-completeness claim |
| `structured/closed-json-change-record` | Independent JSON check plus manual semantic review over request, excerpts, declared record form, and raw object | Parse failure may make manual semantics unscoreable or partial but never auto-zero; check error stays separate; valid JSON may still fail semantics | Separate structural conformance and supported record meaning only; no code, patch, or machine-consumption success claim |

## Hybrid composition

`coding-core-side-by-side-v0` `0.1.0` preserves exactly one supported
deterministic result and one applicable `coding-core-manual-v0` review state for
a hybrid prompt. It does not calculate a weighted value, average, threshold,
gate, override, fallback, or synthetic component.

A complete hybrid scoring record requires both a completed deterministic outcome
(`pass` or `fail`) and a fully `reviewed` manual component. `error`, `not_run`,
`missing`, `unreviewed`, `partial`, and unscoreable states remain visible and
make the combined record incomplete. Incomplete does not mean failed. A
structural `fail` remains independent from the reviewed manual verdict; a
structural `pass` cannot fill manual dimensions or establish semantics. Manual
failure cannot be rewritten as structural failure.

Consumers may display components together and summarize completeness. They must
not emit an unexplained zero, suppress a component, or claim a combined coding
quality value.

## Profiles, custom selection, and bounded summaries

The exact ordered `smoke` membership is:

1. `debug/state-transition-defect`;
2. `patch/bounded-cross-file-change`;
3. `shell/safe-repository-maintenance`; and
4. `structured/closed-json-change-record`.

The default `core` membership is:

1. `debug/state-transition-defect`;
2. `patch/bounded-cross-file-change`;
3. `tests/behavioral-contract-cases`;
4. `diagnosis/supplied-failure-output`;
5. `shell/safe-repository-maintenance`;
6. `api/closed-evidence-integration`;
7. `scope/distractor-aware-change-plan`; and
8. `structured/closed-json-change-record`.

There is no `full` alias or separate profile. Custom prompt selection remains an
explicit ordered custom set and must not be reported as `smoke`, `core`, or full
capability coverage. `repair/prior-response-test-feedback` is multi-turn-only
and belongs to none of these sets.

Because no profile-level numeric method is admitted, a profile or custom set may
produce only transparent coverage/state summaries: selected and present prompt
IDs, generation success/failure/truncation counts, deterministic outcome counts
by exact method version, manual review-state and verdict counts by exact rubric
version, and hybrid completeness counts. Prompt-level dimension values remain
prompt-level evidence.

A named-profile coverage summary is eligible only when suite ID/version, exact
ordered membership, prompt sources and owned inputs, response-form identities,
scoring identities/versions, and selected profile all match the declared
contract. Missing prompts, generation failure, check `error`/`not_run`, or absent
or partial manual review must be counted explicitly; none is dropped or imputed.
A custom set is summarized only as that exact set.

Cross-run comparison must disclose and keep separate any difference in scoring
method version, membership, response form, prompt/input identity, manual review
state, model/runtime, rendering, sampling/reasoning, generation/completion, or
relevant hardware condition. Differing conditions are not merged into one score.

No result from this suite is combined into a universal coding score or with
multi-turn repair, Agent Harness, Generic Core, LocalMaxxing, practical or
historical suites, external benchmarks, or future generated-code execution.
Static results support only response-quality claims under the tested and
reviewed conditions.

## Deferred implementation boundary

The selected next bounded milestone is **Coding-suite schema model and loader
implementation**. It may represent and normalize the accepted fields and logical
references, enforce the fixed role/profile/form/scoring/non-execution
invariants, preserve containment and compatibility, and add focused validation
tests. It adds no prompt, manifest, suite content, scoring-method implementation,
result integration, execution, or runtime behavior.

After that implementation passes, **Coding-suite content and package
implementation** remains the next admitted gate. It must preserve the IDs,
versions, mappings, authority split, profiles, and exclusions in this design.
Scoring implementation, result integration, generated-code or command execution,
patch application, multi-turn scoring, aggregation beyond the bounded state
summaries above, and Agent Harness import remain separate, unselected gates.
