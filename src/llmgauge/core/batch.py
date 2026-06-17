from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml


BATCH_MANIFEST_SCHEMA_VERSION = "llmgauge.batch_manifest.v0"
BATCH_SUMMARY_SCHEMA_VERSION = "llmgauge.batch_summary.v0"


def _require_nonempty_string(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Batch manifest field {key!r} must be a non-empty string")
    return value.strip()


def _optional_nonempty_string(data: dict[str, Any], key: str) -> str | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Batch manifest field {key!r} must be a non-empty string")
    return value.strip()


def _optional_positive_int(data: dict[str, Any], key: str) -> int | None:
    value = data.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"Batch manifest field {key!r} must be a positive integer")
    if value <= 0:
        raise ValueError(f"Batch manifest field {key!r} must be positive")
    return value


def _normalize_model_profiles(data: dict[str, Any]) -> list[str]:
    models = data.get("models")
    if not isinstance(models, list) or not models:
        raise ValueError("Batch manifest field 'models' must be a non-empty list")

    normalized: list[str] = []
    for index, item in enumerate(models, start=1):
        if not isinstance(item, str) or not item.strip():
            raise ValueError(
                f"Batch manifest models entry {index} must be a non-empty string"
            )
        normalized.append(item.strip())

    if len(set(normalized)) != len(normalized):
        raise ValueError("Batch manifest field 'models' contains duplicate entries")

    return normalized


def load_batch_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Batch manifest does not exist: {path}")

    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Batch manifest did not parse as a mapping: {path}")

    schema_version = data.get("schema_version")
    if schema_version != BATCH_MANIFEST_SCHEMA_VERSION:
        raise ValueError(
            f"Batch manifest schema_version must be {BATCH_MANIFEST_SCHEMA_VERSION!r}"
        )

    batch_id = _optional_nonempty_string(data, "batch_id") or path.stem
    suite = _require_nonempty_string(data, "suite")
    include = _optional_nonempty_string(data, "include") or "all"
    only = _optional_nonempty_string(data, "only")
    max_tokens = _optional_positive_int(data, "max_tokens")
    models = _normalize_model_profiles(data)

    return {
        "schema_version": BATCH_MANIFEST_SCHEMA_VERSION,
        "batch_id": batch_id,
        "suite": suite,
        "include": include,
        "only": only,
        "max_tokens": max_tokens,
        "models": models,
    }


def build_batch_summary(
    *,
    batch_id: str,
    suite_id: str,
    suite_path: str,
    include: str,
    only: str | None,
    max_tokens: int | None,
    models: list[str],
    child_runs: list[dict[str, Any]],
    manifest_path: str,
) -> dict[str, Any]:
    completed = sum(1 for item in child_runs if item.get("status") == "completed")
    failed = sum(1 for item in child_runs if item.get("status") == "failed")

    return {
        "schema_version": BATCH_SUMMARY_SCHEMA_VERSION,
        "batch_id": batch_id,
        "manifest_path": manifest_path,
        "suite_id": suite_id,
        "suite_path": suite_path,
        "include": include,
        "only": only,
        "max_tokens": max_tokens,
        "models": models,
        "execution": {
            "mode": "sequential",
            "model_reference_policy": "manifest model entries are model profile names only",
            "parallelism": "disabled",
        },
        "summary": {
            "completed": completed,
            "failed": failed,
            "total": len(child_runs),
        },
        "child_runs": child_runs,
    }


def write_batch_summary(out_dir: Path, summary: dict[str, Any]) -> Path:
    path = out_dir / "batch-summary.json"
    path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def _fmt(value: Any) -> str:
    return "None" if value is None else str(value)


def build_batch_report(summary: dict[str, Any]) -> str:
    lines = [
        f"# LLMGauge Model Batch: {summary['batch_id']}",
        "",
        "This report summarizes sequential local runs across explicit model profiles.",
        "",
        "## Batch",
        "",
        f"- Manifest: {summary['manifest_path']}",
        f"- Suite: {summary['suite_id']}",
        f"- Suite path: {summary['suite_path']}",
        f"- Include: {summary['include']}",
        f"- Only: {_fmt(summary.get('only'))}",
        f"- Max tokens override: {_fmt(summary.get('max_tokens'))}",
        f"- Models: {', '.join(summary['models'])}",
        f"- Completed models: {summary['summary']['completed']}",
        f"- Failed models: {summary['summary']['failed']}",
        f"- Execution mode: {summary['execution']['mode']}",
        "",
        "## Child Runs",
        "",
        "| Model profile | Model ID | Status | Result dir | Completed prompts | Failed prompts | Error |",
        "|---|---|---|---|---:|---:|---|",
    ]

    for child in summary["child_runs"]:
        lines.append(
            "| "
            f"{child.get('model_profile')} | "
            f"{_fmt(child.get('model_id'))} | "
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
            "- Model batch runs are sequential.",
            "- Manifest model entries are existing model profile names only.",
            "- Batch manifests do not accept arbitrary model paths.",
            "- Each child is a normal LLMGauge run directory with raw outputs preserved.",
            "- Failures are recorded per model profile instead of hidden or skipped.",
            "- Batch runs do not auto-download models, mutate GPU settings, or write Monolith databases.",
            "",
        ]
    )

    return "\n".join(lines)


def write_batch_report(out_dir: Path, summary: dict[str, Any]) -> Path:
    path = out_dir / "batch-report.md"
    path.write_text(build_batch_report(summary), encoding="utf-8")
    return path
