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

### Backend provenance

New real-run results may include additive `runtime.backend_provenance` metadata.
Current fields are:

- `backend_name`: `llama.cpp`
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
