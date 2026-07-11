# LLMGauge Roadmap

LLMGauge is a conservative local-first CLI for practical LLM evaluation on real consumer hardware.

The project produces defensible, reproducible public evidence about usefulness, honesty, correctness, safety, speed, VRAM headroom, and workflow fit under disclosed hardware and runtime conditions.

LLMGauge is part of the WumboLabs workflow: **Real Hardware. Real Testing. No Hype.**

## Current release line

- Current stable tag: `v0.66`
- Current development line: v0.70 design after completed v0.66 post-release validation
- Current development focus: schema compatibility policy and canonical evaluation identity design

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

After `v0.66`, LLMGauge provides:

- local-first CLI runs with preserved raw/cleaned outputs and logs
- artifact validation (`validate-result`, ladder/batch validators)
- manual scoring templates and `score --check` / `score --scores` workflow
- auto-draft scoring as review-required triage only
- single-run `report.md` with **Report Scope**, **Evidence Summary**, **Audit Checklist**, **Prompt Artifact Audit**, and **Publish Readiness Notes**
- comparison reports with **Comparison Scope**, publish-readiness, and **Publication evidence summary**
- `export-index` machine-readable metadata for importers
- model profile onboarding and management commands
- dry-run and preflight commands (`smoke`, `doctor`)
- context ladder and fit ladder artifacts with preserved failures
- public-proof workflow guidance across docs
- Practical Eval v1 seed suite (`wumbolabs-practical-v1`)
- artifact schema documentation and result-directory audit guidance
- publish-readiness notes and explicit claim boundaries

## Recently completed releases

Condensed highlights from recent release lines:

| Release | Focus |
|---|---|
| v0.66 | Runtime reproducibility — command metadata, reasoning-mode metadata, model-source reporting |
| v0.57 | Suite and scoring maturity — rubric guidance, scoreability docs |
| v0.58 | Practical suite polish — prompt audit and metadata |
| v0.59 | Scored comparison evidence — publish-readiness in reports/compare, export-index scoring fields |
| v0.60 | Public-proof workflow hardening — end-to-end checklist, CLI next-steps, validate-result artifact messaging |
| v0.61 | Export/index/report integration — artifact roles, export-index scoring fields, roadmap cleanup |
| v0.62 | Public report artifact polish — Report Scope, Evidence Summary, Comparison Scope |
| v0.63 | Result artifact audit polish — Audit Checklist, Prompt Artifact Audit, auditing docs |

Earlier foundations (v0.46–v0.56 and before) established artifact schemas, validation, scoring, comparison, fit ladder, model profiles, CLI modularization, and public documentation.

## Recent development details

### v0.66 — Runtime reproducibility and reasoning-mode metadata

**Goal:** Make LLMGauge artifacts clearer for public-proof reproduction and
reasoning-model interpretation.

**Scope:**

- structured `runtime-command.json` artifact with redacted `command_argv`
- `model_source` metadata (`model_profile` or `direct_model_path`)
- `reasoning_mode` metadata and bounded `--reasoning-mode` control
- dry-run, `report.md`, and `export-index` visibility for command metadata

**Exit criteria:**

- each run stores resolved llama.cpp command metadata when executed
- dry-run shows reasoning mode and command preview
- export-index reports command metadata availability
- existing v0.65 workflows remain compatible
- full local gate passes

**Avoid:** arbitrary llama.cpp passthrough, profiler automation, model downloads,
network behavior, automatic scoring, leaderboards.


### v0.70 Slice 1 — Schema compatibility and canonical identity design

**Goal:** Define additive schema evolution rules and canonical identity inputs
before implementing provenance, caching, public export, or run fingerprints.

**Scope:**

- compatibility policy for non-breaking and breaking v0.x result schema changes
- canonical JSON/content hashing helper
- prompt-definition and suite-definition identity helpers
- model and backend provenance placement design
- hash-cache invalidation design
- run fingerprint input boundaries
- additive reasoning-mode requested semantics

**Exit criteria:**

- older valid v0.x result directories remain valid when optional fields are absent
- identity hashes are stable across YAML mapping key order
- prompt identity includes rubric and output-contract content
- suite identity includes prompt definitions
- docs distinguish local reproduction data from public-export redaction needs

**Avoid:** GGUF hashing, hash-cache writes, GGUF metadata extraction, executable
hashing, llama.cpp version discovery, public export, hardware capture, reasoning
trace detection, new backends, or release metadata.

### v0.65 — Guided setup / first-run onboarding

**Goal:** Reduce first-run friction without downloading models, building
llama.cpp, or launching models automatically.

**Scope:**

- `llmgauge setup` command with `--scan` and `--non-interactive` modes
- conservative `llama-cli` and GGUF path discovery
- config and model profile write helpers that preserve existing fields
- docs and tests for guided setup and manual fallback

**Exit criteria:**

- `llmgauge setup --scan` is read-only and exits 0
- `llmgauge setup --non-interactive` can create valid config/profile with
  placeholder executable and GGUF for dry-run validation
- `doctor`, `smoke`, and `run --dry-run` pass after setup-created config
- manual `init` workflow still works
- full local gate passes

**Avoid:** model downloads, network behavior, schema-breaking changes, release
metadata on the feature branch, real model launches during setup.

### v0.64 — Repo review, clean-clone readiness, and pre-public-proof hardening

**Goal:** Final conservative hardening before pausing feature work for real-world validation.

**Scope:**

- repo-wide doc consistency (README, INSTALL, QUICKSTART, USAGE, artifact docs)
- clean-clone readiness checklist and claim-boundary review
- stale reference cleanup and public/private safety searches
- small test or CLI help fixes only when audit finds real gaps

**Exit criteria:**

- docs agree on install, smoke, validate, score, report, compare, and export-index workflow
- clean-clone checklist is copy/paste-safe and does not assume private paths
- full local gate passes (`uv run pytest`, `uv run ruff check .`)
- repo is ready for v0.64 release-prep, then clean-clone test and model testing

**Avoid:** new features, schema churn, release metadata on the feature branch, real model runs in CI.

## After v0.64 — feature pause for validation and publication prep

Current planned sequence after v0.64:

1. clean local release branches
2. manual clean-clone test per `docs/CLEAN_CLONE_TESTING.md`
3. real model test pass on selected hardware (user-provided `llama.cpp` and GGUF models)
4. WumboLabs website update with bounded claims
5. first public X post draft about LLMGauge

Clean-clone testing validates installation and CLI readiness. It does not prove model quality. Real model testing and website/social work happen after v0.64.

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