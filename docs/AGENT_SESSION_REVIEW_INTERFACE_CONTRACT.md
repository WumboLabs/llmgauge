# Agent-session Review Interface Contract

## Status and scope

Status: accepted interface design for the separately human-gated implementation
milestone following Full Model Testing order 3c. This document implements none
of the interfaces it defines. It specializes the accepted
[Agent-session Scoring and Reporting Contract](AGENT_SESSION_SCORING_REPORTING_CONTRACT.md)
and [Agent Harness Import Contract](AGENT_HARNESS_IMPORT_CONTRACT.md); those
contracts remain the semantic and source-authority authorities.

Admission is **PASS** for one mutable manual-review derivative and one
Agent-Harness-specific human report. It does not admit a result-envelope change,
importer change, structural-validator change, fingerprint change, comparison,
public export, export-index, execution, or observation method.

## Review artifact identity, location, and authority

The sole initial persisted review derivative is a JSON document with this fixed
identity:

| Field | Exact value |
| --- | --- |
| Artifact schema | `llmgauge.agent_session_review.v0` |
| Artifact version | `0.1.0` |
| Method ID | `agent-session-review-v0` |
| Method version | `0.1.0` |
| Canonical contained path | `agent-harness/review/agent-session-review.json` |
| Serialization | UTF-8 JSON object; no comments or duplicate keys |

The artifact is reviewer metadata, not source evidence. Canonical Agent Harness
bytes and `agent-harness/evidence.json` remain immutable source authority. A
reviewer MUST NOT edit, repair, suppress, replace, or reinterpret them. The
report is a mutable derivative generated from canonical source evidence plus
this optional review artifact. The existing imported-source/run fingerprint may
be cited but neither identifies nor authenticates review or report bytes.

No `llmgauge-result.json` discovery reference is added. The fixed contained path
is unambiguous, is validated relative to the imported result root, and keeps the
existing result envelope and immutable fingerprint projection unchanged.

`--init` creates an editable JSON template adjacent to the canonical artifact at
`agent-harness/review/agent-session-review.template.json`; it is not a reviewed
artifact and is never report input. Applying a candidate writes only the fixed
canonical artifact atomically. Replacing an existing canonical artifact,
including a reviewed artifact, requires explicit `--force`. Template replacement
also requires `--force`.

## Bounded review resources and publication

Review parsing uses the established Agent Harness JSON-depth (`64`) and
identifier-length (`192`) limits, with smaller review-specific collection limits.
The candidate, template, and canonical document are each one regular UTF-8 JSON
file of at most 1 MiB (1,048,576 bytes) and nesting depth at most 64. JSON is
parsed with duplicate-key rejection before schema validation.

The following are the complete review-specific limits:

| Item | Limit |
| --- | --- |
| Findings | 64 |
| Required-evidence-basis items | 16 |
| Declared review targets | 8 |
| Source references per finding or basis item | 32 |
| Limitations per document | 32 |
| Limitations per finding | 16 |
| Reviewer tags per finding | 16 |
| Attribution values per finding | 8 |
| Reviewer ID, finding ID, basis ID, and source-reference ID | 192 characters |
| RFC 3339 UTC timestamp | 64 characters |
| Rationale | 4,096 characters |
| Limitation | 1,024 characters |
| Reviewer tag | 64 characters |

All listed strings are non-empty after trimming where required. The 4,096-character
rationale limit applies to finding, evidence-basis, and attribution rationales.
No other free-form string, collection, or nesting is admitted: identity values
have their fixed digest/enum shape, source-reference type is closed, and the
remaining fields are fixed literals, booleans, or null. The limits are validation
limits, not a change to Agent Harness source-import limits.

`--init` and `--apply` write only after complete candidate/template validation.
Without `--force`, `--init` refuses an existing template and `--apply` refuses
an existing canonical review: both are no-clobber errors. Publication uses the
existing atomic contained-artifact write pattern with no-replace publication when
`--force` is absent, so an artifact appearing after the pre-check also fails
rather than being overwritten. With `--force`, the validated complete file
atomically replaces the destination. Any validation, write, or publication
failure leaves no valid-looking partial destination.

## Exact review document shape

The review document is a closed top-level object. Unknown keys are invalid. Its
required fields are:

```json
{
  "schema_version": "llmgauge.agent_session_review.v0",
  "artifact_version": "0.1.0",
  "method": {
    "method_id": "agent-session-review-v0",
    "method_version": "0.1.0",
    "mode": "manual"
  },
  "source": {
    "evidence_schema_version": "llmgauge.agent_harness_evidence.v0",
    "evidence_contract_version": "0.1.0",
    "evaluation_class": "external_agent_environment",
    "evidence_id": "sha256:<64 lowercase hex>",
    "imported_session_id": "sha256:<64 lowercase hex>",
    "source_package_sha256": "<64 lowercase hex>",
    "source_run_fingerprint_state": "represented",
    "source_run_fingerprint": {
      "schema_version": "llmgauge.run_fingerprint.v0",
      "algorithm": "sha256",
      "value": "sha256:<64 lowercase hex>"
    }
  },
  "reviewer": {"reviewer_id": "reviewer identifier"},
  "reviewed_at_utc": "RFC 3339 UTC timestamp or null for a template",
  "declared_review_targets": ["task_completion_evidence"],
  "scoreability": {
    "value": "scoreable",
    "required_evidence_basis": [{
      "basis_id": "task-outcome",
      "target": "task_completion_evidence",
      "state": "sufficient",
      "rationale": "Reviewer basis.",
      "source_references": [{
        "reference_type": "source_terminal",
        "reference_id": "source_terminal"
      }]
    }]
  },
  "review_state": "awaiting_review",
  "findings": [],
  "evidence_completeness": "complete",
  "limitations": [],
  "publication_state": "not_assessed",
  "comparison_state": "not_assessed"
}
```

`source_run_fingerprint_state` is exactly `represented` or `not_represented`.
It is `represented` only with the exact fingerprint object in the owning result;
it is `not_represented` only with `source_run_fingerprint: null`. The other
`source` fields must exactly equal the contained normalized evidence. This binds
a review to one imported session without changing its identity.

`declared_review_targets` is a non-empty unique list of the eight accepted
targets. `scoreability.value` and `review_state` use exactly the closed values
and legal scoreability/review-state pairs established by the semantic contract.
For this initial workflow, both `publication_state` and `comparison_state` are
required literals: `not_assessed`. The broader semantic-contract vocabularies
are reserved for later separately accepted implementations; a candidate,
template, canonical artifact, or report input with any other value is invalid.

`required_evidence_basis` is a non-empty list except for `not_assessed`. Each
item contains a bounded `basis_id`; a `target` from
`declared_review_targets`; a `state` of `sufficient`, `missing`, `unavailable`,
or `target_method_mismatch`; a required rationale; and one or more source
references. `target_method_mismatch` additionally requires a closed
`applicability_mismatch` object with exactly `kind:
"target_method_mismatch"`, `target`, `method_id`, and `method_version`. Its
target and method fields must equal the basis-item target and artifact method
values. This is the sole structural representation of the accepted target/method
mismatch; free-form rationale cannot establish it.

A `scoreable` decision requires every basis item to be `sufficient`;
`unscoreable` requires at least one `missing` or `unavailable` item; and
`not_applicable` requires at least one `target_method_mismatch` item and no
other basis state. `not_assessed` requires an empty basis list. The template
uses `not_assessed` / `not_started`, empty findings, `not_assessed`
publication/comparison state, `reviewer: null`, and `reviewed_at_utc: null`. A
non-template document requires reviewer identity and review time. `reviewed`
requires at least one compatible, fully populated finding for every declared
review target; otherwise a started review is `in_review` or
`incomplete_review`.

Each finding is a closed object with: a unique `finding_id`; `finding_kind`;
`target`; `judgment_outcome`; `rationale`; non-empty `source_references`;
`reviewer`; `reviewed_at_utc`; `evidence_completeness`; `attribution`;
`limitations`; and optional bounded reviewer tags. `finding_kind` is exactly
`judgment` or `annotation`. A judgment has one of `favorable`, `mixed`,
`unfavorable`, or `not_assessable` for `judgment_outcome` and one of the first
six accepted evidence targets. An annotation has `judgment_outcome: null` and
only `attribution_boundary` or `evidence_limitation` target. A `not_assessable`
judgment and every `evidence_limitation` annotation must cite the insufficient
or unavailable evidence and state the limitation.

A finding rationale is required, bounded reviewer explanation. It explains
cited evidence; it MUST NOT introduce an uncited source fact. `limitations` is
a bounded list of reviewer limitations, not a source-evidence replacement.
Each finding's `attribution` has a non-empty unique `values` list from the
accepted attribution vocabulary, one `state` of `observed`,
`reviewer_inference`, `unavailable`, or `unknown`, and a required rationale for
`reviewer_inference`. `observed` attribution requires a source reference.

There are no numeric dimensions, prompt averages, aggregate score, hybrid
score, leaderboard score, model-only score, source-outcome replacement, or
recovery Boolean in this artifact.

## Contained source references

A source reference is a bounded, inert selector into the same contained
`evidence.json`, never a filesystem path, URL, command, tool argument, or raw
trajectory copy. It contains exactly `reference_type` and `reference_id`, where
`reference_type` is one of `trajectory_event`, `tool_lifecycle`,
`model_observation`, `repository_observation`, `source_terminal`,
`source_reference`, or `source_member`. `reference_id` must be the corresponding
canonical identifier present in the loaded evidence document. A source terminal
uses the fixed identifier `source_terminal`.

Each finding and evidence-basis item permits at most 32 references, deduplicated
by type and ID. Validation resolves IDs only against the contained normalized
evidence and, for `source_reference` or `source_member`, its contained inventory
mapping. It does not inspect an external harness, repository, object store, or
live runtime. Source references provide audit location, not a license to copy
raw trajectory, output, commands, tool arguments, or repository contents into
the review artifact.

## Review validation boundary

The implementation adds a separate deterministic, offline, read-only review
check. It loads the result's existing canonical evidence and the candidate or
canonical review JSON, then validates only this interface contract:

- identity, version, closed shape, resource limits, and exact source-session
  binding;
- run-fingerprint representation when present;
- initial-only `not_assessed` comparison/publication states;
- closed targets, finding kinds, outcomes, attribution values/states, and states;
- finding-kind/target compatibility, judgment-outcome requirements, and explicit
  `not_applicable` target/method mismatch representation;
- legal scoreability/review-state pairs and required evidence basis;
- required rationales, reviewer/time requirements, and evidence-completeness
  consistency; and
- bounded source-reference existence and validity.

It MUST NOT replay commands, tools, tests, or verifiers; inspect a repository;
contact OMP, a provider, model, or network; rerun the source verifier; or turn
review judgment into source structural validation. `llmgauge validate-result`
remains the existing Agent Harness structural validator and does not discover or
validate this mutable derivative. The new workflow exposes review validation
instead, preserving the meaning of the existing structural-validation outcome.

## CLI workflow

The initial public surface is one Agent-Harness-specific command:

```text
llmgauge agent-session-review RESULT_DIR --init [--force]
llmgauge agent-session-review RESULT_DIR --review REVIEW_JSON --check
llmgauge agent-session-review RESULT_DIR --review REVIEW_JSON --apply [--force]
llmgauge agent-session-review RESULT_DIR --report
```

The command rejects a non-imported result and any native or transcript result.
`--init`, `--check`, `--apply`, and `--report` are mutually exclusive modes;
`--check` and `--apply` require `--review`; `--force` is valid only with
`--init` or `--apply`. `--check` validates the bounded candidate without writing
result artifacts and exits nonzero on invalid input. `--apply` validates before
publication, atomically writes only the canonical path, and exits nonzero
without mutation on validation or write failure. Without `--force`, an existing
canonical review is a no-clobber error even if it appeared after the initial
destination check. `--report` reads canonical evidence and optional canonical
review only, regenerates the report explicitly, and may overwrite its prior
generated report. Applying review metadata does not generate a report.

Existing `llmgauge score` stays native-only. It neither creates nor reads this
review document. This command is the sole initial Agent Harness review/check/
apply/report interface; there is no new generic score, report, validation, or
comparison mode.

## Report artifact

The Agent Harness report has the fixed contained path
`agent-harness/review/agent-session-review.md`. It is generated from canonical
contained evidence and the optional canonical review document, never from the
template or native score/result fields. It records generator ID
`llmgauge.agent_session_review_report`, the installed LLMGauge version, and
generation time. Every generation replaces the prior file at that path; it does
not modify source evidence, review metadata, or the immutable source/run
fingerprint.

If the canonical review artifact exists, `--report` MUST first validate it
against this interface contract, including its exact contained source/session
binding and initial-only comparison/publication states. On any canonical-review
validation failure it exits nonzero, generates or replaces no report, does not
ignore the malformed review or fall back to no review, and mutates neither source
evidence nor review metadata. If no canonical review artifact exists, the report
is generated with `not_assessed` scoreability, `not_started` review state, no
reviewer judgment, and explicit absence of review metadata. With partial or
unscoreable evidence, it preserves source completeness and review state, reports
limitations and unavailable or unknown facts, and makes no quality, completion,
model-only, comparison, or publication claim. It implements the seven required
semantic-contract sections. The current native `report.md` remains native-only
and is neither read nor written for imported Agent Harness results.

## First implementation milestone and preserved boundaries

The first implementation milestone is limited to the review model/load/write/
check path; the command above; contained-reference and scoreability/state
validation; optional-review Agent Harness report generation; focused tests; and
workflow documentation. `agent-session-evidence-observation-v0` remains
deferred: no repeatable observation machinery is necessary to create, validate,
or render the initial manual review derivative.

Native single-turn scoring, native transcript scoring, generic comparison, public
export, export-index, publication, sanitization, importer behavior, source
structural validation, source fingerprints, session replay, live repository
inspection, and command/tool/test/OMP/model/provider execution remain fail
closed and separately gated.
