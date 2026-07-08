# LLMGauge Roadmap

LLMGauge is a conservative local-first CLI for practical LLM evaluation on real consumer hardware.

The project produces defensible, reproducible public evidence about usefulness, honesty, correctness, safety, speed, VRAM headroom, and workflow fit under disclosed hardware and runtime conditions.

LLMGauge is part of the WumboLabs workflow: **Real Hardware. Real Testing. No Hype.**

## Current release line

- Current stable tag: `v0.61`
- Current development line: `v0.62`
- Current development focus: public report artifact polish

## What LLMGauge is

LLMGauge answers practical local-model questions such as:

- Does this model produce useful answers for real workflows?
- Does it stay honest when it lacks information or tools?
- Does it fit comfortably on consumer hardware?
- How fast is it under the tested runtime settings?
- What context sizes are viable before quality, latency, or VRAM headroom degrade?
- What artifacts support the result?
- What changed between two model runs, suites, scoring passes, or releases?

## What LLMGauge is not

- a cloud evaluation service
- a model downloader
- a hosted leaderboard
- an automatic judge that hides review
- a hardware tuning tool
- a general autonomous agent framework
- a benchmark submission or telemetry system

## Current capabilities

After `v0.61`, LLMGauge provides:

- local-first CLI runs with preserved raw/cleaned outputs and logs
- artifact validation (`validate-result`, ladder/batch validators)
- manual scoring templates and `score --check` / `score --scores` workflow
- auto-draft scoring as review-required triage only
- single-run `report.md` generation with **Publish Readiness Notes**
- comparison reports with publish-readiness and **Publication evidence summary**
- `export-index` machine-readable metadata for importers
- model profile onboarding and management commands
- dry-run and preflight commands (`smoke`, `doctor`)
- context ladder and fit ladder artifacts with preserved failures
- public-proof workflow guidance across docs
- Practical Eval v1 seed suite (`wumbolabs-practical-v1`)
- artifact schema documentation
- publish-readiness notes and explicit claim boundaries

## Recently completed releases

Condensed highlights from recent release lines:

| Release | Focus |
|---|---|
| v0.57 | Suite and scoring maturity — rubric guidance, scoreability docs |
| v0.58 | Practical suite polish — prompt audit and metadata |
| v0.59 | Scored comparison evidence — publish-readiness in reports/compare, export-index scoring fields |
| v0.60 | Public-proof workflow hardening — end-to-end checklist, CLI next-steps, validate-result artifact messaging |

Earlier foundations (v0.46–v0.56 and before) established artifact schemas, validation, scoring, comparison, fit ladder, model profiles, CLI modularization, and public documentation.

## Active development line

### v0.61 — Export/index/report integration polish

**Goal:** Make `report.md`, comparison reports, and export-index artifacts work together more coherently in the public-proof workflow.

**Scope:**

- align report/compare/export-index terminology across docs and generated output
- clarify artifact roles and regeneration points
- improve importer/public-proof metadata guidance
- keep schemas backward-compatible

**Avoid:** breaking artifact compatibility, major schema migration, external integration coupling.

## Near-term roadmap

### v0.62 — Public report artifact polish

**Goal:** Make generated artifacts easier to cite in human-facing reports.

**Possible work:**

- tighten report wording and auditability
- improve comparison excerpts or summary sections
- keep claims bounded and hardware-specific

**Avoid:** model-specific winner claims, leaderboard framing.

### v0.63 — Result artifact usability / audit polish

**Goal:** Improve reviewer ergonomics without changing the file-based design.

**Possible work:**

- improve artifact navigation guidance
- improve raw/cleaned output references in docs and reports
- keep local-first, file-based artifacts as the source of truth

**Avoid:** cloud dashboards, hidden artifact mutation, network dependencies.

## Later roadmap / parking lot

These are optional or exploratory. They are not core commitments:

- optional website publication helpers
- optional LocalMaxxing export/submission integration (not core; no default network activity)
- optional Monolith import/read-only integration (not core)
- richer comparison summaries when deterministic and schema-safe
- package/release automation improvements
- CI/doc automation
- model profile UX polish
- context-size and fit-ladder reporting polish
- optional static report browsing helpers

**Non-goals for later work:**

- automatic LLM-as-judge scoring
- leaderboard or universal ranking
- network submission by default
- production-readiness or daily-driver recommendations from scores alone

## Release discipline / public-proof rules

1. Feature branches from `main` with focused commits.
2. Local full gate before handoff: `uv run pytest`, `uv run ruff check .`, `git diff --check`.
3. Release metadata (`pyproject.toml`, `__init__.py`, `CHANGELOG.md`, lockfile) in a separate release-prep step — not mixed into feature work.
4. Annotated tags only after release metadata merges to `main`.
5. Preserve raw outputs, failed attempts, and scoring provenance in all workflows.
6. Manual scoring remains the trusted path; auto-drafts stay review-required until applied and reviewed.
7. Public claims require disclosed hardware, runtime, suite, scoring status, and artifact evidence.
8. Comparison reports and export index are evidence metadata — not model recommendations.

## Working rule

For every proposed task, ask:

> Does this make LLMGauge better at producing defensible public evidence about local models on real consumer hardware?

If yes, it belongs on the roadmap. If it is only private progress, model chasing, UI polish, or architecture expansion without evidence value, park it.