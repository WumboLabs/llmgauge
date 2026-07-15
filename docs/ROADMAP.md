# LLMGauge Roadmap

LLMGauge is a conservative local-first CLI for practical LLM evaluation on real consumer hardware.

The project produces defensible, reproducible public evidence about usefulness, honesty, correctness, safety, speed, VRAM headroom, and workflow fit under disclosed hardware and runtime conditions.

LLMGauge is part of the WumboLabs workflow: **Real Hardware. Real Testing. No Hype.**

## Current release line

- Current stable tag: `v0.70`
- Current package version: `0.70.0`
- Current release line: `v0.70.0`
- Current focus: public reporting, reproducible evidence, and practical model comparisons

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

## vLLM evidence track

The vLLM work is intentionally bounded to an externally managed local
integration and evidence collection. The accepted [runtime contract](VLLM_RUNTIME_CONTRACT.md)
and [HTTP transport assessment](VLLM_HTTP_TRANSPORT_ASSESSMENT.md) define a
loopback-only, text-only backend using the Python standard library. LLMGauge
does not install, start, supervise, or otherwise own the vLLM server lifecycle;
`llama.cpp`/GGUF remains the default runtime.

### Implemented capability

- External local vLLM adapter with sequential, non-streaming requests to an
  operator-managed loopback server.
- Bounded readiness and served-model checks; no remote, authenticated, streaming,
  concurrent, or server-lifecycle management support.
- Additive runtime evidence for server `/version`, API-readiness state, optional
  `system_fingerprint`, and ordered-unique run-level fingerprints, with
  backward-compatible validation, reporting, and export handling.

### Validated evidence

- [Live external-vLLM smoke](VLLM_LIVE_SMOKE_EVIDENCE.md): real
  Qwen2.5-3B-Instruct server, successful readiness/request/validation/reporting;
  historical pre-fingerprint evidence remains authoritative for that point in
  time.
- [Fingerprint live verification](VLLM_FINGERPRINT_LIVE_SMOKE_EVIDENCE.md):
  vLLM `0.25.1`, `server_state=ready`,
  `server_state_meaning=api_ready_observation`, and
  `vllm-0.25.1-eb488855` agreed across request, prompt, and run-level artifacts.
- [Cross-runtime comparison methodology](VLLM_CROSS_RUNTIME_COMPARISON_METHODOLOGY.md):
  runtime-native metrics, input/template disclosure, and bounded claim rules.
- [First prompt comparison](VLLM_CROSS_RUNTIME_COMPARISON_EVIDENCE.md):
  `tool-honesty/fake-tool-resistance`; vLLM 31/50 (average 3.1, mixed) and
  llama.cpp 25/50 (average 2.5, fail).
- [Second prompt comparison](VLLM_CROSS_RUNTIME_SECOND_PROMPT_EVIDENCE.md):
  `shell-safety/failed-command-recovery`; vLLM 32/50 (average 3.2, mixed) and
  llama.cpp 19/50 (average 1.9, fail). The direction replicated, but these
  two prompt-specific observations are not a benchmark or runtime ranking.

### Closed investigation

- [Gemma 4 12B NVFP4 CPU-offload audit](GEMMA4_12B_NVFP4_CPU_OFFLOAD_EVIDENCE.md):
  one checkpoint, one vLLM environment, one RTX 5070 host, and one controlled
  attempt. Mixed FP8/NVFP4 recognition was verified, but requested 4 GiB CPU
  offload had no successful observed offload before a construction-time BF16
  `ParallelLMHead` CUDA OOM. The server never reached readiness.
  Classification: `not_viable` for the disclosed configuration only.

### Active limitations

- No remote, authentication, streaming, or concurrency support; no
  LLMGauge-owned vLLM lifecycle.
- vLLM VRAM is not captured.
- Throughput and token fields remain runtime-native and non-equivalent.
- F16 GGUF and BF16 Transformers weights are not proven bit-identical, and
  prompt rendering/input forms are not proven identical.
- Manual scores are reviewer judgment, not objective truth; two scored prompts
  do not establish general runtime superiority.
- Server version and fingerprint are unauthenticated metadata. Fingerprint
  equality does not prove identical runtime state, and `server_state=ready`
  means API readiness only.
- Startup success or failure does not establish answer quality. The Gemma
  `not_viable` result does not generalize to another checkpoint, runtime, host,
  offload implementation, or quantization.

### Current decision

The bounded vLLM evidence track is complete enough for the present release line.
No immediate production feature expansion is justified solely by the current
evidence. Future vLLM work requires a concrete product or evidence need.

### Selected next bounded project milestone

**Produce and review one real end-to-end Fit Ladder validation artifact.**
This is the strongest existing project-level next step because Fit Ladder is
already implemented and documented, and a preserved-failure artifact directly
advances LLMGauge as a practical local-model evaluation engine without
speculative vLLM expansion or another random model experiment.

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


### v0.70 - Identity, provenance, and public-export foundations

The following v0.70 foundations are complete on `main`:

- canonical identity and additive compatibility policy
- model provenance and identity-validated hash caching
- llama.cpp executable provenance
- bounded llama.cpp build identity discovery

The v0.70 release completed local wheel, source-distribution, isolated
installed-CLI, real-artifact compatibility, privacy, and source-integrity
validation. `v0.70` is the current validated released install. PyPI availability
is not claimed.

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

## v0.70 release validation

The completed v0.70 release-validation sequence was:

1. packaging audit
2. installed-CLI validation
3. real model test pass on selected hardware, using user-provided `llama.cpp` and GGUF models
4. bounded publication preparation after validation

Packaging and clean-clone checks validate installation and CLI readiness. They
do not prove model quality or establish PyPI availability.

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
