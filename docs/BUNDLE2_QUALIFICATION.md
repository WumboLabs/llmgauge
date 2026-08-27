# Bundle 2 Qualification

This document pins the official EleutherAI `lm-evaluation-harness` identities
used by LLMGauge Bundle 2, mirroring [Bundle 1 Qualification](BUNDLE1_QUALIFICATION.md).
Qualification is computed at report and inspection time from imported
source-backed facts. It is not written into `external-benchmark/evidence.json`.

LLMGauge remains read-only. It imports already-produced lm-eval results. It
does not execute generated code, run models, download weights or datasets,
add lm-eval as a runtime dependency, or contact a network while importing,
validating, or reporting.

## Pin

| Field | Value |
|---|---|
| Qualification ID | `llmgauge.bundle2.v0` |
| Qualification version | `0.1.0` |
| Harness family | `lm_eval` |
| Repository | https://github.com/EleutherAI/lm-evaluation-harness |
| Tag | `v0.4.12` |
| Commit | `6d642546f4688648fced259eb3302efd36ece5af` |
| Qualification date | 2026-08-26 |

The same versioned pin as Bundle 1; v0.4.12 remains the latest official
release at qualification time. Pin-matching rules (including official
`git describe` forms) are identical to Bundle 1.

Overall Bundle 2 status is `qualified` only when all five members are
qualified. Any conflicting member makes the overall status `conflicting`.
Generic lm-eval import remains valid when a result is not Bundle 2-qualified.

## Members

### MMLU-Pro

- Official identity: group `mmlu_pro` → the 14 default subjects from
  `lm_eval/tasks/mmlu_pro/_mmlu_pro.yaml` (`mmlu_pro_biology` through
  `mmlu_pro_psychology`). Group YAML version `2.0`; subject template version
  `3.1`.
- Dataset: `TIGER-Lab/MMLU-Pro`. Split: `test`; few-shot split `validation`
  with pinned `num_fewshot: 5`.
- Output type: `generate_until`. Native metric: `exact_match` under the
  official `custom-extract` filter; group aggregation is mean weighted by
  size.
- The `custom-extract` filter is material: a result whose aggregate or
  subjects carry only a plain `exact_match` suffix is `conflicting`, not
  qualified.
- Distinct from plain `mmlu` and every Flan/generative lookalike.

### GPQA (n-shot)

Three independent members — `gpqa_diamond_n_shot`, `gpqa_extended_n_shot`,
`gpqa_main_n_shot`:

- Dataset: `Idavidrein/gpqa` per variant `dataset_name`
  (`gpqa_diamond`, `gpqa_extended`, `gpqa_main`). Task version `2.2`.
- Output type: `multiple_choice`. Native metrics: `acc` and `acc_norm`,
  preserved separately. Few-shot is not pinned in the task YAML at this tag;
  invocation `n-shot` is recorded when present and not invented.
- **Gated dataset**: upstream requires accepting the dataset terms with an
  operator Hugging Face token before lm-eval can run. LLMGauge imports
  already-produced results only and never downloads the dataset; reproduction
  of a qualifying run is possible only for operators who have accepted those
  terms. This boundary is disclosed, not hidden.
- The upstream dataset has only a `train` split (`test_split` is null);
  split facts are recorded as observed and are not guessed.
- Distinct identities: every `cot_zeroshot`, `cot_n_shot`, `zeroshot`, and
  `generative` variant is a lookalike that does not qualify any n-shot
  member.

### IFEval

- Official identity: task `ifeval` (no group). Task version `4.0`.
- Dataset: `google/IFEval` (public). Split: `train` — the official test data
  lives in the train split; this is pinned verbatim.
- Output type: `generate_until`; pinned few-shot `0`; temperature `0.0`;
  `max_gen_toks` `1280`; no stop strings.
- Native metrics: `prompt_level_strict_acc`, `inst_level_strict_acc`,
  `prompt_level_loose_acc`, `inst_level_loose_acc`. All four are required for
  `qualified` status; strict and loose are never merged, renamed, or averaged
  into one number by LLMGauge.
- Upstream scoring executes deterministic instruction-string checks inside
  lm-eval; it does not execute generated content. LLMGauge imports the
  already-produced numbers only.

## Report

Qualification is exposed through `llmgauge.core.bundle2.qualify_bundle2`
using the same member-status model as Bundle 1 (`qualified`, `unqualified`,
`conflicting`). A qualified identity is not a quality, safety, or ranking
claim. An imported-but-unqualified result remains valid generic lm-eval
evidence. A conflicting identity is never reinterpreted as the official
member.

Rendering Bundle 2 alongside Bundle 1 in `benchmark report` output is a
separately admitted presentation decision; this document fixes only the
qualification semantics.
