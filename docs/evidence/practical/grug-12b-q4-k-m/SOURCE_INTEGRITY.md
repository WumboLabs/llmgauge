# Source Integrity

## Canonical source

Private canonical directory:

`results/grug_12b_q4_k_m-v025-wumbolabs-practical-8k`

The canonical directory was read and validated but not edited. Tracked public-package artifacts live under `docs/evidence/practical/grug-12b-q4-k-m/`.

## Deterministic inventory method

For each regular file below the canonical directory, the review inventory records:

- source-relative POSIX path;
- byte size;
- SHA-256 file digest.

Entries are sorted by relative path. The tree digest is SHA-256 over UTF-8 lines of:

`<file digest><two spaces><byte size><two spaces><relative path><newline>`

This method is deterministic for file content, size, and relative path. It intentionally excludes timestamps, ownership, permissions, and directory entries.

Full private inventories with per-file hashes were retained only in ignored local review records. They are not part of this tracked package and must not be published.

## Comparison result

| Property | Before export | After final export | Result |
|---|---:|---:|---|
| File count | 35 | 35 | identical |
| Total bytes | 100,485 | 100,485 | identical |
| Tree digest prefix | `d29c893294aa` | `d29c893294aa` | identical |
| Per-file path/size/digest records | recorded | recorded | identical |

Conclusion: the final pre/post inventories match exactly after excluding only their `label` fields. No canonical source file changed during export, exporter correction, regeneration, index generation, or package review.

## Derivative relationship

`export-public` selected known artifacts, sanitized text and structured fields, omitted unknown score backup files, staged the output, validated the result, and moved the staged directory into place only after success. The final manifest reports 17 transformed source files and 2 omitted files; the remaining selected files were copied unchanged.

The derivative is not byte-identical to the source. It redacts private paths, local hostname and username tokens, and duplicated prompt text. Path redaction can also reduce the specificity of examples in model outputs. The private source remains authoritative for raw evidence and audit.

## Fingerprint boundary

The selected legacy source has no recorded run fingerprint or model-file provenance fingerprint. `public-export-manifest.json` therefore records `source_run_fingerprint: null`, and the export index records `run_fingerprint: null`.

A fingerprint, when available, is an identifier for canonical evidence. It does not authenticate model authorship, prove hardware identity, prove answer quality, or authenticate transformed public-export bytes. The private inventory comparison above demonstrates local source non-mutation during this workflow; it does not establish upstream model provenance.

## Validation boundary

The canonical source passed `validate-result`, and the regenerated derivative is marked valid in the validated export index. These checks establish artifact structure and references only. They do not validate answer quality, manual scoring correctness, privacy completeness, or publication claims.

Sanitization and automated scans are bounded controls, not guarantees. Human review remains required.
