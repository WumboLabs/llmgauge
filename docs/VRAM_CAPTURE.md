# VRAM Capture

LLMGauge can capture read-only NVIDIA VRAM usage during local llama.cpp runs.

This is intended for practical local-model evaluation on constrained GPUs. It records operational memory behavior alongside speed and scoring data.

## Scope

VRAM capture is:

- read-only
- NVIDIA-focused through `nvidia-smi`
- prompt-level
- non-fatal if unavailable
- stored in local result artifacts

It does not tune GPU clocks, drivers, CUDA, power limits, memory settings, or model parameters.

## Capture method

For each prompt run, LLMGauge samples `nvidia-smi`:

- once before launching `llama-cli`
- periodically while `llama-cli` is running
- once after the process exits

The query shape is:

    nvidia-smi --query-gpu=index,name,memory.used,memory.total --format=csv,noheader,nounits

If `nvidia-smi` is missing, times out, or returns an error, the run continues and VRAM is marked unavailable.

## Result fields

Each prompt result may include:

    "vram": {
      "schema_version": "llmgauge.vram.summary.v0",
      "available": true,
      "sample_count": 14,
      "peak_used_mib": 7535,
      "peak_total_mib": 12227,
      "peak_gpu_index": 0,
      "peak_gpu_name": "NVIDIA GeForce RTX 5070",
      "initial_used_mib": 393,
      "final_used_mib": 393,
      "error": null
    }

and:

    "vram_samples_path": "vram/tool-honesty__fake-tool-resistance.samples.json"

## Sample artifact

Raw sample files are written under the run directory:

    vram/<prompt-id>.samples.json

For prompt IDs containing `/`, the filename uses `__`.

Example:

    tool-honesty/fake-tool-resistance

becomes:

    vram/tool-honesty__fake-tool-resistance.samples.json

The sample artifact contains:

    {
      "schema_version": "llmgauge.vram.samples.v0",
      "prompt_id": "tool-honesty/fake-tool-resistance",
      "samples": [
        {
          "timestamp_utc": "2026-06-17T02:15:12+00:00",
          "gpu_index": 0,
          "gpu_name": "NVIDIA GeForce RTX 5070",
          "used_mib": 393,
          "total_mib": 12227
        }
      ]
    }

## Report display

`report.md` includes prompt-level:

- Peak VRAM MiB
- VRAM Headroom MiB

Headroom is calculated as:

    peak_total_mib - peak_used_mib

If VRAM is unavailable or absent in older artifacts, reports display `-`.

## Comparison display

Comparison reports include:

- run-level peak VRAM MiB
- run-level minimum VRAM headroom MiB
- prompt-level peak VRAM MiB
- prompt-level VRAM headroom MiB

Older artifacts without VRAM data remain readable and display `-`.

## Guardrails

LLMGauge can record warning-only VRAM guardrail metadata when configured.

Example config:

    vram:
      min_headroom_warn_mib: 1000

This does not fail the run. It records whether observed prompt-level VRAM headroom is below the configured warning threshold.

Prompt result field:

    "vram_guardrails": {
      "schema_version": "llmgauge.vram.guardrails.v0",
      "status": "ok",
      "min_headroom_warn_mib": 1000,
      "observed_headroom_mib": 4692,
      "warnings": []
    }

If observed headroom is below the threshold, status becomes:

    warning

and warnings includes:

    vram_headroom_below_warning_threshold

If no threshold is configured, or VRAM is unavailable, `vram_guardrails` may be null.

## Known limitations

Current VRAM capture is intentionally simple.

Limitations:

- NVIDIA-only for now
- depends on `nvidia-smi`
- polling interval can miss very short spikes
- reports GPU-level memory usage, not process-attributed memory
- multi-GPU systems are summarized by the highest observed used memory sample
- no automatic VRAM safety gate or failure threshold yet

Future versions may add explicit VRAM thresholds, process attribution, richer GPU metadata, and non-NVIDIA backends.
