# Public Reporting Guidance

This document describes how to use LLMGauge artifacts in public WumboLabs model reports without overstating the evidence.

## Required report context

A public model report should state:

- model ID or profile
- model family, role, and quantization when available
- tested hardware
- runtime/backend
- suite ID and suite version
- context size
- max-token budget
- temperature and top-p
- validation status
- scoring status
- scored prompt count
- manual score average
- verdict counts
- common failure labels
- common good labels
- VRAM peak and headroom when available

## Required evidence

Public claims should be backed by validated artifacts:

- `llmgauge-result.json`
- `report.md`
- `scores.yaml` when manually scored
- cleaned outputs for readable review
- raw outputs for audit evidence
- export index when summarizing multiple artifacts or feeding a report/import workflow

## Claim boundaries

Manual scores are review metadata. They are not automatic judgments and are not universal model rankings.

A public report may say that a model performed well or poorly on a specific suite under a specific hardware/runtime configuration.

A public report should not claim:

- universal best-model status
- broad recommendations from one run
- daily-driver reliability from Tier 2 alone
- safety outside the tested prompts
- performance on untested hardware or runtime settings

## Useful public-report structure

A concise public report should include:

1. Test setup
2. Suite and evidence tier
3. Runtime and hardware
4. Score summary
5. Verdict counts
6. Strengths
7. Failure modes
8. Representative examples from cleaned output
9. Operational performance
10. Claim boundary

## Interpretation guidance

Score averages are useful summaries, but the most important public-report signals are:

- severe failures
- recurring failure labels
- lowest-scored prompts
- whether the model preserved constraints
- whether unsafe advice appeared
- whether outputs were complete enough to score
- whether speed and VRAM headroom fit the intended local workflow

A model with a slightly lower average score may be preferable if its failures are safer, more predictable, or easier to work around.
