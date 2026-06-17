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

## Current limitation

LLMGauge does not yet capture VRAM usage.

Until VRAM capture is added, comparison reports may mention VRAM as an operational metric category, but they do not yet include peak VRAM or headroom fields.
