# LLMGauge Artifact Schemas

This document describes the current LLMGauge artifact schemas intended for validation, import, and review.

These schemas are intentionally conservative and file-based. They are not database schemas.

## Validation vs quality

`validate-result` and related validators confirm artifact structure, schema
fields, and on-disk references. Passing validation means the directory is
internally consistent enough to inspect, score, compare, or export.

Validation does not prove:

- answer correctness
- operational safety
- manual scoring quality
- publication readiness
- bounded public-claim eligibility

Use `report.md` **Publish Readiness Notes**, comparison publish-readiness
sections, and manual review of raw/cleaned outputs for publication decisions.

## Public-proof artifact roles

Three generated artifacts work together in the public-proof workflow. They
overlap in topic but serve different roles:

| Artifact | Role | Authoritative for | Regenerate when |
|---|---|---|---|
| `report.md` (single-run) | Human review artifact for one run | Prompt-level output review, score/rationale review, single-run publish-readiness | After `score --scores` or other updates to `llmgauge-result.json` |
| `compare.md` (comparison) | Multi-run evidence summary | Cross-run comparison, mixed-set caveats, **Publication evidence summary** | After underlying runs change or are re-scored |
| Export index JSON | Machine-readable metadata | Importer discovery, batch summaries, `scoring_status` and publish-readiness fields | After scoring, validation, or report regeneration |

Source-of-truth references:

- `llmgauge-result.json` is the machine-readable source of truth for run metadata and applied scores.
- `scores.yaml` is authoritative for manual score intent before application.
- Applied scores embedded in `llmgauge-result.json` are authoritative after `score --scores`.
- Raw and cleaned outputs under `raw/` and `cleaned/` are authoritative for prompt-level output review.

None of these artifacts are model recommendations, leaderboards, or automatic
quality judgments. See `docs/PUBLIC_REPORTING.md` for the full workflow
checklist.

## Design rules

- Artifacts should be readable without any external dashboard or importer.
- Downstream tools may import artifacts, but LLMGauge does not write to external application databases.
- Raw prompt, output, and log files remain audit evidence.
- Cleaned outputs are derived review artifacts and do not replace raw outputs.
- `llmgauge.result.v0` evolves additively through 1.0 where practical.
- JSON schemas should evolve additively where possible.
- Importers should check `schema_version` before trusting a file and tolerate
  unknown optional fields.
- Relative artifact paths inside result JSON are relative to the result directory.
- Absolute local model paths should not be exposed in public result metadata.

## Single run directory

A normal run directory contains:

    llmgauge-result.json
    runtime-command.json
    report.md
    raw/
    cleaned/
    logs/

Required machine-readable file:

    llmgauge-result.json

Human-readable file:

    report.md

Audit artifact directories:

    raw/
    logs/

Optional derived review directory:

    cleaned/

Optional operational telemetry:

    vram/

Optional runtime reproducibility artifact (v0.66+):

    runtime-command.json

Optional native multi-turn source tree:

    transcript/transcript.json
    transcript/source/
    transcript/derived/

`transcript/transcript.json` is the sole ordered transcript and declared
feedback-plan authority. `transcript/source/` preserves rendered requests, raw
responses, stderr, declared exact feedback content (whether reached or not), and
visible-state evidence. `transcript/derived/` contains cleaned review aids only.

Optional imported Agent Harness source and review tree:

    agent-harness/evidence.json
    agent-harness/source/session.jsonl
    agent-harness/source/objects/sha256/<64-lowercase-hex-digest>
    agent-harness/review/agent-session-review.template.json
    agent-harness/review/agent-session-review.json
    agent-harness/review/agent-session-review.md

`agent-harness/evidence.json` is the normalized
`llmgauge.agent_harness_evidence.v0` authority. The session file and referenced
objects are exact, digest-bound private source copies. The template, canonical
`llmgauge.agent_session_review.v0` reviewer metadata, and generated review
report are mutable derivatives; they are not evidence authority, result-envelope
discovery fields, or fingerprint inputs. This tree belongs only to a dedicated
external-agent import result; it cannot coexist with a native `transcript`
reference or native prompt results.

Optional imported external-benchmark source tree:

    external-benchmark/evidence.json
    external-benchmark/source/<original source members, exact bytes>
    external-benchmark/source/objects/sha256/<64-lowercase-hex-digest>
    external-benchmark/report.md

`external-benchmark/evidence.json` is the normalized
`llmgauge.external_benchmark_evidence.v0` identity and validation layer. It
does not replace the authoritative lm-eval source. Contained source members
are exact, digest-bound private copies. `external-benchmark/report.md` is a
regenerable read-only summary and Bundle 1 qualification view; it is not
written into evidence and is not a native `report.md`. This tree belongs only
to a dedicated external-benchmark import result; it cannot coexist with native
prompt results, a native `transcript` reference, or `agent_harness_evidence`.


Optional public single-run derivative:

    public-export-manifest.json

## Auditing a result directory

When reviewing or publishing from a result directory, inspect in this order:

1. `llmgauge-result.json` — machine-readable source of truth for run metadata and applied scores.
2. `report.md` — human review artifact with **Audit Checklist** and **Prompt Artifact Audit**.
3. `validate-result` — confirms structure and on-disk references, not answer quality.
4. `raw/` — source audit evidence for prompts and model outputs.
5. `cleaned/` — derived review aids when present; do not treat as a raw replacement.
6. `logs/` — stderr diagnostic evidence.
7. `scores.yaml` — manual score intent before application (when present).
8. `export-index` — optional machine-readable discovery metadata for importers.

Authoritative vs derived:

| Path | Role |
|---|---|
| `raw/*` | Source audit evidence |
| `logs/*` | Diagnostic evidence |
| `cleaned/*` | Derived review aid |
| `vram/*` | Operational telemetry captured locally |
| `llmgauge-result.json` | Applied score and run metadata source |
| `runtime-command.json` | Structured resolved llama.cpp command metadata |
| `report.md` | Regenerable human review summary |
| `transcript/transcript.json` | Authoritative native multi-turn event sequence and relationships |
| `transcript/source/*` | Authoritative rendered input, raw output, feedback, stderr, and visible-state evidence |
| `transcript/derived/*` | Cleaned transcript review aids; never replacement source evidence |
| `agent-harness/evidence.json` | Authoritative normalized imported-session identity, mapping, lifecycle, and availability state |
| `agent-harness/source/session.jsonl` | Exact admitted OMP v3 session source |
| `agent-harness/source/objects/sha256/*` | Exact referenced source objects, deduplicated by full SHA-256 |
| `agent-harness/review/agent-session-review.template.json` | Editable unreviewed review template; never report input |
| `agent-harness/review/agent-session-review.json` | Mutable manual reviewer metadata; never source authority |
| `agent-harness/review/agent-session-review.md` | Regenerable Agent Harness review aid |
| `external-benchmark/evidence.json` | Authoritative normalized imported-benchmark identity, native metrics, and validation state |
| `external-benchmark/source/*` | Exact admitted lm-eval result members |
| `external-benchmark/report.md` | Regenerable read-only imported-benchmark summary and Bundle 1 qualification view |

Retain raw outputs, logs, `llmgauge-result.json`, and `scores.yaml` for audit. Regenerate `report.md` after scoring changes.

## Fit Ladder parent directory

A Fit Ladder parent contains:

    fit-ladder-summary.json
    fit-ladder-report.md
    attempt-NN-ctx-NNNN/

`fit-ladder-summary.json` uses `llmgauge.fit_ladder.v0`. Its `retry_policy`
records the ascending CLI `fallback_contexts` list and stop policy, while its
`attempts` list contains executed attempts only. Therefore
`summary.attempted` and export-index `attempt_count` count executed attempts,
not every context in the requested plan.

`selected_working_settings`, when present, identifies the first completed child
by `attempt_id` and records its selected settings. Each attempt's `result_dir`
references its independently reviewable single-run child directory.
`fallback_changed_context` is true only when a completed selected context exists
and differs from the requested context. It is false on total failure because
there is no selected context, even if fallback retries occurred.

The current schema does not create explicit records for planned contexts skipped
after the first completion. Such a skip is inferred from the retry policy,
executed-attempt count, stop policy, and absence of another child directory.
This is a description of the existing schema, not a schema revision.

Validate the parent with `validate-fit-ladder` and each child with
`validate-result`. Score a completed child result directory, never the parent.

## Public single-run export

`llmgauge export-public RUN_DIR --out OUTPUT_DIR` creates a derived public
review directory from one structurally valid run. The source run remains the
canonical private evidence and is never modified. The output directory must be
new or empty.

The export policy preserves known report, prompt, output, score, VRAM, log, and
machine-readable artifacts after explicit text or JSON sanitization. It omits
unknown files by default. Absolute local paths, secret-like metadata, credential
URLs, full local SHA-256 values, legacy inline prompt duplication, local
endpoint host/port identity, and private stream/token evidence are redacted or
removed. Exact LLMGauge-generated API route literals (`/version`, `/v1/models`,
and `/v1/chat/completions`) remain readable; slash-prefixed filesystem paths
and route-like extensions remain subject to path redaction.

V1 public derivatives omit every represented TTFT projection: neutral metric
records and their evidence refs, per-prompt and request aliases (including
nested convenience metrics), stream refs/first-token fields, private stream
artifacts, and TTFT report lines. Transport-mode disclosure may remain.
Structured reasoning fields are removed. A generated output artifact containing
a known `<think>...</think>` marker is emitted empty rather than heuristically
split into a presumed final answer; final-answer-only output remains available.
The canonical private source and its raw/cleaned output are unchanged.

`public-export-manifest.json` uses schema `llmgauge.public_export.v0` and records
the source artifact type, copied/transformed/omitted relative files, redaction
categories, export timestamp, and the claim boundary that sanitization is not
answer-quality validation. Public-result validation checks represented manifest
file claims and rejects known TTFT, reasoning, token-ID, private-stream, and
structured endpoint contradictions. Users must still review the export before
publication; the bounded policy does not detect arbitrary unmarked reasoning or
guarantee complete secret removal.

When the source run has a canonical run fingerprint, the manifest records it as
`source_run_fingerprint`. This labels the fingerprint of the canonical private
source evidence only; it does not verify or authenticate transformed
public-export bytes.

## Public transcript comparison export

`llmgauge export-public-comparison RUN_A RUN_B --out OUTPUT_DIR` creates a
separate sanitized derivative of exactly two transcript-bearing runs under the
accepted
[Transcript Comparison Public Export Contract](TRANSCRIPT_COMPARISON_PUBLIC_EXPORT_CONTRACT.md).
The output directory contains exactly two files:

    transcript-comparison.json    schema llmgauge.public_transcript_comparison.v0
    report.md                     human-readable rendering of the same facts

The derivative is a content-default-deny allowlist projection: eligibility
booleans and identity field names, the three-way structural classification,
sanitized model labels, integers, closed vocabularies, and sequence-number-only
event/state/attempt skeletons. No prompts, rendered inputs, model outputs,
stderr, feedback content, conversation/run/event/attempt/turn/state/feedback/
branch IDs, suite or task identity values, paths, or full SHA-256 values are
projected, and a closed-world validator rejects any unexpected key or string.
Sources are never modified; the write is staged and atomic. The derivative
declares no aggregate, winner, or quality verdict, and both artifacts state
that human review is required before publication. Single-run `export-public`
keeps rejecting transcript-bearing runs.

## Public single-transcript derivative

`llmgauge export-public-transcript RUN --out OUTPUT_DIR` creates a separate
sanitized derivative of exactly one transcript-bearing run under the accepted
[Native Single-Transcript Public Derivative Contract](NATIVE_TRANSCRIPT_PUBLIC_DERIVATIVE_CONTRACT.md).
The output directory contains exactly two files:

    transcript-summary.json       schema llmgauge.public_transcript.v0
    report.md                     human-readable rendering of the same facts

The derivative is a content-default-deny allowlist projection sharing the
comparison derivative's per-run structural projection (slot label `run`,
fallback model label `Model`), sanitizer pipeline, closed vocabularies,
closed-world validator, and staged atomic write. It additionally discloses
the transcript's closed protocol identity, the producer's numeric release
version (strict `X.Y.Z` shape validation), and the declared/effective limits.
No prompts, rendered inputs, model outputs, stderr, feedback content,
conversation/run/event/attempt/turn/state/feedback/branch IDs, suite or task
identity values, result provenance, run fingerprints, paths, or full SHA-256
values are projected. `redaction` asserts
`raw_transcript_content_included: false` and
`private_identifiers_included: false`. Sources are never modified. The
derivative declares no score, aggregate, or quality verdict, and both
artifacts state that human review is required before publication.

## Schema: llmgauge.result.v0

Primary file:

    llmgauge-result.json

Top-level required keys:

    schema_version
    llmgauge_version
    run
    model
    runtime
    suite
    results
    summary

Expected `schema_version`:

    llmgauge.result.v0

Optional native multi-turn runs add a closed top-level `transcript` discovery
index with `path`, `schema_version`, `protocol_id`, `protocol_version`,
`conversation_id`, and full artifact `sha256`. All fields must equal the
contained `llmgauge.transcript.v0` authority. The object is absent for ordinary
single-turn runs.

Optional imported Agent Harness results instead add one closed top-level
`agent_harness_evidence` discovery reference:

    {
      "schema_version": "llmgauge.agent_harness_evidence.v0",
      "contract_version": "0.1.0",
      "evidence_class": "external_agent_environment",
      "evidence_id": "sha256:<64 lowercase hex characters>",
      "path": "agent-harness/evidence.json",
      "sha256": "<64 lowercase hex characters>"
    }

Such a result has `run.operation: agent_harness_import`, an empty `results`
list, zero completed/failed prompt counts, and no native `transcript`.
`validate-result` understands this dedicated shape. Native scoring, report,
comparison, export-index, and public-export consumers reject it until an
Agent Harness-specific scoring/reporting contract is implemented.

Optional imported external-benchmark results instead add one closed top-level
`external_benchmark_evidence` discovery reference:

    {
      "schema_version": "llmgauge.external_benchmark_evidence.v0",
      "contract_version": "0.1.0",
      "evaluation_class": "external_text_benchmark",
      "evidence_id": "sha256:<64 lowercase hex characters>",
      "path": "external-benchmark/evidence.json",
      "sha256": "<64 lowercase hex characters>"
    }

Such a result has `run.operation: external_benchmark_import`, an empty
`results` list, zero completed/failed prompt counts, and no native
`transcript` or `agent_harness_evidence`. `validate-result` and
`llmgauge benchmark validate` understand this dedicated shape. Native
scoring, report, comparison, export-index, and public-export consumers
reject it. Use `llmgauge benchmark report` to write
`external-benchmark/report.md`. Bundle 1 qualification is computed from
source-backed identities at report time and is not persisted into
`evidence.json`. See [Bundle 1 qualification](BUNDLE1_QUALIFICATION.md).

Normalized evidence records source-backed task identity, harness
identity/version/commit, dataset/config/revision, few-shot and generation
settings, seeds, model identity, runtime facts, native metric names/values,
native aggregation, sample/denominator metadata, source integrity, and import
provenance. Missing facts use the closed availability vocabulary. Native
metric names remain exact; unlike metrics are never renamed into a common
score.


### run

Required or expected fields:

    run_id
    timestamp_utc
    status
    result_dir

Expected `status` values:

    completed
    failed

Notes:

- `run_id` currently follows the output directory name.
- `timestamp_utc` should be ISO-like UTC text.
- `result_dir` is informational and may be local-machine specific.

### model

Expected fields:

    model_id
    model_source
    model_profile
    label
    family
    role
    quant
    model_path
    model_path_policy

Privacy policy:

- `model_path` should be `redacted`.
- `model_path_policy` should describe redaction.
- Importers should not require the original local GGUF path.
- `model_source` is `model_profile` or `direct_model_path`.

New v0.70-compatible results may include optional `model.provenance` metadata
for local model identity and public display fingerprints. Absence of this
object does not invalidate older results.

Current `model.provenance` fields:

    source_type
    filename
    file_size_bytes
    sha256
    public_fingerprint
    status
    warning

`status` is `available` or `unavailable`. When unavailable, `sha256`,
`file_size_bytes`, and `public_fingerprint` are null and `warning` explains
the collection failure. The current slice does not parse GGUF metadata.

#### Checkpoint-directory provenance (additive, M2)

Results may additionally carry a `checkpoint_directory_manifest` shaped
`model.provenance` object for a local Hugging Face / Transformers-style
checkpoint directory. This is the accepted bounded directory identity
contract
([first-class architecture §4.2](FIRST_CLASS_RUNTIME_ARCHITECTURE.md),
[vLLM runtime contract](VLLM_RUNTIME_CONTRACT.md)); no runtime consumes it
yet. Historical results and GGUF-shaped provenance are unchanged, and
`llmgauge.result.v0` is not bumped.

Fields:

    source_type
    provenance_kind: checkpoint_directory_manifest
    status: available | partial | unavailable
    reason
    warnings
    manifest_schema: llmgauge.checkpoint_directory_manifest.v0
    manifest: ordered [{path, size, sha256}] entries (private evidence)
    manifest_sha256 (private full fingerprint)
    public_fingerprint: sha256:<16 lowercase hex>
    entry_count
    weight_file_count
    architecture
    model_type
    repository_id
    revision
    repository_id_source
    tokenizer_identity: {status, files, sha256, public_fingerprint}
    chat_template_identity: {status, source, selection_method, encoding,
        sha256, public_fingerprint}
    checkpoint_quantization: {status, method, sources}
    effective_quantization: {status, reason}
    fingerprint_eligible
    fingerprint_ineligible_reason

Semantics:

- Manifest entries are normalized model-root-relative paths with byte size
  and full SHA-256, unique and lexicographically ordered. The canonical
  manifest fingerprint is the SHA-256 of deterministic UTF-8 canonical JSON
  over the versioned manifest schema identifier plus the ordered entries.
  The public display form is `sha256:` plus the first 16 lowercase hex
  characters; it is a display identifier, not the full local fingerprint.
- The absolute checkpoint root, cache identities, and symlink target paths
  are never persisted in the record. `repository_id`/`revision` are
  descriptive local-only metadata derived conservatively from a recognized
  HF cache snapshot layout (`hf_cache_snapshot_layout`) or null; they are
  never network-resolved and never guessed from names.
- `checkpoint_quantization` is checkpoint-declared evidence only, extracted
  from explicit hashed metadata (`config.json`
  `quantization_config.quant_method` and admitted quantization sidecars),
  with `status` `absent` / `declared` / `conflict` and source-labelled
  `sources` entries. `effective_quantization` is always `unavailable` in
  M2: no runtime observation exists. Requested quantization remains a
  separate profile/runtime concept.
- `status` is `unavailable` when no trustworthy canonical identity exists
  (missing/invalid root or `config.json`, no admitted weights, malformed or
  unsafe index selection, unreadable selected file, selected file changed
  during collection); `partial` when a canonical manifest exists but a
  first-class identity dimension is incomplete or ambiguous (tokenizer
  unavailable, template ambiguous, quantization declarations disagree, or an
  explicit `config.json` `auto_map` dependency on custom code outside the
  admitted allowlist); otherwise `available`. A model without a
  quantization declaration is not partial for that reason.
- `fingerprint_eligible` is the explicit run-fingerprint gate: true only
  when `status` is `available`. Ineligible records carry a precise
  `fingerprint_ineligible_reason` and must not produce a run fingerprint.
- Validators recompute the canonical manifest fingerprint, the public
  fingerprint, and the tokenizer fingerprint from the persisted manifest
  entries and reject divergence. Portable validation never requires the
  original checkpoint directory. Chat-template exact-string identity and
  descriptive metadata are validated structurally and for coherence; they
  are not independently recomputable from result evidence alone.
- Public export replaces the entire private `model.provenance` block with a
  bounded `model.checkpoint_identity` projection (statuses, shortened
  fingerprints, sanitized descriptive identifiers, bounded declared-
  quantization label); manifest entries, full hashes, and any local paths
  are withheld.

### runtime

Expected fields:

    backend
    llama_cli
    ctx_size
    max_tokens
    temperature
    top_p
    top_k
    top_k_state
    min_p
    min_p_state
    seed
    seed_state
    batch_size
    ubatch_size
    parallel_sequences
    gpu_layers
    kv_offload
    cache_type_k
    cache_type_k_state
    cache_type_v
    cache_type_v_state
    flash_attn
    runtime_label
    reasoning_mode
    reasoning_effort
    reasoning_effort_state
    reasoning_budget
    reasoning_budget_state
    fit
    fit_state
    reasoning_preserve
    reasoning_preserve_state
    spec_type
    spec_type_state
    runtime_command_captured
    runtime_command_path
    command
    config_path
    model_profiles_path

Optional reasoning/sampling profile evidence is `runtime.profile`. It contains
`profile_id`, `profile_version`, `profile_kind` (`controlled` or
`vendor_aligned`), `canonical_settings_sha256`, canonical closed `settings`,
`source` (`builtin` or `config`), and sorted `overrides`. The hash is SHA-256
of compact sorted-key UTF-8 JSON for `settings`. The evidence records selected
controls; individual runtime fields remain authoritative. A represented profile
is validated against those fields except for explicit listed overrides. Legacy
results omit this object and remain valid.
Notes:

- `backend` is `llama.cpp` (default) or `vllm` for the external-server slice.
- `reasoning_mode` is one of `off`, `on`, `auto`, `default`, or `unknown`.
- `top_k`, `min_p`, `seed`, cache types, reasoning effort, reasoning
  budget, fit, reasoning preservation, and speculative type are nullable
  requested values.
  Their paired `*_state` is `explicit` or `runtime_default`; omitted/default
  does not claim an observed runtime value.
- `fit` canonically serializes as `on` or `off`; `reasoning_preserve` is a
  boolean; `spec_type` is a canonical comma-separated current llama.cpp
  selection. Explicit `spec_type: none` is distinct from omission.
- Requested fit or reasoning preservation and accepted speculation flags do not
  prove effective model/template behavior, observed placement, or acceptance.
- `kv_offload` is `requested_on` for current llama.cpp runs. This is a command
  request, not proof of observed GPU residency.
- `parallel_sequences` is `1` for current llama.cpp runs.
- `command` is a redacted legacy inline summary; prompt values are replaced by
  a raw-artifact placeholder.
- `runtime_command_path` points to `runtime-command.json` when captured.
- For `backend=vllm`, command metadata is not captured; use
  `vllm-runtime-evidence.json` and per-prompt `request/*.json` instead.
- `config_path` and `model_profiles_path` may be local-machine specific.
- All fields above are additive. Historical v0 artifacts without them remain
  readable and validate under their original evidence contract.

## Schema: llmgauge.vllm_runtime_evidence.v0

Primary file:

    vllm-runtime-evidence.json

Expected fields (optional values may be `unknown` or null):

    schema_version
    lifecycle_ownership
    backend
    proxy_bypass_policy
    endpoint_identity
    requested_served_model
    observed_served_model
    observed_served_models
    readiness_status
    connect_timeout_seconds
    request_timeout_seconds
    max_response_bytes
    vllm_version
    vllm_version_source
    server_state
    server_state_meaning
    observed_system_fingerprints
    system_fingerprint_claim
    streaming
    authentication

`endpoint_identity` records only scheme, loopback class, port, and proxy-bypass
policy. Raw URLs, credentials, headers, and proxy environment values are not
stored.

Optional fields are additive: older artifacts without them remain valid.

For current represented transport evidence, `streaming: true` requires
`transport_mode: "openai_compatible_sse"`; `streaming: false` requires no
streaming transport mode. `validate-result` recomputes agreement with the
result runtime, per-request evidence, any private stream evidence, and any
Area 4 TTFT record. It does not trust a stored consistency boolean.

- `vllm_version`: bounded string from server `GET /version`, or `unknown`.
- `server_state`: API readiness observation (`ready` or `unknown`), not process
  ownership or cold/warm lifecycle history.
- `observed_system_fingerprints`: ordered unique opaque fingerprints from the run.

## Schema: llmgauge.vllm_request_evidence.v0## Schema: llmgauge.vllm_stream_evidence.v0

Private per-request stream evidence artifact for the opt-in vLLM streaming
evidence mode (`--vllm-streaming-evidence`). Preserved as
`request/<prompt>.stream.json`; omitted from public export. Makes TTFT
recomputable by the Area 4 validator.

Required top-level fields:

- `schema_version`: `"llmgauge.vllm_stream_evidence.v0"`
- `transport_mode`: `"openai_compatible_sse"`
- `streaming`: `true`
- `observation_method`: `"llmgauge.vllm_stream_evidence.v0"`
- `vllm_version`: observed server version string
- `version_qualification`: `{"admitted": bool, "rule": str, "observed_vllm_version": str}`
- `return_token_ids`: `true`
- `stream_options`: `{"include_usage": true}`
- `request_start_relationship`: `"elapsed_seconds_since_transmit_start"`
- `events`: ordered list of per-event records with `index`, `elapsed_seconds`,
  `kind` (`"data"` | `"done"`), `data` (exact SSE event payload), `token_ids_count`,
  `ttft_trigger`
- `first_token`: nullable object with `event_index`, `elapsed_seconds`,
  `channel` (`"reasoning"` | `"content"` | `"other_generated"`), `token_ids_in_event`
- `terminal`: object with `state`, `finish_reason`, `usage_present`,
  `done_received`, `server_error`, `malformed_event_index`
- `failure`: object with `class` and `detail` (nullable)

A completed transmitted streaming request requires this artifact in the
canonical private result, including the exact qualified vLLM identity. A
pre-transmission capability/readiness failure may omit it. A transmitted
streaming failure may omit it only when no stream event was observed; once
stream events exist, the artifact preserves them whether or not TTFT became
available. Public export intentionally omits this private artifact and its
TTFT references while retaining admitted transport disclosure.



Primary files:

    request/<prompt_id>.json

Bounded per-request evidence for non-streaming chat-completions. Does not store
full response bodies, arbitrary headers, or raw endpoint URLs.

Optional additive fields when present:

    system_fingerprint
    system_fingerprint_status
    system_fingerprint_claim

`system_fingerprint` is opaque backend metadata from the chat response when the
value is a bounded non-empty string without control characters. Status may be
`present`, `absent`, or `invalid`. Invalid optional fingerprint metadata must not
discard an otherwise valid model answer.

New v0.70-compatible results may include optional `runtime.backend_provenance`.
LLMGauge remains llama.cpp-first; this is not a generic backend abstraction.

Current backend provenance fields:

    backend_name
    executable_filename
    executable_file_size_bytes
    executable_sha256
    public_executable_fingerprint
    status
    warning
    reported_version
    commit
    build_number
    build_type
    build_metadata
    discovery_status
    discovery_warning

When unavailable, executable size, full hash, and public fingerprint are null
and `warning` explains the collection failure. Discovery fields remain null or
absent when the bounded version probe is unavailable or unparseable. The full
executable path and unrestricted probe output are not stored.

## Schema: llmgauge.runtime_command.v0

Primary file:

    runtime-command.json

Expected fields:

    schema_version
    command_argv
    executable
    model_path
    model_source
    model_id
    model_profile
    suite_id
    suite_version
    ctx
    max_tokens
    temperature
    top_p
    top_k
    top_k_state
    seed
    seed_state
    batch
    ubatch
    parallel_sequences
    gpu_layers
    kv_offload
    cache_type_k
    cache_type_k_state
    cache_type_v
    cache_type_v_state
    flash_attn
    runtime_label
    reasoning_mode
    reasoning_effort
    reasoning_effort_state
    reasoning_budget
    reasoning_budget_state
    fit
    fit_state
    reasoning_preserve
    reasoning_preserve_state
    spec_type
    spec_type_state
    prompt_transport
    prompt_commands
    command_argv_scope
    prompt_placeholder
    prompt_source_note
    created_at

- `command_argv` is structured argv, not a shell string. For a one-prompt run
  it is that invocation; otherwise `command_argv_scope` marks it as a template
  and `prompt_commands[]` is authoritative.
- Model paths in `command_argv` are redacted.
- Prompt values in `command_argv` and `prompt_commands[].command_argv` use a
  raw-artifact placeholder. `prompt_commands[]` records the exact `argv` or
  temporary `file` transport per prompt; raw text remains under
  `raw/*.prompt.md`.
- `prompt_transport.argv_max_utf8_bytes` is the deterministic 64 KiB selection
  threshold. `file` transport is local, temporary, and passed as structured
  `--file` argv; its transient path is never presented as durable evidence.
- Older runs may omit this file; `runtime.runtime_command_captured` records availability.


### suite

Expected fields:

    suite_id
    suite_version
    suite_path
    prompt_count
    include
    only

Notes:

- `suite_path` may be local-machine specific.
- `include` records the selected category or `all`.
- `only` records a single prompt id when used.

Coding Core native runs may add a closed portable `suite.selection` object with
selection kind, selected profile, exact ordered selected prompt IDs, canonical
prompt IDs, and default profile. Its logical membership is portable identity;
the existing local `suite_path` is not. `selected_prompt_ids` takes precedence
over legacy `include` and `only` invocation metadata when the optional object is
present.

### results

`results` is a list of prompt result objects.

Expected prompt result fields:

    prompt_id
    title
    category
    status
    raw_prompt_path
    raw_output_path
    cleaned_output_path
    stderr_log_path
    metrics
    score
    failure_labels
    notes
    exit_status
    error

For `coding-core-v1` `0.1.0`, each prompt may include a closed `coding_core`
object containing exact response-form and scoring-method provenance plus a
derived manual-review state. Hybrid prompts also contain the complete
non-executing deterministic record and fail-closed side-by-side composition.
Manual-only prompts contain neither. The independent deterministic record is
authoritative and its composition copy must match exactly; the applied `score`
object remains authoritative for full manual evidence and provenance.

Deterministic `pass` and `fail` describe observed structure only. `error`
describes check/resource/configuration failure, and `not_run` describes absent
raw response evidence after generation failure. The check uses `raw_output_path`
evidence, never cleaned output. Hybrid incompleteness is not prompt failure, and
no numeric profile-level Coding Core score is produced.

Coding Core `report.md` adds a per-prompt evidence table and explicit boundaries:
generated content was not executed, structural conformance is not semantic or
runtime correctness, manual review remains semantic authority, incomplete
hybrid evidence is not failure, and no universal or profile-level Coding Core
score exists. Other suite reports retain their existing sections.

Expected `status` values:

    completed
    failed

Path policy:

- `raw_prompt_path`, `raw_output_path`, `cleaned_output_path`, and `stderr_log_path` are relative to the result directory.
- Importers should resolve these paths from the containing result directory.

### Native multi-turn transcript

Primary contained file:

    transcript/transcript.json

Expected schema identity:

    llmgauge.transcript.v0

The closed transcript records protocol `llmgauge.sequential_supplied_feedback`
`0.1.0`, evaluation class `native_multi_turn_response`, conversation/suite/task
and initial-state identity, fixed `/model` and `/runtime` provenance
relationships, declared and effective limits, completion and terminal facts,
one canonical discriminated `events` order, branch relationships,
final-response selection, and non-numeric review hooks.

The ordered top-level `feedback_plan` is the sole authority for every declared
feedback item's ID, origin, one-based `after_model_turn` schedule, exact source
content, and lifecycle. Lifecycle is `unreached`,
`supplied_unconsumed`, or `consumed`, paired with a closed disposition reason,
an actual supply event ID when supplied, and an exact logical consuming turn
when consumed. Declarations beyond an effective `--max-turns` limit and
declarations not reached before runtime failure, timeout, malformed response,
operator stop, or abandonment remain preserved as `unreached`; they are not
silently omitted or mislabeled as supplied. A feedback event represents only
an actual inert supply occurrence. Consumed feedback has an exact reciprocal
association on every attempt in its consuming logical turn, including fully
failed attempts.

Event kinds are `task`, `model_attempt`, `feedback`, `state`, and `terminal`.
Every response attempt remains represented with a unique attempt/event identity,
an independent closed attempt state, and its exact integer adapter exit status.
A malformed response may retain status `0`; a timeout may retain a negative or
platform-specific status; and a nonzero failure retains its exact code.
llama.cpp records the runtime subprocess status. vLLM records adapter-level `0`
for success or `1` for represented request failure, not an operating-system
subprocess code. Retries of one logical turn share its `turn_id`, input state,
rendered input, parent, branch, and consumed-feedback identity while retaining
separate raw input, output, stderr, exit-status, and cleaned-derivative evidence.
State events preserve exact visible-message snapshots and backward transitions.
Source references carry full SHA-256, availability, capture, truncation,
redaction, and source/derivative roles.

The optional prompt-result `transcript_event_id` is a compatibility link to the
selected final response, not a second transcript authority. Its `exit_status`
is the exact status of the selected compatibility attempt (the final selected
response for completion, otherwise the last attempt), not a synthesized
completion flag. For llama.cpp, compatibility metrics parse the same combined
authoritative raw output and runtime stderr evidence as ordinary single-turn
runs; absent metrics in both sources remain absent. Existing `results[].score`
remains null; transcript completion and terminal state are not generation
status, manual verdict, or a numeric score.

Loading uses the contained-result resolver and bounded reads. Traversal,
absolute or escaping paths, unsafe symlinks, missing/unreadable source evidence,
duplicate authority paths, hash mismatches, unsupported versions, malformed
vocabularies, order/reference cycles, inconsistent feedback/state/terminal
facts, and invalid capture roles fail closed.

Structural validity does not prove semantic quality, feedback execution, safety,
human approval, publication readiness, or Agent Harness success. Current
single-turn scoring and public-export methods fail closed for a represented
transcript; `compare` routes all-transcript result sets to the bounded
structural comparison defined by the
[Transcript Comparison and Review Contract](TRANSCRIPT_COMPARISON_REVIEW_CONTRACT.md)
and fails closed on mixed transcript/single-turn sets; `export-index` may
expose only its discovery index.

### summary

Expected fields:

    completed
    failed
    manual_score_total
    manual_score_max
    manual_score_average
    scoring_status
    scored_prompt_count
    failure_labels
    good_labels
    verdict_counts
    rubric_id
    rubric_version
    score_schema_version

Notes:

- `completed` and `failed` should match prompt result statuses.
- Manual score fields may be null until scoring is applied.
- `scoring_status` is one of `unscored`, `review_metadata_only`, `partially_scored`, or `scored`.
- `score_entry_count` records how many prompt results contain applied score objects, including metadata-only score entries.
- `scored_prompt_count` records how many prompt results contain numeric applied score averages.
- `manual_score_average` is a human-review summary on the configured score scale.
- `failure_labels` and `good_labels` are aggregate label-count mappings from applied scores.
- `verdict_counts` summarizes non-empty prompt verdicts from applied score objects.
- `scoring_mode_counts` summarizes applied score provenance modes such as `manual` or `automatic_rules`.
- `needs_review_verdict_count` counts applied score entries whose verdict is `needs_review`.
- `unreviewed_score_count` counts applied score entries marked `reviewed: false`.
- `missing_score_rationale_count` counts applied score entries without a non-empty `score_rationale`.
- `rubric_id`, `rubric_version`, and `score_schema_version` are copied from applied prompt scores when present.
- These fields are public-proof metadata for report generation and importers. They are not automated judgments.

## Canonical identity and fingerprints

Canonical identity metadata is additive. Older result directories that lack
identity fields remain valid.

Canonical JSON serialization sorts mapping keys and uses deterministic UTF-8 JSON
bytes. YAML mapping order must not affect hashes. Sequence order remains
meaningful when it affects prompt or suite semantics.

Prompt identity combines the evaluation-relevant prompt definition:

- prompt text
- system text
- output contract
- scoring rubric reference or embedded rubric
- evaluation-relevant prompt metadata
- template-specific instructions

Suite identity combines canonical suite content and prompt definition identities.

New finalized single-run results may include an optional top-level
`run_fingerprint` object:

    schema_version: llmgauge.run_fingerprint.v0
    algorithm: sha256
    value: sha256:<64 lowercase hex characters>

The run fingerprint identifies canonical private evidence, not model quality,
publication readiness, a unique execution instance, or transformed public-export
bytes. Its canonical payload includes strong model/backend provenance when
available, suite identity and optional portable logical selection, ordered
prompt identities, material runtime settings, per-prompt execution status and
exit status, and SHA-256 values for authoritative raw prompt, raw output,
stderr, and VRAM sample artifacts.

It excludes run ID, run timestamp, local paths, reports, cleaned output, scores,
reviewer metadata, comparison reports, export indexes, and public-export
manifests. Validation accepts legacy results without the optional field; when
present, it recomputes and checks the fingerprint without rewriting it.

### Area 4 native llama.cpp evidence

Native single-turn llama.cpp results may include optional top-level
`runtime_neutral_metrics` (`llmgauge.runtime_neutral_metrics.v1`) and
`failure_taxonomy` (`llmgauge.failure_taxonomy.v1`) objects. Their absence
remains valid for historical results. The first slice records LLMGauge-observed
request wall time for each measured prompt attempt when its monotonic
process-launch-to-terminal-output boundary was captured, plus an optional
derived `llmgauge.metric.v1.peak_vram` record per observed device when that
prompt's VRAM sampling was attempted (maximum absolute used MiB over the
preserved per-prompt samples; unavailable rather than zero without valid
samples). Native llama.cpp diagnostic timing and layer-offload counts may be
preserved on the contained execution artifact and copied as observed
placement metadata; they are not mapped to Area 4 load, prefill, decode, or
TTFT metrics. TTFT remains unavailable for non-streaming native CLI runs.
Layer N/N does not prove full accelerator residency. Historical results
without these optional facts remain valid.


The associated contained `native/*.execution.json` artifacts preserve bounded
native execution evidence. The derived taxonomy is limited to runtime
environment launch failure, model-weight-load OOM, KV-cache OOM, and
unclassified unknown; it does not replace source stderr, exit status, or
timeout evidence. Exact IDs, references, availability, and v1 fingerprint
rules are defined in [Area 4 native llama.cpp evidence v1](AREA4_NATIVE_LLAMA_CPP_EVIDENCE_V1.md).

For a lineage-qualified llama.cpp runtime — an observed `build_number` plus
`commit` pair resolving to exactly one record of the frozen packaged
upstream identity manifest (`llmgauge.llama_runtime_lineage.v1`,
`src/llmgauge/data/llama_runtime_lineage.json`, policy
`upstream_identity_allowlist`) — the execution artifact may additionally
carry the current `load_tensors:` placement prefix as
`llama_cpp_placement.source` (distinct from historical `llm_load_tensors`),
preserved authoritative diagnostic `raw_lines` for validator recomputation,
and, only when the matched record independently admits slot timing, a
separate `slot_print_timing` object holding the request-final server-slot
block's admitted fields. Placement admission covers builds 9538..10449;
slot-timing admission covers the 44-identity subset 10406..10449.
`slot_print_timing` is a distinct backend-native source identity: it never
populates `llama_cpp_timing`, and its `load_time_seconds`,
`total_time_seconds`, and `graphs_reused` remain null (rejected for that
source). Its `generation_tps` is the source rate over `n_gen - 1` decode
steps while `eval_token_count` preserves the displayed `n_gen`; validators
recompute both from the preserved lines. Capture runs the qualified
executable at effective verbosity 4; successful runs persist only the
admitted diagnostic lines plus warning/error output in `logs/`, never the
full verbosity trace. A placement-only identity never emits a
`slot_print_timing` object even when matching timing lines are present.
Unqualified or unknown runtimes never emit current-prefix evidence.
`runtime.native_diagnostics_capture` records the bounded lineage facts
(policy, identity match, matched canonical short commit, observed build,
independent admission flags, effective verbosity, reason); validators
recompute them from persisted backend provenance plus the packaged
manifest and reject divergence. Pre-lineage capture blobs without
`lineage_policy` are historical records and are not reinterpreted.
Historical results without these fields remain valid.

Results with Area 4 evidence use `llmgauge.run_fingerprint.v1` and a v1 payload
that adds canonical Area 4 records and hashes their referenced native execution
artifacts. Existing `llmgauge.run_fingerprint.v0` payloads remain unchanged and
continue to verify unchanged.

### Area 4 vLLM request evidence

External vLLM results may also carry the same optional
`runtime_neutral_metrics` (`llmgauge.runtime_neutral_metrics.v1`) and
`failure_taxonomy` (`llmgauge.failure_taxonomy.v1`) top-level objects. The
vLLM slice maps `llmgauge.metric.v1.request_wall_time` for transmitted
requests, with the timer boundary
`request_transmit_to_validated_response`: monotonic time from immediately
before request serialization through receipt and structural validation of the
complete non-streaming response. The preserved native
`request_wall_time_seconds` field in `request/*.json` artifacts keeps its own
meaning and is unchanged.

When a request-window VRAM sampler is available for a transmitted vLLM
request, one `llmgauge.metric.v1.peak_vram` record per observed device is
additionally emitted with the request-window observation boundary
(`request_window_peak_vram_observation`: absolute device-used memory sampled
via a bounded concurrent NVIDIA telemetry probe, distinct from the native
llama.cpp process-window boundary). Sampler failure never affects the request
outcome; the metric becomes `unavailable` rather than zero when no valid
samples exist. Historical vLLM results without VRAM evidence remain valid.

Under the non-streaming default, no TTFT, prefill, decode, load, or placement
neutral records are emitted for vLLM. Under the explicit opt-in streaming
evidence mode (`--vllm-streaming-evidence`), `llmgauge.metric.v1.time_to_first_token`
is emitted with the `request_transmit_to_first_generated_token` boundary,
provenance `llmgauge_observed`, and contained evidence refs pointing to the
preserved private stream evidence artifact (`llmgauge.vllm_stream_evidence.v0`,
`request/<prompt>.stream.json`). The non-streaming default is unchanged, and
historical results remain valid. Prefill, decode, load, and placement remain
unavailable for vLLM regardless of mode. `workload.cache_state` remains
`unknown`; API readiness does not imply warm or cold.

The derived failure taxonomy maps vLLM failure classes (`endpoint_unavailable`,
`request_timeout`, `malformed_response`, `served_model_mismatch`, and others)
to the existing closed categories, citing `request/*.json#/failure_class`.
Historical vLLM results without Area 4 evidence remain valid; llama.cpp Area 4
evidence is unchanged.

Results with vLLM Area 4 evidence use `llmgauge.run_fingerprint.v1` (or the
appropriate higher version when extended evidence is present) and hash the
contained `request/*.json` artifacts as the authoritative per-prompt evidence.
vLLM results without Area 4 carry no fingerprint because model SHA-256
provenance is unavailable for the served-model path; that behavior is
unchanged. Public export sanitizes the request evidence files and preserves
the Area 4 objects unchanged.

Results with imported external-benchmark evidence use
`llmgauge.run_fingerprint.v2` and a v2 payload that includes the evidence
schema and contract versions, evaluation class, source type, source-package
SHA-256, immutable identity and native-metric projection, and hashes of
contained source members. Import timestamps, external locators, review notes,
reports, comparisons, public exports, and LocalMaxxing payloads are excluded.
Existing `llmgauge.run_fingerprint.v0` and `llmgauge.run_fingerprint.v1`
payloads remain unchanged and continue to verify unchanged.

Results that record extended llama.cpp sampling, seed, KV-cache, or reasoning
configuration use `llmgauge.run_fingerprint.v3`. Its v3 payload adds those
requested values and request states, the KV offload request, and one parallel
sequence to the material runtime-settings boundary. It retains Area 4 evidence
when present.

Results that record llama.cpp fit, reasoning-preservation, or
speculative-decoding controls use `llmgauge.run_fingerprint.v4`. Its v4
payload extends the v3 runtime-settings boundary with those requested values
and request states. Historical v3 artifacts without the controls remain
byte-verifiable. Controlled v3 artifacts produced during the additive control
rollout also remain verifiable; newly generated controlled runs use v4.
Existing v0, v1, v2, and v3 payloads are not reinterpreted or rewritten.

Results whose model provenance is an admitted `checkpoint_directory_manifest`
record use `llmgauge.run_fingerprint.v6` and a v6 payload. The v6 model
identity is the cryptographic checkpoint manifest fingerprint recomputed from
the persisted ordered manifest entries (path, size, full SHA-256), plus the
versioned manifest schema identifier, tokenizer identity, chat-template
identity, checkpoint-declared quantization evidence, eligibility state, and
descriptive model fields; it also carries the v5 superset runtime-settings and
Area 4/transcript boundaries when represented. The absolute checkpoint root,
cache identities, and symlink targets are never payload inputs. v6 is emitted
only for fingerprint-eligible directory provenance; ineligible records fail
closed with a precise reason and never fabricate identity from a model name,
directory basename, or the shortened public fingerprint. Existing v0-v5
payloads are frozen: GGUF and served-model results keep their existing
versions, payload bytes, and verification behavior unchanged.

Results whose model provenance is an admitted `checkpoint_directory_manifest`
record bound to an external vLLM server run (M3) use
`llmgauge.run_fingerprint.v7` and a v7 payload. v7 keeps the v6 model-identity
boundary (recomputed manifest fingerprint, tokenizer and chat-template
identity, declared/effective quantization, ordered manifest entries) but
replaces the direct-process backend identity with a server-backed identity:
backend `vllm`, runtime provenance kind `external_server`, the observed
server-reported `/version` string and its source, the API-readiness state,
the ordered-unique opaque `system_fingerprint` summary, and the
checkpoint-to-served-model binding record. v7 never claims server-binary
attestation: an operator-managed server has no LLMGauge-observed executable
SHA-256, none is invented, and the checkpoint hash is never reused as
runtime identity. A non-empty observed `/version` is required for v7
construction; without it the run fingerprint is unavailable with a precise
reason while the result itself remains valid under the external-server
evidence ceiling. The local endpoint host/IP/port and the absolute
checkpoint root are never payload inputs. v7 is emitted only for
checkpoint-directory provenance with a server binding record: GGUF results,
direct-process checkpoint results (v6), and `served_model_reference` vLLM
results (no fingerprint) keep their existing selection unchanged. Existing
v0-v6 payloads are frozen: their bytes and verification behavior are
unchanged and regression-pinned.

## Schema: llmgauge.vllm_checkpoint_binding.v0

Optional additive `runtime.checkpoint_binding` object for a vLLM run bound to
a local checkpoint directory (M3). Its presence alongside
`checkpoint_directory_manifest` model provenance selects the v7 run
fingerprint. Top-level expected keys:

    schema_version
    status
    binding_provenance_class
    lifecycle_ownership
    requested_served_model
    observed_served_model
    served_model_observation_source
    checkpoint_public_fingerprint
    checkpoint_identity_source
    evidence_ceiling
    effective_runtime_chat_template
    effective_runtime_quantization
    fingerprint_eligible
    fingerprint_ineligible_reason (present only when ineligible)

Semantics: `status` is `bound` when the requested served model was observed
in the server listing and `unbound` otherwise. `binding_provenance_class` is
`operator_declared` for external-server results; the vocabulary also names
`server_reported` and `llmgauge_observed`, but validators reject any class
other than `operator_declared` while `lifecycle_ownership` is
`external_operator`, because a server listing attests only the server's own
served identity, never the local checkpoint bytes behind it.
`checkpoint_public_fingerprint` is the shortened `sha256:`+16 display
fingerprint linking to `model.provenance`; the full manifest, full hashes,
and the absolute checkpoint root are never recorded here (validators reject
path-shaped fields). `effective_runtime_chat_template` is `unobserved` and
`effective_runtime_quantization` is `unavailable`: the external server's
actual rendering template and loaded quantization are not observable from
the client side under this contract. `fingerprint_eligible` is true only
when the binding is `bound` and a non-`unknown` server `/version` was
observed; ineligible records carry a precise
`fingerprint_ineligible_reason`. Historical vLLM results without this object
remain valid; `llmgauge.result.v0` is not bumped.

## Context ladder directory

A context ladder directory contains:

    ladder-summary.json
    ladder-report.md
    ctx-8192/
    ctx-16384/
    ctx-32768/

Each `ctx-*` child directory should be a normal single run directory with its own `llmgauge-result.json`.

Required machine-readable file:

    ladder-summary.json

Human-readable file:

    ladder-report.md

## Schema: llmgauge.context_ladder.v0

Primary file:

    ladder-summary.json

Top-level expected keys:

    schema_version
    ladder_id
    suite_id
    model_id
    include
    only
    contexts
    child_runs
    summary
    max_context_policy

Expected `schema_version`:

    llmgauge.context_ladder.v0

### contexts

`contexts` is an ordered list of context sizes.

Example:

    [8192, 16384, 32768]

The order should match `child_runs[*].ctx_size`.

### child_runs

`child_runs` is an ordered list of child result summaries.

Expected fields:

    ctx_size
    status
    result_dir
    completed
    failed
    error

Expected `status` values:

    completed
    failed

Rules:

- Completed child runs should point to valid single run directories.
- Failed child runs should preserve error text.
- `result_dir` may be local-machine specific.
- Importers should preserve source path and validation status.

### summary

Expected fields:

    total
    completed
    failed

Rules:

- `total` should equal the number of child runs.
- `completed` should equal the number of completed child runs.
- `failed` should equal the number of failed child runs.

### max_context_policy

Expected fields:

    normal_max_context
    extreme_max_context
    allow_extreme_context
    has_extreme_context
    requires_explicit_opt_in_above_normal_max

Current defaults:

    normal_max_context: 65536
    extreme_max_context: 262144

Purpose:

- Preserve whether a run used normal bounded context behavior.
- Preserve whether explicit extreme-context opt-in was used.
- Help importers and reviewers distinguish ordinary 64k-and-under ladders from extreme context experiments.

## Model batch directory

A model batch directory contains:

    batch-summary.json
    batch-report.md
    model-01-<profile-name>/
    model-02-<profile-name>/

Each `model-*` child directory should be a normal single run directory with its own `llmgauge-result.json` when that model run reached execution.

Required machine-readable file:

    batch-summary.json

Human-readable file:

    batch-report.md

## Schema: llmgauge.batch_manifest.v0

Batch manifests are input files, not result artifacts, but their schema is part of the file-based workflow.

Expected `schema_version`:

    llmgauge.batch_manifest.v0

Expected fields:

    schema_version
    batch_id
    suite
    include
    only
    max_tokens
    models

Rules:

- `batch_id` is optional and defaults to the manifest file stem.
- `suite` is required.
- `include` defaults to `all`.
- `only` is optional.
- `max_tokens` is optional and must be a positive integer when set.
- `models` is required and must be a non-empty list of unique model profile names.
- Batch manifests do not accept arbitrary model paths.

## Schema: llmgauge.batch_summary.v0

Primary file:

    batch-summary.json

Top-level expected keys:

    schema_version
    batch_id
    manifest_path
    suite_id
    suite_path
    include
    only
    max_tokens
    models
    execution
    summary
    child_runs

Expected `schema_version`:

    llmgauge.batch_summary.v0

### execution

Expected fields:

    mode
    model_reference_policy
    parallelism

Current values:

    mode: sequential
    model_reference_policy: manifest model entries are model profile names only
    parallelism: disabled

Purpose:

- Preserve that the batch was run sequentially.
- Preserve that model references came from profile names rather than arbitrary model paths.
- Preserve that parallel execution was not used.

### models

`models` is an ordered list of model profile names from the manifest.

The order should match `child_runs[*].model_profile`.

### child_runs

`child_runs` is an ordered list of child result summaries.

Expected fields:

    model_profile
    model_id
    status
    result_dir
    completed
    failed
    error

Expected `status` values:

    completed
    failed

Rules:

- Completed child runs should point to valid single run directories.
- Failed child runs should preserve error text.
- A failure can occur before a child run directory is written, such as when a model file path is missing.
- `result_dir` may be local-machine specific.
- Importers should preserve source path and validation status.

### summary

Expected fields:

    total
    completed
    failed

Rules:

- `total` should equal the number of child runs.
- `completed` should equal the number of completed child runs.
- `failed` should equal the number of failed child runs.

### Validation

Batch directories can be validated with:

    uv run llmgauge validate-batch <batch-dir>

Validation checks the parent `batch-summary.json`, summary counts, child status values, model order, failed-child error preservation, and completed child result directories.

### Export status

Batch directories are included in `llmgauge.export_index.v0`.

Batch export-index items use:

    artifact_type: batch

Batch export-index support indexes the parent batch artifact. It does not automatically expand every child run into separate run items. Importers that need child-level detail should follow `child_runs[*].result_dir` from `batch-summary.json` or index child run directories explicitly.

## VRAM guardrails

Prompt results may include warning-only VRAM guardrail metadata.

Schema:

    llmgauge.vram.guardrails.v0

Expected fields:

    schema_version
    status
    min_headroom_warn_mib
    observed_headroom_mib
    warnings

Supported `status` values:

    ok
    warning

Current warning labels:

    vram_headroom_below_warning_threshold

Guardrails are informational in this schema version. They do not change prompt status, run status, validation status, or exit behavior.

If no threshold is configured, or VRAM is unavailable, prompt results may use:

    "vram_guardrails": null

## Export index

An export index is a discovery artifact, not a source-of-truth result.

Primary file convention:

    llmgauge-index.json

## Schema: llmgauge.export_index.v0

Top-level expected keys:

    schema_version
    generated_at_utc
    item_count
    validation_checked
    items

Expected `schema_version`:

    llmgauge.export_index.v0

### validation_checked

Boolean.

If false, indexed artifacts were classified but not validated.

If true, each item should include a `validation` object.

### items

`items` is a list of indexed artifacts.

Supported `artifact_type` values:

    run
    ladder
    fit_ladder
    batch

## Export index item: run

Expected fields:

    artifact_type
    path
    schema_version
    result_json
    report
    scores_yaml
    run_id
    status
    timestamp_utc
    suite_id
    suite_version
    model_id
    model_profile
    prompt_count
    completed
    failed
    manual_score_total
    manual_score_max
    scoring_status
    score_entry_count
    scored_prompt_count
    manual_score_average
    failure_labels
    good_labels
    verdict_counts
    scoring_mode_counts
    needs_review_verdict_count
    unreviewed_score_count
    missing_score_rationale_count
    rubric_id
    rubric_version
    score_schema_version
    has_raw_artifacts
    has_cleaned_artifacts
    has_logs
    vram_available
    peak_vram_mib
    min_vram_headroom_mib
    vram_prompt_count
    vram_sample_artifact_count
    validation

`report` points to `report.md` when present.

`scores_yaml` points to `scores.yaml` when present.

`scoring_status` is one of `unscored`, `review_metadata_only`, `partially_scored`, or `scored`.

Scoring evidence fields (`score_entry_count`, `scored_prompt_count`, `verdict_counts`, `scoring_mode_counts`, `needs_review_verdict_count`, `unreviewed_score_count`, `missing_score_rationale_count`, and rubric metadata) mirror the publish-readiness signals in `report.md` **Publish Readiness Notes**. They help importers summarize score state without opening every prompt result. They are not automated judgments.

`has_raw_artifacts` is true when a `raw/` directory exists.

`has_cleaned_artifacts` is true when a `cleaned/` directory exists.

`has_logs` is true when a `logs/` directory exists.

`vram_available` is true when at least one prompt result has available VRAM summary data.

`peak_vram_mib` is the highest prompt-level peak VRAM usage found in the run, or null.

`min_vram_headroom_mib` is the lowest prompt-level VRAM headroom found in the run, or null.

`vram_prompt_count` is the number of prompt results with available VRAM summary data.

`vram_sample_artifact_count` is the number of referenced VRAM sample artifact files that exist on disk.

Older run artifacts without VRAM data should use:

    "vram_available": false
    "peak_vram_mib": null
    "min_vram_headroom_mib": null
    "vram_prompt_count": 0
    "vram_sample_artifact_count": 0

`validation` appears only when export-index is run with validation enabled.

## Export index item: batch

Expected fields:

    artifact_type
    path
    schema_version
    batch_summary
    batch_report
    batch_id
    manifest_path
    suite_id
    suite_path
    include
    only
    max_tokens
    models
    model_count
    child_run_count
    completed
    failed
    total
    has_child_runs
    has_completed_child_runs
    has_failed_child_runs

Expected `artifact_type`:

    batch

Notes:

- `batch_summary` points to `batch-summary.json`.
- `batch_report` points to `batch-report.md` when present.
- `models` preserves manifest model profile order.
- `child_run_count` is the number of entries in `child_runs`.
- `completed`, `failed`, and `total` come from the parent batch summary.
- `has_failed_child_runs` may be true while validation still passes, because preserved child failures are valid batch state.
- Batch export-index items summarize the parent batch artifact and do not automatically duplicate child run metadata.

## Export index item: ladder

Expected fields:

    artifact_type
    path
    schema_version
    ladder_summary
    ladder_report
    ladder_id
    suite_id
    model_id
    include
    only
    contexts
    child_run_count
    completed
    failed
    total
    has_child_runs
    validation

`validation` appears only when export-index is run with validation enabled.

## Validation payload

When present, validation payloads use:

    checked
    status
    errors

Expected values:

    checked: true
    status: valid | invalid
    errors: list of strings

## Current validation commands

Validate a run directory:

    uv run llmgauge validate-result <result-dir>

Validate a ladder directory:

    uv run llmgauge validate-ladder <ladder-dir>

Validate a batch directory:

    uv run llmgauge validate-batch <batch-dir>

Create an index without validation:

    uv run llmgauge export-index <artifact-dir> --out results/llmgauge-index.json

Create an index with validation metadata:

    uv run llmgauge export-index <artifact-dir> --validate --out results/llmgauge-index.json

## Downstream import guidance

Downstream importers should treat LLMGauge artifacts as external source files.

Recommended import behavior:

1. Accept a result directory, ladder directory, or export index.
2. Check `schema_version`.
3. Run validation where practical.
4. Store import timestamp, source path, schema version, artifact type, and validation status.
5. Store summary metadata in the downstream application's database or index.
6. Link back to raw artifacts rather than copying them by default.
7. Preserve compatibility with any existing downstream records when applicable.

Downstream importers should not assume that LLMGauge artifacts are stored inside a specific repository or application data directory.

## Compatibility notes

Existing schema versions are still v0-style schemas. They are useful for local tooling and downstream import experiments, but not final public API commitments.

Known schemas:

    llmgauge.result.v0
    llmgauge.context_ladder.v0
    llmgauge.context_prompt.v0
    llmgauge.suite.v0
    llmgauge.export_index.v0
    llmgauge.external_benchmark_evidence.v0
    llmgauge.run_fingerprint.v2

Future changes should prefer additive fields over breaking changes.


## Cleaned output policy

Cleaned output files live under `cleaned/` and are generated from raw model stdout.

They are review conveniences. They may remove obvious llama.cpp terminal wrapper
text, echoed prompt envelope text, and trailing runtime metric lines. They must
not be treated as a replacement for raw output audit evidence.

Older result artifacts may not include `cleaned_output_path`.


## Schema: scores.yaml

Primary manual scoring template file:

    scores.yaml

Deterministic assisted drafts use the same schema and are written as:

    auto-scores.yaml

Expected `schema_version`:

    llmgauge.scores.v0

Top-level fields:

    schema_version
    run_id
    scale
    rubric_id
    rubric_version
    dimensions
    allowed_verdicts
    scores

Expected `scale`:

    0-5

Default `rubric_id`:

    default-manual-v0

Default `rubric_version`:

    0.1.0

`scores` is a mapping from prompt id to score entry.

Expected score entry fields:

    factual_accuracy
    technical_correctness
    safety
    instruction_following
    uncertainty_honesty
    hallucination_severity
    practical_usefulness
    concision
    context_retention
    overall_trust
    failure_labels
    good_labels
    reviewer_notes
    score_rationale
    verdict
    scoring_mode
    scorer_id
    scorer_version
    confidence
    evidence
    warnings
    reviewed
    override_status

Score dimensions may be integers or floats from 0 to 5, or null when not scored.

`failure_labels` and `good_labels` are lists of strings.

`reviewer_notes` is freeform reviewer context.

`score_rationale` is a concise explanation of why the score was assigned.

Optional scoring provenance fields are preserved when present. Manual score
application defaults `scoring_mode` to `manual`, `scorer_id` to
`human-reviewer`, `reviewed` to true, and `override_status` to `none`.
`evidence` and `warnings` are lists of strings. These fields are metadata for
auditability and downstream reporting; they do not turn assisted scores into
objective truth.

`auto-scores.yaml` entries generated by `--auto-draft` use
`scoring_mode: automatic_rules`, `scorer_id: llmgauge-auto-rules`, and
`reviewed: false`. They are review-required drafts and are not applied until
passed explicitly through `llmgauge score RESULT_DIR --scores auto-scores.yaml`.

Allowed verdict values:

    pass
    mixed
    fail
    needs_review

The empty string is also accepted for unassigned verdicts.

Applied prompt score objects in `llmgauge-result.json` preserve the score schema
version, scale, rubric id, rubric version, dimensions, labels, notes, rationale,
verdict, and scoring provenance metadata when present.
