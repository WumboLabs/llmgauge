# AGENTS.md

Canonical policy for AI coding tools, assistants, and automated editors working
on LLMGauge. `AGENT` means the active coding tool, regardless of harness or
model. This file is self-contained and is the single authority for agent-assisted
development workflow, responsibility, Git boundaries, scope, validation,
reports, compatibility, security, and evidence handling.

## Project identity

LLMGauge is a conservative, local-first Python CLI for evaluating local models
on real consumer hardware. It prioritizes evaluation quality, reproducibility,
artifact integrity, stable command behavior, and defensible evidence over
feature volume or architectural novelty.

It evaluates usefulness, honesty, technical correctness, safety, instruction
following, completion quality, speed, VRAM use and headroom, reproducibility,
and real workflow fit.

LLMGauge is not:

- a cloud evaluation service or hosted multi-user platform;
- a hosted leaderboard or universal model-ranking system;
- a model downloader or hardware tuning tool;
- an agent framework, hidden automatic judge, or telemetry service;
- a replacement for human quality or publication review.

Structural validation is not answer-quality validation. Manual scores are
review metadata, not universal truth. Comparisons summarize bounded evidence;
they are not global recommendations. Auto-draft scoring is review-required
triage.

## Repository map and canonical product sources

- Package: `src/llmgauge/`
- CLI entry point: `src/llmgauge/cli.py`
- Commands: `src/llmgauge/commands/`
- Shared CLI helpers: `src/llmgauge/cli_common.py`
- Evaluation logic: `src/llmgauge/core/`
- Runtime integrations: `src/llmgauge/runners/`
- Bundled and editable suites: `src/llmgauge/builtin_suites/`, `suites/`
- Tests: `tests/`
- User documentation: `docs/`
- Ignored review and result artifacts: `tmp/`, `results/`

Product and artifact contracts live in `README.md`, `docs/DESIGN.md`,
`docs/ROADMAP.md`, `docs/PUBLIC_REPORTING.md`,
`docs/ARTIFACT_SCHEMAS.md`, `docs/FIT_LADDER.md`, and accepted focused contract
documents referenced by `docs/DESIGN.md`. `CHANGELOG.md` records shipped and
Unreleased changes. These documents define product behavior; this file alone
defines agent workflow. If canonical sources conflict, follow the fail-closed
policy instead of choosing silently.

## Governing workflow

> One milestone, one branch, one agent, one report, one human Git gate.

A milestone must be bounded, independently inspectable, testable, and mergeable.
Use a focused branch rather than editing `main`. Keep architecture or contract
definition, meaningful dependency admission, implementation, presentation,
publication, and release preparation as separate milestones when they create
distinct durable boundaries.

The agent may:

- verify the expected baseline and inspect task-relevant history;
- create and switch to the explicitly named working branch after proving the
  working tree is safe;
- inspect relevant code, tests, documentation, and artifacts;
- edit only the accepted milestone scope;
- run non-destructive validation and inspect generated artifacts;
- correct findings from its complete final-diff review;
- write the required untracked review report.

The human exclusively controls:

- staging and unstaging;
- commits and commit amendment;
- merges and branch deletion;
- pushes and remote configuration;
- tags and releases;
- destructive Git actions and history changes.

Agents must leave tracked changes unstaged and uncommitted. They must not merge,
push, tag, release, delete branches, rewrite history, or stage files unless the
user explicitly overrides the relevant boundary for one task. Passing checks
does not authorize a Git gate.

Do not use destructive Git operations such as `git reset --hard`, forced branch
updates, history rewriting, aggressive cleanup, or unreviewed branch deletion.
Do not pull, fetch, switch, or create branches blindly when local changes may be
present. Preserve unrelated and untracked user work.

Pull requests are optional and only used when explicitly requested. CI may not
exist; missing checks are not passing checks. The normal owner path is local
review, human staging and commit, a human `--no-ff` merge, post-merge validation,
and explicit release work later.

## Compact handoffs

Every repository handoff must contain exactly the information needed to execute
the bounded milestone:

- **Repository** — repository path or identity.
- **Expected baseline** — branch, commit, synchronization, and expected tree
  state.
- **Branch** — exact working branch to create or use.
- **Goal** — one bounded outcome.
- **Canonical sources** — only contracts needed for the milestone.
- **Required delta** — observable changes and acceptance criteria.
- **Milestone-specific non-goals** — nearby work intentionally excluded.
- **Special validation** — checks beyond this file's defaults.
- **Report path** — exact ignored `tmp/*-review-report.md` path.
- **Subagents** — explicit authorization or `none`.

Stable workflow, Git, security, privacy, reporting, and default validation rules
from this file must not be repeated in every handoff. Keep model recommendations
and model-selection instructions outside repository handoffs. Do not place
client-specific orchestration or session commands such as `/new` or `/slice`
inside a handoff.

A handoff cannot silently authorize scope expansion, dependency admission,
contract changes, destructive Git operations, model execution, network access,
or publication.

## Session and subagent policy

Default: one primary agent, one integrated session, no subagents. Every handoff
must state subagent authorization explicitly; absence of authorization means
none.

Keep tightly coupled schema, lifecycle, recovery, protocol, containment, or
security work in one integrated session. Use slices only for genuinely
independent, non-overlapping work. Slicing is never automatic and must not split
one invariant or accepted contract across competing owners.

When explicitly authorized, the primary agent may use at most two narrow,
read-only subagents for independent research. Editing subagents are exceptional:
the handoff must authorize them, their file ownership must be isolated and
non-overlapping, and the primary agent remains responsible for integration,
validation, and the report. Never use subagents to evade scope, validation,
responsibility, or the human Git gate.

## Scope and architecture discipline

Before editing, establish:

1. requested outcome and expected baseline;
2. smallest safe implementation slice;
3. canonical files and accepted contracts;
4. observable completion criteria and validation;
5. whether real operator validation is required;
6. untracked or user-owned artifacts that must be preserved;
7. adjacent work that remains deferred.

Inspect before changing. Read only relevant sections. Reuse existing patterns;
do not create a second convention beside an established one. Prefer small,
explicit, deterministic changes and boring designs. Fix root causes. Remove
obsolete in-scope code without leaving aliases, shims, or misleading comments.
Do not perform unrelated cleanup or speculative abstraction.

Architecture-first sequencing is required for public APIs, CLI contracts,
result or configuration schemas, persistence formats, external runtimes,
meaningful dependencies, security boundaries, lifecycle ownership, and
long-lived integrations:

1. accept the contract;
2. admit any meaningful dependency in a separate milestone;
3. implement the accepted contract;
4. add presentation or integration separately;
5. prepare publication or release separately.

Implementation must not silently reopen an accepted contract. Do not add
hypothetical backends, broad migration frameworks, arbitrary runtime argument
passthrough, external execution frameworks, or dependencies without a concrete
accepted need. Never broaden a focused task into release work, model tuning,
automatic scoring, TUI work, hosted services, or publication.

## FAIL: centralized fail-closed policy

Verdict must be `FAIL`, not a reduced or improvised `PASS`, when any of these
conditions applies:

- the expected branch, commit, synchronization, or working-tree baseline is
  incorrect;
- canonical documents conflict on a decision material to the milestone;
- requested work would violate an accepted contract;
- completion requires unauthorized scope expansion;
- completion requires a forbidden or unauthorized schema, dependency, public
  API, or compatibility change;
- a required capability, tool, runtime, artifact, permission, or source is
  unavailable;
- required security, privacy, evidence-integrity, or compatibility guarantees
  cannot be preserved;
- required validation cannot be performed or reported honestly.

Stop before making unsafe changes when the blocker is known. Preserve evidence,
complete any independent safe inspection, and report the exact blocker, what
was verified, and the smallest materially different next milestone. Never hide,
retry away, document around, rename, wrap, mock, or special-case an unresolved
failure. No partial implementation, placeholder, stub, or deferred promise may
be presented as completion.

## Local-first, offline-safe, and runtime boundaries

Default behavior must remain local, offline-safe, explicit, and non-destructive.
Do not introduce automatic model downloads, telemetry, cloud services, hosted
judges, network submission, background agents, external databases, or hardware
mutation. Do not install or modify drivers, CUDA, packages, firewalls, clocks,
GPU state, or host configuration. Do not add network behavior by default.

LLMGauge may integrate only with explicitly accepted local runtimes. Respect
runtime lifecycle ownership: do not install, launch, supervise, or mutate an
external service unless its accepted contract and milestone explicitly require
it. Use structured argv, never shell command strings or arbitrary shell
passthrough. Bound user-facing controls with explicit validated options.

Do not launch real models in normal tests. Prefer dry-run validation, temporary
fixtures, and mocked runners. Before any authorized real operator smoke, print
and inspect the executable, model/profile, suite, prompt selector, context,
maximum tokens, temperature, batch, ubatch, GPU layers, flash-attention,
reasoning mode, runtime label, and output directory. Do not invent paths or
assume hardware, CUDA, runtime builds, or model files.

Runtime metadata must distinguish requested, observed, unavailable, and unknown
behavior. A requested mode is not proof that it became effective. Do not hide
nonzero exits, signals, startup failures, retries, OOMs, readiness failures, or
partial output.

## CLI and configuration compatibility

Preserve public command names, aliases, option names, defaults, exit codes,
dry-run behavior, stdout/stderr ownership, signals, and artifact contracts unless
the accepted milestone changes them. CLI changes require focused tests and
manual `--help` inspection. Prefer hyphenated user-facing names, actionable
errors, bounded options, and explicit `--dry-run`, `--check`, `--yes`, or
`--force` controls where appropriate.

Treat user-owned YAML as data, not scaffolding:

- preserve unknown fields and existing `extra="allow"` behavior;
- validate before writing and reject ambiguous mutation requests;
- require explicit confirmation for destructive changes;
- do not hard-code private paths, model locations, GPUs, or VRAM assumptions;
- keep machine-specific paths in ignored local configuration;
- never download models or build runtimes automatically.

Structured YAML writes may lose comments; do not claim comment preservation
unless deliberately supported.

## Evidence and artifact integrity

Generated results are records, not scratch files. Do not mutate or delete
user-created result artifacts except through an explicit documented artifact
operation. Preserve:

- raw prompts, model stdout, stderr, logs, and original runtime settings;
- cleaned output as a clearly derived review aid;
- telemetry and scheduler traces when captured;
- every failed attempt, exit code, and honest failure classification;
- scores, reports, provenance, and requested versus selected settings.

Raw evidence is authoritative. Cleaned output never replaces it. Never convert a
failed run into success, hide an attempt, silently repair an artifact, or
reinterpret fallback settings as the original request. Validators report
problems; they do not repair user evidence.

Fit and retry workflows must be explicit, opt-in, bounded, reproducible, and
artifact-preserving. Adaptive fallback is not the normal-run default. Preserve
all attempts, stop according to the accepted policy, report the selected working
configuration, and keep substantial GPU-layer fallback explicit. A fitting
fallback does not prove the requested configuration worked, global optimality,
or answer quality.

Generated reports, comparisons, export indexes, and validation are evidence
summaries or structural checks. They do not prove correctness, safety, model
quality, publication readiness, or universal rank. Preserve source-of-truth and
regeneration rules documented in `docs/ARTIFACT_SCHEMAS.md`.

## Schema and provenance compatibility

Prefer additive schema evolution. Normally safe changes are optional fields,
optional artifacts, warnings, and informative validation that keeps previously
valid artifacts valid. Breaking changes include required fields, renamed or
removed fields, changed types or semantics, moved required artifacts, changed
score meaning, or rejection of valid legacy results.

Support older valid v0.x result directories through 1.0 unless corrupted,
unsafe, or technically impossible to interpret. Importers must check
`schema_version`, tolerate unknown optional fields, and avoid assuming one
repository or application data directory. Do not build a migration framework
without demonstrated need.

For provenance:

- use full SHA-256 locally; shortened fingerprints are display identifiers, not
  full identities;
- validate cached hashes against path, size, modification time, and inode or an
  equivalent file identity, and rehash when identity changes;
- prefer GGUF metadata over filename inference and label inference clearly;
- record unavailable provenance as unknown when the artifact remains usable;
- exclude mutable review artifacts from immutable run fingerprints;
- do not add a whole-result-directory hash manifest without an accepted product
  decision.

Fingerprints do not prove model quality, authorship, hardware identity, or the
byte integrity of transformed public exports.

## Scoring and claim boundaries

Manual scoring is authoritative. Do not overwrite reviewed scores without
explicit intent. Auto-draft scores remain review-required drafts until a human
deliberately reviews and applies them. Preserve scoring provenance and make
reviewed, unreviewed, partial, and missing states visible. Deterministic output
checks may supply evidence but must not silently become final quality scores.

Do not calculate or imply full quality from partially reviewed repeated trials.
Compare quality only across like-for-like runs with equivalent prompts and
disclosed model, hardware, runtime, suite, context, generation settings, and
scoring status. Reports may support claims about the tested configuration only;
they must not imply universal rank, untested safety or performance, daily-driver
reliability, or broad recommendations from one run.

## Privacy and public export

Never intentionally capture, expose, report, fixture, or publish API keys,
tokens, passwords, credential-bearing URLs, unrelated environment secrets, or
private machine identity. Inspect changes and generated artifacts for usernames,
hostnames, home paths, model and executable directories, serial numbers, and
unnecessary device identifiers.

Hardware capture remains optional; results are valid when it is disabled. Modes
may be `off`, `minimal`, or `full`, but privacy-sensitive identity must not be
default metadata. State when hardware disclosure was not captured.

Public exports are separate sanitized derivatives and must never mutate their
canonical private source. Public export must redact usernames, home paths,
hostnames, model directories, executable directories, and unrelated environment
data; avoid duplicated full prompts in command metadata; preserve relevant
settings; omit unknown files safely; and produce a redaction summary. Keep the
private source for audit.

Sanitization is not proof that all private data is removed. Every public export
requires human review before publication. Preserve provenance without claiming
that a source fingerprint authenticates transformed export bytes.

## Validation discipline

At the start of substantial work, inspect rather than infer:

```bash
git status --short --branch
git rev-parse HEAD
git log --oneline --decorate --graph --max-count=20
git diff --check
```

Compare local `main`, `origin/main`, and `origin/HEAD` when baseline synchronization
matters. Inspect existing untracked files before branch creation. Use offline,
repository-local, noninteractive commands with timeouts; do not install packages
or write outside the repository for routine validation.

Behavior changes require deterministic focused tests. Test observable contracts,
boundaries, invariants, transitions, precedence, and real errors—not source text
or incidental implementation. Use temporary directories and fixtures; avoid
real models. Test backward compatibility, cache invalidation, redaction, source
immutability, and failure preservation when those boundaries change.

Verification must match the work:

- investigation: run the experiment and preserve its output;
- CLI: exercise parsing, help, output ownership, exits, signals, and artifacts;
- persistence or schema: validate atomicity, reopen behavior, identity, and
  legacy artifacts;
- runtime integration: validate lifecycle, readiness, isolation, cancellation,
  and requested-versus-observed evidence;
- public export: validate source immutability, redaction, provenance, and human
  review boundaries;
- documentation: check changed links, commands, cross-document consistency, and
  Markdown quality;
- real operator behavior: inspect the resolved command before launch and the
  generated artifacts afterward.

Run focused checks during development, then the full project gate once per
milestone when proportional:

```bash
uv run pytest
uv run ruff check .
git diff --check
```

Do not rerun a successful full gate unless later production changes invalidate
it. Documentation-only corrections after a full gate need proportional Markdown,
link, version, lint, and diff checks. Never claim a check ran unless its actual
result was observed.

Before reporting, inspect the complete diff and final status for scope expansion,
contract violations, duplicated authority, compatibility regressions, unsafe
defaults, stale docs, unrelated files, hidden dependencies, leaks, process or
resource leaks, partial-output behavior, and insufficient failure handling.
Correct every in-scope Critical, High, or Medium finding before `PASS`.

## Release and publication boundaries

Feature work must not change release metadata. Release preparation is a separate,
explicit milestone after accepted feature work. Version files, lockfiles,
changelog release sections, commits, merges, annotated tags, pushes, and releases
remain human-controlled unless one boundary is explicitly delegated for one
task. Do not invent nonstandard version tags.

Publication is also separate. Public evidence requires validated artifacts,
manual review, disclosed tested conditions and scoring status, bounded claims,
and inspection of the sanitized derivative. Never publish or submit by default.

## Required review report

Every substantial feature, documentation, process, audit, validation, or release
milestone must end with one untracked Markdown report under the exact handoff
path in `tmp/`. Small read-only inspections need no report unless requested.
The report is the authoritative detailed handoff and must remain untracked.
Approximately 150 lines is the normal ceiling unless evidence genuinely needs
more.

Use these seven core sections:

1. **State and verdict** — explicit `PASS` or `FAIL`; starting branch and HEAD;
   working branch and current HEAD; staged, unstaged, and untracked state;
   readiness for human commit review.
2. **Subagents** — authorization, actual use, role, and file ownership; state
   `none` when none were used.
3. **Changes** — requested scope, files added/modified/removed, diff stat, and
   concise implementation or documentation summary.
4. **Architecture and safety decisions** — contracts followed, compatibility,
   privacy, artifact integrity, decisions made, corrections from self-review,
   and generated/source artifacts inspected.
5. **Validation** — exact commands and actual results; focused checks, full gate,
   Ruff, `git diff --check`, operator validation, and any check not run with the
   reason.
6. **Scope and residual risks** — completed, deferred, blocked, and unsupported
   work; external assumptions; intentional omissions; remaining Critical, High,
   and Medium findings; residual risks and untracked artifacts.
7. **Next gate** — exact recommended human action and final working-tree status.

A report cannot say `PASS` with unresolved Critical, High, or Medium findings or
with dishonest or unavailable required validation. Do not include secrets,
private identifiers, full private hashes, raw prompts or model outputs,
oversized logs, or complete successful test output. Write the report as the
final file-writing action and print its absolute path in the final response.

## Code and communication standards

Target Python 3.11 or newer. Use four-space indentation, minimal explicit
imports, and type hints for public helpers. Prefer clear names and simple
functions over speculative abstractions. Avoid needless allocation, copying,
computation, and broad exception swallowing. Raise clear `ValueError`,
`typer.BadParameter`, or `typer.Exit` errors where appropriate.

Keep agent chat concise and evidence-based. Send progress only for blockers,
approval needs, real-model launch review, material defects, or scope conflicts.
Do not paste routine inspection, successful logs, complete diffs, or report
contents unless requested or needed to diagnose failure. The final response
states completion, important findings or limitations, repository state,
readiness, and the absolute report path.

## Documentation standards

Write practical, precise, reproducible documentation without hype or unsupported
currentness claims. Distinguish structural validation from quality review,
manual scores from objective truth, and current capability from roadmap work.
Keep examples local-first, copy/paste safe, and free of private paths. Do not add
documentation frameworks or broad cleanup outside the milestone.

## Compact LLMGauge handoff example

```text
Repository: /path/to/llmgauge
Expected baseline: main @ <commit>; clean; main and origin/main synchronized
Branch: docs/clarify-score-review
Goal: Clarify that assisted score drafts require human review.
Canonical sources: AGENTS.md; docs/PUBLIC_REPORTING.md; docs/SCORING_RUBRICS.md
Required delta: Align current scoring language and add one Unreleased entry.
Milestone-specific non-goals: No CLI, schema, or scoring behavior changes.
Special validation: Check changed links and search for contradictory scoring claims.
Report path: tmp/clarify-score-review-report.md
Subagents: none
```

## Completion rule

Stop for the human Git gate only after the requested scope is complete, affected
callsites/tests/docs are updated or intentionally unchanged, required validation
has passed honestly, the final diff is clean and bounded, no secrets or generated
results are tracked, and the untracked report is the final file written.
Recommend a commit message if useful; never stage or commit it.
