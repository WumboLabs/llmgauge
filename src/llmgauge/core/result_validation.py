from __future__ import annotations

import math
import json
from pathlib import Path
from typing import Any

from llmgauge.core.agent_harness import validate_agent_harness_result
from llmgauge.core.area4_evidence import validate_area4_evidence
from llmgauge.core.external_benchmark import validate_external_benchmark_result
from llmgauge.core.multi_turn import validate_result_transcript
from llmgauge.core.coding_core_evidence import (
    build_manual_review,
    build_method_provenance,
)
from llmgauge.core.generic_core_evidence import (
    build_manual_review as build_generic_manual_review,
    build_method_provenance as build_generic_method_provenance,
)
from llmgauge.core.generic_core_scoring import (
    GENERIC_CORE_SUITE_ID,
    GENERIC_CORE_VERSION,
)

from llmgauge.core.static_scoring import (
    CODING_CORE_SUITE_ID,
    CODING_CORE_VERSION,
    STATIC_RESPONSE_MAX_CHARS,
    StaticScoringError,
    apply_deterministic_check,
    compose_hybrid_score,
)
from llmgauge.core.run_fingerprint import (
    FingerprintUnavailable,
    resolve_contained_result_artifact,
    verify_run_fingerprint,
)
from llmgauge.core.sampling_profiles import validate_runtime_profile
from llmgauge.core.suite import ScoringRole, SuiteDefinitionError, load_normalized_suite
from llmgauge.core.suite_paths import resolve_suite_path


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


_LLAMA_REQUEST_STATES = frozenset({"explicit", "runtime_default"})

_LLAMA_CACHE_TYPES = frozenset(
    {"f32", "f16", "bf16", "q8_0", "q4_0", "q4_1", "iq4_nl", "q5_0", "q5_1"}
)
_LLAMA_REASONING_EFFORTS = frozenset(
    {"default", "minimal", "low", "medium", "high", "xhigh", "max"}
)
_LLAMA_FIT_MODES = frozenset({"on", "off"})
_LLAMA_SPEC_TYPES = frozenset(
    {
        "none",
        "draft-simple",
        "draft-eagle3",
        "draft-mtp",
        "draft-dflash",
        "draft-dspark",
        "ngram-simple",
        "ngram-map-k",
        "ngram-map-k4v",
        "ngram-mod",
        "ngram-cache",
    }
)


def _validate_optional_llama_runtime_metadata(runtime: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    integer_minimums = {
        "top_k": 0,
        "reasoning_budget": -1,
    }
    for field, minimum in integer_minimums.items():
        value = runtime.get(field)
        if value is not None and (
            isinstance(value, bool) or not isinstance(value, int) or value < minimum
        ):
            errors.append(f"runtime.{field} must be an integer at least {minimum}")
    seed = runtime.get("seed")
    if seed is not None and (isinstance(seed, bool) or not isinstance(seed, int)):
        errors.append("runtime.seed must be an integer when present")
    min_p = runtime.get("min_p")
    if min_p is not None and (
        isinstance(min_p, bool)
        or not isinstance(min_p, int | float)
        or not math.isfinite(min_p)
        or min_p < 0
    ):
        errors.append("runtime.min_p must be a finite number at least 0 when present")

    for field, allowed_values in (
        ("cache_type_k", _LLAMA_CACHE_TYPES),
        ("cache_type_v", _LLAMA_CACHE_TYPES),
        ("reasoning_effort", _LLAMA_REASONING_EFFORTS),
        ("fit", _LLAMA_FIT_MODES),
    ):
        value = runtime.get(field)
        if value is not None and (
            not isinstance(value, str) or value not in allowed_values
        ):
            errors.append(
                f"runtime.{field} must be one of: {', '.join(sorted(allowed_values))}"
            )

    reasoning_preserve = runtime.get("reasoning_preserve")
    if reasoning_preserve is not None and not isinstance(reasoning_preserve, bool):
        errors.append("runtime.reasoning_preserve must be a boolean when present")

    spec_type = runtime.get("spec_type")
    if spec_type is not None:
        if not isinstance(spec_type, str):
            errors.append("runtime.spec_type must be a string when present")
        else:
            spec_tokens = spec_type.split(",")
            if (
                not spec_tokens
                or any(not token for token in spec_tokens)
                or spec_type != spec_type.strip().lower()
                or any(token != token.strip() for token in spec_tokens)
            ):
                errors.append(
                    "runtime.spec_type must be a canonical comma-separated value"
                )
            elif any(token not in _LLAMA_SPEC_TYPES for token in spec_tokens):
                errors.append(
                    "runtime.spec_type contains an unsupported speculative type"
                )
            elif len(spec_tokens) != len(set(spec_tokens)):
                errors.append("runtime.spec_type must not contain duplicate values")
            elif "none" in spec_tokens and len(spec_tokens) != 1:
                errors.append(
                    "runtime.spec_type=none cannot be combined with other values"
                )

    for field in (
        "top_k",
        "min_p",
        "seed",
        "cache_type_k",
        "cache_type_v",
        "reasoning_effort",
        "reasoning_budget",
        "fit",
        "reasoning_preserve",
        "spec_type",
    ):
        state_field = f"{field}_state"
        state = runtime.get(state_field)
        if state is None:
            continue
        if state not in _LLAMA_REQUEST_STATES:
            errors.append(f"runtime.{state_field} must be explicit or runtime_default")
            continue
        if state == "explicit" and runtime.get(field) is None:
            errors.append(f"runtime.{state_field}=explicit requires runtime.{field}")
        if state == "runtime_default" and runtime.get(field) is not None:
            errors.append(
                f"runtime.{state_field}=runtime_default requires runtime.{field}=null"
            )

    parallel_sequences = runtime.get("parallel_sequences")
    if parallel_sequences is not None and parallel_sequences != 1:
        errors.append("runtime.parallel_sequences must be 1 when present")
    kv_offload = runtime.get("kv_offload")
    if kv_offload is not None and kv_offload != "requested_on":
        errors.append("runtime.kv_offload must be requested_on when present")
    return errors


def _validate_runtime_command_consistency(
    runtime: dict[str, Any],
    command_data: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    for field in (
        "top_k",
        "top_k_state",
        "min_p",
        "min_p_state",
        "seed",
        "seed_state",
        "kv_offload",
        "parallel_sequences",
        "cache_type_k",
        "cache_type_k_state",
        "cache_type_v",
        "cache_type_v_state",
        "reasoning_mode",
        "reasoning_effort",
        "reasoning_effort_state",
        "reasoning_budget",
        "reasoning_budget_state",
        "fit",
        "fit_state",
        "reasoning_preserve",
        "reasoning_preserve_state",
        "spec_type",
        "spec_type_state",
    ):
        if field in runtime and command_data.get(field) != runtime.get(field):
            errors.append(
                f"runtime command artifact {field} disagrees with runtime.{field}"
            )
    prompt_commands = command_data.get("prompt_commands")
    if prompt_commands is not None:
        if not isinstance(prompt_commands, list):
            errors.append("runtime command artifact prompt_commands must be a list")
        else:
            for index, prompt_command in enumerate(prompt_commands):
                if not isinstance(prompt_command, dict):
                    errors.append(
                        f"runtime command artifact prompt_commands[{index}] must be an object"
                    )
                    continue
                command_argv = prompt_command.get("command_argv")
                if not isinstance(command_argv, list) or not all(
                    isinstance(value, str) for value in command_argv
                ):
                    errors.append(
                        f"runtime command artifact prompt_commands[{index}].command_argv "
                        "must be a string list"
                    )
                transport = prompt_command.get("prompt_transport")
                if not isinstance(transport, dict):
                    errors.append(
                        f"runtime command artifact prompt_commands[{index}].prompt_transport "
                        "must be an object"
                    )
                    continue
                mode = transport.get("mode")
                if mode not in {"argv", "file", "unknown"}:
                    errors.append(
                        f"runtime command artifact prompt_commands[{index}].prompt_transport "
                        "has an invalid mode"
                    )
                if (
                    mode == "file"
                    and isinstance(command_argv, list)
                    and "--file" not in command_argv
                ):
                    errors.append(
                        f"runtime command artifact prompt_commands[{index}] "
                        "file transport requires --file argv"
                    )
                if (
                    mode == "argv"
                    and isinstance(command_argv, list)
                    and not {"-p", "--prompt"}.intersection(command_argv)
                ):
                    errors.append(
                        f"runtime command artifact prompt_commands[{index}] "
                        "argv transport requires prompt argv"
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
        if not isinstance(value, list) or not all(
            isinstance(item, str) for item in value
        ):
            errors.append(f"{prompt_id}.score.{list_field} must be a list of strings")

    reviewed = score.get("reviewed")
    if reviewed is not None and not isinstance(reviewed, bool):
        errors.append(f"{prompt_id}.score.reviewed must be a boolean")


_SELECTION_FIELDS = {
    "kind",
    "selected_profile",
    "selected_prompt_ids",
    "canonical_prompt_ids",
    "default_profile",
}
_CODING_PROMPT_BASE_FIELDS = {
    "response_form",
    "scoring_method",
    "manual_review",
}


def _read_coding_raw_response(
    result_dir: Path, prompt_result: dict[str, Any]
) -> tuple[str | None, str | None]:
    value = prompt_result.get("raw_output_path")
    if not isinstance(value, str) or not value:
        return None, "authoritative raw response reference is missing"
    try:
        path = resolve_contained_result_artifact(
            result_dir,
            value,
            label=f"{prompt_result.get('prompt_id', 'prompt')}.raw_output_path",
            require_file=True,
        )
    except (FingerprintUnavailable, OSError):
        return None, "authoritative raw response is missing or not safely contained"

    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            raw_response = handle.read(STATIC_RESPONSE_MAX_CHARS + 1)
    except (OSError, UnicodeError):
        return None, "authoritative raw response is unreadable"
    return raw_response, None


def _validate_coding_score_provenance(
    errors: list[str],
    prompt_id: str,
    prompt: Any,
    score: Any,
) -> None:
    if score is None or not isinstance(score, dict):
        return
    scoring = prompt.scoring
    rubric = scoring.manual_rubric if scoring is not None else None
    if (
        rubric is None
        or score.get("rubric_id") != rubric.id
        or score.get("rubric_version") != rubric.version
    ):
        errors.append(
            f"{prompt_id}.score rubric provenance does not match the declared method"
        )

    dimensions = score.get("dimensions")
    applicable = list(build_manual_review(prompt, None)["applicable_dimensions"])
    if (
        not isinstance(dimensions, dict)
        or len(dimensions) != len(applicable)
        or any(dimension not in dimensions for dimension in applicable)
    ):
        errors.append(
            f"{prompt_id}.score dimensions must contain only applicable Coding Core dimensions"
        )
        return
    for value in dimensions.values():
        if value is None:
            continue
        if (
            isinstance(value, bool)
            or not isinstance(value, int | float)
            or not math.isfinite(value)
            or not 0 <= value <= 5
        ):
            errors.append(
                f"{prompt_id}.score dimensions must be null or finite values from 0 to 5"
            )
            break


def _validate_optional_coding_core(
    result_dir: Path,
    data: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    suite_data = data.get("suite")
    results = data.get("results")
    if not isinstance(suite_data, dict) or not isinstance(results, list):
        return errors

    selection = suite_data.get("selection")
    coding_results = [
        item for item in results if isinstance(item, dict) and "coding_core" in item
    ]
    if selection is None and not coding_results:
        return errors
    if not coding_results and suite_data.get("suite_id") != CODING_CORE_SUITE_ID:
        return errors

    if (
        suite_data.get("suite_id") != CODING_CORE_SUITE_ID
        or suite_data.get("suite_version") != CODING_CORE_VERSION
    ):
        errors.append(
            "Coding Core selection or prompt evidence requires the supported suite ID/version"
        )
        return errors

    try:
        contract = load_normalized_suite(resolve_suite_path(Path(CODING_CORE_SUITE_ID)))
    except (FileNotFoundError, SuiteDefinitionError, OSError, RuntimeError):
        errors.append(
            "Coding Core result evidence cannot be validated because the logical suite contract is unavailable"
        )
        return errors

    result_prompt_ids = [
        item.get("prompt_id") for item in results if isinstance(item, dict)
    ]
    if selection is None:
        errors.append(
            "suite.selection is required when Coding Core prompt evidence is present"
        )
    elif not isinstance(selection, dict) or set(selection) != _SELECTION_FIELDS:
        errors.append("suite.selection must be a closed Coding Core selection object")
    else:
        selected_ids = selection.get("selected_prompt_ids")
        canonical_ids = selection.get("canonical_prompt_ids")
        kind = selection.get("kind")
        selected_profile = selection.get("selected_profile")
        if selected_ids != result_prompt_ids:
            errors.append(
                "suite.selection.selected_prompt_ids must exactly match result prompt ordering"
            )
        prompt_count = suite_data.get("prompt_count")
        if (
            isinstance(prompt_count, bool)
            or not isinstance(prompt_count, int)
            or prompt_count != len(results)
            or not isinstance(selected_ids, list)
            or prompt_count != len(selected_ids)
        ):
            errors.append(
                "suite.prompt_count must match exact selected membership and result count"
            )
        if canonical_ids != list(contract.canonical_prompt_ids):
            errors.append(
                "suite.selection.canonical_prompt_ids must match the logical Coding Core contract"
            )
        if selection.get("default_profile") != contract.default_profile:
            errors.append(
                "suite.selection.default_profile must match the logical Coding Core contract"
            )
        if kind == "profile":
            profile_ids = (
                contract.profiles.get(selected_profile)
                if isinstance(selected_profile, str)
                else None
            )
            if profile_ids is None or selected_ids != list(profile_ids):
                errors.append(
                    "suite.selection profile identity and membership are inconsistent"
                )
        elif kind == "custom":
            canonical_positions = {
                prompt_id: index
                for index, prompt_id in enumerate(contract.canonical_prompt_ids)
            }
            valid_ids = (
                isinstance(selected_ids, list)
                and bool(selected_ids)
                and all(
                    isinstance(prompt_id, str) and prompt_id in canonical_positions
                    for prompt_id in selected_ids
                )
            )
            positions = (
                [canonical_positions[prompt_id] for prompt_id in selected_ids]
                if valid_ids
                else []
            )
            if (
                selected_profile is not None
                or not valid_ids
                or len(selected_ids) != len(set(selected_ids))
                or positions != sorted(positions)
            ):
                errors.append(
                    "suite.selection custom membership must be unique and in canonical order"
                )
        else:
            errors.append(
                "suite.selection.kind must be profile or custom for Coding Core"
            )

        include = suite_data.get("include")
        only = suite_data.get("only")
        if not isinstance(include, str) or not include:
            errors.append(
                "suite.include must be non-empty invocation metadata when selection is represented"
            )
        if only is not None:
            if (
                not isinstance(only, str)
                or not only
                or not isinstance(selected_ids, list)
                or selected_ids != [only]
            ):
                errors.append(
                    "suite.only must equal the sole selected prompt when non-null"
                )
        elif kind == "profile":
            if include != "all":
                errors.append(
                    "profile selection requires compatible include=all invocation metadata"
                )
        elif kind == "custom":
            categories = [
                item.get("category") for item in results if isinstance(item, dict)
            ]
            if (
                include == "all"
                or not isinstance(include, str)
                or not include
                or len(categories) != len(results)
                or any(category != include for category in categories)
            ):
                errors.append(
                    "custom selection without suite.only requires matching category invocation metadata"
                )

    if selection is not None and len(coding_results) != len(results):
        errors.append(
            "suite.selection requires closed Coding Core evidence for every selected prompt"
        )
    elif coding_results and len(coding_results) != len(results):
        errors.append(
            "Coding Core prompt evidence must be present for every selected prompt when represented"
        )

    prompts = {prompt.id: prompt for prompt in contract.prompts}
    for prompt_result in coding_results:
        prompt_id = prompt_result.get("prompt_id")
        coding = prompt_result.get("coding_core")
        prompt = prompts.get(prompt_id)
        if prompt is None:
            errors.append("Coding Core prompt evidence references an unknown prompt")
            continue
        scoring = prompt.scoring
        expected_fields = set(_CODING_PROMPT_BASE_FIELDS)
        if scoring is not None and scoring.role is ScoringRole.HYBRID:
            expected_fields.update({"deterministic_result", "hybrid_composition"})
        if not isinstance(coding, dict) or set(coding) != expected_fields:
            errors.append(f"{prompt_id}.coding_core must use the declared closed shape")
            continue

        expected_method = build_method_provenance(prompt)
        if (
            coding.get("response_form") != expected_method["response_form"]
            or coding.get("scoring_method") != expected_method["scoring_method"]
        ):
            errors.append(
                f"{prompt_id}.coding_core method and response-form provenance is inconsistent"
            )

        score = prompt_result.get("score")
        _validate_coding_score_provenance(errors, prompt_id, prompt, score)
        try:
            expected_manual = build_manual_review(
                prompt, score if isinstance(score, dict) else None
            )
        except (StaticScoringError, ValueError):
            errors.append(
                f"{prompt_id}.coding_core manual review evidence is malformed"
            )
            expected_manual = None
        if (
            expected_manual is not None
            and coding.get("manual_review") != expected_manual
        ):
            errors.append(
                f"{prompt_id}.coding_core manual review state or rubric provenance is inconsistent"
            )

        if scoring is None or scoring.role is not ScoringRole.HYBRID:
            continue
        deterministic = coding.get("deterministic_result")
        if not isinstance(deterministic, dict):
            errors.append(
                f"{prompt_id}.coding_core deterministic result must be a closed object"
            )
            continue
        try:
            expected_hybrid = compose_hybrid_score(
                contract,
                prompt_id,
                deterministic,
                score if isinstance(score, dict) else None,
            )
        except StaticScoringError:
            errors.append(
                f"{prompt_id}.coding_core deterministic result is malformed or inconsistent"
            )
            continue
        if coding.get("hybrid_composition") != expected_hybrid:
            errors.append(
                f"{prompt_id}.coding_core hybrid composition or completeness is inconsistent"
            )

        raw_response, replay_error = _read_coding_raw_response(
            result_dir, prompt_result
        )
        if replay_error is not None:
            errors.append(f"{prompt_id}.coding_core {replay_error}")
            continue
        try:
            replayed = apply_deterministic_check(
                contract,
                prompt_id,
                raw_response,
                generation_failed=prompt_result.get("status") == "failed",
            )
        except StaticScoringError:
            errors.append(
                f"{prompt_id}.coding_core deterministic replay could not be evaluated"
            )
            continue
        if replayed != deterministic:
            errors.append(
                f"{prompt_id}.coding_core deterministic result does not match authoritative raw response replay"
            )

    return errors


def _validate_optional_generic_core(
    result_dir: Path, data: dict[str, Any]
) -> list[str]:
    errors: list[str] = []
    suite_data = data.get("suite")
    results = data.get("results")
    if not isinstance(suite_data, dict) or not isinstance(results, list):
        return errors
    generic_results = [
        item for item in results if isinstance(item, dict) and "generic_core" in item
    ]
    is_generic_suite = (
        suite_data.get("suite_id") == GENERIC_CORE_SUITE_ID
        and suite_data.get("suite_version") == GENERIC_CORE_VERSION
    )
    if not generic_results and not is_generic_suite:
        return errors
    if not is_generic_suite:
        return ["Generic Core evidence requires the supported suite ID/version"]
    try:
        contract = load_normalized_suite(
            resolve_suite_path(Path(GENERIC_CORE_SUITE_ID))
        )
    except (FileNotFoundError, SuiteDefinitionError, OSError, RuntimeError):
        return [
            "Generic Core result evidence cannot be validated because the logical suite contract is unavailable"
        ]

    selection = suite_data.get("selection")
    result_prompt_ids = [
        item.get("prompt_id") for item in results if isinstance(item, dict)
    ]
    if selection is None:
        errors.append("suite.selection is required for a Generic Core result")
    elif not isinstance(selection, dict) or set(selection) != _SELECTION_FIELDS:
        errors.append("suite.selection must be a closed Generic Core selection object")
    else:
        selected_ids = selection.get("selected_prompt_ids")
        canonical_ids = selection.get("canonical_prompt_ids")
        kind = selection.get("kind")
        selected_profile = selection.get("selected_profile")
        if selected_ids != result_prompt_ids:
            errors.append(
                "suite.selection.selected_prompt_ids must exactly match result prompt ordering"
            )
        prompt_count = suite_data.get("prompt_count")
        if (
            isinstance(prompt_count, bool)
            or not isinstance(prompt_count, int)
            or prompt_count != len(results)
            or not isinstance(selected_ids, list)
            or prompt_count != len(selected_ids)
        ):
            errors.append(
                "suite.prompt_count must match exact selected membership and result count"
            )
        if canonical_ids != list(contract.canonical_prompt_ids):
            errors.append(
                "suite.selection.canonical_prompt_ids must match the logical Generic Core contract"
            )
        if selection.get("default_profile") != contract.default_profile:
            errors.append(
                "suite.selection.default_profile must match the logical Generic Core contract"
            )
        if kind == "profile":
            profile_ids = (
                contract.profiles.get(selected_profile)
                if isinstance(selected_profile, str)
                else None
            )
            if profile_ids is None or selected_ids != list(profile_ids):
                errors.append(
                    "suite.selection profile identity and membership are inconsistent"
                )
        elif kind == "custom":
            canonical_positions = {
                prompt_id: index
                for index, prompt_id in enumerate(contract.canonical_prompt_ids)
            }
            valid_ids = (
                isinstance(selected_ids, list)
                and bool(selected_ids)
                and all(
                    isinstance(prompt_id, str) and prompt_id in canonical_positions
                    for prompt_id in selected_ids
                )
            )
            positions = (
                [canonical_positions[prompt_id] for prompt_id in selected_ids]
                if valid_ids
                else []
            )
            if (
                selected_profile is not None
                or not valid_ids
                or len(selected_ids) != len(set(selected_ids))
                or positions != sorted(positions)
            ):
                errors.append(
                    "suite.selection custom membership must be unique and in canonical order"
                )
        else:
            errors.append(
                "suite.selection.kind must be profile or custom for Generic Core"
            )

        include = suite_data.get("include")
        only = suite_data.get("only")
        if not isinstance(include, str) or not include:
            errors.append(
                "suite.include must be non-empty invocation metadata when selection is represented"
            )
        if only is not None:
            if (
                not isinstance(only, str)
                or not only
                or not isinstance(selected_ids, list)
                or selected_ids != [only]
            ):
                errors.append(
                    "suite.only must equal the sole selected prompt when non-null"
                )
        elif kind == "profile":
            if include != "all":
                errors.append(
                    "profile selection requires compatible include=all invocation metadata"
                )
        elif kind == "custom":
            categories = [
                item.get("category") for item in results if isinstance(item, dict)
            ]
            if (
                include == "all"
                or not isinstance(include, str)
                or not include
                or len(categories) != len(results)
                or any(category != include for category in categories)
            ):
                errors.append(
                    "custom selection without suite.only requires matching category invocation metadata"
                )

    if len(generic_results) != len(results):
        errors.append("Generic Core evidence must be present for every selected prompt")

    prompts = {prompt.id: prompt for prompt in contract.prompts}
    for prompt_result in generic_results:
        prompt_id = prompt_result.get("prompt_id")
        prompt = prompts.get(prompt_id)
        evidence = prompt_result.get("generic_core")
        if prompt is None or not isinstance(evidence, dict):
            errors.append("Generic Core prompt evidence is malformed or foreign")
            continue
        expected_method = build_generic_method_provenance(prompt)
        if (
            evidence.get("scoring_method") != expected_method["scoring_method"]
            or evidence.get("fixture_references")
            != expected_method["fixture_references"]
        ):
            errors.append(
                f"{prompt_id}.generic_core method or fixture provenance is inconsistent"
            )
            continue
        scoring = prompt.scoring
        if scoring is None:
            errors.append(f"{prompt_id}.generic_core scoring declaration is absent")
            continue
        if scoring.role is ScoringRole.MANUAL:
            if set(evidence) != {
                "scoring_method",
                "fixture_references",
                "manual_review",
            }:
                errors.append(
                    f"{prompt_id}.generic_core manual-only evidence has an invalid shape"
                )
            continue
        deterministic = evidence.get("deterministic_result")
        if not isinstance(deterministic, dict):
            errors.append(
                f"{prompt_id}.generic_core deterministic result is absent or malformed"
            )
            continue
        raw_response, raw_error = _read_coding_raw_response(result_dir, prompt_result)
        if raw_error is not None:
            errors.append(f"{prompt_id}.generic_core {raw_error}")
            continue
        try:
            replayed = apply_deterministic_check(
                contract,
                prompt_id,
                raw_response,
                generation_failed=prompt_result.get("status") == "failed",
            )
        except StaticScoringError:
            errors.append(
                f"{prompt_id}.generic_core deterministic replay could not be evaluated"
            )
            continue
        if replayed != deterministic:
            errors.append(
                f"{prompt_id}.generic_core deterministic result does not match authoritative raw response replay"
            )
        if scoring.role is ScoringRole.HYBRID:
            try:
                expected_manual = build_generic_manual_review(
                    prompt, prompt_result.get("score")
                )
                expected_hybrid = compose_hybrid_score(
                    contract, prompt_id, deterministic, prompt_result.get("score")
                )
            except (StaticScoringError, ValueError):
                errors.append(f"{prompt_id}.generic_core hybrid evidence is malformed")
                continue
            if (
                evidence.get("manual_review") != expected_manual
                or evidence.get("hybrid_composition") != expected_hybrid
            ):
                errors.append(
                    f"{prompt_id}.generic_core hybrid composition is inconsistent"
                )
        elif set(evidence) != {
            "scoring_method",
            "fixture_references",
            "deterministic_result",
        }:
            errors.append(
                f"{prompt_id}.generic_core deterministic evidence has an invalid shape"
            )
    return errors


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
    if isinstance(runtime, dict):
        errors.extend(validate_runtime_profile(runtime.get("profile"), runtime))
    if isinstance(runtime, dict) and runtime.get("backend") == "llama.cpp":
        errors.extend(_validate_optional_llama_runtime_metadata(runtime))
    if isinstance(runtime, dict) and runtime.get("runtime_command_captured"):
        command_path_value = runtime.get("runtime_command_path")
        if not isinstance(command_path_value, str) or not command_path_value:
            errors.append(
                "runtime.runtime_command_path must be set when command metadata is captured"
            )
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
                    if (
                        command_data.get("schema_version")
                        != "llmgauge.runtime_command.v0"
                    ):
                        errors.append(
                            "runtime command artifact schema_version must be "
                            "llmgauge.runtime_command.v0"
                        )
                    if isinstance(command_data, dict):
                        errors.extend(
                            _validate_runtime_command_consistency(runtime, command_data)
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
                    evidence_data = json.loads(
                        evidence_path.read_text(encoding="utf-8")
                    )
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
                errors.append(
                    f"{prompt_id}.failure_class must be a string when present"
                )

            finish_reason = prompt_result.get("finish_reason")
            if finish_reason is not None and not isinstance(finish_reason, str):
                errors.append(
                    f"{prompt_id}.finish_reason must be a string when present"
                )

    errors.extend(_validate_optional_coding_core(result_dir, data))
    errors.extend(_validate_optional_generic_core(result_dir, data))
    errors.extend(validate_agent_harness_result(result_dir, data))
    errors.extend(validate_external_benchmark_result(result_dir, data))
    errors.extend(validate_result_transcript(result_dir, data))
    errors.extend(validate_area4_evidence(result_dir, data))

    errors.extend(verify_run_fingerprint(result_dir, data))

    return errors


def validate_result_dir(result_dir: Path) -> list[str]:
    data = load_result_json(result_dir)
    return validate_result_data(result_dir, data)
