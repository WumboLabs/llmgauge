# Result Validation v0

`llmgauge validate-result` performs structural validation on a LLMGauge result directory.

## Command

    uv run llmgauge validate-result results/example-run

## Checks

- `llmgauge-result.json` exists and parses as JSON.
- Required top-level sections exist:
  - `schema_version`
  - `llmgauge_version`
  - `run`
  - `model`
  - `runtime`
  - `suite`
  - `summary`
  - `results`
- `results` is a list.
- Each prompt result includes required fields:
  - `prompt_id`
  - `category`
  - `status`
  - `raw_prompt_path`
  - `raw_output_path`
  - `stderr_log_path`
  - `exit_status`
  - `metrics`
- Raw prompt, raw output, and stderr log artifacts exist.
- If `cleaned_output_path` is present, the cleaned output artifact exists.
- Prompt IDs are unique.
- `summary.completed` and `summary.failed` match prompt result statuses.
- `score` is either null or a mapping with valid dimensions, label lists, and string metadata fields.
- `model.model_path` remains redacted.

When optional Coding Core native evidence is present, validation additionally
checks:

- the closed portable selection shape, exact result membership/order and count,
  canonical membership, default profile, and named-profile or custom-selection
  semantics;
- complete closed `coding_core` evidence for every selected prompt whenever
  `suite.selection` is represented;
- `suite.prompt_count` and legacy `include`/`only` invocation metadata remain
  consistent with the portable selection;
- exact prompt, response-form, scoring-role, rubric, deterministic-check, and
  hybrid-composition logical identities against `coding-core-v1` `0.1.0`;
- absence of deterministic and hybrid data on manual-only prompts;
- the closed deterministic record and its outcome/evidence/error relationships;
- bounded replay of the accepted static check against the contained
  authoritative `raw_output_path`, using prompt generation status to derive
  `generation_failed`, with exact equality to the persisted deterministic
  record;
- reading at most the accepted static response limit plus one character; that
  bounded over-limit sample is passed through the accepted check so a genuine
  `resource-bound` deterministic error can validate without reading or parsing
  the remainder;
- rejection of missing, escaped, unreadable, or replay-inconsistent raw
  evidence without using cleaned output;
- manual rubric provenance, applicable dimensions, and derived
  `missing`/`unreviewed`/`partial`/`reviewed`/`unscoreable` state;
- exact side-by-side deterministic/manual components and hybrid completeness;
- bounded diagnostics that do not echo raw responses or private physical paths.

These checks use the installed logical suite contract, not the persisted
physical `suite_path`. A malformed represented Coding Core field fails
validation; it is not ignored or repaired.

Genuine legacy results that contain neither `suite.selection` nor per-prompt
`coding_core` evidence remain valid.

When the optional top-level native `transcript` reference is present,
validation additionally checks:

- the exact closed result reference and contained
  `llmgauge.transcript.v0`/`llmgauge.sequential_supplied_feedback` `0.1.0`
  identities;
- transcript artifact hash, bounded JSON load, strict result containment, and
  required source artifact existence/hash;
- unique event, attempt, declared-feedback, state, and branch IDs; unique
  logical-turn IDs except across retries; exact integer per-attempt exit status
  independent of closed attempt state; contiguous canonical event order;
  required first task and final terminal events; and closed event/role/status
  vocabularies;
- backward parent, retry, recovery, state, branch, and source relationships,
  including branch/retry acyclicity and unchanged retry logical-turn identity,
  parent, branch, input state, rendered input, and consumed feedback;
- complete ordered feedback-plan identity, origin, schedule, exact content,
  lifecycle and disposition; actual supply-event consistency; scheduling order;
  unreached and supplied-unconsumed non-consumption; and exact reciprocal
  consuming-turn association on every attempt;
- completion state, actor, reason, selected branch, and final response
  consistency;
- source/derivative, availability, capture, truncation, redaction, and
  duplicate-authority consistency;
- declared turn, attempt, and feedback limits;
- null existing prompt score, closed non-numeric review hooks, exact suite/task
  relationship, and prompt compatibility link; and
- the transcript-aware immutable run fingerprint when present.

These checks establish represented structure only. They do not establish
semantic correctness, execution of supplied feedback or generated content,
safety, model quality, human approval, publication readiness, or Agent Harness
success.

When the optional top-level `agent_harness_evidence` reference is present,
validation additionally checks:

- the exact closed result reference and contained
  `llmgauge.agent_harness_evidence.v0` contract `0.1.0` identities;
- the dedicated import shape: `run.operation: agent_harness_import`, empty
  native results, zero prompt summary counts, and no native transcript;
- bounded evidence JSON loading, strict result containment, exact evidence-file
  hash, and no dependence on the original external source path;
- fixed session/object paths, regular-file requirements, unique inventory and
  logical-reference identities, finite counts and byte totals, full member
  hashes, and canonical source-package hash;
- strict OMP session-v3 structure, physical event order, source-entry and tree
  relationships, supported message/custom entry semantics, and exact reference
  mappings;
- normalized trajectory, command/tool request-start-terminal lifecycle,
  availability, completeness, terminal, model, and repository-state
  consistency without replay or inference;
- imported-session and evidence identity recomputation; and
- the imported-evidence canonical run fingerprint when present.

These checks establish private source containment, represented structure,
integrity, and internal consistency only. They do not establish harness task
success, repository correctness, tests passing, model quality, scoreability,
sanitization, or publication readiness.


## Compatibility expectations

Validation must remain additive for the v0.x result schema line. Missing
optional provenance, identity, fingerprint, runtime-command, or future public
export fields must not invalidate an older result directory that otherwise
passes structural validation.

Unknown optional fields are tolerated where the containing object is already a
free-form artifact object. This preserves forward compatibility for importers
and avoids forcing migrations for older local evidence.

Validation may add warnings or more specific diagnostics, but it should not make
previously valid v0.x artifacts fail unless the artifact is corrupted, unsafe to
interpret, or technically impossible to interpret.

Reasoning-mode metadata is compatibility-sensitive:

- v0.66 artifacts may contain `runtime.reasoning_mode`
- future artifacts may add `runtime.reasoning_mode_requested`
- older artifacts may omit both
- readers must not treat requested reasoning mode as observed or effective
  behavior

## Non-goals

- Full JSON Schema validation.
- Repairing malformed result directories.
- Scoring output quality.
- Validating model factual correctness.
- Validating compatibility with any specific downstream importer.
- Proving publication readiness or bounded public-claim eligibility.

Passing `validate-result` means artifact integrity and on-disk references look
consistent. Review `report.md` **Audit Checklist** and **Prompt Artifact Audit**
sections, then inspect raw and cleaned outputs before citing claims publicly.


## Score validation details

When an applied prompt `score` object is present, result validation checks:

- `dimensions` is an object when present.
- `failure_labels` and `good_labels` are lists.
- `schema_version`, `scale`, `rubric_id`, `rubric_version`, `reviewer_notes`, `score_rationale`, and `verdict` are strings when present and non-null.

Detailed score template validation is handled by `llmgauge score` before scores are
applied.
