# Changelog

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
