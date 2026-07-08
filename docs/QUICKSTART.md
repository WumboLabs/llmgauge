# LLMGauge Quickstart

This guide gets a new local user from a fresh checkout to a validated single-prompt run.

For a compact command reference, see [Usage](USAGE.md).

LLMGauge is local-first. It does not download models, install GPU drivers, modify CUDA, change system packages, tune hardware settings, or submit results to a service. You provide an existing GGUF model and a working `llama.cpp` `llama-cli`.

## Command forms

From a cloned repository checkout, use:

    uv run llmgauge ...

After installing the CLI into your environment, use:

    llmgauge ...

The current recommended path for early users and contributors is the source-checkout workflow with `uv run llmgauge ...`. See [Installation](INSTALL.md) for source-checkout, editable local install, and GitHub install workflows.

## 1. Install from a checkout

From the repository root:

    uv sync
    uv run llmgauge --help

Optional local installed CLI usage:

    uv tool install .

Then:

    llmgauge --help

The rest of this guide uses `uv run llmgauge ...`. Installed CLI users can drop `uv run` after installing the command.

## Installed CLI quick path

If you installed `llmgauge` into your environment, the same workflow applies with
the installed command form:

    llmgauge --version
    llmgauge setup
    llmgauge doctor
    llmgauge smoke
    llmgauge run --suite practical --only honesty-uncertainty/fake-package-currentness --model-profile my_model --dry-run

`setup` is the preferred first-run path. It scans for likely `llama-cli` and GGUF
paths and writes user config files without launching a model.

Manual fallback: `init` creates example template profiles such as `example_model`
in `model-profiles.yaml`. Use a new profile name with `model add`, edit the
template paths in YAML, or replace an existing profile intentionally with
`--force`.

The model path must exist on disk. Use a real GGUF file or a scratch placeholder
for inspection-only dry-run testing.

Installed users normally rely on `~/.config/llmgauge/`. Project-local
`examples/configs/*.local.yaml` files are discovered only when they exist
relative to your current working directory.

## 2. Guided setup (preferred)

Run guided setup to configure `llama-cli` and a model profile:

    uv run llmgauge setup

`setup` scans for likely `llama-cli` candidates and model directories, lets you
select or enter paths, writes user config files, and does not launch a model.

Read-only preview:

    uv run llmgauge setup --scan

Non-interactive scripted setup (useful for clean-clone validation):

    uv run llmgauge setup --non-interactive \
      --llama-cli /path/to/llama-cli \
      --model-path /path/to/model.gguf \
      --profile-name my_model

This creates, or updates with confirmation/`--force`, files under:

    ~/.config/llmgauge/config.yaml
    ~/.config/llmgauge/model-profiles.yaml

`XDG_CONFIG_HOME` is respected. For example, with `XDG_CONFIG_HOME=/tmp/config`,
LLMGauge uses `/tmp/config/llmgauge/`.

## 3. Manual config fallback

If you prefer manual editing, create user config files from templates:

    uv run llmgauge init

The generated `model-profiles.yaml` includes example template profiles such as
`example_model`, `example_large_model`, and `example_context_model`.

Compatibility note: `uv run llmgauge init-config` still creates project-local
ignored files under `examples/configs/` for contributor workflows:

    examples/configs/llmgauge.local.yaml
    examples/configs/model-profiles.local.yaml

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

Alternatively, add a new profile from the CLI after placing your GGUF file:

    uv run llmgauge model add my_model \
      --path /path/to/model.gguf \
      --label "My Model" \
      --family Example \
      --quant Q4_K_M

To use the packaged `example_model` entry instead, edit its `path` in
`model-profiles.yaml`, run `model update example_model --path /path/to/model.gguf`,
or replace it intentionally with `model add example_model --force`.

Use `--model-profile-file` to target a specific profiles YAML. When omitted,
LLMGauge discovers the profiles file using the same order as runs. The older
`--model-profiles` flag remains supported.

Structured CLI writes may not preserve YAML comments.

Optional per-model runtime metadata can also live in the profile:

    models:
      example_model:
        label: Example Model
        family: Example
        quant: Q4_K_M
        path: /path/to/model.gguf
        flash_attn: on
        runtime_label: daily-tuned

## 4. Check the environment in more detail

Run:

    uv run llmgauge doctor

When config files are present, `doctor` auto-detects them.

A ready setup should show:

- config loaded
- `llama-cli` exists and is executable
- model profiles loaded
- optional `nvidia-smi` status

Missing config or profiles appear as `skip`, not `fail`. `doctor` prints next
steps when setup is incomplete.

To check a specific profile:

    uv run llmgauge doctor --model-profile example_model

## 5. Run a safe smoke check

Run:

    uv run llmgauge smoke

Smoke checks verify the package, built-in suites, config discovery, model profile
discovery, `llama-cli`, optional `nvidia-smi`, and an optional selected model
profile. They do not launch `llama.cpp` and do not create result artifacts.

When setup is incomplete, smoke exits zero with `Smoke check passed with warnings`
and prints next steps. Blocking problems still exit nonzero.

To verify a specific profile:

    uv run llmgauge smoke --model-profile example_model

## 6. List model profiles

Inspect configured model profiles and model path status:

    uv run llmgauge model list

`list-model-profiles` remains a compatibility alias for `model list`.

Useful path statuses include:

    ok
    missing-file
    missing-path

Fix any missing model path before running model evaluations.

## 7. List and validate suites

List built-in suites and friendly aliases:

    uv run llmgauge list-suites

Common aliases:

    practical -> wumbolabs-practical-v1
    core      -> core-v1
    agent     -> agent-backend-v1
    context   -> context-v1

Aliases are input conveniences only. Result artifacts continue to record the
canonical `suite_id` from `suite.yaml`.

Validate a suite by alias or canonical ID:

    uv run llmgauge validate-suite practical

## 8. Preview one prompt

Before launching `llama.cpp`, inspect the resolved run plan:

    uv run llmgauge run \
      --suite practical \
      --only honesty-uncertainty/fake-package-currentness \
      --model-profile my_model \
      --ctx 8192 \
      --max-tokens 800 \
      --temp 0.2 \
      --flash-attn auto \
      --runtime-label stock-reference \
      --dry-run

Dry-run mode resolves config, model profiles, model paths, runtime settings, and selected prompt count. It does not launch `llama.cpp` and does not create a result directory.

## 9. Run one prompt

Start with one prompt before running a full suite.

LLMGauge auto-detects configuration in this order:

1. explicit `--config` and `--model-profile-file` (or `--model-profiles`) paths
2. project-local `examples/configs/*.local.yaml`
3. user config under `~/.config/llmgauge/`

Project-local files take precedence over user config so source-checkout
experiments can override installed/user defaults without changing global
settings.

    uv run llmgauge run \
      --suite practical \
      --only honesty-uncertainty/fake-package-currentness \
      --model-profile my_model \
      --ctx 8192 \
      --max-tokens 800 \
      --temp 0.2 \
      --flash-attn auto \
      --runtime-label stock-reference \
      --auto-name \
      --runs-root results \
      --run-name quickstart-smoke

## 10. Validate the result

After the run completes, validate the generated result directory:

    uv run llmgauge validate-result results/<generated-run-directory>

`validate-result` checks artifact structure and references. It does not prove
answer quality, safety, or publication readiness.

Inspect:

    report.md
    llmgauge-result.json
    cleaned/
    raw/
    logs/

In `report.md`, read **Audit Checklist** and **Prompt Artifact Audit** to trace
outputs and score metadata. Raw outputs are source audit evidence. Cleaned
outputs are derived review aids.

## 11. Optional manual scoring

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

## 12. Export an index

Create a machine-readable index for reports, comparisons, or import workflows:

    uv run llmgauge export-index \
      results/<generated-run-directory> \
      --validate \
      --out results/quickstart-index.json

## 13. Compare runs

After you have two or more result directories, create a comparison report:

    uv run llmgauge compare \
      results/run-a \
      results/run-b \
      --out results/compare.md

Comparison reports summarize runtime settings, score totals, prompt verdicts, speed metrics, VRAM metrics, and label counts. They do not declare a universal winner.

Read **Report Scope**, **Audit Checklist**, and **Prompt Artifact Audit** in
`report.md` for single-run review. Read **Comparison Scope**, **Publish
Readiness Notes**, and **Publication evidence summary** in `compare.md` before
making public quality claims.

Export index mirrors scoring evidence fields for importers. Regenerate it after
scoring or validation changes.

See `docs/PUBLIC_REPORTING.md` and `docs/ARTIFACT_SCHEMAS.md` for the full
public-proof workflow and artifact roles.

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
