# LLMGauge Evaluation Budgets

This document records current output-budget guidance for LLMGauge evaluations.

These are practical defaults, not permanent benchmark rules.

## Why output budget matters

A result can complete successfully and validate structurally while still being hard to score if the model output is too short or cut off.

For scoring, the output needs enough room to show:

- instruction following
- factual honesty
- command correctness
- operational safety
- completeness
- recovery or rollback awareness
- uncertainty handling

## Current working defaults

| Run type | Recommended max tokens | Purpose |
|---|---:|---|
| Fast smoke test | 600-900 | Verify the model and runner work. Not enough for full scoring on most ops prompts. |
| Single-prompt scoring | 1600 | Minimum practical budget for normal ops prompts. |
| Full-suite scoring | 2048 | Safer default for scoring all normal prompt suites. |
| Long-context / agent-backend synthetic tasks | 2400-3200 | Use when the prompt expects multi-section analysis or long-context constraint retention. |

## Current recommendation

Use this for serious single-prompt scoring:

    --max-tokens 1600

Use this for full scoring runs unless there is a reason to shorten outputs:

    --max-tokens 2048

Use lower values only for quick smoke tests.

## Evidence from v0.16 smoke testing

Model profile:

    gemma4_12b_qat_q4

Model label:

    Gemma 4 12B IT QAT UD-Q4_K_XL

Environment:

    WumboJetsII
    NVIDIA RTX 5070 12GB
    llama.cpp backend
    installed llmgauge CLI

### 900-token smoke runs

The 900-token Linux and Docker ops outputs completed structurally, but appeared too short for comfortable scoring. They were useful for smoke testing but not ideal as public-quality examples.

### 1600-token extended runs

The 1600-token Linux and Docker runs produced scoreable outputs.

Linux extended run:

    results/v016-real-smoke/2026-06-16_23-04-58-gemma4-q4-linux-extended-001

Observed metrics:

    prompt_eval_tps: 1567.3
    generation_tps: 76.7
    status: completed
    validation: OK

Qualitative note:

    The answer ended cleanly, included Arch News, full system upgrade guidance, pre-checks, NVIDIA verification, post-update checks, rollback/recovery awareness, and uncertainty notes.

Docker extended run:

    results/v016-real-smoke/2026-06-16_23-05-13-gemma4-q4-docker-extended-001

Observed metrics:

    prompt_eval_tps: 1572.6
    generation_tps: 77.0
    status: completed
    validation: OK

Qualitative note:

    The answer ended cleanly and separated observation, diagnosis, action, and verification. It is scoreable, but command correctness and rollback advice should be scored critically.

## Scoring guidance

When scoring operational prompts, do not reward length by itself.

A longer answer is only better if it improves:

- correctness
- safety
- completeness
- specificity
- recoverability
- uncertainty handling

Penalize outputs that:

- recommend destructive rollback steps too casually
- invent command behavior
- use incorrect command syntax
- omit verification
- omit recovery paths
- end mid-list or mid-sentence
- satisfy structure but not substance

## Current suite-level guidance

| Suite | Suggested scoring budget |
|---|---:|
| core-v1 | 2048 |
| agent-backend-v1 | 2048 |
| context-v1 | prompt-dependent; usually 2400+ |

## Future LLMGauge work

Potential future schema fields:

    recommended_max_tokens

at suite level, category level, or prompt level.

Do not add these fields until more runs confirm stable per-prompt budget needs.
