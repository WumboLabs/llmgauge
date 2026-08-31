# LLAMA.CPP STEADY-STATE VRAM FEASIBILITY

## Status

**DEFERRED — CURRENT NATIVE EXECUTION CANNOT ESTABLISH THE REQUIRED
POST-LOAD / POST-WARMUP / PRE-TEARDOWN INTERVAL**

The current native `llama-cli` process-per-request execution does not preserve
enough evidence to admit `llmgauge.metric.v1.steady_state_vram` under the
accepted Area 4 definition. This is an architecture and feasibility milestone
only: no production steady-state VRAM collection is implemented, and no
schema, result, fingerprint, runner, or behavior change is made here.

The accepted definition
([RUNTIME_NEUTRAL_METRICS_FAILURE_TAXONOMY_CONTRACT.md](RUNTIME_NEUTRAL_METRICS_FAILURE_TAXONOMY_CONTRACT.md)):

> `llmgauge.metric.v1.steady_state_vram` is the median absolute used memory in
> `MiB` for that same device over an explicit post-load, post-warmup steady
> interval; it is unavailable without that interval and at least one valid
> sample.

The metric requires an explicit interval that is **post-load**, **post-warmup**,
and bounded before **teardown**. Each boundary must be established from actual
preserved evidence, not from a stability heuristic, a percentage of wall time,
or guessed phase completion. This milestone audits each boundary against the
current native runner and its preserved telemetry.

## Metric authority and non-negotiables

- `llmgauge.metric.v1.steady_state_vram` — median absolute used memory in MiB
  for one device over an explicit post-load, post-warmup steady interval.
- Absolute used memory, not baseline delta; one record per device; no summing
  of devices.
- Missing interval or samples => `unavailable`, never zero.
- No stability heuristic may substitute for a semantic lifecycle boundary.
- `no warmup record means the run is not described as warmed` (contract,
  "Warmup, repetition, aggregation, and comparison").

## Current native execution boundary

The native runner is `src/llmgauge/runners/llama_cpp.py`
(`run_llama_cpp`). It:

1. optionally takes one pre-launch VRAM sample (`_capture_vram_sample`);
2. records `started_at = time.monotonic()` immediately before
   `subprocess.Popen`;
3. launches `llama-cli --single-turn` with `stdout=subprocess.PIPE,
   stderr=subprocess.PIPE, text=True`;
4. loops on `process.communicate(timeout=poll_seconds)` until the child exits
   or the per-turn deadline is reached (killing on timeout); each
   `TimeoutExpired` triggers one VRAM sample while the process is alive;
5. after `communicate()` returns, takes **one final VRAM sample** (post-exit);
6. records `elapsed_seconds = time.monotonic() - started_at`.

So the preserved sample stream per prompt/attempt is:

```
[pre-launch sample?] [alive-window samples...] [post-exit sample]
```

with **no per-sample phase label**. The pre-launch and post-exit samples are
distinguishable only by construction of the sampling loop, not by any field in
the preserved record.

## Preserved VRAM sample schema

Each sample (schema `llmgauge.vram.samples.v0`, artifact `vram/*.samples.json`)
carries:

| Field | Value |
|---|---|
| `timestamp_utc` | wall-clock UTC ISO, **second precision** (`replace(microsecond=0)`) |
| `gpu_index` | device index |
| `gpu_name` | device name |
| `used_mib` | absolute device used memory |
| `total_mib` | device total memory |

The sample record has **no**:

- monotonic timestamp;
- offset from request start;
- process identity;
- sample sequence number;
- sampler start / sampler stop;
- explicit phase (pre-load / loading / post-load / warmup / generation /
  post-exit);
- relationship to process launch or model load.

The only timing relationship preserved is the ordering of samples in the list
(earliest to latest), and the boundary string
`process_launch_to_completion_sampling_window` on the derived peak-VRAM metric
record.

## Sampler lifecycle audit

| Lifecycle event | Directly observed by LLMGauge? | Preserved evidence |
|---|---|---|
| Sampler setup | yes (capture flag) | none beyond samples list |
| First sample | yes | pre-launch sample, wall-clock only |
| Request-start timestamp | yes | `started_at` (monotonic), `elapsed_seconds` |
| `Popen` / process launch | yes | monotonic anchor only, not in sample stream |
| Model load | no | llama.cpp diagnostics on stderr (duration only) |
| Prompt processing | no | llama.cpp diagnostics on stderr (duration only) |
| Generation | no | llama.cpp diagnostics on stderr (duration only) |
| Process completion | yes | `communicate()` return; monotonic elapsed |
| Final sample | yes | post-exit sample, wall-clock only |
| Sampler teardown | yes | none beyond samples list |

LLMGauge never observes model-load completion, warmup completion, or the
generation-phase boundary as an event with a timestamp alignable to the VRAM
sample stream. Wall-clock and monotonic clocks are never bridged in the
preserved artifact, so a sample timestamp cannot be deterministically related
to `started_at` or to process exit.

## Post-load boundary — REJECTED

Candidate: llama.cpp printed `load time` (preserved as
`llama_cpp_timing.load_time_seconds` in `native/*.execution.json`).

Primary-source finding (installed binary at commit `0d9ceae1e`, source
`<operator-local-llama.cpp-sm120-upgrade>`, proven identical by version string):

- `src/llama.cpp:336-337` starts a `time_meas tm(model->t_load_us)` timer at
  model load start (`model->t_start_us`).
- `src/llama-context.cpp:729-731` — in `llama_context::synchronize()`, on the
  **first evaluation**:

  ```cpp
  // get a more accurate load time, upon first eval
  if (n_queued_tokens > 0 && !has_evaluated_once) {
      t_load_us = ggml_time_us() - t_start_us;
      has_evaluated_once = true;
  }
  ```

  The printed `load time` (`llama_perf_context_print`, `llama-context.cpp:4164`)
  is therefore `model-load-start → first-eval-end`, **not** a
  `weight-load-start → model-ready` boundary. It includes the first prompt
  evaluation.

- Even if the end boundary were load-completion, it is a **duration on
  llama.cpp's own clock** with no wall-clock or monotonic anchor shared with
  the VRAM sample stream. It cannot select which preserved samples are
  post-load.

This is consistent with the prior Area 4 milestone that deferred neutral
`model_load_time`: llama.cpp's `load time` was not proven equal to the neutral
boundary. It is **REJECTED** as a sample-selection boundary for steady-state
VRAM.

There is no other post-load candidate: no LLMGauge-observed runtime state
marks load completion, and the process lifecycle alone does not locate model
load within the sample stream.

## Warmup boundary — REJECTED (no warmup exists)

Current native execution performs **no explicit warmup**:

- `run_llama_cpp` launches one `llama-cli --single-turn` process per prompt;
  the model is loaded by that process and the process exits after the single
  turn.
- There is no warmup request, no warmup measurement kind in the native path,
  no retained process/model state across requests, and no accepted warm/cache
  indicator in the native execution evidence (`workload.cache_state` is
  `unknown`).
- A new request starts a new process that reloads the model from scratch.
  A prior process's activity does not warm the next process.

The contract states: "No warmup record means the run is not described as
warmed." The native run has no warmup record. There is therefore **no admitted
post-warmup boundary**, and no interval can be claimed post-warmup.

The only warmup-capable path in the codebase is `localmaxxing` (llama-bench:
one warmup + five measured repetitions), which is a separate protocol with its
own artifact and measurement semantics, not the native single-turn result path.

## End boundary (pre-teardown) — REJECTED

- The final preserved sample is taken **after** `process.communicate()` returns
  (`llama_cpp.py:249-250`), i.e. after the child has exited. That sample can
  reflect memory already released at process teardown.
- No process-exit wall-clock timestamp is preserved; only monotonic
  `elapsed_seconds` is kept, and it is not bridged to the sample stream.
- There is no deterministic, evidence-based rule that excludes post-exit /
  teardown-contaminated samples from the preserved record.

Selecting "samples before process exit" would require either a preserved exit
timestamp aligned to samples (absent) or an inference from sample ordering
(the last sample is post-exit) that is not admitted evidence for a precise
interval end. **REJECTED.**

## Do not use a stability heuristic

A statistically flat-looking tail is not a semantic lifecycle boundary. All
forbidden V1 candidates from the milestone (variance threshold, coefficient of
variation, "three samples within X MiB", middle 50%, last 25%, samples after
peak, fixed settling delay, seconds-after-launch) are explicitly inapplicable:
none can establish that the selected interval is post-load, post-warmup, and
pre-teardown.

## Admission decision

**STEADY_STATE_VRAM_ADMISSION = DEFERRED**

Failure against the required admission list:

1. explicit post-load boundary — **missing** (llama.cpp `load time` is
   first-eval-end, unanchored; no other candidate);
2. explicit post-warmup boundary — **missing** (no warmup in native
   process-per-request execution);
3. explicit pre-teardown end boundary — **missing** (final sample is post-exit;
   no aligned exit timestamp);
4. timestamped device-scoped samples — **partial** (device-scoped wall-clock
   samples exist, but are not alignable to process lifecycle and carry no
   phase);
5. at least one sample can exist in the interval — **cannot be established**
   (no admitted interval);
6. interval belongs to the same execution/model residency — **not
   establishable** (no boundaries to define the interval);
7. no stability heuristic needed — **fails** (any candidate interval requires
   a forbidden heuristic);
8. calculation deterministically recomputable from preserved evidence —
   **fails** (selection depends on unrecorded boundary facts).

## Proven blocker

The current process-per-request `llama-cli` execution preserves device-scoped
wall-clock VRAM samples and monotonic request wall time, but nothing bridges
those clocks or labels any sample with model-load, warmup, generation, or
teardown phase. It has no warmup phase at all. A defensible steady-state
interval therefore cannot be selected from the preserved evidence without a
forbidden stability heuristic or invented phase boundary.

## Missing evidence (what a future implementation needs)

To admit `llmgauge.metric.v1.steady_state_vram` the preserved evidence must
include, per attempt:

- a **same-process warmup phase** with an explicit warmup boundary (or an
  accepted contract that a measured phase is warmed without one);
- a **post-load boundary** — either an LLMGauge-observed event with a
  timestamp shared with the sample clock, or a proven backend event whose end
  semantics equal weight-load-start → model-ready and that is timestamped on
  a clock bridged to the samples;
- a **post-warmup boundary**;
- a **pre-teardown end boundary** with an explicit process-exit timestamp on
  the sample clock;
- monotonic (or clock-bridged) per-sample timestamps with sub-second
  precision and explicit phase labels or sampler-window markers;
- per-attempt isolation so a later retry does not erase an earlier attempt's
  interval evidence.

## Smallest future architecture that could admit it

The smallest change that makes the metric admissible is a **persistent
same-process runtime** where the model stays resident across a warmup turn and
measured turns, e.g. an LLMGauge-owned `llama-server` backend (the same
server-backed route already recorded as the only TTFT-viable native path) or an
equivalent long-lived llama.cpp embedding:

1. launch one process (or connect to one server);
2. run an explicit warmup request in that process;
3. capture a warmup-completion boundary;
4. run measured requests in the same process (model remains resident);
5. sample VRAM on a clock shared with the request lifecycle, with phase labels
   (pre-load / post-load / post-warmup / measured / post-exit);
6. record an explicit process-exit/teardown timestamp on the same clock.

Such an architecture also enables the deferred TTFT (token-stream SSE) and
stronger placement observation, but it is a separate, substantial runtime
architecture change — it is **not** implemented here and requires a separate
accepted contract.

## No product-code change

No production code, schema, result, fingerprint, comparison, reporting, or
export behavior is changed by this milestone. Peak VRAM evidence and current
native timing/placement evidence remain exactly as previously accepted.
Historical results remain valid unchanged. This document and the ROADMAP entry
are architecture/feasibility records only.

## Implementation acceptance gates (future)

A later implementation of `llmgauge.metric.v1.steady_state_vram` may be
admitted only when all of the following hold:

1. Explicit post-load boundary, proven from evidence.
2. Explicit post-warmup boundary (or accepted warm state under a contract).
3. Explicit pre-teardown end boundary on the sample clock.
4. Timestamped device-scoped samples with monotonic/clock-bridged time.
5. At least one valid sample inside the admitted interval.
6. Same execution/model residency for the interval.
7. No stability heuristic used for boundary selection.
8. Deterministic recomputation from preserved evidence, with validator
   recomputation.
9. Per-attempt interval/samples/metric ownership across retries.
10. Absolute used memory, one record per device, no cross-device sum.
11. `unavailable` (never zero) when interval or samples are missing.
12. Exact evidence references, sample count, and interval disclosure.
13. Historical results unchanged; no new fingerprint version unless required
    and separately justified.
14. No device-global value presented as llama.cpp process memory.
15. Bounded real-model proof only after later human authorization.
