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
    "suite_version": "0.1.0"
  },
  "summary": {
    "completed": 10,
    "failed": 0,
    "manual_score_total": 371.0,
    "manual_score_max": 400.0,
    "manual_score_average": 4.64
  },
  "results": [
    {
      "prompt_id": "technical-correctness/arch-nvidia-update-boundary",
      "status": "completed",
      "prompt_eval_tps": 2100.5,
      "generation_tps": 72.3,
      "peak_vram_mib": 8425,
      "vram_headroom_mib": 3380,
      "score": {
        "verdict": "pass",
        "prompt_average": 4.5,
        "failure_labels": [],
        "good_labels": ["verification_first", "safe_stepwise_plan"]
      }
    }
  ]
}

Task:
Return the complete script.

Requirements:
- Accept the result JSON path as the first CLI argument.
- Handle missing optional fields by printing `unknown`.
- Do not crash if `results` is empty.
- Print:
  - run id
  - model id
  - suite id/version
  - completed/failed
  - manual score average
  - average generation tokens/sec across prompt results where present
  - peak VRAM max across prompt results where present
  - per-prompt verdict rows
- Do not use third-party dependencies.
- Do not invent fields outside the provided shape.
- Include a short usage example after the script.
