# AGENTS.md

Guidance for AI coding tools, assistants, and automated editors working on LLMGauge.

LLMGauge is a conservative local-LLM evaluation tool for real consumer hardware. The project values reproducibility, artifact integrity, clear command behavior, and stable local workflows over clever automation or broad rewrites.

`AGENTS` refers to the current AI coding tool, model, assistant, or automated editor reading this file. Keep this file self-contained and current so the same guardrails apply across different agent harnesses and models.

## Project structure

LLMGauge is a Python CLI project using a `src/` layout.

- Core package code lives in `src/llmgauge/`.
- The Typer CLI entry point is `src/llmgauge/cli.py`.
- Focused CLI command modules live under `src/llmgauge/commands/`.
- Shared CLI helpers live in `src/llmgauge/cli_common.py`.
- Shared evaluation logic lives under `src/llmgauge/core/`.
- llama.cpp integration lives under `src/llmgauge/runners/`.
- Bundled prompt suites live in `src/llmgauge/builtin_suites/`.
- Editable suite examples live in `suites/`.
- Local configuration templates live in `examples/configs/`.
- Tests live in `tests/` and should mirror behavior with focused `test_*.py` files.
- User-facing docs live in `docs/`.

## Mission and non-goals

LLMGauge supports practical, reproducible local LLM evaluation on real consumer hardware.

It is not:

- a cloud evaluation service
- a model downloader
- a hosted leaderboard
- an automatic judge that hides review
- a hardware tuning tool
- a general autonomous agent framework
- a telemetry system

## Absolute rules

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
- Do not add harness-specific configuration files unless the user explicitly asks for that specific tool.

## Standard branch workflow

Follow this order for normal branches.

1. Start from `main`.

   ```bash
   git switch main
   git pull --ff-only origin main
   git switch -c descriptive-branch-name
   ```

2. Inspect state.

   ```bash
   git status --short --branch
   git log --oneline --decorate --graph --max-count=12
   uv run llmgauge --version
   ```

3. Read guidance.

   ```bash
   sed -n '1,260p' AGENTS.md
   ```

4. Inspect task-relevant files before editing.

5. Patch the smallest safe set of files.

6. Run targeted tests first when behavior changed.

7. Run the full gate.

   ```bash
   uv run pytest
   uv run ruff check .
   git diff --check
   ```

8. Review the diff.

   ```bash
   git diff --stat
   git diff --name-status
   git diff
   ```

9. Commit focused work.

10. Verify post-commit state.

    ```bash
    git status --short --branch
    git log --oneline --decorate --graph --max-count=12
    ```

11. Stop and report.

Do not push, merge, tag, delete branches, or rewrite history unless explicitly asked.

## AGENTS operating rules

AGENTS should operate as supervised coding assistants, not autonomous maintainers.

At the start of every AGENTS task:

1. read `AGENTS.md`
2. report current branch and HEAD
3. report whether the working tree is clean
4. restate the requested scope
5. identify likely files to change
6. identify planned targeted tests and full gates

AGENTS may write review notes under `tmp/` when explicitly requested, but those reports should not be committed.

AGENTS must not add tool-specific configuration files such as `.cursor/`, `.cursorrules`, `CLAUDE.md`, `GEMINI.md`, or other harness sidecar files unless the user explicitly requests that exact integration.

AGENTS must stop after completing the requested scope and report:

- branch name
- final HEAD
- files changed
- commands run
- test results
- ruff result
- diff-check result
- working tree status
- risks or follow-up items


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
- Do not delete branches unless explicitly asked.
- Do not include private machine paths, local model paths, benchmark artifacts, database files, secrets, `.env` files, generated `results/` data, or personal notes in commits unless intentionally adding fixtures.

Preferred commit shape:

1. implementation
2. tests
3. docs, if needed
4. release metadata only when preparing a release

Commit subjects should be concise, imperative, and specific, for example:

- `Harden model profile mutations`
- `Add model profile management commands`
- `Set v0.50 release metadata`
- `Expand repository agent guidance`

## Release metadata workflow

Only update these during an explicit release-prep step:

- `pyproject.toml`
- `src/llmgauge/__init__.py`
- `uv.lock`
- `CHANGELOG.md`
- release/version language in docs

Do not bump `__version__` just because a feature branch starts.

Release-prep branch order:

1. branch from current `main`
2. update version metadata
3. update lockfile with `uv lock`
4. add changelog entry
5. verify version

   ```bash
   grep '^version' pyproject.toml
   grep '__version__' src/llmgauge/__init__.py
   uv run llmgauge --version
   ```

6. run full gate
7. commit release metadata
8. push and PR only when asked
9. merge only when asked
10. tag only after release metadata is merged to `main`

## PR and CI workflow

When asked to create a PR:

1. verify branch state
2. push branch
3. create PR
4. inspect PR
5. watch checks
6. report PR number, URL, CI result, and mergeability

Use explicit PR numbers with `gh` when using `--repo`.

```bash
gh pr view 1 --repo WumboLabs/llmgauge
gh pr checks 1 --repo WumboLabs/llmgauge --watch
```

CI runs automatically for pull requests and pushes to `main`. Feature branch pushes may not trigger CI unless manually dispatched.

## Merge workflow

When asked to merge a PR:

1. confirm checks passed
2. confirm `mergeable` is `MERGEABLE`
3. use merge commit when preserving focused branch history matters
4. update local `main`
5. run final local gate

```bash
git switch main
git pull --ff-only origin main
uv run pytest
uv run ruff check .
git diff --check
```

## Tag workflow

Only create a release tag after the release metadata merge is on `main`.

Pre-tag checks:

```bash
git status --short --branch
git rev-parse HEAD
uv run llmgauge --version
uv run pytest
uv run ruff check .
git diff --check
```

Create annotated tags:

```bash
git tag -a vX.YY -m "LLMGauge vX.YY"
git push origin refs/tags/vX.YY:refs/tags/vX.YY
```

Use full tag refs if a branch and tag share the same name.

## Branch cleanup workflow

Only clean up after merge and tag verification.

Preferred cleanup:

```bash
git branch -d branch-name
git push origin --delete branch-name
git fetch --prune origin
```

Keep backup branches until the user explicitly confirms they can be removed.

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
- Keep public docs free of private project memory, private machine paths, and local-only benchmark conclusions.

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
- Branch, PR, CI, release, and tag steps were not performed unless explicitly requested.
