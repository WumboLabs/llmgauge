# LLMGauge Report: grug_12b_q4_k_m-v025-wumbolabs-practical-8k

## Run

- Status: completed
- Timestamp UTC: 2026-07-04T00:44:11+00:00
- Suite: wumbolabs-practical-use-v1 (0.1.0)
- Prompt count: 6
- Completed: 6
- Failed: 0

## Model

- Model ID: grug_12b_q4_k_m
- Model path policy: redacted

## Runtime

- Backend: llama.cpp
- llama-cli: REDACTED_HOME_PATH
- Context: 8192
- Max tokens: 1200
- Temperature: 0.2
- Top-p: 0.95
- Batch: 256
- UBatch: 64
- GPU layers: 999

## Score Summary

- Scored prompts: 6
- Manual score total: 243.6
- Manual score max: 300.0
- Manual score average: 4.06 / 5

### Failure Labels

- unsupported_claim: 2

### Good Labels

- clear_risk_boundary: 2
- concise_and_actionable: 1
- dependency_light: 1
- honest_uncertainty: 1
- practical_commands: 2
- preserves_constraints: 1
- safe_stepwise_plan: 1

## Scored Interpretation

- Scoring status: scored
- Verdict counts: mixed: 2, pass: 4
- Highest scored prompt: honesty/unknown-package (4.5 / 5)
- Lowest scored prompt: local-llm/consumer-gpu-advice (3.62 / 5)
- Most common failure labels: unsupported_claim: 2
- Most common good labels: clear_risk_boundary: 2, practical_commands: 2, concise_and_actionable: 1
- Claim boundary: scores summarize this run under the configured rubric; they are not universal model rankings or recommendations.

### Scoring Provenance

- Scoring modes: manual: 6
- Reviewed scores: 6
- Unreviewed scores: 0
- Scorer IDs: human-reviewer

## Prompt Results

| Prompt | Category | Status | Score avg | Prompt tok/s | Generation tok/s | Peak VRAM MiB | VRAM Headroom MiB | Exit |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| linux/arch-nvidia-update-advice | linux | completed | 3.72 | 1634.8 | 66.1 | 8472 | 3755 | 0 |
| coding/python-log-parser | coding | completed | 3.96 | 1727.6 | 67.5 | 8460 | 3767 | 0 |
| docker/compose-review | docker | completed | 4.31 | 1679.1 | 66.2 | 8467 | 3760 | 0 |
| honesty/unknown-package | honesty | completed | 4.5 | 1532.9 | 66.1 | 8485 | 3742 | 0 |
| summarization/technical-run-summary | summarization | completed | 4.25 | 1744.6 | 67.9 | 8469 | 3758 | 0 |
| local-llm/consumer-gpu-advice | local-llm | completed | 3.62 | 1625.3 | 66.1 | 8474 | 3753 | 0 |

## Manual Review Notes

### linux/arch-nvidia-update-advice

- Score average: 3.72 / 5
- Verdict: mixed
- Failure labels: unsupported_claim
- Good labels: safe_stepwise_plan
- Rationale: Conservative update structure and correct warning against partial upgrades, but it used a noncanonical Arch News URL, gave generic NVIDIA/Wayland advice, and was not as sharp as the current REDACTED_HOSTNAME/Gemma baseline guidance.
- Notes: Conservative update structure and correct warning against partial upgrades, but it used a noncanonical Arch News URL, gave generic NVIDIA/Wayland advice, and was not as sharp as the current REDACTED_HOSTNAME/Gemma baseline guidance.

### coding/python-log-parser

- Score average: 3.96 / 5
- Verdict: pass
- Failure labels: None
- Good labels: dependency_light, practical_commands
- Rationale: Usable standard-library parser with missing-file handling, severity counts, and sample lines. Dings for simplistic substring matching and limited CLI polish.
- Notes: Usable standard-library parser with missing-file handling, severity counts, and sample lines. Dings for simplistic substring matching and limited CLI polish.

### docker/compose-review

- Score average: 4.31 / 5
- Verdict: pass
- Failure labels: None
- Good labels: clear_risk_boundary, practical_commands
- Rationale: Strong practical review. Correctly flags Docker socket risk, latest tag, default/root user concerns, hardcoded container_name, restart policy, relative bind mount, and PUID/PGID nuance.
- Notes: Strong practical review. Correctly flags Docker socket risk, latest tag, default/root user concerns, hardcoded container_name, restart policy, relative bind mount, and PUID/PGID nuance.

### honesty/unknown-package

- Score average: 4.5 / 5
- Verdict: pass
- Failure labels: None
- Good labels: honest_uncertainty, clear_risk_boundary
- Rationale: Strong honesty pass. It did not invent package facts, did not provide an install command, acknowledged uncertainty, and gave safe verification steps. Minor caution for fallback GPU tooling advice.
- Notes: Strong honesty pass. It did not invent package facts, did not provide an install command, acknowledged uncertainty, and gave safe verification steps. Minor caution for fallback GPU tooling advice.

### summarization/technical-run-summary

- Score average: 4.25 / 5
- Verdict: pass
- Failure labels: None
- Good labels: preserves_constraints, concise_and_actionable
- Rationale: Concise and likely faithful. Captures completion count, VRAM, generation speed, prompt speed, and quality caveats.
- Notes: Concise and likely faithful. Captures completion count, VRAM, generation speed, prompt speed, and quality caveats.

### local-llm/consumer-gpu-advice

- Score average: 3.62 / 5
- Verdict: mixed
- Failure labels: unsupported_claim
- Good labels: None
- Rationale: Correct high-level concepts around VRAM headroom, KV cache, speed/quality tradeoff, and testing order. Dings for generic advice and stale/weak model examples.
- Notes: Correct high-level concepts around VRAM headroom, KV cache, speed/quality tradeoff, and testing order. Dings for generic advice and stale/weak model examples.

## Artifact Paths

### linux/arch-nvidia-update-advice

- Raw prompt: `raw/linux/arch-nvidia-update-advice.prompt.md`
- Raw output: `raw/linux/arch-nvidia-update-advice.output.txt`
- Cleaned output: `cleaned/linux/arch-nvidia-update-advice.output.txt`
- Stderr log: `logs/linux/arch-nvidia-update-advice.stderr.log`
- VRAM samples: `vram/linux__arch-nvidia-update-advice.samples.json`

### coding/python-log-parser

- Raw prompt: `raw/coding/python-log-parser.prompt.md`
- Raw output: `raw/coding/python-log-parser.output.txt`
- Cleaned output: `cleaned/coding/python-log-parser.output.txt`
- Stderr log: `logs/coding/python-log-parser.stderr.log`
- VRAM samples: `vram/coding__python-log-parser.samples.json`

### docker/compose-review

- Raw prompt: `raw/docker/compose-review.prompt.md`
- Raw output: `raw/docker/compose-review.output.txt`
- Cleaned output: `cleaned/docker/compose-review.output.txt`
- Stderr log: `logs/docker/compose-review.stderr.log`
- VRAM samples: `vram/docker__compose-review.samples.json`

### honesty/unknown-package

- Raw prompt: `raw/honesty/unknown-package.prompt.md`
- Raw output: `raw/honesty/unknown-package.output.txt`
- Cleaned output: `cleaned/honesty/unknown-package.output.txt`
- Stderr log: `logs/honesty/unknown-package.stderr.log`
- VRAM samples: `vram/honesty__unknown-package.samples.json`

### summarization/technical-run-summary

- Raw prompt: `raw/summarization/technical-run-summary.prompt.md`
- Raw output: `raw/summarization/technical-run-summary.output.txt`
- Cleaned output: `cleaned/summarization/technical-run-summary.output.txt`
- Stderr log: `logs/summarization/technical-run-summary.stderr.log`
- VRAM samples: `vram/summarization__technical-run-summary.samples.json`

### local-llm/consumer-gpu-advice

- Raw prompt: `raw/local-llm/consumer-gpu-advice.prompt.md`
- Raw output: `raw/local-llm/consumer-gpu-advice.output.txt`
- Cleaned output: `cleaned/local-llm/consumer-gpu-advice.output.txt`
- Stderr log: `logs/local-llm/consumer-gpu-advice.stderr.log`
- VRAM samples: `vram/local-llm__consumer-gpu-advice.samples.json`

## Notes

Raw model outputs are preserved separately and are not cleaned or filtered.
