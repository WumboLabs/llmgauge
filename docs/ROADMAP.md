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

### Selected next bounded project milestone

**Human publication gate for the tracked practical evidence package (optional
website or release-note surface only after re-read).**

Recommended next accepted work, in order of preference:

1. Human re-read of the tracked package against
   [PUBLICATION_READINESS.md](evidence/practical/grug-12b-q4-k-m/PUBLICATION_READINESS.md)
   and the six cleaned outputs, then optional website or social copy outside
   this repository using only bounded claims already disclosed in the package.
2. Or a second like-for-like practical package for a different model profile
   under the same suite and claim discipline (no ranking synthesis until at
   least two reviewed packages exist and comparison scope is explicit).
3. Or a newer practical re-run that captures runtime-command and fingerprint
   provenance so the next package is not legacy on those fields.

Constraints for any follow-on:

- no automatic publication or network submit from the tool
- no rescoring of published packages without explicit intent and a new package
- no generalized ranking from a single package
- preserve mixed verdicts, privacy caveats, and provenance limits

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
