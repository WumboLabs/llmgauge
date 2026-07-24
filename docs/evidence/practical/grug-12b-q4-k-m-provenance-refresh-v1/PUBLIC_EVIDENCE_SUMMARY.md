# Public Practical Evidence Summary

Classification: `review_ready_with_caveats`

This package is a sanitized, human-review-required derivative of one completed
provenance-refresh LLMGauge run's scored private working source.
Structural validation does not prove answer quality, safety, privacy
completeness, or publication readiness. Manual scores are reviewer metadata,
not objective truth or a universal ranking.

## Test subject and setup

- Model: Grug-12B Q4_K_M (`grug_12b_q4_k_m`), Gemma 4 family.
- Runtime: llama.cpp; observed self-report version 9672, build commit
  `74ade5274`, compiler GNU 16.1.1, platform Linux x86_64.
- Model public fingerprint: `sha256:3928e9af604369c1`.
- Executable public fingerprint: `sha256:21b13a815dd2315d`.
- Context / maximum generation: 8,192 / 1,200 tokens.
- Temperature / top-p: 0.2 / 0.95.
- Batch / ubatch / GPU layers: 256 / 64 / 999.
- Flash attention: `auto` (explicit).
- Reasoning mode: `off` (explicit).
- Runtime label: `stock-reference`.
- Suite: stable tracked `wumbolabs-practical-use-v1` version `0.1.0`.
- Resolved runtime command: captured in `runtime-command.json`.
- Operator capture: start 2026-07-24T21:16:42Z, end
  2026-07-24T21:17:39Z, exit 0, not interrupted, zero retries.
- Hardware capture depth: private privacy-safe OS/kernel/CPU/RAM/GPU/driver
  sidecar plus public GPU/VRAM telemetry. Private sidecars are omitted.
- GPU observed by telemetry: NVIDIA GeForce RTX 5070, 12,227 MiB total VRAM.

## Suite and execution coverage

All six prompts completed once, in accepted historical order, with no failed or
hidden retry attempts:

1. `linux/arch-nvidia-update-advice`;
2. `coding/python-log-parser`;
3. `docker/compose-review`;
4. `honesty/unknown-package`;
5. `summarization/technical-run-summary`;
6. `local-llm/consumer-gpu-advice`.

Raw and cleaned outputs, empty per-prompt stderr logs, and VRAM sample files are
present for all six prompts. This is bounded coverage, not proof of broad
reliability or safety.

## Validation and scoring status

- Canonical private result: structurally valid before scoring and after applying
  scores.
- Public derivative: structurally valid; validated export index contains one
  valid result.
- Scores: 6 of 6, `manual`, explicitly reviewed; 0 unreviewed and 0
  `needs_review`.
- Manual total / average: 222.4 / 300.0; 3.71 / 5.
- Verdicts: 2 pass, 3 mixed, 1 fail.
- Failure labels: `unsupported_claim` × 4, `missing_verification` × 2,
  `ignores_constraints` × 2.
- Rubric: `default-manual-v0` version `0.1.0`.

| Prompt | Average | Verdict | Failure labels |
|---|---:|---|---|
| Arch/NVIDIA update advice | 3.67 | mixed | `unsupported_claim`, `missing_verification` |
| Python log parser | 4.15 | pass | none |
| Docker Compose review | 3.22 | mixed | `unsupported_claim`, `missing_verification`, `ignores_constraints` |
| Unknown-package honesty | 3.88 | mixed | `unsupported_claim` |
| Technical-run summary | 4.53 | pass | none |
| Consumer-GPU advice | 2.79 | fail | `unsupported_claim`, `ignores_constraints` |

## Reviewed strengths

- The summarization answer is concise and faithfully separates measured fit from
  reviewed quality; it omits the supplied 4,054 MiB headroom detail.
- The coding answer supplies a readable standard-library implementation and
  practical invocation. Substring matching, broad exception handling, and
  malformed-input exit behavior remain limitations.
- The Arch answer uses a cautious sequence and rollback awareness.
- The unknown-package answer leads with inability to verify and PKGBUILD review.

## Material weaknesses

- Arch advice calls a noncanonical Arch News URL official, assumes Timeshift,
  and lacks precise module/Wayland verification.
- Docker advice invents tag `1.2.3` and an endpoint/tool, incorrectly claims a
  healthcheck restarts an unhealthy container, and proposes unverified user and
  network changes.
- Unknown-package advice suggests GameFilter as a Linux fallback and describes
  NVML as if it were an optimizer.
- Consumer-GPU advice makes the fit, VRAM, speed, and quality claims that the
  prompt explicitly prohibited, including a conclusion that examples are
  verified to fit with ample headroom.

These weaknesses remain visible in outputs, score rationales, verdicts, and
failure labels. They were not repaired or suppressed.

## Runtime and VRAM observations

Across the six prompts:

- generation speed ranged from 66.8 to 69.7 tokens/s;
- prompt evaluation ranged from 1,572.3 to 1,738.4 tokens/s;
- peak sampled VRAM ranged from 8,539 to 8,558 MiB;
- minimum sampled VRAM headroom was 3,669 MiB.

These observations apply only to the recorded runtime, hardware, settings,
sampling intervals, and prompts. They are not performance or fit guarantees.

## Provenance and source integrity

The exact 36-file pre-scoring live-run tree is represented by a private hash
inventory, but no complete pre-scoring copy or backup was preserved. In-place
scoring changed `llmgauge-result.json` and `report.md` and added `scores.yaml`.
Original live-run byte immutability is therefore not established.

The accepted scoring workflow treats the resulting 37-file scored directory as
the canonical private working source for applied-score review and export. It
includes full local model and executable hashes, backend provenance, observed
runtime identity, run fingerprint, stable suite identity/path, resolved command
metadata, and applied scores. A deterministic inventory matched this scored tree
exactly before and after export; paths, sizes, hashes, and total bytes were
unchanged.

The sanitized public derivative retains short model/executable fingerprints and
the source run fingerprint in the export manifest while redacting full local
file hashes and paths. Fingerprints do not prove authorship, hardware identity,
quality, original-byte preservation, or transformed-byte integrity. Full
inventories remain ignored and private.

## Sanitization and privacy review

The scan covered the complete public export and validated export index. It found
no local username, hostname, home/model/executable paths, full model or
executable hashes, credentials, credential-bearing URLs, unrelated environment
data, or private operator sidecars. The only full-length hash intentionally
remaining is the source run fingerprint in the manifest and generated report,
with its non-authentication boundary.

The exporter records path, username, full-local-hash, and prompt-duplication
redactions. `REDACTED_ABSOLUTE_PATH`, `REDACTED_HOME_PATH`, and
`REDACTED_MODEL_PATH` occur in reviewed contexts. Path redaction affects Docker
examples and llama-cli banner commands, so the private raw source remains the
audit authority.

## Legacy relationship and claim boundaries

This run is separate from and does not supersede the legacy Grug package. After
this run was scored independently, the legacy package was consulted only for
bounded behavioral differences. The refreshed Docker, unknown-package, and
consumer-GPU answers contain more material unsupported claims under this review;
Arch remains mixed, while coding and summarization remain passes. The legacy
scores and artifacts were not modified or reinterpreted.

Supported claims are limited to this artifact completing these six prompts under
the recorded settings, the observed telemetry, preserved provenance, and one
reviewer's stated metadata. Unsupported claims include universal quality,
safety, reliability, rank, winner status, purchasing or daily-driver advice,
model-family advantage, generalized fit, and any claim that the lower refreshed
review average proves regression.

Human review remains mandatory before any external publication. See
`PUBLICATION_READINESS.md`, `SOURCE_INTEGRITY.md`, and `PACKAGE_MANIFEST.md`.
