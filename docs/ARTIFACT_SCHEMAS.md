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
URLs, full local SHA-256 values, and legacy inline prompt duplication are
redacted or removed. Relative artifact references and shortened public
fingerprints remain usable. Stderr logs are transformed under the same bounded
text policy so exported result references remain structurally valid.

`public-export-manifest.json` uses schema `llmgauge.public_export.v0` and records
the source artifact type, copied/transformed/omitted relative files, redaction
categories, export timestamp, and the claim boundary that sanitization is not
answer-quality validation. Users must review the export before publication;
the policy is conservative but does not guarantee complete secret removal.

When the source run has a canonical run fingerprint, the manifest records it as
`source_run_fingerprint`. This labels the fingerprint of the canonical private
source evidence only; it does not verify or authenticate transformed
public-export bytes.

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

### runtime

Expected fields:

    backend
    llama_cli
    ctx_size
    max_tokens
    temperature
    top_p
    batch_size
    ubatch_size
    gpu_layers
    flash_attn
    runtime_label
    reasoning_mode
    runtime_command_captured
    runtime_command_path
    command
    config_path
    model_profiles_path

Notes:

- `backend` is `llama.cpp` (default) or `vllm` for the external-server slice.
- `reasoning_mode` is one of `off`, `on`, `auto`, `default`, or `unknown`.
- `command` should redact the model path (legacy inline summary).
- `runtime_command_path` points to `runtime-command.json` when captured.
- For `backend=vllm`, command metadata is not captured; use
  `vllm-runtime-evidence.json` and per-prompt `request/*.json` instead.
- `config_path` and `model_profiles_path` may be local-machine specific.
- Future hardening may add stronger path redaction for public exports.

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

- `vllm_version`: bounded string from server `GET /version`, or `unknown`.
- `server_state`: API readiness observation (`ready` or `unknown`), not process
  ownership or cold/warm lifecycle history.
- `observed_system_fingerprints`: ordered unique opaque fingerprints from the run.

## Schema: llmgauge.vllm_request_evidence.v0

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
    batch
    ubatch
    gpu_layers
    flash_attn
    runtime_label
    reasoning_mode
    prompt_placeholder
    prompt_source_note
    created_at

Notes:

- `command_argv` is structured argv, not a shell string.
- Model paths in `command_argv` are redacted.
- The prompt argument uses a placeholder; per-prompt text lives under `raw/*.prompt.md`.
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

Expected `status` values:

    completed
    failed

Path policy:

- `raw_prompt_path`, `raw_output_path`, `cleaned_output_path`, and `stderr_log_path` are relative to the result directory.
- Importers should resolve these paths from the containing result directory.

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
available, suite identity, ordered prompt identities, material runtime settings,
per-prompt execution status and exit status, and SHA-256 values for
authoritative raw prompt, raw output, stderr, and VRAM sample artifacts.

It excludes run ID, run timestamp, local paths, reports, cleaned output, scores,
reviewer metadata, comparison reports, export indexes, and public-export
manifests. Validation accepts legacy results without the optional field; when
present, it recomputes and checks the fingerprint without rewriting it.

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

Example:

    {
      "checked": true,
      "status": "valid",
      "errors": []
    }

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
