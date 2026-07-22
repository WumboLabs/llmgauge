# Public Practical Evidence Summary

Classification: `review_ready_with_caveats`

This package is a sanitized, human-review-required derivative of one completed
LLMGauge run. The private source remains canonical. Validation establishes
structural consistency only; it does not prove answer quality, safety, or
publication readiness. Manual scores are reviewer metadata, not objective truth
or a universal model ranking. This package does not support a winner claim or
cross-model ranking against any other package.

## Test subject and setup

- Model: Qwen3.6 35B-A3B UD-IQ2_M (`qwen3_6_35b_a3b_ud_iq2_m`)
- Family: Qwen3.6 MoE
- Quantization: UD-IQ2_M
- Runtime: llama.cpp
- GPU observed by telemetry: NVIDIA GeForce RTX 5070, 12,227 MiB total VRAM
- Context: 8,192 tokens
- Maximum generation: 1,200 tokens
- Temperature / top-p: 0.2 / 0.95
- Batch / ubatch: 256 / 64
- GPU layers requested: 999
- Flash attention: auto (current CLI default; disclosed deviation from the first
  package, which did not pass an explicit flash-attention flag)
- Reasoning mode: off
- Runtime label: stock-reference
- Resolved runtime-command artifact: captured (`runtime-command.json`)
- Model-file public fingerprint: `sha256:2be7ef1ed7e1af8b`
- Source run fingerprint: recorded on the private source and in the export
  manifest (does not authenticate transformed export bytes). Public
  `llmgauge-result.json` / export-index may show a redacted or null
  run-fingerprint field; those roles differ and must not be collapsed.
- GPU name and VRAM samples: observed telemetry only, not authenticated hardware
  identity
- CPU, RAM, operating-system version, driver version, and full host
  configuration: not captured

Evidence: `public-export/llmgauge-result.json`, `public-export/report.md`,
`public-export/runtime-command.json`, and per-prompt files under
`public-export/vram/`.

## Suite and prompt coverage

The run used suite identity `wumbolabs-practical-use-v1` version `0.1.0` — the
same practical suite family as the first tracked package. The source resolved
that suite through a temporary path (`tmp/wumbolabs-practical-use-v1`), not a
stable tracked suite path. Operator console logs record prompt order and
completion only; they are not a substitute for resolved runtime-command or
result metadata. All six prompts completed with no failed prompts:

1. conservative Arch/NVIDIA update advice;
2. a Python log-parser task;
3. Docker Compose risk review;
4. honesty about an unknown package;
5. technical-run summarization;
6. local-LLM advice for a consumer GPU.

This is bounded six-prompt coverage, not broad reliability, safety, or benchmark
coverage.

Evidence: `public-export/llmgauge-result.json` fields `suite`, `results`, and
`summary`.

## Validation and scoring status

- Canonical private source: structurally valid before export.
- Public derivative: structurally valid through the validated export index.
- Scoring status: scored.
- Score coverage: 6 of 6 prompts.
- Scoring mode: manual for all six applied scores.
- Explicitly reviewed: 6; unreviewed: 0.
- Verdicts: 3 pass, 3 mixed, 0 fail, 0 `needs_review`.
- Missing score rationales: 0.
- Manual score total: 239.8 / 300.0.
- Manual score average: 4.00 / 5.

The values above describe one reviewer's application of `default-manual-v0`
version `0.1.0`. They are review metadata, not an automatic judgment. Automatic
draft scoring was not used as final review.

Evidence: `public-export/scores.yaml`, applied scores in
`public-export/llmgauge-result.json`, scoring sections in
`public-export/report.md`, and `export-index.json`.

## Reviewed strengths

- The summarization answer received the strongest prompt average, 4.48 / 5. It
  preserved completion count, VRAM, generation and prompt speeds, and both
  quality caveats without inventing metrics.
- The Docker Compose review averaged 4.25 / 5. The reviewer credited docker.sock
  risk, floating tags, relative bind mounts, PUID/PGID nuance, healthcheck
  guidance, and a concrete safer sketch with uncertainty notes.
- The coding answer averaged 4.15 / 5. It produced a complete standard-library
  argparse script with missing-file handling, severity counts, and sample lines.

Evidence: prompt-level scores and rationales in `public-export/report.md` and
`public-export/scores.yaml`; readable outputs in `public-export/cleaned/`.

## Material failure modes and caveats

- Arch/NVIDIA advice: mixed, 3.91 / 5, labeled `unsupported_claim`. The answer
  recommended `pacman -Qoq | sort` as a pending-update review (incorrect for
  that purpose) and treated `pacman -Syu nvidia` as a partial-upgrade example.
- Unknown-package honesty: mixed, 3.78 / 5, labeled `unsupported_claim`. The
  answer correctly refused install and gave verification steps, but overclaimed
  that the package has no official or AUR record despite no web/tool access.
- Consumer-GPU local-LLM advice: mixed, 3.41 / 5, labeled `incomplete_answer`
  and `unsupported_claim`. The answer truncates mid-list, recommends a
  non-existent “Llama 3.1 14B”, and presents rough fit/speed claims without
  enough uncertainty bounds.
- Peak observed VRAM was tight (11,706 MiB of 12,227 MiB; about 521 MiB
  headroom). That is a fit observation for this configuration only, not a
  general fit guarantee for other contexts, hosts, drivers, or workloads.
- Flash-attention `auto` and temporary suite-path resolution are methodology
  differences versus a stricter reference capture; they must be disclosed in any
  future comparison.
- Sanitization redacts path-like strings and full local hashes. This protects
  privacy but can reduce specificity; the private raw source remains the audit
  authority.

Evidence: `public-export/report.md` manual rationales, `public-export/cleaned/`,
`public-export/public-export-manifest.json`, and `export-index.json`.

## Runtime and VRAM observations

Across the six prompts:

- generation speed ranged from 146.1 to 152.7 tokens/s;
- prompt evaluation ranged from 883.2 to 1,170.9 tokens/s;
- peak observed VRAM use was 11,706 MiB on every prompt sample set;
- minimum observed VRAM headroom was 521 MiB (12,227 − 11,706);
- GPU name from telemetry: NVIDIA GeForce RTX 5070.

These are observations from this run and captured sampling intervals. They do
not establish performance on another runtime, build, driver, GPU, context
length, or workload.

Evidence: `public-export/llmgauge-result.json`, `public-export/report.md`, and
`public-export/vram/`.

## Claim boundaries

### Supported

- This specific UD-IQ2_M model artifact completed all six configured prompts
  under the recorded llama.cpp settings.
- The run produced the stated speed and VRAM observations on the GPU named by
  telemetry.
- One manual reviewer assigned the stated scores, verdicts, labels, and
  rationales.
- Three prompts were marked pass and three mixed; failure labels are disclosed
  above.
- The private source includes model-file provenance, backend provenance, a run
  fingerprint, and resolved runtime-command capture.

### Qualified

- The run provides useful evidence of practical behavior across six named tasks,
  subject to the reviewer rationales and output inspection.
- The model completed this one 8k-context run with tight observed VRAM headroom.
  This is not a fit guarantee for other contexts or hosts.
- The derivative passed structural validation and the privacy scan described in
  `PUBLICATION_READINESS.md`. Sanitization still requires human review.

### Unsupported

- Universal model quality, safety, truthfulness, or reliability.
- A public benchmark rank, best-model claim, winner declaration, or broad
  purchasing recommendation.
- Daily-driver suitability from six prompts.
- Performance or fit on untested hardware, runtimes, settings, or prompt sets.
- Model authorship, upstream provenance, exact model bytes, or runtime-build
  identity.
- Any Grug-versus-Qwen ranking or generalized comparison synthesis.
- Any claim that a fingerprint authenticates model authorship, hardware, or
  transformed bytes.

## Privacy and source-integrity limits

A privacy scan over every publication-intended file under `public-export/` plus
`export-index.json` found no private home paths, local username, local hostname,
credential patterns, environment dumps, private endpoints, or credential-bearing
URLs. Model filename identity and public short fingerprints remain as
publication-intended provenance. Full local file SHA-256 values are redacted in
the derivative. The source run fingerprint is retained in the export manifest
with an explicit non-authentication boundary for transformed bytes.

The pre-export and post-export private inventories contained the same 34 files,
131,072 bytes, and matching deterministic tree digest. Full per-file hashes
remain in private review-only inventories and are not publication content. The
source directory remains the canonical evidence; this public derivative
transforms content and cannot authenticate its own relationship to source bytes.

Human review remains mandatory before publication. See `SOURCE_INTEGRITY.md`,
`PUBLICATION_READINESS.md`, and `PACKAGE_MANIFEST.md`.
