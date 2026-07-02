# Repository Guidelines

## Project Structure & Module Organization

LLMGauge is a Python CLI project using a `src/` layout. Core package code lives in `src/llmgauge/`, with the Typer CLI entry point in `src/llmgauge/cli.py`. Shared evaluation logic is under `src/llmgauge/core/`, llama.cpp integration is under `src/llmgauge/runners/`, and bundled prompt suites live in `src/llmgauge/builtin_suites/`. Tests are in `tests/` and mirror core behavior with focused `test_*.py` files. User-facing docs are in `docs/`; editable suite examples are in `suites/`; local configuration templates are in `examples/configs/`.

## Build, Test, and Development Commands

- `uv sync`: install runtime and development dependencies from `pyproject.toml` and `uv.lock`.
- `uv run llmgauge --help`: verify the CLI entry point and list available commands.
- `uv run pytest`: run the full test suite.
- `uv run pytest tests/test_cli_baseline.py`: run one focused test module.
- `uv run ruff check .`: run lint checks.
- `uv run llmgauge validate-suite suites/core-v1`: validate a suite definition and prompt tree.

## Coding Style & Naming Conventions

Target Python 3.11 or newer. Use 4-space indentation, type hints for public helpers, and clear dataclass or Pydantic models where structured artifacts are involved. Keep module names lowercase with underscores, test files named `test_<feature>.py`, and CLI command names hyphenated for user-facing options. Prefer explicit path and schema helpers in `src/llmgauge/core/` over ad hoc parsing. Run `uv run ruff check .` before submitting changes.

## Testing Guidelines

Tests use `pytest`. Add or update tests whenever behavior changes, especially for artifact schemas, CLI validation, suite loading, report generation, and path handling. Keep tests deterministic and avoid requiring real local models unless explicitly testing runner integration. Use focused assertions against generated files, parsed YAML/JSON, or command output rather than broad snapshots.

## Commit & Pull Request Guidelines

Recent commits use concise imperative subjects such as `Add fit ladder artifact validation and indexing` or `Document scoring provenance metadata`. Keep the first line specific and under roughly 72 characters when practical. Pull requests should explain the user-visible change, list validation commands run, link related issues, and include report or CLI output examples when behavior changes. Do not commit private `.local.yaml` config files, model paths, or generated `results/` data unless intentionally adding fixtures.

## Security & Configuration Tips

Machine-specific paths belong in ignored local files such as `examples/configs/llmgauge.local.yaml` and `model-profiles.local.yaml`. Avoid hard-coding model locations, llama.cpp binary paths, or host-specific VRAM assumptions in source or tests.
