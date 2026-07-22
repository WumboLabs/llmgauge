# Publication Readiness

Classification: `review_ready_with_caveats`

Decision: suitable for human publication review as one bounded practical evidence package. It is not approved for automatic or unreviewed publication.

## Selection decision

The ignored `results/` inventory contained 80 single-run result JSON artifacts. Eighteen completed runs had both `scores.yaml` and applied scores. Five candidates could prove complete score coverage, `reviewed: true` on every applied score, manual scoring mode, no `needs_review`, no blank verdict, no missing rationale, and the expected raw/cleaned/report artifacts.

Selected source:

`results/grug_12b_q4_k_m-v025-wumbolabs-practical-8k`

Why it was preferable:

- six completed practical prompts across Linux, coding, Docker, honesty, summarization, and local-LLM topics;
- complete manual review metadata and rationale coverage;
- no failed prompt or unresolved review state;
- one llama.cpp runtime, avoiding mixed-runtime comparison claims;
- raw, cleaned, log, score, report, and VRAM evidence present;
- broader practical coverage than the other four qualifying candidates, which were one-prompt cross-runtime experiments.

Serious alternatives were rejected or deprioritized as follows:

- older multi-prompt practical runs lacked explicit `reviewed: true` metadata on every applied score, so full review status could not be proved under the current contract;
- the four fully qualifying Qwen2.5 3B artifacts covered one prompt each and were created for cross-runtime evidence, making them less representative and more vulnerable to mixed-runtime overstatement;
- Fit Ladder parents, failed attempts, unscored children, intentionally unscored vLLM smokes, failed runs, and artifacts missing required review/canonical evidence were excluded.

Private selection details remain in ignored local review records (not publication content).

## Readiness checks

| Check | Result |
|---|---|
| Canonical source completed | PASS: 6 completed, 0 failed |
| Canonical source structural validation | PASS |
| `scores.yaml` matches applied result scores | PASS: prompt IDs, dimensions, labels, notes, rationales, and verdicts match |
| `llmgauge-result.json` review state | PASS: 6 manual, 6 reviewed, 0 unreviewed |
| `report.md` scoring state | PASS: 6 scored; 4 pass, 2 mixed; all rationales present |
| `needs_review` | PASS: 0 |
| Missing score rationales | PASS: 0 |
| Unreviewed score drafts | PASS: 0; no `auto-scores.yaml` in selected source |
| Transactional public export | PASS: generated successfully in a new output directory |
| Export structural validation | PASS through validated export index |
| Export index validation | PASS: one indexed run, validation status `valid` |
| Source immutability | PASS: pre/post inventories identical |
| Derived-file parsing | PASS: all JSON/YAML parsed |
| Privacy scan | PASS after focused exporter correction |
| Human claim review | PASS for this package; caveats retained below |

## Privacy review

The first generated derivative revealed a concrete exporter defect: a local hostname embedded in score rationales, the result JSON, report, and scores file was not redacted. The superseded derivative was removed. Production sanitization was narrowly corrected to redact bounded local hostname and username tokens in text and structured strings, with focused regression coverage. A fresh derivative and validated index were then generated.

The final scan covered every file under `public-export/` plus `export-index.json` (35 files total). It found zero instances of:

- private home-directory paths;
- the local username;
- the local hostname;
- credential assignments or credential-bearing URLs;
- full 64-character hexadecimal hashes;
- environment-variable dumps;
- loopback, RFC 1918, or other private endpoints.

One external URL remains: a noncanonical Arch News URL in model output. It is intentionally retained because the manual reviewer identified it as an `unsupported_claim` failure mode. Do not present that URL as authoritative.

The exporter manifest records `absolute_path`, `home_directory_path`, `local_hostname`, `local_username`, and `prompt_duplication` redactions. Two score backup files were omitted as unknown artifacts.

## Scoring and claim review

No unresolved review-state blocker remains. The two mixed verdicts are material publication caveats, not hidden failures:

- Arch/NVIDIA update advice contains a noncanonical news link and generic configuration claims.
- Consumer-GPU local-LLM advice contains generic/stale examples and simplified fit guidance.

A bounded report may state the observed completion, reviewed score distribution, named strengths/failures, speed, and VRAM evidence. It must not turn the 4.06 manual average into a ranking or recommendation.

Validation does not prove quality. Manual scores are reviewer metadata. The derivative is sanitized evidence for review, not an authenticated copy of the canonical source.

## Provenance limits

- `source_run_fingerprint`: unavailable (`null`).
- Exported run fingerprint: unavailable.
- Model-file provenance fingerprint: unavailable.
- Resolved runtime-command artifact: absent.
- GPU identity comes from VRAM telemetry only.
- CPU, RAM, driver, operating-system version, and full host configuration are not captured.

Fingerprints, when present, do not authenticate model authorship, hardware, or transformed export bytes. Their absence here narrows provenance further and must remain disclosed.

## Required human actions before any publication

1. Read `PUBLIC_EVIDENCE_SUMMARY.md` against the public export.
2. Inspect all six cleaned outputs and the two mixed-verdict raw outputs.
3. Confirm that the retained external URL is described only as a failure mode.
4. Confirm no surrounding publication copy adds rankings, broad recommendations, or unsupported hardware/runtime claims.
5. Publish only the files marked publication-intended in `PACKAGE_MANIFEST.md`.
6. Keep the private source and private inventory files nonpublic.

No network publication, upload, release, version change, comparison, model execution, or rescoring occurred.
