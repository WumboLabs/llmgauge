from __future__ import annotations

from typing import Any


def build_markdown_report(result: dict[str, Any]) -> str:
    run = result["run"]
    model = result["model"]
    runtime = result["runtime"]
    suite = result["suite"]
    prompt_result = result["results"][0]
    metrics = prompt_result["metrics"]

    lines = [
        f"# LLMGauge Report: {run['run_id']}",
        "",
        "## Run",
        "",
        f"- Status: {run['status']}",
        f"- Timestamp UTC: {run['timestamp_utc']}",
        f"- Suite: {suite['suite_id']} ({suite['suite_version']})",
        "",
        "## Model",
        "",
        f"- Model ID: {model['model_id']}",
        f"- Model path policy: {model['model_path_policy']}",
        "",
        "## Runtime",
        "",
        f"- Backend: {runtime['backend']}",
        f"- llama-cli: {runtime['llama_cli']}",
        f"- Context: {runtime['ctx_size']}",
        f"- Max tokens: {runtime['max_tokens']}",
        f"- Temperature: {runtime['temperature']}",
        f"- GPU layers: {runtime['gpu_layers']}",
        "",
        "## Prompt Result",
        "",
        f"- Prompt ID: {prompt_result['prompt_id']}",
        f"- Status: {prompt_result['status']}",
        f"- Exit status: {prompt_result['exit_status']}",
        f"- Raw prompt: `{prompt_result['raw_prompt_path']}`",
        f"- Raw output: `{prompt_result['raw_output_path']}`",
        f"- Stderr log: `{prompt_result['stderr_log_path']}`",
        "",
        "## Metrics",
        "",
        f"- Prompt eval tokens: {metrics['prompt_eval_tokens']}",
        f"- Prompt eval tok/s: {metrics['prompt_eval_tps']}",
        f"- Generation tokens: {metrics['generation_tokens']}",
        f"- Generation tok/s: {metrics['generation_tps']}",
        f"- Peak VRAM MiB: {metrics['peak_vram_mib']}",
        f"- VRAM headroom MiB: {metrics['vram_headroom_mib']}",
        "",
        "## Notes",
        "",
        "Raw model output is preserved separately and is not cleaned or filtered.",
        "",
    ]

    return "\n".join(lines)
