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

## Accepted architecture contracts and evidence

- [Initial vLLM runtime integration contract](VLLM_RUNTIME_CONTRACT.md) —
  externally managed, loopback-only, text-only OpenAI-compatible server
  integration.
- [vLLM HTTP transport assessment](VLLM_HTTP_TRANSPORT_ASSESSMENT.md) —
  standard-library HTTP transport for the initial client; no third-party HTTP
  dependency.
- The implemented external adapter is an optional `backend=vllm` path using
  `http.client` against an operator-managed loopback server. It does not install,
  start, or supervise vLLM; llama.cpp remains the default backend. Requests are
  sequential and non-streaming, and runtime-native token/throughput fields are
  not equivalent across runtimes.
- [vLLM live integration smoke evidence](VLLM_LIVE_SMOKE_EVIDENCE.md) —
  completed real-runtime smoke for one fitting model and one prompt; historical
  pre-fingerprint evidence remains authoritative for that point in time.
- [vLLM fingerprint live smoke evidence](VLLM_FINGERPRINT_LIVE_SMOKE_EVIDENCE.md) —
  live `/version`, API-ready `server_state`, and opaque fingerprint capture
  against one operator-managed loopback server.
- [Cross-runtime comparison methodology](VLLM_CROSS_RUNTIME_COMPARISON_METHODOLOGY.md) —
  minimum rules for a bounded llama.cpp-versus-vLLM comparison, including
  template/input disclosure and non-equivalent runtime-native metrics.
- [Cross-runtime comparison evidence](VLLM_CROSS_RUNTIME_COMPARISON_EVIDENCE.md) —
  completed first prompt-specific comparison; F16 GGUF and BF16 Transformers
  weights are not proven bit-identical.
- [Cross-runtime second-prompt replication evidence](VLLM_CROSS_RUNTIME_SECOND_PROMPT_EVIDENCE.md) —
  completed second prompt-specific observation; directional replication only,
  not a combined runtime ranking.
- [Gemma 4 12B NVFP4 CPU-offload evidence](GEMMA4_12B_NVFP4_CPU_OFFLOAD_EVIDENCE.md) —
  completed one-checkpoint, one-host admission audit; `not_viable` only for the
  disclosed configuration after a construction-time BF16 LM-head CUDA OOM.
