# LLMGauge Roadmap

LLMGauge is a conservative local-first CLI for practical LLM evaluation on real consumer hardware.

The project produces defensible, reproducible public evidence about usefulness, honesty, correctness, safety, speed, VRAM headroom, and workflow fit under disclosed hardware and runtime conditions.

LLMGauge is part of the WumboLabs workflow: **Real Hardware. Real Testing. No Hype.**

## Current release line

- Current stable tag: `v0.71`
- Current package version: `0.71.0`
- Current release line: `v0.71.0`
- Current focus: public reporting, reproducible evidence, and practical model comparisons

## What LLMGauge is

LLMGauge answers practical local-model questions such as:

- Does this model produce useful answers for real workflows?
- Does it stay honest when it lacks information or tools?
- Does it fit comfortably on consumer hardware?
- How fast is it under the tested runtime settings?
- What context sizes are viable before quality, latency, or VRAM headroom degrade?
- What artifacts support the result?
- What changed between two model runs, suites, scoring passes, or releases?

## What LLMGauge is not

- a cloud evaluation service
- a model downloader
- a hosted leaderboard
- an automatic judge that hides review
- a hardware tuning tool
- a general autonomous agent framework
- a benchmark submission or telemetry system

## Current capabilities

LLMGauge currently provides:

- local-first CLI runs with preserved raw/cleaned outputs and logs
- default `llama.cpp` / GGUF runtime plus optional external local vLLM adapter
  (`backend=vllm`; operator-managed, loopback-only, sequential, non-streaming)
- artifact validation (`validate-result`, ladder/batch/fit-ladder validators)
- manual scoring templates and `score --check` / `score --scores` workflow
- auto-draft scoring as review-required triage only
- single-run `report.md` with **Report Scope**, **Evidence Summary**, **Audit Checklist**, **Prompt Artifact Audit**, and **Publish Readiness Notes**
- comparison reports with **Comparison Scope**, publish-readiness, and **Publication evidence summary**
- `export-index` machine-readable metadata for importers
- sanitized single-run `export-public` derivatives with source protection
- model profile onboarding and management commands
- dry-run and preflight commands (`smoke`, `doctor`, guided `setup`)
- context ladder and fit ladder artifacts with preserved failures
- public-proof workflow guidance across docs
- Practical Eval v1 seed suite (`wumbolabs-practical-v1`)
- artifact schema documentation and result-directory audit guidance
- publish-readiness notes and explicit claim boundaries
- identity, provenance, and evidence-equivalence fingerprint foundations

## vLLM evidence track

The vLLM work is intentionally bounded to an externally managed local
integration and evidence collection. The accepted [runtime contract](VLLM_RUNTIME_CONTRACT.md)
and [HTTP transport assessment](VLLM_HTTP_TRANSPORT_ASSESSMENT.md) define a
loopback-only, text-only backend using the Python standard library. LLMGauge
does not install, start, supervise, or otherwise own the vLLM server lifecycle;
`llama.cpp`/GGUF remains the default runtime.

### Implemented capability

- External local vLLM adapter with sequential, non-streaming requests to an
  operator-managed loopback server.
- Bounded readiness and served-model checks; no remote, authenticated, streaming,
  concurrent, or server-lifecycle management support.
- Additive runtime evidence for server `/version`, API-readiness state, optional
  `system_fingerprint`, and ordered-unique run-level fingerprints, with
  backward-compatible validation, reporting, and export handling.

### Validated evidence

- [Live external-vLLM smoke](VLLM_LIVE_SMOKE_EVIDENCE.md): real
  Qwen2.5-3B-Instruct server, successful readiness/request/validation/reporting;
  historical pre-fingerprint evidence remains authoritative for that point in
  time.
- [Fingerprint live verification](VLLM_FINGERPRINT_LIVE_SMOKE_EVIDENCE.md):
  vLLM `0.25.1`, `server_state=ready`,
  `server_state_meaning=api_ready_observation`, and
  `vllm-0.25.1-eb488855` agreed across request, prompt, and run-level artifacts.
- [Cross-runtime comparison methodology](VLLM_CROSS_RUNTIME_COMPARISON_METHODOLOGY.md):
  runtime-native metrics, input/template disclosure, and bounded claim rules.
- [First prompt comparison](VLLM_CROSS_RUNTIME_COMPARISON_EVIDENCE.md):
  `tool-honesty/fake-tool-resistance`; vLLM 31/50 (average 3.1, mixed) and
  llama.cpp 25/50 (average 2.5, fail).
- [Second prompt comparison](VLLM_CROSS_RUNTIME_SECOND_PROMPT_EVIDENCE.md):
  `shell-safety/failed-command-recovery`; vLLM 32/50 (average 3.2, mixed) and
  llama.cpp 19/50 (average 1.9, fail). The direction replicated, but these
  two prompt-specific observations are not a benchmark or runtime ranking.

### Closed investigation

- [Gemma 4 12B NVFP4 CPU-offload audit](GEMMA4_12B_NVFP4_CPU_OFFLOAD_EVIDENCE.md):
  one checkpoint, one vLLM environment, one RTX 5070 host, and one controlled
  attempt. Mixed FP8/NVFP4 recognition was verified, but requested 4 GiB CPU
  offload had no successful observed offload before a construction-time BF16
  `ParallelLMHead` CUDA OOM. The server never reached readiness.
  Classification: `not_viable` for the disclosed configuration only.

### Active limitations

- No remote, authentication, streaming, or concurrency support; no
  LLMGauge-owned vLLM lifecycle.
- vLLM VRAM is not captured.
- Throughput and token fields remain runtime-native and non-equivalent.
- F16 GGUF and BF16 Transformers weights are not proven bit-identical, and
  prompt rendering/input forms are not proven identical.
- Manual scores are reviewer judgment, not objective truth; two scored prompts
  do not establish general runtime superiority.
- Server version and fingerprint are unauthenticated metadata. Fingerprint
  equality does not prove identical runtime state, and `server_state=ready`
  means API readiness only.
- Startup success or failure does not establish answer quality. The Gemma
  `not_viable` result does not generalize to another checkpoint, runtime, host,
  offload implementation, or quantization.

### Current decision

The bounded vLLM evidence track is complete enough for the present release line.
No immediate production feature expansion is justified solely by the current
evidence. Future vLLM work requires a concrete product or evidence need.

## Fit Ladder real-workflow evidence

The [real-workflow evidence record](FIT_LADDER_REAL_WORKFLOW_EVIDENCE.md)
completes bounded operator validation of both principal Fit Ladder terminal
paths:

- total failure after all planned contexts produced preserved, retryable OOM
  attempts, with no selected child;
- success after fallback, with one preserved OOM, one completed selected child,
  and stop before the remaining lower context.

Both parents, every executed child, and both export-index records validated.
Parent scoring was rejected in both paths; the completed selected child was
admitted as a normal single-run scoring target. These results validate
orchestration and artifact handling on one host, binary, and prompt. They do not
establish model quality, optimal context, a hardware support matrix, or a
cross-model ranking.

### First reviewed public practical evidence package

**Completed:** the first reviewed practical evidence package is tracked under
[docs/evidence/practical/grug-12b-q4-k-m/](evidence/practical/grug-12b-q4-k-m/).

It publishes one bounded six-prompt `wumbolabs-practical-use-v1` run for
Grug-12B Q4_K_M on llama.cpp (RTX 5070 telemetry), with full sanitized
`export-public` artifacts, export index, source-integrity notes, and claim
boundaries. Classification remains `review_ready_with_caveats`: 4 pass and
2 mixed verdicts (`unsupported_claim` on Arch/NVIDIA update advice and
consumer-GPU local-LLM advice), legacy provenance gaps disclosed, structural
validation only, manual scores as reviewer metadata, no ranking or
daily-driver claim.

See the [public evidence index](evidence/README.md).

### Second reviewed public practical evidence package

**Completed:** the second reviewed practical evidence package is tracked under
[docs/evidence/practical/qwen3-6-35b-a3b-ud-iq2-m/](evidence/practical/qwen3-6-35b-a3b-ud-iq2-m/).

It publishes one bounded six-prompt `wumbolabs-practical-use-v1` run for
Qwen3.6-35B-A3B UD-IQ2_M on llama.cpp (RTX 5070 telemetry), using a **new**
source with model-file provenance, backend provenance, run fingerprint, and
resolved `runtime-command.json`. Classification remains
`review_ready_with_caveats`: 3 pass and 3 mixed verdicts (Arch/NVIDIA command
imprecision; unknown-package overclaim without tools; truncated consumer-GPU
advice with unsupported model examples). Structural validation only; manual
scores as reviewer metadata; no ranking, daily-driver, or Grug-versus-Qwen
comparison synthesis in this package.

Qwen-specific capture caveats retained for honesty and for future comparisons:

- flash attention used `auto` (current CLI default), unlike the older Grug argv
  which did not pass an explicit flash-attention flag;
- the suite was resolved through a temporary suite path
  (`tmp/wumbolabs-practical-use-v1`) rather than a stable tracked suite path;
- the operator console log records prompt order and completion but is not a
  complete resolved execution plan (authoritative settings live in result
  artifacts and `runtime-command.json`);
- observed minimum VRAM headroom was about 521 MiB and is **not** a general fit
  guarantee;
- public-result fingerprint fields and the export-manifest
  `source_run_fingerprint` play different roles and must remain explicitly
  documented;
- hardware telemetry (GPU name/VRAM samples) is observed metadata, not
  authenticated hardware identity.

See the [public evidence index](evidence/README.md).

### Reference practical-run capture standard

Future **reference-quality** practical evidence runs should review and preserve
the following before launch and in the resulting artifacts. This is a
documentation standard for defensible packages; it is not a schema, CLI, or
runtime contract change.

**Identity and suite**

- stable tracked suite path and suite identity (and suite fingerprint when the
  installed tool records one);
- exact model profile name and GGUF path (do not invent paths);
- model-file fingerprint and available GGUF metadata;
- llama.cpp executable path, version/build metadata, and executable fingerprint
  when available.

**Resolved runtime**

- complete resolved `runtime-command.json`;
- explicit flash-attention setting (`auto` / `on` / `off`) rather than relying
  on an implicit default without disclosure;
- explicit reasoning mode;
- context, maximum tokens, temperature, top-p, batch, ubatch, and GPU layers;
- runtime methodology label.

**Hardware and timing**

- hardware disclosure mode;
- GPU plus CPU/RAM/OS/driver metadata when safely supported and privacy-safe;
- start and end timestamps;
- VRAM baseline, peak, and minimum headroom when capture is available.

**Execution evidence**

- prompt order and per-prompt completion or failure status;
- run fingerprint when the installed tool records one;
- raw output, cleaned output, stderr, retries, OOMs, and failed attempts
  preserved without silent replacement.

Operator console logs may aid review but are not substitutes for resolved
command metadata, result JSON, or runtime-command capture. Observed telemetry is
not authenticated identity. Fingerprints identify evidence; they do not prove
authorship, hardware, answer quality, or transformed public-export bytes.

### Completed bounded practical comparison

**Completed:** the first tracked comparison across the two reviewed practical
packages is tracked at
[Grug-12B versus Qwen3.6 practical evidence comparison v1](evidence/comparisons/grug-vs-qwen3-6-practical-v1/).

The comparison verifies the exact six-prompt overlap and reviewed scoring
metadata, discloses architecture, quantization, provenance, runtime-command,
flash-attention, suite-path, hardware-capture, runtime-label, VRAM, and
completion differences before interpreting results, and preserves all mixed
verdicts and failure labels. It confines quality observations to individual
reviewed prompts and operational observations to the recorded settings and
telemetry. Package averages remain descriptive reviewer metadata; the document
does not declare a winner, ranking, purchasing choice, daily-driver choice,
model-family advantage, safety result, or generalized fit.

Methodology differences materially limit attribution: the packages use a dense
Gemma-family Q4_K_M artifact and a Qwen3.6 MoE UD-IQ2_M artifact; the Grug run
has legacy provenance and no resolved runtime-command artifact; flash-attention
and runtime-label capture differ; both results record a temporary suite path;
both hardware records omit CPU, RAM, OS, and driver metadata; and Qwen's
consumer-GPU answer is truncated. See the comparison for the exact supported,
qualified, and unsupported claims.

### Selected next bounded project milestone

**Provenance-complete Grug-12B practical rerun package.**

Capture, review, and publish one new Grug-12B Q4_K_M run of the same six-prompt
practical suite using the reference practical-run capture standard above:
stable tracked suite path, resolved runtime command, explicit flash-attention
and reasoning settings, runtime label, model/backend/run provenance, and the
available privacy-safe hardware metadata. Preserve all attempts and raw
evidence, score the new run manually without changing the legacy package, and
publish it as a separate bounded package with its own readiness review.

This selection is an evidence-capture milestone, not an instruction to rerun or
replace evidence during the completed comparison milestone. It does not
authorize model-family claims, ranking, publication outside the repository,
schema or CLI changes, runtime changes, or rescoring of either existing package.
Other practical packages and integrations remain deferred and unselected.

## Recently completed releases

Condensed highlights (newest first). Details remain in [CHANGELOG.md](../CHANGELOG.md).

| Release | Focus |
|---|---|
| v0.71 | Optional external local vLLM adapter, additive fingerprint evidence, public-export identity redaction, first tracked practical evidence package |
| v0.70 | Identity, provenance, evidence-equivalence fingerprints, and sanitized public export foundations; validated released install tag |
| v0.66 | Runtime reproducibility — command metadata, reasoning-mode metadata, model-source reporting |
| v0.65 | Guided setup / first-run onboarding (`setup`, scan, non-interactive modes) |
| v0.64 | Clean-clone readiness and pre-public-proof documentation hardening |
| v0.63 | Result artifact audit polish — Audit Checklist, Prompt Artifact Audit |
| v0.62 | Public report artifact polish — Report Scope, Evidence Summary, Comparison Scope |
| v0.61 | Export/index/report integration — artifact roles, export-index scoring fields |
| v0.60 | Public-proof workflow hardening — checklist, CLI guidance, validation caveats |
| v0.59 | Scored comparison evidence — publish-readiness and export-index scoring fields |
| v0.58 | Practical suite polish — prompt audit and metadata |
| v0.57 | Suite and scoring maturity — rubric guidance, scoreability docs |

Earlier foundations (v0.46–v0.56 and before) established artifact schemas, validation, scoring, comparison, fit ladder, model profiles, CLI modularization, and public documentation.

### v0.71 release notes (current)

The following v0.71 work is complete on `main`:

- optional externally managed local vLLM backend for single `run` (loopback-only
  stdlib transport; readiness and served-model checks)
- additive vLLM version, API-ready server-state, and system-fingerprint evidence
- fail-closed rejection of `backend=vllm` for batch, ladder, and Fit Ladder
- public-export redaction of local hostname and username tokens
- bounded live, cross-runtime, Gemma, and Fit Ladder evidence records
- first tracked reviewed practical public evidence package (Grug-12B)

Default runtime remains llama.cpp. No remote/authenticated/streaming/concurrent
vLLM support, ranking claims, Gemma viability generalization, or PyPI claim.
Packaging and clean-clone checks validate installation and CLI readiness, not
model quality.

### Selected earlier release context

- **v0.70** established identity, provenance, evidence-equivalence fingerprints,
  and sanitized public export foundations as a validated released install.
- **v0.66** added structured `runtime-command.json`, bounded `reasoning_mode`
  metadata, and `model_source` reporting for public-proof reproduction.
- **v0.65** added `llmgauge setup` as the preferred first-run path while
  preserving manual `init` fallback; no model downloads or automatic launches.
- **v0.64** hardened docs and clean-clone readiness before real-world validation.

## Later roadmap / parking lot

These are optional or exploratory. They are not core commitments:

- optional website publication helpers
- optional LocalMaxxing export/submission integration (not core; no default network activity)
- optional Monolith import/read-only integration (not core)
- richer comparison summaries when deterministic and schema-safe
- package/release automation improvements
- CI/doc automation
- model profile UX polish
- context-size and fit-ladder reporting polish
- optional static report browsing helpers

**Non-goals for later work:**

- automatic LLM-as-judge scoring
- leaderboard or universal ranking
- network submission by default
- production-readiness or daily-driver recommendations from scores alone

## Release discipline / public-proof rules

1. Feature branches from `main` with focused commits.
2. Local full gate before handoff: `uv run pytest`, `uv run ruff check .`, `git diff --check`.
3. Release metadata (`pyproject.toml`, `__init__.py`, `CHANGELOG.md`, lockfile) in a separate release-prep step — not mixed into feature work.
4. Annotated tags only after release metadata merges to `main`.
5. Preserve raw outputs, failed attempts, and scoring provenance in all workflows.
6. Manual scoring remains the trusted path; auto-drafts stay review-required until applied and reviewed.
7. Public claims require disclosed hardware, runtime, suite, scoring status, and artifact evidence.
8. Comparison reports and export index are evidence metadata — not model recommendations.

## Working rule

For every proposed task, ask:

> Does this make LLMGauge better at producing defensible public evidence about local models on real consumer hardware?

If yes, it belongs on the roadmap. If it is only private progress, model chasing, UI polish, or architecture expansion without evidence value, park it.
