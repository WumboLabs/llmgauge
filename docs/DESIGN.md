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
  integration. This is an accepted architecture boundary, not a statement that
  the backend is implemented.
