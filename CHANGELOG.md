# Changelog

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
