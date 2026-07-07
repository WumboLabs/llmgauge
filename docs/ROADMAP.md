# LLMGauge Roadmap

LLMGauge is a local-first evaluation bench for practical local LLM testing on real consumer hardware.

The project direction is intentionally conservative: reproducible workflows, preserved artifacts, explicit methodology, honest claim boundaries, and useful model characterization before broad public claims.

LLMGauge is part of the WumboLabs “Real Hardware. Real Testing. No Hype.” workflow.

## Current release line

- Current stable tag: `v0.55`
- Current development line: `v0.56`
- Current development focus: comparison/report polish and public-proof workflow refinements

## Product identity

LLMGauge should answer practical local-model questions such as:

- Does this model produce useful answers for real workflows?
- Does it stay honest when it lacks information or tools?
- Does it fit comfortably on consumer hardware?
- How fast is it under the tested runtime settings?
- What context sizes are viable before quality, latency, or VRAM headroom degrade?
- What artifacts support the result?
- What changed between two model runs, suites, scoring passes, or releases?

LLMGauge should not become:

- a cloud eval service
- a model downloader
- a hosted leaderboard
- an automatic judge that hides review
- a hardware overclocking/tuning tool
- a general autonomous agent framework
- a benchmark result submission tool without explicit user action

## Core principles

1. Local-first
   - Normal evaluation runs happen on the user’s machine.
   - No hidden network activity.
   - No automatic model downloads.
   - No telemetry.

2. Artifact-first
   - Raw outputs are preserved.
   - Cleaned outputs are supplemental, not replacements.
   - Logs, VRAM samples, command metadata, reports, scores, and validation records are treated as evidence.

3. Reproducibility over hype
   - Runtime settings that affect results must be visible.
   - Methodology boundaries must be explicit.
   - Comparison reports should explain what can and cannot be concluded.

4. Human review remains central
   - Manual scoring is still the trusted scoring path.
   - Automatic-rule scoring drafts remain drafts until reviewed/applied.
   - Provenance must show what was reviewed, what was inferred, and what remains metadata-only.

5. Consumer-hardware usefulness
   - The project prioritizes practical testing on hardware ordinary local-LLM users can plausibly own.
   - Speed, VRAM headroom, context fit, and completion reliability matter alongside answer quality.

## Completed release highlights

### v0.50: CLI modularization and model profile management

v0.50 split the previously monolithic CLI into focused command modules and added model-profile management commands.

Completed scope:

- modularized CLI command implementation under `src/llmgauge/commands/`
- kept `src/llmgauge/cli.py` as the Typer entrypoint
- added shared CLI helpers in `src/llmgauge/cli_common.py`
- added `llmgauge model list`
- added `llmgauge model add`
- added `llmgauge model update`
- added `llmgauge model remove`
- preserved `llmgauge list-model-profiles` as a compatibility command
- added Pydantic-backed config and model-profile validation
- preserved unknown model-profile YAML fields on update paths
- required `--yes` for model-profile removal
- expanded repository AI-agent guidance

### v0.49: packaged config templates

v0.49 made `llmgauge init` and `init-config` work correctly from installed packages by bundling config templates in the package.

Completed scope:

- packaged config templates
- kept installed CLI initialization independent of repo-relative paths
- preserved source-checkout workflows

### v0.48: user-friendly installation and onboarding

v0.48 focused on making LLMGauge easier to start from both a source checkout and an installed CLI.

Completed scope:

- added user-level config initialization with `llmgauge init`
- kept `llmgauge init-config` compatibility for project-local ignored config
- added `llmgauge smoke` readiness checks that do not launch `llama.cpp`
- added built-in suite aliases such as `practical`, `core`, `agent`, and `context`
- documented source checkout, editable local install, and GitHub install workflows

### v0.47: public repository polish

v0.47 focused on repository trust, version clarity, and public usability.

Completed scope:

- package/CLI version metadata
- `llmgauge version`
- global `llmgauge --version`
- result artifact `llmgauge_version`
- suite mirror drift guard test
- roadmap refresh

### v0.53: installed-user workflow polish

v0.53 improved first-run guidance for installed and checkout users.

Completed scope:

- improved `llmgauge doctor` skip/next-step messaging
- clarified `llmgauge smoke` readiness output and warnings
- documented installed-user first-run workflow in `INSTALL.md`, `QUICKSTART.md`, and `USAGE.md`
- preserved network-free, model-download-free setup checks

### v0.52: model profile polish

v0.52 polished model-profile CLI ergonomics and documentation.

Completed scope:

- added `--model-profile-file` as the preferred alias for model profiles YAML paths
- preserved `--model-profiles` compatibility
- improved model profile validation and mutation error messages
- documented model profile lifecycle patterns

### v0.51: documentation and process hardening

v0.51 made the repository easier and safer to work on with human-supervised AI coding tools.

Completed scope:

- refreshed roadmap and agent workflow guidance
- made `AGENTS.md` the canonical AI-coding runbook
- documented branch, PR, CI, release metadata, tag, and branch cleanup workflows
- clarified that tool-specific sidecar files should not be added unless explicitly requested

### v0.46 and earlier: public documentation, suite audit, scoring, fit ladder, and artifact foundations

Earlier releases established the current artifact model, suite structure, validation, scoring, comparison, fit ladder, runtime metadata, public docs, and practical-evaluation methodology.

## Near-term roadmap

### v0.54 candidate: public repo audit cleanup and clean-clone readiness

Potential scope:

- align README and public docs with the current release line and first-run workflow
- harden ignore rules for local/private artifacts
- genericize public model-profile templates
- add a clean-clone testing checklist
- audit public-facing files for private paths, personal contact details, and stale release language
- keep normal runs network-free and model-download-free

### v0.55 candidate: comparison/report polish

Potential scope:

- improve comparison reports for mixed scored/unscored runs
- make speed, VRAM, fit, and quality tradeoffs easier to read
- add clearer comparison caveats
- improve public-report bundle guidance
- preserve artifact provenance

### v0.56 candidate: suite and scoring maturity

Potential scope:

- expand Practical Eval v1 carefully
- improve rubric text and scoring examples
- keep suite changes versioned
- distinguish Tier 1 smoke, Tier 2 practical eval, and Tier 3 research/public-report workflows
- avoid claiming leaderboard-style authority

## Long-term roadmap

### Public-proof model reports

LLMGauge should eventually produce clean, reproducible public report bundles with:

- result summaries
- prompt outputs
- manual score provenance
- runtime metadata
- VRAM and speed summaries
- fit/context caveats
- methodology limitations
- publishable comparison tables

### Web UI / dashboard direction

A future LLMGauge UI could make local evaluation easier without replacing the CLI.

Potential capabilities:

- browse result artifacts
- inspect raw and cleaned outputs
- review and apply scores
- compare models/runs
- inspect VRAM and throughput
- manage model profiles
- export public-report bundles

Constraints:

- CLI remains the canonical workflow
- UI should not hide artifact files
- UI should not require cloud services
- UI should not mutate artifacts without explicit action

### Context scaling and fit workflows

Continue improving context and fit testing while preserving failure evidence.

Potential direction:

- better fit-ladder summaries
- clearer failure classification
- context-size comparison reports
- bounded adaptive retry only when explicitly requested
- no silent fallback in normal runs

### LocalMaxxing integration

LLMGauge has permission to explore LocalMaxxing integration, but it must remain optional and staged.

Potential levels:

1. Documentation-only compatibility
   - map LLMGauge runtime metadata to LocalMaxxing-style fields
   - clarify claim boundaries

2. Export-only integration
   - generate a LocalMaxxing-compatible JSON payload
   - perform no network activity

3. Explicit submit integration
   - only after API docs are reviewed
   - require a deliberate user command
   - preview submitted data
   - preserve returned submission IDs as supplemental metadata

Constraints:

- no automatic network activity
- no submission during normal runs
- no LocalMaxxing dependency for normal users
- no leaderboard claims from LLMGauge quality scores

## Non-goals

- Do not remove the `uv run` development workflow.
- Do not require network activity for normal runs.
- Do not make setup overly magical.
- Do not bundle unrelated feature work into release metadata.
- Do not turn LLMGauge into a cloud service, downloader, benchmark leaderboard, automatic judge, or hardware tuning framework.
- Do not make AI-assisted development autonomous or unsupervised.

## Branch and release discipline

LLMGauge uses `main` as the default branch.

Expected release flow:

1. feature branch from `main`
2. focused commits
3. local full gate
4. push branch only when asked
5. PR to `main`
6. PR CI
7. merge with a merge commit when focused history should be preserved
8. separate release-prep branch for version metadata
9. release-prep PR and CI
10. merge release metadata
11. final main verification
12. annotated tag
13. push tag
14. cleanup merged branches

Release metadata belongs in a separate release-prep commit unless explicitly directed otherwise.
