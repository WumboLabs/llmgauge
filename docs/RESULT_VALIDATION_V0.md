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


## Compatibility expectations

Validation must remain additive for the v0.x result schema line. Missing
optional provenance, identity, fingerprint, runtime-command, or future public
export fields must not invalidate an older result directory that otherwise
passes structural validation.

Unknown optional fields are tolerated where the containing object is already a
free-form artifact object. This preserves forward compatibility for importers
and avoids forcing migrations for older local evidence.

Validation may add warnings or more specific diagnostics, but it should not make
previously valid v0.x artifacts fail unless the artifact is corrupted, unsafe to
interpret, or technically impossible to interpret.

Reasoning-mode metadata is compatibility-sensitive:

- v0.66 artifacts may contain `runtime.reasoning_mode`
- future artifacts may add `runtime.reasoning_mode_requested`
- older artifacts may omit both
- readers must not treat requested reasoning mode as observed or effective
  behavior

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
