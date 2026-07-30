# Multi-turn Transcript Architecture

## Status and scope

Status: accepted architecture and evidence contract for native multi-turn
evaluation. This document completes Full Model Testing milestone 2a.

This contract defines the identity, ordering, state, feedback, completion,
scoring, privacy, compatibility, comparison, and validation boundaries that
must exist before LLMGauge can represent or run a native multi-turn evaluation.
It adds no schema, suite content, fixture, package resource, CLI behavior,
conversation runner, feedback execution, repair loop, scoring implementation,
validator, report behavior, import path, runtime behavior, package version, or
release behavior.

The governing authorities remain the [General Evaluation Taxonomy](GENERAL_EVALUATION_TAXONOMY.md),
the [Full Model Testing Capability Architecture](FULL_MODEL_TESTING_CAPABILITY_ARCHITECTURE.md),
and the existing artifact, result, validation, Coding Core, reporting,
fingerprint, export, and privacy contracts. This document specializes those
authorities for native multi-turn evidence; it does not reopen them.

Admission is **PASS** for this contract-only milestone. Native multi-turn
evaluation remains unavailable until separately accepted representation and
implementation milestones are complete.

## Capability identity and boundary

Native multi-turn evaluation is a distinct, versioned **native response**
capability. Its evaluated subject is a model participating in an
LLMGauge-owned, bounded conversation protocol under disclosed model, runtime,
generation, state, feedback, limit, and termination conditions. A transcript is
not merely a list of otherwise independent responses: the protocol must preserve
which observable state and feedback each response consumed.

It remains separate from:

- ordinary native single-turn response evaluation, whose existing prompt and
  result contracts remain authoritative;
- a coding task domain, which describes task content rather than interaction
  structure;
- generated-code, patch, test, command, or tool execution;
- an autonomous coding agent, repository-editing agent, or general agent loop;
- imported WumboLabs Agent Harness agent-environment evidence;
- official external coding benchmarks and their datasets, harnesses, and
  metrics;
- model runtime transport and external-runtime lifecycle ownership;
- scoring presentation, reports, comparisons, and public export; and
- publication or network submission.

LLMGauge may eventually own a bounded conversation protocol and may supply
feedback admitted by that protocol. That ownership does not make LLMGauge a
repository-editing agent, general tool executor, model-runtime supervisor, or
external harness. Any future execution that produces feedback requires its own
accepted containment, provenance, failure, and lifecycle contract.

A coding task can use this capability later without changing the capability's
primary native-response class. Likewise, a static Coding Core response does not
become multi-turn evidence because its prompt contains inert compiler or test
text.

## Conversation identity and version

Every transcript requires a stable evaluation identity sufficient to determine
what protocol ran and whether another consumer supports it. The conceptual
identity includes:

- a conversation or protocol identity and a protocol version;
- suite and task identity and version when a suite owns the task;
- the selected profile or the exact ordered task selection, without relabeling
  custom selection as a named profile;
- an immutable identity for the initial observable state and task material;
- model, model-artifact, runtime, transport, template, generation-setting, and
  relevant hardware provenance, preserving requested facts separately from
  observed facts;
- declared turn, time, retry, feedback, and termination limits;
- transcript completion and terminal state; and
- enough producer and schema/protocol compatibility information to reject an
  unsupported material version safely.

This list fixes semantic identity, not final schema field names. A later schema
contract must assign one authority to each fact and define which facts are
inline, referenced, required, or optional.

Material changes to turn construction, state exposure, feedback production,
retry policy, termination, or scoring meaning require a new protocol version.
Consumers must fail closed for unsupported required versions. They may preserve
and report an unsupported transcript as opaque evidence, but must not validate,
score, compare, or reinterpret it under another protocol. Unknown optional
metadata remains tolerable only where the owning future schema declares that it
does not change interpretation.

## Ordered turn model

A transcript is an append-only ordered evidence sequence. At minimum it
represents:

1. the initial task or user turn and its visible initial state;
2. every model response attempt, including failed or malformed attempts;
3. each feedback item or observation admitted between responses;
4. the exact later model turn that consumed each feedback item;
5. every observable protocol-state transition;
6. the response selected as the final response, if one exists; and
7. the terminal event and reason.

Each turn has a stable identity that is unique within the conversation and is
not derived solely from its current list position. The transcript also preserves
a canonical total order. Identities are immutable: correction, retry, recovery,
or import may append a linked record but may not reuse an identity or overwrite
an earlier turn. The protocol must reject duplicate identities, gaps where a
required item is absent, order conflicts, forward references that violate the
protocol, and references to unknown turns or feedback.

A model turn must identify the observable message/state input it consumed.
Feedback must identify its creation or observation position and its exact
consuming model turn. Merely placing feedback somewhere before a response is
not sufficient association. Unconsumed feedback remains explicit and cannot be
silently attributed to the final response.

The final response is an explicitly designated preserved model response, not a
cleaned rendering or reconstructed concatenation. A transcript assembled from
missing, reordered, deduplicated, or silently replaced turns is partial or
invalid evidence and cannot qualify as a complete transcript.

## Observable state preservation

The protocol must preserve enough observable state to reconstruct what each
model turn was asked to consume without claiming access to private model
reasoning. Required concepts are:

- the immutable initial task and initial-state identity;
- the exact rendered messages or authoritative references supplied to each
  model turn;
- the accumulated prior visible messages and accepted feedback;
- the visible state before and after each state-changing protocol action;
- the association between an accepted feedback item and the transition it
  caused;
- bounded protocol-control state that affects selection, limits, or
  termination;
- the terminal observable state; and
- the last preserved state for partial, interrupted, or failed transcripts.

Inline snapshots, content-addressed references, or a replayable transition log
may represent state only after a later schema contract chooses one authority and
defines integrity and availability requirements. A mutable path alone is not a
stable initial-state identity.

Visible and hidden state must be bounded explicitly. Visible state is content
rendered or otherwise supplied to the model. LLMGauge-owned hidden protocol
state may include counters, selection state, and termination controls, but must
be disclosed as protocol metadata when it affects behavior. Provider-internal
state, private model reasoning, hidden chain of thought, and undisclosed runtime
state are neither required evidence nor facts LLMGauge may claim to possess.
Only observable protocol inputs, outputs, transitions, and disclosed controls
are evidence under this contract.

## Feedback provenance and authority

Every feedback item must preserve:

- a stable feedback identity and its origin class;
- exact source content or an immutable authoritative artifact reference;
- creation, supply, or observation order;
- the producing action and its provenance when an action produced it;
- the exact model turn that consumed it, or an explicit unconsumed state;
- whether it is authoritative source evidence or a derivative;
- whether the claimed producer actually executed or the content was merely
  supplied as inert evidence; and
- truncation, capture failure, redaction, or availability state.

Origin classes must distinguish at least:

- a deterministic LLMGauge-owned check admitted by a future versioned contract;
- compiler, test, static-analysis, tool, or runtime output with execution and
  environment provenance;
- an LLMGauge-owned protocol observation that did not execute model-generated
  content;
- operator-provided feedback;
- imported external-harness feedback; and
- unavailable or unknown origin, which cannot support an execution claim.

Deterministic feedback is authoritative LLMGauge-owned evidence only when an
accepted method actually produced it under preserved inputs and method version.
Compiler, test, analyzer, tool, or runtime text is execution evidence only when
its producing action and observed outcome are preserved. The same text embedded
in a prompt, pasted by an operator, or imported without sufficient provenance is
inert supplied evidence, not proof that an action ran.

Agent Harness observations remain external harness evidence even when a future
read-only importer exposes them to LLMGauge. Operator feedback remains
operator-authored and must not be relabeled as a deterministic check. If
feedback is unavailable, that absence remains explicit.

A normalized excerpt or synthesized summary may be a derivative review aid. It
must link to its source, disclose transformation and truncation, and never
replace authoritative feedback content. Credentials and secrets must never be
retained to satisfy exact-content preservation; their omission makes the
captured item redacted or partial rather than exact. Other private source
content may be preserved only under a separately accepted privacy contract.

## Completion, termination, retries, and partial evidence

Conversation completion, the actor making a completion claim, and the terminal
reason are separate facts. A protocol must distinguish at least:

- completed conversation under the protocol;
- model-declared completion;
- evaluator-declared completion;
- bounded turn-limit termination;
- timeout;
- nonzero model-runtime or admitted feedback-producer failure;
- malformed model response;
- feedback-generation or capture failure;
- explicit operator stop;
- partial or interrupted transcript;
- retry;
- recovery attempt after admitted feedback;
- abandoned conversation; and
- completed capture whose answer remains unreviewed or unscoreable.

A model declaration does not by itself establish protocol completion. The
protocol's accepted completion rule determines whether an evaluator may mark the
conversation complete. Limit, timeout, runtime failure, malformed response,
feedback failure, operator stop, and abandonment are terminal outcomes unless
the versioned protocol explicitly admits a preserved continuation. They must not
be converted to success because a partial final-looking response exists.

Retries and recovery have different semantics:

- A retry is another preserved attempt at the same logical protocol action from
  the same declared pre-action state, commonly after transport or malformed
  response failure. It may remain in the same conversation when the protocol
  admits it and the pre-state and retry policy are unchanged.
- A recovery turn consumes accepted failure feedback and advances observable
  conversation state. It is not a replacement retry and must retain the failed
  response it addresses.
- Diverging from a prior state with different feedback, controls, or selection
  creates a separately identified evidence branch with an explicit parent and
  branch point when the protocol admits branching.
- Restarting from a changed task, initial state, protocol version, model/runtime
  selection, or independent evaluation invocation creates a new conversation
  identity.

A later schema must represent attempt, parent, branch, and selected-continuation
relationships without permitting silent replacement. Failed, retried,
superseded, branched, recovered, and abandoned attempts remain authoritative
history. A partial transcript may remain useful evidence when its missing and
terminal states are explicit, but it is not a complete transcript and cannot be
scored or compared as though completion occurred.

## Correction and recovery semantics

Correction and recovery are separate evidence from first-response quality. A
future review or scoring contract must be able to preserve and assess, without
conflation:

- initial response quality;
- recognition and faithful use of supplied feedback;
- diagnosis of the observed failure;
- plausibility of the proposed correction;
- whether an observable correction was actually produced;
- regression, repeated error, or introduction of a new failure;
- recovery after one or more failures;
- consistency of claims and actions across turns;
- scope discipline across turns; and
- final-state and final-response quality.

A plausible explanation is not proof of correction. A changed response is not
proof that a compiler, test, tool, or verifier succeeded. Actual correction may
be established only by the authority admitted for that check; otherwise it
remains manually reviewed plausibility. Final quality must not erase poor
initial quality, repeated failures, or excessive recovery cost.

The Coding Core future role `repair/prior-response-test-feedback` remains
multi-turn-only and deferred. This contract does not add it to `coding-core-v1`
`0.1.0`, either profile, the static prompt inventory, or any current suite. Its
prompt, response form, feedback generator, transcript representation, and
scoring behavior require later separately accepted milestones.

## Scoring authority

Multi-turn scoring may later expose distinct evidence or review states for:

- per-turn response quality;
- feedback recognition and use;
- diagnosis and correction quality;
- recovery quality and recovery cost;
- cross-turn consistency and scope discipline;
- final answer or final-state quality;
- transcript structural completeness; and
- incomplete, missing, failed, unsupported, or otherwise unscoreable evidence.

This architecture creates no numeric rubric, weighting, aggregate, threshold,
or schema field. It does not admit a universal multi-turn score. A future
protocol-specific method may define bounded aggregates only after fixing their
meaning and eligibility; reports must still expose the component states and may
not imply universal model quality.

Manual semantic review remains the authority for claims that require judgment,
including correctness, diagnosis quality, correction plausibility, consistency,
and scope discipline, unless a later accepted deterministic method establishes
a narrower fact. Deterministic structural transcript validation establishes
structure only. A deterministic feedback producer may establish its own bounded
observed outcome, such as a versioned check result, but not semantic answer
quality.

Current manual score intent, applied-score authority, deterministic check
outcomes, and side-by-side hybrid evidence remain distinct. Missing or partial
turns, unavailable feedback, unsupported versions, and inconsistent provenance
must produce explicit incomplete or unscoreable states rather than invented
values. No later presentation layer may silently turn those states into zero,
pass, or complete.

## Raw evidence and derivatives

Authoritative native multi-turn source evidence includes the initial task and
state, exact rendered messages, every raw model response attempt, ordered
feedback source artifacts, observable state transitions, runtime and producer
logs required by their contracts, terminal events, and scoring provenance.
Source evidence must retain original failure, truncation, absence, and order.

Artifact roles remain separate:

| Artifact | Role |
|---|---|
| Raw model responses and exact rendered prompts/messages | Authoritative native turn evidence |
| Feedback content and admitted producer artifacts | Authoritative feedback evidence under the producer's declared authority |
| Runtime logs and observed outcomes | Source evidence for bounded runtime and producer claims |
| Cleaned responses and normalized excerpts | Derived review aids |
| Manual and deterministic scoring files | Separate review or method evidence; not replacement turns |
| Reports and comparisons | Derived summaries |
| Export indexes and public exports | Derived indexes or sanitized copies |

Raw ordered transcript evidence is authoritative. Cleaned text, reconstructed
conversation views, summaries, reports, comparisons, and exports must reference
rather than replace source turns and feedback. Regeneration of a derivative must
not mutate its private source.

A future fingerprint contract must define canonical ordering and include the
immutable source facts required to distinguish transcript identity, turns,
feedback, transitions, and completion. Mutable review scores, cleaned text,
reports, comparisons, export indexes, and sanitized exports remain outside the
immutable source fingerprint. This requirement changes no current result
fingerprint algorithm.

## Privacy, sanitization, and publication

Canonical transcript evidence remains local and private by default. Future
capture and export contracts must address user-provided content, source code,
repository and home paths, model and executable paths, tool output, environment
and hardware data, credentials, secrets, operator annotations, and third-party
material.

The protocol must minimize capture to evidence needed for its bounded claim.
Credentials, tokens, passwords, credential-bearing URLs, unrelated environment
secrets, and unnecessary private machine identity must not be intentionally
captured. Operator annotations require explicit provenance and must not silently
modify a source turn or feedback item.

Redaction creates a separately identified sanitized derivative. It must preserve
the source relationship and a bounded redaction summary without asserting that
sanitization is complete. Redaction must never silently alter canonical private
source evidence. If a source cannot be retained safely, the capture must record
that limitation and become partial or unavailable according to the accepted
future contract rather than fabricating exact evidence.

No network publication, upload, submission, telemetry, external database write,
or automatic sharing is admitted. Public derivatives require explicit operator
action and human review under the existing publication boundaries.

## Compatibility with current evidence

This contract is additive and prospective:

- Existing `llmgauge.result.v0` directories remain valid native single-turn
  results. They are not transcripts and must never be reclassified or inferred
  to contain turns, feedback, recovery, or conversation completion.
- Current suites retain their identities, versions, ordered prompts, profile
  meaning, selection behavior, and single-turn evidence authority.
- Current static `coding-core-v1` evidence remains one response per prompt and
  non-executing. Supplied failure text remains inert task material.
- Historical results require no migration, rewriting, transcript wrapper, or
  regenerated fingerprint.
- Existing manual scoring, deterministic structural checks, and side-by-side
  hybrid evidence retain their current authority and meaning.
- Current reports, validators, result fingerprints, comparisons, and exports
  retain current behavior until separately changed under accepted contracts.
- Unknown optional fields remain governed by their owning current schema; this
  document does not broaden tolerance inside closed contract-owned objects.
- A future transcript representation must evolve additively where possible,
  identify its own protocol and compatibility boundary, and preserve old valid
  v0.x artifacts through 1.0 unless they are corrupted, unsafe, or impossible
  to interpret.
- A future Agent Harness import remains a distinct agent-environment evidence
  type and must not be represented as a native LLMGauge transcript.

Future reports and validators must distinguish unsupported transcript evidence
from ordinary valid single-turn evidence. Export behavior must preserve private
source immutability, source/derivative identity, and current redaction rules.
Nothing in this contract authorizes a current schema or behavior change.

## Relationship to Agent Harness evidence

A native LLMGauge multi-turn transcript records a bounded conversation protocol
that LLMGauge owns, including the state and supplied feedback admitted by that
protocol. It measures model responses under that protocol and disclosed runtime
conditions.

A WumboLabs Agent Harness session is **agent-environment** evidence. The harness
remains authoritative for the combined model, agent policy and implementation,
tools, repository and environment state, inspections, edits, commands, tests,
tool observations, failures, retries, recovery, final diff, verifier state,
limits, and terminal outcome. LLMGauge must not reconstruct those facts from a
native conversation or relabel a model-only response as harness success.

The future Agent Harness importer must be read-only. It may preserve, validate,
annotate, score, and summarize supported external evidence under a separately
accepted import contract, but it must not mutate, replay, repair, resume, or
execute a source session. Imported harness feedback retains external provenance;
it does not become LLMGauge-owned deterministic feedback.

This milestone neither defines nor implements the importer. Native multi-turn
and imported Agent Harness records may later be shown side by side only with
their different evaluation classes, subjects, authorities, and scoring meanings
visible. Their outcomes must not be merged into one coding or model score.

## Comparison eligibility

A whole-transcript comparison is eligible only when the comparison method has
established compatibility of:

- native multi-turn evaluation class and conversation protocol identity/version;
- suite/task identity, exact task selection, and immutable initial state;
- model role and disclosed runtime, template, generation, and relevant hardware
  settings, with requested and observed differences visible;
- turn, time, retry, branch, recovery, feedback, and termination limits/rules;
- feedback producer identity/version, authority, availability, and sequence;
- scoring method/version and manual review state; and
- transcript completeness and terminal state.

Comparisons must disclose material differences rather than normalize them away.
A shared protocol does not make different initial states, limits, or feedback
trajectories like for like. When model behavior causes feedback sequences to
diverge, the divergence is evidence: comparisons may use an explicitly defined
common prefix or stratified presentation, but must not force incompatible
trajectories into a misleading aggregate.

Partial, failed, abandoned, retried, and recovered conversations remain visible.
A successful recovery cannot be compared as an ordinary first-turn success, and
a complete transcript cannot be ranked against an incomplete transcript as if
both received identical evaluation opportunity. No comparison supports a
universal model rank, untested safety claim, or Agent Harness outcome.

## Structural validation boundary

A future transcript validator may prove only the represented structural facts,
including:

- supported conversation and protocol identity/version;
- presence and consistency of required task, selection, initial-state, model,
  runtime, and limit provenance;
- unique stable identities and complete canonical ordering of represented
  turns, attempts, feedback, transitions, branches, and terminal events;
- valid references, including feedback production and exact consuming-turn
  associations;
- consistency among completion actor, terminal reason, retry/recovery history,
  final response, and partial state;
- source-versus-derivative separation and source-reference integrity;
- presence and internal consistency of required provenance, truncation,
  redaction, availability, and scoring states; and
- supported compatibility and declared comparison eligibility facts.

Validation must fail closed for malformed represented evidence and unsupported
required versions while preserving previously valid single-turn artifacts.
Structural validation does **not** prove:

- answer, diagnosis, correction, or final-state correctness;
- that code, patches, tests, commands, tools, or feedback producers executed
  successfully beyond separately authoritative observed evidence;
- safety or absence of secrets;
- model quality, agent quality, or universal rank;
- human approval or completed semantic review;
- publication readiness or complete sanitization; or
- Agent Harness validity, verifier success, or terminal success.

Validators report problems; they do not repair, reorder, fill, summarize, or
silently discard source evidence.

## Dependency and milestone split

The accepted Full Model Testing sequence remains:

1. **2a — Multi-turn transcript architecture:** this completed contract-only
   milestone.
2. **2b — Multi-turn schema and native evaluation behavior:** later and
   separately bounded under this contract.
3. **3a — Agent Harness import contract:** later architecture work.
4. **3b — Read-only importer and validation:** later implementation work.
5. **3c — Agent-session scoring and reporting:** later presentation and scoring
   work.

Selecting 2b does not authorize Agent Harness work or combine every native
multi-turn dependency. Before native multi-turn behavior is complete, focused
future handoffs must separately accept and, where applicable, implement:

- transcript schema representation and compatibility behavior;
- task, fixture, and package-resource ownership;
- CLI task/profile selection and dry-run contract;
- native conversation-runner lifecycle, limits, cancellation, and artifact
  atomicity;
- deterministic feedback-generation methods, execution containment, producer
  lifecycle, and failure preservation;
- manual, deterministic, and hybrid scoring methods;
- structural validation and legacy compatibility;
- reporting, comparison, fingerprint, and export presentation;
- the deferred Coding Core repair role and its suite/profile relationship; and
- human-authorized bounded live evidence after deterministic validation passes.

Architecture, dependency admission, schema, fixtures, CLI, runner, feedback
execution, scoring, validation, reporting, integration, bounded live evidence,
publication, and release remain separate gates whenever they create distinct
durable boundaries. No item above is implemented or authorized by this
document. LocalMaxxing remains a parallel unselected lane, Generic Core remains
downstream admitted work, the existing `v0.73` gate remains unchanged, and this
contract makes no release-version decision.
