# Model Batch Runs

Model batch runs execute the same selected prompt set sequentially across explicit model profiles.

They are intended for conservative local comparison workflows such as:

- fake-tool honesty smoke tests across candidate models
- short agent-backend checks across several 12GB-friendly profiles
- repeatable pre-scoring runs before manual review
- controlled comparison inputs for later reporting or Monolith import planning

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
- no Monolith SQLite writes

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

Each completed child run is a normal LLMGauge result directory and can be validated with:

    uv run llmgauge validate-result results/gemma4-agent-smoke/model-01-gemma4-12b-qat-q4

There is no dedicated `validate-batch` command yet.

## Export index status

Initial model batch support does not add export-index support.

For now, export individual completed child run directories when a machine-readable index is needed. Batch-level export-index support can be added later after the batch artifact shape has settled.

## Current limitations

- No parallel execution.
- No retry logic.
- No per-model override fields in the manifest.
- No dedicated `validate-batch` command.
- No batch-level export-index support yet.
- No automatic comparison report generation from a batch.
- No automatic scoring.
