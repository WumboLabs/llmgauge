# Package Manifest

Classification: `review_ready_with_caveats`

Package root:
`docs/evidence/practical/grug-12b-q4-k-m-provenance-refresh-v1/`

The scored private working result is canonical for applied-score review and
export. This manifest separates publication-intended derivatives from private
review records; it does not claim preservation of the unscored live-run bytes.

## Publication-intended files

| Path | Role |
|---|---|
| `README.md` | Package landing page, setup, score summary, and claim boundaries |
| `PUBLIC_EVIDENCE_SUMMARY.md` | Bounded evidence, manual review findings, and limitations |
| `PUBLICATION_READINESS.md` | Human publication gate, privacy review, and required actions |
| `SOURCE_INTEGRITY.md` | Public-safe distinction between unpreserved original state and scored-source export immutability |
| `PACKAGE_MANIFEST.md` | Package contents and disclosure boundary |
| `export-index.json` | One-item index with structural validation metadata |
| `public-export/public-export-manifest.json` | Transformations, omissions, redactions, and fingerprint boundary |
| `public-export/llmgauge-result.json` | Sanitized run, telemetry, provenance, and applied-score evidence |
| `public-export/runtime-command.json` | Sanitized resolved runtime command and settings |
| `public-export/report.md` | Sanitized generated single-run review report |
| `public-export/scores.yaml` | Six manually reviewed score records |
| `public-export/raw/**` | Sanitized prompts and raw outputs for six prompts |
| `public-export/cleaned/**` | Sanitized derived reading aids for six outputs |
| `public-export/logs/**` | Sanitized stderr evidence for six prompts |
| `public-export/vram/**` | Sanitized per-prompt VRAM samples |

The `public-export/` tree contains 35 files including its manifest. Together
with `export-index.json`, the derived-file validation/privacy review covers 36
files. The five package Markdown files require the same final human review
before publication.

## Private review-only material

Do not publish or track:

| Material | Reason |
|---|---|
| Scored canonical private working result | Contains private paths, full local hashes, operator sidecars, and authoritative applied-score/export evidence |
| Pre-scoring and scored-source inventories | The pre-scoring inventory identifies 36 original files, but no complete original copy survives; full hashes remain private |
| Preparation and continuation report under `tmp/` | Internal milestone and Git-state record |
| Prepared live-run wrapper and private preparation record | Local operator controls and private paths/provenance |
| Legacy private Grug result | Separate source; not selected or rescored |

None of that material is included under this tracked package path.

## Export disposition

The final export manifest records 17 copied files, 17 transformed files, and 3
omitted unknown private sidecars. It retains all schema-known scores, applied
review metadata, prompt artifacts, logs, VRAM samples, public provenance,
resolved runtime command, and generated report required by result references.

The omitted sidecars are `operator-capture.json`, `operator-console.log`, and
`private-preflight-provenance.json`. Public documentation discloses their capture
roles and omission without publishing private content.

Redaction tokens remain in reviewed contexts where path-like benchmark or
llama-cli text was transformed. The private raw source is authoritative when
redaction reduces specificity.

## Package limitations

- This is a separate provenance-refresh run; the legacy Grug package remains
  unchanged and is not superseded.
- The original 36-file pre-scoring byte tree was inventoried but not preserved
  as a complete copy. Only the scored 37-file working source was verified
  unchanged through export and package assembly.
- Validation is structural, not answer-quality or privacy proof.
- Scores and verdicts are one manual reviewer's metadata.
- Three mixed verdicts, one fail verdict, and all failure labels must remain
  disclosed.
- One run and six prompts do not support universal rank, winner, recommendation,
  daily-driver, safety, reliability, or fit claims.
- Observed GPU/VRAM values and private hardware capture do not authenticate
  hardware identity or generalize to other systems.
- Fingerprints identify evidence within stated roles; they do not authenticate
  authorship, hardware, quality, or transformed bytes.
- Human review is required before external publication.
