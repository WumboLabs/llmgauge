# Multi-turn Transcript Schema and Native Evaluation Contract

## Status and admission

Status: accepted representation and implementation contract for Full Model Testing
milestone 2b. It specializes the accepted
[Multi-turn Transcript Architecture](MULTI_TURN_TRANSCRIPT_ARCHITECTURE.md).
The explicitly combined 2b handoff admits contract, schema, native orchestration,
validation, result integration, fingerprinting, reporting, compatibility, tests,
and documentation on one branch. It does not admit Agent Harness work or any
later milestone.

Admission is **PASS**. The representation below is additive, local-only,
non-executing, and compatible with existing `llmgauge.result.v0` ownership.
No dependency or package-resource admission is required.

## One serialized authority

A native conversation has exactly one authoritative serialized transcript:
`transcript/transcript.json`, schema `llmgauge.transcript.v0`. It is a separately
versioned contained artifact referenced by the optional top-level
`llmgauge.result.v0.transcript` object. The transcript's discriminated `events`
sequence is the sole authority for event order, turns, attempts, feedback,
observable state, transitions, retry/recovery, branches, selection, and terminal
facts.

The result reference is a closed discovery and integrity index. Its duplicated
schema, protocol, and conversation identifiers MUST equal the contained
transcript and are not independent authorities. A prompt result may contain
`transcript_event_id` to identify the selected compatibility response; existing
prompt-result fields remain a single-turn-compatible index and MUST agree with
the source event. Reports are derivatives. No other serialized transcript form
is authoritative.

The optional result reference is absent for ordinary single-turn runs. Its
absence MUST NOT cause transcript inference or change historical validation,
fingerprints, reports, scores, comparisons, or exports. Historical results need
no migration. If the optional reference is present, every transcript check is
required and malformed or unsupported evidence fails closed.

Agent Harness evidence is outside this schema and MUST NOT use the native
transcript reference or evaluation class.

## Versions and identities

The initial supported identities are closed:

- transcript schema: `llmgauge.transcript.v0`;
- task document schema: `llmgauge.multi_turn_task.v0`;
- protocol ID: `llmgauge.sequential_supplied_feedback`;
- protocol version: `0.1.0`;
- evaluation class: `native_multi_turn_response`;
- producer ID: `llmgauge` with the installed LLMGauge package version.

Unsupported required identities or versions fail closed. Material changes to
message construction, feedback semantics, retry rules, termination, or event
meaning require a new protocol version.

`conversation_id` is operator supplied, stable within the result, and matches
`[A-Za-z0-9][A-Za-z0-9._-]{0,127}`. Event, attempt, feedback, state, and branch
IDs use the same bounded identifier grammar and are unique in their respective
namespaces. A `turn_id` uniquely identifies one logical model turn; retry
attempts for that turn share it and may not use it for another initial,
continuation, or recovery turn. Logical task IDs additionally admit non-empty
`/`-separated segments to match current suite prompt IDs; absolute, empty, `.`,
and `..` segments are forbidden. Canonical event `sequence` values are
contiguous integers starting at zero; array order MUST equal sequence order.

The transcript identity object records:

- suite ID and version;
- exact task ID and version;
- selection kind `exact_task` and the selected task ID;
- immutable `initial_state_id` and SHA-256 of the initial task material;
- producer ID/version;
- model and runtime provenance relationships, expressed as the fixed result
  JSON pointers `/model` and `/runtime`;
- declared model-turn, retry, feedback, and per-turn timeout limits;
- completion state, actor, terminal reason, selected branch, and optional final
  response event.

The result's model, runtime, and settings remain authoritative for those facts.
The transcript records relationships to them rather than a divergent copy.
Requested runtime settings remain distinct from observed runtime evidence.

## Task document

`llmgauge.multi_turn_task.v0` is a closed, local JSON input document. It contains
`protocol_id`, `protocol_version`, `task_id`, `task_version`, `initial_state_id`,
a closed `limits` object, and ordered `feedback` definitions. The selected suite
prompt is the initial user/task content; `task_id` MUST equal the exact `--only`
selection. Named profile and category selection are not admitted with a
conversation task.

Each feedback definition contains a unique `feedback_id`, exact inert `content`,
`origin`, and one-based `after_model_turn`. Initial origins are
`suite_static`, `protocol_static`, `operator_local`, and `synthetic_test`.
All are supplied inert text. The document cannot name commands, executors,
tools, patches, tests, compilers, or lifecycle actions.

The transcript copies every ordered declaration into its top-level
`feedback_plan`, which is the sole authority for feedback identity, origin,
schedule, exact source content, and lifecycle. Each plan item records one state:
`unreached`, `supplied_unconsumed`, or `consumed`; one matching disposition
reason; the actual supply event ID when supplied; and the exact consuming
logical `turn_id` when consumed. Declaration order is preserved. A feedback
event is only the actual inert supply occurrence and does not duplicate content,
origin, schedule, or consumption authority.

Limits are positive and bounded: `max_model_turns` 1..32,
`max_attempts_per_turn` 1..8, `max_feedback_items` 0..64, and
`per_turn_timeout_seconds` greater than zero and no more than 3600. `--max-turns`
may only reduce the declared model-turn limit. A feedback schedule beyond the
effective limit remains declared with state `unreached` and reason
`scheduling_point_not_reached`; it MUST NOT be omitted or represented as
supplied. Terminal state and reason still describe the actual conversation
outcome.

## Canonical events

Every event has `event_id`, `sequence`, `kind`, `branch_id`,
`source_derivative_role`, and `execution_status`. The initial branch is `main`.
Closed kinds and roles are:

| kind | role | authority |
|---|---|---|
| `task` | `user` | initial task and state identity |
| `model_attempt` | `assistant` | every raw response attempt |
| `feedback` | `evaluator` | supplied inert feedback |
| `state` | `protocol` | observable visible-state snapshot/transition |
| `terminal` | `protocol` | completion and terminal facts |

The first event is exactly one `task`; the last event is exactly one `terminal`.
A transcript contains at least one model attempt. State events provide the one
observable-state authority: each has a unique `state_id`, optional previous
state, backward `caused_by_event_id`, and an authoritative exact visible-message
artifact. Model attempts name a previously established `input_state_id`.

A logical model turn has a unique `turn_id`. Each model attempt for that turn
has a unique `attempt_id`, an attempt state `completed`, `failed`, `timeout`, or
`malformed`, and an exact integer `exit_status` supplied by its runtime adapter.
Attempt state and exit status are independent evidence: a malformed response may
have status `0`, a timeout may have a negative or platform-specific status, and
a runtime failure retains its exact nonzero status. Each attempt also has an
optional backward parent, optional backward `retry_of_event_id`, ordered
consumed feedback IDs, ordered recovery feedback IDs, authoritative raw
rendered-input, raw output, and runtime stderr references, and an optional
cleaned derivative. The first attempt establishes
the logical turn as `initial`, `continuation`, or `recovery`. A retry is a later
attempt in that same logical turn and uses the same `turn_id`, branch, parent,
input-state identity, rendered input, and ordered consumed-feedback identity.
Its `attempt_id` and event ID remain distinct, and `retry_of_event_id` links to
the immediately preceding unsuccessful attempt. A retry cannot target a
completed or unrelated turn. Recovery means a logical turn consumes named
feedback and advances visible state if an attempt completes. No attempt is
replaced or discarded.

The ordered feedback plan preserves every declaration before execution. A
feedback event contains only the stable feedback ID and `supplied_inert: true`;
it exists exactly when the scheduling point was reached and inert feedback was
actually supplied. A supplied plan item names that event. A consumed plan item
also names exactly one later logical model `turn_id`, and every attempt in that
turn MUST name the feedback ID. Consumption means the feedback was supplied in
that turn's rendered input, whether the attempts complete or all fail.
`supplied_unconsumed` has no consuming turn because no follow-up request was
admitted. `unreached` has no supply event or consuming turn because execution
stopped before its scheduling point. Supplied text never proves execution.

Branches are a separately typed relationship index, not a second event order.
Each branch has an ID, optional parent branch, optional backward branch-point
event, and state `active`, `selected`, `superseded`, or `abandoned`. Parent
relationships are acyclic. Exactly one branch is selected for a completed
conversation. The initial implementation emits only selected `main`; the schema
can preserve admitted future branches without changing event authority.

## Artifacts and capture state

All transcript paths are POSIX result-relative references rooted at the result
directory and normally beneath `transcript/`. Loading uses the existing strict
contained-result resolver. Absolute paths, `..`, empty components, traversal,
unreadable files, non-regular files, escaping symlinks, and references outside
the result root are rejected. Every authoritative available artifact carries
its lowercase full SHA-256; validation recomputes it with bounded reads. A path
may be owned by only one transcript fact, preventing conflicting duplicate
authority.

An artifact reference records:

- `path` when available;
- `sha256` when available;
- role `source` or `derivative`;
- availability `available`, `unavailable`, or `redacted`;
- capture state `complete`, `partial`, or `failed`;
- booleans `truncated` and `redacted`.

Available source evidence requires a path, hash, and complete or partial capture.
Unavailable evidence has no path or hash and uses failed capture. Redacted
source evidence has no private content path, sets `redacted: true`, and makes the
transcript partial or abandoned. A derivative MUST name a backward source event
and cannot replace required source evidence. A source cannot claim redaction
while remaining exact and complete.

The native writer preserves exact rendered input for every request, every raw
model stdout or response body made available by the adapter, runtime stderr or
bounded structured failure text, exact adapter exit status, feedback source
content, every visible-state snapshot, and terminal facts. Cleaned output is
always derivative. Failed, empty, partial, and timed-out captures are retained
honestly. For llama.cpp, the status is the runtime subprocess status. The vLLM
adapter has no subprocess status and represents adapter success as `0` and
represented request failure as `1`; this is not claimed as an operating-system
subprocess code.

Artifact loading is data-only. It never executes, imports, evaluates, compiles,
applies, invokes, or replays represented content.

## Native protocol behavior

Before model execution, the native writer materializes the complete ordered
feedback plan and persists each exact feedback source artifact. The resulting
transcript preserves that plan even when execution terminates early. After a
successful model turn reaches a scheduling point, the writer appends one
feedback supply event and marks the corresponding plan item supplied. Before
every attempt in the admitted follow-up logical turn, it marks the item consumed
and preserves the reciprocal feedback association.
On termination, every declaration still pending is finalized as `unreached`;
an item supplied after the final admitted turn remains
`supplied_unconsumed`.

The initial protocol is sequential and non-streaming: one active conversation,
one model request at a time, one selected task, one branch, bounded turns,
bounded attempts, and the existing per-runtime request/subprocess boundary.
Visible state is an ordered message list. Before each request LLMGauge persists
and discloses the exact rendered accumulated state. Successful model text and
then scheduled supplied feedback are appended in canonical order. The next
request consumes that exact state and explicitly names its feedback IDs.

The protocol supports first response, supplied feedback, correction/recovery,
and completion. It preserves nonzero runtime failure, timeout, empty/malformed
response, retries from unchanged state, recovery after feedback, turn limit,
operator stop when represented by an admitted caller, partial state, and
abandonment. Failed attempts remain source events. Limits, runtime failures,
malformed responses, and operator stops cannot become success because text
looks final.

Both runtime paths use their existing one-request interfaces. llama.cpp remains
an LLMGauge-launched subprocess under its current configuration. vLLM remains an
operator-managed loopback service; orchestration neither starts nor mutates it.
Both receive equivalent ordered rendered requests. No generalized transport or
lifecycle refactor is admitted.

Dry-run loads and validates the task, exact suite prompt, limits, and runtime
configuration. It prints declared and effective limits separately, the actual
runtime-conditional deterministic request/supply sequence, the complete
declared feedback plan with origin, schedule, exact content, and reachability,
runtime, model, settings, output plan, and an explicit non-execution statement.
It does not present upper turn limits as requests. It does not create a result
directory, launch llama.cpp, contact vLLM, or execute any content.

## Completion and review state

Closed completion states are `completed`, `partial`, and `abandoned`. Completion
actors are `evaluator`, `model`, `operator`, `protocol`, and `runtime`. Terminal
reasons are `completed`, `turn_limit`, `timeout`, `runtime_failure`,
`malformed_response`, `operator_stop`, `interrupted`, and `abandoned`.
Completion state, actor, and reason MUST be a valid tuple. A completed transcript
uses reason `completed`, has a selected branch, and selects a completed model
attempt as final response. Partial and abandoned transcripts cannot claim
completed terminal reason.

Generation status in `run.status` and prompt-result `status` remains a runtime
capture summary. It is not transcript completion, semantic correctness, manual
verdict, or score.

The transcript contains only future-scoring hooks: scoreability
`unreviewed` or `unscoreable` and closed review states for `per_turn`,
`feedback_use`, `correction`, `recovery`, `consistency`, and `final_response`:
`unreviewed`, `incomplete`, or `unscoreable`. No numeric score, rubric,
automatic semantic judgment, or aggregate is admitted. Existing
`results[].score` is not reinterpreted and MUST remain absent/null for native
transcripts. The deferred Coding Core role
`repair/prior-response-test-feedback` remains absent from `coding-core-v1`.

## Result, fingerprint, and compatibility

The optional result reference fields are `path`, `schema_version`,
`protocol_id`, `protocol_version`, `conversation_id`, and `sha256`. Validation
resolves the contained path, checks the artifact hash, loads the supported
schema, performs all semantic and artifact checks, and verifies the discovery
index and selected prompt-result link.

When no transcript reference exists, the canonical run-fingerprint payload is
byte-for-byte unchanged. When represented, it adds one `transcript` payload
containing schema/protocol/conversation identity, task and initial-state
identity, declared and effective limits, branch relationships, the complete
ordered immutable feedback plan and source hashes, canonical ordered immutable
event identities, attempt states, exact exit statuses and source hashes,
feedback supply occurrences and reciprocal consumption associations, state
transitions, completion/terminal facts, selected final response, and fixed
model/runtime result relationships.
Cleaned derivatives, review state, manual scores, reports, comparisons, export
indexes, sanitized exports, and reviewer annotations are excluded.

Current single-turn scoring and single-run public-export methods do not have a
native multi-turn interpretation contract. They fail closed when a transcript
reference is present rather than silently flattening transcript evidence.
Comparison has an accepted bounded structural contract in
[Transcript Comparison and Review Contract](TRANSCRIPT_COMPARISON_REVIEW_CONTRACT.md);
mixed transcript/single-turn comparison still fails closed. Public exposure of
a comparison is admitted only as the closed allowlist derivative in
[Transcript Comparison Public Export Contract](TRANSCRIPT_COMPARISON_PUBLIC_EXPORT_CONTRACT.md).
`export-index` may expose the non-authoritative transcript discovery index and
validation result. Ordinary single-turn behavior is unchanged.

## Structural validation boundary

Validation rejects unsupported versions; malformed closed objects or vocabulary;
non-integer represented exit status; noncontiguous order; duplicate IDs, events,
paths, or conflicting authorities; missing task/model/terminal events; invalid
kind/role pairs; unknown, cyclic, or invalid forward
parent/retry/recovery/branch references; unrelated logical-turn ID reuse; retry
changes to turn, branch, parent, input state, rendered input, or consumed
feedback; retries of completed or nonpreceding attempts; missing, duplicated,
reordered, or contradictory feedback declarations; invalid plan
state/disposition combinations; supply before schedule; supply events absent
from or inconsistent with the plan; unreached feedback represented as supplied
or consumed; supplied-unconsumed feedback naming a consumer; consumed feedback
without exact reciprocal association on every attempt; inconsistent state
transitions or initial state; invalid terminal/completion/final response;
partial/abandoned inconsistency; artifact containment, availability, hash, role,
capture, truncation, or redaction errors; protocol-limit violations; and
scoring-hook or result-link inconsistencies.

Passing validation establishes represented structure only. It does not prove
semantic correctness, code or feedback execution, safety, model quality, human
approval, complete sanitization, publication readiness, or Agent Harness
success. Supplied feedback remains inert. LLMGauge executes no generated
content, commands, patches, compilers, tests, analyzers, or tools in this
protocol. Partial and failed transcripts remain evidence but are not complete
success. No universal multi-turn score exists.
