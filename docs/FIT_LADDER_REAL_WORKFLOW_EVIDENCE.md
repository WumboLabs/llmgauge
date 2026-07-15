# Fit Ladder Real-Workflow Evidence

## Status and scope

Recorded: **2026-07-15**

This is a documentation-only evidence record for two completed, bounded Fit
Ladder parent executions performed in separate milestones. It records real
operator validation of the two principal terminal paths:

1. all planned attempts fail;
2. a failed attempt triggers a lower-context retry, that retry completes, and
   the ladder stops.

Both executions used one host (WumboJetsII, NVIDIA GeForce RTX 5070 12 GB), one
llama.cpp binary identity (`9672 (74ade5274)`), two local model profiles, and one
prompt (`tool-honesty/fake-tool-resistance`). The private result artifacts remain
under ignored `results/` directories. This record validates orchestration and
evidence handling; it does not evaluate either model's answer quality.

## What Fit Ladder is validating

The reviewed workflows exercise:

- deterministic context planning;
- retryable failure classification;
- preservation of every executed child attempt;
- automatic context fallback;
- selection of the first completed child;
- termination after all planned contexts fail;
- independent parent and child validation;
- Fit Ladder representation in `export-index`;
- rejection of a Fit Ladder parent as a scoring target;
- human-readable parent and child reports;
- process and GPU cleanup after completion or failure.

Structural validation establishes artifact consistency, not answer correctness,
quality, or publication readiness.

## Shared workflow rules

- Supply `--fallback-contexts` values to the CLI in ascending order, from
  smallest to largest. Both accepted inputs followed this rule.
- Execution starts at the requested context, then tries lower fallback contexts
  from highest to lowest.
- Only context changed within either parent. Batch, ubatch, GPU layers,
  generation settings, flash-attention mode, and reasoning mode remained
  constant within that parent.
- GPU-layer fallback was not used; it remains explicit-only.
- Neither workflow was a broad batch, ubatch, KV-type, or GPU-layer parameter
  sweep.
- Private results and review material remained ignored and untracked.
- Failed child attempts were retained and were never deleted or overwritten.

## Evidence record 1: total failure

### Identity and bounded plan

- Parent: `results/2026-07-15-fit-ladder-e2e-qwen36-35b-a3b-001`
- Workflow classification: `validated_with_caveats`
- Model profile: `qwen3_6_35b_a3b_ud_iq2_m`
- Model family and quantization: Qwen3.6-35B-A3B, UD-IQ2_M GGUF
- Public short model fingerprint: `sha256:2be7ef1ed7e1af8b`
- Runtime: llama.cpp `9672 (74ade5274)`
- Host: WumboJetsII, NVIDIA GeForce RTX 5070 12 GB
- Prompt: `tool-honesty/fake-tool-resistance`
- CLI fallback input: `8192,16384`
- Planned and executed order: `32768 → 16384 → 8192`
- Constants: batch 256, ubatch 64, GPU layers 999, flash attention `auto`,
  reasoning off, max tokens 256, temperature 0.2, top-p 0.95

### Attempts and terminal state

| Attempt | Context | Status | Failure class | Retryable | Exit | Approx. peak VRAM | Approx. headroom |
|---|---:|---|---|---|---:|---:|---:|
| `attempt-01` | 32768 | failed | `oom` | true | -11 | 11751 MiB | 476 MiB |
| `attempt-02` | 16384 | failed | `oom` | true | -11 | 11751 MiB | 476 MiB |
| `attempt-03` | 8192 | failed | `oom` | true | -11 | 11751 MiB | 476 MiB |

All three attempts failed during CUDA KV-cache allocation. The first two
classified OOM failures caused automatic transitions to the next planned
context. The third exhausted the plan. The parent recorded:

- `final_status=failed`;
- attempted/completed/failed counts of `3 / 0 / 3`;
- `selected_working_settings=null` and no selected context;
- `oom_detected=true`;
- `fallback_changed_context=false`.

Here, `fallback_changed_context=false` does **not** mean that no retries
occurred. The field asks whether a completed selected context differs from the
requested context. No completed context existed to compare.

### Artifact behavior

- `validate-fit-ladder` accepted the parent.
- `validate-result` independently accepted all three failed child artifacts as
  structurally valid failed runs.
- `export-index --validate` identified `artifact_type=fit_ladder`, reported no
  completed attempt, reported failed attempts and detected OOM, emitted
  `selected_ctx=null`, and returned valid status.
- Scoring the parent was rejected with guidance to use a child attempt result
  directory. No completed child existed to score.
- Parent and child reports retained the requested settings, attempt sequence,
  failure classifications, diagnostic evidence, and sampled VRAM summaries.
- The llama.cpp process exited and GPU use returned near its pre-run display
  baseline. No failed attempt was removed.

## Evidence record 2: success after fallback

### Identity and bounded plan

- Parent: `results/2026-07-15-fit-ladder-success-fallback-qwen3-14b-001`
- Workflow classification: `validated`
- Model profile: `qwen3_14b_q4_k_m`
- Model family and quantization: Qwen3 14B, Q4_K_M GGUF
- Public short model fingerprint: `sha256:712c0791d5124d3d`
- Runtime: llama.cpp `9672 (74ade5274)`
- Host: WumboJetsII, NVIDIA GeForce RTX 5070 12 GB
- Prompt: `tool-honesty/fake-tool-resistance`
- CLI fallback input: `4096,8192`
- Planned order: `32768 → 8192 → 4096`
- Constants: batch 256, ubatch 64, GPU layers 999, flash attention `auto`,
  default KV types, reasoning off, max tokens 256, temperature 0.2, top-p 0.95

Before this execution, the operator closed Brave and Obsidian/electron to lower
the display baseline safely; the compositor remained running. Sampled GPU use
at ladder start was approximately 361 MiB. This baseline is part of the bounded
observation, not a generalized fit requirement.

### Attempts and terminal state

| Attempt | Context | Status | Failure class | Retryable | Exit | Approx. peak VRAM | Approx. headroom |
|---|---:|---|---|---|---:|---:|---:|
| `attempt-01` | 32768 | failed | `oom` | true | -11 | 8693 MiB | 3534 MiB |
| `attempt-02` | 8192 | completed | — | false | 0 | 10029 MiB | 2198 MiB |
| planned `attempt-03` | 4096 | not executed | n/a | n/a | n/a | n/a | n/a |

The first attempt encountered genuine CUDA OOM during KV-cache allocation; the
failed allocation was approximately 5120 MiB. The ladder classified it as
retryable and automatically moved to 8192. The second child completed with one
of one prompt completed, non-empty cleaned output, and no observed harness or
template failure. Manual model-quality scoring was intentionally not performed.

The parent recorded:

- `final_status=completed_with_fallback`;
- attempted/completed/failed counts of `2 / 1 / 1`;
- selected `attempt-02` at context 8192;
- requested context 32768;
- `fallback_changed_context=true`;
- `oom_detected=true`;
- `stop_on_first_completed=true`.

The planned 4096 context did not execute, and no `attempt-03-ctx-4096`
directory was created. This proves stop-on-first-success for this execution.

### Artifact behavior

- `validate-fit-ladder` accepted the parent.
- `validate-result` independently accepted the failed child and the selected
  completed child.
- The selected child reference resolved to `attempt-02-ctx-8192`.
- `export-index --validate` identified `artifact_type=fit_ladder`, selected
  context 8192, both completed and failed attempts, changed context, detected
  OOM, and valid status.
- Scoring the parent was rejected with child-directory guidance. `score --init`
  admitted the selected child as a normal single-run target; the temporary
  template was then removed, leaving the child unscored.
- The llama.cpp process exited and GPU use returned near the reduced display
  baseline. The failed child remained preserved.

## Side-by-side terminal paths

This table compares workflow semantics only. The resource observations above
remain separate and are not a cross-model performance comparison.

| Workflow field | Total failure | Success after fallback |
|---|---|---|
| Parent final status | `failed` | `completed_with_fallback` |
| Requested context | 32768 | 32768 |
| Planned lower contexts | 16384, 8192 | 8192, 4096 |
| Executed attempts | 3 | 2 |
| Failed attempts | 3 | 1 |
| Completed attempts | 0 | 1 |
| Selected context | none | 8192 |
| `fallback_changed_context` | false; no selected completed context | true; selected 8192 differs from requested 32768 |
| OOM detected | true | true |
| Stop condition | planned contexts exhausted | first completed child selected |
| Parent validation | valid | valid |
| Child validation | all 3 failed children valid | failed and completed children valid |
| Export-index status | valid; failed only; `selected_ctx=null` | valid; failed and completed; `selected_ctx=8192` |
| Scoring target behavior | parent rejected; no completed child | parent rejected; selected child admitted |

## Product-validation findings

The two real operator workflows now validate, within their stated boundaries:

- retry after a classified CUDA OOM;
- preservation of failed attempt artifacts;
- honest exhaustion after all planned contexts fail;
- selection and reference of a completed child;
- stopping after the first completed child;
- non-execution of a skipped lower fallback;
- structurally valid failed child artifacts;
- a structurally valid successful child artifact;
- valid parents for both terminal paths;
- export-index representation of both terminal paths;
- parent scoring rejection and completed-child scoring admission;
- process exit and return of sampled GPU use near the applicable baseline.

## Operator-usability findings

- `--dry-run` displays the planned execution order without launching llama.cpp
  or creating attempt directories.
- Parent output names and `attempt-NN-ctx-NNNN` child names are predictable and
  discoverable.
- Console messages clearly identify OOM and the next context.
- The parent-scoring error is actionable and directs the operator to a child.
- `selected_working_settings.attempt_id` and the selected context make the
  completed child easy to locate.
- Planned but skipped contexts are implicit in policy, counts, and absent
  directories; they are not explicit attempt records.
- Requiring ascending `--fallback-contexts` input can be counterintuitive when
  the displayed execution order is descending.
- Private stderr excerpts can contain private absolute paths. They remain local
  diagnostic evidence and require review before any publication.

## Caveats

- The current schema has no explicit `skipped` attempt object. A context skipped
  after success is inferred from the retry policy, executed-attempt count, stop
  policy, and absent child directory.
- A completed child report can render finish reason as unavailable even when
  status and exit evidence show completion.
- VRAM values are sampled and approximate.
- Fit depends on the desktop/display VRAM baseline as well as model and runtime
  settings.
- `fallback_changed_context=false` on total failure can be mistaken for “no
  retry”; it means no completed selected context differed from the request.
- Local profile build metadata can lag the identity reported by the executable;
  the observed binary identity governs these records.
- Neither run establishes answer quality or an optimal context.

## Claim boundaries

These records cover two models, not a support matrix; one host; one llama.cpp
binary identity; one prompt; and two bounded ladders. Specifically:

- A high-context OOM does not prove universal incompatibility for that model.
- A lower-context completion does not prove that context is optimal.
- Skipped contexts were not evaluated.
- Sampled resource evidence is approximate and baseline-dependent.
- The evidence validates orchestration, preservation, validation, indexing,
  reporting, score-target routing, and cleanup—not answer quality.
- No cross-model ranking or performance comparison is supported.
- No vLLM comparison was performed or inferred.
- Private artifacts remain canonical local evidence and require human review
  before any public use.
