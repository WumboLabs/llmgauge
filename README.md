# LLMGauge

Practical local LLM evaluation on real hardware.

LLMGauge is a local-first CLI for running practical prompt suites against local GGUF models through llama.cpp. It is designed for real workstation testing, constrained VRAM, reproducible local runs, preserved raw outputs, manual scoring, and clear model comparison.

It is not a synthetic benchmark leaderboard, not an automatic judge system, and not a model downloader.

## Current status

Development checkpoint: v0.07

Current capabilities:

- Validate prompt suites.
- Run one prompt, one category, or a full suite.
- Capture raw prompt, raw output, stderr logs, runtime metadata, and speed metrics.
- Generate Markdown reports.
- Create and apply manual score templates.
- Compare two or more result directories.
- Use local YAML config and model profiles.
- Validate result directory integrity.

## Install for development

    uv sync
    uv run llmgauge --help

## Validate suites

    uv run llmgauge validate-suite suites/core-v1

## Run a suite with explicit paths

    uv run llmgauge run \
      --suite suites/core-v1 \
      --include all \
      --model-id example-model \
      --model-path /path/to/model.gguf \
      --llama-cli /path/to/llama-cli \
      --ctx 8192 \
      --max-tokens 800 \
      --temp 0.2 \
      --gpu-layers 999 \
      --out results/example-run

## Run with config and model profiles

    uv run llmgauge run \
      --suite suites/core-v1 \
      --include honesty \
      --model-profile example_model \
      --config examples/configs/llmgauge.local.yaml \
      --model-profiles examples/configs/model-profiles.local.yaml \
      --out results/example-profile-run

Local files matching `examples/configs/*.local.yaml` are ignored by git and are intended for private machine-specific paths.

## Agent backend evaluation suite

`agent-backend-v1` contains prompt-based tests for local models intended to act as coding or operations agent backends.

The suite tests:

- fake tool resistance
- failed shell command recovery
- conservative config-edit planning
- small coding-task usefulness
- synthetic agent preload / long-context constraint retention

Example:

    uv run llmgauge run \
      --suite suites/agent-backend-v1 \
      --include all \
      --model-profile example_model \
      --config examples/configs/llmgauge.local.yaml \
      --model-profiles examples/configs/model-profiles.local.yaml \
      --max-tokens 900 \
      --out results/example-agent-backend-smoke

This suite does not require a real agent framework. It simulates the kind of context and constraints an agent backend may receive.

## Generate a synthetic context prompt

`contextgen` creates a synthetic long-context prompt and separate metadata file. It does not run a model by itself.

    uv run llmgauge contextgen \
      --target-tokens 8192 \
      --placement 0.75 \
      --needle "The deployment codename is Wumbo Finch." \
      --question "What is the deployment codename?" \
      --out-prompt tmp/context-prompts/wumbo-finch-8k.md \
      --out-metadata tmp/context-prompts/wumbo-finch-8k.json

The current token count is an approximation based on a character heuristic. Tokenizer-verified sizing is planned for a later hardening pass.

## Run a context ladder

Context ladders run the same selected prompt set across explicit context sizes.

    uv run llmgauge run-ladder \
      --suite suites/core-v1 \
      --include honesty \
      --model-profile example_model \
      --config examples/configs/llmgauge.local.yaml \
      --model-profiles examples/configs/model-profiles.local.yaml \
      --ctx-ladder 8192,16384,32768 \
      --max-tokens 400 \
      --out results/example-ladder

The default ladder is `8192,16384,32768`. v0.08 caps context ladders at `65536`; larger context testing is reserved for a later explicit extreme-context workflow.

## Extreme context guardrails

Normal context ladder runs are capped at `65536` tokens.

Context values above `65536` require explicit operator opt-in:

    uv run llmgauge run-ladder \
      --suite suites/core-v1 \
      --include honesty \
      --model-profile example_model \
      --config examples/configs/llmgauge.local.yaml \
      --model-profiles examples/configs/model-profiles.local.yaml \
      --ctx-ladder 8192,65536,131072 \
      --allow-extreme-context \
      --max-tokens 400 \
      --out results/example-extreme-ladder

Extreme context mode is capped at `262144` tokens in v0.10. LLMGauge does not auto-tune KV cache, quantization, GPU settings, or CPU fallback.

## Validate a result directory

    uv run llmgauge validate-result results/example-run

## Create and apply manual scores

    uv run llmgauge score results/example-run --init

    uv run llmgauge score \
      results/example-run \
      --scores results/example-run/scores.yaml

Manual scoring uses a 0-5 scale across practical evaluation dimensions such as technical correctness, safety, instruction following, uncertainty honesty, hallucination severity, practical usefulness, and overall trust.

## Compare runs

    uv run llmgauge compare \
      results/example-run-a \
      results/example-run-b \
      --out results/compare.md

Comparison reports summarize runtime settings, prompt scores, prompt eval speed, generation speed, and label counts. They do not declare a universal winner.

## Result artifacts

Each run writes a result directory containing:

    llmgauge-result.json
    report.md
    raw/<prompt_id>.prompt.md
    raw/<prompt_id>.output.txt
    logs/<prompt_id>.stderr.log

Raw model outputs are preserved separately and are not cleaned or filtered.

## Privacy and safety posture

- Model paths are redacted in stored result JSON.
- Raw prompts and outputs are preserved for review.
- LLMGauge does not download models by default.
- LLMGauge does not modify GPU drivers, CUDA, kernel settings, firewall rules, or system packages.
- Local config files are intended to stay private.

## Development checks

    uv run pytest
    uv run ruff format .
    uv run ruff check .

## Monolith bridge artifacts

LLMGauge is designed to produce portable result artifacts that another local application, such as Monolith, can import without LLMGauge writing directly to that application's database.

Explicit output path:

    uv run llmgauge run \
      --suite suites/agent-backend-v1 \
      --only tool-honesty/fake-tool-resistance \
      --model-profile gemma4_12b_qat_q4 \
      --config examples/configs/llmgauge.local.yaml \
      --model-profiles examples/configs/model-profiles.local.yaml \
      --max-tokens 300 \
      --out results/agent-backend-fake-tool

Automatic timestamped output path:

    uv run llmgauge run \
      --suite suites/agent-backend-v1 \
      --only tool-honesty/fake-tool-resistance \
      --model-profile gemma4_12b_qat_q4 \
      --config examples/configs/llmgauge.local.yaml \
      --model-profiles examples/configs/model-profiles.local.yaml \
      --max-tokens 300 \
      --auto-name \
      --runs-root results \
      --run-name agent-backend-fake-tool

Create a machine-readable export index:

    uv run llmgauge export-index \
      results/2026-06-16_06-06-45-agent-backend-fake-tool-001 \
      --out results/llmgauge-index.json

See `docs/MONOLITH_BRIDGE_CONTRACT.md` for the Monolith import boundary and compatibility rules.
