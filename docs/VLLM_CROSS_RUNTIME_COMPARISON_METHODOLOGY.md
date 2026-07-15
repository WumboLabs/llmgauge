# Cross-runtime comparison methodology (llama.cpp vs vLLM)

- Status: Accepted methodology (documentation only)
- Accepted: 2026-07-15
- Scope: First bounded llama.cpp-versus-vLLM comparison under existing LLMGauge capabilities
- Related:
  - [VLLM_RUNTIME_CONTRACT.md](VLLM_RUNTIME_CONTRACT.md)
  - [VLLM_LIVE_SMOKE_EVIDENCE.md](VLLM_LIVE_SMOKE_EVIDENCE.md)
  - [PUBLIC_REPORTING.md](PUBLIC_REPORTING.md)
  - [RESULT_SCHEMA_V0.md](RESULT_SCHEMA_V0.md)

This document defines the **minimum** methodology for one credible comparison
between a direct-process `llama.cpp` run and an externally managed local vLLM
run. It does **not** implement or execute that comparison.

## Purpose

Establish what LLMGauge may and may not claim when placing llama.cpp and vLLM
results side by side. Normalization provides comparison vocabulary; it is not
proof that the runtimes implement equivalent tokenization, templates, kernels,
memory accounting, or throughput semantics.

Parent contracts already require:

- separate server-admission evidence from per-request evaluation evidence;
- backend-reported token counts labeled by source;
- end-to-end completion throughput for vLLM, not decode-only throughput;
- no silent conversion between prompt and chat forms with an unidentified
  template;
- structural validation of artifacts, not answer quality.

## Claim boundary

A completed first comparison may support only **bounded, disclosed** statements
about the exact model identities, suite, prompt subset, hardware, runtime
versions, quantizations or dtypes, and settings used.

| May claim (when evidence supports it) | Must not claim |
|---|---|
| Under these disclosed settings, runtime A completed the shared prompt subset with these observed wall times / native token counts / finish reasons | Universal runtime superiority of llama.cpp or vLLM |
| Answer quality differences after **manual** scoring of the same prompt text | That backend-reported tokens/s are the same physical unit across runtimes |
| That structural `validate-result` passed for each private result | That validation proves answer quality or publication readiness |
| That public export produced a sanitized derivative requiring human review | That token counts are interchangeable across tokenizers or templates |
| That throughput differences are **observed under disclosure**, with likely contributors listed | That throughput differences are caused only by “engine quality” without disclosing dtype, quant, templates, cache, or server config |

Hard boundaries:

1. **One comparison is not a ranking system.** It does not establish general
   superiority across models, hardware classes, context sizes, or workloads.
2. **Token counts may differ** across runtimes even for the same natural-language
   prompt, because tokenizers, chat templates, special tokens, and message
   framing can differ.
3. **Throughput is not a single comparable scalar.** Differences may reflect
   dtype, quantization, kernels, templates, prefix/KV cache state, continuous
   batching or server config, measurement boundary (process vs HTTP), and
   warm/cold state—not only the named engine.
4. **Answer quality is scored separately from speed.** Manual scores remain
   review metadata. Auto-draft scores stay triage until reviewed.
5. **Validation proves artifact structure**, references, and schema
   compatibility—not answer quality, honesty, safety, or readiness to publish.

## Methodology minimum

### 1. Model identity

Use the **same model family and instruct checkpoint content** where technically
possible.

| Side | Identity rules |
|---|---|
| vLLM | Hugging Face / Transformers-style checkpoint admitted by the operator-managed server. Record requested and observed served-model names separately. Directory-model cryptographic provenance may be partial or unavailable in the current adapter slice. |
| llama.cpp | GGUF built from the same instruct family and, where the operator can verify it, the same upstream checkpoint lineage. Record GGUF provenance (filename, size, full local SHA-256 when available) and quantization. |

Do **not** treat a matching display name alone as cryptographic identity.
Disclose when the comparison is:

- **same-checkpoint content** (operator-verified same upstream weights lineage),
  or
- **same-family only** (e.g. instruct-tuned Qwen2.5-3B GGUF vs HF weights without
  a shared manifest fingerprint).

Quantization and dtype are **first-class disclosures**, not footnotes. A GGUF
`Q4_K_M` run versus a vLLM `bfloat16` run is a valid **qualified** comparison
only when those weight formats are stated in every public claim.

### 2. Prompt suite and prompt text

| Requirement | Rule |
|---|---|
| Suite | Same `suite_id` and `suite_version` on both runs |
| Prompt subset | Identical `--only` selection (or both full-suite with the same include set) |
| Prompt text | Same suite files / built-in suite content; do not edit one side’s prompt copy |
| Input form | Record whether each backend used plain prompt text, chat messages, or a rendered template |

For the first experiment, prefer a **clearly bounded subset** over a large suite
so failures and incomplete outputs remain inspectable.

### 3. Shared generation settings

Match these requested settings on both sides:

| Setting | First-experiment default | Notes |
|---|---|---|
| Context limit (`--ctx`) | `8192` | Requested limit; server-effective limit remains separate evidence when known |
| Max completion tokens (`--max-tokens`) | `512` | Backend field may differ; record the requested value |
| Temperature (`--temp`) | `0.2` | Do not silently drop unsupported sampling |
| Top-p (`--top-p`) | `0.95` | Same |

Unsupported settings must fail capability validation rather than be approximated.
Seed may be set when both backends accept it; if only one side supports seed,
record the asymmetry and do not claim identical sampling trajectories.

### 4. Templates and tokenization (explicit recording)

For each run, record what is known and mark the rest `unknown` or `partial`:

- chat-template identity or “server-side template not identified”;
- tokenizer identity when locally available;
- whether LLMGauge sent ordered chat messages (vLLM slice) versus
  llama.cpp’s process-rendered prompt path;
- that `raw/*.prompt.md` combined forms are **review aids** and are not claimed
  byte-identical to the backend’s evaluated input.

Do not claim the evaluated inputs were identical unless template and tokenizer
identity evidence supports that claim. Prefer: “same suite prompt text; runtime
framing may differ as disclosed.”

### 5. Metrics: direct vs qualified

Report **runtime-native** metrics side by side. Never merge them into one
anonymous “tokens/s” without labels.

| Metric | llama.cpp (typical) | vLLM (current slice) | Comparison rule |
|---|---|---|---|
| Prompt token count | Backend / log-derived when present | Backend-reported `prompt_tokens` when present | **Qualified only** — different tokenizers/templates allowed |
| Completion token count | Backend / log-derived when present | Backend-reported `completion_tokens` when present | **Qualified only** |
| Request / process wall time | Process wall time for the launched evaluation | `request_wall_time_seconds` at the LLMGauge HTTP boundary | **Qualified** — different lifecycle boundaries |
| Prefill / prompt-eval throughput | `prompt_eval_tps` when parsed from llama.cpp logs | Not fabricated from wall time | **Do not equate** missing or differently defined values |
| Decode / generation throughput | `generation_tps` when parsed from llama.cpp logs | Not claimed; `generation_tps` remains null for vLLM in the current adapter | **Do not equate** to vLLM end-to-end rates |
| End-to-end completion throughput | May be absent or differently defined | `end_to_end_completion_tps` = completion tokens / positive request wall time | **Report with label**; not decode-only; **not** claimed equivalent to `generation_tps` |
| Finish reason | Backend value (+ normalized when lossless) | Backend value (+ normalized when lossless) | **Direct** for shared normalized values; keep raw backend values |
| Generated text | Raw then cleaned derivative | Raw then cleaned derivative | **Direct** for human review and manual scoring |
| Peak VRAM / memory samples | When captured | When captured | **Qualified** — sampler scope and attribution differ |
| Failure class | Preserved failure taxonomy | vLLM failure class / detail when present | **Direct** for completion vs failure labeling |

**Rule of thumb:** answer text and completion success/failure can be compared
directly under the shared suite. Token counts and throughput always need
runtime-native labels and qualification.

### 6. Hardware and runtime disclosures

Every comparison write-up must disclose:

| Category | Examples |
|---|---|
| Hardware | GPU model and VRAM class; CPU offload if any (say “none” when full GPU) |
| Host role | Operator-managed local machine; no remote/cloud endpoints in this methodology |
| llama.cpp | Executable identity/version when available; GPU layers; batch/ubatch; flash-attention mode; reasoning mode |
| vLLM | Version when known; otherwise `unknown` with that label; served model; loopback endpoint **class** only (scheme + loopback + port)—never credentials or non-loopback URLs in public text |
| Weights | HF revision or GGUF quant/dtype; requested vs observed quantization |
| KV cache / server | Context length, `max-num-seqs` or equivalent, gpu-memory-utilization, any prefix cache notes the operator can honestly state |
| Warmth | `cold` / `warm` / `unknown` per [VLLM_RUNTIME_CONTRACT.md](VLLM_RUNTIME_CONTRACT.md); do not invent warmth |

Server lifecycle remains outside LLMGauge. Admission duration must not be folded
into request throughput.

### 7. Warm-up and run-order rules

1. **Stable host.** Avoid concurrent heavy GPU jobs on the same device.
2. **No hidden retries.** Do not silently re-issue a failed evaluation request.
   Preserve every attempt as its own evidence if a rerun is deliberate.
3. **Warm-up (recommended).** After model admission (vLLM) or first process load
   (llama.cpp), run one non-scoring throwaway generation **or** clearly label the
   first scored request as potentially cold. Prefer discarding warm-up outputs
   from scored comparison sets.
4. **Run order.** Record order (e.g. llama.cpp first, then vLLM, or the reverse).
   Prefer one complete backend pass before the other rather than interleaving
   prompts across backends on a contended GPU.
5. **Sequential only.** One evaluation request at a time. No concurrency
   benchmark, no continuous-batch load test, no multi-client fan-out.
6. **Server state labels.** Default to `unknown` unless direct evidence supports
   `cold` or `warm`. Readiness alone does not prove warmth or cache reuse.

### 8. Failure and incomplete-output handling

| Case | Handling |
|---|---|
| OOM / admission failure | Record as fit/admission failure; do not convert into a quality score |
| Transport / timeout / HTTP error | Preserve failure class and detail; do not retry silently |
| `finish_reason` length/stop mismatch | Keep backend value; treat max-token truncation as incomplete for quality claims until scored |
| Partial suite completion | Compare only the shared completed prompt IDs; disclose dropouts |
| Missing optional metrics | Leave unavailable; do not invent tokens/s |
| Structural validation failure | Fix or re-run before any public claim; validation is a gate, not a polish step |

Failed attempts remain evidence. Do not delete or overwrite them to manufacture
a clean story.

### 9. Scoring and reporting workflow

Use existing CLI capabilities only:

1. Run llama.cpp result directory (private).
2. Run vLLM result directory (private).
3. `validate-result` on each.
4. Inspect raw and cleaned outputs.
5. Manual score both runs when making quality claims (`score --init`, review,
   `score --check`, `score --scores`).
6. Regenerate single-run `report.md` after scoring.
7. `compare` the two result directories for a multi-run evidence summary.
8. Read **Comparison Scope**, **Publish Readiness Notes**, and **Publication
   evidence summary**.
9. Optional: `export-public` per run; human-review before any publication.

Notes on current `compare` behavior:

- Like-for-like quality flags consider suite, suite version, prompt set, context,
  max tokens, temperature, and **runtime labels**. Different backends often use
  different runtime labels even when sampling settings match.
- Treat a `no` like-for-like flag caused by backend/runtime-label differences as
  expected for cross-runtime work: still useful for evidence layout, **not** a
  free pass to publish ranking-style claims.
- Speed columns may show llama.cpp `generation_tps` beside vLLM
  `end_to_end_completion_tps`. Keep the methodology labels; do not narrate them
  as the same metric.

Public reporting still follows [PUBLIC_REPORTING.md](PUBLIC_REPORTING.md):
comparison output is evidence, not a leaderboard.

## Recommended first comparison experiment

Selected after inspecting:

- completed vLLM live smoke evidence ([VLLM_LIVE_SMOKE_EVIDENCE.md](VLLM_LIVE_SMOKE_EVIDENCE.md));
- local untracked result artifacts for that smoke;
- operator-local model assets and model-profile inventory (private; not
  committed).

### Selection rationale

| Candidate | Decision |
|---|---|
| **Qwen2.5-3B-Instruct** | **Recommended.** Only model with a completed fitting-model external-vLLM smoke on the operator host used for integration proof. Before execution, the operator must verify availability and provenance of both the Hugging Face checkpoint and the corresponding GGUF. Small enough for comfortable 8k sequential runs on a 12 GB-class GPU under the smoke launch shape. |
| Larger Qwen3 / Qwen3.6 GGUF profiles already used for llama.cpp practical suites | Deferred. No completed vLLM fit proof in-repo for those sizes on the same 12 GB-class path. |
| Gemma 4 12B family (including NVFP4 paths) | Deferred. Prior contract notes a full-GPU admission fit failure for a related 12 GB investigation; CPU-offload audit remains a separate milestone. |

Do not invent a tracked repo profile for Qwen2.5-3B. At methodology time, example
profiles are placeholders; operator-local profiles may list other families. The
llama.cpp side should use an operator-provided GGUF path or a **local** profile
the operator creates. The vLLM side continues to use served-model identity, not
a GGUF path.

### Experiment shape

| Parameter | Value |
|---|---|
| Model family | Qwen2.5-3B-Instruct |
| vLLM weights | Same instruct checkpoint family as the live smoke (`Qwen/Qwen2.5-3B-Instruct` lineage); dtype/quant as operator-admitted (smoke used bf16) |
| llama.cpp weights | Operator GGUF of the same instruct family; **disclose quant** (F16/Q8/Q6/Q5/Q4/etc.). Prefer the closest practical parity the host can run; if using a low-bit quant against bf16, state that explicitly in every speed or quality claim |
| Suite | `agent-backend-v1` |
| Prompt subset | `--only tool-honesty/fake-tool-resistance` (single high-stakes tool-honesty prompt; same subset as the completed vLLM smoke) |
| Context | `8192` |
| Max tokens | `512` |
| Temperature | `0.2` |
| Top-p | `0.95` |
| Execution | Sequential; one backend at a time; no batch command, no ladder, no fit ladder, no concurrency |
| Endpoint class | Loopback-only external vLLM; no remote endpoints |
| Long-context claims | None (single short suite prompt; 8k is a limit, not a long-context stress claim) |

### Operator outline (not executed by this milestone)

1. Admit Qwen2.5-3B-Instruct on the operator-managed local vLLM server (loopback).
2. Confirm readiness (`/v1/models`) and optional direct chat smoke.
3. LLMGauge dry-run then real `run` with `backend=vllm`, matching the shared
   settings table, writing a **new** private result directory dedicated to the
   comparison (do not overwrite prior smoke artifacts unless intentional).
4. LLMGauge dry-run then real `run` with default llama.cpp backend against the
   operator GGUF, same suite/subset/settings, separate private result directory.
5. Apply warm-up and run-order rules; record order and warmth labels.
6. Validate both results; inspect raw/cleaned outputs; manual-score if quality
   claims are intended.
7. `compare` the two directories; read scope and publish-readiness sections.
8. Optional dual `export-public`; human review before any public use.

Exact machine paths, private result names, and loopback URLs stay in operator
notes or ignored local config—not in public methodology claims.

### Explicit non-goals of the first experiment

- No multi-model sweep
- No context ladder or fit ladder
- No batching or continuous-batch throughput curves
- No remote/cloud endpoints or authentication
- No streaming / TTFT claims
- No long-context preload stress (`long-context/synthetic-agent-preload` is out
  of the first subset)
- No Gemma NVFP4 CPU-offload work
- No requirement for cryptographic directory-model fingerprints before the first
  run (record what is available; mark the rest partial/unknown)
- No schema or report-code changes in this methodology milestone

## What “success” means for the later execution milestone

A later **execution** milestone succeeds when:

1. both private results complete or honestly fail with preserved evidence;
2. both pass structural validation when completion is claimed;
3. disclosures in this methodology are filled (or explicitly marked unknown);
4. any public narrative respects the claim boundary above;
5. no private paths, credentials, or non-loopback endpoints are published.

It does **not** require that one runtime “wins.”

## Deferred work

- Server/version fingerprint capture (`vllm_version`, defensible `server_state`,
  `system_fingerprint`) when the adapter can persist them
- Directory-model provenance fingerprints for vLLM checkpoints
- Broader suite expansion and multi-prompt statistical replication
- Same-tokenizer recount studies (explicitly labeled secondary analysis)
- Streaming / TTFT methodology
- Concurrency and continuous-batch methodology
- Gemma NVFP4 CPU-offload audit as its own investigation

## Summary

LLMGauge may compare llama.cpp and vLLM on a shared suite and shared requested
settings, with runtime-native metrics and honest disclosures. It may not treat
token counts or tokens-per-second as interchangeable, may not declare universal
runtime superiority from one experiment, and may not substitute structural
validation for quality review or publication judgment.
