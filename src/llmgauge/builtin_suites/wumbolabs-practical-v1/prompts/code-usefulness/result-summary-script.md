Write a small Python 3 script that reads a LLMGauge `llmgauge-result.json` file and prints a concise Markdown summary.

Use only the Python standard library.

The result JSON shape for this task is:

{
  "run": {
    "run_id": "gemma-q4-practical-v1",
    "status": "completed",
    "timestamp_utc": "2026-06-21T12:00:00Z"
  },
  "model": {
    "model_id": "gemma-4-12b-it-qat-ud-q4-k-xl",
    "model_profile": "gemma4_qat_q4"
  },
  "suite": {
    "suite_id": "wumbolabs-practical-v1",
    "suite_version": "0.2.0",
    "prompt_count": 1
  },
  "results": [
    {
      "prompt_id": "technical-correctness/linux-gpu-update-boundary",
      "status": "completed",
      "metrics": {
        "prompt_eval_tokens": null,
        "prompt_eval_tps": 2100.5,
        "generation_tokens": null,
        "generation_tps": 72.3,
        "peak_vram_mib": null,
        "vram_headroom_mib": null
      },
      "vram": {
        "available": true,
        "peak_used_mib": 8425,
        "peak_total_mib": 12227,
        "sample_count": 10
      },
      "vram_guardrails": {
        "status": "ok",
        "observed_headroom_mib": 3802,
        "warnings": []
      },
      "score": null
    }
  ]
}

Task:
Return the complete script.

Requirements:
- Accept the result JSON path as the first CLI argument.
- Handle missing optional fields by printing `unknown`.
- Do not crash if `results` is empty.
- Do not crash if `score` is null.
- Compute average generation tokens/sec using only results where `metrics.generation_tps` is numeric.
- Compute average prompt-eval tokens/sec using only results where `metrics.prompt_eval_tps` is numeric.
- Print:
  - run id
  - model id
  - suite id/version
  - prompt count
  - average generation tokens/sec across prompt results where present
  - average prompt-eval tokens/sec across prompt results where present
  - peak VRAM max from `vram.peak_used_mib` where present
  - minimum VRAM headroom from `vram_guardrails.observed_headroom_mib` where present
  - per-prompt verdict rows, using `unknown` when score/verdict is missing
- Prefer nested `metrics`, `vram`, and `vram_guardrails` values.
- Treat `metrics.peak_vram_mib` and `metrics.vram_headroom_mib` as legacy/null fields unless populated.
- Do not use third-party dependencies.
- Do not invent fields outside the provided shape.
- Include a short usage example after the script.
