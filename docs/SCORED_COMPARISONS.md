# Scored Comparison Reports

LLMGauge comparison reports are designed to compare completed local evaluation runs without declaring a universal winner.

They are most useful after runs have been manually scored with:

    llmgauge score RESULT_DIR --scores RESULT_DIR/scores.yaml

or, during development from the repository checkout:

    uv run llmgauge score RESULT_DIR --scores RESULT_DIR/scores.yaml

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

## What the report includes

A scored comparison report includes interpretation notes, quality signals, performance signals, and detailed prompt-level tables.

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
