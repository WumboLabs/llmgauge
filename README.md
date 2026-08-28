# LLMGauge

Practical local LLM evaluation on real consumer hardware.

LLMGauge is a local-first CLI for running reproducible prompt suites on real consumer hardware. The default runtime is local GGUF models through `llama.cpp`. An optional, externally managed local vLLM backend is also supported for bounded text-only evaluation. LLMGauge is designed for workstation testing, constrained VRAM, preserved artifacts, manual review, and practical model comparison.

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

- run built-in or custom prompt suites against local `llama.cpp` / GGUF models by default
- run the built-in `generic-core-v1` general-purpose suite (`smoke` and `core` profiles) with deterministic evidence checks, manual review, and side-by-side hybrid scoring
- optionally evaluate against an operator-managed local vLLM OpenAI-compatible server (`--backend vllm`; loopback-only, sequential, non-streaming; no remote, auth, concurrency, or lifecycle management; runtime-native metrics are not equivalent to llama.cpp)
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

Current stable tag: v0.75

Current package version: 0.75.0

Current release line: v0.75.0.

Install from PyPI:

    uv tool install llmgauge

Then verify:

    llmgauge --version

Upgrade and uninstall:

    uv tool upgrade llmgauge
    uv tool uninstall llmgauge

Alternatives: `pipx install llmgauge` for another isolated CLI install, or
`pip install llmgauge` to install into an existing Python environment. A
pinned version is available with `uv tool install "llmgauge==0.75.0"`.

Pinned Git source installation remains available as an explicit
pinned-source/development/fallback method:

    uv tool install git+https://github.com/WumboLabs/llmgauge.git@v0.75

Contributors and unreleased development should use a source checkout with
`uv sync` and `uv run llmgauge ...`. Editable installation is a development
convenience, not the formal released-user workflow.

Installing LLMGauge installs only the Python CLI and its Python dependencies.
It does not install `llama.cpp`, GGUF models, CUDA, NVIDIA drivers, vLLM
servers, or any other operator-provided model runtime.

See [Installation](https://github.com/WumboLabs/llmgauge/blob/main/docs/INSTALL.md)
for all installation paths, and [Roadmap](https://github.com/WumboLabs/llmgauge/blob/main/docs/ROADMAP.md)
for current plans; vLLM capability, evidence, and limitations are consolidated
in the [vLLM evidence roadmap](https://github.com/WumboLabs/llmgauge/blob/main/docs/ROADMAP.md#vllm-evidence-track).

## Quick start from a checkout

From the repository root:

    uv sync
    uv run llmgauge --version

Run guided setup (preferred first-run path):

    uv run llmgauge setup

`setup` scans for likely `llama-cli` and GGUF paths, writes `config.yaml` and
`model-profiles.yaml`, and does not launch a model. Use `llmgauge setup --scan`
for a read-only preview, or `llmgauge setup --non-interactive` with explicit
flags for scripted clean-clone validation.

Inspect the environment:

    uv run llmgauge doctor

Inspect built-in reasoning/sampling profiles:

    uv run llmgauge profiles list
    uv run llmgauge profiles show qwen3-thinking-v1

Manual fallback: `llmgauge init` still creates user config files from templates.
`init` includes example template profiles such as `example_model` in
`model-profiles.yaml`. Add a new profile name with `model add`, edit the
template paths in YAML, or replace an existing profile intentionally with
`--force`.

Add and verify your own model profile (manual path):

    uv run llmgauge model add my_model \
      --path /path/to/model.gguf \
      --label "My Model"
    uv run llmgauge model list

The model path must exist on disk. Replace `/path/to/model.gguf` with a real
GGUF file, or create a scratch placeholder for inspection-only dry-run testing.

Run a safe readiness check:

    uv run llmgauge smoke

Preview one prompt without launching `llama.cpp`:

    uv run llmgauge run \
      --suite practical \
      --only honesty-uncertainty/fake-package-currentness \
      --model-profile my_model \
      --ctx 8192 \
      --max-tokens 800 \
      --temp 0.2 \
      --dry-run

`doctor`, `smoke`, and `--dry-run` are inspection-only. They do not launch `llama.cpp` or create result artifacts. `list-model-profiles` remains a compatibility alias for `model list`.

Run one prompt:

    uv run llmgauge run \
      --suite practical \
      --only honesty-uncertainty/fake-package-currentness \
      --model-profile my_model \
      --ctx 8192 \
      --max-tokens 800 \
      --temp 0.2 \
      --auto-name \
      --runs-root results \
      --run-name quickstart-smoke

Validate the result:

    uv run llmgauge validate-result results/<generated-run-directory>

Validation checks artifact structure, not model quality. For public-facing
evidence, follow the checklist in [Public reporting](https://github.com/WumboLabs/llmgauge/blob/main/docs/PUBLIC_REPORTING.md):
run, validate, inspect outputs, `score --check`, apply scores, re-validate,
review **Report Scope**, **Audit Checklist**, **Prompt Artifact Audit**, and
**Publish Readiness Notes** in `report.md`, then compare or export-index as needed.

See [Quickstart](https://github.com/WumboLabs/llmgauge/blob/main/docs/QUICKSTART.md) for the full first-run workflow.

## Generic Core suite

`generic-core-v1` `0.1.0` is a built-in balanced general-purpose suite with two
ordered profiles: `smoke` (4 prompts) and `core` (13 prompts). Seven
deterministic checks run against preserved raw responses and contained
fixtures; manual scores apply per-prompt review dimensions and recompose
side-by-side hybrid evidence without rerunning deterministic checks.

Inspect the suite without launching a model:

    uv run llmgauge list-suites
    uv run llmgauge validate-suite generic-core-v1
    uv run llmgauge run --suite generic-core-v1 --profile core --dry-run

The D5 coding check does not execute generated code in this suite version: it
reproducibly reports `not_run`. Executable D5 evaluation is future suite-version
work behind a separately accepted containment and resource-limit contract.
There is no profile aggregate score; reviewed manual scores remain the quality
authority.

## LocalMaxxing performance benchmark

LocalMaxxing is a dedicated llama.cpp speed-benchmark integration, not a
quality-suite result. Normal `run`, `report`, export, and validation commands
never contact LocalMaxxing.

Create a local artifact using a configured model profile, validate it, and export
its API payload offline:

    uv run llmgauge localmaxxing run --output results/lmx --profile qwen3 \
      --hf-id Qwen/Qwen3-8B --gpu-name "RTX 4090" --vram-gb 24 \
      --llama-bench /path/to/llama-bench
    uv run llmgauge localmaxxing validate results/lmx
    uv run llmgauge localmaxxing export results/lmx

When available, the local artifact also captures source-backed CPU/RAM/OS and
GPU identity, total-device NVIDIA telemetry, llama.cpp runtime flags, a
separately measured combined TPS companion, and a localhost llama-server TTFT
companion. Optional metrics remain absent when their probes cannot prove them;
sampler settings, context length, and hardware cost are never guessed.

`dry-run` is an explicit authenticated non-writing validation and reads
`LOCALMAXXING_API_KEY` only from the environment. `submit` is public and refuses
without `--confirm-public`; no normal command publishes, submits, or polls.
vLLM is not supported. Future Area 4 normalized metrics may be used as an input,
but Area 4 is not implemented. See
[the integration contract](https://github.com/WumboLabs/llmgauge/blob/main/docs/LOCALMAXXING_INTEGRATION_CONTRACT.md).

## External benchmark import

Import a local EleutherAI `lm-eval` results JSON file as contained
read-only evidence. This does not run a benchmark, execute generated
code, or contact a network:

    uv run llmgauge benchmark import /path/to/results.json results/imported-lm-eval
    uv run llmgauge benchmark validate results/imported-lm-eval
    uv run llmgauge benchmark report results/imported-lm-eval

Import success is structural only. Bundle 1 qualification is a separate
exact-identity check against the pinned official harness tasks. Native
score/report/export paths reject these results. The existing
`localmaxxing` namespace remains speed-only. See
[Bundle 1 qualification](https://github.com/WumboLabs/llmgauge/blob/main/docs/BUNDLE1_QUALIFICATION.md).

## Source-checkout usage vs installed CLI usage

Audience split:

- installed end users: PyPI install (`uv tool install llmgauge`), then `llmgauge ...`
- contributors and unreleased development: source checkout with `uv run llmgauge ...`
- editable local install: development convenience only

Use this form when running from a cloned checkout:

    uv run llmgauge ...

Use this form after installing the released CLI into your environment:

    llmgauge ...

Documentation examples often use `uv run llmgauge ...` for contributor
workflows. Installed end users should follow the PyPI install path in
[Installation](https://github.com/WumboLabs/llmgauge/blob/main/docs/INSTALL.md).

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

Generated `report.md` includes **Audit Checklist** and **Prompt Artifact Audit**
sections for tracing public claims back to raw/cleaned outputs and score
rationales. See [Artifact schemas](https://github.com/WumboLabs/llmgauge/blob/main/docs/ARTIFACT_SCHEMAS.md).

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

See [Scoring rubrics](https://github.com/WumboLabs/llmgauge/blob/main/docs/SCORING_RUBRICS.md).

## Compare runs

Generate a comparison report:

    uv run llmgauge compare \
      results/run-a \
      results/run-b \
      --out results/compare.md

Comparison reports summarize runtime settings, score totals, prompt verdicts, trust signals, speed metrics, VRAM metrics, and label counts.

They do not declare a universal winner.

When every compared run carries a native multi-turn transcript, `compare`
writes a bounded structural comparison instead: eligibility identity match,
structural classification, side-by-side represented facts, and recorded review
hooks — with no aggregate score, no winner, and no quality verdict. Mixed
transcript/single-turn comparison fails closed.

## Publish a transcript comparison

To create a sanitized public derivative of exactly two transcript-bearing runs:

    uv run llmgauge export-public-comparison \
      results/run-a \
      results/run-b \
      --out public/transcript-comparison

The output directory contains exactly `transcript-comparison.json` and
`report.md`. The derivative is a content-default-deny allowlist projection of
structural facts only: no prompts, model outputs, feedback content, private
identifiers, paths, or full hashes are included, and no aggregate, winner, or
quality verdict is computed. Human review is required before publication;
sanitization is not proof that private data is absent. Single-run
`export-public` keeps rejecting transcript-bearing runs. See
[Transcript Comparison Public Export Contract](https://github.com/WumboLabs/llmgauge/blob/main/docs/TRANSCRIPT_COMPARISON_PUBLIC_EXPORT_CONTRACT.md).

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

- [Quickstart](https://github.com/WumboLabs/llmgauge/blob/main/docs/QUICKSTART.md)
- [Clean clone testing](https://github.com/WumboLabs/llmgauge/blob/main/docs/CLEAN_CLONE_TESTING.md)
- [Usage command map](https://github.com/WumboLabs/llmgauge/blob/main/docs/USAGE.md)
- [Local model testing workflow](https://github.com/WumboLabs/llmgauge/blob/main/docs/LOCAL_MODEL_TESTING.md)
- [Evaluation tiers](https://github.com/WumboLabs/llmgauge/blob/main/docs/EVALUATION_TIERS.md)
- [Practical Eval v1](https://github.com/WumboLabs/llmgauge/blob/main/docs/PRACTICAL_EVAL_V1.md)
- [Scoring rubrics](https://github.com/WumboLabs/llmgauge/blob/main/docs/SCORING_RUBRICS.md)
- [Scored comparisons](https://github.com/WumboLabs/llmgauge/blob/main/docs/SCORED_COMPARISONS.md)
- [Fit Ladder](https://github.com/WumboLabs/llmgauge/blob/main/docs/FIT_LADDER.md)
- [VRAM capture](https://github.com/WumboLabs/llmgauge/blob/main/docs/VRAM_CAPTURE.md)
- [Artifact schemas](https://github.com/WumboLabs/llmgauge/blob/main/docs/ARTIFACT_SCHEMAS.md)
- [Public reporting guidance](https://github.com/WumboLabs/llmgauge/blob/main/docs/PUBLIC_REPORTING.md)
- [Roadmap](https://github.com/WumboLabs/llmgauge/blob/main/docs/ROADMAP.md)
