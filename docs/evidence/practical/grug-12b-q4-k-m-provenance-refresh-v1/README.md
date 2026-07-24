# Grug-12B Q4_K_M provenance-refresh practical evidence

Classification: `review_ready_with_caveats`

This is a **separate provenance-refresh run**: one bounded, sanitized,
human-reviewed six-prompt package. It does not modify, replace, or supersede the
[legacy Grug package](../grug-12b-q4-k-m/). It is not a benchmark rank, winner,
safety certification, purchasing guide, fit guarantee, or daily-driver
recommendation.

## Setup (this run only)

| Field | Value |
|---|---|
| Model | Grug-12B Q4_K_M (`grug_12b_q4_k_m`) |
| Family / quant | Gemma 4 / Q4_K_M |
| Runtime | llama.cpp |
| Observed runtime self-report | version 9672, commit `74ade5274`, GNU 16.1.1 for Linux x86_64 |
| Context / max tokens | 8,192 / 1,200 |
| Temperature / top-p | 0.2 / 0.95 |
| Batch / ubatch / GPU layers | 256 / 64 / 999 |
| Flash attention | auto (explicit) |
| Reasoning mode | off (explicit) |
| Runtime label | stock-reference |
| Observed GPU telemetry | NVIDIA GeForce RTX 5070, 12,227 MiB total VRAM |
| Hardware capture depth | Private privacy-safe OS/kernel/CPU/RAM/GPU/driver capture plus public GPU/VRAM telemetry; private sidecars omitted from export |
| Suite | tracked `wumbolabs-practical-use-v1` 0.1.0 |
| Run ID | `grug_12b_q4_k_m-provenance-refresh-v1-wumbolabs-practical-use-v1-8k` |
| Run start / end (UTC) | 2026-07-24T21:16:42Z / 2026-07-24T21:17:39Z |
| Operator result | exit 0, not interrupted, zero retries |
| Observed minimum VRAM headroom | 3,669 MiB (this configuration only) |

## Manual score summary

Manual scores are **reviewer metadata**, not objective truth.

| Metric | Value |
|---|---|
| Scoring status | scored (6/6, manual, all reviewed) |
| Manual average | 3.71 / 5 |
| Manual total | 222.4 / 300.0 |
| Verdicts | **2 pass**, **3 mixed**, **1 fail** |
| Failure labels | `unsupported_claim` × 4, `missing_verification` × 2, `ignores_constraints` × 2 |
| Rubric | `default-manual-v0` 0.1.0 |

### Material reviewed caveats

1. **linux/arch-nvidia-update-advice** — mixed, 3.67 / 5. A
   noncanonical Arch News URL is called official; module/Wayland verification
   is vague; Timeshift is assumed without support.
2. **docker/compose-review** — mixed, 3.22 / 5. It invents a version tag and
   endpoint/tool, incorrectly claims a healthcheck restarts an unhealthy
   container, and proposes unverified configuration changes.
3. **honesty/unknown-package** — mixed, 3.88 / 5. It handles uncertainty well,
   but GameFilter is an inappropriate Linux fallback and NVML is not an
   optimizer.
4. **local-llm/consumer-gpu-advice** — fail, 2.79 / 5. It violates explicit
   constraints with unsupported fit, VRAM, speed, and quality claims.

The coding prompt passed at 4.15 / 5; the summarization prompt passed at 4.53 / 5.
See the applied rationales rather than treating averages as rankings.

## Provenance and capture

Three artifact roles must remain distinct:

1. **Original live-run state:** an ignored 36-file pre-scoring inventory
   survives, but no complete pre-scoring copy or backup does. Scoring changed
   `llmgauge-result.json` and `report.md` and added `scores.yaml`, so original
   live-run byte immutability is not established.
2. **Scored canonical private working source:** the current 37-file result
   records model and executable/backend provenance, the run fingerprint, stable
   suite identity/path, resolved `runtime-command.json`, and applied scores. It
   was verified unchanged during export and package assembly.
3. **Sanitized public derivative:** `public-export/` was generated from the
   scored source. It redacts full local hashes and paths and retains the source
   run fingerprint only with a boundary that it does not authenticate
   transformed bytes, authorship, hardware, or answer quality.

The built-in runtime record preserves reported version `9672 (74ade5274)`; the
private observed self-report separately records commit, compiler, and platform.
The public package discloses those safe observed build facts without publishing
private paths or operator sidecars.

## Relationship to the legacy Grug package

The legacy package remains unchanged and authoritative for its earlier source.
Its separate outputs were scored 4 pass / 2 mixed with a 4.06 reviewer average.
This refreshed output was scored only after independent review and produced more
material unsupported claims in Docker, unknown-package, and consumer-GPU
answers; Arch remained mixed, while coding and summarization remained passes.
Those differences describe two generated response sets and two bounded manual
reviews. They do not establish a model regression, winner, rank, or general
quality trend. The legacy scores were not copied or changed.

## Capture and sanitization caveats

- The private wrapper captured privacy-safe OS/kernel/CPU/RAM/GPU/driver facts,
  start/end timestamps, exit status, and operator console output. Those unknown
  sidecars were intentionally omitted by the public exporter.
- Public GPU name and VRAM samples are observed telemetry, not authenticated
  hardware identity.
- Sanitization transformed path-like prompt and output text, including Docker
  paths and llama-cli interactive command banners. Redaction tokens are visible
  evidence of those transformations and can reduce example specificity.
- The source run is one successful attempt with zero retries. Six completed
  prompts do not establish broad reliability, safety, quality, recommendation,
  or hardware fit.

## Supporting package

- [Public evidence summary](PUBLIC_EVIDENCE_SUMMARY.md)
- [Publication readiness](PUBLICATION_READINESS.md)
- [Source integrity](SOURCE_INTEGRITY.md)
- [Package manifest](PACKAGE_MANIFEST.md)
- [Export index](export-index.json)
- Sanitized run tree: [public-export/](public-export/)
  - [report.md](public-export/report.md)
  - [scores.yaml](public-export/scores.yaml)
  - [llmgauge-result.json](public-export/llmgauge-result.json)
  - [runtime-command.json](public-export/runtime-command.json)
  - [public-export-manifest.json](public-export/public-export-manifest.json)
  - [raw/](public-export/raw/), [cleaned/](public-export/cleaned/),
    [logs/](public-export/logs/), [vram/](public-export/vram/)

[Evidence index](../../README.md) · [Public reporting guidance](../../../PUBLIC_REPORTING.md)
