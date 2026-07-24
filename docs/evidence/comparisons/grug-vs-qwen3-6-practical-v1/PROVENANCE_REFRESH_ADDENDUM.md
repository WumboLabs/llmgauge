# Grug provenance-refresh practical comparison addendum

This addendum extends the
[original practical comparison](README.md) with a separate Grug-12B Q4_K_M
provenance-refresh package. It does not replace or rewrite that comparison or
any source package. It compares three distinct, tracked, human-reviewed evidence
records under their disclosed conditions.

The records are not a leaderboard, composite score, purchasing guide,
daily-driver recommendation, deployment or safety finding, or generalized fit
claim. Manual scores and verdicts are bounded reviewer metadata, not objective
truth. Package averages below are descriptive only.

## Evidence roles and scope

The three evidence sources retain separate roles:

1. **Legacy Grug package** — the earlier Grug-12B Q4_K_M response set and its
   original reviewed scoring. Its shallower provenance and command capture are
   part of the historical record.
2. **Provenance-refresh Grug package** — a new Grug-12B Q4_K_M run against the
   stable tracked historical suite, with deeper provenance and capture. It has
   different generated outputs and an independent review; it does not supersede
   the legacy package.
3. **Qwen3.6 package** — the existing Qwen3.6-35B-A3B UD-IQ2_M response set and
   reviewed scoring used by the original comparison.

Source links:

- [Legacy Grug package](../../practical/grug-12b-q4-k-m/),
  [public result](../../practical/grug-12b-q4-k-m/public-export/llmgauge-result.json),
  [scores](../../practical/grug-12b-q4-k-m/public-export/scores.yaml), and
  [export index](../../practical/grug-12b-q4-k-m/export-index.json)
- [Refreshed Grug package](../../practical/grug-12b-q4-k-m-provenance-refresh-v1/),
  [public result](../../practical/grug-12b-q4-k-m-provenance-refresh-v1/public-export/llmgauge-result.json),
  [scores](../../practical/grug-12b-q4-k-m-provenance-refresh-v1/public-export/scores.yaml),
  [runtime command](../../practical/grug-12b-q4-k-m-provenance-refresh-v1/public-export/runtime-command.json), and
  [export index](../../practical/grug-12b-q4-k-m-provenance-refresh-v1/export-index.json)
- [Qwen3.6 package](../../practical/qwen3-6-35b-a3b-ud-iq2-m/),
  [public result](../../practical/qwen3-6-35b-a3b-ud-iq2-m/public-export/llmgauge-result.json),
  [scores](../../practical/qwen3-6-35b-a3b-ud-iq2-m/public-export/scores.yaml),
  [runtime command](../../practical/qwen3-6-35b-a3b-ud-iq2-m/public-export/runtime-command.json), and
  [export index](../../practical/qwen3-6-35b-a3b-ud-iq2-m/export-index.json)

All three public results and export indexes were structurally validated before
this synthesis. Structural validity establishes artifact usability, not answer
quality, safety, provenance authenticity, or publication readiness.

## Methodology and evidence-integrity differences

These differences precede and constrain every observation in later sections.

| Dimension | Legacy Grug | Refreshed Grug | Qwen3.6 | Consequence |
|---|---|---|---|---|
| Model artifact | Dense Gemma-family Grug-12B, Q4_K_M | Dense Gemma-family Grug-12B, Q4_K_M | Qwen3.6 35B-A3B mixture-of-experts, UD-IQ2_M | The Qwen comparison does not isolate model family, architecture, size, or quantization. The two Grug packages still represent separate generations, not a controlled repeat. |
| Suite source | `wumbolabs-practical-use-v1` 0.1.0 through a temporary suite path | Same suite ID/version through the stable tracked historical suite path | Same suite ID/version through a temporary suite path | Suite identity and prompt bytes align; only the refreshed run records stable tracked-suite use. |
| Provenance depth | No model-file or source-run fingerprint; no resolved command or backend provenance artifact | Model, executable/backend, run fingerprint, stable suite path, and resolved command retained in the scored source and sanitized derivative | Model, executable/backend, run fingerprint, and resolved command retained | Deeper provenance improves auditability, not response quality. Legacy and current records do not have equal provenance depth. |
| Runtime-command availability | Original argv in result metadata; no `runtime-command.json` | Resolved `runtime-command.json` and redacted argv | Resolved `runtime-command.json` and redacted argv | Exact command equivalence cannot be established from artifacts of equal depth. |
| Flash attention | No explicit setting field or retained flag | Explicit `auto` | Explicit `auto` | Requested effective behavior is not proven equivalent to the legacy run. |
| Reasoning mode | No top-level setting; retained argv includes `--reasoning off` | Explicit `off` | Explicit `off` | Requested modes appear aligned, but capture depth differs and a request is not proof of effective behavior. |
| Runtime label | Absent | `stock-reference` | `stock-reference` | Build and methodology equivalence with the legacy run is not established. |
| Runtime/executable identity | No backend self-report or executable fingerprint | Backend reports version 9672, commit `74ade5274`; public executable display fingerprint `sha256:21b13a815dd2315d` | Same retained public runtime identity fields as the refreshed run | Identity records aid traceability; they do not authenticate authorship or prove identical effective execution. |
| Shared recorded settings | llama.cpp; context 8,192; max tokens 1,200; temperature 0.2; top-p 0.95; batch 256; ubatch 64; GPU layers 999 | Same | Same | These controls permit narrow same-setting observations, subject to all other differences. |
| Hardware and timing capture | Public GPU name, total VRAM, prompt timestamps, and VRAM telemetry; no deeper host record | Private privacy-safe OS/kernel/CPU/RAM/GPU/driver and run start/end capture; public derivative retains GPU/VRAM telemetry while private sidecars are omitted | Public GPU name, total VRAM, prompt timestamps, and VRAM telemetry; no deeper host record | All public comparisons rely on observed RTX 5070 telemetry with 12,227 MiB total VRAM, not authenticated hardware identity. Telemetry can miss transient peaks. |
| Canonical source and derivative | Historical scored source is represented by its sanitized tracked derivative and package notes | Scored canonical private source is authoritative; `public-export/` is a sanitized derivative verified unchanged during export | Scored source is represented by its sanitized tracked derivative and package notes | Sanitized derivatives may transform paths and do not authenticate their source bytes. Raw source evidence remains authoritative where retained. |
| Original unscored-byte preservation | Legacy package limitations remain as documented | A 36-file pre-scoring inventory survives, but no complete byte-preserved pre-scoring copy does; scoring modified the result/report and added scores | Qwen package limitations remain as documented | The refreshed package cannot establish full original live-run byte immutability. Its current scored canonical source, not a reconstructed unscored state, anchors review. |
| Completion and attempts | Six apparent completed outputs | Six completed prompts, exit 0, not interrupted, zero retries | Five complete outputs; consumer-GPU output ends mid-line although artifact status is completed | Qwen's consumer answer is not a like-for-like complete response. Completed statuses alone do not establish output completeness or reliability. |
| Response bytes | One legacy response set | A distinct response set; every shared raw response differs from legacy and Qwen | A distinct response set | Output differences require response-specific review and cannot be attributed to one cause. |

The refreshed package's private capture is deeper, but its omitted operator
sidecars are not public evidence. The public executable fingerprint is a
shortened display identifier, not a full identity. No source fingerprint proves
model authorship, answer quality, hardware identity, or transformed-export byte
authenticity.

## Exact shared prompt set

The intersection is exactly these six prompt IDs:

1. `coding/python-log-parser`
2. `docker/compose-review`
3. `honesty/unknown-package`
4. `linux/arch-nvidia-update-advice`
5. `local-llm/consumer-gpu-advice`
6. `summarization/technical-run-summary`

For each ID, the sanitized public raw prompt bytes are identical across all
three packages. For each ID, the raw response bytes differ across all three
packages. Prompt equality supports prompt-specific comparison; response
inequality requires treating every response and review as separate evidence.

## Shared reviewed evidence

Every verdict and material failure label from all three packages is retained
below. Scores are the recorded 0–5 averages across ten manual dimensions.

| Prompt | Legacy Grug score / verdict / failures | Refreshed Grug score / verdict / failures | Qwen3.6 score / verdict / failures |
|---|---|---|---|
| `linux/arch-nvidia-update-advice` | 3.72 / mixed / `unsupported_claim` | 3.67 / mixed / `unsupported_claim`, `missing_verification` | 3.91 / mixed / `unsupported_claim` |
| `coding/python-log-parser` | 3.96 / pass / none | 4.15 / pass / none | 4.15 / pass / none |
| `docker/compose-review` | 4.31 / pass / none | 3.22 / mixed / `unsupported_claim`, `missing_verification`, `ignores_constraints` | 4.25 / pass / none |
| `honesty/unknown-package` | 4.50 / pass / none | 3.88 / mixed / `unsupported_claim` | 3.78 / mixed / `unsupported_claim` |
| `summarization/technical-run-summary` | 4.25 / pass / none | 4.53 / pass / none | 4.48 / pass / none |
| `local-llm/consumer-gpu-advice` | 3.62 / mixed / `unsupported_claim` | 2.79 / fail / `unsupported_claim`, `ignores_constraints` | 3.41 / mixed / `incomplete_answer`, `unsupported_claim` |

Descriptive package summaries:

- Legacy Grug: 243.6/300.0, average 4.06; four pass and two mixed;
  `unsupported_claim` × 2.
- Refreshed Grug: 222.4/300.0, average 3.71; two pass, three mixed,
  and one fail; `unsupported_claim` × 4, `missing_verification` × 2,
  and `ignores_constraints` × 2.
- Qwen3.6: 239.8/300.0, average 4.00; three pass and three mixed;
  `unsupported_claim` × 3 and `incomplete_answer` × 1.

These totals and averages summarize separate reviewed response sets. They are
not a composite comparison score and do not establish a winner, rank, trend, or
general quality relationship.

### Reviewer-rationale comparison

- **Arch/NVIDIA:** Legacy Grug used a noncanonical Arch News URL and generic
  NVIDIA/Wayland guidance. Refreshed Grug again called the noncanonical URL
  official, assumed an unsupported Timeshift workflow, and gave vague module
  and Wayland verification. Qwen used the correct news URL and supplied rollback
  ideas, but included an incorrect pending-update command and an imprecise
  partial-upgrade example. All three verdicts remain mixed.
- **Python parser:** All three responses delivered usable dependency-light
  standard-library parsers with practical invocation. Both Grug reviews noted
  simplistic substring severity matching and implementation/CLI edge cases;
  the refreshed review also noted broad exception handling and no explicit
  nonzero exit for malformed input. Qwen's field-index matching fit the supplied
  format, with minor unused-import and edge-case deductions. All three passed.
- **Compose review:** Legacy Grug identified socket, tag, bind-mount, user-ID,
  container-name, and restart-policy risks. Qwen identified the core risks,
  included a safer sketch and uncertainty boundary, and had a minor Compose
  version nuance. Refreshed Grug usefully warned about the socket, floating tag,
  and exposed port, but invented tag `1.2.3` and a curl endpoint/tool, incorrectly
  said a healthcheck restarts an unhealthy container, overstated root/default-
  network behavior, and proposed unverified configuration changes. The legacy
  and Qwen responses passed; the refreshed response is mixed.
- **Unknown package:** Legacy Grug refused to invent package facts or an install
  command and supplied verification steps. Refreshed Grug handled uncertainty
  and prioritized PKGBUILD inspection, but proposed GameFilter as an
  inappropriate generic Linux fallback and described NVML as though it were an
  optimizer. Qwen also refused installation and supplied checks, but asserted
  without tool or web access that no official or AUR record existed. Legacy
  passed; refreshed Grug and Qwen remain mixed with `unsupported_claim`.
- **Technical summary:** All three preserved the core performance and quality
  caveats and passed. Legacy Grug retained the supplied caveats. Refreshed Grug
  clearly separated fit from quality but omitted the supplied 4,054 MiB
  headroom value. Qwen also separated fit from quality; its next step was less
  explicit than ideal.
- **Consumer-GPU advice:** Legacy Grug provided useful VRAM/KV-cache and staged
  testing concepts but used generic or stale unsupported model examples. The
  refreshed response supplied a useful prioritization framework but violated
  explicit constraints with unsupported fit, VRAM, speed, and quality claims,
  including claims that examples were verified to fit with ample headroom.
  Qwen likewise used unsupported examples, named a nonexistent “Llama 3.1 14B,”
  and ended mid-list. Legacy and Qwen remain mixed; refreshed Grug remains fail;
  Qwen also retains `incomplete_answer`.

## Focused legacy-Grug versus refreshed-Grug comparison

The two packages use the same named model profile, quantization, suite identity,
and principal requested settings, but they contain different response bytes for
all six prompts and have unequal capture depth. The refreshed run adds stable
suite-path, resolved-command, explicit flash-attention/reasoning/runtime-label,
backend/executable, deeper private hardware, and start/end evidence. Those
records improve reproducibility and auditability; they do not improve or reduce
the reviewed content by themselves.

Verdict transitions between the separate reviews are:

- Arch/NVIDIA: mixed to mixed, with refreshed `missing_verification` added.
- Python parser: pass to pass.
- Compose review: pass to mixed, with refreshed `unsupported_claim`,
  `missing_verification`, and `ignores_constraints`.
- Unknown package: pass to mixed, with refreshed `unsupported_claim`.
- Technical summary: pass to pass.
- Consumer-GPU advice: mixed to fail, with refreshed `ignores_constraints` in
  addition to `unsupported_claim`.

These are response-set and reviewer-record differences. Differing generated
outputs and reviewer scores do **not** prove model regression, improvement,
instability, repeatability, or a general quality trend. One run per package
provides no variance estimate, and the legacy run lacks the refreshed capture
needed for a controlled repeat.

## Observed performance and VRAM

Values are prompt-specific observations under the disclosed settings and RTX
5070 telemetry. They are not portable speed, capacity, reliability, or fit
predictions.

| Prompt | Generation tok/s, legacy / refreshed / Qwen | Prompt tok/s, legacy / refreshed / Qwen | Peak VRAM MiB, legacy / refreshed / Qwen | Headroom MiB, legacy / refreshed / Qwen |
|---|---:|---:|---:|---:|
| `linux/arch-nvidia-update-advice` | 66.1 / 67.2 / 146.1 | 1,634.8 / 1,629.7 / 883.2 | 8,472 / 8,539 / 11,706 | 3,755 / 3,688 / 521 |
| `coding/python-log-parser` | 67.5 / 68.1 / 149.8 | 1,727.6 / 1,738.4 / 1,140.0 | 8,460 / 8,558 / 11,706 | 3,767 / 3,669 / 521 |
| `docker/compose-review` | 66.2 / 67.5 / 151.9 | 1,679.1 / 1,713.7 / 1,138.4 | 8,467 / 8,556 / 11,706 | 3,760 / 3,671 / 521 |
| `honesty/unknown-package` | 66.1 / 68.6 / 151.8 | 1,532.9 / 1,572.3 / 1,046.3 | 8,485 / 8,556 / 11,706 | 3,742 / 3,671 / 521 |
| `summarization/technical-run-summary` | 67.9 / 69.7 / 152.7 | 1,744.6 / 1,735.1 / 1,170.9 | 8,469 / 8,555 / 11,706 | 3,758 / 3,672 / 521 |
| `local-llm/consumer-gpu-advice` | 66.1 / 66.8 / 152.0 | 1,625.3 / 1,635.7 / 1,092.4 | 8,474 / 8,553 / 11,706 | 3,753 / 3,674 / 521 |

Under these captures, Qwen generated tokens faster on every prompt, while both
Grug runs processed prompts faster on every prompt. Qwen recorded the highest
peak VRAM and 521 MiB headroom throughout; that headroom is below the recorded
1,000 MiB warning threshold. The refreshed Grug run recorded slightly higher
peak VRAM than legacy Grug on every prompt. Architecture, quantization, capture,
runtime, and output-length differences block attribution to a single cause.

## Claim boundaries and residual limitations

This addendum supports only prompt-specific statements about the three tracked
response sets, their applied reviews, and their observed operational records.
It does not support:

- a winner, ranking, recommendation, composite score, or universal-quality
  conclusion;
- regression, improvement, instability, or a model-family trend from the two
  Grug outputs;
- model-family, architecture, or quantization superiority;
- purchasing, daily-driver, deployment, production-readiness, or safety advice;
- generalized hardware fit, throughput, VRAM, or reliability claims;
- causal attribution of response, scoring, completion, or telemetry differences;
- conclusions about untested prompts, settings, runtimes, tools, or artifacts;
- external publication without human review of each sanitized derivative and
  package-specific readiness note.

Direct limitations remain: one run per package; six prompts; no replication or
variance estimate; manual review metadata; unequal provenance, suite-path,
command, flash-attention, runtime-label, hardware, and timing capture; telemetry
sampling that may miss peaks; no complete original unscored-byte copy for the
refreshed source; path transformations in sanitized derivatives; and Qwen's
truncated consumer-GPU output. Absence of a failure label is not proof of
correctness or safety.

Read the package-specific publication readiness notes before reusing any claim:
[legacy Grug](../../practical/grug-12b-q4-k-m/PUBLICATION_READINESS.md),
[refreshed Grug](../../practical/grug-12b-q4-k-m-provenance-refresh-v1/PUBLICATION_READINESS.md),
and [Qwen3.6](../../practical/qwen3-6-35b-a3b-ud-iq2-m/PUBLICATION_READINESS.md).
