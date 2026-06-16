# Migration from Quant Lab

Quant Lab is the existing local evaluation workflow.

LLMGauge is the standalone future form of that workflow.

Initial rule:

Preserve known-good Quant Lab behavior before improving it.

Known-good runner behavior to preserve:

- llama.cpp / GGUF
- combined system prompt and prompt text
- `-p "$COMBINED_PROMPT"`
- `--reasoning off`
- `--no-mmproj`
- `--no-display-prompt`
- `--simple-io`
- `--single-turn`

Known bad or fragile behavior from earlier testing:

- using `-f` for prompt files produced blank output in prior attempts
- using `--system-prompt-file` produced blank output in prior attempts
- omitting `--simple-io` caused capture problems

Legacy Monolith internals should remain untouched until a deliberate migration plan exists:

- `quant-lab`
- `MONOLITH_QUANT_LAB_ROOT`
- `quant_lab_*` SQLite tables
- `scripts/import-quant-lab-core-v2.py`
