# vLLM fingerprint live smoke evidence

- Status: Completed (operator evidence record)
- Recorded: 2026-07-15
- Scope: Post-merge live verification of external-vLLM fingerprint and version
  capture on one operator-managed loopback server
- Related:
  - [VLLM_RUNTIME_CONTRACT.md](VLLM_RUNTIME_CONTRACT.md)
  - [VLLM_LIVE_SMOKE_EVIDENCE.md](VLLM_LIVE_SMOKE_EVIDENCE.md) (historical
    pre-fingerprint smoke; remains accurate for that earlier adapter slice)
  - [VLLM_CROSS_RUNTIME_COMPARISON_EVIDENCE.md](VLLM_CROSS_RUNTIME_COMPARISON_EVIDENCE.md)

This document records a **completed** live smoke of the merged vLLM runtime
fingerprint capture path. It is durable operator evidence for field capture and
artifact integration only. It is not a model ranking, not a publication package,
not an answer-quality review, and not a claim of server authenticity or
reproducibility.

Private result artifacts remain **untracked local evidence**. This file
summarizes bounded metadata fields; it does not replace raw outputs,
`validate-result`, or full generated JSON.

## Purpose and exact bounds

**Purpose:** Prove that the post-merge fingerprint implementation works against
**one** real, operator-managed external vLLM server by:

1. observing server `GET /version` and persisting `vllm_version` with source;
2. recording API-readiness `server_state` and `server_state_meaning` after
   readiness and served-model checks;
3. capturing per-request `system_fingerprint` and `system_fingerprint_status`
   when present and well-formed;
4. summarizing ordered-unique run-level `observed_system_fingerprints`;
5. completing one LLMGauge `run`, structural `validate-result`, and report
   rendering with explicit fingerprint claim boundaries.

**In scope for this record:**

| Bound | Value |
|---|---|
| Implementation baseline | Fingerprint capture in `472c909`; merge baseline `912ae83` |
| Server ownership | External operator-managed process (LLMGauge does not start or stop vLLM) |
| Endpoint class | IPv4 loopback HTTP only (no remote/cloud endpoint) |
| Model family | Qwen2.5-3B-Instruct (HF-style root `Qwen/Qwen2.5-3B-Instruct`) |
| Served-model alias | `llmgauge-qwen25-3b-fingerprint-smoke` |
| Suite | `suites/agent-backend-v1` (suite version `0.1.0`) |
| Prompt subset | `tool-honesty/fake-tool-resistance` only |
| Context | 8192 |
| Max tokens | 128 |
| Temperature | 0.2 |
| Top-p | 0.95 |
| Runtime label | `vllm-qwen25-3b-bf16-fingerprint-smoke` |
| Scoring | Intentionally not scored |

**Out of scope (not claimed):**

- answer quality, model quality, or production readiness;
- server authentication or that the reported version string is truthful;
- reproducibility of runs, GPU health, PID/process health, model warmth, or
  cache state;
- bit-identical model checkpoint revision identity;
- full server launch configuration, CUDA, kernel, or device inventory;
- multi-prompt suites, ladders, concurrency, batching, streaming, or remote
  endpoints;
- cross-runtime metric equivalence or ranking.

## Baseline implementation context

| Item | Value |
|---|---|
| Fingerprint implementation commit | `472c909` — *Add vLLM runtime fingerprint capture* |
| Merge into `main` | `912ae83` — *Merge vLLM runtime fingerprint capture* |
| Post-merge local gates (pre-evidence docs) | Ruff clean; pytest 390 passed, 1 skipped; `git diff --check` clean |

The historical live smoke in [VLLM_LIVE_SMOKE_EVIDENCE.md](VLLM_LIVE_SMOKE_EVIDENCE.md)
was recorded **before** these fields were persisted by the adapter. That earlier
document correctly reports `vllm_version` / `server_state` as `unknown` and
notes that `system_fingerprint` was not stored in LLMGauge artifacts at that
time. Do not reinterpret that historical smoke as if fingerprint capture already
existed.

## Operator-managed lifecycle boundary

- LLMGauge did **not** install, start, stop, or supervise the vLLM process.
- Server lifecycle, model admission, and launch configuration remain
  **operator-owned**.
- LLMGauge performed loopback HTTP readiness, optional `/version`, and one
  non-streaming chat-completions request under the accepted external-server
  contract.
- `server_state=ready` is an **API readiness observation** only. It does not
  describe PID, process health, GPU health, model warmth, cache state, or launch
  ownership.

## Environment (disclosed for this smoke)

| Item | Disclosure |
|---|---|
| Endpoint class | HTTP, IPv4 loopback (port recorded in private endpoint identity only) |
| Lifecycle ownership | `external_operator` |
| Authentication | none |
| Streaming | false |
| Server-reported version (`GET /version`) | `{"version":"0.25.1"}` → stored `vllm_version: "0.25.1"` |
| Root model (operator models listing) | `Qwen/Qwen2.5-3B-Instruct` |
| Served model alias | `llmgauge-qwen25-3b-fingerprint-smoke` |
| Max model length (operator models listing) | 8192 |
| Evaluation context | 8192 |

The model checkpoint revision and full server launch configuration remain
**outside** this smoke’s proof boundary. Do not infer additional version, build,
CUDA, kernel, model-revision, or hardware metadata from the stored fields.

## Phase 1: Version and readiness observation

Operator-managed loopback server responded successfully to:

1. **`GET /version`** — body included `"version": "0.25.1"`.
2. **Models / readiness path** — served alias
   `llmgauge-qwen25-3b-fingerprint-smoke` was present with root model
   `Qwen/Qwen2.5-3B-Instruct` and max model length 8192.

LLMGauge readiness status after checks: `ready`.

## Phase 2: LLMGauge run and structural validation

Private result directory (local only; not tracked in Git):

    results/qwen25-3b-vllm-fingerprint-live-smoke

| Setting | Value |
|---|---|
| Suite | `agent-backend-v1` (`suites/agent-backend-v1`) |
| Prompt | `tool-honesty/fake-tool-resistance` |
| Backend | `vllm` |
| Context | 8192 |
| Max tokens | 128 |
| Temperature | 0.2 |
| Top-p | 0.95 |
| Runtime label | `vllm-qwen25-3b-bf16-fingerprint-smoke` |
| Run status | `completed` |
| Prompt status | `completed` |
| Finish reason | `length` |
| Scoring | unscored (intentionally) |

Structural validation of the private result directory passed
(`validate-result`).

### Finish reason note

`finish_reason=length` resulted from the **bounded 128-token smoke budget**.
That outcome does **not** invalidate this metadata integration test. No runtime
or model-quality conclusion should be drawn from the length finish reason in this
record. The earlier pre-fingerprint smoke and cross-runtime comparison used a
larger max-token budget and are separate evidence records.

## Phase 3: Exact metadata fields observed

Values below are quoted from the private artifacts for this run. Only the
bounded fields needed for verification are restated; full generated JSON is not
copied into durable docs.

### Runtime evidence (`vllm-runtime-evidence.json`)

| Field | Observed |
|---|---|
| `vllm_version` | `"0.25.1"` |
| `vllm_version_source` | `"server_/version"` |
| `server_state` | `"ready"` |
| `server_state_meaning` | `"api_ready_observation"` |
| `readiness_status` | `"ready"` |
| `observed_system_fingerprints` | `["vllm-0.25.1-eb488855"]` |
| `lifecycle_ownership` | `"external_operator"` |
| `requested_served_model` / `observed_served_model` | `llmgauge-qwen25-3b-fingerprint-smoke` |

### Prompt result (`llmgauge-result.json`)

| Field | Observed |
|---|---|
| Prompt status | `completed` |
| `finish_reason` | `length` |
| `system_fingerprint` | `"vllm-0.25.1-eb488855"` |
| `system_fingerprint_status` | `"present"` |

Run-level runtime fields agreed with the same version and fingerprint summary:

- `runtime.vllm_version`: `"0.25.1"`
- `runtime.server_state`: `"ready"`
- `runtime.observed_system_fingerprints`: `["vllm-0.25.1-eb488855"]`
- `backend_provenance.vllm_version_source`: `"server_/version"`

### Request evidence

(`request/tool-honesty__fake-tool-resistance.json`)

| Field | Observed |
|---|---|
| `system_fingerprint` | `"vllm-0.25.1-eb488855"` |
| `system_fingerprint_status` | `"present"` |
| `finish_reason` / `backend_finish_reason` | `length` |
| `http_status` | 200 |

### Cross-artifact agreement

| Layer | Fingerprint value | Status |
|---|---|---|
| Request evidence | `vllm-0.25.1-eb488855` | `present` |
| Prompt result | `vllm-0.25.1-eb488855` | `present` |
| Run-level ordered-unique summary | `["vllm-0.25.1-eb488855"]` | single unique value |

Version, readiness state, and fingerprint metadata were therefore **persisted
consistently** across request evidence, prompt result, and run-level summary for
this one-prompt run.

Treat the fingerprint string as **bounded opaque evidence**, not as secret or
security-sensitive material, and not as a stable server, build, model, hardware,
or reproducibility identity.

## Phase 4: Report rendering

Private `report.md` rendered:

- backend-observed vLLM version from server `/version` (`0.25.1`);
- API-readiness server state (`ready`);
- ordered-unique observed system fingerprints (`vllm-0.25.1-eb488855`);
- per-prompt opaque fingerprint metadata with the same value;
- explicit fingerprint claim boundary (opaque backend metadata; equality does
  not prove identical runtime state; inequality must not be overinterpreted);
- scoring status **unscored** with no quality-ranking claim.

## Claim boundary

| Proven by this record | Not proven |
|---|---|
| Merged fingerprint implementation works against one real external vLLM server on loopback | Arbitrary models, remote endpoints, streaming, concurrency, or production readiness |
| Server-reported `/version` was observed and stored as `vllm_version` with source `server_/version` | That the server-reported version is truthful or complete launch identity |
| API-readiness `server_state=ready` with `server_state_meaning=api_ready_observation` after readiness and model checks | PID, process health, GPU health, model warmth, cache state, or launch ownership |
| Per-request fingerprint and status were captured when present | That fingerprint equality implies identical runtime state |
| Run-level ordered-unique fingerprint summary matched the single request | Reproducibility of future runs |
| Structural `validate-result` and report rendering succeeded for this private result | Answer quality or publication readiness |
| Field capture and artifact integration for this smoke configuration | Benchmark, ranking, or model-quality conclusions |

Hard boundaries restated:

1. **This smoke proves field capture and artifact integration only.**
2. **It does not authenticate the server.**
3. **It does not prove the server-reported version is truthful.**
4. **It does not make runs reproducible.**
5. **Fingerprint equality does not prove identical runtime state.**
6. **Fingerprint inequality must not be overinterpreted.**
7. **`server_state=ready` is only an API observation.**
8. **Structural validation does not prove answer quality.**
9. **One bounded prompt is not a benchmark or ranking.**
10. **No runtime or model-quality conclusion should be drawn from `finish_reason=length`.**
11. **The run was intentionally not scored.**

## Residual risks

- Operator-owned server processes can change between runs without LLMGauge
  detecting a full configuration delta.
- Opaque fingerprints may change or stay the same for reasons outside LLMGauge’s
  observation surface.
- Directory-model / GGUF-style provenance remains unavailable for `backend=vllm`
  (`served_model_only`); identity is the served-model name.
- Private result paths, scores (none here), request evidence, and exports must
  stay untracked and out of durable public docs beyond the bounded fields above.

## Reproducibility outline (operator review)

Commands below are an outline for an operator who already has a fitting
operator-managed local vLLM server on **loopback**, serving a known Qwen2.5-3B-
Instruct alias, with server lifecycle owned outside LLMGauge. They are not a
guarantee that other hosts, models, or vLLM builds will succeed.

Do not commit `results/`, score files, request evidence copies, temporary
exports, or private config paths.

1. Operator starts and admits the model outside LLMGauge (loopback only).
2. Confirm readiness with a direct models listing against the loopback endpoint.
3. Confirm server `GET /version` returns a parseable version string when testing
   fingerprint capture.
4. LLMGauge dry run (no evaluation HTTP / no result directory), then real `run`
   with `backend=vllm`, suite `agent-backend-v1`, prompt subset
   `tool-honesty/fake-tool-resistance`, context 8192, max tokens 128 (or another
   deliberate smoke budget), temperature 0.2, top-p 0.95, and a dedicated private
   result directory.
5. Run `validate-result` on that directory.
6. Inspect `vllm-runtime-evidence.json`, the prompt row in
   `llmgauge-result.json`, request evidence, and `report.md` for version, server
   state, and fingerprint agreement.
7. Do **not** treat unscored output or `finish_reason=length` as quality
   evidence.

## Relationship to other evidence

| Document | Role |
|---|---|
| [VLLM_LIVE_SMOKE_EVIDENCE.md](VLLM_LIVE_SMOKE_EVIDENCE.md) | Historical pre-fingerprint live smoke; adapter did not yet persist version/fingerprint fields |
| [VLLM_CROSS_RUNTIME_COMPARISON_EVIDENCE.md](VLLM_CROSS_RUNTIME_COMPARISON_EVIDENCE.md) | Separate scored llama.cpp-versus-vLLM comparison under larger max-token budget |
| This document | Post-merge fingerprint capture live verification only |

## Deferred work

Not started by this documentation milestone:

- optional second-prompt cross-runtime replication under the accepted methodology;
- Gemma NVFP4 CPU-offload audit (separate track);
- any further runtime, schema, report, or export code changes.
