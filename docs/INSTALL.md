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

First-run setup (guided path):

```bash
uv run llmgauge --version
uv run llmgauge setup
uv run llmgauge doctor
uv run llmgauge smoke
```

`setup` scans for likely `llama-cli` and GGUF paths, writes user config files,
and does not launch a model. Use `llmgauge setup --scan` for a read-only
preview.

Manual fallback:

```bash
uv run llmgauge init
uv run llmgauge model add my_model --path /path/to/model.gguf --label "My Model"
uv run llmgauge model list
```

`init` creates example template profiles such as `example_model` in
`model-profiles.yaml`. Use a new profile name with `model add`, edit the template
paths in YAML, or replace an existing profile intentionally with `--force`.

`model add` requires the model path to exist. Use a real GGUF file or a scratch
placeholder when you only need inspection and dry-run checks.

```bash
uv run llmgauge smoke
uv run llmgauge run \
  --suite practical \
  --only honesty-uncertainty/fake-package-currentness \
  --model-profile my_model \
  --dry-run
```

`doctor`, `smoke`, and `--dry-run` are inspection-only. They do not launch
`llama.cpp` or create result artifacts.

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
llmgauge --version
llmgauge setup
llmgauge doctor
llmgauge model list
llmgauge smoke
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
llmgauge --version
llmgauge setup
llmgauge doctor
llmgauge model list
llmgauge smoke
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

## Installed CLI first-run workflow

After installing the CLI, a typical first run looks like this:

```bash
llmgauge --version
llmgauge setup
llmgauge doctor
llmgauge smoke
llmgauge smoke --model-profile my_model
llmgauge run \
  --suite practical \
  --only honesty-uncertainty/fake-package-currentness \
  --model-profile my_model \
  --dry-run
```

Manual fallback: `llmgauge init` and `llmgauge model add` still work.

`doctor` and `smoke` are inspection-only. They do not launch `llama.cpp` and do
not create result artifacts.

## Configuration discovery

LLMGauge resolves config in this order:

1. explicit CLI paths such as `--config` and `--model-profile-file` (or
   `--model-profiles`)
2. project-local files under `examples/configs/*.local.yaml` relative to the
   current working directory
3. user config under `~/.config/llmgauge/`

`XDG_CONFIG_HOME` is respected. For example, if `XDG_CONFIG_HOME=/tmp/config`,
LLMGauge looks under `/tmp/config/llmgauge/`.

Project-local files are intended for source-checkout contributor workflows. An
installed CLI user running from `$HOME` or another directory will normally see
only user-level config unless explicit CLI paths are passed.

For normal installed use, prefer:

```bash
llmgauge setup
```

Manual fallback:

```bash
llmgauge init
```

For source-checkout contributor workflows that need repo-local ignored config
files, compatibility remains available:

```bash
uv run llmgauge init-config
```

## Safe readiness checks

Use `doctor` for a broader environment table and `smoke` for a shorter readiness
check before launching a model:

```bash
llmgauge doctor
llmgauge smoke
llmgauge smoke --model-profile my_model
```

Status meanings in `doctor` and `smoke` output:

- `ok` — check completed successfully
- `skip` — check was intentionally skipped because config or profiles were not
  found
- `warn` — optional or incomplete setup, such as missing `nvidia-smi` or
  placeholder paths
- `fail` — blocking problem; `doctor` and `smoke` exit nonzero

When config or profiles are missing, the commands print next-step guidance
rather than treating skipped checks as hard failures.

Smoke checks verify the package, built-in suites, config discovery, model profile
discovery, `llama-cli`, optional `nvidia-smi`, and an optional selected model
profile. They do not launch `llama.cpp` and do not create result artifacts.

Before a real run, preview the resolved plan:

```bash
llmgauge run \
  --suite practical \
  --only honesty-uncertainty/fake-package-currentness \
  --model-profile my_model \
  --dry-run
```

For a full fresh-clone audit pass, see [Clean clone testing](CLEAN_CLONE_TESTING.md).
That checklist includes `uv run pytest` as a developer gate. Clean-clone testing
validates installation and CLI readiness, not model quality. Real model testing
uses user-provided `llama.cpp` and GGUF files after release hardening.
