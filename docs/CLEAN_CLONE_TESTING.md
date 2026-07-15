# Clean Clone Testing

This checklist verifies that LLMGauge can be exercised from a fresh clone or
install without relying on private machine state, hidden network behavior, or
accidental local artifacts.

## Purpose

Use this workflow after v0.64 release-prep, before tagging a release, or after
public-facing repo changes. It is a manual audit pass, not an automated CI gate.

A clean clone validates installation and test execution. It does not prove model
quality. Real model testing happens after v0.64 using user-provided `llama.cpp`
and GGUF files.

## What this test verifies

- clone and dependency install steps are documented and reproducible
- `init` creates only the expected user config files
- `setup --scan` is read-only and `setup --non-interactive` can write config/profile
- `doctor` and `smoke` remain inspection-only
- `model add` and `model list` work against isolated user config
- `--dry-run` resolves a run plan without launching `llama.cpp`
- public docs, templates, and ignore rules look safe for external readers
- `uv run pytest` passes in the clone (developer/contributor gate)

## What this test does not verify

- real `llama.cpp` execution
- real GGUF model quality or speed
- GPU driver, CUDA, or VRAM behavior on a specific machine
- scoring accuracy or comparison conclusions
- network-free `git clone` or `uv sync` (those steps require network by design)

## Prerequisites

- Python 3.11 or newer
- `uv`
- `git`
- a fresh clone directory or clean working tree
- no requirement for a real GGUF model file when using placeholder paths

Do not use `set -e` or `set -euo pipefail` in this manual checklist. Run one
phase at a time so you can inspect failures before continuing.

## Isolated user config

Use a dedicated config directory for the whole pass:

```bash
export XDG_CONFIG_HOME="$PWD/tmp/clean-clone-audit/xdg"
mkdir -p "$XDG_CONFIG_HOME"
```

This keeps the test away from your normal `~/.config/llmgauge/` files.

## Working directory and config discovery

Config discovery checks explicit CLI paths first, then project-local
`examples/configs/*.local.yaml` relative to the current working directory, then
the isolated or default user config under `$XDG_CONFIG_HOME/llmgauge/`.

If you run commands from an existing developer checkout at the repo root, any
local `examples/configs/*.local.yaml` files take precedence over the isolated
user config even when `XDG_CONFIG_HOME` is set. That can make `doctor`, `smoke`,
`model list`, and `--dry-run` reflect private contributor state instead of a
fresh external install.

For a faithful clean-clone pass, prefer one of these approaches:

- clone to a fresh directory such as `/tmp/llmgauge-clean-clone` and do not
  create project-local `*.local.yaml` files there
- run from a neutral working directory without project-local overrides
- pass explicit `--config` and `--model-profile-file` paths when you need to
  force the isolated user config

## Source-checkout clean-clone path

```bash
git clone https://github.com/WumboLabs/llmgauge.git /tmp/llmgauge-clean-clone
cd /tmp/llmgauge-clean-clone
uv sync
export XDG_CONFIG_HOME="$PWD/tmp/clean-clone-audit/xdg"
mkdir -p "$XDG_CONFIG_HOME"
uv run llmgauge --version
```

## Editable installed CLI path

From a checkout:

```bash
uv tool install --editable .
llmgauge --version
```

Use the same `XDG_CONFIG_HOME` isolation when testing the installed command.

## GitHub installed CLI path

```bash
uv tool install git+https://github.com/WumboLabs/llmgauge.git@v0.70
llmgauge --version
```

This validates the latest formal release tag (`v0.70`, package/CLI version
`0.70.0`). Reinstall with `--force` only when intentionally retesting that
tag.

## Pre-init doctor and smoke expectations

Before `init`, run:

```bash
uv run llmgauge doctor
uv run llmgauge smoke
```

Expected behavior:

- exit code `0` unless a true `fail` row appears
- `Config` and `Model profiles` rows show `skip`, not `fail`
- next-step guidance mentions `llmgauge setup` or `llmgauge init`
- commands do not launch `llama.cpp`
- commands do not create result artifacts

Placeholder `llama-cli` or model-path warnings are acceptable after `init`.

## Guided setup workflow (preferred)

Read-only scan:

```bash
uv run llmgauge setup --scan
```

Expected behavior:

- exit code `0`
- prints detected `llama-cli` candidates and model directories when present
- does not write config or profile files

Non-interactive setup for audit passes without a real GGUF file:

```bash
mkdir -p tmp/clean-clone-audit
printf '#!/usr/bin/env sh\nprintf "placeholder llama-cli for dry-run only\n"\n' > tmp/clean-clone-audit/llama-cli
chmod +x tmp/clean-clone-audit/llama-cli
touch tmp/clean-clone-audit/placeholder.gguf

uv run llmgauge setup --non-interactive \
  --llama-cli "$PWD/tmp/clean-clone-audit/llama-cli" \
  --model-path "$PWD/tmp/clean-clone-audit/placeholder.gguf" \
  --profile-name clean_clone_model
```

Expected behavior:

- creates or updates `$XDG_CONFIG_HOME/llmgauge/config.yaml` and
  `model-profiles.yaml`
- does not launch `llama.cpp`
- prints next-step guidance for `doctor`, `smoke`, and `run --dry-run`

## Init workflow (manual fallback)

```bash
uv run llmgauge init
```

Expected files created under `$XDG_CONFIG_HOME/llmgauge/`:

- `config.yaml`
- `model-profiles.yaml`

The generated `model-profiles.yaml` already includes example template profiles
such as `example_model`. Do not run `model add example_model` immediately after
`init` unless you intentionally replace that entry with `--force`.

Expected files not created:

- anything under `results/`
- project-local `examples/configs/*.local.yaml` unless you explicitly run
  `init-config`

## Post-init doctor and smoke expectations

```bash
uv run llmgauge doctor
uv run llmgauge smoke
```

Expected behavior:

- config and model profiles rows load from the isolated user config directory
- `llama-cli` and model file rows may remain `warn` when templates still use
  placeholder paths such as `/path/to/llama-cli` or `/path/to/model.gguf`
- `doctor` and `smoke` still do not launch `llama.cpp`

## Model profile add and list workflow

`model add` validates that the model path exists on disk. After `init`, use a
new profile name because `example_model` already exists in the packaged
template. For an audit pass without a real GGUF file, create a scratch
placeholder first:

```bash
mkdir -p tmp/clean-clone-audit
touch tmp/clean-clone-audit/placeholder.gguf
PROFILES="$XDG_CONFIG_HOME/llmgauge/model-profiles.yaml"
CONFIG="$XDG_CONFIG_HOME/llmgauge/config.yaml"
uv run llmgauge model add clean_clone_model \
  --model-profile-file "$PROFILES" \
  --path tmp/clean-clone-audit/placeholder.gguf \
  --label "Clean Clone Model"
uv run llmgauge model list --model-profile-file "$PROFILES"
```

Expected behavior:

- `model add` updates the isolated `model-profiles.yaml` when the path exists
- `model add` exits nonzero with a clear error when the path is missing
- `model add example_model` after `init` exits nonzero unless `--force` is passed
- `model list` shows `clean_clone_model` after a successful add
- `model list` also shows packaged template profiles such as `example_model`
- `doctor` or `smoke` may still report `warn` for scratch placeholder files;
  that is acceptable for this audit pass

## Dry-run workflow

```bash
uv run llmgauge run \
  --suite practical \
  --only honesty-uncertainty/fake-package-currentness \
  --model-profile clean_clone_model \
  --config "$CONFIG" \
  --model-profile-file "$PROFILES" \
  --dry-run
```

Expected behavior:

- command resolves suite, config, profiles, and selected prompt count
- command does not launch `llama.cpp`
- command does not create a result directory under `results/`

`--dry-run` still validates that the resolved model path and `llama-cli` path
exist on disk. If your isolated `config.yaml` still uses `/path/to/llama-cli`,
create scratch placeholders and point both paths at them before dry-run:

```bash
touch tmp/clean-clone-audit/placeholder.gguf
touch tmp/clean-clone-audit/placeholder-llama-cli
chmod +x tmp/clean-clone-audit/placeholder-llama-cli
```

Edit `config.yaml` so `runtime.llama_cli` points at the scratch binary, and
ensure `clean_clone_model.path` exists from the successful `model add` step
above. To use the packaged `example_model` entry instead, edit its `path` in
YAML, run `model update example_model --path ...`, or replace it with
`model add example_model --force`.

If dry-run exits nonzero, record the exact message and compare it against the
public docs rather than treating the failure as hidden.

## Developer gate in a fresh clone

From the clone root:

```bash
uv run pytest
uv run ruff check .
```

Expected behavior:

- all tests pass without real model runs
- ruff reports no issues
- this gate checks code and documented CLI behavior, not answer quality

## Expected files created

- `$XDG_CONFIG_HOME/llmgauge/config.yaml`
- `$XDG_CONFIG_HOME/llmgauge/model-profiles.yaml`
- optional `tmp/clean-clone-audit/` notes or scratch output if you keep audit logs

## Expected files not created

- `results/` run artifacts from dry-run
- network downloads of GGUF models
- telemetry sidecar files
- edits to tracked public templates unless the test intentionally patches them

## Public-safety checks

Before calling the pass complete, search tracked files for private machine
identifiers, personal paths, and old personal contact addresses. Use placeholder
terms in committed docs; run exact private-term searches manually on your
workstation when needed.

Example checks (replace placeholders with terms that would expose private state
on your machine):

```bash
git grep -n "YOUR_HOSTNAME" || true
git grep -n "YOUR_USERNAME" || true
git grep -n "/home/YOUR_USERNAME" || true
git grep -n "/path/to/private/project" || true
git grep -n "/mnt/private-data" || true
git grep -n "old-personal-email@example.com" || true
```

Review sensitive terms carefully:

```bash
git grep -n "api_key" || true
git grep -n "API_KEY" || true
git grep -n "secret" || true
git grep -n "password" || true
git grep -n "token" || true
```

Allowed public identifiers include WumboLabs, WumboCore, and
`contact@wumbocore.com`. Placeholder paths such as `/path/to/model.gguf` are
allowed.

## Cleanup commands

```bash
rm -rf tmp/clean-clone-audit
rm -rf /tmp/llmgauge-clean-clone
uv tool uninstall llmgauge
```

Only delete your normal `~/.config/llmgauge/` files if you intentionally tested
outside the isolated `XDG_CONFIG_HOME` path.

## Pass/fail checklist

- [ ] `uv sync` succeeds in a fresh clone
- [ ] `uv run llmgauge --version` reports the expected release line
- [ ] pre-init `doctor` and `smoke` show skipped config/profile checks, not hidden failures
- [ ] `setup --scan` is read-only and exits 0
- [ ] `setup --non-interactive` writes config/profile without launching a model
- [ ] `init` creates only the expected user config files (manual fallback)
- [ ] `model add` and `model list` work against isolated config
- [ ] `--dry-run` does not launch `llama.cpp` or create result artifacts
- [ ] `uv run pytest` and `uv run ruff check .` pass in the clone
- [ ] README, INSTALL, QUICKSTART, and USAGE agree on first-run order
- [ ] docs reference current `report.md` sections (**Audit Checklist**, **Prompt Artifact Audit**)
- [ ] public templates use neutral example profile names
- [ ] audit searches show no private machine paths or personal email addresses
- [ ] normal LLMGauge commands performed no hidden network activity beyond clone/install steps you ran manually
