# vLLM live integration smoke evidence

- Status: Completed (operator evidence record)
- Recorded: 2026-07-15
- Scope: One real external-vLLM integration smoke on WumboJetsII
- Related contracts: [VLLM_RUNTIME_CONTRACT.md](VLLM_RUNTIME_CONTRACT.md),
  [VLLM_HTTP_TRANSPORT_ASSESSMENT.md](VLLM_HTTP_TRANSPORT_ASSESSMENT.md)

This document records a completed real-runtime smoke for the externally managed
vLLM adapter. It is an evidence boundary record, not a general model ranking,
not a publication package, and not a claim of answer quality.

## Purpose

Prove that LLMGauge can:

1. talk to an **operator-managed** local vLLM server over the admitted loopback
   HTTP transport;
2. complete **one** suite prompt through the normal `run` path;
3. write additive vLLM runtime/request evidence;
4. pass structural `validate-result`; and
5. produce a sanitized `export-public` derivative without mutating the private
   source result.

This smoke does **not** prove arbitrary models, remote endpoints, streaming,
concurrency, batching, ladders, long-context behavior, cross-runtime metric
equivalence, or answer quality.

## Claim boundary

| Proven | Not proven |
|---|---|
| Runtime compatibility for one fitting Hugging Face model under the tested vLLM launch shape | Support for other models, quantizations, or hardware |
| Successful adapter execution for one prompt | Answer quality, honesty, or safety of the response |
| Structural result validation | Publication readiness without human review |
| Public-export sanitization and source immutability for this run | That every future export is free of private data without inspection |
| Loopback external-server path works end-to-end | Remote/cloud endpoints, HTTPS, authentication, streaming, batching, ladders |

Distinctions preserved:

- **Runtime compatibility** — server and model loaded and answered on the host.
- **Successful adapter execution** — LLMGauge completed a real `run` with
  `backend=vllm`.
- **Artifact structural validation** — `validate-result` and public-export
  validation passed.
- **Answer quality** — not assessed; no manual scores applied in this record.
- **Publication readiness** — not claimed; public export still requires human
  review before any public use.

## Environment

| Item | Value |
|---|---|
| Operator host label | WumboJetsII |
| GPU | RTX 5070 12 GB |
| vLLM version | 0.25.1 |
| Server ownership | External operator-managed process (not started by LLMGauge) |
| Endpoint class | Loopback HTTP |
| Endpoint (local only) | `127.0.0.1:8000` |
| Backing model | `Qwen/Qwen2.5-3B-Instruct` |
| Served model alias | `llmgauge-qwen25-3b-smoke` |
| Context (server / evaluation) | 8192 |

Server launch shape used by the operator (summary):

- `dtype` bfloat16
- `gpu-memory-utilization` 0.75
- `max-num-seqs` 1
- `generation-config` vllm

LLMGauge does not own server lifecycle. Exact operator launch argv may vary;
the values above describe the smoke configuration that produced the recorded
results.

## Phase 1: Direct readiness (`/v1/models`)

Direct OpenAI-compatible models listing against the loopback server succeeded.
The served model alias was available for subsequent chat requests.

## Phase 2: Direct chat-completions

Direct `/v1/chat/completions` against the same loopback server succeeded with:

| Field | Observed |
|---|---|
| Response text | `vLLM smoke passed` |
| `finish_reason` | `stop` |
| `prompt_tokens` | 35 |
| `completion_tokens` | 6 |
| `total_tokens` | 41 |
| `system_fingerprint` | `vllm-0.25.1-eb488855` |

Note: the adapter does **not** currently persist `system_fingerprint` into
LLMGauge artifacts. Capture of `system_fingerprint`, `vllm_version`, and richer
`server_state` is deferred future evidence work, not a defect of this smoke
documentation slice.

## Phase 3: LLMGauge dry run

Dry run succeeded for:

| Setting | Value |
|---|---|
| Suite | `agent-backend-v1` |
| Prompt | `tool-honesty/fake-tool-resistance` |
| Backend | `vllm` |
| Context | 8192 |
| Max tokens | 512 |
| Temperature | 0.2 |
| Top-p | 0.95 |

Dry run does not send evaluation HTTP or create a result directory; it resolves
and prints the plan only.

## Phase 4: Real LLMGauge run and validation

Real run completed with private result directory:

    results/vllm-qwen25-3b-smoke-8k

(Local private artifact; not tracked in Git.)

Observed run evidence:

| Field | Observed |
|---|---|
| Run status | `completed` |
| Prompt status | `completed` |
| Requested served model | matched observed served model |
| `finish_reason` | `stop` |
| `prompt_tokens` | 209 |
| `completion_tokens` | 436 |
| `request_wall_time_seconds` | 4.966604451001331 |
| `end_to_end_completion_tps` | 87.78633456749246 |
| `failure_class` | null |
| `failure_detail` | null |

Structural validation of the private result directory passed
(`validate-result`).

Current runtime evidence intentionally reports:

- `server_state`: `unknown`
- `vllm_version`: `unknown`

These are expected for the present adapter slice when version and lifecycle
state are not collected from the server. They are future fingerprint/evidence
work, not failures of this smoke.

Token counts and end-to-end completion throughput are **backend-reported /
request-boundary** metrics for this run. They are not claimed equivalent to
llama.cpp prompt-eval or decode-only throughput.

## Phase 5: Public export and source immutability

Public export completed at:

    tmp/vllm-qwen25-3b-smoke-public

(Local temporary derivative; not tracked in Git.)

- Public export validation passed.
- Transformed files:
  - `llmgauge-result.json`
  - `request/tool-honesty__fake-tool-resistance.json`
  - `vllm-runtime-evidence.json`
- No files were omitted from the export selection for this result.
- Source artifact hashes remained unchanged (source immutability).
- Sensitive-string scan found no matches.

Public export remains a sanitized derivative requiring human review before any
publication. Structural validation and a clean scan do not equal publication
readiness.

## Evidence limitations (current)

- Single host, single GPU class, single vLLM version, single model, single
  prompt, single context size.
- Server lifecycle and admission logs remain operator-owned outside LLMGauge.
- `vllm_version` and `server_state` in LLMGauge runtime evidence are `unknown`.
- Direct-API `system_fingerprint` is not persisted by the adapter today.
- No manual scoring, comparison, ladder, batch, or multi-prompt suite expansion.
- No remote endpoint, streaming, concurrency, or authentication exercise.

## Reproducible command outline

Commands below are an outline for an operator who already has a fitting local
vLLM server serving `llmgauge-qwen25-3b-smoke` on loopback. They are not a
guarantee that other hosts, models, or vLLM builds will succeed.

1. Operator starts and admits the model outside LLMGauge (loopback only).
2. Confirm readiness with a direct `/v1/models` check against the loopback
   endpoint.
3. Optional: direct `/v1/chat/completions` smoke with a trivial prompt.
4. LLMGauge dry run (no HTTP evaluation):

```bash
uv run llmgauge run \
  --backend vllm \
  --vllm-endpoint http://127.0.0.1:8000 \
  --served-model llmgauge-qwen25-3b-smoke \
  --model-id llmgauge-qwen25-3b-smoke \
  --suite agent-backend-v1 \
  --only tool-honesty/fake-tool-resistance \
  --ctx 8192 \
  --max-tokens 512 \
  --temp 0.2 \
  --top-p 0.95 \
  --dry-run
```

5. Real run:

```bash
uv run llmgauge run \
  --backend vllm \
  --vllm-endpoint http://127.0.0.1:8000 \
  --served-model llmgauge-qwen25-3b-smoke \
  --model-id llmgauge-qwen25-3b-smoke \
  --suite agent-backend-v1 \
  --only tool-honesty/fake-tool-resistance \
  --ctx 8192 \
  --max-tokens 512 \
  --temp 0.2 \
  --top-p 0.95 \
  --out results/vllm-qwen25-3b-smoke-8k
```

6. Validate and export (private paths remain local):

```bash
uv run llmgauge validate-result results/vllm-qwen25-3b-smoke-8k
uv run llmgauge export-public results/vllm-qwen25-3b-smoke-8k \
  --out tmp/vllm-qwen25-3b-smoke-public
```

Do not commit `results/` or temporary public-export directories.

## Relationship to roadmap milestones

| Milestone | Status relative to this record |
|---|---|
| Runtime contract + stdlib transport admission | Already accepted |
| Externally managed adapter implementation | Merged on `main` before this record |
| Fitting-model integration smoke | **Completed** by this evidence |
| Cross-runtime comparison methodology | Next bounded product work |
| Server/version fingerprint capture (`vllm_version`, `server_state`, `system_fingerprint`) | Deferred evidence enrichment |
| Gemma NVFP4 CPU-offload audit | Separate investigation; not gated by this smoke |

## Summary statement

On WumboJetsII with vLLM 0.25.1 and an operator-managed loopback server serving
`Qwen/Qwen2.5-3B-Instruct` as `llmgauge-qwen25-3b-smoke`, LLMGauge completed a
real single-prompt `agent-backend-v1` run at 8k context, validated the private
result, and produced a validated public export without mutating source
artifacts. That is one fitting model and one prompt through the external-server
adapter—not a general vLLM capability claim.
