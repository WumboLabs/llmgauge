# Public Reporting Guidance

This document describes how to use LLMGauge artifacts in public WumboLabs model reports without overstating the evidence.

## Public-proof workflow checklist

For public-facing evidence, prefer this order:

1. Run the suite.
2. `validate-result` on the result directory.
3. Inspect `raw/` and `cleaned/` outputs.
4. `score --init` to create `scores.yaml`.
5. Fill scores manually with rationale, labels, and verdicts.
6. `score --check` before applying scores.
7. `score --scores` to apply reviewed scores.
8. `validate-result` again after scoring.
9. Read `report.md`: **Report Scope**, **Evidence Summary**, **Audit Checklist**, **Prompt Artifact Audit**, and **Publish Readiness Notes**.
10. `compare` only like-for-like scored runs when making quality claims.
11. Read comparison **Publish Readiness Notes** and **Publication evidence summary**.
12. `export-index` when an importer or summary workflow needs metadata.
13. Write bounded claims with hardware, runtime, suite, and scoring disclosure.
14. Retain raw/cleaned artifacts for audit.

Validation confirms artifact shape and references. It does not prove model
quality, safety, or publication readiness. Auto-drafts are triage only until a
reviewer applies reviewed scores.

## Artifact roles in the workflow

| Step | Artifact | Use for |
|---|---|---|
| Single-run review | `report.md` | **Audit Checklist**, **Prompt Artifact Audit**, score/rationale review, **Publish Readiness Notes** |
| Multi-run review | `compare.md` | Cross-run comparison, **Publish Readiness Notes**, **Publication evidence summary** |
| Importer metadata | Export index JSON | Discovery, `scoring_status`, scoring evidence fields, validation status |

Regenerate `report.md` after applying scores. Regenerate `compare.md` when
underlying runs change. Regenerate export index after scoring, validation, or
report changes.

See `docs/ARTIFACT_SCHEMAS.md` for field-level schema detail.

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
- scoring provenance and review status
- scored prompt count
- manual score average
- verdict counts
- common failure labels
- common good labels
- VRAM peak and headroom when available

## Required evidence

Public claims should be backed by validated artifacts:

- `llmgauge-result.json`
- `runtime-command.json` when present (resolved llama.cpp command metadata)
- `report.md`
- `scores.yaml` when manually scored
- cleaned outputs for readable review
- raw outputs for audit evidence
- export index when summarizing multiple artifacts or feeding a report/import workflow

## Claim boundaries

Manual scores are review metadata. They are not automatic judgments and are not universal model rankings.

Generated single-run reports surface scoring provenance, including scoring mode and
reviewed/unreviewed counts. If assisted draft scores were applied before review,
treat the report warning as a claim boundary and finish manual review before
using those scores in public conclusions.

Single-run `report.md` files and comparison reports both include **Publish
Readiness Notes** with deterministic signals such as:

- scoring status (`scored`, `partially_scored`, `review_metadata_only`, `unscored`)
- scored prompt coverage
- `needs_review` verdict counts
- unreviewed assisted drafts
- missing `score_rationale` entries
- mixed suite IDs or suite versions
- mixed runtime settings
- prompt-set overlap
- artifact gaps

Comparison reports also add a **Publication evidence summary** that separates
safer bounded claims from unsupported ranking-style claims. Use these sections
to decide whether a comparison is complete enough to publish.

When comparing multiple runs:

- compare only like-for-like runs when making quality claims
- disclose hardware, runtime, suite, prompt subset, context, max tokens, temperature, and scoring status
- do not publish unreviewed automatic-rule scores as final human judgment
- treat comparison output as evidence, not as a universal leaderboard
- keep raw and cleaned outputs available for audit when possible

A public report may say that a model performed well or poorly on a specific suite under a specific hardware/runtime configuration.

A public report should not claim:

- universal best-model status
- broad recommendations from one run
- daily-driver reliability from Tier 2 alone
- safety outside the tested prompts
- performance on untested hardware or runtime settings

## Generated report sections

Single-run `report.md` files include:

- **Report Scope** — what the report is and is not for
- **Evidence Summary** — cite-friendly run, model, suite, runtime, and scoring snapshot
- **Publish Readiness Notes** — deterministic publish-readiness signals
- **Test Configuration** — detailed run, model, and runtime metadata
- **Audit Checklist** — validation, inspection, and retention steps before publication
- **Prompt Artifact Audit** — per-prompt paths, score rationales, and source vs derived artifact roles

Comparison `compare.md` files add:

- **Comparison Scope** — like-for-like check and supported/unsupported comparison uses
- **Publication evidence summary** — safer vs unsupported public claims

## Useful public-report structure

When writing a human-facing WumboLabs report, cite material from the generated
sections above. A concise public writeup should include:

1. Test setup (from Evidence Summary / Test Configuration)
2. Suite and evidence tier
3. Runtime and hardware
4. Score summary (manual review metadata only)
5. Verdict counts
6. Strengths
7. Failure modes
8. Representative examples from cleaned output
9. Operational performance
10. Claim boundary (from Report Scope / Publish Readiness Notes)
11. Comparison scope and publish-readiness notes when multiple runs are summarized

## Comparison reports

Generate a comparison report only after the underlying runs are validated and,
when making quality claims, scored with reviewed metadata:

    uv run llmgauge compare results/run-a results/run-b --out results/compare.md

Read **Publish Readiness Notes** and **Publication evidence summary** before
publishing. Prefer same-suite, same-suite-version, same-prompt-subset
comparisons with matching runtime settings and reviewed scores. Mixed result sets
can still be useful, but they support narrower claims.

Treat any `needs_review` verdict, unreviewed automatic-rule draft, or missing
`score_rationale` as a publication blocker for ranking-style claims until review
is complete.

Do not select a public winner from score averages alone. A slightly lower average
may be preferable when failures are safer or more predictable.

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
