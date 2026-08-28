# Native Single-Transcript Public Derivative Contract

Status: **accepted** — human-accepted for the first implementation slice
(`feat/native-transcript-public-derivative-v1`). Accepted V1 decisions: one
native transcript-bearing run may be published as a **content-default-deny
allowlist projection** into a new `llmgauge.public_transcript.v0` derivative
via the dedicated command `llmgauge export-public-transcript RUN --out DIR`;
no transcript content, raw evidence, private identifiers, or full hashes may
ever appear in it; the existing single-run `llmgauge export-public` path
remains fail-closed for transcript-bearing results and is not broadened; and
every generated artifact carries the human-review-before-publication boundary.

This document is the separately admitted single-run export slice referenced by
the [Transcript Comparison Public Export Contract](TRANSCRIPT_COMPARISON_PUBLIC_EXPORT_CONTRACT.md)
(non-goals section) and supplements the
[Multi-turn Transcript Schema and Native Evaluation Contract](MULTI_TURN_TRANSCRIPT_SCHEMA_CONTRACT.md).
It changes no existing schema.

## Problem

The comparison derivative publishes structural evidence for exactly two runs.
Operators frequently need to publish the outcome of a **single** native
multi-turn conversation — one model, one task — without running a comparison
and without touching the private `results/` tree. The only existing single-run
command, `llmgauge export-public`, is built around the single-turn artifact
policy (raw outputs, cleaned outputs, logs, prompts) and correctly refuses
transcript-bearing runs: flattening transcript evidence into that policy would
reinterpret it and could leak conversation content. There is currently no
accepted way to publish one conversation's bounded structural facts without
publishing private content.

## Non-negotiable boundaries

1. **Content-default-deny.** The derivative is built exclusively from an
   explicit field allowlist. Any field not named in the projection tables
   below must not appear in the output, in any nesting order. Adding a
   transcript field never adds it to the public projection.
2. **No content, ever.** Rendered inputs, model outputs, stderr text, visible
   message content, feedback content, prompts, and any file body are private
   evidence and are excluded unconditionally. This contract introduces no
   content redaction path because no content is admitted.
3. **No private identifiers or hashes.** Conversation IDs, run IDs, event,
   attempt, turn, state, feedback, and branch IDs, result-directory paths,
   usernames, hostnames, home paths, executable paths, and full SHA-256
   values are excluded. Structural linkage is expressed only through
   canonical event **sequence numbers**, which are positional, not
   identity-bearing.
4. **Same private fact, same public interpretation.** The projection reuses
   the comparison derivative's infrastructure: the same sanitizer pipeline,
   the same per-run structural projection, the same closed vocabularies, the
   same closed-world validator, and the same staged-write and destination
   guards. A fact that is projected one way in a comparison must project
   identically in a single-run derivative.
5. **No scores or aggregates.** The derivative restates represented
   structural facts only. It declares no session score, no quality verdict,
   no aggregate, and no recommendation. Review hooks are projected exactly
   as recorded and are review metadata, not validation.
6. **Human review required before publication.** Every generated artifact
   states this boundary. Sanitization is not answer-quality validation and is
   not proof that all private data is removed.
7. **Existing contracts unchanged.** `llmgauge.result.v0`,
   `llmgauge.transcript.v0`, single-run `export-public`,
   `export-public-comparison`, `compare`, scoring, validation, and
   fingerprints are byte-compatible and unchanged. `export-public` keeps
   rejecting transcript-bearing runs; this contract admits a **separate
   command**, not a behavior change to the old one.

## Command surface

    llmgauge export-public-transcript RUN --out DIR

- Exactly one transcript-bearing result directory is admitted in V1. The
  directory must contain a loadable `llmgauge.result.v0` result.
- `--out DIR` is the derivative directory. It must be new or empty, must not
  be the source directory, and must not be inside the source directory. The
  export is staged in a sibling temporary directory and renamed into place
  atomically; any failure removes the staging directory and leaves the source
  and the destination untouched.
- On success the output directory contains exactly two files:
  `transcript-summary.json` and `report.md`. Nothing else is copied,
  referenced, or generated.
- The source is opened read-only and is never modified.

## Input eligibility (fail-closed admission)

The command admits a run only when every check below passes; each failure is
a nonzero, message-bearing exit with no output written:

1. The directory contains a loadable `llmgauge.result.v0` result that passes
   `validate_result_dir` (the same structural gate as single-run export).
2. The result is native — not Agent Harness or external-benchmark imported
   evidence (existing `require_native_result` gate).
3. The result is transcript-bearing (`transcript` reference present). A
   single-turn result is rejected with an explicit boundary message pointing
   at `export-public`.
4. The referenced transcript loads, validates against
   `llmgauge.transcript.v0`, and passes `validate_transcript_structure` and
   `validate_transcript_artifacts` against its source directory. A transcript
   whose contained evidence is missing, mutated, escaping, or duplicated
   fails closed.

Admission runs before staging; a failed admission never creates the output
directory.

## Projection: `llmgauge.public_transcript.v0`

`transcript-summary.json` is a closed JSON object.

### Top-level (closed)

| Field | Content |
|---|---|
| `schema_version` | literal `llmgauge.public_transcript.v0` |
| `generated_by` | literal `llmgauge` |
| `created_at_utc` | export timestamp (ISO-8601 UTC, validated shape-only) |
| `source_class` | literal `native_multi_turn_response` (the transcript's closed evaluation class) |
| `transcript_schema` | literal `llmgauge.transcript.v0` |
| `protocol` | `protocol_id` and `protocol_version` (closed LLMGauge literals) |
| `producer` | `producer_id` (literal `llmgauge`) and `producer_version` (the released LLMGauge version that produced the transcript; validated against a strict numeric `X.Y.Z` shape) |
| `limits` | `effective_max_model_turns`, `max_attempts_per_turn`, `max_feedback_items` (integers; the same closed identity numbers the comparison basis discloses) |
| `run` | the single per-run structural projection (see below) |
| `redaction` | disclosure summary (see Redaction and disclosure) |
| `claim_boundary` | fixed boundary text (see Claim boundaries) |
| `human_review_required_before_publication` | literal `true` |

Protocol ID/version are fixed LLMGauge protocol literals, not operator data.
`producer_version` is the public LLMGauge release version recorded in the
transcript, not a private build path; it is admitted here (and only here)
because it is required to interpret which transcript-producer semantics
generated the structural facts. This is the one deliberate difference from
the comparison derivative, and it is validated by strict shape, not by
allowlist membership.

Suite ID/version and task ID/version values are **not** projected: they are
operator-owned, potentially private, and task identity is not required to
interpret the structural facts.

### `run` (single-run projection)

Identical in shape and interpretation to one `runs[]` entry of
`llmgauge.public_transcript_comparison.v0`, with the positional slot label
`run` instead of `run-a`/`run-b`:

| Field | Content |
|---|---|
| `slot` | literal `run` |
| `model_label` | sanitized model label (see Model labels) |
| `completion` | `completion_state`, `completion_actor`, `terminal_reason` (closed vocabularies) |
| `turns` | `logical_model_turns`, `model_attempts`, `retries`, `recoveries` (integers) |
| `attempt_states` | per model-attempt event, ordered by sequence: `{sequence, relationship, attempt_state, exit_status}` — integers and closed literals only; no attempt/turn/event IDs |
| `states` | `state_transitions` (integer) and per state event `{sequence, previous_sequence, caused_by_sequence}` (sequence numbers or null) |
| `event_order` | per event: `{sequence, kind, role, execution_status}` plus `model_attempt` events' `relationship` — the role- and order-preserving skeleton; no IDs, no content |
| `capture_health` | `truncated_artifacts`, `partial_artifacts`, `failed_artifacts`, `redacted_artifacts` (integers) |
| `review_hooks` | the seven closed review hooks exactly as recorded |

Explicitly excluded from the run projection: `selected_branch_id`,
`final_response_event_id`, `conversation_id`, `suite_id`/`suite_version`,
`task_id`/`task_version`, `initial_state_id`/`initial_state_sha256`,
`attempt_outcomes` and `feedback_dispositions` strings (ID-bearing), all
`ArtifactReference` paths and SHA-256 values, `result_provenance`, the run
fingerprint, runtime and generation settings, hardware metadata, VRAM
metrics, speed metrics, scores, and every raw/derived text body.

## Model labels

The public label is derived from the result's `model.model_id` through the
shared sanitization pipeline (`_sanitize_text` + full-hash segment removal),
then constrained to the transcript ID character class
(`^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$`). A label that is empty after
sanitization, or that still contains a disallowed character, is replaced by
the neutral fallback literal `Model`. Any substitution or redaction applied
to a label is recorded in the `redaction` disclosure. A model ID is display
metadata, not identity proof, and the export must not be used to attribute
results to a machine or account.

## Redaction and disclosure

`redaction` records:

- `policy`: literal `content-default-deny-allowlist-projection`;
- `categories`: the union of sanitizer categories touched while projecting
  (for example `absolute_path`, `local_username`, `full_local_sha256`),
  sorted;
- `model_label_substitutions`: record of whether the slot `run` fell back to
  `Model` or was redacted;
- `omitted_field_classes`: the closed list of excluded classes (identical to
  the comparison list except that `producer_version_and_result_provenance`
  becomes `result_provenance_and_run_fingerprint`, reflecting the admitted
  `producer_version`);
- `raw_transcript_content_included`: literal `false`;
- `private_identifiers_included`: literal `false`.

The two boolean fields are self-describing assertions, not enforcement: the
closed-world validator and the allowlist projection are the enforcement.
Sanitization is conservative and does not guarantee complete secret removal;
that boundary is stated in both artifacts.

## `report.md`

A human-readable rendering of exactly the projected JSON — no additional
facts. It restates source class, protocol and producer identity, limits,
completion, turn/attempt/feedback/state structure, the sequence-numbered
event skeleton with roles preserved, capture health, and review hooks as
recorded. It carries the claim boundaries and the mandatory statement that
**human review is required before publication** and that the report proves
only represented structural facts about the tested configuration.

## Claim boundaries

Both artifacts state:

- the derivative supports claims about the tested configuration only; it
  implies no universal rank, no untested safety or performance, and no
  daily-driver reliability;
- completion is not correctness; supplied inert feedback is not executed
  work;
- structural facts are not answer-quality validation;
- no session aggregate, score, winner, or quality verdict exists;
- human review is required before publication; sanitization is not proof that
  private data is absent.

## Compatibility

- Purely additive: one new schema identity, one new command, no new module.
  No field is added to or removed from any existing schema; no existing
  command behavior changes.
- `llmgauge export-public RUN_DIR` keeps failing closed for
  transcript-bearing runs. This contract supersedes only the
  "no single-run transcript public export" non-goal of the comparison
  contract by admitting a separate command with its own schema; it does not
  amend any accepted comparison behavior.
- Historical results need no migration; the projection reads only fields
  already required by `llmgauge.transcript.v0`.
- The derivative is a record, not scratch state: it is never regenerated in
  place over a non-empty directory and never mutates its source.

## Security invariants and required validation

- **Closed-world output test:** the projected JSON must contain exactly the
  keys defined above, at every nesting level; a test walks the schema and
  rejects unknown keys. Injecting any unexpected key or disallowed string
  into the projection must make validation fail.
- **Adversarial privacy canaries:** fixtures seed secret-like and private
  values (credential-bearing URLs, absolute/home paths, usernames, 64-hex
  hashes, secret-like tokens) into model IDs, conversation IDs, feedback
  content, and captured stdout/stderr; a recursive scan of every byte of the
  output directory must find none of the canary literals, and any canary that
  reaches a projected string must appear only in redacted form and be counted
  in `redaction.categories`.
- **Fail-closed regressions:** missing directory, non-transcript-bearing
  result, malformed or hash-mismatched transcript, imported-evidence result,
  unsafe or non-empty destination, and destination-inside-source all exit
  nonzero with no output written and no staging residue.
- **Reuse invariance:** the same run projected through this derivative and as
  one side of a comparison derivative must produce identical structural
  facts (modulo the positional slot label), proving one private fact → one
  public interpretation.
- **No-score invariant:** no score, aggregate, or verdict key exists anywhere
  in the derivative.

## Implementation home

- `src/llmgauge/core/transcript_public_export.py` — admission, projection,
  closed-world validation, report rendering, staged write. The single-run
  path reuses the comparison module's sanitizer imports, per-run projection,
  vocabularies, validator, and destination/staging helpers directly.
- `src/llmgauge/commands/export_public.py` — the `export-public-transcript`
  command wrapper.
- Tests: `tests/test_transcript_public_export.py`.

## Non-goals

No content publication in any mode (including "redacted content"); no change
to `export-public`, `export-public-comparison`, `compare`, `score`,
`validate-result`, or `export-index`; no scores, aggregates, rankings, or
leaderboard entries; no machine-readable index entry for the derivative; no
multi-run (>2) public comparison; no canonical-schema, fingerprint, or
publication/submission behavior change.
