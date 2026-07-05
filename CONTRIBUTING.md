# Contributing to LLMGauge

LLMGauge is an early-stage local LLM evaluation CLI. Contributions should keep the project conservative, reproducible, and understandable from a clean checkout.

## Project scope

LLMGauge focuses on:

- practical local LLM evaluation on real hardware
- GGUF and llama.cpp-oriented workflows
- reproducible prompt suites
- preserved raw artifacts and cleaned outputs
- explicit runtime metadata
- manual scoring and reviewable comparison reports
- honest claim boundaries

LLMGauge is not:

- a leaderboard
- a cloud eval service
- a model downloader
- an automatic judge
- an agent framework
- a hardware tuning tool

## Development setup

Recommended source-checkout workflow:

    uv run llmgauge --help
    uv run pytest
    uv run ruff check .

Do not assume users have your local model paths, GPU, shell aliases, or machine-specific config.

## Before opening a pull request

Run the standard gate:

    uv run pytest
    uv run ruff check .
    git diff --check

For changes that affect suites, also run:

    uv run pytest tests/test_suite_loading.py tests/test_suite_paths.py tests/test_suite_mirror.py

For CLI changes, add or update focused tests under `tests/` and run the relevant test file before the full gate.

## Prompt suite guidelines

Prompt suites should be self-contained and public-safe.

Prompts should:

- define the task clearly
- include all context needed to answer
- avoid private machine names, personal paths, credentials, and internal project notes
- avoid depending on current internet access
- reward honest uncertainty over confident fabrication
- preserve clear claim boundaries

When changing packaged built-in suites, keep the source-checkout `suites/` mirror and `src/llmgauge/builtin_suites/` synchronized. The suite mirror drift test is expected to fail if prompt or suite files diverge.

Top-level `suites/*/baselines/` files are allowed to be source-checkout-only and are not required to exist under packaged built-ins.

## Artifact and reporting guidelines

Do not hide raw model output. LLMGauge artifacts should preserve enough information for review and reproduction.

When adding fields to artifacts or reports:

- keep existing artifacts readable when possible
- document new public fields in the relevant docs
- avoid silently changing interpretation of existing fields
- distinguish requested settings from selected or fallback settings
- keep assisted scoring clearly separate from reviewed manual scoring

## Runtime and hardware claim boundaries

Runtime settings can materially affect comparability. Be explicit when changing or reporting:

- context size
- batch and ubatch
- GPU layers
- flash attention mode
- llama.cpp build or backend
- runtime labels
- GPU/driver metadata when available

Do not present tuned daily-use results as stock/reference comparisons unless the methodology explicitly says so.

## Style

Keep changes small, testable, and reversible.

Prefer:

- focused commits
- direct error messages
- explicit configuration over hidden magic
- standard-library Python where practical
- clear docs over implicit behavior

Avoid:

- unrelated feature expansion
- network activity during normal runs
- automatic model downloads
- private/local assumptions in public docs
- benchmark or leaderboard claims not supported by artifacts
