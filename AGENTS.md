# AGENTS.md

Guidance for AI coding tools, assistants, and automated editors working on LLMGauge.

LLMGauge is a conservative local-LLM evaluation tool for real consumer hardware. The project values reproducibility, artifact integrity, clear command behavior, and stable local workflows over clever automation or broad rewrites.

## Project structure

LLMGauge is a Python CLI project using a `src/` layout.

- Core package code lives in `src/llmgauge/`.
- The Typer CLI entry point is `src/llmgauge/cli.py`.
- Focused CLI command modules live under `src/llmgauge/commands/`.
- Shared evaluation logic lives under `src/llmgauge/core/`.
- llama.cpp integration lives under `src/llmgauge/runners/`.
- Bundled prompt suites live in `src/llmgauge/builtin_suites/`.
- Editable suite examples live in `suites/`.
- Local configuration templates live in `examples/configs/`.
- Tests live in `tests/` and should mirror behavior with focused `test_*.py` files.
- User-facing docs live in `docs/`.

## Core rules

- Make small, reviewable changes.
- Prefer boring, explicit, deterministic code.
- Do not introduce network calls, telemetry, model downloads, cloud services, background agents, or external execution frameworks.
- Do not change public CLI behavior accidentally.
- Do not hide failures, retries, OOMs, missing files, validation errors, or nonzero exits.
- Do not mutate user-owned config files, result artifacts, scores, or reports unless the command explicitly exists to do that.
- Preserve raw outputs and original artifacts whenever possible.
- Treat generated evaluation artifacts as records, not scratch files.
- Avoid broad refactors unless the task is explicitly a refactor and tests cover compatibility.
- Do not add dependencies unless they are necessary, lightweight, and justified.

## Local development expectations

Use the existing project tooling.

Common commands:

```bash
uv sync
uv run llmgauge --help
uv run llmgauge validate-suite suites/core-v1
uv run pytest
uv run ruff check .
git diff --check
```

Run these gates before any commit:

```bash
uv run pytest
uv run ruff check .
git diff --check
```

For targeted changes, run focused tests first, then the full gate.

```bash
uv run pytest tests/test_cli_model_commands.py tests/test_model_profiles_store.py -vv
uv run pytest
uv run ruff check .
git diff --check
```

## Git workflow

- Work on a feature branch, not directly on `main`.
- Keep commits focused.
- Do not mix release metadata with feature work.
- Do not create tags unless explicitly asked.
- Do not push unless explicitly asked.
- Do not rewrite public history unless explicitly asked.
- Do not include private machine paths, local model paths, benchmark artifacts, database files, secrets, `.env` files, generated `results/` data, or personal notes in commits unless intentionally adding fixtures.

Preferred commit shape:

1. implementation
2. tests
3. docs, if needed
4. release metadata only when preparing a release

Commit subjects should be concise, imperative, and specific, for example `Harden model profile mutations`.

## Release metadata

Only update these during an explicit release-prep step:

- `pyproject.toml`
- `src/llmgauge/__init__.py`
- `uv.lock`
- `CHANGELOG.md`
- release/version language in docs

Do not bump `__version__` just because a feature branch starts.

## CLI compatibility

LLMGauge is a CLI-first tool. Preserve existing command names, aliases, option names, exit codes, and dry-run behavior unless the task explicitly asks to change them.

When changing CLI code:

- Add or update CLI tests.
- Check help output manually when adding commands.
- Preserve compatibility aliases where practical.
- Keep destructive commands explicit.
- Prefer `--dry-run`, `--check`, `--yes`, or `--force` semantics for commands that validate, preview, remove, overwrite, or mutate files.
- Use hyphenated command and option names for user-facing CLI surfaces.

## Config and profile files

User-owned YAML files must be treated carefully.

When writing config/model-profile commands:

- Do not silently drop unknown fields.
- Do not silently remove user data.
- Avoid destructive operations without explicit confirmation such as `--yes`.
- Reject ambiguous mutation requests.
- Validate input before writing.
- Keep errors clear and actionable.
- Do not hard-code model locations, llama.cpp binary paths, or host-specific VRAM assumptions in source or tests.

Known acceptable limitation: YAML comments may not be preserved by structured write operations unless comment-preserving YAML support is intentionally added.

Machine-specific paths belong in ignored local files such as `examples/configs/llmgauge.local.yaml` and `examples/configs/model-profiles.local.yaml`.

## Result artifacts

Result directories are evidence. Do not mutate them unless a command explicitly applies scoring, validation, export, or report update.

Rules:

- Preserve raw output.
- Preserve cleaned output.
- Preserve stderr logs.
- Preserve VRAM sample data.
- Preserve original command metadata with model paths redacted.
- Never convert failed runs into successful runs.
- Never hide failed attempts in fit-ladder or retry workflows.
- Validation should report problems, not silently repair artifacts.

## Model execution

Do not launch real model runs in tests.

For code paths that would call `llama-cli`:

- Use dry-run tests where possible.
- Mock runner behavior in unit tests.
- Keep model paths redacted in artifacts where expected.
- Do not assume a specific GPU, CUDA version, llama.cpp build, or model file exists.

## Fit ladder and retry behavior

Fit/retry workflows must be explicit and artifact-preserving.

- Do not make adaptive fallback the default for normal runs.
- Record every failed attempt.
- Classify failures honestly.
- Preserve failed attempt directories.
- Report the selected working configuration clearly.
- Do not hide the originally requested context/settings.

## Scoring behavior

Manual scoring remains review-oriented.

- Do not overwrite reviewed scores without explicit user intent.
- Auto scoring drafts must remain drafts unless explicitly applied.
- Keep provenance fields accurate.
- Keep unreviewed/metadata-only score states visible.

## Testing guidelines

Tests use `pytest`.

- Add or update tests whenever behavior changes.
- Prioritize artifact schemas, CLI validation, suite loading, report generation, path handling, and mutation safety.
- Keep tests deterministic.
- Avoid requiring real local models unless explicitly testing runner integration.
- Use focused assertions against generated files, parsed YAML/JSON, or command output rather than broad snapshots.

## Documentation style

Docs should be practical and precise.

- Avoid hype.
- Avoid leaderboard claims unless backed by artifacts.
- Prefer reproducible commands.
- State limitations plainly.
- Keep examples local-first and source-checkout friendly.
- Do not recommend cloud workflows as the default path.

## Code style

- Target Python 3.11 or newer.
- Use 4-space indentation.
- Use type hints for public helpers.
- Use clear names.
- Prefer simple functions over clever abstractions.
- Keep imports minimal and explicit.
- Avoid broad exception swallowing.
- Raise clear `ValueError`, `typer.BadParameter`, or `typer.Exit` where appropriate.
- Keep schema changes backward-compatible where practical.
- Preserve `extra="allow"` behavior in Pydantic models that load user-owned YAML.

## Review checklist

Before presenting work as complete, verify:

- Tests pass.
- Ruff passes.
- `git diff --check` passes.
- CLI help still renders.
- Existing aliases still work.
- No unexpected release/version bump was included.
- No user data, model paths, result artifacts, caches, or secrets were staged.
- Destructive behavior requires explicit confirmation.
- User-owned YAML unknown fields are preserved by update paths.
