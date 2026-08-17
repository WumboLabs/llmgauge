# Bundle 1 Qualification

This document pins the official EleutherAI `lm-evaluation-harness` identities
used by LLMGauge Bundle 1. Qualification is computed at report and inspection
time from imported source-backed facts. It is not written into
`external-benchmark/evidence.json`.

LLMGauge remains read-only. It imports already-produced lm-eval results. It
does not execute generated code, run models, download weights or datasets, add
lm-eval as a runtime dependency, or contact a network while importing,
validating, or reporting.

## Pin

| Field | Value |
|---|---|
| Qualification ID | `llmgauge.bundle1.v0` |
| Qualification version | `0.1.0` |
| Harness family | `lm_eval` |
| Repository | https://github.com/EleutherAI/lm-evaluation-harness |
| Tag | `v0.4.12` |
| Commit | `6d642546f4688648fced259eb3302efd36ece5af` |
| Qualification date | 2026-08-16 |

This is a versioned pin, not floating `latest`. The GitHub `v0.4.12` tag object
resolves to that commit. Display names are not identities.

Official isolated `v0.4.12` writer output uses `git describe --always`,
which emits `v0.4.10-81-g6d642546` at this commit. Pin matching accepts
that describe form when the abbreviated hash prefixes the pinned
commit. Official group aggregates also emit a `sample_count` object
beside `sample_len`; both are writer metadata, not native metrics.
Stderr values may be the string `N/A` when bootstrap is disabled.
Official MMLU `group_subtasks` lists expanded `mmlu_*` subject IDs, not
the YAML tags such as `mmlu_stem_tasks`. HumanEval and MBPP cannot emit
official pass@1 without upstream generated-code execution.

## Fail-closed statuses

Each intended member is independently:

- `qualified` when the exact official identity and contract match;
- `unqualified` when that official identity is absent, including lookalike
  tasks such as `mmlu_pro`, `mmlu_generative`, `truthfulqa_mc1`, `gsm8k_cot`,
  `humaneval_instruct`, or `mbpp_plus`;
- `conflicting` when the official identity is present but dataset, split,
  output type, pinned few-shot, version, required native metrics, or official
  group composition disagree.

Overall Bundle 1 status is `qualified` only when all eight members are
qualified. Any conflicting member makes the overall status `conflicting`.
Generic lm-eval import remains valid when a result is not Bundle 1-qualified.

Dataset revisions are generally unpinned in the official task YAML at this
tag. Absent revision is recorded as unavailable; it is not guessed.

## Members

### MMLU

- Official identity: group `mmlu` → subgroups `mmlu_stem`, `mmlu_other`,
  `mmlu_social_sciences`, `mmlu_humanities` → the 57 default `mmlu_*`
  subjects from `lm_eval/tasks/mmlu/_generate_configs.py`.
- Dataset: `cais/mmlu` with per-subject `dataset_name`.
- Split: `test`. Output type: `multiple_choice`.
- Native metric: `acc`. Group aggregation: mean weighted by size.
- Few-shot is not pinned in the task YAML. Invocation `n-shot` must be
  recorded when present; it is not invented.
- Distinct from `mmlu_continuation`, `mmlu_generative`, Flan variants, and
  `mmlu_pro`. A two-subject grouped fixture remains valid generic import and
  is not Bundle 1-qualified.

### ARC Challenge

- Official identity: task `arc_challenge`.
- Dataset: `allenai/ai2_arc` / `ARC-Challenge`.
- Split: `test`. Output type: `multiple_choice`.
- Native metrics: `acc` and `acc_norm`.
- Distinct from `arc_easy` and `arc_challenge_chat`.

### HellaSwag

- Official identity: task `hellaswag`.
- Dataset: `Rowan/hellaswag`.
- Split: `validation`. Output type: `multiple_choice`.
- Native metrics: `acc` and `acc_norm`, preserved separately.

### WinoGrande

- Official identity: task `winogrande`.
- Dataset: `allenai/winogrande` / `winogrande_xl`.
- Split: `validation`. Output type: `multiple_choice`.
- Native metric: `acc`.

### TruthfulQA MC2

- Official identity: task `truthfulqa_mc2`.
- Dataset: `truthfulqa/truthful_qa` / `multiple_choice`.
- Split: `validation`. Output type: `multiple_choice`.
- Pinned few-shot: `0`. Task version: `3.0`.
- Native metric: `acc`.
- Distinct from `truthfulqa_mc1` and `truthfulqa_gen`.

### GSM8K

- Official identity: task `gsm8k`.
- Dataset: `openai/gsm8k` / `main`.
- Split: `test`. Output type: `generate_until`.
- Pinned few-shot: `5`. Task version: `3.0`.
- Native metric: `exact_match`, including official `strict-match` and
  `flexible-extract` filters when present.
- Distinct from `gsm8k_cot` and `gsm8k_cot_llama`.

### HumanEval

- Official identity: task `humaneval`.
- Dataset: `openai/openai_humaneval`.
- Split: `test`. Output type: `generate_until`.
- Pinned few-shot: `0`.
- Native metric: `pass@1` / `pass_at_1` / `pass_at_k` as emitted by the
  official `utils.pass_at_k` wrapper.
- Official YAML sets `unsafe_code: true`. Upstream evaluation executes
  generated Python through HuggingFace `code_eval` and requires
  `--confirm_run_unsafe_code`.
- LLMGauge may import already-produced results only. It never executes
  candidate or generated code and never invokes benchmark test execution.
- Distinct from `humaneval_64`, `humaneval_instruct`, and `humaneval_plus`.

### MBPP

- Official identity: task `mbpp`.
- Dataset: `google-research-datasets/mbpp` / `full`.
- Split: `test`. Output type: `generate_until`.
- Pinned few-shot: `3`.
- Native metric: `pass@1` / `pass_at_1` as emitted by official
  `utils.pass_at_1`.
- Official YAML sets `unsafe_code: true` and uses the same `code_eval`
  execution path. LLMGauge remains read-only.
- Distinct from `mbpp_plus` and `mbpp_instruct`.

## Report

`llmgauge benchmark report RESULT_DIR` writes regenerable
`external-benchmark/report.md`. The report summarizes imported identities,
native metrics, and Bundle 1 qualification. It does not invent a universal
score, cross-benchmark ranking, metric equivalence, missing-metadata repair,
or model recommendation.

Native `score`, native `report`, `compare`, export-index, and public-export
paths continue to reject imported external-benchmark results. Use
`llmgauge benchmark report` for this result class.

See [the interoperability contract](EXTERNAL_BENCHMARK_LOCALMAXXING_INTEROP_CONTRACT.md)
for authority and isolation rules.
