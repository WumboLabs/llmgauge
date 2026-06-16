from __future__ import annotations

from typing import Any


def _fmt(value: Any) -> str:
    return "None" if value is None else str(value)


def build_markdown_report(result: dict[str, Any]) -> str:
    run = result["run"]
    model = result["model"]
    runtime = result["runtime"]
    suite = result["suite"]
    summary = result["summary"]

    lines = [
        f"# LLMGauge Report: {run['run_id']}",
        "",
        "## Run",
        "",
        f"- Status: {run['status']}",
        f"- Timestamp UTC: {run['timestamp_utc']}",
        f"- Suite: {suite['suite_id']} ({suite['suite_version']})",
        f"- Prompt count: {suite['prompt_count']}",
        f"- Completed: {summary['completed']}",
        f"- Failed: {summary['failed']}",
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
        f"- Top-p: {runtime['top_p']}",
        f"- Batch: {runtime['batch_size']}",
        f"- UBatch: {runtime['ubatch_size']}",
        f"- GPU layers: {runtime['gpu_layers']}",
        "",
        "## Prompt Results",
        "",
        "| Prompt | Category | Status | Prompt tok/s | Generation tok/s | Exit |",
        "|---|---|---:|---:|---:|---:|",
    ]

    for prompt_result in result["results"]:
        metrics = prompt_result["metrics"]
        lines.append(
            "| "
            f"{prompt_result['prompt_id']} | "
            f"{prompt_result.get('category') or ''} | "
            f"{prompt_result['status']} | "
            f"{_fmt(metrics['prompt_eval_tps'])} | "
            f"{_fmt(metrics['generation_tps'])} | "
            f"{prompt_result['exit_status']} |"
        )

    lines.extend(
        [
            "",
            "## Artifact Paths",
            "",
        ]
    )

    for prompt_result in result["results"]:
        lines.extend(
            [
                f"### {prompt_result['prompt_id']}",
                "",
                f"- Raw prompt: `{prompt_result['raw_prompt_path']}`",
                f"- Raw output: `{prompt_result['raw_output_path']}`",
                f"- Stderr log: `{prompt_result['stderr_log_path']}`",
                "",
            ]
        )

    lines.extend(
        [
            "## Notes",
            "",
            "Raw model outputs are preserved separately and are not cleaned or filtered.",
            "",
        ]
    )

    return "\n".join(lines)
