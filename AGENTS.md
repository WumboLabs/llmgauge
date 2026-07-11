# AGENTS.md

Guidance for AI coding tools, assistants, and automated editors working on LLMGauge.

LLMGauge is a conservative local-model evaluation tool for real consumer hardware. The project values evaluation quality, reproducibility, artifact integrity, stable command behavior, and defensible evidence over feature volume, architectural novelty, or broad automation.

`AGENT` refers to the coding tool, model, assistant, or automated editor currently working in this repository. This file is intentionally self-contained so the same guardrails apply across different agent harnesses.

## Project identity

LLMGauge is primarily:

- a local-model evaluation engine
- an artifact-preserving evaluation bench
- a reproducibility and public-evidence system
- a CLI-first tool for real consumer hardware and constrained VRAM

LLMGauge evaluates dimensions such as:

- usefulness
- honesty and truthfulness
- technical correctness
- safety
- instruction following
- completion quality
- speed
- VRAM use and headroom
- reproducibility
- real workflow fit

LLMGauge is not:

- a cloud evaluation service
- a hosted leaderboard
- a universal model-ranking system
- a model downloader
- a hardware tuning tool
- an agent framework
- a hidden automatic judge
- a telemetry or data-collection service
- a hosted multi-user platform

Structural validation is not answer-quality validation.

Manual scores are review metadata, not universal truth.

Comparison reports are evidence summaries, not global recommendations.

Auto-draft scoring is review-required triage.

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
- Tests live in `tests/`.
- User-facing documentation lives in `docs/`.
- Temporary local review artifacts belong under ignored `tmp/`.
- Generated evaluation artifacts normally belong under ignored `results/`.

## Absolute rules

- Inspect repository state before making changes.
- Read this file before editing.
- Make small, focused, reviewable changes.
- Prefer explicit, deterministic code over clever abstractions.
- Do not broaden scope merely because adjacent code is visible.
- Do not perform unrelated cleanup.
- Do not silently commit unrelated files.
- Do not introduce network behavior by default.
- Do not introduce telemetry, model downloads, cloud services, background agents, or external execution frameworks.
- Do not add an automatic LLM judge.
- Do not add arbitrary llama.cpp argument passthrough.
- Do not create abstractions solely for hypothetical future backends.
- Do not change public CLI behavior accidentally.
- Do not hide failures, retries, OOMs, missing files, validation errors, or nonzero exits.
- Do not silently repair or reinterpret user-owned artifacts.
- Preserve raw outputs and original evidence.
- Treat generated evaluation artifacts as records, not scratch files.
- Do not automatically delete user-created result artifacts.
- Avoid broad refactors unless the requested task is explicitly a refactor and compatibility is covered by tests.
- Do not add dependencies unless they are necessary, lightweight, and justified.
- Do not add tool-specific sidecar files unless explicitly requested.
- Never expose secrets in reports, fixtures, command output, or public artifacts.
- Never assume public redaction is perfect; public exports must still require human review.

## Scope discipline

Before editing, define:

1. the requested scope
2. the smallest safe implementation slice
3. the files likely to change
4. the tests needed
5. adjacent work that will remain deferred

Do not expand a focused task into:

- a broad architecture rewrite
- unrelated documentation cleanup
- speculative backend support
- model downloading
- hardware tuning
- automatic scoring
- TUI work
- release work
- PR or CI ceremony

unless the user explicitly requests that scope.

When a milestone contains several dependent features, implement them in focused slices rather than one uncontrolled commit.

## Starting every repository task

At the start of every substantial repository task:

1. Read `AGENTS.md`.
2. Inspect the current branch and HEAD.
3. Inspect the working tree.
4. Inspect recent history.
5. Compare local `main` with `origin/main` when remote state matters.
6. Restate the requested scope.
7. Identify likely files and modules.
8. Identify targeted tests and full gates.
9. Identify whether real operator validation will be required.
10. Identify any existing untracked artifacts that must be preserved.

Suggested read-only commands:

```bash
git status --short --branch
git rev-parse HEAD
git log --oneline --decorate --graph --max-count=20
git tag --points-at HEAD
git diff --check
uv run llmgauge --version
```

Do not invent repository state. Inspect it.

## Branch workflow

Work on a focused feature branch rather than directly on `main`.

Before creating a branch, confirm that the working tree is safe and that existing untracked files will not be disturbed.

Typical owner workflow:

```bash
git switch main
git pull --ff-only origin main
git switch -c feature/descriptive-name
```

A coding agent must not pull, fetch, switch branches, or create a branch blindly when local changes may be present.

When remote synchronization is not explicitly authorized, inspect rather than mutate:

```bash
git status --short --branch
git rev-parse main
git rev-parse origin/main
git log --oneline --decorate --graph --max-count=20
```

Do not use destructive Git operations such as:

- `git reset --hard`
- forced branch updates
- history rewriting
- aggressive cleanup
- unreviewed branch deletion

unless explicitly approved.

## Implementation workflow

For normal feature work:

1. Inspect task-relevant code and tests.
2. Define the smallest approved change.
3. Patch only relevant files.
4. Run focused tests.
5. Inspect generated artifacts when behavior changes.
6. Run the full local gate.
7. Review the complete diff.
8. Create the required untracked review report.
9. Commit focused work only when requested or when the task explicitly includes committing.
10. Stop and report.

Recommended checks:

```bash
uv run pytest
uv run ruff check .
git diff --check
```

Review before committing:

```bash
git diff --stat
git diff --name-status
git diff
git status --short --branch
```

## Commit rules

- Keep commits focused.
- Do not mix feature work with release metadata.
- Do not commit generated `results/`.
- Do not commit temporary `tmp/` review artifacts.
- Do not commit private machine paths, secrets, `.env` files, local databases, caches, or personal notes.
- Do not silently stage unrelated files.
- Review the exact staged diff before committing.

Use explicit, noninteractive commit messages:

```bash
git commit -m "Add cached model provenance"
```

Do not invoke an interactive editor or assume `vi` is installed or configured.

Commit subjects should be concise, imperative, and specific.

Examples:

- `Add cached model provenance`
- `Harden public export redaction`
- `Document schema compatibility policy`
- `Set v0.70.0 release metadata`

## Owner merge workflow

Pull requests are optional and are not the default owner workflow.

The normal owner workflow is:

1. Complete the focused feature branch.
2. Run targeted tests.
3. Run the full local gate.
4. Create and inspect the untracked review report.
5. Review the branch locally.
6. Switch to `main`.
7. Confirm `main` is synchronized and clean.
8. Merge with a merge commit:

```bash
git merge --no-ff feature/descriptive-name -m "Merge descriptive feature"
```

9. Run the final local gate on `main`.
10. Perform any required real operator smoke.
11. Create release metadata separately when preparing a release.
12. Tag and push only when explicitly requested.

Do not merge automatically merely because tests pass.

Do not delete the feature branch until merge, release, and tag state have been verified and the user approves cleanup.

## Pull request workflow

PRs are optional.

Only create or use a pull request when explicitly requested.

When asked to create a PR:

1. Verify branch state.
2. Confirm the branch contains only intended commits.
3. Push the branch.
4. Create the PR.
5. Inspect the PR diff and metadata.
6. Inspect checks when checks actually exist.
7. Report the PR number, URL, checks, and mergeability.

Do not assume CI exists or has run.

LLMGauge currently treats local validation as authoritative. CI may be added later when contributor volume, packaging complexity, or multi-environment testing justifies it.

When a PR has no checks, say so plainly rather than treating missing checks as success.

## Release workflow

Release metadata must remain separate from feature work.

Only update release metadata during an explicit release-preparation step.

Typical release files include:

- `pyproject.toml`
- `src/llmgauge/__init__.py`
- `uv.lock`
- `CHANGELOG.md`
- release/version language in documentation

Do not bump the package version merely because a feature branch starts.

Release preparation should:

1. Start after feature work is merged.
2. Update version metadata.
3. Update the lockfile when required.
4. Update the changelog.
5. Verify package and CLI versions.
6. Run the full local gate.
7. Commit release metadata separately.
8. Merge release metadata into `main`.
9. Run final gates.
10. Create an annotated tag.
11. Push `main` and the tag only when explicitly requested.

Version checks:

```bash
grep '^version' pyproject.toml
grep '__version__' src/llmgauge/__init__.py
uv run llmgauge --version
```

Annotated tag example:

```bash
git tag -a v0.70.0 -m "LLMGauge v0.70.0"
git push origin refs/tags/v0.70.0:refs/tags/v0.70.0
```

Use semantic version tags.

Do not create nonstandard release tags such as:

- `v0.70-final`
- `v0.70-fix2`
- `v0.71a`

## Required review report

Every substantial feature, documentation, process, audit, validation, or release-preparation task must produce an untracked Markdown report under `tmp/`.

Small read-only inspections do not require a report unless requested.

Required path pattern:

```text
tmp/<task-or-branch-name>-review-report.md
```

The report must remain untracked.

Do not place it under:

- `docs/`
- `results/`
- another tracked directory

The report should include:

- branch and HEAD
- requested scope
- explicit scope boundaries
- files changed
- branch commits relative to `main`
- diff stat and changed files
- commands run
- targeted tests
- full gate results
- real operator validation, when relevant
- generated artifacts inspected
- public/private safety checks
- known limitations
- deferred work
- untracked artifacts created
- final working-tree status
- readiness recommendation

Print the absolute report path at the end of the task.

A report is intended to make the agent’s work easy to inspect after the turn. It is not a substitute for concise final reporting.

## Chat response discipline

Keep interactive chat output concise.

The untracked review report is the authoritative detailed record of repository work. Do not duplicate its full contents in chat.

During a task, only send an update when:

- a blocker requires user input
- a destructive or externally visible action requires approval
- a real model command requires review before launch
- a significant defect or scope conflict is discovered
- the requested scope cannot be completed as written

Do not narrate routine:

- file inspection
- repository orientation
- successful commands
- passing tests
- repeated status checks
- implementation details already captured in the review report

Do not paste full test output, diffs, logs, or generated artifacts into chat unless the user requests them or a failure needs diagnosis.

Normal progress updates should be short and decision-oriented.

The final chat response should summarize only:

- what was completed
- important findings
- failures or limitations
- repository state
- readiness recommendation
- absolute review-report path

Avoid repeating:

- the original task
- the project identity
- settled product decisions
- complete command histories
- full test lists
- full file lists already present in the review report

## Context and usage discipline

Use repository context economically.

- Do not use subagents, delegated scouts, or parallel agent tasks unless the user explicitly authorizes them.
- Read only files directly relevant to the requested change.
- Do not reread broad project documentation when `AGENTS.md` and the task provide sufficient context.
- Do not repeat settled product decisions in analysis, reports, or chat.
- Stop repository orientation once the relevant implementation path and tests are identified.
- Do not produce speculative designs for explicitly deferred features.
- Do not inspect every potentially related module merely for completeness.
- Prefer one focused implementation objective per turn.
- Run targeted tests while developing and the full suite once before final handoff.
- Do not rerun successful full gates without a concrete reason.
- Keep review reports concise and evidence-oriented.
- Summarize commands and results rather than pasting complete successful output.
- Record only decisions made during the current task; link or reference existing documentation for established policy.
- Treat token and tool usage as project resources. Additional investigation must have a clear expected effect on correctness.

Unless the task requires more detail, review reports should stay under approximately 150 lines.

## Final task report

After completing the requested scope, report:

- branch name
- final HEAD
- requested scope
- files changed
- commands run
- targeted test results
- full pytest result
- Ruff result
- `git diff --check` result
- real-run validation, when applicable
- known limitations
- deferred work
- untracked artifacts
- working-tree status
- readiness recommendation
- absolute review-report path

Do not bury failures or partial validation.

## CLI compatibility

LLMGauge is CLI-first.

Preserve existing:

- command names
- aliases
- option names
- defaults
- exit codes
- dry-run behavior
- output artifact contracts

unless the task explicitly changes them.

When changing CLI behavior:

- Add or update CLI tests.
- Inspect `--help` output manually.
- Preserve compatibility aliases where practical.
- Keep destructive behavior explicit.
- Prefer bounded options over arbitrary passthrough.
- Use `--dry-run`, `--check`, `--yes`, or `--force` where appropriate.
- Use hyphenated user-facing command and option names.
- Keep errors clear and actionable.
- Do not silently change defaults with compatibility implications.

## Configuration and model profiles

User-owned YAML must be treated carefully.

When reading or writing config and model-profile files:

- Preserve unknown fields.
- Do not silently remove user data.
- Validate before writing.
- Reject ambiguous mutation requests.
- Avoid destructive changes without explicit confirmation.
- Do not hard-code private machine paths.
- Do not hard-code model locations.
- Do not hard-code GPU or VRAM assumptions.
- Preserve `extra="allow"` behavior where user-owned configuration models rely on it.
- Keep setup and config behavior local-first.
- Do not download models or build llama.cpp automatically.

Known acceptable limitation:

YAML comments may not be preserved by structured writes unless comment-preserving YAML support is deliberately introduced.

Machine-specific paths belong in ignored local configuration files.

## Result artifacts

Result directories are evidence.

Do not mutate them unless an explicit command applies:

- scoring
- validation
- reporting
- export
- another documented artifact operation

Preserve:

- raw prompts
- raw model output
- cleaned output
- stderr logs
- VRAM telemetry
- scheduler traces when explicitly captured
- runtime metadata
- failed attempts
- scores
- reports

Rules:

- Raw output is authoritative source evidence.
- Cleaned output is a derived review aid.
- Do not convert failed runs into successful runs.
- Do not hide failed attempts.
- Do not rewrite original runtime settings.
- Validation should report problems rather than silently repair artifacts.
- Public export must not mutate the source result.
- Missing optional provenance must not invalidate otherwise usable legacy artifacts unless the schema explicitly requires it.

## Local and public artifact boundaries

Local evidence and public exports have different disclosure requirements.

Local result artifacts may retain information needed for debugging and reproduction, subject to existing schema redaction rules.

Public artifacts must be copied into a separate export and sanitized.

Public export must:

- never mutate the original result
- redact usernames and home-directory paths by default
- redact hostnames
- redact model directories
- redact executable directories
- omit unrelated environment data
- avoid duplicated full prompts in command metadata
- preserve evaluation-relevant settings
- produce a redaction summary
- validate the exported result
- warn that human review is still required

Never intentionally capture or export:

- API keys
- authentication tokens
- passwords
- credential-bearing URLs
- unrelated environment secrets

Shortened public fingerprints are display identifiers, not substitutes for full cryptographic identity.

## Schema compatibility

Prefer additive schema changes.

Non-breaking changes generally include:

- optional fields
- optional artifacts
- warnings
- additional report sections
- new enum values that older readers can treat as unknown
- more informative validation that does not reject previously valid artifacts

Breaking changes include:

- new required fields
- renamed or removed fields
- changed field types
- changed field semantics
- moved required artifacts
- changed score semantics
- making previously valid legacy results fail

Older valid v0.x result directories should remain supported through 1.0 unless they are:

- corrupted
- unsafe
- technically impossible to interpret

Do not build a large migration framework without a demonstrated user or integration need.

## Model execution

Do not launch real models during normal unit tests.

Use:

- dry-run validation
- mocked runner behavior
- temporary fixtures
- controlled integration tests

when possible.

Before launching a real operator smoke, print and inspect:

- llama.cpp executable path
- model path or model profile
- suite
- prompt selector
- context size
- maximum tokens
- temperature
- batch
- ubatch
- GPU layers
- flash-attention mode
- reasoning mode
- runtime label
- output directory

Do not launch a model until the command and paths are resolved and reviewed.

Do not invent a model path.

Do not assume a specific GPU, CUDA version, llama.cpp build, or GGUF exists.

Public/reference artifacts should use disclosed stock methodology unless a tuned configuration is explicitly part of the evaluation.

## Runtime command construction

Use structured argv.

Do not construct shell command strings for execution.

Do not add arbitrary shell passthrough.

Bound user-facing runtime controls through explicit validated options.

Runtime metadata should distinguish:

- requested behavior
- observed behavior
- unavailable or unknown behavior

Do not claim an effective reasoning mode merely from a requested option.

## Provenance and fingerprints

When implementing provenance:

- Use full SHA-256 locally.
- Use shortened fingerprints for public display where configured.
- Do not treat shortened fingerprints as full identities.
- Cache expensive hashes only with file-identity validation.
- Cache identity should include path, size, modification time, and inode or equivalent identity where available.
- Rehash when file identity changes.
- Mark unavailable provenance as unknown rather than failing usable runs unnecessarily.
- Prefer GGUF metadata over filename inference.
- Mark inferred architecture or quantization clearly.
- Keep mutable review artifacts out of immutable run fingerprints.

Do not implement a whole-result-directory hash manifest unless the product decision explicitly changes.

## Hardware metadata

Hardware capture must remain optional.

A result is valid when hardware metadata is disabled.

Hardware capture modes may include:

- `off`
- `minimal`
- `full`

Do not capture privacy-sensitive machine identity by default.

Exclude or redact:

- hostname
- username
- serial numbers
- private paths
- unnecessary PCI identifiers

Reports must state plainly when hardware disclosure was not captured.

## Fit ladders and retries

Fit and retry workflows must remain explicit and artifact-preserving.

- Do not make adaptive fallback the default for normal runs.
- Preserve every failed attempt.
- Classify failures honestly.
- Preserve requested settings.
- Report the selected working configuration.
- Do not hide OOMs or runtime failures.
- Do not silently reinterpret a fallback as the originally requested run.

## Scoring

Manual scoring remains authoritative.

- Do not overwrite reviewed scores without explicit user intent.
- Auto-draft scores must remain review-required drafts until deliberately applied.
- Keep scoring provenance accurate.
- Keep reviewed and unreviewed states visible.
- Do not silently calculate a full quality claim from partially reviewed repeated trials.
- Deterministic output checks may provide evidence but must not silently determine final manual scores.

## Testing

Tests use `pytest`.

- Add or update tests whenever behavior changes.
- Run focused tests before the full suite.
- Keep tests deterministic.
- Avoid real model dependencies in normal tests.
- Prefer temporary directories and fixtures.
- Assert against generated JSON, YAML, files, command output, and exit behavior.
- Avoid broad snapshots when focused assertions are clearer.
- Test backward compatibility when schemas change.
- Test cache invalidation when caching file hashes.
- Test path redaction and privacy boundaries.
- Test that public export does not mutate source artifacts.
- Test older artifacts when validation behavior changes.

Full gate:

```bash
uv run pytest
uv run ruff check .
git diff --check
```

## Documentation

Documentation should be practical, precise, and reproducible.

- Avoid hype.
- Avoid universal ranking claims.
- Avoid unsupported currentness claims.
- State limitations plainly.
- Distinguish structural validation from quality review.
- Distinguish manual scores from objective truth.
- Keep commands copy/paste safe.
- Keep examples local-first.
- Do not expose private paths or personal notes.
- Do not describe optional future features as current capabilities.
- Keep release state, roadmap state, and CLI behavior synchronized.

## Code style

- Target Python 3.11 or newer.
- Use 4-space indentation.
- Use type hints for public helpers.
- Prefer clear names.
- Prefer simple functions over speculative abstractions.
- Keep imports minimal and explicit.
- Avoid broad exception swallowing.
- Raise clear `ValueError`, `typer.BadParameter`, or `typer.Exit` errors where appropriate.
- Preserve backward compatibility.
- Keep privacy and artifact behavior explicit.
- Avoid hidden side effects.

## Safety and privacy checks

Before presenting work as complete, inspect for:

- home-directory paths
- usernames
- hostnames
- local model directories
- llama.cpp executable directories
- API keys
- tokens
- secrets
- credential-bearing URLs
- `.env` content
- generated result artifacts
- caches
- local databases
- unrelated personal notes

Use generic searches rather than embedding unnecessary personal identifiers in tracked project guidance.

Examples:

```bash
git grep -n "/home/" || true
git grep -n "/Users/" || true
git grep -ni "api[_-]key" || true
git grep -ni "token" || true
git grep -ni "secret" || true
git grep -ni "password" || true
git grep -n "Projects/local-llm" || true
git status --short --branch
```

Interpret matches carefully. A matching word in documentation or a test fixture is not automatically a leak.

## Completion checklist

Before presenting work as ready:

- Requested scope is complete.
- Unrequested work was not added.
- Tests pass.
- Ruff passes.
- `git diff --check` passes.
- CLI help renders where relevant.
- Existing aliases still work.
- Backward compatibility was tested where relevant.
- No unexpected version bump was included.
- No unrelated files were staged.
- No generated results were committed.
- No temporary review reports were committed.
- No secrets or private paths were introduced.
- User-owned YAML fields remain preserved.
- Destructive behavior requires explicit confirmation.
- Original result artifacts remain preserved.
- Public export does not mutate its source.
- Real operator validation was performed when required.
- The review report exists and remains untracked.
- The final working-tree state is clearly reported.
- PR, merge, push, release, tag, and cleanup actions were performed only when explicitly requested.
