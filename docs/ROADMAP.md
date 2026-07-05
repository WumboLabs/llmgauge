# LLMGauge Roadmap

This roadmap is conservative and may change as real local testing exposes friction.

## Current direction

LLMGauge should become a practical, independently usable local LLM evaluation bench before publishing many model findings.

Priority is external usability, reproducible workflows, clear artifacts, preserved raw outputs, honest claim boundaries, and public-proof methodology.

LLMGauge is not a leaderboard, cloud eval service, model downloader, automatic judge, agent framework, or hardware tuning tool.

## Current release line

- Current stable tag: `v0.47`
- Current development line: `v0.48`
- Current development focus: easier install, user-level initialization, doctor polish, smoke-test onboarding, and reproducibility guardrails

## Recently completed

### v0.43: runtime metadata trust work

v0.43 made runtime settings that affect reproducibility visible in artifacts and reports.

Completed scope:

- added explicit `--flash-attn auto|on|off`
- allowed `flash_attn` in model profiles and default config
- stored `runtime.flash_attn` in result JSON
- showed Flash attention in run reports and comparison reports
- added explicit runtime methodology labels such as `stock-reference`, `daily-tuned`, or `experimental`
- kept power-limit and deeper GPU telemetry capture for a later, separate slice

### v0.44: public-understandable documentation work

v0.44 made the repository more understandable to a technically curious public user without requiring prior project context.

Completed scope:

- refreshed README as a concise public front door
- made the source-checkout workflow explicit with `uv run llmgauge ...`
- kept installed CLI usage separate from development/source-checkout usage
- clarified the first-run path in Quickstart
- kept public install/package polish for a later release

### v0.46: public docs cleanup and suite/prompt audit

v0.46 folded in the untagged v0.45 public-docs cleanup work and finalized a public-facing suite/prompt audit slice.

Completed scope:

- removed stale historical notes from public docs
- removed private/internal project-memory notes from the public repository
- sanitized public docs and bundled prompts so they do not depend on private machine or project context
- added public suite methodology guidance
- generalized `wumbolabs-practical-v1` technical-correctness coverage to a distro-agnostic Linux/NVIDIA update-boundary prompt
- bumped `wumbolabs-practical-v1` to suite version `0.2.0`
- clarified `agent-backend-v1` and `context-v1` scope
- synced the source-checkout `suites/` tree with packaged built-in suites

## Completed v0.47 public repository polish

v0.47 focused on repository trust, version clarity, and public usability before deeper feature expansion.

Completed scope:

- package/CLI version metadata
- `llmgauge version`
- global `llmgauge --version`
- run artifact `llmgauge_version` sourced from package metadata
- suite mirror drift guard test for source-checkout suites vs packaged built-ins
- roadmap refresh after v0.46

Potential v0.48 scope:

- add `LICENSE`
- add `CONTRIBUTING.md`
- add GitHub Actions CI
- add or update repository metadata guidance
- clean duplicate `.gitignore` entries if straightforward
- keep changes small, testable, and release-safe

## Near-term roadmap

### v0.48: user-friendly installation and onboarding

Goals:

- make LLMGauge easier to try from a clean checkout or installed CLI
- make setup failures diagnosable with clear next steps
- keep onboarding explicit, local-first, and non-magical
- avoid model downloads, hidden network activity, or private-path assumptions

Planned work:

- clarify source-checkout usage vs installed CLI usage
- add or refine user-level config discovery under `~/.config/llmgauge/`
- add preferred `llmgauge init` flow while keeping `init-config` compatibility
- polish `llmgauge doctor` so setup checks are action-oriented
- add a simple `llmgauge smoke` workflow for proving one configured model can create and validate a result artifact
- update README, Quickstart, and Usage docs around the new first-run path

### Repository trust and public maintenance

Recently completed in v0.47:

- MIT license
- contributor guide
- read-only GitHub Actions CI
- package/CLI version metadata
- suite mirror drift guard test

Potential later work:

- add issue/PR templates if external activity warrants it
- add `SECURITY.md` when the project surface grows
- clean duplicate `.gitignore` entries if straightforward

### User-friendly installation and onboarding

Goal: make LLMGauge feel like a normal installed CLI tool for users, while preserving the current `uv run` development workflow for contributors.

Current development workflow:

- `uv run llmgauge ...`
- `uv run pytest`
- `uv run ruff check .`

Target user workflow:

- `llmgauge doctor`
- `llmgauge init`
- `llmgauge model add ...`
- `llmgauge run ...`
- `llmgauge score ...`
- `llmgauge compare ...`

Planned direction:

1. Installation and usage documentation split
   - clearly document normal installed CLI usage with `llmgauge ...`
   - separately document development usage with `uv run llmgauge ...`
   - explain editable local installs with `uv tool install --editable .`
   - keep public quickstart examples free of machine-specific local paths

2. User config discovery
   - support user-level config under `~/.config/llmgauge/`
   - keep project-local config discovery for repo/development workflows
   - prefer explicit CLI paths over discovered config
   - keep built-in defaults conservative

3. `llmgauge init`
   - create initial user config files
   - configure the llama.cpp binary path
   - configure default results directory
   - optionally record default backend/runtime settings
   - keep the first version conservative and non-magical

4. Model onboarding polish
   - improve `llmgauge model add`
   - improve `llmgauge model list`
   - add or improve model update/remove flows if needed
   - validate missing model paths clearly
   - preserve the mental model that `--model-profile` selects a configured model and `--model-path` loads an exact GGUF file

5. Suite discovery and built-in suite aliases
   - add or improve `llmgauge suite list`
   - allow users to run built-in suites by ID rather than repo-relative paths
   - keep explicit suite paths supported for custom/local suites

6. Smoke-test workflow
   - add a simple `llmgauge smoke` path
   - run one short built-in prompt against a configured/default model
   - validate artifact creation
   - print the report path and next recommended command

7. Public install polish
   - support a clean GitHub install path first, such as `uv tool install git+https://github.com/WumboLabs/llmgauge`
   - consider PyPI later only when packaging, docs, versioning, and bundled suite behavior are stable
   - do not require network activity for normal runs

### Runtime reproducibility metadata

Goal: preserve comparability when users tune llama.cpp/runtime settings.

Planned direction:

- capture and report runtime settings that affect comparability
- include fields such as power limit, batch, ubatch, flash-attn mode, llama.cpp build/commit, GPU name, driver version, model path/quant, and runtime profile metadata when available
- avoid silently mixing tuned daily runs with stock/reference comparison artifacts

## Later milestones

- comparison/report workflow polish
- example public report bundle
- expanded Practical Eval v1 prompt set
- richer installed-CLI validation
- downstream import polish
- gradual `cli.py` module split
- config/profile/suite schema validation polish
- public artifact sanitization/export mode

## Future GitHub and branch-name maintenance

- Use `main` as the default branch name for new GitHub repositories going forward.
- Keep existing LLMGauge `master` branch as-is unless a separate branch-rename maintenance task is intentionally scheduled.
- If LLMGauge is later renamed from `master` to `main`, handle it as a standalone compatibility task:
  - update GitHub default branch settings before deleting or retiring `master`
  - review branch protection and repository rules
  - update docs, badges, scripts, release notes, and examples that mention `master`
  - verify local and remote tracking branches after the rename
  - avoid bundling the rename with feature work or release-critical fixes
- Future CLI polish idea: keep `--model-profile` as the configured model selector, and consider adding `--model-profile-file` as the clearer preferred name for the YAML file path currently passed with `--model-profiles`.
- If `--model-profile-file` is added, keep `--model-profiles` as a compatibility alias for at least one release cycle and document the transition clearly.

## Future LocalMaxxing integration

LLMGauge has green light from LottoLabs to explore LocalMaxxing integration. This is now a planned optional integration area, but not the immediate v0.48 priority.

LLMGauge and LocalMaxxing solve complementary problems:

- LLMGauge focuses on reproducible quality evaluation, prompt-suite artifacts, manual scoring, and reporting.
- LocalMaxxing focuses on local LLM inference performance benchmarking, public hardware/model comparison, and benchmark sharing.

Integration should be staged and opt-in.

### Proposed integration levels

1. Documentation-only compatibility
   - document how LLMGauge runtime metadata maps to LocalMaxxing-style benchmark fields
   - clarify what LLMGauge can and cannot claim from prompt-suite runs

2. Export-only integration
   - add `llmgauge export-localmaxxing`
   - write a LocalMaxxing-compatible JSON payload from an existing artifact or dedicated benchmark artifact
   - perform no network activity

3. Explicit submit integration
   - add `llmgauge submit-localmaxxing`
   - use LocalMaxxing API docs from the website after reviewing the API contract
   - require an explicit user command
   - preview what will be submitted
   - preserve any returned benchmark/submission ID as supplemental metadata

4. Dedicated benchmark runner, if needed
   - only if LocalMaxxing requires benchmark data that LLMGauge prompt-suite runs should not approximate
   - keep this separate from LLMGauge's quality-evaluation workflow

Design constraints:

- entirely optional
- no LocalMaxxing dependency for normal LLMGauge users
- no automatic network or API activity
- no submission during normal `run`, `smoke`, `score`, or `compare`
- no change to LLMGauge's primary quality-evaluation mission
- no leaderboard claims from LLMGauge quality scores
- preserve raw artifacts and methodology boundaries
- do not implement API calls until LocalMaxxing API docs have been reviewed and captured in a design note

Likely roadmap placement:

- v0.48: install/onboarding, `init`, `doctor`, and `smoke`
- v0.49 or later: LocalMaxxing export-only design and payload generation
- later: optional submit command, if the API contract and user value justify it

## Non-goals

- do not remove the `uv run` development workflow
- do not require network activity for normal runs
- do not make setup overly magical
- do not bundle unrelated feature work into installation polish
- do not turn LLMGauge into a cloud service, downloader, benchmark leaderboard, automatic judge, or hardware tuning tool
