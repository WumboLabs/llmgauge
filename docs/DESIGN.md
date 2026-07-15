# LLMGauge Design Notes

LLMGauge is a standalone local LLM evaluation CLI/tool for practical testing on real hardware.

It grew out of earlier local evaluation workflows, but it must remain independently usable.

Core goals:

- practical local LLM evaluation
- llama.cpp / GGUF first
- raw prompt and raw output preservation
- reproducible run metadata
- Markdown reports for humans
- JSON results for machine import
- manual scoring first
- context-scaling support
- portable artifacts for optional downstream tooling later

Non-goals for the first pass:

- no web UI
- no model downloads
- no driver/CUDA/package/firewall mutation
- no automatic LLM-based scoring
- no SQLite dependency
- no external application database migration
- no migration of unrelated legacy internals

## Accepted architecture contracts

- [Initial vLLM runtime integration contract](VLLM_RUNTIME_CONTRACT.md) —
  externally managed, loopback-only, text-only OpenAI-compatible server
  integration.
- [vLLM HTTP transport assessment](VLLM_HTTP_TRANSPORT_ASSESSMENT.md) —
  standard-library HTTP transport is admitted for the initial vLLM client;
  no third-party HTTP dependency is required for the accepted loopback
  contract.
- Externally managed vLLM adapter (first production slice): optional
  `backend=vllm` path using `http.client` against an operator-managed loopback
  server. Does not install, start, or supervise vLLM. llama.cpp remains the
  default backend. Token counts and throughput are not claimed equivalent
  across runtimes.
- [vLLM live integration smoke evidence](VLLM_LIVE_SMOKE_EVIDENCE.md) —
  completed real-runtime smoke for one fitting model and one prompt on an
  external local server; records environment, metrics, validation, public
  export, and explicit claim boundaries (historical pre-fingerprint slice).
- [vLLM fingerprint live smoke evidence](VLLM_FINGERPRINT_LIVE_SMOKE_EVIDENCE.md) —
  post-merge live verification of server `/version`, API-ready `server_state`,
  and opaque `system_fingerprint` capture against one operator-managed loopback
  server; field capture and artifact integration only.
- [Cross-runtime comparison methodology](VLLM_CROSS_RUNTIME_COMPARISON_METHODOLOGY.md) —
  minimum rules for one credible llama.cpp-versus-vLLM comparison under existing
  capabilities; token counts and throughput remain non-equivalent across
  runtimes.
- [Cross-runtime comparison evidence](VLLM_CROSS_RUNTIME_COMPARISON_EVIDENCE.md) —
  completed first bounded llama.cpp-versus-vLLM comparison (one model family,
  one prompt, reviewed manual scores); private results remain untracked;
  throughput and weight formats stay non-equivalent across runtimes.
- [Cross-runtime second-prompt replication evidence](VLLM_CROSS_RUNTIME_SECOND_PROMPT_EVIDENCE.md) —
  completed second-prompt replication under the same methodology
  (`shell-safety/failed-command-recovery`); directional quality-gap
  replication only; not a combined runtime ranking.
- [Gemma 4 12B NVFP4 CPU-offload evidence](GEMMA4_12B_NVFP4_CPU_OFFLOAD_EVIDENCE.md) —
  completed one-checkpoint, one-host admission audit; `not_viable` for the
  disclosed configuration after a construction-time BF16 LM-head CUDA OOM;
  runtime format recognition does not imply successful offload or admission.
