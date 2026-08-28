# Transcript Comparison Public Export Contract

Status: **accepted** — human-accepted on current main for the first
implementation slice (`feat/transcript-public-comparison-export-v1`). Accepted
V1 decisions: the public transcript surface is a **comparison-only,
content-default-deny allowlist projection** into a new
`llmgauge.public_transcript_comparison.v0` derivative; no transcript content,
raw evidence, private identifiers, or full hashes may ever appear in it; the
single-run `llmgauge export-public` path remains fail-closed for
transcript-bearing results; and every generated artifact carries the
human-review-before-publication boundary. This document is the separately
admitted export slice referenced by the
[Transcript Comparison and Review Contract](TRANSCRIPT_COMPARISON_REVIEW_CONTRACT.md)
and supplements the
[Multi-turn Transcript Schema and Native Evaluation Contract](MULTI_TURN_TRANSCRIPT_SCHEMA_CONTRACT.md).
It changes no existing schema.

## Problem

The bounded structural transcript comparison exists only as private review
evidence written under the operator's `results/` tree. Publishing any of it
requires a sanitized derivative, but the existing single-run
`llmgauge export-public` pipeline is built around the single-turn artifact
policy (raw outputs, cleaned outputs, logs, prompts) and correctly refuses
transcript-bearing runs: flattening transcript evidence into that policy would
reinterpret it and could leak conversation content. There is currently no
accepted way to publish comparison evidence without publishing private
conversation content.

## Non-negotiable boundaries

1. **Content-default-deny.** The public derivative is built exclusively from
   an explicit field allowlist. Any field not named in the projection tables
   below must not appear in the output, in any nesting order. Adding a
   transcript field never adds it to the public projection.
2. **No content, ever.** Rendered inputs, model outputs, stderr text, visible
   message content, feedback content, prompts, and any file body are private
   evidence and are excluded unconditionally. This slice introduces no content
   redaction path because no content is admitted.
3. **No private identifiers or hashes.** Conversation IDs, run IDs, event,
   attempt, turn, state, feedback, and branch IDs, result-directory paths,
   usernames, hostnames, home paths, executable paths, and full SHA-256 values
   are excluded. Structural linkage is expressed only through canonical event
   **sequence numbers**, which are positional, not identity-bearing.
4. **No aggregate, ranking, or winner.** The derivative restates the bounded
   structural classification only. It declares no session score, no quality
   verdict, and no recommendation.
5. **Human review required before publication.** Every generated artifact
   states this boundary. Sanitization is not answer-quality validation and is
   not proof that all private data is removed.
6. **Existing contracts unchanged.** `llmgauge.result.v0`,
   `llmgauge.transcript.v0`, single-run `export-public`, `compare`, scoring,
   validation, and fingerprints are byte-compatible and unchanged. The
   single-run export keeps rejecting transcript-bearing runs.

## Command surface

    llmgauge export-public-comparison RUN_A RUN_B --out DIR

- Exactly two transcript-bearing result directories are admitted in V1; fewer
  than two fails closed. More than two fails closed with an explicit V1
  boundary message (the private `compare` surface remains the multi-run
  review tool).
- `--out DIR` is the derivative directory. It must be new or empty, must not
  be inside either source directory, and must differ from both. The export is
  staged in a sibling temporary directory and renamed into place atomically;
  any failure removes the staging directory and leaves both sources and the
  destination untouched.
- On success the output directory contains exactly two files:
  `transcript-comparison.json` and `report.md`. Nothing else is copied,
  referenced, or generated.
- Sources are opened read-only and are never modified.

## Input eligibility (fail-closed admission)

The command admits a pair only when every check below passes; each failure is
a nonzero, message-bearing exit with no output written:

1. Each directory contains a loadable `llmgauge.result.v0` result that passes
  `validate_result_dir` (the same structural gate as single-run export).
2. Each result is transcript-bearing (`transcript` reference present) and not
  Agent Harness or external-benchmark imported evidence (existing
  `require_native_result` gate).
3. Each referenced transcript loads, validates against
  `llmgauge.transcript.v0`, and passes `validate_transcript_structure` and
  `validate_transcript_artifacts` against its source directory. A transcript
  whose contained evidence is missing, mutated, escaping, or duplicated fails
  closed.
4. Mixed transcript/single-turn pairs fail closed with the same evaluation-class
  boundary used by `compare`.

Admission runs before staging; a failed admission never creates the output
directory.

## Projection: `llmgauge.public_transcript_comparison.v0`

`transcript-comparison.json` is a closed JSON object. Fields are grouped by
owner; per-run entries are keyed by a positional slot label (`run-a`, `run-b`)
— never by run, model, or conversation identity.

### Top-level (closed)

| Field | Content |
|---|---|
| `schema_version` | literal `llmgauge.public_transcript_comparison.v0` |
| `generated_by` | literal `llmgauge` |
| `created_at_utc` | export timestamp (ISO-8601 UTC, validated shape-only) |
| `source_artifact_types` | both `llmgauge.result.v0` (closed literals) |
| `transcript_schema_versions` | both `llmgauge.transcript.v0` (closed literals) |
| `eligibility` | see below |
| `classification` | see below |
| `runs` | two ordered per-run projections, slot-labeled |
| `redaction` | disclosure summary (see Redaction and disclosure) |
| `claim_boundary` | fixed boundary text (see Claim boundaries) |
| `human_review_required_before_publication` | literal `true` |

### `eligibility`

The closed identity comparison from the review contract, projected to
booleans and field names only — identity **values** are not disclosed:

- `eligible` (boolean), `classification` (one of `identical structure`,
  `structurally comparable`, `structurally incomparable`),
  `mismatched_identity_fields` (closed field-name list), and
  `comparison_basis` listing the exact identity fields required to match:
  protocol ID and version, task ID and version, initial-state ID and
  initial-state SHA-256, suite ID and version, and effective limits
  (`effective_max_model_turns`, `max_attempts_per_turn`,
  `max_feedback_items`).

Protocol ID/version and transcript/result schema versions are closed
LLMGauge literals and are included verbatim in the top-level fields above.
Suite ID/version and task ID/version values are **not** projected: they are
operator-owned, potentially private, and their equality is already disclosed
through the eligibility result.

### `classification`

- `classification` (three-way, same value as in `eligibility`),
- `differing_facts` (closed fact-name list),
- `completion_asymmetry` (boolean, never the raw per-run
  `completion_state/terminal_reason` strings, which could fingerprint a
  private run; the asymmetry statement lives in `report.md` prose).

### `runs[]` (per run, exactly two entries)

| Field | Content |
|---|---|
| `slot` | `run-a` or `run-b` |
| `model_label` | sanitized model label (see Model labels) |
| `completion` | `completion_state`, `completion_actor`, `terminal_reason` (closed vocabularies) |
| `turns` | `logical_model_turns`, `model_attempts`, `retries`, `recoveries` (integers) |
| `attempt_states` | per model-attempt event, ordered by sequence: `{sequence, relationship, attempt_state, exit_status}` — integers and closed literals only; no attempt/turn/event IDs |
| `states` | `state_transitions` (integer) and per state event `{sequence, previous_sequence, caused_by_sequence}` (sequence numbers or null) |
| `event_order` | per event: `{sequence, kind, role, execution_status}` plus `model_attempt` events' `relationship` — the role- and order-preserving skeleton; no IDs, no content |
| `capture_health` | `truncated_artifacts`, `partial_artifacts`, `failed_artifacts`, `redacted_artifacts` (integers) |
| `review_hooks` | the seven closed review hooks exactly as recorded |

Explicitly excluded from every run projection: `selected_branch_id`,
`final_response_event_id`, `conversation_id`, `suite_id`/`suite_version`,
`task_id`/`task_version`, `initial_state_id`/`initial_state_sha256`,
`attempt_outcomes` and `feedback_dispositions` strings (ID-bearing), all
`ArtifactReference` paths and SHA-256 values, `producer_version`,
`result_provenance`, runtime and generation settings, hardware metadata,
scores, and every raw/derived text body.

## Model labels

The public label is derived from the result's `model.model_id` through the
shared sanitization pipeline (`_sanitize_text` + full-hash segment removal),
then constrained to the transcript ID character class
(`^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$`). A label that is empty after
sanitization, or that still contains a disallowed character, is replaced by
the positional fallback `Model A` / `Model B`. Any substitution or redaction
applied to a label is recorded in the `redaction` disclosure. A model ID is
display metadata, not identity proof, and the export must not be used to
attribute results to a machine or account.

## Redaction and disclosure

`redaction` records:

- `policy`: literal `content-default-deny-allowlist-projection`;
- `categories`: the union of sanitizer categories touched while projecting
  (for example `absolute_path`, `local_username`, `full_local_sha256`),
  sorted;
- `model_label_substitutions`: per-slot record of which slots fell back to
  `Model A`/`Model B` or were redacted;
- `omitted_field_classes`: the closed list of excluded classes above, so the
  reader can see what is *not* disclosed.

Sanitization is conservative and does not guarantee complete secret removal;
that boundary is stated in both artifacts.

## `report.md`

A human-readable rendering of exactly the projected JSON — no additional
facts. It restates eligibility, classification, completion asymmetry (in
prose, without raw terminal strings beyond the closed vocabularies already
projected), side-by-side structural facts, the sequence-numbered event
skeleton with roles preserved, and review hooks as recorded. It carries the
claim boundaries and the mandatory statement that **human review is required
before publication** and that the report proves only represented structural
facts about the tested configuration.

## Claim boundaries

Both artifacts state:

- the derivative supports claims about the tested configuration only; it
  implies no universal rank, no untested safety or performance, and no
  daily-driver reliability;
- completion is not correctness; supplied inert feedback is not executed work;
- structural comparison is not answer-quality validation;
- no session aggregate, winner, or quality verdict exists;
- human review is required before publication; sanitization is not proof that
  private data is absent.

## Compatibility

- Purely additive: one new schema identity, one new command, one new core
  module. No field is added to or removed from any existing schema; no
  existing command behavior changes.
- `llmgauge export-public RUN_DIR` keeps failing closed for
  transcript-bearing runs; this contract does not admit single-run transcript
  public export in any form.
- Historical results need no migration; the projection reads only fields
  already required by `llmgauge.transcript.v0`.
- The derivative is a record, not scratch state: it is never regenerated in
  place over a non-empty directory and never mutates its sources.

## Security invariants and required validation

- **Closed-world output test:** the projected JSON must contain exactly the
  keys defined above, at every nesting level; a test walks the schema and
  rejects unknown keys.
- **Adversarial privacy canaries:** fixtures seed secret-like and private
  values (credential-bearing URLs, absolute/home paths, usernames, 64-hex
  hashes) into model IDs, conversation IDs, feedback content, and captured
  stdout/stderr; a recursive scan of every byte of the output directory must
  find none of the canary literals, and any canary that reaches a projected
  string must appear only in redacted form and be counted in
  `redaction.categories`.
- **Fail-closed regressions:** fewer than two directories, more than two,
  mixed transcript/single-turn, non-transcript-bearing, malformed or
  hash-mismatched transcripts, imported-evidence results, unsafe or non-empty
  destinations, and destination-inside-source all exit nonzero with no output
  written.
- **Eligibility regressions:** protocol, task, initial-state, suite, and
  limits mismatches project `eligible: false` with the correct closed
  field-name list and never fail the export itself (incomparability is
  disclosed, not hidden).

## Implementation home

- `src/llmgauge/core/transcript_public_export.py` — admission, projection,
  report rendering, staged write; reuses the private sanitizers of
  `public_export.py` by internal import (no new public sanitizer API) and the
  comparison primitives of `transcript_compare.py`.
- `src/llmgauge/commands/export_public.py` — the
  `export-public-comparison` command wrapper.
- Tests: `tests/test_transcript_public_export.py`.

## Non-goals

No single-run transcript public export; no content publication in any mode
(including "redacted content"); no multi-run (>2) public comparison; no
machine-readable index entry, leaderboard, or aggregate; no change to
`compare`, `score`, `validate-result`, `export-index`, or `export-public`; no
publication or submission behavior.
