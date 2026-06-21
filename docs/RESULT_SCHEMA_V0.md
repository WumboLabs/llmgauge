# LLMGauge Result Schema v0

Canonical machine-readable result:

- `llmgauge-result.json`

Canonical human-readable report:

- `report.md`

Raw artifacts must be preserved:

- raw prompt text
- raw model output
- cleaned review output when available
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


## Cleaned output

Newer run artifacts may include `cleaned_output_path` on each prompt result.

This path points to a derived review artifact under `cleaned/`. It is intended to
make manual review easier by removing obvious llama.cpp terminal wrapper text,
prompt echo, and trailing runtime metric lines where possible.

Raw output remains the audit source of truth.
