from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from llmgauge.core.result_validation import validate_result_dir


LADDER_SCHEMA_VERSION = "llmgauge.context_ladder.v0"
LADDER_SUMMARY_FILENAME = "ladder-summary.json"


def _load_ladder_summary(path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    errors: list[str] = []

    if not path.exists():
        return None, [f"missing {LADDER_SUMMARY_FILENAME}"]

    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception as exc:
        return None, [f"invalid {LADDER_SUMMARY_FILENAME}: {exc}"]

    if not isinstance(data, dict):
        return None, [f"{LADDER_SUMMARY_FILENAME} must contain a JSON object"]

    return data, errors


def _require_int(value: Any, name: str, errors: list[str]) -> None:
    if not isinstance(value, int):
        errors.append(f"{name} must be an integer")


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


def validate_ladder_dir(ladder_dir: Path) -> list[str]:
    errors: list[str] = []

    if not ladder_dir.exists():
        return [f"ladder directory does not exist: {ladder_dir}"]

    if not ladder_dir.is_dir():
        return [f"ladder path is not a directory: {ladder_dir}"]

    ladder, load_errors = _load_ladder_summary(ladder_dir / LADDER_SUMMARY_FILENAME)
    errors.extend(load_errors)

    if ladder is None:
        return errors

    if ladder.get("schema_version") != LADDER_SCHEMA_VERSION:
        errors.append(
            f"schema_version must be {LADDER_SCHEMA_VERSION}, got {ladder.get('schema_version')!r}"
        )

    contexts = ladder.get("contexts")
    if not isinstance(contexts, list):
        errors.append("contexts must be a list")
        contexts = []

    if not all(isinstance(ctx, int) for ctx in contexts):
        errors.append("contexts must contain only integers")

    child_runs = ladder.get("child_runs")
    if not isinstance(child_runs, list):
        errors.append("child_runs must be a list")
        child_runs = []

    typed_child_runs = [child for child in child_runs if isinstance(child, dict)]

    if len(typed_child_runs) != len(child_runs):
        errors.append("child_runs must contain only objects")

    if contexts and typed_child_runs:
        child_contexts = [child.get("ctx_size") for child in typed_child_runs]
        if child_contexts != contexts:
            errors.append("contexts do not match child_runs ctx_size order")

    summary = ladder.get("summary")
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
        result_dir_value = child.get("result_dir")
        ctx_size = child.get("ctx_size")

        if not isinstance(ctx_size, int):
            errors.append(f"child_runs[{index}].ctx_size must be an integer")

        if status not in {"completed", "failed"}:
            errors.append(f"child_runs[{index}].status must be completed or failed")

        if not isinstance(result_dir_value, str) or not result_dir_value:
            errors.append(f"child_runs[{index}].result_dir must be a non-empty string")
            continue

        result_dir = Path(result_dir_value)

        if not result_dir.is_absolute() and not result_dir.exists():
            result_dir = ladder_dir / result_dir_value

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
