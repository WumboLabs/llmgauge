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
- If `cleaned_output_path` is present, the cleaned output artifact exists.
- Prompt IDs are unique.
- `summary.completed` and `summary.failed` match prompt result statuses.
- `score` is either null or a mapping with valid dimensions, label lists, and string metadata fields.
- `model.model_path` remains redacted.

## Non-goals

- Full JSON Schema validation.
- Repairing malformed result directories.
- Scoring output quality.
- Validating model factual correctness.
- Validating compatibility with any specific downstream importer.
- Proving publication readiness or bounded public-claim eligibility.

Passing `validate-result` means artifact integrity and on-disk references look
consistent. Review `report.md` **Audit Checklist** and **Prompt Artifact Audit**
sections, then inspect raw and cleaned outputs before citing claims publicly.


## Score validation details

When an applied prompt `score` object is present, result validation checks:

- `dimensions` is an object when present.
- `failure_labels` and `good_labels` are lists.
- `schema_version`, `scale`, `rubric_id`, `rubric_version`, `reviewer_notes`, `score_rationale`, and `verdict` are strings when present and non-null.

Detailed score template validation is handled by `llmgauge score` before scores are
applied.
