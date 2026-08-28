# LLMGauge Result Schema v0

Canonical machine-readable result:

- `llmgauge-result.json`

Canonical human-readable report:

- `report.md`

Key `report.md` sections for audit and publication review:

- **Report Scope** — supported and unsupported uses
- **Evidence Summary** — cite-friendly run snapshot
- **Audit Checklist** — validation, inspection, and retention steps
- **Prompt Artifact Audit** — per-prompt paths, score rationales, source vs derived roles
- **Publish Readiness Notes** — claim boundaries

Raw artifacts must be preserved:

- raw prompt text
- raw model output
- cleaned review output when available
- runner logs
- stderr/stdout where useful

The local run directory is the canonical private evidence. A public export is a
sanitized derivative created by `llmgauge export-public`; it must not modify the
source run and is not a substitute for private raw evidence or manual review.

Quality scores are separate from runtime metrics.

Runtime metrics include:

- prompt eval tokens/sec
- generation tokens/sec
- context size
- max generated tokens
- peak VRAM where available
- VRAM headroom where available
- backend
- model quantization
- llama.cpp metadata where available


## Compatibility policy

`llmgauge.result.v0` evolves additively through the v0.x line. Valid older v0.x
result directories remain supported through 1.0 unless they are corrupted,
unsafe to interpret, or technically impossible to interpret.

Non-breaking changes include:

- optional fields
- optional artifacts
- additional warnings
- additional report sections
- enum values older readers may treat as unknown
- more informative validation that still accepts prior valid data

Breaking changes include:

- required fields
- renamed or removed fields
- changed field types
- changed field semantics
- moved required artifacts
- changed score semantics
- making previously valid legacy artifacts invalid

Do not introduce a migration framework until a concrete compatibility need
exists. Prefer readers that tolerate missing optional fields and preserve unknown
fields.

## Optional imported Agent Harness evidence

A dedicated read-only Agent Harness import adds one closed top-level reference:

    {
      "agent_harness_evidence": {
        "schema_version": "llmgauge.agent_harness_evidence.v0",
        "contract_version": "0.1.0",
        "evidence_class": "external_agent_environment",
        "evidence_id": "sha256:<64 lowercase hex characters>",
        "path": "agent-harness/evidence.json",
        "sha256": "<64 lowercase hex characters>"
      }
    }

The owning `llmgauge.result.v0` has `run.operation:
agent_harness_import`, an empty native `results` list, matching zero summary
counts, and no native `transcript`. Its contained source authority is:

    agent-harness/evidence.json
    agent-harness/source/session.jsonl
    agent-harness/source/objects/sha256/<64-lowercase-hex-digest>

The evidence schema is closed and contract-versioned. It preserves source
identity and completeness, normalized physical-order trajectory, tool
lifecycle, model and repository availability, terminal state, source-reference
mapping, and exact source inventory. Unknown or unavailable facts remain
explicit; import and structural validation do not infer task success,
scoreability, quality, or publication readiness. See
[Agent Harness Import Contract](AGENT_HARNESS_IMPORT_CONTRACT.md).

## Canonical evaluation identity design

Canonical identity data is additive metadata for reproducibility and comparison.
It must not replace preserved raw artifacts.

### Model provenance

New runs record model provenance under an additive optional `model.provenance`
object while preserving existing `model` fields. Current fields are:

- `source_type`: `model_profile` or `direct_model_path`
- `filename`
- `file_size_bytes`
- `sha256`: full local GGUF SHA-256 when available
- `public_fingerprint`: shortened display fingerprint for public reports
- `status`: `available` or `unavailable`
- `warning`: collection warning when unavailable

The public fingerprint is the deterministic `sha256:` prefix followed by the
first 16 lowercase hexadecimal characters of the full SHA-256. It contains no
local path data. Architecture, quantization, and GGUF metadata are deferred.

Unavailable provenance is recorded explicitly rather than making an otherwise
usable run invalid.

### vLLM external-server runtime (additive)

When `runtime.backend` is `vllm`, results may include optional fields and
artifacts. Missing optional vLLM metadata remains valid and is treated as
unknown. Legacy llama.cpp and earlier v0.x results remain valid without these
fields.

This slice supports `llmgauge run` only. Batch, ladder, and fit-ladder reject
`backend=vllm` fail-closed before evaluation HTTP. Local `--model-path` /
profile `path` values are rejected for vLLM; directory-model and GGUF
provenance remain deferred. Model identity is the requested/observed
served-model name. Chat requests send ordered system and user messages;
`raw/*.prompt.md` remains a human-readable combined form and is not claimed
identical to the chat message list.

Optional runtime fields:

- `lifecycle_ownership` (expected: `external_operator`)
- `endpoint_identity` — sanitized scheme, loopback class, and port only
- `requested_served_model` / `observed_served_model`
- `connect_timeout_seconds` / `request_timeout_seconds` / `max_response_bytes`
- `vllm_runtime_evidence_captured` / `vllm_runtime_evidence_path`
- `proxy_bypass_policy`, `streaming`, `authentication`
- `runtime_command_captured` is false; `runtime-command.json` is not used for HTTP evidence

Optional artifacts:

- `vllm-runtime-evidence.json` (`llmgauge.vllm_runtime_evidence.v0`)
- per-prompt `request/<prompt>.json` (`llmgauge.vllm_request_evidence.v0`) referenced by
  `results[].request_evidence_path`

Optional per-prompt fields: `failure_class`, `failure_detail`, `finish_reason`,
`observed_served_model`, and additive metrics such as
`request_wall_time_seconds` and `end_to_end_completion_tps` (end-to-end, not
decode-only; not claimed equivalent to llama.cpp `generation_tps`).

### Backend provenance

New real-run results may include additive `runtime.backend_provenance` metadata.
Current fields are:

- `backend_name`: `llama.cpp` or `vllm`
- `executable_filename`
- `executable_file_size_bytes`
- `executable_sha256`: full local executable SHA-256 when available
- `public_executable_fingerprint`: deterministic `sha256:` plus the first 16
  lowercase hexadecimal characters of the full digest
- `status`: `available` or `unavailable`
- `warning`: collection warning when unavailable
- `reported_version`: concise reported version text when available
- `commit`: clearly labeled commit identifier when available
- `build_number`: clearly labeled build number when available
- `build_type`: clearly labeled build type when available
- `build_metadata`: concise compiler/build metadata when available
- `discovery_status`: `available`, `partial`, or `unavailable`
- `discovery_warning`: probe or parsing warning when needed

The public executable fingerprint contains no local path data. Executable path,
version probe command output, and unrestricted subprocess output are not stored.
Unrecognized commit, build number, build type, and build metadata remain null.

### Hash cache design

File hashing caches expensive hashes under the user-owned
`$XDG_CACHE_HOME/llmgauge/hash-cache-v0.json` directory, or
`~/.cache/llmgauge/hash-cache-v0.json` when `XDG_CACHE_HOME` is unset. Cache
entries include:

- path
- size
- modification time
- inode and device, or platform-equivalent file identity when available
- hash algorithm
- full hash
- update timestamp

A cached hash must never be trusted when any available file identity field
changes. If inode/device-equivalent identity is unavailable, cache validation
falls back to path, size, and modification time, and may rehash more often.
Cache corruption must be treated as a cache miss, not as a run failure. Writes
should be atomic. Concurrent writers may race safely by recomputing and
replacing the cache. Explicit future rehash support should bypass the cache and
refresh the entry.

### Prompt and suite identity

Prompt identity should hash one canonical evaluation-relevant prompt definition,
not unrelated hashes for rubric and output contract. Inputs include:

- prompt text
- system text
- output contract
- scoring rubric reference or embedded rubric
- evaluation-relevant prompt metadata
- template-specific instructions

Suite identity should hash canonical suite content plus the prompt definition
identities. Canonical serialization sorts mapping keys so YAML key ordering does
not affect identity. Sequence order remains meaningful where it changes suite or
prompt semantics.

### Canonical run fingerprint

New finalized single-run results may include an optional top-level
`run_fingerprint` object:

    {
      "schema_version": "llmgauge.run_fingerprint.v0",
      "algorithm": "sha256",
      "value": "sha256:<64 lowercase hex characters>"
    }

The fingerprint identifies canonical private evidence for one single-run
result. It is an evidence-integrity identifier, not a quality score, signature,
authorship proof, hardware attestation, or whole-directory manifest.

The v0 payload includes stable private evidence:

- result schema version and LLMGauge version
- model source type, model filename, provenance status, and full model SHA-256
  when locally available
- backend name, executable filename, executable SHA-256, and bounded
  llama.cpp version/build identity when locally available
- suite identity fields
- ordered prompt identities from the result schema
- material generation/runtime settings
- per-prompt status and exit status
- SHA-256 of authoritative referenced artifacts: raw prompt, raw output, stderr
  log, and VRAM samples when recorded

The payload uses relative artifact references only and hashes artifact bytes
rather than embedding artifact contents. JSON serialization uses deterministic
UTF-8 JSON with sorted mapping keys and compact separators.

Run ID and run timestamp are excluded. The same immutable evidence can therefore
produce the same fingerprint in a different result directory or at a different
timestamp; this is evidence equivalence, not unique execution-instance identity.

The fingerprint must exclude mutable or regenerated review artifacts:

- `report.md`
- `scores.yaml`
- comparison reports
- export indexes
- cleaned output
- manually edited review metadata
- local result-directory paths, config paths, model paths, executable paths,
  home-directory paths, and temporary paths

Validation preserves legacy compatibility when `run_fingerprint` is absent. When
present, validation checks schema version, algorithm, value format, referenced
artifact availability, and recomputes the canonical SHA-256. Validation reports
mismatches but never rewrites the fingerprint.

Imported Agent Harness results use a distinct canonical payload containing the
evidence schema/contract/class, evidence and imported-session identities,
source-package hash, importer identity, and immutable normalized mapping.
Ordinary single-turn and native-transcript fingerprint payloads are unchanged.
Validation recomputes the contained evidence identity, source-package identity,
member hashes, and imported run fingerprint; it never consults the original
external session path.

### Optional native multi-turn transcript

Native multi-turn runs add one optional closed top-level reference:

    {
      "transcript": {
        "path": "transcript/transcript.json",
        "schema_version": "llmgauge.transcript.v0",
        "protocol_id": "llmgauge.sequential_supplied_feedback",
        "protocol_version": "0.1.0",
        "conversation_id": "<stable ID>",
        "sha256": "<64 lowercase hex characters>"
      }
    }

The separately versioned contained artifact is the sole transcript authority.
Its ordered `feedback_plan` is the sole authority for every declared feedback
item's identity, origin, schedule, exact source content, and lifecycle
(`unreached`, `supplied_unconsumed`, or `consumed`). The canonical discriminated
event sequence records actual supply occurrences separately and preserves task,
every model attempt with independent attempt state and exact integer adapter
exit status, observable state transitions, retries/recovery, branches, final
selection, and terminal facts. The result reference is only a
discovery/integrity index and must match the contained authority exactly.
Ordinary single-turn results omit it and are never inferred to be transcripts.

A transcript prompt result may add `transcript_event_id` as a compatibility
link to the selected final response. Existing prompt status remains generation
status; it does not replace transcript completion, terminal, or review state.
Its `exit_status` is copied from the selected compatibility attempt rather than
synthesized from completion. llama.cpp compatibility metrics parse authoritative
raw output plus authoritative runtime stderr exactly as the single-turn path
does; no metric is invented when neither contains one. Existing
`results[].score` remains null because no native multi-turn scoring contract or
universal numeric score exists.

When a transcript is represented, the existing run-fingerprint payload adds
immutable transcript schema/protocol/conversation/task/initial-state identity,
declared and effective limits, branch relationships, the complete ordered
feedback plan with source hashes and lifecycle associations, ordered event
identities, actual feedback supply occurrences, attempt states, exact exit
statuses and source hashes, state transitions, and
completion/terminal/final-response facts.
Cleaned derivatives, review hooks, scores, reports, comparisons, export indexes,
and sanitized exports remain excluded. The payload is unchanged when transcript
evidence is absent, so historical fingerprints remain stable.

Current single-turn scoring and public export fail closed for transcript
evidence. `compare` accepts all-transcript result sets only under the bounded
structural comparison in
[Transcript Comparison and Review Contract](TRANSCRIPT_COMPARISON_REVIEW_CONTRACT.md)
and fails closed on mixed sets. `export-index` may
include the non-authoritative transcript discovery object. Agent Harness
evidence must not use this native representation.

### Reasoning-mode compatibility

v0.66 writes `runtime.reasoning_mode`. Future metadata should add
`runtime.reasoning_mode_requested` while preserving the legacy field. Readers
should prefer `reasoning_mode_requested` when present, fall back to
`reasoning_mode` for v0.66 artifacts, and use `unknown` when older artifacts
omit both.

Supported requested values are `default`, `off`, `on`, and `auto`. Legacy
readers may also encounter `unknown`. Observed or effective reasoning behavior
must remain separate future metadata and must not be inferred from the requested
mode alone. Reports should avoid empty reasoning sections and avoid claiming
effective reasoning behavior without evidence.

## Optional Coding Core native evidence

Native `coding-core-v1` `0.1.0` runs may add a closed `suite.selection` object:

- `kind`: `profile` or `custom`;
- `selected_profile`: the named profile, or null for a custom selection;
- `selected_prompt_ids`: exact ordered result membership;
- `canonical_prompt_ids`: exact admitted canonical suite membership;
- `default_profile`: the declared default profile.

`suite.selection.selected_prompt_ids` is the portable selection authority when
present. Existing `include` and `only` fields remain invocation metadata for
legacy compatibility. `suite_path` remains local workflow metadata and is not
portable suite identity. The optional selection is included in a new run's
canonical fingerprint payload; legacy fingerprints without it remain valid.

Each selected Coding Core prompt may add a closed `coding_core` object with:

- `response_form`: exact category, logical ID, and version;
- `scoring_method`: exact role and manual-rubric reference, plus deterministic
  check and hybrid-composition references only where declared;
- `manual_review`: rubric ID/version, applicable dimensions, derived review
  state, reviewed flag, and verdict;
- `deterministic_result`: the complete accepted static-check record, only for a
  hybrid prompt;
- `hybrid_composition`: the accepted side-by-side composition, only for a
  hybrid prompt.

The prompt's applied `score` object remains authoritative for manual dimensions,
reviewer/scorer identity, rationale, verdict, evidence, warnings, and score
provenance. `coding_core.manual_review` is a derived state summary and must agree
with that object. The independent `coding_core.deterministic_result` is the
deterministic authority; the copy inside `hybrid_composition` must match it
exactly. Score application updates manual and hybrid state without rerunning the
static check.

Deterministic outcomes remain distinct:

- `pass`: observed structural conformance;
- `fail`: observed structural nonconformance;
- `error`: check, resource, or configuration failure;
- `not_run`: no check attempt because raw response evidence is absent after
  generation failure.

The check consumes preserved raw output, not cleaned output. Structural
conformance is not semantic or runtime correctness. Manual-only prompts contain
no deterministic or hybrid records. Hybrid `complete` is true only when the
deterministic outcome is `pass` or `fail` and manual review is fully `reviewed`;
incomplete is not failed. Coding Core has no numeric profile-level or universal
aggregate score.


## Cleaned output

Newer run artifacts may include `cleaned_output_path` on each prompt result.

This path points to a derived review artifact under `cleaned/`. It is intended to
make manual review easier by removing obvious llama.cpp terminal wrapper text,
prompt echo, and trailing runtime metric lines where possible.

Raw output remains the audit source of truth.


## Applied manual scores

Prompt results may include an applied `score` object.

Expected applied score fields:

- `schema_version`
- `scale`
- `rubric_id`
- `rubric_version`
- `dimensions`
- `prompt_total`
- `prompt_max`
- `prompt_average`
- `failure_labels`
- `good_labels`
- `reviewer_notes`
- `score_rationale`
- `verdict`

Manual scores are human review metadata. They are separate from runtime metrics.

Applied score objects may also include scoring provenance fields such as
`scoring_mode`, `scorer_id`, `scorer_version`, `confidence`, `evidence`,
`warnings`, `reviewed`, and `override_status`. These fields are preserved for
auditability and downstream reporting. They do not make automatic or assisted
scores authoritative without review.
