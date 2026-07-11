from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from llmgauge.core.run_fingerprint import verify_run_fingerprint


REQUIRED_TOP_LEVEL_KEYS = [
    "schema_version",
    "llmgauge_version",
    "run",
    "model",
    "runtime",
    "suite",
    "summary",
    "results",
]

REQUIRED_PROMPT_RESULT_KEYS = [
    "prompt_id",
    "category",
    "status",
    "raw_prompt_path",
    "raw_output_path",
    "stderr_log_path",
    "exit_status",
    "metrics",
]


def load_result_json(result_dir: Path) -> dict[str, Any]:
    result_path = result_dir / "llmgauge-result.json"
    if not result_path.exists():
        raise FileNotFoundError(f"Missing result file: {result_path}")

    data = json.loads(result_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Result JSON did not parse as an object: {result_path}")

    return data


def _check_required_mapping(
    errors: list[str],
    data: dict[str, Any],
    key: str,
    label: str,
) -> None:
    if key not in data:
        errors.append(f"Missing {label}: {key}")
        return

    if not isinstance(data[key], dict):
        errors.append(f"{label} must be an object: {key}")


def _check_artifact_path(
    errors: list[str],
    result_dir: Path,
    prompt_id: str,
    field: str,
    value: Any,
) -> None:
    if not isinstance(value, str) or not value:
        errors.append(f"{prompt_id}.{field} must be a non-empty string")
        return

    path = result_dir / value
    if not path.exists():
        errors.append(f"{prompt_id}.{field} missing artifact: {value}")


def _check_score_shape(errors: list[str], prompt_id: str, score: Any) -> None:
    if score is None:
        return

    if not isinstance(score, dict):
        errors.append(f"{prompt_id}.score must be null or an object")
        return

    dimensions = score.get("dimensions")
    if dimensions is not None and not isinstance(dimensions, dict):
        errors.append(f"{prompt_id}.score.dimensions must be an object when present")

    for label_field in ["failure_labels", "good_labels"]:
        labels = score.get(label_field, [])
        if not isinstance(labels, list):
            errors.append(f"{prompt_id}.score.{label_field} must be a list")

    for string_field in [
        "schema_version",
        "scale",
        "rubric_id",
        "rubric_version",
        "reviewer_notes",
        "score_rationale",
        "verdict",
        "scoring_mode",
        "scorer_id",
        "scorer_version",
        "confidence",
        "override_status",
    ]:
        value = score.get(string_field, "")
        if value is not None and not isinstance(value, str):
            errors.append(f"{prompt_id}.score.{string_field} must be a string")

    for list_field in ["evidence", "warnings"]:
        value = score.get(list_field, [])
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            errors.append(f"{prompt_id}.score.{list_field} must be a list of strings")

    reviewed = score.get("reviewed")
    if reviewed is not None and not isinstance(reviewed, bool):
        errors.append(f"{prompt_id}.score.reviewed must be a boolean")


def validate_result_data(result_dir: Path, data: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    for key in REQUIRED_TOP_LEVEL_KEYS:
        if key not in data:
            errors.append(f"Missing top-level key: {key}")

    for key in ["run", "model", "runtime", "suite", "summary"]:
        _check_required_mapping(errors, data, key, "top-level object")

    results = data.get("results")
    if not isinstance(results, list):
        errors.append("Top-level key 'results' must be a list")
        return errors

    prompt_ids: list[str] = []
    completed = 0
    failed = 0

    for index, prompt_result in enumerate(results):
        if not isinstance(prompt_result, dict):
            errors.append(f"results[{index}] must be an object")
            continue

        prompt_id = prompt_result.get("prompt_id", f"results[{index}]")
        if not isinstance(prompt_id, str) or not prompt_id:
            errors.append(f"results[{index}].prompt_id must be a non-empty string")
            prompt_id = f"results[{index}]"
        else:
            prompt_ids.append(prompt_id)

        for key in REQUIRED_PROMPT_RESULT_KEYS:
            if key not in prompt_result:
                errors.append(f"{prompt_id} missing required field: {key}")

        status = prompt_result.get("status")
        if status == "completed":
            completed += 1
        elif status == "failed":
            failed += 1
        else:
            errors.append(f"{prompt_id}.status must be completed or failed")

        metrics = prompt_result.get("metrics")
        if not isinstance(metrics, dict):
            errors.append(f"{prompt_id}.metrics must be an object")

        for field in ["raw_prompt_path", "raw_output_path", "stderr_log_path"]:
            _check_artifact_path(
                errors,
                result_dir,
                prompt_id,
                field,
                prompt_result.get(field),
            )

        if "cleaned_output_path" in prompt_result:
            _check_artifact_path(
                errors,
                result_dir,
                prompt_id,
                "cleaned_output_path",
                prompt_result.get("cleaned_output_path"),
            )

        _check_score_shape(errors, prompt_id, prompt_result.get("score"))

    duplicate_ids = sorted(
        {prompt_id for prompt_id in prompt_ids if prompt_ids.count(prompt_id) > 1}
    )
    for prompt_id in duplicate_ids:
        errors.append(f"Duplicate prompt_id: {prompt_id}")

    summary = data.get("summary", {})
    if isinstance(summary, dict):
        if summary.get("completed") != completed:
            errors.append(
                f"summary.completed is {summary.get('completed')}, expected {completed}"
            )
        if summary.get("failed") != failed:
            errors.append(
                f"summary.failed is {summary.get('failed')}, expected {failed}"
            )

    model = data.get("model", {})
    if isinstance(model, dict):
        model_path = model.get("model_path")
        if model_path != "redacted":
            errors.append("model.model_path must be redacted")

    runtime = data.get("runtime", {})
    if isinstance(runtime, dict) and runtime.get("runtime_command_captured"):
        command_path_value = runtime.get("runtime_command_path")
        if not isinstance(command_path_value, str) or not command_path_value:
            errors.append("runtime.runtime_command_path must be set when command metadata is captured")
        else:
            command_path = result_dir / command_path_value
            if not command_path.exists():
                errors.append(
                    f"runtime command artifact missing: {command_path_value}"
                )
            else:
                try:
                    command_data = json.loads(command_path.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    errors.append(
                        f"runtime command artifact is not valid JSON: {command_path_value}"
                    )
                else:
                    if command_data.get("schema_version") != "llmgauge.runtime_command.v0":
                        errors.append(
                            "runtime command artifact schema_version must be "
                            "llmgauge.runtime_command.v0"
                        )

    errors.extend(verify_run_fingerprint(result_dir, data))

    return errors


def validate_result_dir(result_dir: Path) -> list[str]:
    data = load_result_json(result_dir)
    return validate_result_data(result_dir, data)
