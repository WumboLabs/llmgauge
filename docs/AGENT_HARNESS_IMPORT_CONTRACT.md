# Agent Harness Import Contract

## Status and admission

Status: accepted architecture and evidence contract for Full Model Testing order
3a, implemented by the bounded read-only importer in order 3b. It specializes
the accepted [general evaluation taxonomy](GENERAL_EVALUATION_TAXONOMY.md) and
[Full Model Testing Capability Architecture](FULL_MODEL_TESTING_CAPABILITY_ARCHITECTURE.md).
It also fixes the separation from the accepted
[native multi-turn architecture](MULTI_TURN_TRANSCRIPT_ARCHITECTURE.md) and
[native transcript schema contract](MULTI_TURN_TRANSCRIPT_SCHEMA_CONTRACT.md).

Admission is **PASS** for one additive external-evidence model. This document
selects identity, authority, containment, compatibility, lifecycle, privacy,
result, fingerprint, validation, scoring, comparison, and failure boundaries.
The order 3b implementation provides the schema, importer command, contained
package, structural validation, and imported-evidence fingerprint integration.
It deliberately provides no runner, score, Agent Harness report, comparison,
export, package resource, publication, or release behavior.

The decision is deliberately narrow: LLMGauge may later ingest one supported
WumboLabs OMP Agent Harness session as preserved read-only external evidence.
Import is evidence ingestion, not session continuation. Agent Harness remains
the producer of the source session; LLMGauge remains the owner of import
validation and any later, separately contracted evaluation decision.

## Evidence class and versioned identity

Imported Agent Harness evidence is a distinct evaluation and evidence class.
The initial identities are closed:

| Concept | Exact identity |
|---|---|
| Evidence `schema_version` | `llmgauge.agent_harness_evidence.v0` |
| Evidence `contract_version` | `0.1.0` |
| Evaluation class | `external_agent_environment` |
| Imported source type | `wumbolabs_omp_session` |
| Source format | `wumbolabs.omp.session_jsonl` |
| Supported source format version | integer `3` only |
| Source producer | `wumbolabs.omp` |
| Importer | `llmgauge.agent_harness_importer` |
| Owning result schema | `llmgauge.result.v0` |

The normalized evidence records the installed LLMGauge version as the importer
version. It records the harness implementation version when the admitted source
provides it; otherwise that version has an explicit availability state and no
value is invented. The fixed producer ID identifies the admitted source family,
not proof of an unavailable build version or authorship claim.

A containing result represents exactly one imported session and may carry
exactly one optional top-level `agent_harness_evidence` reference. A result with
that reference is a dedicated external-agent import result: it has no native
`transcript` reference and synthesizes no native prompt result. Multiple
sessions require separate results. This contract does not generalize the field
to arbitrary external evidence.

These identities MUST NOT be replaced by `native_multi_turn_response`,
`llmgauge.transcript.v0`, native feedback events, or native transcript runtime
ownership. A material change to source semantics, normalized evidence meaning,
or authority requires a new evidence schema or contract version. A new source
format or foreign harness requires a separately accepted source identity.

## Source authority and self-contained package

The future importer uses one arrangement: it copies every admitted source byte
needed by the imported claim into the owning LLMGauge result. A mutable external
path or live harness store is never the sole long-term authority.

The contained layout is fixed:

```text
agent-harness/
  evidence.json
  source/
    session.jsonl
    objects/
      sha256/
        <64-lowercase-hex-digest>
```

`agent-harness/source/session.jsonl` is the exact admitted session source. Each
available out-of-line source artifact or blob is copied once as exact bytes to
its content-addressed object path. `evidence.json` contains a unique source-file
inventory and maps source logical artifact or blob references to those contained
objects. Several logical references may map to the same digest; one logical
reference may not map to conflicting bytes. No other path is source authority.

`session.jsonl` is always required. Every logical source reference in an
admitted entry must either resolve to one copied object or carry a
source-explicit allowed absence, unavailability, or redaction state. If the
source claims bytes are available but they cannot be safely copied and verified,
import fails. Unreferenced objects in an external blob store are not discovered
or imported.

Every unique copied file inventory entry records its contained relative path,
role, byte count, and `sha256` as 64 lowercase hexadecimal characters.
The fixed session member uses role `session_log`; content-addressed members use
role `source_object`.
`source_package_sha256` uses the same digest form and is computed over a
canonical JSON array of those entries, sorted by contained path. Canonical JSON
is UTF-8, has recursively sorted object keys, uses `,` and `:` separators
without insignificant whitespace, and has no trailing newline. The member
hashes bind the exact bytes; the package hash binds the inventory. Source
reference mappings and explicit loss states are bound separately by the
imported evidence identity and run-fingerprint projection.

Authority is layered, not duplicated:

1. The harness-owned artifacts are the provenance origin. At import time they
   establish the source facts and bytes.
2. After atomic publication, the digest-bound contained copies are the private
   canonical source authority for the imported result. Later validation reads
   only those copies, never the original external locations.
3. `evidence.json` is authoritative for LLMGauge's normalized identity,
   source-reference mapping, availability classification, lifecycle mapping,
   and validation state. It does not replace or repair source facts.
4. Sanitized exports, reports, scores, comparisons, indexes, and reviewer notes
   are derivatives. They never replace the contained source package or
   normalized evidence.

A source-side redacted export may be admitted only when the source marks the
redaction or exclusion explicitly. Its copied bytes then establish only the
redacted fact, not the missing original content. LLMGauge never edits a source
copy in place and never describes a transformed derivative as exact raw source.

## Imported session identity and availability

The normalized evidence has two stable identities:

- `imported_session_id` is a `sha256:<64 lowercase hex>` digest over the
  canonical identity projection containing the source type, source format and
  version, producer ID and producer-version availability, source session/run
  ID, and source package SHA-256.
- `evidence_id` is a `sha256:<64 lowercase hex>` digest over the imported
  session ID, evidence schema and contract versions, evaluation class,
  importer ID and version, and the immutable normalized mapping projection.
  The projection includes source references, availability and loss states,
  identities, repository-state evidence, command/tool lifecycle facts,
  model/runtime provenance, and source terminal facts represented by the import.
  Mutable import time, external locator, review, score, report, comparison, and
  export fields are excluded.

Both identity projections use the canonical JSON encoding defined for the source
inventory. Ordered source and trajectory collections retain their defined
physical or logical order; sets are represented as sorted lists. The projection
excludes its own digest field.

The source session/run ID is required for this admitted v3 source. A missing or
invalid ID is malformed source; LLMGauge does not derive one from a filename,
path, timestamp, repository, or final answer. Reimporting unchanged source with
the same importer contract produces the same identities regardless of input or
result location.

The identity record preserves, with source references and availability:

- harness producer identity and implementation version;
- source session/run ID, source format, and source-package identity;
- task identity and task material identity when represented;
- model/checkpoint identity when represented;
- runtime, provider, and transport identity when represented;
- repository identity and initial/final state evidence when applicable;
- source start and end timestamps or states when represented;
- selected branch or leaf when the harness designates one;
- terminal source-session outcome and its evidence;
- every copied source artifact hash; and
- importer identity and version.

All normalized optional facts use one closed availability vocabulary:

| State | Meaning |
|---|---|
| `available` | The admitted source directly carries the value or exact bytes. |
| `absent` | The supported source format permits omission and no value is present. |
| `unknown` | No authoritative value can be established from the complete admitted source. |
| `unavailable` | The source says evidence existed, but its value or bytes were not retained or supplied. |
| `redacted` | The source explicitly removed the value or bytes for privacy or policy. |
| `unsupported` | An optional source representation is present but this evidence version assigns it no semantics. |

An availability state is not a value. Empty output is not absent output;
redacted is not unknown; unsupported is not malformed. `unsupported` is allowed
only for an extension that the v3 format defines as optional and non-semantic to
required identity, order, references, lifecycle, or outcome. Otherwise the
whole source is unsupported and import fails closed.

## Repository-state evidence

Repository evidence is a list of zero or more source-backed repository
observations. Each observation has a stable local ID, source references, and
separate availability for every fact. One repository may be marked primary only
when the source does so. No repository is inferred merely because a command,
path, or task text resembles repository work.

When represented by admitted source evidence, an observation may record:

- repository path exactly as observed, as private metadata only;
- credential-free remote identity and the source form from which it came;
- branch or detached state;
- initial and final `HEAD` object IDs;
- dirty state at each captured point;
- staged, unstaged, and untracked state separately;
- initial and final diffs, with exact source-member references and hashes;
- worktree-change or patch artifacts, with their source roles preserved;
- repository snapshot or manifest hashes, including algorithm and declared
  scope; and
- capture point, ordering, and relationship to the session trajectory.

A mutable filesystem path is never repository identity. A remote URL is an
observed source fact, not proof of ownership or content. A Git object ID proves
only the committed object graph named by that ID; it does not prove branch
position after capture, remote equivalence, a clean index, a clean worktree,
untracked-file absence, submodule state, ignored files, or the complete dirty
worktree.

Dirty, staged, unstaged, and untracked states remain distinct. A Boolean dirty
marker does not establish which bytes changed. Initial and final state are
independent observations: neither may be derived from the other. A patch or diff
proves only its captured bytes and declared basis; it does not prove that it was
applied, that it is complete, or that it equals final repository state.
Repository snapshot or manifest hashes retain their source-declared algorithm
and scope. LLMGauge does not upgrade them into whole-worktree identities.

If the harness captured a diff, patch, manifest, or snapshot, the importer
preserves that source artifact. It never regenerates it from the current
filesystem. Imported repository paths are not dereferenced during normalization
or validation. The importer never runs Git, checks out an object, applies a
patch, or performs destructive reconstruction to fill a missing fact.

## Command and tool evidence

Command and tool evidence preserves source order, identity, arguments,
lifecycle, outputs, and availability without execution. Each normalized fact
points to an admitted source record or contained source member.

Lifecycle stages are independent:

- a command or tool **request** establishes only that an actor requested it;
- a **started** event establishes actual dispatch only when the harness source
  records that lifecycle transition;
- output observations establish only the bytes and stream represented;
- a terminal event establishes the source-recorded completion, failure,
  timeout, denial, interruption, cancellation, or unavailable result; and
- an absent terminal event remains non-terminal or unknown according to source
  facts and may not be converted to success.

The normalized aggregate `lifecycle_state` is one of `requested`, `started`,
`completed`, `failed`, `timed_out`, `denied`, `interrupted`, `cancelled`,
`unavailable`, or `unknown`. `requested` and `started` are non-terminal.
`completed` is only the harness-recorded terminal completion and retains the
independent exit status or tool result; it is not semantic task success.
`denied` may follow a request without a start. `unknown` is used only when the
supported source cannot establish a later state. State progression must be
supported by ordered source events; output alone does not advance it.

The import preserves, when represented:

- requested command text or structured arguments, without reparsing them into a
  stronger invocation claim;
- the exact command or tool invocation that the harness records as started;
- tool name, invocation ID, call arguments, and parent/source relationships;
- stdout and stderr separately, including exact empty output;
- integer exit status, signal, timeout, or harness-native failure evidence;
- denied actions and the actor or policy recorded by the source;
- explicit missing, unavailable, redacted, and truncated output states; and
- request, start, observation, and terminal ordering for each lifecycle.

Truncation records that retained bytes are incomplete and preserves any
source-declared original size or truncation reason; LLMGauge never reconstructs
the omitted bytes. An exit status is meaningful only with its source-recorded
terminal lifecycle. A denial is not execution. A request is not dispatch.
Model prose, a final answer, or command-shaped text claiming that a command ran
is not execution evidence. Execution requires an admitted harness event or
artifact carrying the applicable lifecycle fact.

Tool arguments and output remain inert data. Validation may check identifiers,
ordering, references, states, sizes, hashes, and lifecycle consistency. It never
replays a command, invokes a tool, applies output, or contacts the environment to
confirm an assertion.

## Model interaction evidence

The source trajectory remains an agent-environment trajectory, including its
physical record order, logical tree IDs, parent links, branches, retries, and
harness lifecycle records. The normalized evidence may index, with exact source
references and visibility classification:

- user or task input;
- system and developer instructions when available and allowed to be retained;
- user-visible and model-visible messages;
- model/assistant messages and any source-designated final answer;
- tool-call requests and tool results;
- retries, alternative branches, selections, and recovery attempts;
- runtime or provider failures;
- token, timing, and runtime metadata when the source records them; and
- requested versus observed model/provider/runtime facts separately.

Normalized interaction visibility is one of `user_visible`, `model_visible`,
`user_and_model_visible`, `harness_internal`, `redacted`, or `unknown`, and
requires a source-backed mapping. Source-declared message roles are preserved;
roles are never guessed from content. Harness lifecycle records remain harness
events rather than fabricated messages. `harness_internal` permits only
admitted lifecycle metadata, not hidden message or reasoning content.

The assistant final answer exists only when the source explicitly designates or
unambiguously types it under the admitted v3 semantics. The importer does not
select the last assistant-looking message as final. Branches are retained and
are not flattened into one fabricated linear success trajectory.

Private chain of thought, hidden reasoning, provider-internal reasoning,
provider-internal payloads, and messages not allowed for import are excluded.
They are neither required nor normalized. The importer does not infer them from
summaries, token counts, redaction markers, or visible responses. A source that
contains prohibited hidden/private material must be replaced by a source-side
export that explicitly marks the exclusion, or import fails; LLMGauge does not
silently copy or rewrite that material.

## Separation from native multi-turn evidence

Native transcript evidence and imported Agent Harness evidence have different
owners and semantics:

- `llmgauge.transcript.v0` is LLMGauge-owned native execution evidence under a
  bounded LLMGauge conversation protocol.
- `llmgauge.agent_harness_evidence.v0` is externally produced
  agent-environment evidence whose repository and tool lifecycle belong to the
  harness source.
- Neither authority replaces, repairs, or upgrades the other.
- Each requires its own source, lifecycle, containment, validation, scoring,
  comparison, and reporting semantics.

Conversation-like records, multiple model messages, retries, feedback, or tool
results do not make an Agent Harness session a native transcript. Imported
records never use native transcript feedback events, native execution status,
native runtime ownership, prompt-result compatibility links, or native terminal
semantics.

A future contract may permit explicit ID-based cross-references between a native
transcript and imported evidence. No cross-reference exists in this version. No
automatic conversion to native transcript authority exists. If a future importer
creates a normalized conversational view, that view remains a derivative of the
contained harness source and cannot become `llmgauge.transcript.v0` evidence.

## Lifecycle, completeness, and terminal states

Four decisions remain separate from source-session outcome: import outcome,
structural validation, scoreability, and publication readiness. Evidence
completeness is also separate from whether the task succeeded.

The closed source-session outcomes are:

- `completed`;
- `failed`;
- `partial`;
- `interrupted`;
- `timed_out`;
- `denied`;
- `operator_stopped`;
- `abandoned`; and
- `unknown`.

The outcome requires a source-backed mapping. A polished final answer does not
establish `completed`. Absence of a terminal record does not establish
`abandoned`; it is `unknown` unless the source explicitly supports another
mapping.

The closed import outcomes are:

- `completed` — a new package was atomically published and passed structural
  validation;
- `already_imported` — the requested destination already contains the same
  valid evidence identity and source-package identity, so nothing was changed;
- `unsupported_source` — source family, format, version, entry semantics, or
  required extension is outside this contract;
- `malformed_source` — a recognizable supported v3 source violates required
  structure, identity, ordering, or references; and
- `failed` — reading, privacy admission, containment, copying, hashing,
  validation, or atomic publication failed for another reason.

Validation outcome is `passed`, `failed`, or `not_run`. A published result must
have import outcome `completed` and validation outcome `passed`; failure
attempts do not publish those values in a result. Evidence completeness is
`complete` or `partial`. `partial` may be published only when every required
source member and lifecycle relationship is present and every optional loss is
explicitly `absent`, `unknown`, `unavailable`, `redacted`, or allowed
`unsupported`. An unexpectedly missing required artifact fails import.

Scoreability and publication readiness are both `not_assessed` in the initial
import contract. They are not inferred from structural validation,
completeness, source outcome, harness verifier output, or import success. A
successful import does not mean the harness task succeeded. A successful
harness task does not mean the captured evidence is complete. A complete source
package does not mean it is correct, safe, scoreable, or public-safe.

## Containment and path security

The importer accepts only an operator-selected source session and its explicitly
referenced source objects. It does not crawl a home directory, repository, blob
store, or harness workspace looking for possible evidence.

All contained authority paths are normalized relative POSIX paths beneath the
owning result. The fixed session and object paths above are the only source-copy
locations. The importer rejects:

- absolute paths used as contained authority;
- empty, `.`, or `..` path segments, traversal, alternate separators, or
  result-root escape;
- symlinks, devices, sockets, FIFOs, or other non-regular source members;
- destination symlinks or a result root whose containment cannot be established;
- missing or unreadable required source files;
- source members that change identity, size, or bytes while being copied;
- a member whose computed SHA-256 disagrees with a source-declared digest;
- duplicate contained authority paths, conflicting logical-reference mappings,
  or conflicting copies for one declared identity; and
- any source whose line, member, member-count, or total-byte limits would require
  an unbounded read.

The implementation applies these closed limits:

| Resource | Limit |
|---|---:|
| Source session bytes | 64 MiB |
| One logical JSONL record | 8 MiB |
| Logical event count | 100,000 |
| Referenced object count | 256 |
| One referenced object | 64 MiB |
| Total unique source bytes | 256 MiB |
| Normalized evidence JSON | 16 MiB |
| JSON nesting depth | 64 |
| Entries examined in one artifact directory | 4,096 |

Total source bytes count the session once plus each unique content-addressed
object once, even when several logical references name the same bytes. Limits
are applied before allocation or copy where possible; hashing and copying are
streamed. Exceeding a limit is a closed failure, never silent truncation.
Archive extraction and implicit recursive directory import remain outside the
initial source contract.

Absolute repository paths, remote locators, command paths, and source-store
locations may remain source-observed private metadata. They are data only. A
validator never dereferences them. No imported string is treated as a command,
executable, import path, template, glob, archive member, or instruction.

## Privacy and sanitization

The contained import is canonical private evidence, not a public package. Even
private evidence follows data minimization and must never knowingly retain
credentials merely for exactness.

The importer must not admit raw credentials, tokens, API keys, passwords,
credential-bearing URLs, SSH private material, cookies, provider credentials,
or broad unrelated environment dumps. Known or detected secret-bearing source
must be excluded by an upstream source export with an explicit redaction/loss
marker, or the import fails before publication. LLMGauge does not copy first and
redact its canonical source afterward. No automated scan proves that a source is
secret-free.

The same review applies to environment-variable values, shell history, command
and tool arguments, stdout, stderr, model/provider payloads, patches, diffs, and
repository files. Environment capture is allowlisted provenance, not a general
environment dump. Private reasoning and provider-internal payloads remain
excluded under the model-interaction boundary.

Home-directory paths, usernames, hostnames, credential-free private repository
URLs/remotes, proprietary source, repository contents, and private command
output may be retained only when they are part of explicitly selected private
evidence and policy permits it. Normalized metadata minimizes duplication and
labels privacy-sensitive observed values. Material omitted for privacy records
`redacted` or `unavailable` with a bounded reason and source reference; omission
must not be described as complete evidence.

Any future sanitization creates a separate derivative. It must never overwrite
or mutate the canonical private import, must preserve loss and provenance, and
must redact home paths, usernames, hostnames, private remotes, credentials,
private source, and unnecessary command/tool/model payloads according to an
accepted export contract. Sanitization is not proof that all private data was
removed, and human review remains mandatory before publication. This milestone
implements no sanitization or publication behavior.

## Source-format compatibility

The initial importer recognizes only a WumboLabs OMP session JSONL whose first
logical header is `type: "session"` with integer `version: 3`, including the
format-defined optional physical title slot. It preserves physical source order,
logical entry IDs, tree IDs and parents, message and lifecycle entries,
format-defined custom entries, artifact references, and admitted
content-addressed objects. A physical title is preserved source data but does
not replace the logical session header or session ID.

Compatibility is fail closed:

- exact supported v3 sources are parsed under this contract, not through a
  generic log reader;
- source versions 1 and 2 are unsupported even if the upstream harness can
  migrate them;
- an unknown newer version is unsupported;
- missing version information is unsupported because semantics cannot be
  established;
- recognizable v3 with invalid structure is malformed;
- partially recognized required entries or extensions make the source
  unsupported rather than partially guessed;
- a foreign harness, converted agent log, arbitrary chat log, terminal capture,
  or repository history is not `wumbolabs_omp_session`; and
- unknown optional fields may be retained only when v3 declares them
  extension-safe and they cannot alter required identity, order, reference,
  lifecycle, or outcome meaning.

The importer does not reuse upstream migrations, repair behavior, lenient
loaders, or defaults to reinterpret historical or future source. Support for an
older version, newer version, or foreign harness requires explicit source
semantics, compatibility fixtures, and a separately accepted contract/version.

## Import transaction and failure behavior

Import is one transaction over one source session and one new result directory:

1. Resolve only the explicitly selected source and referenced members without
   mutating them.
2. Create a non-result staging directory beside the final destination so final
   publication can remain on one filesystem.
3. Stream-copy admitted bytes, compute full hashes, build the source inventory
   and normalized evidence, and verify that source members did not change while
   being read.
4. Write the dedicated result reference and fingerprint projection in staging.
5. Run complete structural validation against the staged self-contained package.
6. Atomically rename the validated staging directory to the previously absent
   final destination.

Until step 6 succeeds, no directory may look like a complete LLMGauge result.
A failed or partial copy is never published and never receives import outcome
`completed`. Cleanup of staging is best-effort after failure; stale staging is
not a result and a retry never trusts it. Failure diagnostics are bounded,
structured, privacy-safe, and returned through the importer error surface; they
do not retain raw provider payloads, source contents, credentials, or a false
result artifact.

The importer never overwrites or merges a destination. If an existing valid
destination has the same evidence and source-package identities, the operation
returns `already_imported` without mutation. Any identity, hash, session, or
content conflict fails. Importing the same source into another explicitly chosen
new result is allowed; no mutable global deduplication registry becomes
authority. Retry rereads and revalidates the source from the beginning. An
unchanged source is deterministic; a changed source is new evidence and may not
reuse a prior staging package or identity.

## Result integration and historical compatibility

The smallest additive `llmgauge.result.v0` relationship is one optional closed
`agent_harness_evidence` discovery/integrity reference. It contains only:

- `schema_version` = `llmgauge.agent_harness_evidence.v0`;
- `contract_version` = `0.1.0`;
- `evidence_class` = `external_agent_environment`;
- `evidence_id`;
- `path` = `agent-harness/evidence.json`; and
- `sha256` = the file's 64-character lowercase SHA-256 digest.

Every duplicated identity must equal the contained document. The reference is
not a second source-session authority and does not duplicate trajectory,
repository, command, lifecycle, or outcome content. The contained evidence owns
those normalized mappings; its source references lead to the copied source
authority.

A result carrying this field is dedicated to the one imported session. Its
existing native `results` collection is empty, and it has no native transcript.
The 3b validator may admit that empty collection only when the complete valid
Agent Harness reference is present. It must reject mixed native and imported
Agent Harness authority under this contract version.

The existing required result envelope is compatibility metadata, not a second
agent-session representation. Its import form is exact:

- `schema_version` remains `llmgauge.result.v0`, and `llmgauge_version` records
  the importing installation;
- `run` records the local import operation with `operation` set to
  `agent_harness_import`, the current `run_id`, `timestamp_utc`, and
  `result_dir` fields, and `status` set to `completed`; that status means atomic
  import success only;
- `model` contains only the existing `model_path: redacted` sentinel;
- `runtime` and `suite` are empty objects;
- `summary.completed` and `summary.failed` are both zero because there are no
  native prompt results; and
- `results` is the empty list.

Source model, runtime, provider, task, repository, and terminal facts live only
in `evidence.json` with availability and source references. They are not copied
into legacy native fields or replaced with placeholder identities. The imported
fingerprint path does not treat the compatibility envelope as source
provenance. Existing consumers must check the Agent Harness reference before
interpreting `run.status`, the zero prompt summary, or the empty native objects.

Ordinary results omit the optional field and retain their exact current shape,
validation, fingerprint, scoring, reporting, comparison, and export behavior.
Unknown optional fields remain tolerated according to current
[artifact](ARTIFACT_SCHEMAS.md), [result](RESULT_SCHEMA_V0.md), and
[validation](RESULT_VALIDATION_V0.md) contracts, but a consumer that recognizes
this field may not ignore its evaluation class and process it as native evidence.
No historical artifact is migrated, rewritten, relabeled, or required to gain a
field.

## Fingerprint boundary

The current run-fingerprint implementation is unchanged in 3a. The 3b
implementation must extend its versioned canonical payload only for a valid
represented `agent_harness_evidence` reference. Ordinary-result fingerprint
payloads and values remain unchanged.

The imported-evidence projection includes:

- evidence schema and contract versions and evaluation class;
- source type, format, and exact format version;
- producer identity and producer-version availability/value;
- imported session ID, source session/run ID, evidence ID, and importer
  identity/version;
- source package SHA-256, the canonical source-file inventory, and full member
  hashes;
- task identity and availability;
- immutable model, runtime, provider, and transport provenance and availability;
- repository-state facts and referenced diff, patch, snapshot, or manifest
  hashes;
- command/tool event identities, source references, ordering, lifecycle states,
  and authoritative output-member hashes;
- explicit source-reference loss/redaction/availability states; and
- source-session terminal outcome and evidence-completeness state.

The projection does not include the mutable input locator, result path, import
time, reports, cleaned or conversational views, reviewer notes, manual scores,
deterministic score derivatives, comparisons, export indexes, sanitized
exports, or publication decisions. Those artifacts may cite the source run
fingerprint but cannot change it or authenticate transformed bytes.

A fingerprint identifies the represented canonical private evidence and mapping
contract. It does not prove authorship, repository correctness, command
execution beyond admitted lifecycle evidence, model quality, agent reliability,
hardware identity, source success, human approval, or publication readiness.

## Structural validation boundary

Implemented structural validation is deterministic, offline, read-only, and
fail-closed. It validates:

- the supported evidence schema and contract versions, evaluation class, source
  type, source format/version, producer, and importer identities;
- owning-result/reference cardinality, exact contained path, reference hash,
  empty native results, and native-transcript absence;
- source-package inventory canonicalization, path uniqueness, byte counts,
  full member hashes, package hash, and self-containment;
- supported v3 header, source session ID, physical order, logical/tree ID
  uniqueness, parent ordering, and admitted entry semantics;
- unique normalized IDs, canonical ordering where defined, valid backward or
  source references, and exact availability states;
- model-message, retry, branch, selection, and source-terminal consistency
  without inventing a linear transcript;
- command and tool request/start/output/terminal lifecycle consistency,
  including denial, timeout, truncation, missing output, and exit-status rules;
- repository observation ordering and distinct initial/final, staged/unstaged,
  untracked, dirty, diff, patch, snapshot, and manifest relationships;
- privacy/redaction/exclusion markers and required-versus-optional source-member
  availability;
- containment, regular-file requirements, source/reference mapping, size limits,
  duplicate/conflict rejection, and no external authority dependency;
- evidence completeness, source-session outcome, import outcome, and validation
  state consistency;
- evidence ID and imported-session-ID recomputation;
- versioned run-fingerprint recomputation when represented; and
- explicit separation from native transcript schema, event, feedback, runtime,
  prompt-result, and terminal authority.

Validators report defects and never repair evidence, follow imported paths,
query repositories, replay commands, contact providers, or infer missing facts.
Passing validation establishes represented structure, containment, integrity,
and internal consistency only. It does not establish semantic correctness,
successful software modification, tests passing, repository correctness, model
quality, safety, agent reliability, scoreability, human approval, complete
sanitization, or publication readiness.

## Scoring authority boundary

Agent Harness may supply verifier results, task outcomes, or score-like fields.
They remain harness-owned source facts with provenance; they are not LLMGauge
scores and do not decide LLMGauge validation, review, scoreability, comparison,
export, or publication.

Imported evidence may later support separately contracted review dimensions such
as task completion, instruction adherence, tool-use correctness, recovery,
repository correctness, test/validation evidence, and final-answer quality.
This document does not create a rubric, aggregation, threshold, deterministic
checker, or universal agent score. Agent-environment outcome remains attributable
to the observed model, harness, tools, repository, environment, limits, and
operator conditions, not the model alone.

Current [scoring rubrics](SCORING_RUBRICS.md), native transcript scoring hooks,
and `results[].score` retain their existing meanings. They cannot be reused or
reinterpreted for imported sessions. Manual scoring and deterministic evidence
checks require separate contracts and provenance, and neither may overwrite the
contained source or harness outcome.

## Comparison, reporting, and export boundary

Current native report, [scored comparison](SCORED_COMPARISONS.md), public-export,
and [public reporting](PUBLIC_REPORTING.md) behavior has no Agent Harness
semantics. A consumer must fail closed when asked to interpret an imported
session until an Agent Harness-specific contract and implementation exists. It
must not silently omit the evidence, flatten harness outcomes into transcript or
prompt results, compare them through current native score fields, or publish a
native-looking report.

Order 3b does not generate the current native `report.md`. Native report
generation rejects this evidence class rather than treating zero native prompt
results as a successful empty evaluation. An Agent Harness-specific human
report becomes canonical only after the separate 3c scoring/reporting contract
defines its evidence, review, and claim boundaries. Report absence in 3b is not
publication readiness and does not weaken preservation of the machine-readable
canonical source package.

A future export index may expose only bounded discovery metadata already in the
result reference plus structural validation status, after an explicit contract.
That possibility does not authorize source copying, trajectory export,
sanitization, comparison, public export, publication, or cross-harness ranking.
Any later comparison must establish compatible source identity/version, task,
repository basis, model/harness/tool/runtime stack, limits, evidence
completeness, outcome semantics, scoring state, and privacy boundary. No such
eligibility contract exists now.

## Read-only import rule

The importer is read-only with respect to the source session, harness store, and
source repository. Its only durable write is construction of a new contained
LLMGauge result through the staging transaction above.

It never:

- checks out commits or branches;
- resets, cleans, stages, commits, amends, merges, rebases, cherry-picks, tags,
  applies patches, or changes remotes;
- reconstructs a repository, index, worktree, diff, or manifest;
- replays commands, tool calls, tests, builds, compilers, or verifiers;
- launches or resumes an agent or harness session;
- sends a user, model, system, developer, feedback, or retry message;
- contacts a model runtime, provider, remote repository, network service, or
  external API;
- launches tools, shells, runtimes, services, or background processes;
- mutates, repairs, truncates, redacts in place, locks through mutation, or
  deletes source evidence; or
- treats imported content as instructions or an execution surface.

Reading and copying the explicitly selected source package does not authorize
reading the referenced repository or current external paths. Source bytes may
change concurrently because a session is live or mutable; detection causes
failure rather than locking, retrying around, or modifying the source.

## Missing evidence and inference prohibition

Every normalized assertion requires an admitted source reference. When optional
evidence is absent, the importer records the exact allowed availability state.
When required identity, structure, reference, or source evidence is absent,
conflicting, or unsupported, import or validation fails.

In particular, LLMGauge does not:

- reconstruct command output from the current repository or filesystem;
- infer command or tool execution from model prose, a planned action, or a
  request;
- infer test success because files look correct or a final answer says tests
  passed;
- infer final repository state, applied changes, or commit state from a patch;
- infer a complete dirty worktree from a Git SHA, dirty Boolean, or tracked diff;
- infer initial state from final state or final state from initial state;
- infer branch, remote, repository identity, or source bytes from a path;
- infer model, checkpoint, provider, runtime, token, timing, or hardware facts
  absent from source evidence;
- infer a selected branch or final answer from physical position alone;
- infer task success from import success, validation success, verifier-like
  text, or evidence completeness; or
- replace unknown, unavailable, redacted, unsupported, malformed, or failed
  evidence with defaults.

Unknown stays unknown. Unavailable stays unavailable. Redacted stays redacted.
Unsupported semantics fail where required. A narrower honest record is valid
only where this contract marks the fact optional; invention is never a
compatibility strategy.

## Implemented boundary for Full Model Testing 3b

Full Model Testing order 3b implements **Agent Harness importer schema and
read-only package ingestion** under this accepted contract.

The implementation includes only:

- models for `llmgauge.agent_harness_evidence.v0` contract version `0.1.0` and
  the closed result reference;
- strict bounded detection of `wumbolabs.omp.session_jsonl` version 3 without
  migrations or foreign-log guessing;
- read-only source selection, source/reference resolution, streaming contained
  copying, source inventory, hashing, and atomic package publication;
- imported-session/evidence identity and structural validation;
- the additive `llmgauge.result.v0.agent_harness_evidence` relationship and
  required fail-closed recognition by existing native consumers;
- the imported-evidence run-fingerprint projection while preserving ordinary
  fingerprints; and
- focused secret-free synthetic fixtures and tests for supported, malformed,
  unsupported, partial, containment, integrity, lifecycle, atomic-failure,
  duplicate, and legacy-result paths.

It does not implement semantic or deterministic scoring, agent comparison,
native transcript conversion, native reporting, public export, publication,
session replay/resume, model or provider contact, command/tool/test execution,
repository inspection or mutation, live Agent Harness execution, broad foreign
harness support, dependencies, package-resource changes, release preparation,
or release metadata.

The selected next bounded milestone is **Agent-session scoring and reporting**,
Full Model Testing order 3c, and remains separately gated.
Runtime-neutral metrics and the remainder of the accepted Full Model Testing
order remain unchanged. LocalMaxxing remains a parallel unselected
performance-benchmark lane. Generic Core and its existing `v0.73` gate remain
admitted downstream without a release-version decision.
