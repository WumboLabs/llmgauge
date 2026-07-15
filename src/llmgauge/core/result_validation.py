from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from llmgauge.core.run_fingerprint import (
    FingerprintUnavailable,
    resolve_contained_result_artifact,
    verify_run_fingerprint,
)


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

# Bounds for optional untrusted vLLM server metadata (additive fields).
_MAX_VLLM_VERSION_LENGTH = 64
_MAX_SYSTEM_FINGERPRINT_LENGTH = 256
_ALLOWED_SERVER_STATES = frozenset({"ready", "unknown", "cold", "warm"})
_ALLOWED_FINGERPRINT_STATUSES = frozenset({"present", "absent", "invalid"})


def _contains_control_characters(value: str) -> bool:
    return any(ord(ch) < 32 or ord(ch) == 127 for ch in value)


def _validate_bounded_optional_string(
    value: Any,
    *,
    label: str,
    max_length: int,
    allow_unknown: bool = False,
) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, str):
        return [f"{label} must be a string when present"]
    if allow_unknown and value == "unknown":
        return []
    if not value:
        return [f"{label} must be non-empty when present"]
    if len(value) > max_length:
        return [f"{label} exceeds maximum length {max_length}"]
    if _contains_control_characters(value):
        return [f"{label} must not contain control characters"]
    return []


def _validate_optional_system_fingerprint(
    mapping: dict[str, Any],
    *,
    label: str,
) -> list[str]:
    errors: list[str] = []
    if "system_fingerprint" in mapping:
        errors.extend(
            _validate_bounded_optional_string(
                mapping.get("system_fingerprint"),
                label=f"{label}.system_fingerprint",
                max_length=_MAX_SYSTEM_FINGERPRINT_LENGTH,
            )
        )
    status = mapping.get("system_fingerprint_status")
    if status is not None:
        if not isinstance(status, str):
            errors.append(
                f"{label}.system_fingerprint_status must be a string when present"
            )
        elif status not in _ALLOWED_FINGERPRINT_STATUSES:
            errors.append(
                f"{label}.system_fingerprint_status must be one of "
                "present, absent, invalid"
            )
    return errors


def _validate_optional_vllm_runtime_metadata(
    mapping: dict[str, Any],
    *,
    label: str,
) -> list[str]:
    """Validate optional vLLM version/state/fingerprint fields when present."""
    errors: list[str] = []
    if "vllm_version" in mapping:
        errors.extend(
            _validate_bounded_optional_string(
                mapping.get("vllm_version"),
                label=f"{label}.vllm_version",
                max_length=_MAX_VLLM_VERSION_LENGTH,
                allow_unknown=True,
            )
        )
    server_state = mapping.get("server_state")
    if server_state is not None:
        if not isinstance(server_state, str):
            errors.append(f"{label}.server_state must be a string when present")
        elif server_state not in _ALLOWED_SERVER_STATES:
            errors.append(
                f"{label}.server_state must be one of ready, unknown, cold, warm"
            )
    fingerprints = mapping.get("observed_system_fingerprints")
    if fingerprints is not None:
        if not isinstance(fingerprints, list):
            errors.append(
                f"{label}.observed_system_fingerprints must be a list when present"
            )
        else:
            for index, item in enumerate(fingerprints):
                errors.extend(
                    _validate_bounded_optional_string(
                        item,
                        label=f"{label}.observed_system_fingerprints[{index}]",
                        max_length=_MAX_SYSTEM_FINGERPRINT_LENGTH,
                    )
                )
    return errors


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

    try:
        resolve_contained_result_artifact(
            result_dir,
            value,
            label=f"{prompt_id}.{field}",
            require_file=True,
        )
    except FingerprintUnavailable as exc:
        errors.append(str(exc))


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
            try:
                command_path = resolve_contained_result_artifact(
                    result_dir,
                    command_path_value,
                    label="runtime.runtime_command_path",
                    require_file=True,
                )
            except FingerprintUnavailable as exc:
                errors.append(str(exc))
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

    if isinstance(runtime, dict) and runtime.get("vllm_runtime_evidence_captured"):
        evidence_path_value = runtime.get("vllm_runtime_evidence_path")
        if not isinstance(evidence_path_value, str) or not evidence_path_value:
            errors.append(
                "runtime.vllm_runtime_evidence_path must be set when vLLM "
                "runtime evidence is captured"
            )
        else:
            try:
                evidence_path = resolve_contained_result_artifact(
                    result_dir,
                    evidence_path_value,
                    label="runtime.vllm_runtime_evidence_path",
                    require_file=True,
                )
            except FingerprintUnavailable as exc:
                errors.append(str(exc))
            else:
                try:
                    evidence_data = json.loads(evidence_path.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    errors.append(
                        "vLLM runtime evidence artifact is not valid JSON: "
                        f"{evidence_path_value}"
                    )
                else:
                    if evidence_data.get("schema_version") != (
                        "llmgauge.vllm_runtime_evidence.v0"
                    ):
                        errors.append(
                            "vLLM runtime evidence schema_version must be "
                            "llmgauge.vllm_runtime_evidence.v0"
                        )
                    endpoint_identity = evidence_data.get("endpoint_identity")
                    if endpoint_identity is not None:
                        if not isinstance(endpoint_identity, dict):
                            errors.append(
                                "vLLM runtime evidence endpoint_identity must be an object"
                            )
                        else:
                            for forbidden in (
                                "url",
                                "raw_url",
                                "username",
                                "password",
                                "headers",
                                "proxy",
                            ):
                                if forbidden in endpoint_identity:
                                    errors.append(
                                        "vLLM runtime evidence endpoint_identity "
                                        f"must not include {forbidden}"
                                    )
                    errors.extend(
                        _validate_optional_vllm_runtime_metadata(
                            evidence_data,
                            label="vLLM runtime evidence",
                        )
                    )

            for key in ("endpoint_identity",):
                value = runtime.get(key)
                if value is not None and not isinstance(value, dict):
                    errors.append(f"runtime.{key} must be an object when present")

            for key in (
                "requested_served_model",
                "observed_served_model",
                "lifecycle_ownership",
                "proxy_bypass_policy",
            ):
                value = runtime.get(key)
                if value is not None and not isinstance(value, str):
                    errors.append(f"runtime.{key} must be a string when present")

            errors.extend(
                _validate_optional_vllm_runtime_metadata(
                    runtime,
                    label="runtime",
                )
            )

    # Optional per-prompt vLLM request evidence (additive).
    results = data.get("results")
    if isinstance(results, list):
        for prompt_result in results:
            if not isinstance(prompt_result, dict):
                continue
            prompt_id = prompt_result.get("prompt_id", "prompt")
            request_path_value = prompt_result.get("request_evidence_path")
            if request_path_value is None:
                # Still validate optional in-result fingerprint fields.
                errors.extend(
                    _validate_optional_system_fingerprint(
                        prompt_result,
                        label=str(prompt_id),
                    )
                )
                failure_class = prompt_result.get("failure_class")
                if failure_class is not None and not isinstance(failure_class, str):
                    errors.append(
                        f"{prompt_id}.failure_class must be a string when present"
                    )
                finish_reason = prompt_result.get("finish_reason")
                if finish_reason is not None and not isinstance(finish_reason, str):
                    errors.append(
                        f"{prompt_id}.finish_reason must be a string when present"
                    )
                continue
            if not isinstance(request_path_value, str) or not request_path_value:
                errors.append(
                    f"{prompt_id}.request_evidence_path must be a non-empty string"
                )
                continue
            try:
                request_path = resolve_contained_result_artifact(
                    result_dir,
                    request_path_value,
                    label=f"{prompt_id}.request_evidence_path",
                    require_file=True,
                )
            except FingerprintUnavailable as exc:
                errors.append(str(exc))
            else:
                try:
                    request_data = json.loads(request_path.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    errors.append(
                        f"{prompt_id}.request_evidence_path is not valid JSON"
                    )
                else:
                    if request_data.get("schema_version") != (
                        "llmgauge.vllm_request_evidence.v0"
                    ):
                        errors.append(
                            f"{prompt_id} request evidence schema_version must be "
                            "llmgauge.vllm_request_evidence.v0"
                        )
                    else:
                        errors.extend(
                            _validate_optional_system_fingerprint(
                                request_data,
                                label=f"{prompt_id} request evidence",
                            )
                        )

            errors.extend(
                _validate_optional_system_fingerprint(
                    prompt_result,
                    label=str(prompt_id),
                )
            )

            failure_class = prompt_result.get("failure_class")
            if failure_class is not None and not isinstance(failure_class, str):
                errors.append(f"{prompt_id}.failure_class must be a string when present")

            finish_reason = prompt_result.get("finish_reason")
            if finish_reason is not None and not isinstance(finish_reason, str):
                errors.append(
                    f"{prompt_id}.finish_reason must be a string when present"
                )

    errors.extend(verify_run_fingerprint(result_dir, data))

    return errors


def validate_result_dir(result_dir: Path) -> list[str]:
    data = load_result_json(result_dir)
    return validate_result_data(result_dir, data)
