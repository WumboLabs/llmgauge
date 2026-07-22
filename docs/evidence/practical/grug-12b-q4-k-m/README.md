# Grug-12B Q4_K_M practical evidence

Classification: `review_ready_with_caveats`

This is **one bounded six-prompt practical run**, published as a sanitized
human-reviewed evidence package. It is not a benchmark rank, model scorecard,
safety certification, purchasing guide, or daily-driver recommendation.

## Setup (this run only)

| Field | Value |
|---|---|
| Model | Grug-12B Q4_K_M (`grug_12b_q4_k_m`) |
| Family / quant | Gemma 4 / Q4_K_M |
| Runtime | llama.cpp |
| Context / max tokens | 8,192 / 1,200 |
| Temperature / top-p | 0.2 / 0.95 |
| Batch / ubatch / GPU layers | 256 / 64 / 999 |
| Observed GPU (telemetry) | NVIDIA GeForce RTX 5070, 12,227 MiB total VRAM |
| Suite | `wumbolabs-practical-use-v1` 0.1.0 |
| Run ID | `grug_12b_q4_k_m-v025-wumbolabs-practical-8k` |
| Run timestamp (UTC) | 2026-07-04T00:44:11+00:00 |

## Manual score summary

Manual scores are **reviewer metadata**, not universal truth.

| Metric | Value |
|---|---|
| Scoring status | scored (6/6, manual, all reviewed) |
| Manual average | 4.06 / 5 |
| Manual total | 243.6 / 300.0 |
| Verdicts | **4 pass**, **2 mixed** |
| Failure labels | `unsupported_claim` × 2 |
| Rubric | `default-manual-v0` 0.1.0 |

### Mixed verdicts (material caveats)

1. **linux/arch-nvidia-update-advice** — mixed, 3.72 / 5, `unsupported_claim`.
   Noncanonical Arch News URL and generic NVIDIA/Wayland guidance.
2. **local-llm/consumer-gpu-advice** — mixed, 3.62 / 5, `unsupported_claim`.
   Generic or stale model examples and simplified fit guidance; not a hardware
   guarantee.

### Pass prompts (summary only)

- honesty/unknown-package — 4.50 / 5
- docker/compose-review — 4.31 / 5
- summarization/technical-run-summary — 4.25 / 5
- coding/python-log-parser — 3.96 / 5

## Claim boundaries

**Structural validation does not prove quality, safety, or publication
readiness.** Sanitization requires human review and is not a guarantee that
every private value has been removed.

This package supports only claims about **this** model artifact, suite, runtime
settings, observed telemetry, and one reviewer's applied scores. It does **not**
support:

- universal quality, safety, truthfulness, or reliability claims;
- leaderboard rank, “best model,” winner, purchasing, or daily-driver advice;
- performance or fit on untested hardware, runtimes, contexts, or prompts;
- model authorship, exact model bytes, or runtime-build identity.

## Provenance limitations (legacy run)

- No source run fingerprint or model-file provenance fingerprint (`null`).
- No resolved runtime-command capture artifact.
- GPU identity comes from VRAM telemetry only.
- CPU, RAM, driver, OS version, and full host configuration were not captured.
- Fingerprints, when present elsewhere, do not authenticate authorship,
  hardware, or transformed public-export bytes.

## Supporting package

Start with the fuller human summary, then inspect artifacts:

- [Public evidence summary](PUBLIC_EVIDENCE_SUMMARY.md)
- [Publication readiness](PUBLICATION_READINESS.md)
- [Source integrity](SOURCE_INTEGRITY.md)
- [Package manifest](PACKAGE_MANIFEST.md)
- [Export index](export-index.json)
- Sanitized run tree: [public-export/](public-export/)
  - [report.md](public-export/report.md)
  - [scores.yaml](public-export/scores.yaml)
  - [llmgauge-result.json](public-export/llmgauge-result.json)
  - [public-export-manifest.json](public-export/public-export-manifest.json)
  - [raw/](public-export/raw/), [cleaned/](public-export/cleaned/),
    [logs/](public-export/logs/), [vram/](public-export/vram/)

[Evidence index](../../README.md) · [Public reporting guidance](../../../PUBLIC_REPORTING.md)
