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
> Solve the named problem. Make the smallest correct change. Prove that change.
> Stop.

A milestone must be bounded, independently inspectable, testable, and mergeable.
Use a focused branch rather than editing `main`. Closing or replacing a session
does not justify creating another branch for the same unfinished milestone. Keep
architecture or contract definition, meaningful dependency admission,
implementation, presentation, publication, and release preparation separate
when they create distinct durable boundaries.

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
- **Create or continue** — exact working branch to create or continue.
- **Goal** — one bounded outcome.
- **Canonical sources** — only contracts needed for the milestone.
- **Required delta** — observable changes and acceptance criteria.
- **Milestone-specific non-goals** — nearby work intentionally excluded.
- **Special validation** — checks beyond this file's defaults.
- **Report path** — exact ignored `tmp/*-review-report.md` path.
- **Subagents** — explicit authorization or `none`.
- **Git boundary** — the exact instruction: `Do not stage, commit, merge, or
  push. Leave all changes unstaged and uncommitted.`

Stable security, privacy, reporting, and validation rules from this file need
not be repeated. The Git boundary above must be explicit in every handoff. Keep
model recommendations and client-specific orchestration commands outside
repository handoffs.

A handoff cannot silently authorize scope expansion, dependency admission,
contract changes, destructive Git operations, model execution, network access,
or publication.

## Session and subagent policy

Default: one primary agent, one integrated session, no subagents. Every handoff
must explicitly authorize subagents or state `none`.

Start a new session for a new milestone or to resume unfinished work after its
prior session closes. Keep direct review corrections and validation fixes in
the same session and branch. A fresh continuation session must receive exactly:
`This is a fresh session. First inspect the current unstaged branch state and
the existing report. Do not restart or reimplement completed work.` Session
closure alone never authorizes a replacement branch.

Keep tightly coupled schema, lifecycle, recovery, protocol, containment, or
security work in one integrated session. Use slices only for genuinely
independent, non-overlapping work. Slicing must not split one invariant or
accepted contract across competing owners.

When explicitly authorized, the primary agent may use at most two narrow,
read-only subagents for independent research. Editing subagents require
authorized, isolated, non-overlapping file ownership. The primary agent remains
responsible for integration, validation, and the report; subagents must not
evade scope, validation, responsibility, or the human Git gate.

## Scope and architecture discipline

Before editing, perform a minimal preflight:

1. verify the named baseline, branch, synchronization requirement, and tree
   state;
2. identify the named outcome, accepted contracts, allowed files, acceptance
   criteria, required validation, and protected user artifacts;
3. classify admission explicitly as `PASS` or `FAIL`.

Preflight must not read the repository broadly or run broad tests. Read only
the named sources and directly relevant references. `PASS` admits only the
smallest safe implementation slice. `FAIL` admits no implementation; report the
blocker under the centralized fail-closed policy. When implementation is not
admitted because architecture or contract work is required first, use a
separate, explicitly handed-off architecture-only branch rather than mixing
architecture and implementation.

Reuse existing patterns; do not create a second convention beside an
established one. Prefer small, explicit, deterministic changes and boring
designs. Fix root causes. Remove obsolete in-scope code without aliases, shims,
or misleading comments. Do not perform unrelated cleanup or abstraction.

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

Live tests against real models or providers are human-controlled. Agents may run
an inspected, bounded command only with explicit authorization. Scripted
transports are allowed for deterministic protocol and failure-path tests; label
them synthetic, keep fixtures bounded and secret-free, and never present them
as live-provider evidence.

Provider diagnostics may retain only bounded structured facts needed to
classify the failure:

- HTTP status, normalized content type, provider error code, rejected field or
  parameter, and closed error category;
- selected model, request byte count, and tool count;
- event names, output-item types, terminal-event presence, and action count;
- admitted and observed resource limits.

Never retain raw provider payloads, arbitrary provider messages, prompts,
repository contents, tool arguments, raw headers, credentials, tokens, JWTs,
or account or workspace identifiers. A generic HTTP 400 or other unclassified
provider error cannot justify a behavior, fallback, compatibility, or contract
change; reproduce and classify the cause first.

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

Preflight is the minimal admission check defined above. When synchronization
matters, compare local `main`, `origin/main`, and `origin/HEAD`; inspect existing
untracked files before creating a branch. Use offline, repository-local,
noninteractive commands with timeouts. Do not install packages or write outside
the repository for routine validation.

Testing must be proportional to the changed boundary. Run deterministic focused
tests during implementation. Run the full suite only for repository-wide impact
or an explicit governing requirement. Never replace a failed required gate with
a narrower passing check. Documentation-only work uses focused Markdown, link,
command, cross-reference, and diff checks unless Python tests are required.

Test observable contracts, boundaries, invariants, transitions, precedence,
and real errors—not source text or incidental implementation. Use temporary
directories and fixtures; avoid real models. Test backward compatibility,
cache invalidation, redaction, source immutability, and failure preservation
when those boundaries change.

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

Never rerun a successful broad gate unless later production changes invalidate
it. Record every required check and its actual result. Distinguish stale
failures that were directly corrected and rerun from the final corrected state;
do not describe an earlier failure as current or omit it from validation
history.

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
milestone must end with the required untracked `tmp/` report. Small read-only
inspections need no report unless requested. About 150 lines is the normal
ceiling unless evidence requires more.

Use these six core sections:

1. **State** — branches and HEADs; admission; subagent authorization and actual
   use, normally `none`; staged, unstaged, and untracked state; readiness for
   human review.
2. **Changes** — scope, exact files, diff stat, and concise summary.
3. **Validation** — commands, actual results, omitted required checks with
   reasons, and stale corrected failures distinguished from final state.
4. **Findings and residual risks** — decisions, completed and deferred scope,
   corrections, unresolved findings, assumptions, risks, and artifacts.
5. **Outcome** — final `PASS` or `FAIL`; no `PASS` with unresolved Critical,
   High, or Medium findings or unavailable required validation.
6. **Next gate** — smallest exact human action and final working-tree state.

For a direct correction after the report exists, append a small dated follow-up
section describing only the correction, affected validation, resulting outcome,
and next gate; do not rewrite history or duplicate the full report. Do not
include secrets, private identifiers, full private hashes, raw prompts or model
outputs, oversized logs, or complete successful test output. The report must be
the last intentional task artifact, remain untracked, and have its absolute path
printed in the final response.

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
Create or continue: docs/clarify-score-review
Goal: Clarify that assisted score drafts require human review.
Canonical sources: AGENTS.md; docs/PUBLIC_REPORTING.md; docs/SCORING_RUBRICS.md
Required delta: Align current scoring language and add one Unreleased entry.
Milestone-specific non-goals: No CLI, schema, or scoring behavior changes.
Special validation: Check changed links and contradictory scoring claims.
Report path: tmp/clarify-score-review-report.md
Subagents: none
Git boundary: Do not stage, commit, merge, or push. Leave all changes unstaged and uncommitted.
```

## Completion rule

Stop as soon as acceptance criteria pass and required evidence is recorded.
Proceed to the human Git gate only when the scope is complete, affected
callsites/tests/docs are updated or intentionally unchanged, validation passed
honestly, the diff is bounded, no secrets or generated results are tracked, and
the untracked report is the last intentional task artifact. Recommend a commit
message if useful; never stage or commit it.
