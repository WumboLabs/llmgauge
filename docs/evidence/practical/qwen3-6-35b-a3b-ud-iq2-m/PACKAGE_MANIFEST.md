# Package Manifest

Classification: `review_ready_with_caveats`

Package root: `docs/evidence/practical/qwen3-6-35b-a3b-ud-iq2-m/`

The private result remains canonical. This manifest separates publication-intended
derivatives from private review records.

## Publication-intended files

| Path | Role |
|---|---|
| `README.md` | Concise package landing page and claim boundaries |
| `PUBLIC_EVIDENCE_SUMMARY.md` | Human-facing bounded evidence summary and claim boundaries |
| `PUBLICATION_READINESS.md` | Human publication gate, caveats, and required final actions |
| `SOURCE_INTEGRITY.md` | Public-safe source immutability method, result, and limitations |
| `PACKAGE_MANIFEST.md` | Package contents and disclosure boundary |
| `export-index.json` | One-item machine-readable index with structural validation metadata |
| `public-export/public-export-manifest.json` | Export policy, transformations, omissions, redaction categories, and fingerprint boundary |
| `public-export/llmgauge-result.json` | Sanitized machine-readable run and applied-score evidence |
| `public-export/runtime-command.json` | Sanitized resolved runtime command metadata |
| `public-export/report.md` | Sanitized single-run review report |
| `public-export/scores.yaml` | Sanitized manual score intent |
| `public-export/raw/**` | Sanitized source prompts and raw model outputs for six prompts |
| `public-export/cleaned/**` | Sanitized derived reading aids for six outputs |
| `public-export/logs/**` | Sanitized stderr evidence for six prompts |
| `public-export/vram/**` | Sanitized VRAM samples for six prompts |

The `public-export/` tree contains 35 files including its export manifest.
Together with `export-index.json`, the derived-file privacy scan covered 36
files. The five package Markdown files must receive the same final human review
before publication.

## Private review-only material (not in this tracked package)

Do not publish or track:

| Material | Reason |
|---|---|
| Private pre/post source inventories | Full per-file hashes of canonical private evidence |
| Internal package review reports | Milestone process and repository-state records |
| Run console logs under `tmp/` | Operator process logs that record prompt order/completion only; not a complete resolved execution plan and not publication evidence |
| Canonical private result directory `results/qwen3_6_35b_a3b_ud_iq2_m-v071-wumbolabs-practical-8k/` | Private source evidence; remains local and untracked |
| Legacy private result `results/qwen3_6_35b_a3b_ud_iq2_m-v025-wumbolabs-practical-8k/` | Not the selected source; lacks required provenance artifacts |

None of the above materials are included under this tracked package path.

## Export disposition

Final `public-export-manifest.json` records:

- 18 transformed source files;
- 16 copied source files;
- 0 omitted source files;
- bounded redaction categories for absolute paths, home-directory paths, local
  username, full local SHA-256, and duplicated prompt text;
- source run fingerprint present with an explicit non-authentication boundary
  for transformed bytes;
- the requirement for human review.

Current `scores.yaml`, all applied scores, all six raw/cleaned prompt artifacts,
logs, VRAM samples, and `runtime-command.json` required by the result references
are present.

## Package limitations

- Validation is structural, not answer-quality validation.
- Manual scores are reviewer metadata, not universal truth.
- Three mixed verdicts and their failure labels must remain disclosed.
- Capture caveats (flash-attn `auto`, temporary suite path, console-log limits,
  ~521 MiB VRAM headroom, fingerprint role split, telemetry-only hardware) must
  remain disclosed; see package README and `docs/ROADMAP.md`.
- Fingerprints do not authenticate authorship, hardware, or transformed bytes.
- Sanitization still requires human review.
- The private source remains canonical.
- No comparison ranking, publication, model execution, rescoring, release, or
  network action is included in this package milestone.
