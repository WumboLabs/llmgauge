from __future__ import annotations

from typing import Any


def _fmt(value: Any) -> str:
    return "None" if value is None else str(value)


def _score_average(prompt_result: dict[str, Any]) -> Any:
    score = prompt_result.get("score")
    if not isinstance(score, dict):
        return None
    return score.get("prompt_average")


def _fmt_optional_mib(value: Any) -> str:
    return "-" if value is None else str(value)


def _vram_peak_used_mib(prompt_result: dict[str, Any]) -> int | None:
    vram = prompt_result.get("vram")
    if not isinstance(vram, dict) or not vram.get("available"):
        return None

    peak_used_mib = vram.get("peak_used_mib")
    if not isinstance(peak_used_mib, int):
        return None

    return peak_used_mib


def _vram_headroom_mib(prompt_result: dict[str, Any]) -> int | None:
    vram = prompt_result.get("vram")
    if not isinstance(vram, dict) or not vram.get("available"):
        return None

    peak_used_mib = vram.get("peak_used_mib")
    peak_total_mib = vram.get("peak_total_mib")
    if not isinstance(peak_used_mib, int) or not isinstance(peak_total_mib, int):
        return None

    return peak_total_mib - peak_used_mib


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
    ]

    if summary.get("scored_prompt_count"):
        lines.extend(
            [
                "## Score Summary",
                "",
                f"- Scored prompts: {summary.get('scored_prompt_count')}",
                f"- Manual score total: {summary.get('manual_score_total')}",
                f"- Manual score max: {summary.get('manual_score_max')}",
                f"- Manual score average: {summary.get('manual_score_average')} / 5",
                "",
            ]
        )

        failure_labels = summary.get("failure_labels", {})
        good_labels = summary.get("good_labels", {})

        if failure_labels:
            lines.extend(["### Failure Labels", ""])
            for label, count in sorted(failure_labels.items()):
                lines.append(f"- {label}: {count}")
            lines.append("")

        if good_labels:
            lines.extend(["### Good Labels", ""])
            for label, count in sorted(good_labels.items()):
                lines.append(f"- {label}: {count}")
            lines.append("")

    lines.extend(
        [
            "## Prompt Results",
            "",
            "| Prompt | Category | Status | Score avg | Prompt tok/s | Generation tok/s | Peak VRAM MiB | VRAM Headroom MiB | Exit |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )

    for prompt_result in result["results"]:
        metrics = prompt_result["metrics"]
        lines.append(
            "| "
            f"{prompt_result['prompt_id']} | "
            f"{prompt_result.get('category') or ''} | "
            f"{prompt_result['status']} | "
            f"{_fmt(_score_average(prompt_result))} | "
            f"{_fmt(metrics['prompt_eval_tps'])} | "
            f"{_fmt(metrics['generation_tps'])} | "
            f"{_fmt_optional_mib(_vram_peak_used_mib(prompt_result))} | "
            f"{_fmt_optional_mib(_vram_headroom_mib(prompt_result))} | "
            f"{prompt_result['exit_status']} |"
        )

    scored_results = [
        item for item in result["results"] if isinstance(item.get("score"), dict)
    ]

    if scored_results:
        lines.extend(["", "## Manual Review Notes", ""])

        for prompt_result in scored_results:
            score = prompt_result["score"]
            failure_labels = score.get("failure_labels", [])
            good_labels = score.get("good_labels", [])
            reviewer_notes = score.get("reviewer_notes", "")
            verdict = score.get("verdict", "")

            lines.extend(
                [
                    f"### {prompt_result['prompt_id']}",
                    "",
                    f"- Score average: {_fmt(score.get('prompt_average'))} / 5",
                    f"- Verdict: {verdict}",
                    f"- Failure labels: {', '.join(failure_labels) if failure_labels else 'None'}",
                    f"- Good labels: {', '.join(good_labels) if good_labels else 'None'}",
                    f"- Notes: {reviewer_notes}",
                    "",
                ]
            )

    lines.extend(
        [
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
                f"- Cleaned output: `{prompt_result['cleaned_output_path']}`"
                if prompt_result.get("cleaned_output_path")
                else "- Cleaned output: not available",
                f"- Stderr log: `{prompt_result['stderr_log_path']}`",
            ]
        )

        if prompt_result.get("vram_samples_path"):
            lines.append(f"- VRAM samples: `{prompt_result['vram_samples_path']}`")

        lines.append("")

    lines.extend(
        [
            "## Notes",
            "",
            "Raw model outputs are preserved separately and are not cleaned or filtered.",
            "",
        ]
    )

    return "\n".join(lines)
