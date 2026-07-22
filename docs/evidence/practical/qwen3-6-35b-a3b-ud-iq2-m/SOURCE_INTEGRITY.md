# Source Integrity

## Canonical source

Private canonical directory:

`results/qwen3_6_35b_a3b_ud_iq2_m-v071-wumbolabs-practical-8k`

The canonical directory was read and validated but not edited after scoring
application for publication packaging. Tracked public-package artifacts live
under `docs/evidence/practical/qwen3-6-35b-a3b-ud-iq2-m/`.

## Deterministic inventory method

For each regular file below the canonical directory, the review inventory
records:

- source-relative POSIX path;
- byte size;
- SHA-256 file digest.

Entries are sorted by relative path. The tree digest is SHA-256 over UTF-8 lines
of:

`<file digest><two spaces><byte size><two spaces><relative path><newline>`

This method is deterministic for file content, size, and relative path. It
intentionally excludes timestamps, ownership, permissions, and directory
entries.

Full private inventories with per-file hashes were retained only in ignored
local review records. They are not part of this tracked package and must not be
published.

## Comparison result

| Property | Before export | After final export | Result |
|---|---:|---:|---|
| File count | 34 | 34 | identical |
| Total bytes | 131,072 | 131,072 | identical |
| Tree digest prefix | `8cab71c6cf494bec` | `8cab71c6cf494bec` | identical |
| Per-file path/size/digest records | recorded | recorded | identical |

Conclusion: the final pre/post inventories match exactly after excluding only
their `label` fields. No canonical source file changed during export, index
generation, or package assembly into the tracked path.

## Derivative relationship

`export-public` selected known artifacts, sanitized text and structured fields,
staged the output, validated the result, and wrote the staged directory. The
final manifest reports 18 transformed source files, 16 copied files, and 0
omitted files.

The derivative is not byte-identical to the source. It redacts private paths,
local username tokens, full local file hashes, and duplicated prompt text. Path
redaction can also reduce the specificity of examples in model outputs. The
private source remains authoritative for raw evidence and audit.

## Fingerprint boundary

The selected source records a run fingerprint and model-file provenance. Roles:

| Carrier | Role |
|---|---|
| Private `llmgauge-result.json` run fingerprint | Identifies the canonical private evidence |
| `public-export-manifest.json` `source_run_fingerprint` | Public record of the source identifier with an explicit non-authentication boundary for transformed export bytes |
| Public `llmgauge-result.json` / export-index `run_fingerprint` | May be redacted or `null` after sanitization; do not treat as proof the source lacked a fingerprint |

The public export retains the source run fingerprint in
`public-export-manifest.json` and keeps the model public fingerprint while
redacting full local SHA-256 values. The validated export index may show
`run_fingerprint: null` on the public result JSON path because the structured
result field is redacted there; the manifest remains the public carrier for the
source run fingerprint value.

A fingerprint is an identifier for canonical evidence. It does not authenticate
model authorship, prove hardware identity, prove answer quality, or authenticate
transformed public-export bytes. Hardware telemetry in the same package is
observed metadata only. The private inventory comparison above demonstrates
local source non-mutation during this workflow; it does not establish upstream
model provenance.

## Validation boundary

The canonical source passed `validate-result`, and the regenerated derivative is
marked valid in the validated export index. These checks establish artifact
structure and references only. They do not validate answer quality, manual
scoring correctness, privacy completeness, or publication claims.

Sanitization and automated scans are bounded controls, not guarantees. Human
review remains required.
