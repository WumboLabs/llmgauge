# LocalMaxxing integration contract

## Boundary

LocalMaxxing is an optional public speed-benchmark destination. LLMGauge owns local measurement and provenance. Practical Use, Coding Core, multi-turn, Agent Session, reports, exports, and result validation never invoke this integration. Only the `localmaxxing` CLI namespace may access it; only `dry-run` and `submit` use the network.

## Method and artifact

The first method is `localmaxxing-llama-cpp-v1`; the first runtime is llama.cpp only. A run produces an immutable `benchmark.json` with `schema_version: llmgauge.localmaxxing_benchmark.v1` and `artifact_version: 1`. Its SHA-256 fingerprint is computed over canonical JSON with the `fingerprint` member omitted. It is independent of `llmgauge.run_fingerprint.v0`.

The artifact records canonical HF ID (and revision if known), exact quantization, safe model reference, profile identity, engine name/version/backend/executable evidence, source-backed host hardware, workload, normalized command provenance, runtime metadata, optional telemetry, warmup policy, every measured repetition, optional companion measurements, aggregate metrics, eligibility and creation time. Missing HF ID or ambiguous quantization permits a locally valid artifact but makes it ineligible.

## Workload and measurements

The llama.cpp adapter uses `llama-bench` only with its inspected supported flags. It records one warmup, then five measured repetitions by default, one benchmark stream (`batchSize: 1`), full GPU placement, deterministic benchmark semantics, a 512-token prompt/prefill target, and 128-token decode target. It explicitly uses llama.cpp logical token batch `-b 2048` and physical microbatch `-ub 512`; these engine flags are command provenance, not LocalMaxxing request concurrency. `llama-bench` cannot configure or evidence a runtime context-window size, so the workload omits `context_length` and export omits `contextLength`. `-d` is context depth/prefilled KV-cache depth and is not used as a context-window substitute. The adapter additionally runs one excluded warmup and five measured `-pg 512,128` companion tests for source-measured combined TPS. A localhost-only llama-server companion probe may record five streamed TTFT samples after its excluded warmup; it never changes the llama-bench throughput method. NVIDIA telemetry is sampled at 200 ms over total device usage, so peak VRAM is total-device rather than process-attributed. CPU, total RAM, OS, GPU count, runtime flags, combined TPS, TTFT, telemetry, and power are recorded/exported only when source-backed; unavailable values remain absent. Sampler controls, hardware cost, unified memory, chip variant, and unproven effective Flash Attention remain absent. Warmup is never included in aggregates. Each successful measurement must have positive `tok_s_out`; `tok_s_prefill` is captured where llama-bench supplies it. Aggregates are arithmetic means across every successful measured repetition; no fastest-run selection is permitted. TTFT, total TPS, peak VRAM and other unavailable metrics are omitted, never zero-filled.

## LocalMaxxing API mapping

The supported external contract is LocalMaxxing OpenAPI 1.6.0 retrieved 2026-08-15. `POST /api/speed-tests/dry-run` validates without writing; `POST /api/speed-tests` is public submission. The payload maps: `model.hf_id`→`hfId`, `model.revision`→`modelRevision`, source-backed `hardware`→`hardware`, engine fields, workload fields, aggregate `tok_s_out`→`tokSOut`, aggregate `tok_s_prefill`→`tokSPrefill`, source-measured combined TPS→`tokSTotal`, companion TTFT→`ttftMs`, total-device telemetry peak→`peakVramGb`, telemetry power samples→`gpuPowerWatts`, supported runtime flags→`engineFlags`, and command provenance→`engineFlags.commandSnippet`. Required API fields are HF ID, hardware, engine name, quantization, positive output TPS, plus one positive secondary metric. Missing optional local evidence remains absent; exporter does not invent a value.

## Eligibility and validation

Offline validation separately reports `locally_valid`, `localmaxxing_eligible`, or `localmaxxing_ineligible`. Eligibility fails closed for missing HF ID, quantization, valid discrete-GPU hardware, engine provenance, output TPS, prefill TPS, command provenance, incomplete/failing repetitions, or fingerprint mismatch. Validation is offline and never repairs artifacts.

## Network, auth, and submission

`run`, `validate`, and `export` are offline. Explicit online commands fetch agent context and fail closed when endpoint or contract identity differs. Authentication is only `LOCALMAXXING_API_KEY`; keys are not persisted, logged, exported, or included in errors. `submit` requires `--confirm-public`, dry-runs before the public request, and writes a separate receipt containing fingerprint, endpoint, timestamp, server ID and safe response metadata. It never mutates `benchmark.json`; failed submission writes no success receipt.

## Hardware and Area 4

The first adapter accepts one evidenced discrete GPU (`DISCRETE_GPU`) with GPU name/VRAM plus optional CPU, RAM and OS; it does not hardcode host identity. Validated native llama.cpp measurements are current inputs. Future Area 4 runtime-neutral measurements may provide the same fields without changing LocalMaxxing semantics. Area 4 is not implemented here.
