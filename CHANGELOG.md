# Changelog

## v0.55 - 2026-07-07

- Corrected first-run and clean-clone documentation so post-init `model add` examples use new profile names instead of colliding with packaged `example_model`.
- Clarified that `llmgauge init` creates example template profiles and that users should edit, update, or intentionally replace them with `--force`.
- Updated clean-clone docs to use `clean_clone_model` for add/list/dry-run verification.
- Removed the remaining stale `model add example_model` example from local model testing docs.

## v0.54 - 2026-07-07

- Refreshed public onboarding docs so README, Install, Quickstart, and Usage agree on the current first-run workflow.
- Updated the roadmap for the v0.54 release line and moved recent candidate work into completed release highlights.
- Hardened `.gitignore` for local config, generated results, scratch output, environment files, editor noise, and common Python caches.
- Replaced the public package contact email with `contact@wumbocore.com`.
- Genericized public model-profile templates so they no longer imply specific model recommendations.
- Added `docs/CLEAN_CLONE_TESTING.md` as a repeatable fresh-clone audit checklist.
- Removed tracked local config from the public repository and sanitized audit docs to avoid committed private machine identifiers.

## v0.53 - 2026-07-07

- Improved `llmgauge doctor` first-run guidance for missing config, missing profiles, skipped checks, and selected model profile prerequisites.
- Clarified `llmgauge smoke` readiness output, including pass-with-warnings behavior for incomplete setup.
- Updated `llmgauge init` next steps to include `doctor`, `model add`, `model list`, `smoke`, and dry-run preview.
- Documented the installed-user first-run workflow across Install, Quickstart, and Usage docs.
- Clarified `doctor` and `smoke` status meanings, inspection-only behavior, and project-local versus user-level config discovery.

## v0.52 - 2026-07-07

- Added `--model-profile-file` as a clearer alias for model profile YAML paths while preserving `--model-profiles` compatibility.
- Improved model profile validation and mutation error messages.
- Documented the model profile lifecycle in Usage, Quickstart, and Local Model Testing docs.
- Clarified profile path discovery, update behavior, `add --force` replacement behavior, `remove --yes`, and YAML comment caveats.
- Polished doctor and smoke guidance wording to prefer `--model-profile-file` while noting the compatibility alias.

## v0.51 - 2026-07-07

- Refreshed the roadmap for the v0.50 stable / v0.51 development line.
- Expanded the roadmap into a fuller LLMGauge direction document.
- Hardened `AGENTS.md` as the self-contained guidance source for supervised AI coding tools across different agent harnesses and models.
- Documented the standard branch, PR, CI, merge, release metadata, tag, and cleanup workflows.
- Updated README release-line references.

## v0.50 - 2026-07-07

- Modularized the CLI into focused command modules while preserving the public command surface.
- Added `llmgauge model` profile management commands for listing, adding, updating, and removing local model profiles.
- Preserved the `llmgauge list-model-profiles` compatibility command.
- Added Pydantic-backed validation for config and model-profile documents.
- Hardened model-profile mutations: removals require `--yes`, and update paths preserve unknown YAML fields.
- Expanded repository agent guidance in `AGENTS.md`.

## v0.49 - 2026-07-05

- Packaged `llmgauge init` and `init-config` templates inside the installable package so GitHub and tool installs no longer depend on repo-relative `examples/configs` files.
- Treated template placeholder paths as setup warnings during `smoke`, preserving safe first-run checks without failing before users edit local paths.
- Finalized install/onboarding documentation for source checkout, editable installs, GitHub installs, update/uninstall workflows, and first-run verification.
- Validated source checkout, editable `uv tool install`, GitHub `uv tool install`, global tool reinstall, and main CI.

## v0.48 - 2026-07-05

- Added user-level initialization with `llmgauge init`, while preserving `init-config` for project-local compatibility.
- Added `llmgauge smoke` readiness checks for package, suite, config, model-profile, `llama-cli`, optional `nvidia-smi`, and optional selected-model validation without launching `llama.cpp`.
- Added built-in suite aliases such as `practical`, `core`, `agent`, and `context`, while preserving canonical suite IDs in resolved run metadata.
- Added public install documentation covering source checkout, editable local install, GitHub install, first-run setup, configuration discovery, and safe dry-run checks.
- Linked install guidance from README, Quickstart, and Usage.

## v0.47 - 2026-07-04

- Added package and CLI version metadata for the v0.47 development line.
- Added `llmgauge version` and global `llmgauge --version`.
- Updated run artifacts so `llmgauge_version` is sourced from package metadata instead of a hardcoded placeholder.
- Added tests for CLI version output and run artifact version metadata.
- Added a suite mirror drift guard test to keep source-checkout suites and packaged built-in suites synchronized.
- Refreshed the roadmap for v0.47 public repository polish.
- Added an MIT license.
- Added contributor guidance for development gates, suite hygiene, artifact preservation, runtime claim boundaries, and public-safe prompts.
- Added read-only GitHub Actions CI for tests, ruff, and whitespace diff checks.

## v0.46 - 2026-07-04

- Cleaned the public documentation tree by removing stale historical notes and private/internal project-memory docs.
- Sanitized public docs and bundled prompts to remove private machine names, stale internal context, and project-specific leakage.
- Added public suite methodology guidance emphasizing self-contained prompts, practical usefulness, honest uncertainty, conservative technical advice, manual review, reproducibility, and bounded claims.
- Generalized WumboLabs Practical Eval v1 technical-correctness coverage from an Arch-specific NVIDIA update prompt to a distro-agnostic Linux/NVIDIA update-boundary prompt.
- Bumped `wumbolabs-practical-v1` to suite version `0.2.0`.
- Added claim-scope notes to `agent-backend-v1` and clarified that `context-v1` currently provides context ladder presets.
- Synced the source-checkout `suites/` tree with packaged built-in suites so CLI behavior and packaged suite metadata agree.
- Note: the untagged v0.45 public-docs cleanup work was folded into this v0.46 release.

## v0.44 - 2026-07-04

- Refreshed README as a concise public overview for technically curious users.
- Clarified that the current recommended early-user workflow is source-checkout usage with `uv run llmgauge ...`.
- Updated Quickstart with a clearer first-run path, command-form guidance, and runtime metadata examples.
- Added `docs/USAGE.md` as a compact command map for common LLMGauge workflows.
- Updated the roadmap to mark v0.43 runtime metadata work complete and v0.44 public documentation polish active.

## v0.43 - 2026-07-04

- Added explicit `--flash-attn auto|on|off` runtime configuration for llama.cpp runs.
- Stored `runtime.flash_attn` in result artifacts and surfaced it in run reports and comparison reports.
- Allowed `flash_attn` to be configured from model profiles or defaults, including YAML boolean-style `on`/`off` values.
- Added explicit `--runtime-label` metadata for distinguishing stock-reference, daily-tuned, experimental, or other runtime methodologies in artifacts and reports.

## v0.42 - 2026-07-03

- Improved run model-selection guidance when a configured model profile name is accidentally passed with `--model-id`.
- Clarified `--only` help text as the exact prompt ID selector.
- Added a warning when score files validate or apply as review metadata without numeric dimension values.

## v0.41 - 2026-07-02

- Show scored interpretation and scoring provenance in run reports whenever applied score objects exist, including nonnumeric assisted drafts.

## v0.40 - 2026-07-02

- Added scoring provenance visibility to generated run reports, including scoring mode counts, reviewed/unreviewed counts, and scorer IDs.
- Added an explicit report warning when applied scores include unreviewed assisted drafts.

## v0.39 - 2026-06-26

- Added overwrite protection for `llmgauge score --auto-draft`; existing `auto-scores.yaml` files are preserved unless `--force` is supplied.
- Improved auto-draft command output with review-required guidance and the next validation command.

## v0.38 - 2026-06-26

- Added `llmgauge score RESULT_DIR --auto-draft` to create deterministic assisted scoring drafts in `auto-scores.yaml`.
- Auto score drafts use local rules only, preserve review-required provenance metadata, and do not modify `llmgauge-result.json`, `report.md`, raw outputs, cleaned outputs, or logs.
- Kept assisted scoring inside the existing explicit apply workflow: validate with `--scores auto-scores.yaml --check`, then apply with `--scores auto-scores.yaml` after review.

## v0.37 - 2026-06-26

- Improved `llmgauge score` errors when a ladder, Fit Ladder, or batch parent artifact is passed instead of a single-run result directory.
- Added scoring provenance metadata preservation for applied score objects, including scoring mode, scorer identity, confidence, evidence, warnings, review status, and override status.
- Added `scoring_mode_counts` to run items in `export-index` so manual and assisted scoring metadata can be distinguished in downstream reports.

## v0.36 - 2026-06-26

- Polished Fit Ladder report output by rendering empty report fields as `—` instead of `None`.
- Added a VRAM summary table to `fit-ladder-report.md` when attempt-level VRAM data is available.
- `llmgauge fit-ladder` now prints the generated `fit-ladder-report.md` path after completed or failed runs.

## v0.35 - 2026-06-24

- Added Fit Ladder artifact validation with `validate-fit-ladder`.
- Added Fit Ladder artifact detection and metadata to `export-index`.
- Added `fit-ladder-report.md` generation for Fit Ladder runs.

## v0.34 - 2026-06-23

- Added explicit `llmgauge fit-ladder` execution for opt-in context fallback attempts.
- Added `llmgauge fit-ladder --dry-run` to preview requested context and fallback attempt order without launching llama.cpp.
- Fit Ladder now writes `fit-ladder-summary.json` and stops at the first completed attempt while preserving failed attempt directories.

## v0.33 - 2026-06-23

- Added Fit Ladder foundation helpers for context fallback planning, attempt records, OOM/process-killed/runtime failure classification, and fit-ladder summaries.
- Kept Fit Ladder execution opt-in and deferred the retry execution loop to a later release.

## v0.32 - 2026-06-23

- Added `llmgauge run-ladder --dry-run` to resolve and print multi-context ladder plans without launching llama.cpp or creating artifacts.

## v0.31 - 2026-06-23

- Added `llmgauge run --dry-run` to resolve and print run plans without launching llama.cpp or creating result artifacts.

## v0.30 - 2026-06-23

- Added `llmgauge init-config` to create ignored local config files from example templates.
- Added `llmgauge list-model-profiles` to inspect configured model profiles and model path status.
- Updated `llmgauge doctor` to auto-detect local config and model profile files when present.
- Updated run option resolution to auto-detect local config and model profile files when explicit paths are omitted.
- Added model-profile onboarding and first-run command polish roadmap.
- Updated Quickstart for the shorter first-run setup flow.

## v0.29 - 2026-06-23

- Expanded `llmgauge doctor` to check config, llama-cli, model profiles, selected model file paths, built-in suites, and optional NVIDIA telemetry.
- Added a clean quickstart for first-run setup, validation, scoring, and export-index workflow.
- Documented the planned Fit Ladder / adaptive-fit design for explicit OOM-aware fallback testing.
- Updated README status and public documentation links.

## v0.28 - 2026-06-23

- Added scored interpretation summaries to run reports.
- Added public reporting guidance for evidence, claim boundaries, and report structure.

## v0.27 - 2026-06-23

- Added public-proof scoring metadata to run items in `export-index`.
- Added `scoring_status`, `scored_prompt_count`, `manual_score_average`, aggregate score labels, verdict counts, and rubric metadata to exported run indexes.
- Documented additive export-index scoring fields for report-generation and importer workflows.

## v0.26 - 2026-06-23

- Added evaluation tier documentation to define what LLMGauge results can and cannot claim.
- Added Practical Eval v1 publication-grade prompt quality and scoring guidance.
- Added the initial WumboLabs Practical Eval v1 seed suite with 10 prompts.
- Added suite-aware manual score templates that use suite-defined dimensions when available.
- Added manual score label validation against the selected rubric or suite vocabulary.
- Tightened the WumboLabs Practical Eval v1 seed prompts after shakedown review.
- Validated the v0.26 Practical Eval v1 workflow with a local Mellum2 Instruct shakedown run:
  - 10/10 prompts completed
  - result validation passed
  - suite-aware scoring passed
  - scored report generated successfully
  - manual score average: 3.59 / 5
- Clarified that Practical Eval v1 is still a seed suite and should not be treated as a finished public benchmark.

## v0.25 - 2026-06-21

- Added `llmgauge score --check` to validate score files without mutating result artifacts.
- Documented score-file validation workflow before applying manual scores.

## v0.24 - 2026-06-20

- Added comparison report interpretation notes.
- Added quality-signal and performance-signal summaries to comparison reports.
- Updated scored comparison documentation for VRAM-aware reports and safer interpretation.

## v0.23 - 2026-06-20

- Added manual scoring rubric guidance for default, safety/local-ops, and agent-backend review.
- Documented a reusable failure/good label vocabulary for scored runs.
- Linked rubric guidance from README and scoring workflow docs.

## v0.22 - 2026-06-20

- Hardened manual score schema constants and validation.
- Added rubric metadata to generated score templates and applied prompt scores.
- Added `score_rationale` to manual score entries.
- Added allowed verdict validation for manual score templates.
- Strengthened result validation for applied score metadata.
- Documented `scores.yaml` and applied score fields.
- Clarified user-facing manual scoring workflow, verdicts, and score rationale guidance.

## v0.21

- Added cleaned output preview artifacts under `cleaned/`.
- Preserved raw model stdout unchanged under `raw/`.
- Added `cleaned_output_path` to new prompt results.
- Updated reports to link cleaned output when available.
- Added `has_cleaned_artifacts` to run export-index items.
- Kept cleaned output validation optional for backward compatibility with older result artifacts.
- Documented cleaned output as a derived review artifact, not audit evidence.

## v0.20.1

- Added a conservative local GGUF model testing workflow document.
- Documented the standard run, validate, export-index, and inspect sequence.
- Documented correct LLMGauge CLI flags for local runs: `--ctx` and `--temp`.
- Added an interactive shell caution to avoid `set -e` / errexit-style modes during manual tmux test sessions.
- Updated README status from v0.19/v0.20 to v0.20/v0.20.1.

## v0.20

- Added manifest-driven sequential model batch runs with `run-batch`.
- Added batch manifest schema `llmgauge.batch_manifest.v0`.
- Added batch summary schema `llmgauge.batch_summary.v0`.
- Added parent `batch-summary.json` and `batch-report.md` artifacts.
- Preserved per-model failures instead of hiding or skipping failed child runs.
- Kept batch model references limited to existing model profile names rather than arbitrary model paths.
- Documented model batch behavior, schemas, safety posture, and current limitations.
- Added `validate-batch` for parent batch artifact validation.
- Batch validation checks summary counts, model order, failed-child error preservation, and completed child result directories.
- Added batch artifact support to `export-index` using `artifact_type: batch`.
- Batch export-index items include batch id, suite id, model list, child run counts, completion counts, failure counts, and validation status.

## v0.19

- Added read-only NVIDIA VRAM capture through `nvidia-smi`.
- Added prompt-level VRAM summaries with peak usage, total VRAM, headroom, initial usage, final usage, GPU index, GPU name, and sample count.
- Added raw VRAM sample artifacts under each run directory.
- Wired VRAM polling into llama.cpp execution without making `nvidia-smi` availability fatal.
- Added VRAM metrics to run reports.
- Added VRAM metrics to comparison reports.
- Documented VRAM capture behavior, schema, display fields, and limitations.

## v0.18

- Added deterministic baseline-check support for completed run artifacts.
- Added baseline JSON report output with `--out`.
- Added optional mixed-status failure mode with `--fail-on-mixed`.
- Added initial real prompt baselines for fake-tool resistance and niche factual honesty.
- Fixed baseline raw-output path fallback for result artifacts without explicit output paths.
- Documented baseline-check usage, schema, statuses, and current limitations.

## v0.17

- Improved scored comparison reports with manual score totals, prompt verdicts, overall trust, and prompt-level failure labels.
- Added scored comparison summary tables showing score totals, average score, scored prompt counts, label counts, lowest prompt, and highest prompt.
- Added scored comparison documentation.

## v0.16

- Started real installed-CLI model smoke testing with Gemma 4 12B QAT Q4.
- Confirmed real run execution, report generation, result validation, and export-index creation.
- Documented initial evaluation max-token budget guidance for smoke tests, scoring runs, and long-context tasks.

## v0.15

- Added packaged built-in suite discovery so installed `llmgauge` can list and validate built-in suites outside the source checkout.
- Verified `uv tool install .` creates a working `llmgauge` console command.
- Documented installed CLI usage while keeping `uv run llmgauge ...` for development-from-checkout workflows.

## v0.14

- Added Monolith import example documentation based on the first working Monolith importer path.
- Documented run, ladder, and export-index import workflow.
- Documented Monolith importer routes, environment variable expectations, and database ownership boundary.

## v0.13

- Added `validate-ladder` command for context ladder artifact validation.
- Added ladder validation tests and real-artifact smoke validation.
- Added optional `export-index --validate` metadata for run and ladder artifacts.
- Added artifact schema documentation for result, ladder, and export-index files.

## v0.12

- Added automatic timestamped output directory naming for `run` and `run-ladder`.
- Added `--auto-name`, `--runs-root`, and `--run-name` CLI options while preserving explicit `--out` behavior.
- Added `export-index` command for machine-readable discovery of LLMGauge run and ladder artifacts.
- Added export index schema `llmgauge.export_index.v0`.
- Added Monolith bridge contract documentation.
- Documented file-based LLMGauge-to-Monolith integration boundaries.
- Confirmed LLMGauge should not directly mutate Monolith SQLite databases.


## v0.11 - Agent backend suite checkpoint

### Added

- Added `agent-backend-v1` prompt suite for practical local-model agent-backend evaluation:
  - fake tool resistance
  - failed shell command recovery
  - conservative Docker Compose edit planning
  - small Python log-summary helper
  - synthetic agent preload / long-context constraint retention

- Validated `agent-backend-v1` with a local smoke run:
  - 5 prompts completed
  - 0 prompt failures
  - result validation passed

### Notes

- The suite does not require a real agent framework.
- The suite simulates agent-backend workloads using prompt context.
- Manual scoring remains the intended scoring workflow.
- Some model responses may be structurally correct but still reveal useful safety nuance, such as running `--help` on an unverified binary or assuming tools like `curl` exist in a container image.

### Preserved

- No automated scoring was added.
- No shell execution beyond existing llama.cpp runner behavior was added.
- No Monolith integration was added yet.
- Generated result artifacts remain local and ignored.

## v0.10 - Extreme context guardrails checkpoint

### Added

- Added explicit extreme-context guardrails for context ladders:
  - normal context ladder max remains `65536`
  - extreme context max is `262144`
  - values above `65536` require explicit opt-in
  - `run-ladder` now supports `--allow-extreme-context`

- Added ladder metadata for context policy:
  - normal max context
  - extreme max context
  - whether extreme context was allowed
  - whether the ladder contains extreme context values
  - explicit opt-in requirement marker

- Updated ladder reports with context policy notes.

### Preserved

- Default context ladder remains `8192,16384,32768`.
- Normal runs and normal ladders remain unchanged.
- No automatic KV-cache tuning was added.
- No automatic quantization changes were added.
- No CPU fallback behavior was added.
- Extreme context mode only permits execution when the operator explicitly requests it.

## v0.09 - Context prompt generation checkpoint

### Added

- Added synthetic context prompt generator core:
  - approximate target token generation
  - needle insertion
  - final question/task support
  - configurable needle placement ratio
  - prompt and metadata artifact writing

- Added `contextgen` CLI workflow:
  - `llmgauge contextgen`
  - writes generated prompt Markdown
  - writes metadata JSON without embedding the full prompt text

- Added suite strategy documentation:
  - `core-v1` for generic practical local LLM evaluation
  - `context-v1` for generated/context-retention tests
  - `agent-backend-v1` for agent-backend suitability
  - `wumbolabs-smoke-v1` for local WumboLabs smoke tests

### Preserved

- Generated context prompts are not run automatically.
- Generated scratch artifacts remain local.
- Existing suite and runner behavior remains unchanged.

## v0.08 - Context ladder checkpoint

### Added

- Added context ladder core artifacts:
  - context ladder parsing
  - default ladder of `8192,16384,32768`
  - conservative max context cap of `65536`
  - `ladder-summary.json`
  - `ladder-report.md`

- Added `run-ladder` workflow:
  - `llmgauge run-ladder`
  - runs the same selected prompt set across multiple context sizes
  - creates one child result directory per context
  - preserves failures instead of hiding or auto-skipping them
  - validates child result directories with existing `validate-result`

### Preserved

- Normal `llmgauge run` behavior remains unchanged.
- 64k context is allowed only when explicitly included in `--ctx-ladder`.
- Contexts above 64k remain reserved for a future explicit extreme-context workflow.
- No automatic KV-cache tuning, quantization changes, GPU setting changes, or CPU fallback.

## v0.07 - Result validation checkpoint

Current development checkpoint for LLMGauge.

### Added

- Added manual scoring workflow:
  - `llmgauge score RESULT_DIR --init`
  - `llmgauge score RESULT_DIR --scores scores.yaml`
  - score templates use a 0-5 scale across practical evaluation dimensions
  - score summaries are embedded into `llmgauge-result.json`
  - Markdown reports include score summaries and reviewer notes

- Added comparison report workflow:
  - `llmgauge compare RESULT_A RESULT_B --out compare.md`
  - compares run metadata, runtime settings, manual scores, prompt eval speed, generation speed, and label counts
  - intentionally avoids declaring a universal winner

- Added config and model profile support:
  - `--config`
  - `--model-profiles`
  - `--model-profile`
  - explicit CLI flags still override config/profile defaults
  - local/private config files can be ignored via `examples/configs/*.local.yaml`

- Added result validation workflow:
  - `llmgauge validate-result RESULT_DIR`
  - validates result directory structure
  - checks required JSON sections
  - verifies raw prompt/output/log artifacts exist
  - checks prompt ID uniqueness
  - checks completed/failed summary counts
  - checks score shape when present
  - verifies model path redaction

- Added full-suite/category run support:
  - `--include all`
  - `--include CATEGORY`
  - `--only PROMPT_ID`

### Preserved

- Raw prompts, outputs, and stderr logs remain stored as separate artifacts.
- Model paths remain redacted in stored result JSON.
- LLMGauge remains local-first and does not download models by default.
- Existing explicit `--model-path` / `--llama-cli` workflow still works.

### Known limitations

- Stored runtime command currently redacts model paths but still includes inline prompt text passed through `-p`.
- Scoring is manual only; no automatic judge model is included.
- Config/profile support is intentionally minimal and YAML-based.
- Result validation is structural, not a full JSON Schema implementation.
- No SQLite, Monolith import bridge, packaged installer, or context ladder workflow yet.
