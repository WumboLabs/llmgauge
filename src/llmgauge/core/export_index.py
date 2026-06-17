from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from llmgauge.core.batch_validation import validate_batch_dir
from llmgauge.core.ladder_validation import validate_ladder_dir
from llmgauge.core.result_validation import validate_result_dir


EXPORT_INDEX_SCHEMA_VERSION = "llmgauge.export_index.v0"
RUN_RESULT_FILENAME = "llmgauge-result.json"
LADDER_SUMMARY_FILENAME = "ladder-summary.json"
BATCH_SUMMARY_FILENAME = "batch-summary.json"
RUN_REPORT_FILENAME = "report.md"
LADDER_REPORT_FILENAME = "ladder-report.md"
BATCH_REPORT_FILENAME = "batch-report.md"


def _utc_timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    if not isinstance(data, dict):
        raise ValueError(f"JSON artifact must contain an object: {path}")

    return data


def _optional_path(path: Path) -> str | None:
    if path.exists():
        return str(path)
    return None


def _validation_payload(errors: list[str]) -> dict[str, Any]:
    return {
        "checked": True,
        "status": "valid" if not errors else "invalid",
        "errors": errors,
    }


def _int_or_none(value: Any) -> int | None:
    return value if isinstance(value, int) else None


def _run_vram_metadata(path: Path, results: list[Any]) -> dict[str, Any]:
    vram_prompt_count = 0
    peak_values: list[int] = []
    headroom_values: list[int] = []
    vram_sample_artifact_count = 0

    for prompt_result in results:
        if not isinstance(prompt_result, dict):
            continue

        vram = prompt_result.get("vram")
        if isinstance(vram, dict) and vram.get("available"):
            vram_prompt_count += 1

            peak_used_mib = _int_or_none(vram.get("peak_used_mib"))
            peak_total_mib = _int_or_none(vram.get("peak_total_mib"))

            if peak_used_mib is not None:
                peak_values.append(peak_used_mib)

            if peak_used_mib is not None and peak_total_mib is not None:
                headroom_values.append(peak_total_mib - peak_used_mib)

        samples_path = prompt_result.get("vram_samples_path")
        if isinstance(samples_path, str) and (path / samples_path).exists():
            vram_sample_artifact_count += 1

    return {
        "vram_available": vram_prompt_count > 0,
        "peak_vram_mib": max(peak_values) if peak_values else None,
        "min_vram_headroom_mib": min(headroom_values) if headroom_values else None,
        "vram_prompt_count": vram_prompt_count,
        "vram_sample_artifact_count": vram_sample_artifact_count,
    }


def detect_artifact_type(path: Path) -> str:
    if not path.exists():
        raise ValueError(f"artifact path does not exist: {path}")

    if path.is_dir() and (path / RUN_RESULT_FILENAME).exists():
        return "run"

    if path.is_dir() and (path / LADDER_SUMMARY_FILENAME).exists():
        return "ladder"

    if path.is_dir() and (path / BATCH_SUMMARY_FILENAME).exists():
        return "batch"

    raise ValueError(f"unsupported artifact path: {path}")


def build_run_index_item(path: Path, *, validate: bool = False) -> dict[str, Any]:
    result_path = path / RUN_RESULT_FILENAME
    result = _read_json(result_path)

    run = result.get("run", {})
    model = result.get("model", {})
    suite = result.get("suite", {})
    summary = result.get("summary", {})
    results = result.get("results", [])

    if not isinstance(results, list):
        results = []

    item = {
        "artifact_type": "run",
        "path": str(path),
        "schema_version": result.get("schema_version"),
        "result_json": str(result_path),
        "report": _optional_path(path / RUN_REPORT_FILENAME),
        "run_id": run.get("run_id") or path.name,
        "status": run.get("status"),
        "timestamp_utc": run.get("timestamp_utc"),
        "suite_id": suite.get("suite_id"),
        "suite_version": suite.get("suite_version"),
        "model_id": model.get("model_id"),
        "model_profile": model.get("model_profile"),
        "prompt_count": summary.get("prompt_count")
        or suite.get("prompt_count")
        or len(results),
        "completed": summary.get("completed"),
        "failed": summary.get("failed"),
        "manual_score_total": summary.get("manual_score_total"),
        "manual_score_max": summary.get("manual_score_max"),
        "has_raw_artifacts": (path / "raw").exists(),
        "has_logs": (path / "logs").exists(),
        **_run_vram_metadata(path, results),
    }

    if validate:
        item["validation"] = _validation_payload(validate_result_dir(path))

    return item


def build_ladder_index_item(path: Path, *, validate: bool = False) -> dict[str, Any]:
    summary_path = path / LADDER_SUMMARY_FILENAME
    ladder = _read_json(summary_path)

    summary = ladder.get("summary", {})
    child_runs = ladder.get("child_runs", [])
    contexts = ladder.get("contexts", [])

    if not isinstance(child_runs, list):
        child_runs = []

    if not isinstance(contexts, list):
        contexts = []

    item = {
        "artifact_type": "ladder",
        "path": str(path),
        "schema_version": ladder.get("schema_version"),
        "ladder_summary": str(summary_path),
        "ladder_report": _optional_path(path / LADDER_REPORT_FILENAME),
        "ladder_id": ladder.get("ladder_id") or path.name,
        "suite_id": ladder.get("suite_id"),
        "model_id": ladder.get("model_id"),
        "include": ladder.get("include"),
        "only": ladder.get("only"),
        "contexts": contexts,
        "child_run_count": len(child_runs),
        "completed": summary.get("completed"),
        "failed": summary.get("failed"),
        "total": summary.get("total"),
        "has_child_runs": bool(child_runs),
    }

    if validate:
        item["validation"] = _validation_payload(validate_ladder_dir(path))

    return item


def build_batch_index_item(path: Path, *, validate: bool = False) -> dict[str, Any]:
    summary_path = path / BATCH_SUMMARY_FILENAME
    batch = _read_json(summary_path)

    summary = batch.get("summary", {})
    child_runs = batch.get("child_runs", [])
    models = batch.get("models", [])

    if not isinstance(child_runs, list):
        child_runs = []

    if not isinstance(models, list):
        models = []

    completed_child_runs = [
        child
        for child in child_runs
        if isinstance(child, dict) and child.get("status") == "completed"
    ]
    failed_child_runs = [
        child
        for child in child_runs
        if isinstance(child, dict) and child.get("status") == "failed"
    ]

    item = {
        "artifact_type": "batch",
        "path": str(path),
        "schema_version": batch.get("schema_version"),
        "batch_summary": str(summary_path),
        "batch_report": _optional_path(path / BATCH_REPORT_FILENAME),
        "batch_id": batch.get("batch_id") or path.name,
        "manifest_path": batch.get("manifest_path"),
        "suite_id": batch.get("suite_id"),
        "suite_path": batch.get("suite_path"),
        "include": batch.get("include"),
        "only": batch.get("only"),
        "max_tokens": batch.get("max_tokens"),
        "models": models,
        "model_count": len(models),
        "child_run_count": len(child_runs),
        "completed": summary.get("completed"),
        "failed": summary.get("failed"),
        "total": summary.get("total"),
        "has_child_runs": bool(child_runs),
        "has_completed_child_runs": bool(completed_child_runs),
        "has_failed_child_runs": bool(failed_child_runs),
    }

    if validate:
        item["validation"] = _validation_payload(validate_batch_dir(path))

    return item


def build_export_index(paths: list[Path], *, validate: bool = False) -> dict[str, Any]:
    items: list[dict[str, Any]] = []

    for path in paths:
        artifact_type = detect_artifact_type(path)

        if artifact_type == "run":
            items.append(build_run_index_item(path, validate=validate))
        elif artifact_type == "ladder":
            items.append(build_ladder_index_item(path, validate=validate))
        elif artifact_type == "batch":
            items.append(build_batch_index_item(path, validate=validate))
        else:
            raise ValueError(f"unsupported artifact type: {artifact_type}")

    return {
        "schema_version": EXPORT_INDEX_SCHEMA_VERSION,
        "generated_at_utc": _utc_timestamp(),
        "item_count": len(items),
        "validation_checked": validate,
        "items": items,
    }


def write_export_index(path: Path, index: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(index, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
