# Transcript Comparison and Review Contract

Status: **accepted** — human-accepted on current main for the first
implementation slice (`feat/transcript-comparison-v1`). Accepted V1 decisions:
no automatic transcript/session aggregate score; the first comparison surface
is human-readable CLI/report output via `llmgauge compare`; transcript-bearing
public export remains fail-closed. It supplements the
[Multi-turn Transcript Schema and Native Evaluation Contract](MULTI_TURN_TRANSCRIPT_SCHEMA_CONTRACT.md)
and the [Multi-turn Transcript Architecture](MULTI_TURN_TRANSCRIPT_ARCHITECTURE.md).
Single-turn scoring, comparison of mixed transcript/single-turn sets, and
public export continue to fail closed when a transcript reference is present;
only the bounded structural comparison defined here is admitted.

## Problem

Native multi-turn transcripts exist and validate, but there is no accepted way
to compare two transcript-bearing results or to present transcript review
state. The gap is deliberate: turn-level scalar scores do not automatically
compose into a meaningful session score, and no rubric currently defines one
mathematically.

## Non-negotiable boundaries

1. No automatic session aggregate. A session-level numeric score exists only
   after a separately accepted rubric defines its exact arithmetic over
   named reviewed facts. Review metadata never becomes truth by summation.
2. Comparison is disclosure plus eligibility classification. It never ranks,
   declares winners, or implies quality equivalence across differing
   conversations or protocols.
3. Requested settings remain distinct from observed evidence; completion is
   not correctness; supplied inert feedback is not executed work.
4. Existing single-turn behavior, schemas, and fingerprints remain unchanged
   when transcript references are absent.

## Transcript identity and comparison eligibility

Two transcript-bearing results are **eligible for bounded structural
comparison** only when all of the following match exactly:

- protocol ID and version (`llmgauge.sequential_supplied_feedback` 0.1.0 or a
  shared later version);
- task ID and task version;
- `initial_state_id` and the SHA-256 of the initial task material;
- suite ID and suite version;
- effective declared limits (`max_model_turns`, `max_attempts_per_turn`,
  `max_feedback_items`) after any operator reduction.

Differing model IDs are expected in model comparisons and do not block
eligibility; they are disclosed. Differing runtime labels, context sizes, or
generation settings follow existing runtime-settings mixing rules.

Any identity mismatch makes the runs **not comparable**; a report may still
list both transcripts side by side as independent evidence, labeled as such.

## Structural comparison facts

When eligible, comparison discloses, per run, only represented facts:

- completion state, actor, terminal reason, selected branch, final response
  selection;
- logical model turn count, attempt counts, retry counts, recovery turns;
- attempt states and exact exit statuses (as preserved, never normalized);
- feedback plan: declared count, supplied, consumed, supplied-unconsumed,
  unreached items, with disposition reasons;
- observable-state transition count;
- capture health: truncated, partial, failed, or redacted artifact counts;
- scoreability and closed review-state hooks exactly as recorded.

It classifies the pair: identical structure, structurally comparable, or
structurally incomparable (for example, different terminal reasons, one
partial versus one completed). Partial versus completed is never scored
side-by-side as though completion occurred on both; the failure asymmetry is
stated.

## Role and ordering preservation

Comparison output must preserve canonical event order semantics: task first,
terminal last; attempts grouped under their logical `turn_id`; retries shown
as retries of a specific preceding attempt; recovery turns linked to their
consumed feedback. Roles (`user`, `assistant`, `evaluator`, `protocol`) are
never flattened into an undifferentiated message list. Missing turns are
represented by the preserved terminal reason and unreached plan items — never
synthesized.

## Manual review presentation

Review presentation reads the transcript's existing hooks only:
`unreviewed`, `incomplete`, `unscoreable`, and the six closed review states.
A reviewer may record per-turn verdicts under a separately admitted rubric;
until then, presentation counts and locates review state without inventing
verdicts. Reviewed, unreviewed, partial, and missing states stay visibly
distinct in any output.

## Public export boundary

Transcript content (rendered inputs, raw outputs, visible states) is private
evidence. Any sanitized derivative requires the standard public-export
redaction pipeline, a redaction summary, and human review before publication.
Until a transcript-specific export slice is admitted, transcript-bearing
results continue to fail closed at public export rather than exporting a
flattened derivative.

## Compatibility

No field is added to `llmgauge.result.v0` by this contract. When an
implementation is later admitted, comparison/report additions must leave
single-turn results, transcript fingerprints, validation, and exports
byte-compatible, and historical results need no migration.

## Implementation prerequisites

Implementation requires: (a) human acceptance of this contract — accepted;
(b) a decided home for transcript comparison output — decided: the existing
`llmgauge compare` command routes an all-transcript result set to this bounded
structural comparison; and (c) if any aggregate is ever desired, a separate
rubric contract defining its exact arithmetic — none exists, so V1 admits no
aggregate. The first implementation slice is `feat/transcript-comparison-v1`.
