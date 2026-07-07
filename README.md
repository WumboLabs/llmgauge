# LLMGauge

Practical local LLM evaluation on real consumer hardware.

LLMGauge is a local-first CLI for running reproducible prompt suites against local GGUF models through `llama.cpp`. It is designed for workstation testing, constrained VRAM, preserved artifacts, manual review, and practical model comparison.

It helps answer questions like:

- Did this local model complete the task?
- Did it hallucinate commands, packages, tools, APIs, or facts?
- Did it follow constraints?
- Was the answer useful enough to trust?
- What runtime settings were used?
- How much VRAM headroom did the run have?
- Can another person inspect the raw evidence?

LLMGauge is part of the WumboLabs “Real Hardware. Real Testing. No Hype.” workflow.

## What LLMGauge is

LLMGauge is an artifact-preserving local model evaluation bench.

It can:

- run built-in or custom prompt suites against local `llama.cpp` / GGUF models
- preview run plans before launching a model
- preserve raw prompts, raw outputs, cleaned review outputs, and stderr logs
- capture runtime metadata such as context size, batch settings, flash-attention mode, and runtime methodology labels
- capture prompt-level speed metrics
- capture NVIDIA VRAM usage summaries when `nvidia-smi` is available
- validate result directories
- generate Markdown run reports
- initialize and apply manual score templates
- create scored comparison reports across runs
- run context ladders and adaptive fit ladders for local hardware fit testing
- run manifest-driven model batches across configured model profiles

## What LLMGauge is not

LLMGauge is not:

- a synthetic benchmark leaderboard
- an automatic model judge
- a model downloader
- a cloud evaluation service
- an agent framework
- a hardware tuning tool
- a replacement for manual review

Scores are review metadata, not universal truth. Comparison reports are evidence summaries, not global rankings.

## Current status

Current stable tag: v0.53

Current development line: v0.54

LLMGauge is usable from a repository checkout with `uv run llmgauge ...` or as an installed CLI with `llmgauge ...`. See [Installation](docs/INSTALL.md) for source-checkout, editable local install, and GitHub install workflows.

## Quick start from a checkout

From the repository root:

    uv sync
    uv run llmgauge --version

Create user config files and inspect the environment:

    uv run llmgauge init
    uv run llmgauge doctor

Add and verify a model profile:

    uv run llmgauge model add example_model \
      --path /path/to/model.gguf \
      --label "Example Model"
    uv run llmgauge model list

The model path must exist on disk. Replace `/path/to/model.gguf` with a real
GGUF file, or create a scratch placeholder for inspection-only dry-run testing.

Run a safe readiness check:

    uv run llmgauge smoke

Preview one prompt without launching `llama.cpp`:

    uv run llmgauge run \
      --suite practical \
      --only honesty-uncertainty/fake-package-currentness \
      --model-profile example_model \
      --ctx 8192 \
      --max-tokens 800 \
      --temp 0.2 \
      --dry-run

`doctor`, `smoke`, and `--dry-run` are inspection-only. They do not launch `llama.cpp` or create result artifacts. `list-model-profiles` remains a compatibility alias for `model list`.

Run one prompt:

    uv run llmgauge run \
      --suite practical \
      --only honesty-uncertainty/fake-package-currentness \
      --model-profile example_model \
      --ctx 8192 \
      --max-tokens 800 \
      --temp 0.2 \
      --auto-name \
      --runs-root results \
      --run-name quickstart-smoke

Validate the result:

    uv run llmgauge validate-result results/<generated-run-directory>

See [Quickstart](docs/QUICKSTART.md) for the full first-run workflow.

## Source-checkout usage vs installed CLI usage

Use this form when running from a cloned checkout:

    uv run llmgauge ...

Use this form only after installing the CLI into your environment:

    llmgauge ...

Current development and documentation examples prefer `uv run llmgauge ...` unless they are explicitly discussing installed CLI behavior.

Configuration discovery checks explicit CLI paths first, then project-local
`examples/configs/*.local.yaml` relative to the current working directory, then
user config under `~/.config/llmgauge/`. `XDG_CONFIG_HOME` is respected.

## Local configuration

LLMGauge does not download models or guess private machine paths.

User machine-specific files live outside the repository:

    ~/.config/llmgauge/config.yaml
    ~/.config/llmgauge/model-profiles.yaml

`XDG_CONFIG_HOME` is respected. Project-local ignored files under
`examples/configs/*.local.yaml` are still supported for contributor workflows
and take precedence over user config when present.

The config file points to `llama-cli`.

The model profiles file defines named local models and their GGUF paths.

Example model profile:

    models:
      example_model:
        label: Example Model
        family: Example
        quant: Q4_K_M
        path: /path/to/model.gguf

Run commands can then use:

    --model-profile example_model

instead of repeating model paths.

## Result artifacts

Each normal run writes a result directory containing:

    llmgauge-result.json
    report.md
    raw/<prompt_id>.prompt.md
    raw/<prompt_id>.output.txt
    cleaned/<prompt_id>.output.txt
    logs/<prompt_id>.stderr.log

Raw outputs are preserved as audit evidence.

Cleaned outputs are derived review artifacts that remove obvious `llama.cpp` terminal wrapper text where possible. They do not replace raw outputs.

## Manual scoring

LLMGauge supports manual scoring through reviewable YAML files.

Initialize a score file:

    uv run llmgauge score results/<run-directory> --init

Validate a score file without mutating artifacts:

    uv run llmgauge score \
      results/<run-directory> \
      --scores results/<run-directory>/scores.yaml \
      --check

Apply scores:

    uv run llmgauge score \
      results/<run-directory> \
      --scores results/<run-directory>/scores.yaml

Manual scoring uses practical review dimensions such as technical correctness, safety, instruction following, uncertainty honesty, hallucination severity, practical usefulness, and overall trust.

See [Scoring rubrics](docs/SCORING_RUBRICS.md).

## Compare runs

Generate a comparison report:

    uv run llmgauge compare \
      results/run-a \
      results/run-b \
      --out results/compare.md

Comparison reports summarize runtime settings, score totals, prompt verdicts, trust signals, speed metrics, VRAM metrics, and label counts.

They do not declare a universal winner.

## Privacy and safety posture

LLMGauge is local-first and conservative by design.

- Model paths are redacted in stored result JSON.
- Raw prompts and outputs are preserved for audit.
- Local config files are intended to stay private.
- LLMGauge does not download models by default.
- LLMGauge does not modify GPU drivers, CUDA, kernel settings, firewall rules, or system packages.
- LLMGauge does not tune GPU power limits, clocks, or memory settings.

## Development checks

    uv run pytest
    uv run ruff check .
    git diff --check

## Documentation

Start here:

- [Quickstart](docs/QUICKSTART.md)
- [Clean clone testing](docs/CLEAN_CLONE_TESTING.md)
- [Usage command map](docs/USAGE.md)
- [Local model testing workflow](docs/LOCAL_MODEL_TESTING.md)
- [Evaluation tiers](docs/EVALUATION_TIERS.md)
- [Practical Eval v1](docs/PRACTICAL_EVAL_V1.md)
- [Scoring rubrics](docs/SCORING_RUBRICS.md)
- [Scored comparisons](docs/SCORED_COMPARISONS.md)
- [Fit Ladder](docs/FIT_LADDER.md)
- [VRAM capture](docs/VRAM_CAPTURE.md)
- [Artifact schemas](docs/ARTIFACT_SCHEMAS.md)
- [Public reporting guidance](docs/PUBLIC_REPORTING.md)
- [Roadmap](docs/ROADMAP.md)
