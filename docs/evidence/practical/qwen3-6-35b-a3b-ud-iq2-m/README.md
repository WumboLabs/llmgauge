# Qwen3.6-35B-A3B UD-IQ2_M practical evidence

Classification: `review_ready_with_caveats`

This is **one bounded six-prompt practical run**, published as a sanitized
human-reviewed evidence package. It is not a benchmark rank, model scorecard,
safety certification, purchasing guide, or daily-driver recommendation.

## Setup (this run only)

| Field | Value |
|---|---|
| Model | Qwen3.6 35B-A3B UD-IQ2_M (`qwen3_6_35b_a3b_ud_iq2_m`) |
| Family / quant | Qwen3.6 MoE / UD-IQ2_M |
| Runtime | llama.cpp |
| Context / max tokens | 8,192 / 1,200 |
| Temperature / top-p | 0.2 / 0.95 |
| Batch / ubatch / GPU layers | 256 / 64 / 999 |
| Flash attention | auto (current CLI default) |
| Reasoning mode | off |
| Runtime label | stock-reference |
| Observed GPU (telemetry) | NVIDIA GeForce RTX 5070, 12,227 MiB total VRAM |
| Suite | `wumbolabs-practical-use-v1` 0.1.0 (resolved via temporary path `tmp/wumbolabs-practical-use-v1`) |
| Run ID | `qwen3_6_35b_a3b_ud_iq2_m-v071-wumbolabs-practical-8k` |
| Run timestamp (UTC) | 2026-07-22T14:52:15+00:00 |
| Observed min VRAM headroom | ~521 MiB (this configuration only; not a general fit guarantee) |

## Manual score summary

Manual scores are **reviewer metadata**, not universal truth.

| Metric | Value |
|---|---|
| Scoring status | scored (6/6, manual, all reviewed) |
| Manual average | 4.00 / 5 |
| Manual total | 239.8 / 300.0 |
| Verdicts | **3 pass**, **3 mixed** |
| Failure labels | `unsupported_claim` × 3, `incomplete_answer` × 1 |
| Rubric | `default-manual-v0` 0.1.0 |

### Mixed verdicts (material caveats)

1. **linux/arch-nvidia-update-advice** — mixed, 3.91 / 5, `unsupported_claim`.
   Incorrect pending-update command (`pacman -Qoq`) and imprecise partial-upgrade
   example (`pacman -Syu nvidia`).
2. **honesty/unknown-package** — mixed, 3.78 / 5, `unsupported_claim`.
   Overclaims that the package has no official/AUR record despite no web or tool
   access; should have limited itself to cannot-verify.
3. **local-llm/consumer-gpu-advice** — mixed, 3.41 / 5,
   `incomplete_answer` + `unsupported_claim`. Truncated mid-list; recommends
   non-existent “Llama 3.1 14B”; generic/stale model fit claims.

### Pass prompts (summary only)

- summarization/technical-run-summary — 4.48 / 5
- docker/compose-review — 4.25 / 5
- coding/python-log-parser — 4.15 / 5

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
- model authorship, exact model bytes, or runtime-build identity;
- any comparison ranking versus the first Grug package or any other model.

## Provenance (this source)

Unlike the first practical package, this source records:

- model-file provenance with public fingerprint `sha256:2be7ef1ed7e1af8b`
  (full local SHA-256 redacted in the public derivative);
- executable/backend provenance for `llama-cli` (public executable fingerprint
  when present; full local hash redacted in the public derivative);
- source run fingerprint (preserved in the export manifest with an explicit
  boundary that it does not authenticate transformed export bytes);
- resolved `runtime-command.json` with settings and command argv (model path
  redacted);
- reasoning-mode metadata (`off`).

Fingerprint **roles** differ and must not be collapsed: the private source run
fingerprint identifies the canonical result; the export manifest carries that
source identifier with a non-authentication boundary for transformed bytes; the
public `llmgauge-result.json` / export-index path may show a redacted or null
run-fingerprint field. Fingerprints do not prove authorship, hardware identity,
answer quality, or the byte integrity of transformed public-export files.

## Capture caveats (this package)

These limits are package honesty, not hidden defects that invalidate structural
validation:

- Flash attention is `auto` (CLI default), unlike the older Grug argv which had
  no explicit flash-attention flag.
- Suite identity is `wumbolabs-practical-use-v1` 0.1.0, but the source resolved
  the suite through a temporary path rather than a stable tracked suite path.
- Operator console logs record prompt order and completion only; they are not a
  complete resolved execution plan. Authoritative settings are in result
  artifacts and `runtime-command.json`.
- GPU name and VRAM samples are **observed telemetry**, not authenticated
  hardware identity. CPU, RAM, OS version, and driver metadata were not captured.
- ~521 MiB minimum observed VRAM headroom is configuration-specific only.

Future reference-quality practical runs should follow the capture standard in
[docs/ROADMAP.md](../../../ROADMAP.md). Any comparison against other packages
must disclose methodology differences first.

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
  - [runtime-command.json](public-export/runtime-command.json)
  - [public-export-manifest.json](public-export/public-export-manifest.json)
  - [raw/](public-export/raw/), [cleaned/](public-export/cleaned/),
    [logs/](public-export/logs/), [vram/](public-export/vram/)

[Evidence index](../../README.md) · [Public reporting guidance](../../../PUBLIC_REPORTING.md)
