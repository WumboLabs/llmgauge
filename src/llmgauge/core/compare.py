from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_compare_result(result_dir: Path) -> dict[str, Any]:
    result_path = result_dir / "llmgauge-result.json"
    if not result_path.exists():
        raise FileNotFoundError(f"Missing result file: {result_path}")

    result = json.loads(result_path.read_text(encoding="utf-8"))
    result["_result_dir"] = str(result_dir)
    return result


def _fmt(value: Any) -> str:
    return "None" if value is None else str(value)


def _score_average(prompt_result: dict[str, Any]) -> Any:
    score = prompt_result.get("score")
    if not isinstance(score, dict):
        return None
    return score.get("prompt_average")


def _result_label(result: dict[str, Any]) -> str:
    model_id = result.get("model", {}).get("model_id", "unknown-model")
    run_id = result.get("run", {}).get("run_id", "unknown-run")
    return f"{model_id} ({run_id})"


def _prompt_map(result: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["prompt_id"]: item for item in result.get("results", [])}


def _collect_prompt_ids(results: list[dict[str, Any]]) -> list[str]:
    prompt_ids: set[str] = set()
    for result in results:
        prompt_ids.update(_prompt_map(result))
    return sorted(prompt_ids)


def _label_counts(result: dict[str, Any], key: str) -> dict[str, int]:
    summary = result.get("summary", {})
    value = summary.get(key, {})
    return value if isinstance(value, dict) else {}


def build_compare_report(results: list[dict[str, Any]]) -> str:
    if len(results) < 2:
        raise ValueError("Need at least two result directories to compare")

    lines = [
        "# LLMGauge Comparison Report",
        "",
        "This report compares completed local evaluation runs. It does not declare a universal winner.",
        "",
        "## Runs",
        "",
        "| Run | Model | Suite | Status | Completed | Failed | Scored | Avg score |",
        "|---|---|---|---:|---:|---:|---:|---:|",
    ]

    for result in results:
        run = result.get("run", {})
        model = result.get("model", {})
        suite = result.get("suite", {})
        summary = result.get("summary", {})

        lines.append(
            "| "
            f"{run.get('run_id')} | "
            f"{model.get('model_id')} | "
            f"{suite.get('suite_id')} | "
            f"{run.get('status')} | "
            f"{summary.get('completed')} | "
            f"{summary.get('failed')} | "
            f"{summary.get('scored_prompt_count')} | "
            f"{summary.get('manual_score_average')} |"
        )

    lines.extend(
        [
            "",
            "## Runtime",
            "",
            "| Run | Backend | Context | Max tokens | Temp | Top-p | Batch | UBatch | GPU layers |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )

    for result in results:
        runtime = result.get("runtime", {})
        lines.append(
            "| "
            f"{_result_label(result)} | "
            f"{runtime.get('backend')} | "
            f"{runtime.get('ctx_size')} | "
            f"{runtime.get('max_tokens')} | "
            f"{runtime.get('temperature')} | "
            f"{runtime.get('top_p')} | "
            f"{runtime.get('batch_size')} | "
            f"{runtime.get('ubatch_size')} | "
            f"{runtime.get('gpu_layers')} |"
        )

    lines.extend(
        [
            "",
            "## Prompt Scores",
            "",
        ]
    )

    prompt_ids = _collect_prompt_ids(results)

    header = (
        "| Prompt | " + " | ".join(_result_label(result) for result in results) + " |"
    )
    separator = "|---|" + "|".join("---:" for _ in results) + "|"
    lines.extend([header, separator])

    prompt_maps = [_prompt_map(result) for result in results]

    for prompt_id in prompt_ids:
        row = [prompt_id]
        for prompt_lookup in prompt_maps:
            prompt_result = prompt_lookup.get(prompt_id)
            row.append(
                _fmt(_score_average(prompt_result)) if prompt_result else "missing"
            )
        lines.append("| " + " | ".join(row) + " |")

    lines.extend(
        [
            "",
            "## Generation Speed",
            "",
        ]
    )

    header = (
        "| Prompt | " + " | ".join(_result_label(result) for result in results) + " |"
    )
    separator = "|---|" + "|".join("---:" for _ in results) + "|"
    lines.extend([header, separator])

    for prompt_id in prompt_ids:
        row = [prompt_id]
        for prompt_lookup in prompt_maps:
            prompt_result = prompt_lookup.get(prompt_id)
            if not prompt_result:
                row.append("missing")
                continue
            metrics = prompt_result.get("metrics", {})
            row.append(_fmt(metrics.get("generation_tps")))
        lines.append("| " + " | ".join(row) + " |")

    lines.extend(
        [
            "",
            "## Prompt Eval Speed",
            "",
        ]
    )

    lines.extend([header, separator])

    for prompt_id in prompt_ids:
        row = [prompt_id]
        for prompt_lookup in prompt_maps:
            prompt_result = prompt_lookup.get(prompt_id)
            if not prompt_result:
                row.append("missing")
                continue
            metrics = prompt_result.get("metrics", {})
            row.append(_fmt(metrics.get("prompt_eval_tps")))
        lines.append("| " + " | ".join(row) + " |")

    lines.extend(
        [
            "",
            "## Failure Labels",
            "",
        ]
    )

    for result in results:
        counts = _label_counts(result, "failure_labels")
        lines.extend([f"### {_result_label(result)}", ""])
        if counts:
            for label, count in sorted(counts.items()):
                lines.append(f"- {label}: {count}")
        else:
            lines.append("- None")
        lines.append("")

    lines.extend(
        [
            "## Good Labels",
            "",
        ]
    )

    for result in results:
        counts = _label_counts(result, "good_labels")
        lines.extend([f"### {_result_label(result)}", ""])
        if counts:
            for label, count in sorted(counts.items()):
                lines.append(f"- {label}: {count}")
        else:
            lines.append("- None")
        lines.append("")

    lines.extend(
        [
            "## Notes",
            "",
            "Scores are manual/local-context judgments. Speed and VRAM metrics are operational metrics, not quality scores.",
            "",
        ]
    )

    return "\n".join(lines)
