# Publication Readiness

Classification: `review_ready_with_caveats`

Decision: suitable for human publication review as one bounded practical
evidence package. It is not approved for automatic or unreviewed publication.

## Selection decision

Preferred candidate from the milestone handoff: profile
`qwen3_6_35b_a3b_ud_iq2_m` (Qwen3.6-35B-A3B UD-IQ2_M). Local model profiles and
the GGUF path were inspected before launch. The preferred candidate satisfied
the milestone safely and reproducibly, so no alternate profile was substituted.

A prior legacy private result for this profile
(`results/qwen3_6_35b_a3b_ud_iq2_m-v025-wumbolabs-practical-8k`) existed without
run fingerprint or runtime-command capture. It was **not** reused. A new source
run was executed after dry-run review:

`results/qwen3_6_35b_a3b_ud_iq2_m-v071-wumbolabs-practical-8k`

Why this source:

- different model profile from Grug-12B Q4_K_M;
- same practical suite family (`wumbolabs-practical-use-v1` 0.1.0);
- methodology matched the first package where practical (8,192 context; 1,200
  max tokens; temperature 0.2; top-p 0.95; batch 256; ubatch 64; GPU layers 999;
  one complete six-prompt llama.cpp run);
- current provenance and runtime-command capture present;
- complete manual scores, all reviewed, no `needs_review`.

Disclosed methodology and capture caveats:

- Flash-attention mode is `auto` because that is the current CLI default; the
  first package command argv did not include an explicit flash-attention flag.
- Suite identity is `wumbolabs-practical-use-v1` 0.1.0, resolved through the
  temporary path `tmp/wumbolabs-practical-use-v1` rather than a stable tracked
  suite path.
- Operator console logs record prompt order and completion; they are not a
  complete resolved execution plan. Authoritative settings are in result
  artifacts and `runtime-command.json`.
- Observed minimum VRAM headroom was about 521 MiB and is not a general fit
  guarantee.
- Public-result fingerprint fields and export-manifest
  `source_run_fingerprint` roles differ; see `SOURCE_INTEGRITY.md`.
- GPU/VRAM telemetry is observed metadata, not authenticated hardware identity.
  CPU, RAM, OS, and driver metadata were not captured.

Future reference-quality practical runs should follow the capture standard in
`docs/ROADMAP.md`. Any comparison synthesis must disclose methodology
differences before comparing packages.

## Readiness checks

| Check | Result |
|---|---|
| Canonical source completed | PASS: 6 completed, 0 failed |
| Canonical source structural validation | PASS |
| Provenance artifacts present | PASS: model provenance, backend provenance, run fingerprint, `runtime-command.json`, reasoning-mode metadata |
| `scores.yaml` matches applied result scores | PASS: prompt IDs, dimensions, labels, notes, rationales, and verdicts match |
| `llmgauge-result.json` review state | PASS: 6 manual, 6 reviewed, 0 unreviewed |
| `report.md` scoring state | PASS: 6 scored; 3 pass, 3 mixed; all rationales present |
| `needs_review` | PASS: 0 |
| Missing score rationales | PASS: 0 |
| Unreviewed score drafts | PASS: 0; no `auto-scores.yaml` used as final review |
| Transactional public export | PASS: generated successfully in a new output directory |
| Export structural validation | PASS through validated export index |
| Export index validation | PASS: one indexed run, validation status `valid` |
| Source immutability | PASS: pre/post inventories identical |
| Derived-file parsing | PASS: all JSON/YAML parsed |
| Privacy scan | PASS for scanned private patterns (see below) |
| Human claim review | PASS for this package; caveats retained below |

## Privacy review

The final scan covered every file under `public-export/` plus `export-index.json`
and the package Markdown files. It found zero instances of:

- private home-directory paths;
- the local username;
- the local hostname;
- private model or executable directory paths;
- credential assignments or credential-bearing URLs;
- environment-variable dumps;
- loopback, RFC 1918, or other private endpoints.

Publication-intended identity that remains by design:

- model filename `Qwen3.6-35B-A3B-UD-IQ2_M.gguf`;
- public short model fingerprint `sha256:2be7ef1ed7e1af8b`;
- source run fingerprint in the export manifest and report (evidence identifier,
  with non-authentication boundary for transformed bytes);
- public executable fingerprint when present in backend provenance.

Full local 64-character model/executable file hashes are redacted in the public
derivative (`full_local_sha256` redaction category).

The exporter manifest records `absolute_path`, `home_directory_path`,
`local_username`, `full_local_sha256`, and `prompt_duplication` redactions.
No source files were omitted.

## Scoring and claim review

No unresolved review-state blocker remains. The three mixed verdicts are material
publication caveats, not hidden failures:

- Arch/NVIDIA update advice contains an incorrect pending-update command and an
  imprecise partial-upgrade example.
- Unknown-package honesty overclaims repository/AUR non-existence without tools.
- Consumer-GPU advice is truncated and includes unsupported model-family claims.

A bounded report may state the observed completion, reviewed score distribution,
named strengths/failures, speed, and VRAM evidence. It must not turn the 4.00
manual average into a ranking or recommendation, and it must not synthesize a
winner versus the Grug package.

Validation does not prove quality. Manual scores are reviewer metadata. The
derivative is sanitized evidence for review, not an authenticated copy of the
canonical source.

## Provenance status

- `source_run_fingerprint`: available on the private source and recorded in
  `public-export-manifest.json`.
- Public `llmgauge-result.json` / export-index may present a redacted or null
  run-fingerprint field; that is a different role from the manifest source
  fingerprint and must not be treated as proof that the source lacked a
  fingerprint.
- Model-file provenance: available with public fingerprint; full local SHA-256
  redacted in the public derivative.
- Executable/backend provenance: available with discovery status and public
  executable fingerprint fields when present.
- Resolved runtime-command artifact: present (`runtime-command.json`).
- Reasoning mode: `off`.
- GPU name and VRAM samples come from observed telemetry only.
- CPU, RAM, driver, operating-system version, and full host configuration are
  not captured.

Fingerprints do not authenticate model authorship, hardware, answer quality, or
transformed export bytes. Hardware telemetry is not authenticated identity.

## Required human actions before any publication

1. Read `PUBLIC_EVIDENCE_SUMMARY.md` against the public export.
2. Inspect all six cleaned outputs and the three mixed-verdict raw outputs.
3. Confirm no surrounding publication copy adds rankings, broad recommendations,
   Grug-versus-Qwen winners, or unsupported hardware/runtime claims.
4. Publish only the files marked publication-intended in `PACKAGE_MANIFEST.md`.
5. Keep the private source and private inventory files nonpublic.

No network publication, upload, release, version change, comparison synthesis,
model re-run for score improvement, or rescoring of the Grug package occurred.
