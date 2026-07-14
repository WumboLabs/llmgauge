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

## Agent and human responsibility boundary

Use one agent for each bounded milestone.

The operating rule is:

`One milestone, one branch, one agent, one report, one human Git gate.`

The agent may:

- verify the expected repository baseline
- create and switch to the explicitly named working branch
- inspect relevant files and history
- plan the bounded milestone
- edit in-scope code, documentation, tests, and local configuration
- run non-destructive validation
- inspect and correct its own complete final diff
- write the required untracked review report

The human retains exclusive control over:

- staging
- commits
- merges
- branch deletion
- pushes
- tags
- releases
- remote configuration
- destructive Git operations
- history rewriting

The agent must leave tracked changes unstaged and uncommitted unless the user
explicitly overrides this policy for one task.

Do not use subagents, delegated scouts, or parallel agent tasks unless explicitly
authorized.

## Scope discipline

Before editing, define:

1. the requested outcome
2. the smallest safe implementation slice
3. the canonical files or contracts
4. the observable completion criteria
5. the required validation
6. adjacent work that will remain deferred

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

Each milestone must be independently inspectable, testable, and mergeable.

Keep these as separate milestones when they introduce distinct durable
boundaries:

- architecture or contract definition
- dependency admission
- implementation
- presentation or integration
- publication
- release preparation

Do not combine:

- architecture and implementation
- dependency admission and production behavior
- feature work and release metadata
- unrelated cleanup and a bounded correction
- several integration layers in one uncontrolled change

When a milestone contains dependent work, implement it in focused slices.

## Architecture-first sequencing

Use architecture-first sequencing when work introduces or changes:

- public APIs
- CLI contracts
- result or configuration schemas
- persistence formats
- external runtimes or services
- meaningful dependencies
- security or permission boundaries
- lifecycle ownership
- long-lived integration formats

Preferred sequence:

1. define the contract or ADR
2. admit any meaningful dependency separately
3. implement the accepted contract
4. add presentation or additional integration layers
5. perform release or publication work separately

Implementation must follow accepted contracts rather than silently reopening
them.

If implementation reveals a genuine contradiction or missing contract, stop and
report the exact blocker instead of changing the architecture implicitly.

## Lean handoff standard

Task handoffs should contain only:

- repository and expected baseline
- branch to create
- one bounded milestone
- essential canonical context
- required observable behavior
- hard constraints
- explicit out-of-scope work
- validation commands
- report path
- exact expected next action

Stable workflow rules belong in `AGENTS.md` and should not be repeated in every
handoff.

Do not include session commands, model-selection commands, `/new`, `/slice`, or
orchestration instructions inside repository handoffs.

State each instruction once.

Do not over-prescribe implementation details before repository inspection unless
they are already canonical or required for compatibility, privacy, security, or
correctness.

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

For normal milestone work:

1. Read `AGENTS.md`.
2. Verify the expected repository baseline.
3. Create and switch to the explicitly named branch.
4. Inspect only task-relevant code, tests, and canonical documentation.
5. Define the smallest correct change.
6. Patch only relevant files.
7. Add or update focused tests.
8. Run targeted validation.
9. Inspect generated artifacts when behavior changes.
10. Run the full project gate when proportional and practical.
11. Inspect the complete final diff adversarially.
12. Correct all in-scope findings.
13. Create the required untracked review report as the final file-writing action.
14. Leave tracked changes unstaged and uncommitted.
15. Stop for human review.

Run the full suite once per milestone unless a later production-code correction
materially invalidates that result.

Documentation-only corrections after a successful full gate normally require
only proportional documentation, version, lint, and diff validation.

Use timeouts for commands that may hang.

Recommended checks:

- `uv run pytest`
- `uv run ruff check .`
- `git diff --check`

Before reporting, inspect:

- `git diff --stat`
- `git diff --name-status`
- `git diff`
- `git status --short --branch`

## Human Git gate

The agent must not stage or commit work.

After receiving a PASS report, the human:

1. reads the review report
2. inspects the complete working-tree diff
3. stages only the reviewed files
4. inspects the staged name/status and diff
5. runs `git diff --cached --check`
6. runs the required pre-commit validation
7. commits the bounded milestone
8. switches to `main`
9. merges with `--no-ff`
10. runs post-merge validation
11. verifies the final repository state
12. pushes and deletes the branch only when appropriate

Do not commit:

- generated `results/`
- temporary `tmp/` reports or audit data
- private machine paths
- secrets or `.env` files
- caches
- local databases
- personal notes
- unrelated files

Commit subjects should be concise, imperative, and milestone-specific.

The agent may recommend a commit message in its report but must not execute it.

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
git tag -a v0.70 -m "LLMGauge v0.70"
git push origin refs/tags/v0.70:refs/tags/v0.70
```

Use semantic version tags.

Do not create nonstandard release tags such as:

- `v0.70-final`
- `v0.70-fix2`
- `v0.71a`

## Required review report

Every substantial feature, documentation, process, audit, validation, or
release-preparation milestone must produce an untracked Markdown report under
`tmp/`.

Small read-only inspections do not require a report unless requested.

Required path pattern:

`tmp/<milestone>-review-report.md`

The report must remain untracked.

Do not place it under:

- `docs/`
- `results/`
- another tracked directory

The report must include:

- explicit `PASS` or `FAIL`
- readiness for human commit review
- exact recommended next action
- verified starting branch and HEAD
- working branch and current HEAD
- staged or unstaged state
- requested scope and explicit boundaries
- files added, modified, and removed
- complete diff stat
- decisions made
- implementation or documentation summary
- compatibility impact
- exact validation commands and actual results
- targeted-test results
- full-project gate result
- Ruff result
- `git diff --check` result
- self-review findings
- corrections made
- remaining Critical findings
- remaining High findings
- remaining Medium findings
- residual risks
- external assumptions
- unsupported cases
- real operator validation when relevant
- generated artifacts inspected
- source-artifact integrity when relevant
- privacy findings when relevant
- deferred work
- untracked artifacts created
- final working-tree status

A milestone must not receive PASS with unresolved Critical, High, or Medium
findings.

The report must clearly distinguish:

- completed work
- deferred work
- blocked work
- future recommendations

Do not include:

- secrets
- private usernames
- unnecessary absolute private paths
- full private hashes
- raw prompts
- raw model outputs
- oversized logs
- complete successful test output

Approximately 150 lines is the normal upper bound unless the milestone genuinely
requires more.

Print the absolute report path at the end of the task.

The report is the authoritative detailed record of the milestone. It is not a
substitute for a concise final response.

## Investigation and evidence discipline

Distinguish completed capability from:

- prototypes
- partial implementation
- documentation-only work
- mocks
- special-case success
- unresolved reductions
- moved or renamed problems

Do not claim completion unless the stated observable criteria are satisfied.

When blocked by a missing contract, unavailable capability, unresolved
dependency, unproved assumption, external requirement, or security or
compatibility contradiction:

- record the exact blocker
- preserve the evidence
- stop retrying equivalent approaches
- recommend the smallest materially different next milestone

Ground conclusions in exact files, commands, observed results, reproduction
cases, tests, corrections, residual risks, and remaining gaps.

Avoid vague claims such as:

- `looks good`
- `should work`
- `mostly complete`
- `appears safe`
- `probably compatible`

Do not treat documenting, wrapping, renaming, moving, or abstracting an unresolved
problem as solving it.

## Adversarial self-review

Before reporting, inspect the complete final diff for:

- scope expansion
- contract violations
- duplicated authority
- compatibility regressions
- unsafe defaults
- missing validation
- stale documentation
- unrelated changes
- hidden dependency assumptions
- secret or error leakage
- resource or process leaks
- partial-output behavior
- insufficient failure handling

Apply checks specific to the changed boundary.

Examples:

- CLI: parsing, stdout/stderr ownership, exit codes, signals, partial output
- API: malformed inputs, bounds, timeouts, cancellation, redaction
- persistence: atomicity, rollback, reopen behavior, identity mismatch
- runtime integration: lifecycle ownership, readiness, request isolation,
  cancellation, telemetry semantics, startup versus request evidence
- public artifacts: source immutability, redaction, provenance, trust boundaries

Correct all in-scope findings before assigning PASS.

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

- Read only files directly relevant to the requested change.
- Do not reread broad project documentation when `AGENTS.md` and the task provide
  sufficient context.
- Do not repeat settled product decisions in analysis, reports, or chat.
- Stop repository orientation once the implementation path and tests are known.
- Do not produce speculative designs for explicitly deferred features.
- Do not inspect every potentially related module merely for completeness.
- Prefer one focused implementation objective per milestone.
- Run targeted tests while developing and the full suite once before final
  handoff when proportional.
- Do not rerun successful full gates without a concrete reason.
- Keep review reports concise and evidence-oriented.
- Summarize commands and results rather than pasting complete successful output.
- Record only decisions made during the current task.
- Treat token and tool usage as project resources.
- Use large context only for a concrete repository-wide need.
- Keep numeric model context limits and billing thresholds out of tracked
  repository policy; those belong in operator configuration.

## Unattended-run discipline

Before substantive work, inspect the planned workflow for commands likely to
trigger approval.

For unattended runs:

- use repository-local paths
- use existing project dependencies
- prefer offline commands
- avoid network access
- avoid writes outside the repository
- avoid package installation
- avoid privileged or host-modifying commands
- avoid destructive Git operations
- use noninteractive command forms
- request unavoidable approval before implementation begins

Do not begin a long run that is predictably unable to finish under the current
permission policy.

When an unexpected approval interruption occurs, record:

- the exact command
- the reason approval was requested
- whether it is a normal project operation
- whether the task or permission profile should change

Do not recommend unrestricted permissions without a bounded operational need.

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
