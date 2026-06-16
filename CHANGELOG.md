# Changelog

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
