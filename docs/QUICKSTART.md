# LLMGauge Quickstart

This guide gets a new local user from a fresh checkout to a validated single-prompt run.

LLMGauge does not download models, install GPU drivers, modify CUDA, change system packages, or tune hardware settings. You provide an existing GGUF model and a working llama.cpp `llama-cli`.

## 1. Install from a checkout

From the repository root:

    uv sync
    uv run llmgauge --help

Optional installed CLI usage:

    uv tool install .
    llmgauge --help

## 2. Check the base environment

Run:

    uv run llmgauge doctor

This should confirm that the package imports, the runner module is available, and built-in suites can be found.

Warnings about missing config or model profiles are expected before you create local config files.

## 3. Create local config files

Copy the examples:

    cp examples/configs/llmgauge.example.yaml examples/configs/llmgauge.local.yaml
    cp examples/configs/model-profiles.example.yaml examples/configs/model-profiles.local.yaml

Local config files matching `examples/configs/*.local.yaml` are ignored by git and should contain your machine-specific paths.

Edit `examples/configs/llmgauge.local.yaml`:

    runtime:
      llama_cli: /path/to/llama-cli

Edit `examples/configs/model-profiles.local.yaml` and set at least one model profile path:

    models:
      gemma4_12b_it_qat_ud_q4_k_xl:
        path: /path/to/model.gguf

## 4. Check the configured environment

Run doctor with your config and selected model profile:

    uv run llmgauge doctor \
      --config examples/configs/llmgauge.local.yaml \
      --model-profiles examples/configs/model-profiles.local.yaml \
      --model-profile gemma4_12b_it_qat_ud_q4_k_xl

A ready setup should show:

- config loaded
- `llama-cli` exists and is executable
- model profiles loaded
- selected model profile resolved
- model file exists
- optional `nvidia-smi` status

## 5. List and validate suites

List built-in suites:

    uv run llmgauge list-suites

Validate a suite:

    uv run llmgauge validate-suite core-v1

## 6. Run one prompt

Start with one prompt before running a full suite:

    uv run llmgauge run \
      --suite core-v1 \
      --include honesty \
      --model-profile gemma4_12b_it_qat_ud_q4_k_xl \
      --config examples/configs/llmgauge.local.yaml \
      --model-profiles examples/configs/model-profiles.local.yaml \
      --ctx 8192 \
      --max-tokens 800 \
      --temp 0.2 \
      --auto-name \
      --runs-root results \
      --run-name quickstart-honesty

## 7. Validate the result

After the run completes, validate the generated result directory:

    uv run llmgauge validate-result results/<generated-run-directory>

Inspect:

    report.md
    llmgauge-result.json
    cleaned/
    raw/
    logs/

Raw model outputs are preserved for audit. Cleaned outputs are derived review artifacts.

## 8. Optional manual scoring

Initialize a score file:

    uv run llmgauge score results/<generated-run-directory> --init

Edit:

    results/<generated-run-directory>/scores.yaml

Validate without mutating artifacts:

    uv run llmgauge score \
      results/<generated-run-directory> \
      --scores results/<generated-run-directory>/scores.yaml \
      --check

Apply scores:

    uv run llmgauge score \
      results/<generated-run-directory> \
      --scores results/<generated-run-directory>/scores.yaml

Validate again:

    uv run llmgauge validate-result results/<generated-run-directory>

## 9. Export an index

Create a machine-readable index for reports, comparisons, or import workflows:

    uv run llmgauge export-index \
      results/<generated-run-directory> \
      --validate \
      --out results/quickstart-index.json

## Claim boundary

A single quickstart run proves only that your local setup can execute and produce artifacts. It is not a model recommendation, ranking, or daily-driver evaluation.
