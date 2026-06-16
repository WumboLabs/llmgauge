# LLMGauge Design Notes

LLMGauge is a standalone local LLM evaluation CLI/tool for practical testing on real hardware.

It grew out of the older Quant Lab workflow used by Monolith, but it must not require Monolith.

Core goals:

- practical local LLM evaluation
- llama.cpp / GGUF first
- raw prompt and raw output preservation
- reproducible run metadata
- Markdown reports for humans
- JSON results for machine import
- manual scoring first
- context-scaling support
- Monolith-compatible artifacts later

Non-goals for the first pass:

- no web UI
- no model downloads
- no driver/CUDA/package/firewall mutation
- no automatic LLM-based scoring
- no SQLite dependency
- no Monolith database migration
- no renaming legacy Quant Lab internals
