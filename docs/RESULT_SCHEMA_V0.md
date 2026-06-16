# LLMGauge Result Schema v0

Canonical machine-readable result:

- `llmgauge-result.json`

Canonical human-readable report:

- `report.md`

Raw artifacts must be preserved:

- raw prompt text
- raw model output
- runner logs
- stderr/stdout where useful

Quality scores are separate from runtime metrics.

Runtime metrics include:

- prompt eval tokens/sec
- generation tokens/sec
- context size
- max generated tokens
- peak VRAM where available
- VRAM headroom where available
- backend
- model quantization
- llama.cpp metadata where available
