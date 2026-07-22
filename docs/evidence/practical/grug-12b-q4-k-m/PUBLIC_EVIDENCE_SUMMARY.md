# Public Practical Evidence Summary

Classification: `review_ready_with_caveats`

This package is a sanitized, human-review-required derivative of one completed LLMGauge run. The private source remains canonical. Validation establishes structural consistency only; it does not prove answer quality, safety, or publication readiness. Manual scores are reviewer metadata, not objective truth or a universal model ranking.

## Test subject and setup

- Model: Grug-12B Q4_K_M (`grug_12b_q4_k_m`)
- Family: Gemma 4
- Quantization: Q4_K_M
- Runtime: llama.cpp
- GPU observed by telemetry: NVIDIA GeForce RTX 5070, 12,227 MiB total VRAM
- Context: 8,192 tokens
- Maximum generation: 1,200 tokens
- Temperature / top-p: 0.2 / 0.95
- Batch / ubatch: 256 / 64
- GPU layers requested: 999
- Reasoning mode: not recorded in this legacy result
- Resolved runtime-command artifact: not captured
- CPU, RAM, operating-system version, driver version, and full host configuration: not captured

Evidence: `public-export/llmgauge-result.json`, `public-export/report.md`, and per-prompt files under `public-export/vram/`.

## Suite and prompt coverage

The run used `wumbolabs-practical-use-v1` version `0.1.0`. All six prompts completed with no failed prompts:

1. conservative Arch/NVIDIA update advice;
2. a Python log-parser task;
3. Docker Compose risk review;
4. honesty about an unknown package;
5. technical-run summarization;
6. local-LLM advice for a consumer GPU.

This is bounded six-prompt coverage, not broad reliability, safety, or benchmark coverage.

Evidence: `public-export/llmgauge-result.json` fields `suite`, `results`, and `summary`.

## Validation and scoring status

- Canonical private source: structurally valid before export.
- Public derivative: structurally valid through the validated export index.
- Scoring status: scored.
- Score coverage: 6 of 6 prompts.
- Scoring mode: manual for all six applied scores.
- Explicitly reviewed: 6; unreviewed: 0.
- Verdicts: 4 pass, 2 mixed, 0 fail, 0 `needs_review`.
- Missing score rationales: 0.
- Manual score total: 243.6 / 300.0.
- Manual score average: 4.06 / 5.

The values above describe one reviewer's application of `default-manual-v0` version `0.1.0`. They are review metadata, not an automatic judgment.

Evidence: `public-export/scores.yaml`, applied scores in `public-export/llmgauge-result.json`, scoring sections in `public-export/report.md`, and `export-index.json`.

## Reviewed strengths

- The unknown-package answer received the strongest prompt average, 4.50 / 5. The reviewer found that it acknowledged uncertainty, avoided inventing package facts or an install command, and proposed verification steps.
- The Docker Compose review averaged 4.31 / 5. The reviewer credited its treatment of socket exposure, floating image tags, user identity, container naming, restart policy, bind mounts, and PUID/PGID limitations.
- The summarization answer averaged 4.25 / 5 and preserved the supplied completion, speed, VRAM, and quality caveats concisely.
- The coding answer averaged 3.96 / 5. It used the standard library, handled a missing file, and produced severity counts and samples, though its matching and CLI were basic.

Evidence: prompt-level scores and rationales in `public-export/report.md` and `public-export/scores.yaml`; readable outputs in `public-export/cleaned/`.

## Material failure modes and caveats

- Arch/NVIDIA advice: mixed, 3.72 / 5, labeled `unsupported_claim`. The answer linked to a noncanonical Arch News URL and gave generic NVIDIA/Wayland guidance that requires independent verification.
- Consumer-GPU local-LLM advice: mixed, 3.62 / 5, labeled `unsupported_claim`. The answer used generic or stale model examples and simplified fit guidance; its size and fit statements are not hardware guarantees.
- The coding answer uses substring matching and a broad exception handler. It is a useful sketch, not production-ready parsing code.
- Sanitization redacts path-like strings in model outputs. This protects privacy but can reduce the specificity of examples; the private raw source remains the audit authority.
- The result predates resolved runtime-command capture and run/model fingerprint metadata. Runtime identity and model-file identity therefore cannot be independently established from this package.

Evidence: `public-export/report.md` manual rationales, `public-export/cleaned/`, `public-export/public-export-manifest.json`, and `export-index.json`.

## Runtime and VRAM observations

Across the six prompts:

- generation speed ranged from 66.1 to 67.9 tokens/s;
- prompt evaluation ranged from 1,532.9 to 1,744.6 tokens/s;
- peak observed VRAM use ranged from 8,460 to 8,485 MiB;
- minimum observed VRAM headroom was 3,742 MiB;
- every recorded VRAM guardrail status was `ok` at the configured 1,000 MiB warning threshold.

These are observations from this run and captured sampling intervals. They do not establish performance on another runtime, build, driver, GPU, context length, or workload.

Evidence: `public-export/llmgauge-result.json`, `public-export/report.md`, and `public-export/vram/`.

## Claim boundaries

### Supported

- This specific Q4_K_M model artifact completed all six configured prompts under the recorded llama.cpp settings.
- The run produced the stated speed and VRAM observations on the GPU named by telemetry.
- One manual reviewer assigned the stated scores, verdicts, labels, and rationales.
- Four prompts were marked pass and two mixed; the two mixed prompts carried `unsupported_claim` labels.

### Qualified

- The run provides useful evidence of practical behavior across six named tasks, subject to the reviewer rationales and output inspection.
- The model fit this one 8k-context run with observed VRAM headroom. This is not a fit guarantee for other contexts or hosts.
- The derivative passed structural validation and the privacy scan described in `PUBLICATION_READINESS.md`. Sanitization still requires human review.

### Unsupported

- Universal model quality, safety, truthfulness, or reliability.
- A public benchmark rank, best-model claim, winner declaration, or broad purchasing recommendation.
- Daily-driver suitability from six prompts.
- Performance or fit on untested hardware, runtimes, settings, or prompt sets.
- Model authorship, upstream provenance, exact model bytes, or runtime-build identity.
- Any claim that a fingerprint authenticates model authorship, hardware, or transformed bytes. This source has no recorded run/model fingerprint; even when present, fingerprints do not provide those guarantees.

## Privacy and source-integrity limits

The existing public exporter initially preserved a local hostname embedded in review text. A focused exporter correction redacted local hostnames and usernames; the derivative was regenerated and rescanned. The final scan found no private home paths, local username, local hostname, credential patterns, full 64-character hashes, environment dumps, private endpoints, or credential-bearing URLs in the 35 publication-intended export/index files. The only URL found was the model answer's noncanonical Arch News link, retained as evidence of a reviewed failure mode.

The pre-export and post-export private inventories contained the same 35 files, 100,485 bytes, and matching deterministic tree digest. Full per-file hashes remain in private review-only inventories and are not publication content. The source directory remains the canonical evidence; this public derivative transforms content and cannot authenticate its own relationship to source bytes.

Human review remains mandatory before publication. See `SOURCE_INTEGRITY.md`, `PUBLICATION_READINESS.md`, and `PACKAGE_MANIFEST.md`.
