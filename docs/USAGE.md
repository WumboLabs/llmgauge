# LLMGauge Usage

See [Installation](INSTALL.md) for source-checkout, editable local install, and GitHub install workflows.

This page is a compact command map for common LLMGauge workflows.

For a first run, start with [Quickstart](QUICKSTART.md). For local model evaluation process guidance, see [Local model testing workflow](LOCAL_MODEL_TESTING.md).

## Command forms

From a repository checkout, use:

    uv run llmgauge ...

After installing the CLI into your environment, use:

    llmgauge ...

Most current examples use the source-checkout form.

## Setup and inspection

Show top-level help:

    uv run llmgauge --help

Create user config files:

    uv run llmgauge init

This writes user config files under `~/.config/llmgauge/`:

    ~/.config/llmgauge/config.yaml
    ~/.config/llmgauge/model-profiles.yaml

`XDG_CONFIG_HOME` is respected. Use `uv run llmgauge init-config` only when you
specifically want project-local ignored files under `examples/configs/`.

Run a safe setup smoke check:

    uv run llmgauge smoke

Check one configured model profile without launching a model:

    uv run llmgauge smoke --model-profile example_model

Check the environment in more detail:

    uv run llmgauge doctor

Check one configured model profile:

    uv run llmgauge doctor --model-profile example_model

List configured model profiles:

    uv run llmgauge model list

`list-model-profiles` remains a compatibility alias for `model list`.

## Model profile management

Manage profiles with the `model` command group:

    uv run llmgauge model list
    uv run llmgauge model add example_model --path /path/to/model.gguf --label "Example Model"
    uv run llmgauge model update example_model --label "Updated Label"
    uv run llmgauge model remove example_model --yes

Pass an explicit profiles YAML path with `--model-profile-file`. The older
`--model-profiles` flag remains supported with identical behavior.

When no path is given, LLMGauge discovers the profiles file in this order:

1. explicit `--model-profile-file` or `--model-profiles`
2. project-local `examples/configs/model-profiles.local.yaml` if present
3. user config `~/.config/llmgauge/model-profiles.yaml` if present

Lifecycle notes:

- `model update` merges only the fields you pass and preserves unknown YAML
  extras on the profile entry.
- `model add --force` replaces the entire profile entry; unknown extras on
  that entry are not preserved.
- `model remove` requires `--yes`.
- Structured CLI writes may not preserve YAML comments.

List built-in suites:

    uv run llmgauge list-suites

Built-in aliases:

    practical -> wumbolabs-practical-v1
    core      -> core-v1
    agent     -> agent-backend-v1
    context   -> context-v1

Aliases are accepted anywhere a built-in suite is resolved. Result artifacts
still record canonical suite IDs.


Validate a suite:

    uv run llmgauge validate-suite practical

## Run planning

Preview one exact prompt without launching `llama.cpp`:

    uv run llmgauge run \
      --suite practical \
      --only honesty-uncertainty/fake-package-currentness \
      --model-profile example_model \
      --ctx 8192 \
      --max-tokens 800 \
      --flash-attn auto \
      --runtime-label stock-reference \
      --dry-run

Preview a category:

    uv run llmgauge run \
      --suite practical \
      --include honesty-uncertainty \
      --model-profile example_model \
      --dry-run

Use `--only <prompt-id>` for one exact prompt. Use `--include <category>` for a category, or `--include all` for a full suite.

## Run execution

Run one exact prompt:

    uv run llmgauge run \
      --suite practical \
      --only honesty-uncertainty/fake-package-currentness \
      --model-profile example_model \
      --ctx 8192 \
      --max-tokens 800 \
      --auto-name \
      --runs-root results \
      --run-name practical-smoke

Run a full suite:

    uv run llmgauge run \
      --suite practical \
      --include all \
      --model-profile example_model \
      --ctx 8192 \
      --max-tokens 1200 \
      --auto-name \
      --runs-root results \
      --run-name practical-full

## Runtime metadata

Record the llama.cpp flash-attention mode:

    --flash-attn auto
    --flash-attn on
    --flash-attn off

Record the run methodology:

    --runtime-label stock-reference
    --runtime-label daily-tuned
    --runtime-label experimental

Runtime labels are manual metadata. They do not change hardware settings.

## Validation

Validate a single run:

    uv run llmgauge validate-result results/<run-directory>

Validate a context ladder:

    uv run llmgauge validate-ladder results/<ladder-directory>

Validate a Fit Ladder artifact:

    uv run llmgauge validate-fit-ladder results/<fit-ladder-directory>

Validate a model batch:

    uv run llmgauge validate-batch results/<batch-directory>

## Scoring

Initialize a manual score file:

    uv run llmgauge score results/<run-directory> --init

Validate scores without applying them:

    uv run llmgauge score \
      results/<run-directory> \
      --scores results/<run-directory>/scores.yaml \
      --check

Apply scores:

    uv run llmgauge score \
      results/<run-directory> \
      --scores results/<run-directory>/scores.yaml

Create a deterministic assisted draft for review:

    uv run llmgauge score results/<run-directory> --auto-draft

Manual scores are review metadata. They are not automatic LLM judgments.

## Compare and export

Compare two or more runs:

    uv run llmgauge compare \
      results/run-a \
      results/run-b \
      --out results/compare.md

Create an export index:

    uv run llmgauge export-index \
      results/<artifact-directory> \
      --validate \
      --out results/llmgauge-index.json

## Context ladders

Preview a context ladder:

    uv run llmgauge run-ladder \
      --suite wumbolabs-practical-v1 \
      --only honesty-uncertainty/fake-package-currentness \
      --model-profile example_model \
      --ctx-ladder 8192,16384,32768 \
      --dry-run

Run a context ladder:

    uv run llmgauge run-ladder \
      --suite wumbolabs-practical-v1 \
      --only honesty-uncertainty/fake-package-currentness \
      --model-profile example_model \
      --ctx-ladder 8192,16384,32768 \
      --max-tokens 800 \
      --out results/example-ladder

## Fit Ladder

Preview adaptive fit attempts:

    uv run llmgauge fit-ladder \
      --suite wumbolabs-practical-v1 \
      --only honesty-uncertainty/fake-package-currentness \
      --model-profile example_model \
      --ctx 65536 \
      --fallback-contexts 32768,16384,8192 \
      --dry-run

Run Fit Ladder:

    uv run llmgauge fit-ladder \
      --suite wumbolabs-practical-v1 \
      --only honesty-uncertainty/fake-package-currentness \
      --model-profile example_model \
      --ctx 65536 \
      --fallback-contexts 32768,16384,8192 \
      --out results/example-fit-ladder

Fit Ladder preserves failed attempts and records the selected working configuration. It does not hide the originally requested configuration.

## Model batches

Run a manifest-driven model batch:

    uv run llmgauge run-batch \
      --manifest tmp/example-batch.yaml \
      --out results/example-batch

Batch manifests reference configured model profile names. They do not accept arbitrary model paths.

See [Model batch runs](MODEL_BATCHES.md).

## Claim boundary

A single run proves only that a model produced output under the recorded settings.

A scored comparison report is evidence for review. It is not a universal leaderboard or model recommendation.
