# LLMGauge Roadmap

LLMGauge is the evidence engine for practical local model testing on real consumer hardware.

The project direction is intentionally conservative: reproducible workflows, preserved artifacts, explicit methodology, honest claim boundaries, and useful model characterization before broad public claims.

The point is not to chase every model, build a hosted leaderboard, or declare universal winners. The point is to produce defensible, reproducible public evidence about usefulness, honesty, correctness, safety, speed, VRAM/headroom, and workflow fit under disclosed hardware/runtime conditions.

LLMGauge is part of the WumboLabs “Real Hardware. Real Testing. No Hype.” workflow.

## Current release line

- Current stable tag: `v0.60`
- Current development line: `v0.61`
- Current development focus: export/index/report integration polish

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

### v0.54: public repo audit cleanup and clean-clone readiness

v0.54 prepared the public repository for external-style installs and audits.

Completed scope:

- aligned README and public docs with the current release line and first-run workflow
- hardened ignore rules for local/private artifacts
- genericized public model-profile templates
- added `docs/CLEAN_CLONE_TESTING.md`
- removed tracked local config files and sanitized audit-doc placeholders
- kept normal runs network-free and model-download-free

### v0.55: clean-clone doc corrections

v0.55 fixed first-run and clean-clone documentation after v0.54 testing.

Completed scope:

- corrected post-init `model add` examples so they do not collide with packaged `example_model`
- aligned README, INSTALL, QUICKSTART, USAGE, and CLEAN_CLONE_TESTING guidance
- documented init template profiles and `--force` replacement behavior

### v0.56: comparison and report polish

v0.56 improved comparison-report clarity for public-proof workflows.

Completed scope:

- added **Publish Readiness Notes** to comparison reports
- expanded interpretation notes and claim-boundary language
- documented responsible comparison usage in `PUBLIC_REPORTING.md` and `LOCAL_MODEL_TESTING.md`
- preserved deterministic Markdown output and existing artifact schemas

### v0.46 and earlier: public documentation, suite audit, scoring, fit ladder, and artifact foundations

Earlier releases established the current artifact model, suite structure, validation, scoring, comparison, fit ladder, runtime metadata, public docs, and practical-evaluation methodology.

## Forward roadmap

### v0.57 — Suite and scoring maturity

Primary goal:

Make existing practical suites and scoring guidance more credible, consistent, and publishable.

Likely work:

- review Practical Eval v1 scoring guidance
- tighten rubric wording where ambiguous
- add better scoring examples for pass/mixed/fail cases
- clarify when a result is scoreable vs `needs_review`
- improve docs around failure labels and good labels
- check whether existing labels are too broad, duplicated, or under-defined
- add tests only if scoring metadata or generated templates change

Good outcome:

A human reviewer has clearer guidance for scoring practical local-model outputs, and public comparison claims are easier to defend.

Avoid:

- automatic LLM-as-judge scoring
- new leaderboard framing
- changing score meanings casually
- large suite rewrites
- adding many new prompts before current rubric quality is stable

### v0.58 — Practical suite polish

Primary goal:

Improve actual prompt suite quality, especially `wumbolabs-practical-v1`.

Likely work:

- audit prompt wording for ambiguity
- remove or revise prompts that overfit to one environment
- ensure prompts test useful, real consumer-hardware behavior
- improve prompt metadata and expected review dimensions
- confirm each prompt produces enough evidence for scoring
- add or refine only a small number of prompts if there is a clear gap

Good outcome:

The practical suite becomes a stronger public-proof suite for usefulness, honesty, technical correctness, safety, and real workflow fit.

Avoid:

- expanding prompt count just to expand it
- agent-heavy framing unless a prompt is explicitly agent-oriented
- benchmark trivia
- model-specific prompts

### v0.59 — Scored comparison evidence polish

Primary goal:

Make scored comparisons easier to turn into public WumboLabs proof.

Likely work:

- improve scored comparison docs
- clarify how to compare same-suite vs cross-suite runs
- add better examples of bounded public claims
- improve report language around small score differences
- possibly add better summary tables if they are deterministic and schema-safe

Good outcome:

A comparison report can be read by an outside person and they can understand what is supported, what is not supported, and why.

Avoid:

- declaring winners automatically
- ranking models globally
- hiding caveats behind averages

### v0.60 — Public-proof workflow hardening

Primary goal:

Tighten the full run → validate → inspect → score → compare → publish workflow.

Likely work:

- review docs end-to-end from clean install to public comparison
- make sure commands are consistent across README, QUICKSTART, USAGE, LOCAL_MODEL_TESTING, and PUBLIC_REPORTING
- add a concise public-proof checklist
- add examples of publishable vs non-publishable claims
- ensure report artifacts, score files, cleaned outputs, and raw outputs are referenced consistently

Good outcome:

The project has a coherent, repeatable public-proof workflow, not just a set of independent CLI commands.

Avoid:

- new major CLI surface
- packaging churn
- external website integration before the proof workflow is tight

### v0.61 — Export/index/report integration polish

Primary goal:

Improve how downstream tools, website scripts, or Monolith can consume results without changing core semantics.

Likely work:

- review export-index fields for public-proof completeness
- improve docs for machine-readable metadata
- ensure scoring provenance, artifact paths, run metadata, and comparison caveats are visible
- possibly add small metadata fields only if clearly needed and backward-safe

Good outcome:

External reporting tools can consume LLMGauge artifacts without guessing about score state, review state, or artifact completeness.

Avoid:

- breaking artifact compatibility
- major schema migration
- Monolith-specific coupling

### v0.62 — Real-result publication preparation

Primary goal:

Prepare the first polished public comparison result set.

Likely work:

- pick a narrow model set
- re-run or verify existing practical-use results
- confirm comparable settings
- confirm score files are reviewed
- generate comparison reports
- prepare public-readable result summaries
- identify exact artifacts worth publishing

Good outcome:

WumboLabs has a clean candidate result set for publication, not just private local testing notes.

Candidate comparison set:

- Gemma 4 12B IT QAT UD-Q4_K_XL
- Mellum2 Instruct Q4_K_M
- Qwen3.6 35B-A3B UD-IQ2_M
- Qwen3-14B Q4_K_M
- possibly Grug-12B Q4_K_M as an additional comparison point

The point is not to chase every model. The point is to publish a defensible, bounded comparison.

### v0.63 — Public WumboLabs proof layer

Primary goal:

Move selected results into a public-facing WumboLabs presentation.

Likely work:

- decide website format for result summaries
- publish bounded claims only
- include hardware/runtime disclosure
- include score caveats
- link or reference relevant artifacts
- avoid leaderboard framing

Good outcome:

The WumboLabs site can show real local-model evidence under “Real Hardware. Real Testing. No Hype.”

Avoid:

- making the website a benchmark leaderboard
- hiding failure cases
- overstating generality

### v0.64+ — Tooling after public proof is credible

Primary goal:

Only after the public-proof loop is working, consider broader tooling improvements.

Possible later lanes:

- better comparison table formatting
- optional static report generation
- more robust artifact browsing
- richer score summaries
- fit-ladder/report integration polish
- context-size comparison reporting
- importer/exporter polish for Monolith
- more suite aliases
- better result grouping by model/profile/suite/hardware

These are useful, but they should follow evidence quality, not precede it.

## Strategic priority order

1. v0.57: scoring/rubric maturity
2. v0.58: practical suite polish
3. v0.59: scored comparison evidence polish
4. v0.60: public-proof workflow hardening
5. v0.61: export/index/report integration polish
6. v0.62: prepare first public result set
7. v0.63: publish WumboLabs proof layer
8. v0.64+: only then add broader tooling polish

## Working rule

For every proposed v0.57+ task, ask:

Does this make LLMGauge better at producing defensible public evidence about local models on real consumer hardware?

If yes, it belongs on the roadmap.

If it is only private progress, model chasing, UI polish, or architecture expansion, park it.

## Later exploration

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
