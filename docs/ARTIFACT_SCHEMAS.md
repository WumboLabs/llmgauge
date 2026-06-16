# LLMGauge Artifact Schemas

This document describes the current LLMGauge artifact schemas intended for validation, import, and review.

These schemas are intentionally conservative and file-based. They are not database schemas.

## Design rules

- Artifacts should be readable without Monolith.
- Monolith may import artifacts, but LLMGauge does not write to Monolith databases.
- Raw prompt, output, and log files remain audit evidence.
- JSON schemas should evolve additively where possible.
- Importers should check `schema_version` before trusting a file.
- Relative artifact paths inside result JSON are relative to the result directory.
- Absolute local model paths should not be exposed in public result metadata.

## Single run directory

A normal run directory contains:

    llmgauge-result.json
    report.md
    raw/
    logs/

Required machine-readable file:

    llmgauge-result.json

Human-readable file:

    report.md

Audit artifact directories:

    raw/
    logs/

## Schema: llmgauge.result.v0

Primary file:

    llmgauge-result.json

Top-level required keys:

    schema_version
    llmgauge_version
    run
    model
    runtime
    suite
    results
    summary

Expected `schema_version`:

    llmgauge.result.v0

### run

Required or expected fields:

    run_id
    timestamp_utc
    status
    result_dir

Expected `status` values:

    completed
    failed

Notes:

- `run_id` currently follows the output directory name.
- `timestamp_utc` should be ISO-like UTC text.
- `result_dir` is informational and may be local-machine specific.

### model

Expected fields:

    model_id
    model_profile
    label
    family
    role
    quant
    model_path
    model_path_policy

Privacy policy:

- `model_path` should be `redacted`.
- `model_path_policy` should describe redaction.
- Importers should not require the original local GGUF path.

### runtime

Expected fields:

    backend
    llama_cli
    ctx_size
    max_tokens
    temperature
    top_p
    batch_size
    ubatch_size
    gpu_layers
    command
    config_path
    model_profiles_path

Notes:

- `backend` is currently `llama.cpp`.
- `command` should redact the model path.
- `config_path` and `model_profiles_path` may be local-machine specific.
- Future hardening may add stronger path redaction for public exports.

### suite

Expected fields:

    suite_id
    suite_version
    suite_path
    prompt_count
    include
    only

Notes:

- `suite_path` may be local-machine specific.
- `include` records the selected category or `all`.
- `only` records a single prompt id when used.

### results

`results` is a list of prompt result objects.

Expected prompt result fields:

    prompt_id
    title
    category
    status
    raw_prompt_path
    raw_output_path
    stderr_log_path
    metrics
    score
    failure_labels
    notes
    exit_status
    error

Expected `status` values:

    completed
    failed

Path policy:

- `raw_prompt_path`, `raw_output_path`, and `stderr_log_path` are relative to the result directory.
- Importers should resolve these paths from the containing result directory.

### summary

Expected fields:

    completed
    failed
    manual_score_total
    manual_score_max
    failure_labels

Notes:

- `completed` and `failed` should match prompt result statuses.
- Manual score fields may be null until scoring is applied.

## Context ladder directory

A context ladder directory contains:

    ladder-summary.json
    ladder-report.md
    ctx-8192/
    ctx-16384/
    ctx-32768/

Each `ctx-*` child directory should be a normal single run directory with its own `llmgauge-result.json`.

Required machine-readable file:

    ladder-summary.json

Human-readable file:

    ladder-report.md

## Schema: llmgauge.context_ladder.v0

Primary file:

    ladder-summary.json

Top-level expected keys:

    schema_version
    ladder_id
    suite_id
    model_id
    include
    only
    contexts
    child_runs
    summary
    max_context_policy

Expected `schema_version`:

    llmgauge.context_ladder.v0

### contexts

`contexts` is an ordered list of context sizes.

Example:

    [8192, 16384, 32768]

The order should match `child_runs[*].ctx_size`.

### child_runs

`child_runs` is an ordered list of child result summaries.

Expected fields:

    ctx_size
    status
    result_dir
    completed
    failed
    error

Expected `status` values:

    completed
    failed

Rules:

- Completed child runs should point to valid single run directories.
- Failed child runs should preserve error text.
- `result_dir` may be local-machine specific.
- Importers should preserve source path and validation status.

### summary

Expected fields:

    total
    completed
    failed

Rules:

- `total` should equal the number of child runs.
- `completed` should equal the number of completed child runs.
- `failed` should equal the number of failed child runs.

### max_context_policy

Expected fields:

    normal_max_context
    extreme_max_context
    allow_extreme_context
    has_extreme_context
    requires_explicit_opt_in_above_normal_max

Current defaults:

    normal_max_context: 65536
    extreme_max_context: 262144

Purpose:

- Preserve whether a run used normal bounded context behavior.
- Preserve whether explicit extreme-context opt-in was used.
- Help importers and reviewers distinguish ordinary 64k-and-under ladders from extreme context experiments.

## Export index

An export index is a discovery artifact, not a source-of-truth result.

Primary file convention:

    llmgauge-index.json

## Schema: llmgauge.export_index.v0

Top-level expected keys:

    schema_version
    generated_at_utc
    item_count
    validation_checked
    items

Expected `schema_version`:

    llmgauge.export_index.v0

### validation_checked

Boolean.

If false, indexed artifacts were classified but not validated.

If true, each item should include a `validation` object.

### items

`items` is a list of indexed artifacts.

Supported `artifact_type` values:

    run
    ladder

## Export index item: run

Expected fields:

    artifact_type
    path
    schema_version
    result_json
    report
    run_id
    status
    timestamp_utc
    suite_id
    suite_version
    model_id
    model_profile
    prompt_count
    completed
    failed
    manual_score_total
    manual_score_max
    has_raw_artifacts
    has_logs
    validation

`validation` appears only when export-index is run with validation enabled.

## Export index item: ladder

Expected fields:

    artifact_type
    path
    schema_version
    ladder_summary
    ladder_report
    ladder_id
    suite_id
    model_id
    include
    only
    contexts
    child_run_count
    completed
    failed
    total
    has_child_runs
    validation

`validation` appears only when export-index is run with validation enabled.

## Validation payload

When present, validation payloads use:

    checked
    status
    errors

Expected values:

    checked: true
    status: valid | invalid
    errors: list of strings

Example:

    {
      "checked": true,
      "status": "valid",
      "errors": []
    }

## Current validation commands

Validate a run directory:

    uv run llmgauge validate-result <result-dir>

Validate a ladder directory:

    uv run llmgauge validate-ladder <ladder-dir>

Create an index without validation:

    uv run llmgauge export-index <artifact-dir> --out results/llmgauge-index.json

Create an index with validation metadata:

    uv run llmgauge export-index <artifact-dir> --validate --out results/llmgauge-index.json

## Monolith import guidance

Monolith should treat LLMGauge artifacts as external source files.

Recommended import behavior:

1. Accept a result directory, ladder directory, or export index.
2. Check `schema_version`.
3. Run validation where practical.
4. Store import timestamp, source path, schema version, artifact type, and validation status.
5. Store summary metadata in Monolith's database.
6. Link back to raw artifacts rather than copying them by default.
7. Keep old Quant Lab/core-v2/Hermes records readable.

Monolith should not assume that LLMGauge artifacts are stored inside the Monolith repository or data directory.

## Compatibility notes

Existing schema versions are still v0-style schemas. They are stable enough for private Monolith import work, but not final public API commitments.

Known schemas:

    llmgauge.result.v0
    llmgauge.context_ladder.v0
    llmgauge.context_prompt.v0
    llmgauge.suite.v0
    llmgauge.export_index.v0

Future changes should prefer additive fields over breaking changes.
