# Scored Comparison Reports

LLMGauge comparison reports are designed to compare completed local evaluation runs without declaring a universal winner.

They are most useful after runs have been manually scored with:

    llmgauge score RESULT_DIR --scores RESULT_DIR/scores.yaml

or, during development from the repository checkout:

    uv run llmgauge score RESULT_DIR --scores RESULT_DIR/scores.yaml

## Before you compare

Prefer this order for public-proof evidence:

1. Validate each run with `validate-result`.
2. Inspect raw/cleaned outputs.
3. Apply reviewed scores with `score --check` first, then `score --scores`.
4. Re-run `validate-result` after scoring.
5. Generate the comparison report.
6. Read **Publish Readiness Notes** and **Publication evidence summary**.
7. Use `export-index` when an importer or summary workflow needs machine-readable metadata.

Per-run `report.md` files remain authoritative for single-run review. Comparison
reports summarize multiple runs. Export index mirrors scoring evidence fields for
importers but does not replace either report type.

## Generate a comparison report

Compare two or more result directories:

    uv run llmgauge compare \
      results/run-a \
      results/run-b \
      --out results/compare.md

For installed CLI usage:

    llmgauge compare \
      results/run-a \
      results/run-b \
      --out results/compare.md

## Comparison Scope

Comparison reports open with **Comparison Scope**, including a like-for-like
quality check, model/suite/prompt overlap, and explicit use/do-not-use guidance.
Read this section before interpreting score tables or making public claims.

## Publish Readiness Notes

Comparison reports include **Publish Readiness Notes** after the scope and
interpretation notes. Read this section before publishing or importing comparison evidence.

It summarizes deterministic signals such as:

- scored vs unscored runs
- partially scored or review-metadata-only runs
- `needs_review` verdict counts
- unreviewed automatic-rule drafts
- missing `score_rationale` entries
- mixed suite IDs or suite versions
- mixed runtime settings
- prompt-set overlap
- artifact gaps

The report also includes a **Publication evidence summary** that lists safer
bounded claims and explicitly unsupported ranking-style claims.

Do not treat a higher manual score average as a winner declaration. Use verdict
counts, failure labels, lowest-scored prompts, and publish-readiness warnings
together.

## What the report includes

A scored comparison report includes interpretation notes, publish-readiness
signals, quality signals, performance signals, and detailed prompt-level tables.

A scored comparison report includes:

- run metadata
- suite ID
- model ID
- run status
- completed and failed prompt counts
- scored prompt count
- manual score total and maximum
- manual score average
- runtime settings
- prompt score averages
- prompt verdicts
- overall trust scores
- prompt-level failure labels
- generation speed
- prompt-eval speed
- run-level failure-label counts
- run-level good-label counts

## Score totals and averages

LLMGauge reports both total score and average score.

Example:

    308.0/400.0
    3.85/5

The total shows how much scoring coverage exists. The average makes runs easier to compare at a glance.

When comparing runs from different suites, the average is useful, but it should not be treated as a universal ranking. Different suites test different behaviors.

## Prompt verdicts

Prompt verdict rows summarize the practical score outcome for each prompt.

Example:

    verdict=pass; trust=4; failures=None

or:

    verdict=fail; trust=0; failures=severe_hallucination

These fields come from the applied manual score data.

## Missing prompts

When comparing runs from different suites, some prompts will show as `missing`.

That is expected. A `core-v1` run and an `agent-backend-v1` run do not contain the same prompt IDs.

Cross-suite comparisons are useful for understanding broad behavior, but same-suite comparisons are better for direct model-to-model evaluation.

## Speed metrics

Comparison reports include:

- generation tokens per second
- prompt-eval tokens per second

These are operational metrics. They are not quality scores.

A faster model is not necessarily a better model. A slower model is not necessarily worse. Speed should be interpreted alongside score, failure labels, context size, quantization, and hardware limits.

## VRAM metrics

When VRAM sampling is available in the source runs, comparison reports include peak VRAM usage and minimum VRAM headroom. Older runs or runs without VRAM sampling may show missing VRAM values.


## Score file contract

Manual score templates are created with:

    uv run llmgauge score RESULT_DIR --init

Score files can be validated before applying them:

    uv run llmgauge score RESULT_DIR --scores RESULT_DIR/scores.yaml --check

Check mode validates the score file and exits without rewriting `llmgauge-result.json`,
`report.md`, or `scores.yaml`.

The generated `scores.yaml` uses schema version `llmgauge.scores.v0` and the
default rubric metadata:

    rubric_id: default-manual-v0
    rubric_version: 0.1.0

Each prompt score entry includes numeric dimensions on a 0-5 scale, label lists,
reviewer notes, a concise `score_rationale`, and a verdict.

Allowed verdict values are:

    pass
    mixed
    fail
    needs_review

The empty string is allowed before a verdict is assigned.

## Score rationale

Use `score_rationale` for the short reason behind the assigned score. Keep longer
context in `reviewer_notes`.

A useful rationale explains the scoring decision, not the whole model answer. For
example:

    Safe verification-first answer, but missing rollback detail.

Scores remain manual/local-context judgments. They should be interpreted alongside
raw output, cleaned output, runtime settings, VRAM behavior, and the actual task
stakes.

For scoring dimensions, safety guidance, agent-backend review notes, and label vocabulary, see `docs/SCORING_RUBRICS.md`.


## Interpretation guidance

Comparison reports are decision aids.

Prefer same-suite comparisons. Treat manual scores, verdicts, failure labels,
speed, VRAM, and raw/cleaned artifacts as separate signals.

Do not select a model only because it has the highest average score. A model with
slightly lower average score may be the better operational choice if it is safer,
more honest about uncertainty, or has more predictable failure modes.

## Artifact integration

- Per-run `report.md` files are authoritative for single-run review and **Publish Readiness Notes**.
- `compare.md` is the multi-run evidence summary; read **Publication evidence summary** before quality claims.
- Export index JSON mirrors scoring evidence fields (`scoring_status`, verdict counts, publish-readiness signals) for importers.
- Regenerate comparison reports and export index after underlying runs are re-scored or re-validated.

See `docs/ARTIFACT_SCHEMAS.md` for schema detail and `docs/PUBLIC_REPORTING.md` for the full workflow checklist.
