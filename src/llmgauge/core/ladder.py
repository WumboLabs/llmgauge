from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULT_CTX_LADDER = "8192,16384,32768"
DEFAULT_MAX_CONTEXT = 65536


def parse_ctx_ladder(
    value: str | None,
    max_context: int = DEFAULT_MAX_CONTEXT,
) -> list[int]:
    raw_value = value if value is not None else DEFAULT_CTX_LADDER

    if not raw_value.strip():
        raise ValueError("Context ladder cannot be empty")

    contexts: list[int] = []
    for raw_part in raw_value.split(","):
        part = raw_part.strip()
        if not part:
            raise ValueError(f"Invalid empty context value in ladder: {raw_value!r}")

        try:
            ctx = int(part)
        except ValueError as exc:
            raise ValueError(f"Context value must be an integer: {part!r}") from exc

        if ctx <= 0:
            raise ValueError(f"Context value must be positive: {ctx}")

        if ctx > max_context:
            raise ValueError(
                f"Context value {ctx} exceeds max allowed context {max_context}"
            )

        contexts.append(ctx)

    if len(set(contexts)) != len(contexts):
        raise ValueError("Context ladder contains duplicate values")

    if contexts != sorted(contexts):
        raise ValueError("Context ladder must be sorted from smallest to largest")

    return contexts


def build_ladder_summary(
    ladder_id: str,
    suite_id: str,
    include: str,
    only: str | None,
    model_id: str,
    contexts: list[int],
    child_runs: list[dict[str, Any]],
) -> dict[str, Any]:
    completed = sum(1 for item in child_runs if item.get("status") == "completed")
    failed = sum(1 for item in child_runs if item.get("status") == "failed")

    return {
        "schema_version": "llmgauge.context_ladder.v0",
        "ladder_id": ladder_id,
        "suite_id": suite_id,
        "include": include,
        "only": only,
        "model_id": model_id,
        "contexts": contexts,
        "max_context_policy": {
            "max_context": DEFAULT_MAX_CONTEXT,
            "requires_future_opt_in_above_max": True,
        },
        "summary": {
            "completed": completed,
            "failed": failed,
            "total": len(child_runs),
        },
        "child_runs": child_runs,
    }


def write_ladder_summary(out_dir: Path, summary: dict[str, Any]) -> Path:
    path = out_dir / "ladder-summary.json"
    path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def _fmt(value: Any) -> str:
    return "None" if value is None else str(value)


def build_ladder_report(summary: dict[str, Any]) -> str:
    lines = [
        f"# LLMGauge Context Ladder: {summary['ladder_id']}",
        "",
        "This report summarizes repeated local runs across explicit context sizes.",
        "",
        "## Ladder",
        "",
        f"- Suite: {summary['suite_id']}",
        f"- Include: {summary['include']}",
        f"- Only: {_fmt(summary.get('only'))}",
        f"- Model: {summary['model_id']}",
        f"- Contexts: {', '.join(str(ctx) for ctx in summary['contexts'])}",
        f"- Completed contexts: {summary['summary']['completed']}",
        f"- Failed contexts: {summary['summary']['failed']}",
        "",
        "## Child Runs",
        "",
        "| Context | Status | Result dir | Completed prompts | Failed prompts | Error |",
        "|---:|---|---|---:|---:|---|",
    ]

    for child in summary["child_runs"]:
        lines.append(
            "| "
            f"{child.get('ctx_size')} | "
            f"{child.get('status')} | "
            f"{child.get('result_dir')} | "
            f"{_fmt(child.get('completed'))} | "
            f"{_fmt(child.get('failed'))} | "
            f"{_fmt(child.get('error'))} |"
        )

    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- Context ladder runs use explicitly selected context sizes.",
            "- Default context ladder is 8192, 16384, 32768.",
            "- v0.08 context ladders are capped at 65536 tokens.",
            "- Runs above 65536 tokens are intentionally reserved for a later explicit extreme-context workflow.",
            "- Context ladder runs do not auto-tune KV cache, quantization, GPU settings, or CPU fallback.",
            "- Failures are preserved as child-run failures instead of hidden or skipped.",
            "",
        ]
    )

    return "\n".join(lines)


def write_ladder_report(out_dir: Path, summary: dict[str, Any]) -> Path:
    path = out_dir / "ladder-report.md"
    path.write_text(build_ladder_report(summary), encoding="utf-8")
    return path
