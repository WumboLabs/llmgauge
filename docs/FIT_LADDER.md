# Fit Ladder / Adaptive Fit

Fit Ladder is a planned LLMGauge feature for finding a working local runtime configuration when a requested model/context setting fails, especially due to out-of-memory conditions.

This feature is not enabled by default and should not silently change a normal run.

## Goal

Answer a practical local-hardware question:

    What is the largest useful configuration this model can run on this machine?

Example:

    requested ctx=65536
    attempt ctx=65536 -> OOM
    retry ctx=32768
    attempt ctx=32768 -> completed

The final report must clearly say:

    requested 65536
    65536 failed with OOM
    selected working context 32768

## Design rules

Fit Ladder should be:

- opt-in
- bounded
- explicit
- reproducible
- artifact-preserving
- honest about failed attempts

It must not hide the original failure.

## Default fallback order

The conservative fallback order should be:

1. lower context size
2. lower batch / ubatch if configured
3. reduce GPU layers only with explicit opt-in

GPU-layer reduction changes performance characteristics substantially, so it should not be part of the default fallback policy.

## User-visible progress

When an OOM or fit failure is detected, LLMGauge should print a clear status message such as:

    OOM detected at ctx=65536; retrying at ctx=32768

or:

    Fit attempt failed at ctx=32768 batch=256 ubatch=64; retrying with ctx=16384

## Attempt artifacts

Each attempt should preserve enough information for review:

- attempted context size
- batch and ubatch
- GPU layers
- status
- exit code
- failure classification
- stderr excerpt
- VRAM samples when available
- child result directory when a normal result artifact exists

## Summary artifact

A future Fit Ladder run should produce a parent summary containing:

- requested settings
- retry policy
- attempt ladder
- selected working settings
- final status
- failed attempts
- completed attempt if any
- whether OOM was detected
- whether fallback changed context, batch, ubatch, or GPU layers

## Claim boundary

A completed Fit Ladder result may say that a model fits under the selected fallback settings on the tested hardware/runtime.

It should not claim that the originally requested settings worked if they failed.

It should not compare quality across attempts unless equivalent prompts, scoring, and review were performed.

## v0.33 foundation

The initial implementation layer defines helper logic only:

- context-first fallback attempt planning
- fit-attempt records
- OOM, process-killed, and generic runtime failure classification
- parent fit-ladder summary structures

This foundation does not yet execute retries. Normal `run` and `run-ladder` behavior must remain unchanged unless a future Fit Ladder command or option is explicitly invoked.

## v0.34 execution loop

The initial execution loop is explicit and context-only:

    uv run llmgauge fit-ladder \
      --suite core-v1 \
      --include honesty \
      --model-profile example_model \
      --ctx 65536 \
      --fallback-contexts 8192,32768 \
      --out results/example-fit-ladder

Behavior:

- requested context is attempted first
- lower fallback contexts are attempted from largest to smallest
- retry continues only for retryable fit failures such as OOM or process-killed failures
- non-retryable runtime errors stop the ladder
- execution stops at the first completed attempt
- failed attempt directories are preserved
- parent summary is written to `fit-ladder-summary.json`
- GPU-layer fallback remains explicit-only and is not automatically applied

## v0.36 report polish

v0.36 improves the human-facing Fit Ladder report without changing Fit Ladder
execution behavior:

- `llmgauge fit-ladder` prints the generated `fit-ladder-report.md` path after
  completed or failed runs.
- Empty report fields render as `—` instead of `None`.
- `fit-ladder-report.md` includes a VRAM summary table when attempt-level VRAM
  data is available.

Fit Ladder remains explicit and opt-in. GPU-layer fallback remains
explicit-only.

## v0.35 artifact polish

Fit Ladder artifacts are first-class review artifacts:

- `fit-ladder-summary.json` stores requested settings, retry policy, selected working settings, and attempts.
- `fit-ladder-report.md` provides a human-readable summary.
- `validate-fit-ladder` validates summary shape, attempt records, counts, selected working settings, and completed child result artifacts.
- `export-index` detects Fit Ladder directories and records fit-specific metadata.

Fit Ladder reports preserve the core claim boundary: the selected fallback settings may be reported as working on the tested hardware/runtime, but failed requested settings must not be described as successful.
