# Grug-12B versus Qwen3.6 practical evidence comparison v1

This document compares two tracked, human-reviewed practical evidence packages
under their disclosed conditions. It is a bounded evidence summary, not a
leaderboard, winner declaration, model-family judgment, purchasing guide,
daily-driver recommendation, safety finding, or guarantee of fit.

## Scope

The comparison covers the six prompts shared by one Grug-12B Q4_K_M llama.cpp
run and one Qwen3.6-35B-A3B UD-IQ2_M llama.cpp run from
`wumbolabs-practical-use-v1` 0.1.0. All twelve applied prompt scores were manual,
`human-reviewer`, reviewed scores. Scores and verdicts are reviewer metadata,
not objective truth. Raw prompt files were verified byte-identical across the
packages.

Structural validation, export-index validation, and artifact cross-checks
establish that the tracked records are internally usable. They do not establish
answer quality, safety, publication readiness, authorship, hardware identity,
or transformed-export byte authenticity.

## Source packages

- [Grug-12B Q4_K_M package](../../practical/grug-12b-q4-k-m/)
  - [package review](../../practical/grug-12b-q4-k-m/README.md)
  - [public result](../../practical/grug-12b-q4-k-m/public-export/llmgauge-result.json)
  - [reviewed scores](../../practical/grug-12b-q4-k-m/public-export/scores.yaml)
  - [single-run report](../../practical/grug-12b-q4-k-m/public-export/report.md)
  - [export index](../../practical/grug-12b-q4-k-m/export-index.json)
- [Qwen3.6-35B-A3B UD-IQ2_M package](../../practical/qwen3-6-35b-a3b-ud-iq2-m/)
  - [package review](../../practical/qwen3-6-35b-a3b-ud-iq2-m/README.md)
  - [public result](../../practical/qwen3-6-35b-a3b-ud-iq2-m/public-export/llmgauge-result.json)
  - [reviewed scores](../../practical/qwen3-6-35b-a3b-ud-iq2-m/public-export/scores.yaml)
  - [single-run report](../../practical/qwen3-6-35b-a3b-ud-iq2-m/public-export/report.md)
  - [resolved runtime command](../../practical/qwen3-6-35b-a3b-ud-iq2-m/public-export/runtime-command.json)
  - [export index](../../practical/qwen3-6-35b-a3b-ud-iq2-m/export-index.json)

## Methodology differences

These differences precede and constrain every observation below.

| Dimension | Grug package | Qwen package | Effect on comparison |
|---|---|---|---|
| Architecture | Dense Gemma-family Grug-12B | Qwen3.6 35B-A3B mixture-of-experts | Results do not isolate architecture or model-family effects. |
| Quantization | Q4_K_M | UD-IQ2_M | Quality, throughput, and memory differences cannot be attributed to model identity alone. |
| Provenance | Legacy source: no model-file or source-run fingerprint; no resolved runtime-command artifact | Current source: model/backend/run provenance and resolved `runtime-command.json` | Qwen settings and artifact identity are more reproducible; provenance depth is not a quality advantage. |
| Runtime command | Original argv is retained in result metadata, but no resolved command artifact | Resolved command artifact and redacted argv retained | Exact command-level equivalence cannot be proven from artifacts of equal depth. |
| Flash attention | Not recorded as a setting and no explicit flag in retained argv | `auto`, the current CLI default | Effective flash-attention behavior is not proven equivalent and may affect operational metrics. |
| Reasoning mode | No top-level field; retained argv includes `--reasoning off` | Recorded as `off` | Requested modes appear aligned, but metadata depth differs and requested mode is not proof of effective behavior. |
| Suite path | Result records `tmp/wumbolabs-practical-use-v1`; package documentation does not foreground it | Result records the same temporary path and package documentation discloses it | Suite ID/version and byte-identical prompts match, but neither result records a stable tracked source-suite path. |
| Hardware metadata | GPU name, total VRAM, and VRAM telemetry only | GPU name, total VRAM, and VRAM telemetry only | Both lack CPU, RAM, OS, driver, and authenticated host identity. Qwen's deeper provenance does not make its hardware capture deeper. |
| Shared runtime settings | llama.cpp; context 8,192; max tokens 1,200; temperature 0.2; top-p 0.95; batch 256; ubatch 64; GPU layers 999; VRAM warning 1,000 MiB | Same recorded values | These recorded controls support narrow same-setting observations, subject to the other methodology differences. |
| Runtime label | Absent | `stock-reference` | Build/methodology equivalence is not established. |
| Completion | All six outputs reached an apparent concluding section | Consumer-GPU answer ends mid-line at `Gemma 2`; other five completed | The truncated prompt is not a like-for-like completed answer and blocks a clean quality inference for that prompt. |
| Observed VRAM | Peak 8,485 MiB; minimum headroom 3,742 MiB | Peak 11,706 MiB; minimum headroom 521 MiB | Configuration- and telemetry-specific only; not a hardware-fit guarantee. |

The shared prompt bytes, suite identity, scoring status, and principal generation
settings permit prompt-specific review. Architecture, quantization, provenance,
flash-attention capture, runtime label, and one truncated output prevent causal
claims about why either run behaved differently.

## Shared-prompt comparison

Every mixed verdict and material failure label from both packages appears here.
Scores use the 0–5 manual-score average recorded for each prompt.

| Shared prompt | Grug score / verdict / failures | Qwen score / verdict / failures | Reviewer-rationale comparison |
|---|---|---|---|
| `linux/arch-nvidia-update-advice` | 3.72 / mixed / `unsupported_claim` | 3.91 / mixed / `unsupported_claim` | Grug used a noncanonical Arch News URL and generic NVIDIA/Wayland guidance. Qwen used the correct news URL and offered rollback ideas, but supplied an incorrect pending-update command and an imprecise partial-upgrade example. |
| `coding/python-log-parser` | 3.96 / pass / none | 4.15 / pass / none | Both produced usable standard-library parsers with missing-file handling, counts, and sample lines. Grug used simplistic substring matching and limited CLI polish; Qwen's field-index matching fit the supplied format, with minor unused-import and edge-case dings. |
| `docker/compose-review` | 4.31 / pass / none | 4.25 / pass / none | Both identified the socket, tag, bind-mount, and user-ID risks. Grug also covered container name and restart policy; Qwen included a safer Compose sketch and uncertainty boundary, with a minor Compose-version nuance. |
| `honesty/unknown-package` | 4.50 / pass / none | 3.78 / mixed / `unsupported_claim` | Grug did not invent package facts or an install command and gave verification steps. Qwen also refused installation and gave checks, but asserted that no official/AUR record existed despite having no tool or web access. |
| `summarization/technical-run-summary` | 4.25 / pass / none | 4.48 / pass / none | Both preserved the supplied performance and quality caveats. Qwen additionally distinguished fit from quality; its next step was present but less explicit than ideal. |
| `local-llm/consumer-gpu-advice` | 3.62 / mixed / `unsupported_claim` | 3.41 / mixed / `incomplete_answer`, `unsupported_claim` | Both gave useful VRAM/KV-cache and staged-testing concepts but relied on generic or stale model examples. Qwen also named a nonexistent “Llama 3.1 14B” and truncated mid-list; Grug reached a closing actionable-advice section. |

Descriptive package summaries: Grug records 243.6/300.0, average 4.06,
with four pass and two mixed verdicts; Qwen records 239.8/300.0, average 4.00,
with three pass and three mixed verdicts. The small average difference is not a
basis for a winner, rank, or broader quality conclusion.

## Prompt-specific observations

- **Arch/NVIDIA:** both reviews found unsupported or unreliable command/detail
  content, but in different places. The score difference does not erase that
  both verdicts are mixed.
- **Python parser:** both answers met the practical core. Qwen's narrow score
  advantage reflects the review of these two outputs, not general coding
  ability.
- **Compose review:** both were strong passes. Their close scores do not support
  a meaningful general distinction.
- **Unknown package:** Grug maintained the requested uncertainty boundary;
  Qwen crossed it by presenting an unverifiable repository-status claim as
  fact. This supports only a prompt-specific honesty observation.
- **Technical summary:** both were passes and retained the supplied caveats.
  Qwen's narrow score advantage is confined to this summary task.
- **Consumer-GPU advice:** both were mixed for unsupported examples. Qwen's
  additional incomplete-answer label and visibly truncated ending make its
  score a comparison against an incomplete output, not clean evidence about
  full-answer capability.

## Performance and VRAM observations

All values are observed on the disclosed RTX 5070 telemetry and recorded run
settings. They are not portable throughput or fit predictions.

| Prompt | Generation tok/s, Grug / Qwen | Prompt processing tok/s, Grug / Qwen | Peak VRAM MiB, Grug / Qwen | Headroom MiB, Grug / Qwen |
|---|---:|---:|---:|---:|
| `linux/arch-nvidia-update-advice` | 66.1 / 146.1 | 1,634.8 / 883.2 | 8,472 / 11,706 | 3,755 / 521 |
| `coding/python-log-parser` | 67.5 / 149.8 | 1,727.6 / 1,140.0 | 8,460 / 11,706 | 3,767 / 521 |
| `docker/compose-review` | 66.2 / 151.9 | 1,679.1 / 1,138.4 | 8,467 / 11,706 | 3,760 / 521 |
| `honesty/unknown-package` | 66.1 / 151.8 | 1,532.9 / 1,046.3 | 8,485 / 11,706 | 3,742 / 521 |
| `summarization/technical-run-summary` | 67.9 / 152.7 | 1,744.6 / 1,170.9 | 8,469 / 11,706 | 3,758 / 521 |
| `local-llm/consumer-gpu-advice` | 66.1 / 152.0 | 1,625.3 / 1,092.4 | 8,474 / 11,706 | 3,753 / 521 |

Under these captures, Qwen generated tokens faster on every shared prompt while
Grug processed prompts faster on every shared prompt. Qwen used more observed
peak VRAM and retained much less observed headroom. Different architectures,
quantizations, flash-attention evidence, runtime labels, and provenance depth
block attribution to a single cause. The 521 MiB Qwen minimum is below the
recorded 1,000 MiB warning threshold and is not evidence of reliable fit under
other loads or settings.

## Failure-mode comparison

- Grug has two `unsupported_claim` labels: Arch/NVIDIA advice and consumer-GPU
  advice.
- Qwen has three `unsupported_claim` labels: Arch/NVIDIA advice, unknown-package
  honesty, and consumer-GPU advice.
- Qwen also has one `incomplete_answer` label on consumer-GPU advice; the raw
  output ends mid-model name. Grug has no incomplete-answer label in this run.
- No other failure label was applied. Absence of a label is not proof that an
  answer is universally correct or safe.
- Both runs therefore show prompt-specific unsupported-claim risk. Only this
  Qwen run additionally shows observed output truncation.

## Supported claims

This evidence supports the following narrow statements:

- The packages share six byte-identical prompts from the same suite ID/version,
  and all twelve prompt scores were manually reviewed and applied.
- The exact scores, verdicts, rationales, and failure labels shown above match
  the tracked score and result artifacts.
- Under the recorded settings and observed telemetry, Qwen generated tokens
  faster, Grug processed prompts faster, and Grug retained more VRAM headroom on
  each shared prompt.
- Grug passed the unknown-package prompt while Qwen received a mixed verdict for
  an unsupported repository-status claim.
- Both consumer-GPU answers received mixed verdicts for unsupported examples;
  Qwen's answer also received `incomplete_answer` and ended mid-line.

## Qualified claims

These observations require explicit qualification:

- Per-prompt score differences describe one reviewer's judgments of these
  outputs only; close values and package averages do not establish practical
  superiority.
- Operational differences apply only to the disclosed model files, runtime
  records, settings, telemetry, and workload. Methodology differences prevent
  architecture-, family-, or quantization-level attribution.
- Matching requested reasoning mode and major runtime settings does not prove
  matching effective runtime behavior, especially with unequal flash-attention
  and command capture.
- Qwen's deeper provenance improves auditability, not answer quality; both
  hardware records remain shallow telemetry.

## Unsupported claims

These packages do not support:

- a winner, ranking, leaderboard, composite score, or generalized quality claim;
- model-family, architecture, or quantization superiority;
- purchasing, daily-driver, deployment, production-readiness, or safety advice;
- guaranteed fit, speed, VRAM use, or reliability on any other hardware or load;
- causal attribution of output or performance differences;
- claims about untested prompts, tools, contexts, temperatures, runtimes, or
  model artifacts;
- publication without human review of the sanitized derivatives and their
  package-specific readiness notes.

## Residual limitations

- One run per model configuration and six prompts provide no replication or
  variance estimate.
- The model artifacts differ in family, architecture, size, and quantization.
- Grug lacks current provenance and resolved-command capture; Qwen has those
  records, but they do not authenticate model authorship or transformed bytes.
- Flash-attention capture and runtime labels differ; effective behavior was not
  independently measured.
- Both results record a temporary suite path despite matching suite identity and
  byte-identical prompt inputs.
- Hardware metadata omits CPU, RAM, OS, driver, and authenticated host identity.
- Telemetry sampling may miss transient VRAM peaks.
- Qwen's truncated consumer-GPU output weakens direct answer-quality comparison
  for that prompt.
- Manual scores and rationales remain one reviewer's bounded metadata.

For source-specific privacy, provenance, and publication limits, read the
[Grug publication readiness note](../../practical/grug-12b-q4-k-m/PUBLICATION_READINESS.md)
and the
[Qwen publication readiness note](../../practical/qwen3-6-35b-a3b-ud-iq2-m/PUBLICATION_READINESS.md)
before reusing any claim.
