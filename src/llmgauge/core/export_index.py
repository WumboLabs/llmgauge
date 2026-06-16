from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from llmgauge.core.ladder_validation import validate_ladder_dir
from llmgauge.core.result_validation import validate_result_dir


EXPORT_INDEX_SCHEMA_VERSION = "llmgauge.export_index.v0"
RUN_RESULT_FILENAME = "llmgauge-result.json"
LADDER_SUMMARY_FILENAME = "ladder-summary.json"
RUN_REPORT_FILENAME = "report.md"
LADDER_REPORT_FILENAME = "ladder-report.md"


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


def detect_artifact_type(path: Path) -> str:
    if not path.exists():
        raise ValueError(f"artifact path does not exist: {path}")

    if path.is_dir() and (path / RUN_RESULT_FILENAME).exists():
        return "run"

    if path.is_dir() and (path / LADDER_SUMMARY_FILENAME).exists():
        return "ladder"

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


def build_export_index(paths: list[Path], *, validate: bool = False) -> dict[str, Any]:
    items: list[dict[str, Any]] = []

    for path in paths:
        artifact_type = detect_artifact_type(path)

        if artifact_type == "run":
            items.append(build_run_index_item(path, validate=validate))
        elif artifact_type == "ladder":
            items.append(build_ladder_index_item(path, validate=validate))
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
