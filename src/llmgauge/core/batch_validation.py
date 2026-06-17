from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from llmgauge.core.result_validation import validate_result_dir


BATCH_SCHEMA_VERSION = "llmgauge.batch_summary.v0"
BATCH_SUMMARY_FILENAME = "batch-summary.json"

REQUIRED_TOP_LEVEL_KEYS = [
    "schema_version",
    "batch_id",
    "manifest_path",
    "suite_id",
    "suite_path",
    "include",
    "only",
    "max_tokens",
    "models",
    "execution",
    "summary",
    "child_runs",
]


def _load_batch_summary(path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    if not path.exists():
        return None, [f"missing {BATCH_SUMMARY_FILENAME}"]

    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception as exc:
        return None, [f"invalid {BATCH_SUMMARY_FILENAME}: {exc}"]

    if not isinstance(data, dict):
        return None, [f"{BATCH_SUMMARY_FILENAME} must contain a JSON object"]

    return data, []


def _require_int(value: Any, name: str, errors: list[str]) -> None:
    if not isinstance(value, int):
        errors.append(f"{name} must be an integer")


def _require_nonempty_string(value: Any, name: str, errors: list[str]) -> None:
    if not isinstance(value, str) or not value:
        errors.append(f"{name} must be a non-empty string")


def _validate_summary_counts(
    *,
    summary: dict[str, Any],
    child_runs: list[dict[str, Any]],
    errors: list[str],
) -> None:
    total = summary.get("total")
    completed = summary.get("completed")
    failed = summary.get("failed")

    _require_int(total, "summary.total", errors)
    _require_int(completed, "summary.completed", errors)
    _require_int(failed, "summary.failed", errors)

    if not all(isinstance(value, int) for value in [total, completed, failed]):
        return

    actual_total = len(child_runs)
    actual_completed = sum(
        1 for child in child_runs if child.get("status") == "completed"
    )
    actual_failed = sum(1 for child in child_runs if child.get("status") == "failed")

    if total != actual_total:
        errors.append(
            f"summary.total {total} does not match child run count {actual_total}"
        )

    if completed != actual_completed:
        errors.append(
            f"summary.completed {completed} does not match completed child count {actual_completed}"
        )

    if failed != actual_failed:
        errors.append(
            f"summary.failed {failed} does not match failed child count {actual_failed}"
        )


def _resolve_child_result_dir(batch_dir: Path, result_dir_value: str) -> Path:
    result_dir = Path(result_dir_value)

    if result_dir.is_absolute():
        return result_dir

    if result_dir.exists():
        return result_dir

    batch_relative = batch_dir / result_dir
    if batch_relative.exists():
        return batch_relative

    parts = result_dir.parts
    if batch_dir.name in parts:
        index = len(parts) - 1 - parts[::-1].index(batch_dir.name)
        suffix = Path(*parts[index + 1 :])
        if str(suffix) != ".":
            suffix_candidate = batch_dir / suffix
            if suffix_candidate.exists():
                return suffix_candidate

    return batch_relative


def validate_batch_dir(batch_dir: Path) -> list[str]:
    errors: list[str] = []

    if not batch_dir.exists():
        return [f"batch directory does not exist: {batch_dir}"]

    if not batch_dir.is_dir():
        return [f"batch path is not a directory: {batch_dir}"]

    batch, load_errors = _load_batch_summary(batch_dir / BATCH_SUMMARY_FILENAME)
    errors.extend(load_errors)

    if batch is None:
        return errors

    for key in REQUIRED_TOP_LEVEL_KEYS:
        if key not in batch:
            errors.append(f"Missing top-level key: {key}")

    if batch.get("schema_version") != BATCH_SCHEMA_VERSION:
        errors.append(
            f"schema_version must be {BATCH_SCHEMA_VERSION}, got {batch.get('schema_version')!r}"
        )

    models = batch.get("models")
    if not isinstance(models, list):
        errors.append("models must be a list")
        models = []

    typed_models = [model for model in models if isinstance(model, str) and model]
    if len(typed_models) != len(models):
        errors.append("models must contain only non-empty strings")

    child_runs = batch.get("child_runs")
    if not isinstance(child_runs, list):
        errors.append("child_runs must be a list")
        child_runs = []

    typed_child_runs = [child for child in child_runs if isinstance(child, dict)]
    if len(typed_child_runs) != len(child_runs):
        errors.append("child_runs must contain only objects")

    if typed_models and typed_child_runs:
        child_profiles = [child.get("model_profile") for child in typed_child_runs]
        if child_profiles != typed_models:
            errors.append("models do not match child_runs model_profile order")

    execution = batch.get("execution")
    if not isinstance(execution, dict):
        errors.append("execution must be an object")
    else:
        if execution.get("mode") != "sequential":
            errors.append("execution.mode must be sequential")
        if execution.get("parallelism") != "disabled":
            errors.append("execution.parallelism must be disabled")

    summary = batch.get("summary")
    if not isinstance(summary, dict):
        errors.append("summary must be an object")
        summary = {}

    _validate_summary_counts(
        summary=summary,
        child_runs=typed_child_runs,
        errors=errors,
    )

    for index, child in enumerate(typed_child_runs, start=1):
        status = child.get("status")
        model_profile = child.get("model_profile")
        result_dir_value = child.get("result_dir")

        _require_nonempty_string(
            model_profile,
            f"child_runs[{index}].model_profile",
            errors,
        )

        if status not in {"completed", "failed"}:
            errors.append(f"child_runs[{index}].status must be completed or failed")

        if not isinstance(result_dir_value, str) or not result_dir_value:
            errors.append(f"child_runs[{index}].result_dir must be a non-empty string")
            continue

        result_dir = _resolve_child_result_dir(batch_dir, result_dir_value)

        if status == "completed":
            try:
                child_errors = validate_result_dir(result_dir)
            except Exception as exc:
                errors.append(f"child_runs[{index}] {result_dir}: {exc}")
            else:
                for child_error in child_errors:
                    errors.append(f"child_runs[{index}] {result_dir}: {child_error}")
        elif not child.get("error"):
            errors.append(
                f"child_runs[{index}] failed child run must preserve error text"
            )

    return errors
