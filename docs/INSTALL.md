# Installation

LLMGauge can be used two ways:

1. source checkout, recommended for contributors and early testers
2. installed CLI, recommended when you want to run `llmgauge ...` directly

LLMGauge does not download models, install GPU drivers, modify CUDA, change
system packages, tune hardware settings, or submit results to a service. You
provide an existing GGUF model and a working `llama.cpp` `llama-cli`.

## Requirements

- Python 3.11 or newer
- `uv`
- an existing `llama.cpp` `llama-cli` binary for real model runs
- an existing local GGUF model for real model runs

`llmgauge smoke`, `llmgauge list-suites`, and `llmgauge run --dry-run` are safe
to run before you have a working model configured.

## Source checkout

Use this path when developing LLMGauge or testing from a cloned repository.

```bash
git clone https://github.com/WumboLabs/llmgauge.git
cd llmgauge
uv run llmgauge --help
```

First-run setup:

```bash
uv run llmgauge init
uv run llmgauge smoke
uv run llmgauge list-suites
uv run llmgauge run \
  --suite practical \
  --only honesty-uncertainty/fake-package-currentness \
  --model-profile example_model \
  --dry-run
```

The source-checkout form is:

```bash
uv run llmgauge ...
```

## Installed CLI from a local checkout

Use this path when you want the `llmgauge` command available directly from your
shell while still working from a local checkout.

```bash
git clone https://github.com/WumboLabs/llmgauge.git
cd llmgauge
uv tool install --editable .
```

Then run:

```bash
llmgauge --help
llmgauge init
llmgauge smoke
llmgauge list-suites
```

Editable installs are useful during local development because command changes
track the checkout.

Update an editable install by pulling the checkout:

```bash
git pull --ff-only
```

Remove the installed command when you no longer need it:

```bash
uv tool uninstall llmgauge
```

## Installed CLI from GitHub

Use this path when you want to install from the GitHub repository without
manually working inside a checkout.

```bash
uv tool install git+https://github.com/WumboLabs/llmgauge
```

Then run:

```bash
llmgauge --help
llmgauge init
llmgauge smoke
llmgauge list-suites
```

Update a GitHub install by reinstalling the tool:

```bash
uv tool install --force git+https://github.com/WumboLabs/llmgauge
```

Remove the installed command when you no longer need it:

```bash
uv tool uninstall llmgauge
```

## What installation does not do

Installing LLMGauge only installs the Python CLI and its Python dependencies.

It does not:

- install or build `llama.cpp`
- download GGUF models
- install GPU drivers, CUDA, ROCm, or other accelerator runtimes
- modify system packages, kernel settings, firewall rules, clocks, or power limits
- create result directories until you run an evaluation command
- upload prompts, outputs, results, or hardware details to a service

## Configuration discovery

LLMGauge resolves config in this order:

1. explicit CLI paths such as `--config` and `--model-profiles`
2. project-local files under `examples/configs/*.local.yaml`
3. user config under `~/.config/llmgauge/`

`XDG_CONFIG_HOME` is respected. For example, if `XDG_CONFIG_HOME=/tmp/config`,
LLMGauge looks under `/tmp/config/llmgauge/`.

For normal installed use, prefer:

```bash
llmgauge init
```

For source-checkout contributor workflows that need repo-local ignored config
files, compatibility remains available:

```bash
uv run llmgauge init-config
```

## Safe readiness checks

Use `smoke` before launching a model:

```bash
llmgauge smoke
llmgauge smoke --model-profile example_model
```

Smoke checks verify the package, built-in suites, config discovery, model profile
discovery, `llama-cli`, optional `nvidia-smi`, and an optional selected model
profile. They do not launch `llama.cpp` and do not create result artifacts.

Before a real run, preview the resolved plan:

```bash
llmgauge run \
  --suite practical \
  --only honesty-uncertainty/fake-package-currentness \
  --model-profile example_model \
  --dry-run
```
