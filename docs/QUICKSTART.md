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

## 2. Create local config files

Create ignored local config files from the example templates:

    uv run llmgauge init-config

This creates, or skips if already present:

    examples/configs/llmgauge.local.yaml
    examples/configs/model-profiles.local.yaml

Local config files matching `examples/configs/*.local.yaml` are ignored by git and should contain your machine-specific paths.

## 3. Edit local config

Edit `examples/configs/llmgauge.local.yaml` and set your llama.cpp path:

    runtime:
      llama_cli: /path/to/llama-cli

Edit `examples/configs/model-profiles.local.yaml` and set at least one model profile path:

    models:
      example_model:
        label: Example Model
        path: /path/to/model.gguf

## 4. Check the environment

Run:

    uv run llmgauge doctor

When local config files are present, `doctor` auto-detects them.

A ready setup should show:

- config loaded
- `llama-cli` exists and is executable
- model profiles loaded
- optional `nvidia-smi` status

To check a specific profile:

    uv run llmgauge doctor --model-profile example_model

## 5. List model profiles

Inspect configured model profiles and model path status:

    uv run llmgauge list-model-profiles

Useful path statuses include:

    ok
    missing-file
    missing-path

Fix any missing model path before running model evaluations.

## 6. List and validate suites

List built-in suites:

    uv run llmgauge list-suites

Validate a suite:

    uv run llmgauge validate-suite core-v1

## 7. Preview one prompt

Before launching llama.cpp, inspect the resolved run plan:

    uv run llmgauge run \
      --suite core-v1 \
      --include honesty \
      --model-profile example_model \
      --ctx 8192 \
      --max-tokens 800 \
      --temp 0.2 \
      --dry-run

Dry-run mode resolves config, model profiles, model paths, runtime settings, and selected prompt count. It does not launch llama.cpp and does not create a result directory.

## 8. Run one prompt

Start with one prompt before running a full suite.

When `examples/configs/llmgauge.local.yaml` and `examples/configs/model-profiles.local.yaml` exist, LLMGauge auto-detects them. Explicit `--config` and `--model-profiles` still override the defaults.

    uv run llmgauge run \
      --suite core-v1 \
      --include honesty \
      --model-profile example_model \
      --ctx 8192 \
      --max-tokens 800 \
      --temp 0.2 \
      --auto-name \
      --runs-root results \
      --run-name quickstart-honesty

## 9. Validate the result

After the run completes, validate the generated result directory:

    uv run llmgauge validate-result results/<generated-run-directory>

Inspect:

    report.md
    llmgauge-result.json
    cleaned/
    raw/
    logs/

Raw model outputs are preserved for audit. Cleaned outputs are derived review artifacts.

## 10. Optional manual scoring

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

## 11. Export an index

Create a machine-readable index for reports, comparisons, or import workflows:

    uv run llmgauge export-index \
      results/<generated-run-directory> \
      --validate \
      --out results/quickstart-index.json

## Claim boundary

A single quickstart run proves only that your local setup can execute and produce artifacts. It is not a model recommendation, ranking, or daily-driver evaluation.
