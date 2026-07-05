# Model Batch Runs

Model batch runs execute the same selected prompt set sequentially across explicit model profiles.

They are intended for conservative local comparison workflows such as:

- fake-tool honesty smoke tests across candidate models
- short agent-backend checks across several 12GB-friendly profiles
- repeatable pre-scoring runs before manual review
- controlled comparison inputs for later reporting or downstream import planning

Model batch runs are intentionally not a scheduler, not a parallel executor, and not a model downloader.

## Safety and scope

Model batch manifests reference existing model profile names only.

They do not accept arbitrary GGUF model paths. The model paths still come from the operator-controlled model profiles YAML passed through `--model-profiles`.

Current behavior:

- sequential execution only
- one normal LLMGauge child run directory per model profile
- raw prompts, raw outputs, stderr logs, reports, metrics, and VRAM artifacts preserved in each child run
- parent `batch-summary.json`
- parent `batch-report.md`
- per-model failures preserved instead of hidden or skipped
- no automatic model downloads
- no GPU, driver, CUDA, kernel, firewall, or package mutation
- no writes to external application databases

## Manifest schema

Current manifest schema:

    llmgauge.batch_manifest.v0

Minimal example:

    schema_version: llmgauge.batch_manifest.v0
    batch_id: gemma4-agent-smoke
    suite: agent-backend-v1
    only: tool-honesty/fake-tool-resistance
    include: all
    max_tokens: 300
    models:
      - gemma4_12b_qat_q4
      - gemma4_12b_q5

Fields:

- `schema_version`: required; must be `llmgauge.batch_manifest.v0`
- `batch_id`: optional non-empty string; defaults to the manifest file stem
- `suite`: required suite ID or suite path
- `only`: optional prompt ID
- `include`: optional prompt category or `all`; defaults to `all`
- `max_tokens`: optional positive integer override for every child run
- `models`: required non-empty list of model profile names

Rules:

- `models` entries must be non-empty strings.
- Duplicate model profile names are rejected.
- Model profile names must resolve through the provided `--model-profiles` file.
- Missing model files are recorded as child failures in the batch summary/report.

## Run a batch

Example from the repository checkout:

    uv run llmgauge run-batch \
      --manifest tmp/gemma4-agent-smoke.yaml \
      --config examples/configs/llmgauge.local.yaml \
      --model-profiles examples/configs/model-profiles.local.yaml \
      --out results/gemma4-agent-smoke

The `--config` and `--model-profiles` arguments are required for `run-batch` so the model resolution path is explicit.

## Output layout

A successful batch directory has this shape:

    results/gemma4-agent-smoke/
      batch-summary.json
      batch-report.md
      model-01-gemma4-12b-qat-q4/
        llmgauge-result.json
        report.md
        raw/
        logs/
        vram/
      model-02-gemma4-12b-q5/
        llmgauge-result.json
        report.md
        raw/
        logs/
        vram/

If a model profile fails before a child run can be written, the parent batch artifacts still record the attempted child directory and error text.

## Summary schema

Current summary schema:

    llmgauge.batch_summary.v0

Primary file:

    batch-summary.json

Expected top-level keys:

    schema_version
    batch_id
    manifest_path
    suite_id
    suite_path
    include
    only
    max_tokens
    models
    execution
    summary
    child_runs

`execution` records:

    mode
    model_reference_policy
    parallelism

Current fixed values:

    mode: sequential
    model_reference_policy: manifest model entries are model profile names only
    parallelism: disabled

`summary` records:

    completed
    failed
    total

`child_runs` is an ordered list matching the manifest model order.

Expected child fields:

    model_profile
    model_id
    status
    result_dir
    completed
    failed
    error

Supported child status values:

    completed
    failed

## Validation

Validate the parent batch directory with:

    uv run llmgauge validate-batch results/gemma4-agent-smoke

`validate-batch` checks the parent `batch-summary.json`, verifies summary counts, verifies child run statuses, confirms failed children preserve error text, and validates each completed child run with the normal result validator.

Each completed child run is still a normal LLMGauge result directory and can also be validated directly with:

    uv run llmgauge validate-result results/gemma4-agent-smoke/model-01-gemma4-12b-qat-q4

## Export index status

Model batch directories can be included in an export index:

    uv run llmgauge export-index \
      results/gemma4-agent-smoke \
      --validate \
      --out results/gemma4-agent-smoke-index.json

Batch export-index items use `artifact_type: "batch"` and include batch-level metadata such as batch id, suite id, model list, child run count, completed count, failed count, and validation status when `--validate` is used.

Batch export-index support does not automatically expand or duplicate every child run. Pass child run directories explicitly when child-level run items are also needed.

## Current limitations

- No parallel execution.
- No retry logic.
- No per-model override fields in the manifest.
- No automatic comparison report generation from a batch.
- No automatic scoring.
