# Result Validation v0

`llmgauge validate-result` performs structural validation on a LLMGauge result directory.

## Command

    uv run llmgauge validate-result results/example-run

## Checks

- `llmgauge-result.json` exists and parses as JSON.
- Required top-level sections exist:
  - `schema_version`
  - `llmgauge_version`
  - `run`
  - `model`
  - `runtime`
  - `suite`
  - `summary`
  - `results`
- `results` is a list.
- Each prompt result includes required fields:
  - `prompt_id`
  - `category`
  - `status`
  - `raw_prompt_path`
  - `raw_output_path`
  - `stderr_log_path`
  - `exit_status`
  - `metrics`
- Raw prompt, raw output, and stderr log artifacts exist.
- Prompt IDs are unique.
- `summary.completed` and `summary.failed` match prompt result statuses.
- `score` is either null or a mapping with valid list fields.
- `model.model_path` remains redacted.

## Non-goals

- Full JSON Schema validation.
- Repairing malformed result directories.
- Scoring output quality.
- Validating model factual correctness.
- Validating Monolith import compatibility.
