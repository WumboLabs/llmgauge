from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from llmgauge.core.fit_ladder import (
    FIT_ATTEMPT_SCHEMA_VERSION,
    FIT_LADDER_SCHEMA_VERSION,
)
from llmgauge.core.result_validation import validate_result_dir


FIT_LADDER_SUMMARY_FILENAME = "fit-ladder-summary.json"

VALID_FINAL_STATUSES = {
    "completed_without_fallback",
    "completed_with_fallback",
    "failed",
}

VALID_ATTEMPT_STATUSES = {
    "completed",
    "failed",
}

VALID_FAILURE_CLASSES = {
    None,
    "oom",
    "process_killed",
    "runtime_error",
}


def _load_fit_ladder_summary(path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    if not path.exists():
        return None, [f"missing {FIT_LADDER_SUMMARY_FILENAME}"]

    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception as exc:
        return None, [f"invalid {FIT_LADDER_SUMMARY_FILENAME}: {exc}"]

    if not isinstance(data, dict):
        return None, [f"{FIT_LADDER_SUMMARY_FILENAME} must contain a JSON object"]

    return data, []


def _require_mapping(
    errors: list[str],
    data: dict[str, Any],
    key: str,
) -> dict[str, Any]:
    value = data.get(key)
    if not isinstance(value, dict):
        errors.append(f"{key} must be an object")
        return {}
    return value


def _require_int(errors: list[str], value: Any, name: str) -> None:
    if not isinstance(value, int):
        errors.append(f"{name} must be an integer")


def _require_bool(errors: list[str], value: Any, name: str) -> None:
    if not isinstance(value, bool):
        errors.append(f"{name} must be a boolean")


def _validate_attempt(
    *,
    fit_ladder_dir: Path,
    attempt: dict[str, Any],
    index: int,
    errors: list[str],
) -> None:
    prefix = f"attempts[{index}]"

    if attempt.get("schema_version") != FIT_ATTEMPT_SCHEMA_VERSION:
        errors.append(
            f"{prefix}.schema_version must be {FIT_ATTEMPT_SCHEMA_VERSION}, "
            f"got {attempt.get('schema_version')!r}"
        )

    attempt_id = attempt.get("attempt_id")
    if not isinstance(attempt_id, str) or not attempt_id:
        errors.append(f"{prefix}.attempt_id must be a non-empty string")

    for field in ["ctx_size", "batch_size", "ubatch_size", "gpu_layers", "exit_status"]:
        _require_int(errors, attempt.get(field), f"{prefix}.{field}")

    status = attempt.get("status")
    if status not in VALID_ATTEMPT_STATUSES:
        errors.append(f"{prefix}.status must be completed or failed")

    failure_class = attempt.get("failure_class")
    if failure_class not in VALID_FAILURE_CLASSES:
        errors.append(f"{prefix}.failure_class is invalid: {failure_class!r}")

    _require_bool(errors, attempt.get("retryable"), f"{prefix}.retryable")

    failure_reason = attempt.get("failure_reason")
    if not isinstance(failure_reason, str) or not failure_reason:
        errors.append(f"{prefix}.failure_reason must be a non-empty string")

    stderr_excerpt = attempt.get("stderr_excerpt")
    if stderr_excerpt is not None and not isinstance(stderr_excerpt, str):
        errors.append(f"{prefix}.stderr_excerpt must be a string or null")

    result_dir_value = attempt.get("result_dir")
    if result_dir_value is not None and not isinstance(result_dir_value, str):
        errors.append(f"{prefix}.result_dir must be a string or null")
        result_dir_value = None

    if status == "completed":
        if failure_class is not None:
            errors.append(f"{prefix}.completed attempt must not have a failure_class")
        if attempt.get("exit_status") != 0:
            errors.append(f"{prefix}.completed attempt must have exit_status 0")
        if not result_dir_value:
            errors.append(f"{prefix}.completed attempt must preserve result_dir")
            return

        result_dir = Path(result_dir_value)
        if not result_dir.is_absolute() and not result_dir.exists():
            result_dir = fit_ladder_dir / result_dir_value

        try:
            child_errors = validate_result_dir(result_dir)
        except Exception as exc:
            errors.append(f"{prefix} {result_dir}: {exc}")
        else:
            for child_error in child_errors:
                errors.append(f"{prefix} {result_dir}: {child_error}")

    if status == "failed":
        if failure_class is None:
            errors.append(f"{prefix}.failed attempt must have a failure_class")
        if not attempt.get("stderr_excerpt"):
            errors.append(f"{prefix}.failed attempt must preserve stderr_excerpt")


def validate_fit_ladder_data(
    fit_ladder_dir: Path,
    data: dict[str, Any],
) -> list[str]:
    errors: list[str] = []

    if data.get("schema_version") != FIT_LADDER_SCHEMA_VERSION:
        errors.append(
            f"schema_version must be {FIT_LADDER_SCHEMA_VERSION}, "
            f"got {data.get('schema_version')!r}"
        )

    fit_ladder_id = data.get("fit_ladder_id")
    if not isinstance(fit_ladder_id, str) or not fit_ladder_id:
        errors.append("fit_ladder_id must be a non-empty string")

    final_status = data.get("final_status")
    if final_status not in VALID_FINAL_STATUSES:
        errors.append(f"final_status is invalid: {final_status!r}")

    requested_settings = _require_mapping(errors, data, "requested_settings")
    retry_policy = _require_mapping(errors, data, "retry_policy")
    summary = _require_mapping(errors, data, "summary")

    if requested_settings:
        _require_int(errors, requested_settings.get("ctx_size"), "requested_settings.ctx_size")

    if retry_policy:
        fallback_order = retry_policy.get("fallback_order")
        if not isinstance(fallback_order, list) or not all(
            isinstance(item, str) for item in fallback_order
        ):
            errors.append("retry_policy.fallback_order must be a list of strings")

        fallback_contexts = retry_policy.get("fallback_contexts")
        if not isinstance(fallback_contexts, list) or not all(
            isinstance(item, int) for item in fallback_contexts
        ):
            errors.append("retry_policy.fallback_contexts must be a list of integers")

    attempts = data.get("attempts")
    if not isinstance(attempts, list):
        errors.append("attempts must be a list")
        attempts = []

    typed_attempts = [attempt for attempt in attempts if isinstance(attempt, dict)]
    if len(typed_attempts) != len(attempts):
        errors.append("attempts must contain only objects")

    for index, attempt in enumerate(typed_attempts, start=1):
        _validate_attempt(
            fit_ladder_dir=fit_ladder_dir,
            attempt=attempt,
            index=index,
            errors=errors,
        )

    if summary:
        for field in ["attempted", "completed", "failed"]:
            _require_int(errors, summary.get(field), f"summary.{field}")

        for field in ["oom_detected", "fallback_changed_context"]:
            _require_bool(errors, summary.get(field), f"summary.{field}")

        if all(isinstance(summary.get(field), int) for field in ["attempted", "completed", "failed"]):
            actual_attempted = len(typed_attempts)
            actual_completed = sum(
                1 for attempt in typed_attempts if attempt.get("status") == "completed"
            )
            actual_failed = sum(
                1 for attempt in typed_attempts if attempt.get("status") == "failed"
            )

            if summary["attempted"] != actual_attempted:
                errors.append(
                    f"summary.attempted {summary['attempted']} does not match attempt count {actual_attempted}"
                )
            if summary["completed"] != actual_completed:
                errors.append(
                    f"summary.completed {summary['completed']} does not match completed attempt count {actual_completed}"
                )
            if summary["failed"] != actual_failed:
                errors.append(
                    f"summary.failed {summary['failed']} does not match failed attempt count {actual_failed}"
                )

    completed_attempts = [
        attempt for attempt in typed_attempts if attempt.get("status") == "completed"
    ]
    if len(completed_attempts) > 1:
        errors.append("fit ladder must stop at first completed attempt")

    selected = data.get("selected_working_settings")
    if final_status == "failed":
        if selected is not None:
            errors.append("failed fit ladder must not have selected_working_settings")
    else:
        if not isinstance(selected, dict):
            errors.append("completed fit ladder must have selected_working_settings")
        elif completed_attempts:
            selected_attempt_id = selected.get("attempt_id")
            completed_attempt_ids = {
                attempt.get("attempt_id") for attempt in completed_attempts
            }
            if selected_attempt_id not in completed_attempt_ids:
                errors.append(
                    "selected_working_settings.attempt_id must reference a completed attempt"
                )

    return errors


def validate_fit_ladder_dir(fit_ladder_dir: Path) -> list[str]:
    if not fit_ladder_dir.exists():
        return [f"fit-ladder directory does not exist: {fit_ladder_dir}"]

    if not fit_ladder_dir.is_dir():
        return [f"fit-ladder path is not a directory: {fit_ladder_dir}"]

    data, load_errors = _load_fit_ladder_summary(
        fit_ladder_dir / FIT_LADDER_SUMMARY_FILENAME
    )
    if data is None:
        return load_errors

    return load_errors + validate_fit_ladder_data(fit_ladder_dir, data)
