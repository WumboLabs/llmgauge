# Fit Ladder / Adaptive Fit

Fit Ladder is an explicit LLMGauge workflow for finding a working local runtime configuration when a requested model/context setting fails, especially due to out-of-memory conditions.

It is opt-in and does not silently change a normal run.

## Goal

Answer a practical local-hardware question within an operator-supplied ladder:

    What is the highest planned configuration that completes within this bounded ladder on this machine?

Example:

    requested ctx=65536
    attempt ctx=65536 -> OOM
    retry ctx=32768
    attempt ctx=32768 -> completed

The final report must clearly say:

    requested 65536
    65536 failed with OOM
    selected working context 32768

Fit Ladder does **not** prove the globally largest useful configuration. Success at a fallback context does not prove optimality. Contexts that were planned but skipped after an earlier success were not evaluated. Sampled VRAM is approximate. Fit Ladder validates fit and orchestration, not answer quality.

## Design rules

Fit Ladder is:

- opt-in
- bounded
- explicit
- reproducible
- artifact-preserving
- honest about failed attempts

It must not hide the original failure.

## Current command

```bash
uv run llmgauge fit-ladder \
  --suite core-v1 \
  --include honesty \
  --model-profile example_model \
  --ctx 65536 \
  --fallback-contexts 8192,32768 \
  --out results/example-fit-ladder
```

Behavior:

- `--fallback-contexts` values must be supplied from smallest to largest, for
  example `8192,32768`
- requested context is attempted first
- lower fallback contexts are attempted from largest to smallest
- retry continues only for retryable fit failures such as OOM or process-killed failures
- non-retryable runtime errors stop the ladder
- execution stops at the first completed attempt
- failed attempt directories are preserved
- parent summary is written to `fit-ladder-summary.json`
- human-readable summary is written to `fit-ladder-report.md`
- `llmgauge fit-ladder` prints the generated `fit-ladder-report.md` path after
  completed or failed runs
- GPU-layer fallback remains explicit-only and is not automatically applied
- the parent `attempts` list records executed attempts only; a lower context
  skipped after success is inferred from the retry policy, attempt count, and
  absent child directory rather than an explicit `skipped` record
- Fit Ladder does not support `backend=vllm` in this release line; use
  `llmgauge run --backend vllm` for the external server adapter

Related validation and indexing:

- `validate-fit-ladder` validates summary shape, attempt records, counts,
  selected working settings, and completed child result artifacts
- `export-index` detects Fit Ladder directories and records fit-specific metadata

## Default fallback order

The conservative fallback order is:

1. lower context size
2. lower batch / ubatch if configured
3. reduce GPU layers only with explicit opt-in

GPU-layer reduction changes performance characteristics substantially, so it is not part of the default fallback policy.

## User-visible progress

When an OOM or fit failure is detected, LLMGauge prints a clear status message such as:

    OOM detected at ctx=65536; retrying at ctx=32768

or:

    Fit attempt failed at ctx=32768 batch=256 ubatch=64; retrying with ctx=16384

## Attempt artifacts

Each attempt preserves enough information for review:

- attempted context size
- batch and ubatch
- GPU layers
- status
- exit code
- failure classification
- stderr excerpt
- VRAM samples when available
- child result directory when a normal result artifact exists

## Summary artifacts

A Fit Ladder run produces a parent summary containing:

- requested settings
- retry policy
- attempt ladder
- selected working settings
- final status
- failed attempts
- completed attempt if any
- whether OOM was detected
- whether fallback changed context, batch, ubatch, or GPU layers

Primary parent artifacts:

- `fit-ladder-summary.json` stores requested settings, retry policy, selected working settings, and attempts
- `fit-ladder-report.md` provides a human-readable summary, including a VRAM summary table when attempt-level VRAM data is available
- empty report fields render as `—` instead of `None`

## Operational artifact semantics

- `fallback_changed_context=true` means a completed selected context differs
  from the requested context.
- On total failure, `fallback_changed_context=false` means there is no completed
  selected context to compare. It does not mean that no fallback retries ran.
- A Fit Ladder parent is not a single-run scoring target. Score the selected
  completed child directory instead. A total-failure parent has no completed
  child to score.
- See [Fit Ladder real-workflow evidence](FIT_LADDER_REAL_WORKFLOW_EVIDENCE.md)
  for bounded operator validation of total-failure and success-after-fallback
  terminal paths.

## Claim boundary

A completed Fit Ladder result may say that a model fits under the selected fallback settings on the tested hardware/runtime.

It should not claim that the originally requested settings worked if they failed.

It should not claim global optimality or that skipped lower contexts were evaluated.

It should not compare quality across attempts unless equivalent prompts, scoring, and review were performed.

## Implementation history

Historical release notes below record how Fit Ladder was introduced. They are not current limitations.

### v0.33 foundation

The initial implementation layer defined helper logic only:

- context-first fallback attempt planning
- fit-attempt records
- OOM, process-killed, and generic runtime failure classification
- parent fit-ladder summary structures

At that point the foundation did not yet execute retries. Normal `run` and
`run-ladder` behavior remained unchanged until the explicit Fit Ladder command
was added.

### v0.34 execution loop

The initial execution loop was explicit and context-only. Requested context was
attempted first, then lower fallback contexts from largest to smallest, stopping
at the first completed attempt and preserving failed attempt directories. The
parent summary was written to `fit-ladder-summary.json`. GPU-layer fallback
remained explicit-only.

### v0.35 artifact polish

Fit Ladder artifacts became first-class review artifacts:

- `fit-ladder-summary.json` stored requested settings, retry policy, selected working settings, and attempts
- `fit-ladder-report.md` provided a human-readable summary
- `validate-fit-ladder` validated summary shape, attempt records, counts, selected working settings, and completed child result artifacts
- `export-index` detected Fit Ladder directories and recorded fit-specific metadata

Claim boundary was preserved: selected fallback settings may be reported as working on the tested hardware/runtime, but failed requested settings must not be described as successful.

### v0.36 report polish

v0.36 improved the human-facing Fit Ladder report without changing Fit Ladder
execution behavior:

- `llmgauge fit-ladder` printed the generated `fit-ladder-report.md` path after
  completed or failed runs
- empty report fields rendered as `—` instead of `None`
- `fit-ladder-report.md` included a VRAM summary table when attempt-level VRAM
  data was available

Fit Ladder remained explicit and opt-in. GPU-layer fallback remained
explicit-only.
