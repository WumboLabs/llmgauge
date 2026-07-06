# LLMGauge Quickstart

This guide gets a new local user from a fresh checkout to a validated single-prompt run.

For a compact command reference, see [Usage](USAGE.md).

LLMGauge is local-first. It does not download models, install GPU drivers, modify CUDA, change system packages, tune hardware settings, or submit results to a service. You provide an existing GGUF model and a working `llama.cpp` `llama-cli`.

## Command forms

From a cloned repository checkout, use:

    uv run llmgauge ...

After installing the CLI into your environment, use:

    llmgauge ...

The current recommended path for early users and contributors is the source-checkout workflow with `uv run llmgauge ...`.

## 1. Install from a checkout

From the repository root:

    uv sync
    uv run llmgauge --help

Optional local installed CLI usage:

    uv tool install .

Then:

    llmgauge --help

Installed CLI behavior is still being clarified. The rest of this guide uses `uv run llmgauge ...`.

## 2. Create user config files

Create user config files from the example templates:

    uv run llmgauge init

This creates, or skips if already present:

    ~/.config/llmgauge/config.yaml
    ~/.config/llmgauge/model-profiles.yaml

`XDG_CONFIG_HOME` is respected. For example, with `XDG_CONFIG_HOME=/tmp/config`,
LLMGauge uses `/tmp/config/llmgauge/`.

Compatibility note: `uv run llmgauge init-config` still creates project-local
ignored files under `examples/configs/` for contributor workflows:

    examples/configs/llmgauge.local.yaml
    examples/configs/model-profiles.local.yaml

## 3. Edit user config

Edit `~/.config/llmgauge/config.yaml` and set your `llama-cli` path:

    runtime:
      llama_cli: /path/to/llama-cli

Optional defaults can also live here:

    defaults:
      ctx_size: 8192
      max_tokens: 800
      temperature: 0.2
      flash_attn: auto
      runtime_label: stock-reference

Edit `~/.config/llmgauge/model-profiles.yaml` and set at least one model profile path:

    models:
      example_model:
        label: Example Model
        family: Example
        quant: Q4_K_M
        path: /path/to/model.gguf

Optional per-model runtime metadata can also live in the profile:

    models:
      example_model:
        label: Example Model
        family: Example
        quant: Q4_K_M
        path: /path/to/model.gguf
        flash_attn: on
        runtime_label: daily-tuned

## 4. Check the environment

Run:

    uv run llmgauge doctor

When config files are present, `doctor` auto-detects them.

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

    uv run llmgauge validate-suite wumbolabs-practical-v1

## 7. Preview one prompt

Before launching `llama.cpp`, inspect the resolved run plan:

    uv run llmgauge run \
      --suite wumbolabs-practical-v1 \
      --only honesty-uncertainty/fake-package-currentness \
      --model-profile example_model \
      --ctx 8192 \
      --max-tokens 800 \
      --temp 0.2 \
      --flash-attn auto \
      --runtime-label stock-reference \
      --dry-run

Dry-run mode resolves config, model profiles, model paths, runtime settings, and selected prompt count. It does not launch `llama.cpp` and does not create a result directory.

## 8. Run one prompt

Start with one prompt before running a full suite.

LLMGauge auto-detects configuration in this order:

1. explicit `--config` / `--model-profiles` paths
2. project-local `examples/configs/*.local.yaml`
3. user config under `~/.config/llmgauge/`

Project-local files take precedence over user config so source-checkout
experiments can override installed/user defaults without changing global
settings.

    uv run llmgauge run \
      --suite wumbolabs-practical-v1 \
      --only honesty-uncertainty/fake-package-currentness \
      --model-profile example_model \
      --ctx 8192 \
      --max-tokens 800 \
      --temp 0.2 \
      --flash-attn auto \
      --runtime-label stock-reference \
      --auto-name \
      --runs-root results \
      --run-name quickstart-smoke

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

## 12. Compare runs

After you have two or more result directories, create a comparison report:

    uv run llmgauge compare \
      results/run-a \
      results/run-b \
      --out results/compare.md

Comparison reports summarize runtime settings, score totals, prompt verdicts, speed metrics, VRAM metrics, and label counts. They do not declare a universal winner.

## Runtime metadata notes

Use `--flash-attn` to record and pass the llama.cpp flash-attention mode:

    --flash-attn auto
    --flash-attn on
    --flash-attn off

Use `--runtime-label` to identify the methodology behind a run:

    --runtime-label stock-reference
    --runtime-label daily-tuned
    --runtime-label experimental

These labels are manual metadata. They do not change hardware settings. They help prevent mixing stock/reference runs with daily-tuned or experimental runs without noticing.

## Claim boundary

A single quickstart run proves only that your local setup can execute and produce artifacts. It is not a model recommendation, ranking, or daily-driver evaluation.
