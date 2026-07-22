# Package Manifest

Classification: `review_ready_with_caveats`

Package root: `docs/evidence/practical/grug-12b-q4-k-m/`

The private result remains canonical. This manifest separates publication-intended derivatives from private review records.

## Publication-intended files

| Path | Role |
|---|---|
| `PUBLIC_EVIDENCE_SUMMARY.md` | Human-facing bounded evidence summary and claim boundaries |
| `PUBLICATION_READINESS.md` | Human publication gate, caveats, and required final actions |
| `SOURCE_INTEGRITY.md` | Public-safe source immutability method, result, and limitations |
| `PACKAGE_MANIFEST.md` | Package contents and disclosure boundary |
| `export-index.json` | One-item machine-readable index with structural validation metadata |
| `public-export/public-export-manifest.json` | Export policy, transformations, omissions, redaction categories, and fingerprint boundary |
| `public-export/llmgauge-result.json` | Sanitized machine-readable run and applied-score evidence |
| `public-export/report.md` | Sanitized single-run review report |
| `public-export/scores.yaml` | Sanitized manual score intent |
| `public-export/raw/**` | Sanitized source prompts and raw model outputs for six prompts |
| `public-export/cleaned/**` | Sanitized derived reading aids for six outputs |
| `public-export/logs/**` | Sanitized stderr evidence for six prompts |
| `public-export/vram/**` | Sanitized VRAM samples for six prompts |

The `public-export/` tree contains 34 files including its export manifest. Together with `export-index.json`, the derived-file privacy scan covered 35 files. The four package Markdown files must receive the same final human review before publication.

## Private review-only material (not in this tracked package)

Do not publish or track:

| Material | Reason |
|---|---|
| Private candidate-selection records | Selection analysis over ignored local results |
| Private pre/post source inventories | Full per-file hashes of canonical private evidence |
| Internal package review reports | Milestone process and repository-state records |
| Canonical private result directory `results/grug_12b_q4_k_m-v025-wumbolabs-practical-8k/` | Private source evidence; remains local and untracked |

None of the above materials are included under this tracked package path.

## Export disposition

Final `public-export-manifest.json` records:

- 17 transformed source files;
- 2 omitted source files;
- bounded redaction categories for absolute paths, home-directory paths, local hostname, local username, and duplicated prompt text;
- no source run fingerprint;
- the requirement for human review.

The omitted files are two historical score backup files. Current `scores.yaml`, all applied scores, all six raw/cleaned prompt artifacts, logs, and VRAM samples required by the result references are present.

## Package limitations

- Validation is structural, not answer-quality validation.
- Manual scores are reviewer metadata, not universal truth.
- The source has no run/model fingerprint; fingerprints would not authenticate authorship, hardware, or transformed bytes in any case.
- Runtime-command capture is absent.
- Sanitization still requires human review.
- The private source remains canonical.
- No comparison, ranking, publication, model execution, rescoring, release, or network action is included.
