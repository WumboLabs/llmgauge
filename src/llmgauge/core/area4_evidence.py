from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any, Mapping

from llmgauge.core.metrics import parse_llama_cpp_diagnostics, placement_states

VLLM_REQUEST_EVIDENCE_SCHEMA = "llmgauge.vllm_request_evidence.v0"
VLLM_STREAM_EVIDENCE_SCHEMA = "llmgauge.vllm_stream_evidence.v0"
TTFT_METRIC_ID = "llmgauge.metric.v1.time_to_first_token"
TTFT_BOUNDARY = "request_transmit_to_first_generated_token"
_VLLM_REQUEST_FORM = "chat_messages"
_VLLM_MEASUREMENT_ID_RE = re.compile(r"^vllm-request-[0-9]+$")

_VLLM_FAILURE_CATEGORY_MAP: dict[str, str] = {
    "endpoint_unavailable": "endpoint_failure",
    "connect_failed": "endpoint_failure",
    "request_timeout": "endpoint_failure",
    "server_request_error": "endpoint_failure",
    "readiness_failure": "endpoint_failure",
    "malformed_response": "malformed_response",
    "served_model_mismatch": "runtime_environment_failure",
}

RUNTIME_NEUTRAL_METRICS_SCHEMA = "llmgauge.runtime_neutral_metrics.v1"
FAILURE_TAXONOMY_SCHEMA = "llmgauge.failure_taxonomy.v1"
NATIVE_EXECUTION_EVIDENCE_SCHEMA = "llmgauge.native_llama_cpp_execution_evidence.v1"

_MEASUREMENT_ID_RE = re.compile(r"^native-single-turn-[0-9]+$")
_EXECUTION_REF_RE = re.compile(r"^results/[0-9]+$")
_ATTEMPT_ID = "attempt-0"
_OOM_RE = re.compile(
    r"\b(?:out of memory|oom|cuda(?:\s+error)?:?\s+.*(?:alloc|memory))\b", re.I
)
_WEIGHT_LOAD_RE = re.compile(
    r"\b(?:llama_model_load|llama_load_model_from_file)\b", re.I
)
_KV_CACHE_RE = re.compile(r"\b(?:llama_kv_cache|kv[ _-]?cache)", re.I)
_PEAK_VRAM_METRIC_ID = "llmgauge.metric.v1.peak_vram"
PEAK_VRAM_CALCULATION = "llmgauge.area4.peak_used_mib_by_device.v1"
_PEAK_VRAM_BOUNDARY = "process_launch_to_completion_sampling_window"
VLLM_PEAK_VRAM_BOUNDARY = "request_window_peak_vram_observation"


def _valid_vram_samples(samples: object) -> list[dict[str, Any]]:
    if not isinstance(samples, list):
        return []
    valid: list[dict[str, Any]] = []
    for sample in samples:
        if not isinstance(sample, Mapping):
            continue
        gpu_index = sample.get("gpu_index")
        gpu_name = sample.get("gpu_name")
        used_mib = sample.get("used_mib")
        if (
            isinstance(gpu_index, int)
            and not isinstance(gpu_index, bool)
            and isinstance(gpu_name, str)
            and isinstance(used_mib, int)
            and not isinstance(used_mib, bool)
            and used_mib >= 0
        ):
            valid.append(
                {"gpu_index": gpu_index, "gpu_name": gpu_name, "used_mib": used_mib}
            )
    return valid


def _peak_vram_metric_records(
    samples: list[Any],
    evidence_path: str | None,
    *,
    boundary: str = _PEAK_VRAM_BOUNDARY,
) -> list[dict[str, Any]]:
    """Deterministic peak-VRAM metric records over preserved samples.

    One record per observed device (gpu_index + gpu_name); the value is the
    maximum absolute used memory in the sampling window, never a baseline
    delta or cross-device aggregate. An attempted but invalid capture yields
    one unavailable record; absence of capture yields no record at all.
    """
    evidence_refs = (
        [f"{evidence_path}#/samples"] if isinstance(evidence_path, str) else []
    )
    groups: dict[tuple[int, str], list[int]] = {}
    for sample in _valid_vram_samples(samples):
        groups.setdefault((sample["gpu_index"], sample["gpu_name"]), []).append(
            sample["used_mib"]
        )
    records: list[dict[str, Any]] = []
    for (gpu_index, gpu_name), used in groups.items():
        records.append(
            {
                "metric_id": _PEAK_VRAM_METRIC_ID,
                "native_metric_id": None,
                "value": max(used),
                "unit": "MiB",
                "availability": "available",
                "provenance": "calculated",
                "boundary": boundary,
                "equivalence": "unproven",
                "evidence_refs": evidence_refs,
                "calculation_semantics": PEAK_VRAM_CALCULATION,
                "device_scope": {"gpu_index": gpu_index, "gpu_name": gpu_name},
                "sample_count": len(used),
                "sampling_interval": "unknown",
            }
        )
    if not records:
        records.append(
            {
                "metric_id": _PEAK_VRAM_METRIC_ID,
                "native_metric_id": None,
                "value": None,
                "unit": "MiB",
                "availability": "unavailable",
                "provenance": "unavailable",
                "boundary": boundary,
                "equivalence": "unavailable",
                "evidence_refs": evidence_refs,
                "calculation_semantics": PEAK_VRAM_CALCULATION,
                "device_scope": None,
                "sample_count": 0,
                "sampling_interval": "unknown",
            }
        )
    return records


def native_execution_ref(index: int) -> str:
    return f"results/{index}"


def native_measurement_id(index: int) -> str:
    return f"native-single-turn-{index}"


def vllm_measurement_id(index: int) -> str:
    return f"vllm-request-{index}"


def _failure_category(failure: Mapping[str, Any]) -> str:
    if failure.get("phase") == "model_weight_load" and failure.get("oom") is True:
        return "model_weight_load_oom"
    if failure.get("phase") == "kv_cache" and failure.get("oom") is True:
        return "kv_cache_oom"
    if failure.get("launch_error") == "process_launch_failed":
        return "runtime_environment_failure"
    return "unclassified_unknown"


def _vllm_failure_category(failure_class: str | None) -> str:
    if isinstance(failure_class, str) and failure_class in _VLLM_FAILURE_CATEGORY_MAP:
        return _VLLM_FAILURE_CATEGORY_MAP[failure_class]
    return "unclassified_unknown"


def _native_failure(
    stdout: str,
    stderr: str,
    *,
    exit_status: int,
    timed_out: bool,
    launch_error: str | None,
) -> dict[str, Any] | None:
    if exit_status == 0 and not timed_out and launch_error is None:
        return None
    diagnostic = "\n".join((stdout, stderr))
    phase = None
    oom = False
    for line in diagnostic.splitlines():
        if _WEIGHT_LOAD_RE.search(line) and _OOM_RE.search(line):
            phase, oom = "model_weight_load", True
            break
        if _KV_CACHE_RE.search(line) and _OOM_RE.search(line):
            phase, oom = "kv_cache", True
            break
    return {
        "exit_status": exit_status,
        "timed_out": timed_out,
        "launch_error": launch_error,
        "phase": phase,
        "oom": oom,
    }


def _execution_placement(execution: Mapping[str, Any]) -> dict[str, Any]:
    placement = execution.get("llama_cpp_placement")
    if not isinstance(placement, Mapping):
        return {"requested": "unknown", "observed": "unknown"}
    observed = placement.get("observed")
    if observed not in placement_states():
        observed = "unknown"
    record: dict[str, Any] = {"requested": "unknown", "observed": observed}
    offloaded = placement.get("offloaded_layers")
    total = placement.get("total_layers")
    if isinstance(offloaded, int) and isinstance(total, int):
        record["native_offloaded_layers"] = offloaded
        record["native_total_layers"] = total
        source = placement.get("source")
        if isinstance(source, str) and source:
            record["native_source"] = source
    return record


def _validate_optional_timing(timing: object, label: str, errors: list[str]) -> None:
    if timing is None:
        return
    if not isinstance(timing, Mapping):
        errors.append(f"{label} must be an object when present")
        return
    seconds_fields = (
        "load_time_seconds",
        "prompt_eval_time_seconds",
        "eval_time_seconds",
        "total_time_seconds",
        "prompt_eval_tps",
        "generation_tps",
    )
    count_fields = ("prompt_eval_token_count", "eval_token_count")
    for field in seconds_fields:
        value = timing.get(field)
        if value is None:
            continue
        if (
            not isinstance(value, int | float)
            or isinstance(value, bool)
            or not math.isfinite(value)
            or value < 0
        ):
            errors.append(f"{label}.{field} must be finite and non-negative or null")
    for field in count_fields:
        value = timing.get(field)
        if value is None:
            continue
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            errors.append(f"{label}.{field} must be a non-negative integer or null")


def _validate_optional_placement(
    placement: object, label: str, errors: list[str]
) -> dict[str, Any] | None:
    if placement is None:
        return None
    if not isinstance(placement, Mapping):
        errors.append(f"{label} must be an object when present")
        return None
    observed = placement.get("observed")
    if observed not in placement_states():
        errors.append(f"{label}.observed is not an admitted placement state")
    offloaded = placement.get("offloaded_layers")
    total = placement.get("total_layers")
    if (offloaded is None) != (total is None):
        errors.append(f"{label} layer counts must both be present or both null")
    if offloaded is not None and (
        not isinstance(offloaded, int)
        or isinstance(offloaded, bool)
        or offloaded < 0
        or not isinstance(total, int)
        or isinstance(total, bool)
        or total < 0
        or offloaded > total
    ):
        errors.append(f"{label} layer counts are internally impossible")
    return dict(placement)


def build_native_execution_evidence(
    *,
    prompt_id: str,
    elapsed_seconds: float | None,
    stdout: str,
    stderr: str,
    exit_status: int,
    timed_out: bool,
    launch_error: str | None,
) -> dict[str, Any]:
    """Build bounded LLMGauge-observed evidence for one native process attempt."""
    valid_elapsed = (
        isinstance(elapsed_seconds, int | float)
        and not isinstance(elapsed_seconds, bool)
        and math.isfinite(elapsed_seconds)
        and elapsed_seconds >= 0
    )
    diagnostics = parse_llama_cpp_diagnostics(f"{stdout}\n{stderr}")
    return {
        "schema_version": NATIVE_EXECUTION_EVIDENCE_SCHEMA,
        "prompt_id": prompt_id,
        "request_wall_time_seconds": float(elapsed_seconds) if valid_elapsed else None,
        "request_wall_time_boundary": "process_launch_to_terminal_output_receipt",
        "llama_cpp_timing": diagnostics["llama_cpp_timing"],
        "llama_cpp_placement": diagnostics["llama_cpp_placement"],
        "failure": _native_failure(
            stdout,
            stderr,
            exit_status=exit_status,
            timed_out=timed_out,
            launch_error=launch_error,
        ),
    }


def build_area4_evidence(
    *,
    prompt_results: list[Mapping[str, Any]],
    suite: Mapping[str, Any],
    runtime: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build the first bounded Area 4 top-level representations."""
    measurements: list[dict[str, Any]] = []
    observations: list[dict[str, Any]] = []
    primary_by_execution: list[dict[str, Any]] = []
    for index, prompt_result in enumerate(prompt_results):
        execution_ref = native_execution_ref(index)
        evidence_path = prompt_result["native_execution_evidence_path"]
        execution = prompt_result["_area4_native_execution_evidence"]
        elapsed = execution["request_wall_time_seconds"]
        available = (
            isinstance(elapsed, float) and math.isfinite(elapsed) and elapsed >= 0
        )
        measurements.append(
            {
                "measurement_id": native_measurement_id(index),
                "execution_ref": execution_ref,
                "attempt_id": _ATTEMPT_ID,
                "attempt_sequence": 0,
                "kind": "measured",
                "retry_of_attempt_id": None,
                "completion_state": "timeout"
                if execution["failure"] and execution["failure"]["timed_out"]
                else (
                    "completed" if prompt_result["status"] == "completed" else "failed"
                ),
                "workload": {
                    "prompt_id": prompt_result["prompt_id"],
                    "suite_id": suite.get("suite_id"),
                    "suite_version": suite.get("suite_version"),
                    "request_form": "llama_cpp_cli_single_turn",
                    "generation_limits": {"max_tokens": runtime.get("max_tokens")},
                    "batching": {
                        "batch_size": runtime.get("batch_size"),
                        "ubatch_size": runtime.get("ubatch_size"),
                    },
                    "cache_state": "unknown",
                    "requested_runtime_settings_ref": "runtime",
                    "observed_runtime_settings_ref": None,
                },
                "execution_placement": _execution_placement(execution),
                "metrics": [
                    {
                        "metric_id": "llmgauge.metric.v1.request_wall_time",
                        "native_metric_id": "request_wall_time_seconds",
                        "value": elapsed if available else None,
                        "unit": "s",
                        "availability": "available" if available else "unavailable",
                        "provenance": "llmgauge_observed"
                        if available
                        else "unavailable",
                        "boundary": "request_transmit_to_validated_response",
                        "equivalence": "unproven" if available else "unavailable",
                        "evidence_refs": [
                            f"{evidence_path}#/request_wall_time_seconds"
                        ],
                    }
                ],
            }
        )
        vram_samples = prompt_result.get("_area4_vram_samples")
        if isinstance(vram_samples, list):
            measurements[-1]["metrics"].extend(
                _peak_vram_metric_records(
                    vram_samples, prompt_result.get("vram_samples_path")
                )
            )
        failure = execution["failure"]
        if failure is None:
            primary_by_execution.append(
                {
                    "execution_ref": execution_ref,
                    "primary_observation_id": None,
                    "state": "none",
                }
            )
            continue
        observation_id = f"native-failure-{index}"
        observations.append(
            {
                "failure_observation_id": observation_id,
                "execution_ref": execution_ref,
                "attempt_id": _ATTEMPT_ID,
                "retry_of_attempt_id": None,
                "category": _failure_category(failure),
                "source_fact_refs": [f"{evidence_path}#/failure"],
                "evidence_basis": {
                    "kind": "llmgauge_derived_native_execution_evidence",
                    "schema_version": NATIVE_EXECUTION_EVIDENCE_SCHEMA,
                },
                "execution_state": "terminal",
            }
        )
        primary_by_execution.append(
            {
                "execution_ref": execution_ref,
                "primary_observation_id": observation_id,
                "state": "classified",
            }
        )
    return (
        {
            "schema_version": RUNTIME_NEUTRAL_METRICS_SCHEMA,
            "measurements": measurements,
        },
        {
            "schema_version": FAILURE_TAXONOMY_SCHEMA,
            "observations": observations,
            "primary_by_execution": primary_by_execution,
        },
    )



def _ttft_metric_record(
    stream_evidence: Mapping[str, Any],
    stream_path: str | None,
) -> dict[str, Any] | None:
    """Derive the neutral TTFT metric record from preserved stream evidence.

    Returns None when the evidence cannot support an honest TTFT record
    (malformed structure, no first-token marker); an unavailable record is
    still emitted for an admitted streaming observation without a first token.
    """
    first_token = stream_evidence.get("first_token")
    if not isinstance(first_token, Mapping):
        return {
            "metric_id": TTFT_METRIC_ID,
            "native_metric_id": "time_to_first_token_seconds",
            "value": None,
            "unit": "s",
            "availability": "unavailable",
            "provenance": "unavailable",
            "boundary": TTFT_BOUNDARY,
            "equivalence": "unavailable",
            "evidence_refs": (
                [f"{stream_path}#/terminal/state"] if stream_path is not None else []
            ),
        }
    elapsed = first_token.get("elapsed_seconds")
    if (
        not isinstance(elapsed, int | float)
        or isinstance(elapsed, bool)
        or not math.isfinite(elapsed)
        or elapsed < 0
    ):
        return {
            "metric_id": TTFT_METRIC_ID,
            "native_metric_id": "time_to_first_token_seconds",
            "value": None,
            "unit": "s",
            "availability": "unavailable",
            "provenance": "unavailable",
            "boundary": TTFT_BOUNDARY,
            "equivalence": "unavailable",
            "evidence_refs": (
                [f"{stream_path}#/first_token/elapsed_seconds"]
                if stream_path is not None
                else []
            ),
        }
    return {
        "metric_id": TTFT_METRIC_ID,
        "native_metric_id": "time_to_first_token_seconds",
        "value": float(elapsed),
        "unit": "s",
        "availability": "available",
        "provenance": "llmgauge_observed",
        "boundary": TTFT_BOUNDARY,
        "equivalence": "unproven",
        "channel": first_token.get("channel"),
        "evidence_refs": (
            [f"{stream_path}#/first_token/elapsed_seconds"]
            if stream_path is not None
            else []
        ),
    }


def build_vllm_area4_evidence(
    *,
    prompt_results: list[Mapping[str, Any]],
    suite: Mapping[str, Any],
    runtime: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build Area 4 representations for vLLM per-request evidence.

    The vLLM request_wall_time metric is always represented for transmitted
    requests. Request transmission and complete response validation both fall
    inside its boundary. Execution placement and cache state stay unknown
    because the vLLM API does not expose them. When a request-window VRAM
    sample artifact exists for a transmitted request, one calculated peak-VRAM
    record per observed device is added under the request-window observation
    boundary; an attempted sampler with no valid samples yields an unavailable
    record, and an untransmitted request yields no peak record.
    """
    measurements: list[dict[str, Any]] = []
    observations: list[dict[str, Any]] = []
    primary_by_execution: list[dict[str, Any]] = []
    for index, prompt_result in enumerate(prompt_results):
        execution_ref = native_execution_ref(index)
        evidence = prompt_result.get("_area4_vllm_request_evidence")
        if not isinstance(evidence, Mapping):
            evidence = {}
        request_evidence_path = prompt_result.get("request_evidence_path")
        if not isinstance(request_evidence_path, str) or not request_evidence_path:
            request_evidence_path = None
        wall = evidence.get("request_wall_time_seconds")
        transmitted = evidence.get("request_transmitted", False) is True
        available = (
            transmitted
            and isinstance(wall, int | float)
            and not isinstance(wall, bool)
            and math.isfinite(wall)
            and wall >= 0
        )
        status = prompt_result.get("status")
        failure_class = evidence.get("failure_class") or prompt_result.get(
            "failure_class"
        )
        if status == "completed":
            completion_state = "completed"
        elif failure_class == "request_timeout":
            completion_state = "timeout"
        else:
            completion_state = "failed"
        measurement: dict[str, Any] = {
            "measurement_id": vllm_measurement_id(index),
            "execution_ref": execution_ref,
            "attempt_id": _ATTEMPT_ID,
            "attempt_sequence": 0,
            "kind": "measured",
            "retry_of_attempt_id": None,
            "completion_state": completion_state,
            "workload": {
                "prompt_id": prompt_result.get("prompt_id"),
                "suite_id": suite.get("suite_id"),
                "suite_version": suite.get("suite_version"),
                "request_form": _VLLM_REQUEST_FORM,
                "generation_limits": {"max_tokens": runtime.get("max_tokens")},
                "batching": {"batch_size": 1},
                "cache_state": "unknown",
                "requested_runtime_settings_ref": "runtime",
                "observed_runtime_settings_ref": None,
            },
            "execution_placement": {"requested": "unknown", "observed": "unknown"},
            "metrics": [
                {
                    "metric_id": "llmgauge.metric.v1.request_wall_time",
                    "native_metric_id": "request_wall_time_seconds",
                    "value": float(wall) if available else None,
                    "unit": "s",
                    "availability": "available" if available else "unavailable",
                    "provenance": "llmgauge_observed" if available else "unavailable",
                    "boundary": "request_transmit_to_validated_response",
                    "equivalence": "unproven" if available else "unavailable",
                    "evidence_refs": (
                        [f"{request_evidence_path}#/request_wall_time_seconds"]
                        if request_evidence_path is not None
                        else []
                    ),
                }
            ],
        }
        measurements.append(measurement)
        vram_samples = prompt_result.get("_area4_vram_samples")
        if transmitted and isinstance(vram_samples, list):
            measurements[-1]["metrics"].extend(
                _peak_vram_metric_records(
                    vram_samples,
                    prompt_result.get("vram_samples_path"),
                    boundary=VLLM_PEAK_VRAM_BOUNDARY,
                )
            )
        # Neutral TTFT: represented only when streaming evidence was admitted.
        stream_evidence = prompt_result.get("_area4_vllm_stream_evidence")
        stream_path = prompt_result.get("stream_evidence_path")
        streaming = evidence.get("streaming") is True
        if streaming and isinstance(stream_evidence, Mapping):
            ttft_record = _ttft_metric_record(
                stream_evidence,
                stream_path if isinstance(stream_path, str) else None,
            )
            if ttft_record is not None:
                measurements[-1]["metrics"].append(ttft_record)
        if status == "completed":
            primary_by_execution.append(
                {
                    "execution_ref": execution_ref,
                    "primary_observation_id": None,
                    "state": "none",
                }
            )
            continue
        observation_id = f"vllm-failure-{index}"
        observations.append(
            {
                "failure_observation_id": observation_id,
                "execution_ref": execution_ref,
                "attempt_id": _ATTEMPT_ID,
                "retry_of_attempt_id": None,
                "category": _vllm_failure_category(failure_class),
                "source_fact_refs": (
                    [f"{request_evidence_path}#/failure_class"]
                    if request_evidence_path is not None
                    else []
                ),
                "evidence_basis": {
                    "kind": "llmgauge_derived_vllm_request_evidence",
                    "schema_version": VLLM_REQUEST_EVIDENCE_SCHEMA,
                },
                "execution_state": "terminal",
            }
        )
        primary_by_execution.append(
            {
                "execution_ref": execution_ref,
                "primary_observation_id": observation_id,
                "state": "classified",
            }
        )
    return (
        {
            "schema_version": RUNTIME_NEUTRAL_METRICS_SCHEMA,
            "measurements": measurements,
        },
        {
            "schema_version": FAILURE_TAXONOMY_SCHEMA,
            "observations": observations,
            "primary_by_execution": primary_by_execution,
        },
    )


def _load_native_evidence(
    result_dir: Path, prompt_results: list[object], errors: list[str]
) -> dict[str, tuple[str, Mapping[str, Any]]]:
    from llmgauge.core.run_fingerprint import (
        FingerprintUnavailable,
        resolve_contained_result_artifact,
    )

    loaded: dict[str, tuple[str, Mapping[str, Any]]] = {}
    for index, prompt_result in enumerate(prompt_results):
        if not isinstance(prompt_result, Mapping):
            continue
        execution_ref = native_execution_ref(index)
        path = prompt_result.get("native_execution_evidence_path")
        if not isinstance(path, str) or not path:
            errors.append(f"{execution_ref}.native_execution_evidence_path must be set")
            continue
        try:
            artifact = resolve_contained_result_artifact(
                result_dir,
                path,
                label=f"{execution_ref}.native_execution_evidence_path",
                require_file=True,
            )
            evidence = json.loads(artifact.read_text(encoding="utf-8"))
        except (FingerprintUnavailable, json.JSONDecodeError) as exc:
            errors.append(
                f"{execution_ref}.native_execution_evidence_path is invalid: {exc}"
            )
            continue
        if not isinstance(evidence, Mapping):
            errors.append(
                f"{execution_ref} native execution evidence must be an object"
            )
            continue
        if evidence.get(
            "schema_version"
        ) != NATIVE_EXECUTION_EVIDENCE_SCHEMA or evidence.get(
            "prompt_id"
        ) != prompt_result.get("prompt_id"):
            errors.append(
                f"{execution_ref} native execution evidence identity is invalid"
            )
        elapsed = evidence.get("request_wall_time_seconds")
        if elapsed is not None and (
            not isinstance(elapsed, int | float)
            or isinstance(elapsed, bool)
            or not math.isfinite(elapsed)
            or elapsed < 0
        ):
            errors.append(f"{execution_ref} native request wall time is invalid")
        loaded[execution_ref] = (path, evidence)
    return loaded


def _load_vram_samples(
    result_dir: Path, prompt_results: list[object], errors: list[str]
) -> dict[str, list[Any] | None]:
    from llmgauge.core.run_fingerprint import (
        FingerprintUnavailable,
        resolve_contained_result_artifact,
    )

    loaded: dict[str, list[Any] | None] = {}
    for index, prompt_result in enumerate(prompt_results):
        if not isinstance(prompt_result, Mapping):
            continue
        execution_ref = native_execution_ref(index)
        path = prompt_result.get("vram_samples_path")
        if not isinstance(path, str) or not path:
            loaded[execution_ref] = None
            continue
        try:
            artifact = resolve_contained_result_artifact(
                result_dir,
                path,
                label=f"{execution_ref}.vram_samples_path",
                require_file=True,
            )
            payload = json.loads(artifact.read_text(encoding="utf-8"))
        except (FingerprintUnavailable, json.JSONDecodeError) as exc:
            errors.append(f"{execution_ref}.vram_samples_path is invalid: {exc}")
            loaded[execution_ref] = None
            continue
        samples = payload.get("samples") if isinstance(payload, Mapping) else None
        if not isinstance(samples, list):
            errors.append(f"{execution_ref} vram samples artifact is invalid")
            loaded[execution_ref] = None
            continue
        loaded[execution_ref] = samples
    return loaded


def _load_vllm_request_evidence(
    result_dir: Path, prompt_results: list[object], errors: list[str]
) -> dict[str, tuple[str, Mapping[str, Any]]]:
    from llmgauge.core.run_fingerprint import (
        FingerprintUnavailable,
        resolve_contained_result_artifact,
    )

    loaded: dict[str, tuple[str, Mapping[str, Any]]] = {}
    for index, prompt_result in enumerate(prompt_results):
        if not isinstance(prompt_result, Mapping):
            continue
        execution_ref = native_execution_ref(index)
        path = prompt_result.get("request_evidence_path")
        if not isinstance(path, str) or not path:
            errors.append(f"{execution_ref}.request_evidence_path must be set")
            continue
        try:
            artifact = resolve_contained_result_artifact(
                result_dir,
                path,
                label=f"{execution_ref}.request_evidence_path",
                require_file=True,
            )
            evidence = json.loads(artifact.read_text(encoding="utf-8"))
        except (FingerprintUnavailable, json.JSONDecodeError) as exc:
            errors.append(f"{execution_ref}.request_evidence_path is invalid: {exc}")
            continue
        if not isinstance(evidence, Mapping):
            errors.append(f"{execution_ref} vLLM request evidence must be an object")
            continue
        if evidence.get("schema_version") != VLLM_REQUEST_EVIDENCE_SCHEMA:
            errors.append(
                f"{execution_ref} vLLM request evidence schema_version is invalid"
            )
        loaded[execution_ref] = (path, evidence)
    return loaded


def _load_vllm_stream_evidence(
    result_dir: Path, prompt_results: list[object], errors: list[str]
) -> dict[str, tuple[str, Mapping[str, Any]] | None]:
    """Load preserved stream evidence for each vLLM execution when present."""
    from llmgauge.core.run_fingerprint import (
        FingerprintUnavailable,
        resolve_contained_result_artifact,
    )

    loaded: dict[str, tuple[str, Mapping[str, Any]] | None] = {}
    for index, prompt_result in enumerate(prompt_results):
        if not isinstance(prompt_result, Mapping):
            continue
        execution_ref = native_execution_ref(index)
        path = prompt_result.get("stream_evidence_path")
        if not isinstance(path, str) or not path:
            loaded[execution_ref] = None
            continue
        try:
            artifact = resolve_contained_result_artifact(
                result_dir,
                path,
                label=f"{execution_ref}.stream_evidence_path",
                require_file=True,
            )
            evidence = json.loads(artifact.read_text(encoding="utf-8"))
        except (FingerprintUnavailable, json.JSONDecodeError) as exc:
            errors.append(f"{execution_ref}.stream_evidence_path is invalid: {exc}")
            loaded[execution_ref] = None
            continue
        if not isinstance(evidence, Mapping):
            errors.append(f"{execution_ref} vLLM stream evidence must be an object")
            loaded[execution_ref] = None
            continue
        if evidence.get("schema_version") != VLLM_STREAM_EVIDENCE_SCHEMA:
            errors.append(
                f"{execution_ref} vLLM stream evidence schema_version "
                f"must be {VLLM_STREAM_EVIDENCE_SCHEMA}"
            )
        loaded[execution_ref] = (path, evidence)
    return loaded

def validate_area4_evidence(result_dir: Path, data: Mapping[str, object]) -> list[str]:
    """Validate represented Area 4 evidence without changing legacy requirements."""
    metrics, taxonomy = (
        data.get("runtime_neutral_metrics"),
        data.get("failure_taxonomy"),
    )
    if metrics is None and taxonomy is None:
        return []
    if not isinstance(metrics, Mapping) or not isinstance(taxonomy, Mapping):
        return [
            "Area 4 evidence requires both runtime_neutral_metrics and failure_taxonomy objects"
        ]
    runtime = data.get("runtime")
    if not isinstance(runtime, Mapping):
        return ["Area 4 evidence requires runtime metadata"]
    backend = runtime.get("backend")
    if backend not in {"llama.cpp", "vllm"}:
        return [
            "Area 4 evidence is supported only for native llama.cpp or vLLM results"
        ]
    if (
        data.get("transcript") is not None
        or data.get("agent_harness_evidence") is not None
        or data.get("external_benchmark_evidence") is not None
    ):
        return [
            "Area 4 evidence is unsupported for transcript, Agent Harness, "
            "or external benchmark results"
        ]
    if backend == "vllm":
        return _validate_vllm_area4_evidence(result_dir, data, metrics, taxonomy)
    errors: list[str] = []
    prompt_results = data.get("results")
    if not isinstance(prompt_results, list):
        return errors + ["Area 4 evidence requires prompt results"]
    known_executions = {
        native_execution_ref(index) for index in range(len(prompt_results))
    }
    native = _load_native_evidence(result_dir, prompt_results, errors)
    vram_samples_by_execution = _load_vram_samples(result_dir, prompt_results, errors)

    measurements = metrics.get("measurements")
    if metrics.get(
        "schema_version"
    ) != RUNTIME_NEUTRAL_METRICS_SCHEMA or not isinstance(measurements, list):
        errors.append(
            "runtime_neutral_metrics schema_version or measurements is invalid"
        )
        measurements = []
    if len(measurements) != len(prompt_results):
        errors.append(
            "runtime_neutral_metrics must contain one measurement per prompt result"
        )
    seen_measurements: set[str] = set()
    for index, measurement in enumerate(measurements):
        label = f"runtime_neutral_metrics.measurements[{index}]"
        if not isinstance(measurement, Mapping):
            errors.append(f"{label} must be an object")
            continue
        execution_ref = measurement.get("execution_ref")
        if (
            execution_ref not in known_executions
            or measurement.get("measurement_id")
            != native_measurement_id(int(str(execution_ref).removeprefix("results/")))
            if isinstance(execution_ref, str)
            and _EXECUTION_REF_RE.fullmatch(execution_ref)
            else True
        ):
            errors.append(f"{label} has invalid measurement or execution identity")
        if (
            measurement.get("attempt_id") != _ATTEMPT_ID
            or measurement.get("attempt_sequence") != 0
            or measurement.get("retry_of_attempt_id") is not None
            or measurement.get("kind") != "measured"
            or measurement.get("completion_state")
            not in {"completed", "failed", "timeout"}
        ):
            errors.append(f"{label} has invalid attempt semantics")
        measurement_id = measurement.get("measurement_id")
        if (
            not isinstance(measurement_id, str)
            or not _MEASUREMENT_ID_RE.fullmatch(measurement_id)
            or measurement_id in seen_measurements
        ):
            errors.append(f"{label}.measurement_id must be unique")
        seen_measurements.add(str(measurement_id))
        if not isinstance(measurement.get("workload"), Mapping) or not isinstance(
            measurement.get("execution_placement"), Mapping
        ):
            errors.append(f"{label}.workload and execution_placement must be objects")
        else:
            placement = measurement["execution_placement"]
            requested = placement.get("requested")
            observed = placement.get("observed")
            if (
                requested not in placement_states()
                or observed not in placement_states()
            ):
                errors.append(
                    f"{label}.execution_placement requested/observed is invalid"
                )
            if requested != "unknown":
                errors.append(
                    f"{label}.execution_placement.requested must remain unknown; "
                    "requested GPU layers are not observed placement"
                )
            evidence_pair = native.get(str(execution_ref))
            if evidence_pair is not None:
                native_evidence = evidence_pair[1]
                _validate_optional_timing(
                    native_evidence.get("llama_cpp_timing"),
                    f"{label} native llama_cpp_timing",
                    errors,
                )
                native_placement = _validate_optional_placement(
                    native_evidence.get("llama_cpp_placement"),
                    f"{label} native llama_cpp_placement",
                    errors,
                )
                if native_placement is not None:
                    if observed != native_placement.get("observed"):
                        errors.append(
                            f"{label}.execution_placement.observed differs from "
                            "native placement evidence"
                        )
                    native_off = native_placement.get("offloaded_layers")
                    native_total = native_placement.get("total_layers")
                    if native_off is None:
                        if (
                            "native_offloaded_layers" in placement
                            or "native_total_layers" in placement
                        ):
                            errors.append(
                                f"{label}.execution_placement must not invent "
                                "native layer counts"
                            )
                    elif (
                        placement.get("native_offloaded_layers") != native_off
                        or placement.get("native_total_layers") != native_total
                    ):
                        errors.append(
                            f"{label}.execution_placement native layer counts "
                            "differ from native evidence"
                        )

        records = measurement.get("metrics")
        if (
            not isinstance(records, list)
            or len(records) < 1
            or not isinstance(records[0], Mapping)
        ):
            errors.append(f"{label}.metrics must contain at least one record")
            continue
        metric = records[0]
        evidence = native.get(str(execution_ref))
        expected_ref = f"{evidence[0]}#/request_wall_time_seconds" if evidence else None
        available = metric.get("availability") == "available"
        value = metric.get("value")
        if (
            metric.get("metric_id") != "llmgauge.metric.v1.request_wall_time"
            or metric.get("native_metric_id") != "request_wall_time_seconds"
            or metric.get("unit") != "s"
            or metric.get("boundary") != "request_transmit_to_validated_response"
            or metric.get("evidence_refs") != [expected_ref]
        ):
            errors.append(
                f"{label}.metrics[0] identity or evidence reference is invalid"
            )
        if available:
            if (
                not isinstance(value, int | float)
                or isinstance(value, bool)
                or not math.isfinite(value)
                or value < 0
                or metric.get("provenance") != "llmgauge_observed"
                or metric.get("equivalence") != "unproven"
            ):
                errors.append(
                    f"{label}.metrics[0] available value/provenance is invalid"
                )
        elif (
            value is not None
            or metric.get("availability") != "unavailable"
            or metric.get("provenance") != "unavailable"
            or metric.get("equivalence") != "unavailable"
        ):
            errors.append(f"{label}.metrics[0] unavailable value/provenance is invalid")
        if evidence is not None and value != evidence[1].get(
            "request_wall_time_seconds"
        ):
            errors.append(f"{label}.metrics[0].value differs from native evidence")
        vram_samples = vram_samples_by_execution.get(str(execution_ref))
        expected_peak_records: list[dict[str, Any]] = []
        if vram_samples is not None:
            prompt_result = prompt_results[
                int(str(execution_ref).removeprefix("results/"))
            ]
            vram_path = (
                prompt_result.get("vram_samples_path")
                if isinstance(prompt_result, Mapping)
                else None
            )
            expected_peak_records = _peak_vram_metric_records(
                vram_samples,
                vram_path if isinstance(vram_path, str) else None,
            )
        if records[1:]:
            # Wall-time-only measurements remain valid (historical results).
            # Once peak VRAM records are represented they must match the
            # preserved samples evidence exactly.
            if records[1:] != expected_peak_records:
                errors.append(
                    f"{label}.metrics peak VRAM records differ from the "
                    "preserved vram samples evidence"
                )

    observations, primary = (
        taxonomy.get("observations"),
        taxonomy.get("primary_by_execution"),
    )
    if (
        taxonomy.get("schema_version") != FAILURE_TAXONOMY_SCHEMA
        or not isinstance(observations, list)
        or not isinstance(primary, list)
    ):
        return errors + [
            "failure_taxonomy schema_version, observations, or primary_by_execution is invalid"
        ]
    observation_ids: set[str] = set()
    observation_executions: dict[str, str] = {}
    for index, observation in enumerate(observations):
        label = f"failure_taxonomy.observations[{index}]"
        if not isinstance(observation, Mapping):
            errors.append(f"{label} must be an object")
            continue
        observation_id, execution_ref = (
            observation.get("failure_observation_id"),
            observation.get("execution_ref"),
        )
        if (
            not isinstance(observation_id, str)
            or not observation_id
            or observation_id in observation_ids
            or execution_ref not in known_executions
        ):
            errors.append(f"{label} has invalid identity or execution reference")
        observation_ids.add(str(observation_id))
        observation_executions[str(observation_id)] = str(execution_ref)
        evidence = native.get(str(execution_ref))
        expected_ref = f"{evidence[0]}#/failure" if evidence else None
        failure = evidence[1].get("failure") if evidence else None
        if (
            observation.get("attempt_id") != _ATTEMPT_ID
            or observation.get("retry_of_attempt_id") is not None
            or observation.get("execution_state") != "terminal"
            or not isinstance(observation.get("evidence_basis"), Mapping)
            or observation.get("source_fact_refs") != [expected_ref]
        ):
            errors.append(f"{label} has invalid structure or evidence reference")
        if not isinstance(failure, Mapping) or observation.get(
            "category"
        ) != _failure_category(failure):
            errors.append(f"{label}.category differs from native evidence")
    primary_executions: set[str] = set()
    for index, entry in enumerate(primary):
        label = f"failure_taxonomy.primary_by_execution[{index}]"
        if (
            not isinstance(entry, Mapping)
            or entry.get("execution_ref") not in known_executions
            or entry.get("execution_ref") in primary_executions
        ):
            errors.append(f"{label} must uniquely reference a prompt result")
            continue
        execution_ref, state, observation_id = (
            entry["execution_ref"],
            entry.get("state"),
            entry.get("primary_observation_id"),
        )
        primary_executions.add(str(execution_ref))
        failure = native.get(str(execution_ref), (None, {}))[1].get("failure")
        if isinstance(failure, Mapping):
            if (
                state != "classified"
                or observation_executions.get(str(observation_id)) != execution_ref
            ):
                errors.append(
                    f"{label} failed execution must reference its classification"
                )
        elif state != "none" or observation_id is not None:
            errors.append(f"{label} completed execution must have no classification")
    if primary_executions != known_executions:
        errors.append("failure_taxonomy must classify every prompt execution")
    return errors


FIRST_TOKEN_CHANNELS = frozenset({"reasoning", "content", "other_generated"})


def _expected_ttft_record(
    stream_evidence: Mapping[str, Any],
    stream_path: str | None,
    label: str,
    errors: list[str],
) -> dict[str, Any] | None:
    """Recompute the neutral TTFT record from preserved stream evidence.

    Validates: streamed transport admitted, observation-method identity,
    version qualification, `return_token_ids` representation, the first
    token-bearing event, elapsed finiteness/non-negativity, closed channel
    vocabulary, and the absence of any earlier token-bearing event.
    Returns None (with errors appended) when the evidence is malformed.
    """
    if (
        stream_evidence.get("transport_mode") != "openai_compatible_sse"
        or stream_evidence.get("streaming") is not True
    ):
        errors.append(f"{label} stream evidence transport identity is invalid")
        return None
    if stream_evidence.get("observation_method") != VLLM_STREAM_EVIDENCE_SCHEMA:
        errors.append(f"{label} stream evidence observation method is invalid")
        return None
    if stream_evidence.get("return_token_ids") is not True:
        errors.append(f"{label} stream evidence return_token_ids is not represented")
        return None
    version_qual = stream_evidence.get("version_qualification")
    if (
        not isinstance(version_qual, Mapping)
        or version_qual.get("admitted") is not True
    ):
        errors.append(f"{label} stream evidence version qualification is invalid")
        return None

    events = stream_evidence.get("events")
    if not isinstance(events, list):
        errors.append(f"{label} stream evidence events must be a list")
        return None
    first_token = stream_evidence.get("first_token")
    if first_token is None:
        # No token: verify no event carries token evidence, then an
        # unavailable TTFT record is expected.
        for event in events:
            if isinstance(event, Mapping) and event.get("token_ids_count"):
                errors.append(
                    f"{label} stream evidence has a token event but no "
                    "first_token marker"
                )
                return None
        return {
            "metric_id": TTFT_METRIC_ID,
            "native_metric_id": "time_to_first_token_seconds",
            "value": None,
            "unit": "s",
            "availability": "unavailable",
            "provenance": "unavailable",
            "boundary": TTFT_BOUNDARY,
            "equivalence": "unavailable",
            "evidence_refs": (
                [f"{stream_path}#/terminal/state"] if stream_path is not None else []
            ),
        }
    if not isinstance(first_token, Mapping):
        errors.append(f"{label} stream evidence first_token must be an object")
        return None
    first_index = first_token.get("event_index")
    elapsed = first_token.get("elapsed_seconds")
    channel = first_token.get("channel")
    if (
        not isinstance(first_index, int)
        or isinstance(first_index, bool)
        or first_index < 0
        or first_index >= len(events)
    ):
        errors.append(f"{label} stream evidence first_token event_index is invalid")
        return None
    if (
        not isinstance(elapsed, int | float)
        or isinstance(elapsed, bool)
        or not math.isfinite(elapsed)
        or elapsed < 0
    ):
        errors.append(f"{label} stream evidence first_token elapsed is invalid")
        return None
    if channel not in FIRST_TOKEN_CHANNELS:
        errors.append(f"{label} stream evidence first_token channel is invalid")
        return None
    # The first token-bearing event must be the recorded first_token, and no
    # earlier event may carry token evidence.
    first_token_event = events[first_index]
    if not isinstance(first_token_event, Mapping):
        errors.append(f"{label} stream evidence first_token event is invalid")
        return None
    if not first_token_event.get("token_ids_count"):
        errors.append(
            f"{label} stream evidence first_token event has no token evidence"
        )
        return None
    if first_token_event.get("ttft_trigger") is not True:
        errors.append(f"{label} stream evidence first_token event is not marked")
        return None
    for event in events[:first_index]:
        if isinstance(event, Mapping) and event.get("token_ids_count"):
            errors.append(f"{label} stream evidence has an earlier token-bearing event")
            return None
    event_elapsed = first_token_event.get("elapsed_seconds")
    if event_elapsed != elapsed:
        errors.append(
            f"{label} stream evidence first_token elapsed differs from its event"
        )
        return None
    return {
        "metric_id": TTFT_METRIC_ID,
        "native_metric_id": "time_to_first_token_seconds",
        "value": float(elapsed),
        "unit": "s",
        "availability": "available",
        "provenance": "llmgauge_observed",
        "boundary": TTFT_BOUNDARY,
        "equivalence": "unproven",
        "channel": channel,
        "evidence_refs": (
            [f"{stream_path}#/first_token/elapsed_seconds"]
            if stream_path is not None
            else []
        ),
    }


def _validate_vllm_area4_evidence(
    result_dir: Path,
    data: Mapping[str, object],
    metrics: Mapping[str, object],
    taxonomy: Mapping[str, object],
) -> list[str]:
    """Validate vLLM Area 4 evidence against preserved request evidence."""
    errors: list[str] = []
    prompt_results = data.get("results")
    if not isinstance(prompt_results, list):
        return errors + ["Area 4 evidence requires prompt results"]
    known_executions = {
        native_execution_ref(index) for index in range(len(prompt_results))
    }
    request_evidence_by_execution = _load_vllm_request_evidence(
        result_dir, prompt_results, errors
    )
    stream_evidence_by_execution = _load_vllm_stream_evidence(
        result_dir, prompt_results, errors
    )
    vram_samples_by_execution = _load_vram_samples(result_dir, prompt_results, errors)

    measurements = metrics.get("measurements")
    if metrics.get(
        "schema_version"
    ) != RUNTIME_NEUTRAL_METRICS_SCHEMA or not isinstance(measurements, list):
        errors.append(
            "runtime_neutral_metrics schema_version or measurements is invalid"
        )
        measurements = []
    if len(measurements) != len(prompt_results):
        errors.append(
            "runtime_neutral_metrics must contain one measurement per prompt result"
        )
    seen_measurements: set[str] = set()
    failed_executions: set[str] = set()
    for index, measurement in enumerate(measurements):
        label = f"runtime_neutral_metrics.measurements[{index}]"
        if not isinstance(measurement, Mapping):
            errors.append(f"{label} must be an object")
            continue
        execution_ref = measurement.get("execution_ref")
        if (
            execution_ref not in known_executions
            or measurement.get("measurement_id") != vllm_measurement_id(index)
            or measurement.get("attempt_id") != _ATTEMPT_ID
            or measurement.get("attempt_sequence") != 0
            or measurement.get("retry_of_attempt_id") is not None
            or measurement.get("kind") != "measured"
            or measurement.get("completion_state")
            not in {
                "completed",
                "failed",
                "timeout",
            }
        ):
            errors.append(f"{label} has invalid measurement or execution identity")
        measurement_id = measurement.get("measurement_id")
        if (
            not isinstance(measurement_id, str)
            or not _VLLM_MEASUREMENT_ID_RE.fullmatch(measurement_id)
            or measurement_id in seen_measurements
        ):
            errors.append(f"{label}.measurement_id must be unique")
        seen_measurements.add(str(measurement_id))
        completion_state = measurement.get("completion_state", "")
        if completion_state in {"failed", "timeout"}:
            failed_executions.add(str(execution_ref))
        if not isinstance(measurement.get("workload"), Mapping) or not isinstance(
            measurement.get("execution_placement"), Mapping
        ):
            errors.append(f"{label}.workload and execution_placement must be objects")
        else:
            placement = measurement["execution_placement"]
            requested = placement.get("requested")
            observed = placement.get("observed")
            if requested != "unknown" or observed != "unknown":
                errors.append(
                    f"{label}.execution_placement must be unknown for vLLM; "
                    "the API does not expose placement"
                )

        records = measurement.get("metrics")
        if (
            not isinstance(records, list)
            or len(records) < 1
            or not isinstance(records[0], Mapping)
        ):
            errors.append(f"{label}.metrics must contain at least one record")
            continue
        metric = records[0]
        evidence = request_evidence_by_execution.get(str(execution_ref))
        expected_ref = f"{evidence[0]}#/request_wall_time_seconds" if evidence else None
        available = metric.get("availability") == "available"
        value = metric.get("value")
        if (
            metric.get("metric_id") != "llmgauge.metric.v1.request_wall_time"
            or metric.get("native_metric_id") != "request_wall_time_seconds"
            or metric.get("unit") != "s"
            or metric.get("boundary") != "request_transmit_to_validated_response"
            or metric.get("evidence_refs") != [expected_ref]
        ):
            errors.append(
                f"{label}.metrics[0] identity or evidence reference is invalid"
            )
        if available:
            if (
                not isinstance(value, int | float)
                or isinstance(value, bool)
                or not math.isfinite(value)
                or value < 0
                or metric.get("provenance") != "llmgauge_observed"
                or metric.get("equivalence") != "unproven"
            ):
                errors.append(
                    f"{label}.metrics[0] available value/provenance is invalid"
                )
        elif (
            value is not None
            or metric.get("availability") != "unavailable"
            or metric.get("provenance") != "unavailable"
            or metric.get("equivalence") != "unavailable"
        ):
            errors.append(f"{label}.metrics[0] unavailable value/provenance is invalid")
        if evidence is not None and value != evidence[1].get(
            "request_wall_time_seconds"
        ):
            errors.append(f"{label}.metrics[0].value differs from request evidence")
        vram_samples = vram_samples_by_execution.get(str(execution_ref))
        expected_peak_records: list[dict[str, Any]] = []
        if vram_samples is not None:
            prompt_result = prompt_results[
                int(str(execution_ref).removeprefix("results/"))
            ]
            vram_path = (
                prompt_result.get("vram_samples_path")
                if isinstance(prompt_result, Mapping)
                else None
            )
            expected_peak_records = _peak_vram_metric_records(
                vram_samples,
                vram_path if isinstance(vram_path, str) else None,
                boundary=VLLM_PEAK_VRAM_BOUNDARY,
            )
        # TTFT: recompute from preserved stream evidence.
        stream_pair = stream_evidence_by_execution.get(str(execution_ref))
        stream_path = stream_pair[0] if stream_pair is not None else None
        stream_evidence = stream_pair[1] if stream_pair is not None else None
        streaming_evidence_flag = (
            isinstance(evidence, tuple)
            and len(evidence) == 2
            and isinstance(evidence[1], Mapping)
            and evidence[1].get("streaming") is True
        )
        expected_ttft: dict[str, Any] | None = None
        if streaming_evidence_flag:
            req_claims_ttft = (
                isinstance(evidence, tuple)
                and len(evidence) == 2
                and isinstance(evidence[1], Mapping)
                and (
                    evidence[1].get("time_to_first_token_seconds") is not None
                    or evidence[1].get("first_token_channel") is not None
                )
            )
            if stream_evidence is None and req_claims_ttft:
                errors.append(
                    f"{label} TTFT claim is missing stream evidence"
                )
            elif stream_evidence is not None:
                expected_ttft = _expected_ttft_record(
                    stream_evidence,
                    stream_path,
                    label,
                    errors,
                )
                if expected_ttft is None:
                    errors.append(
                        f"{label} TTFT cannot be recomputed from stream evidence"
                    )
                    expected_ttft = {
                        "metric_id": TTFT_METRIC_ID,
                        "native_metric_id": "time_to_first_token_seconds",
                        "value": None,
                        "unit": "s",
                        "availability": "unavailable",
                        "provenance": "unavailable",
                        "boundary": TTFT_BOUNDARY,
                        "equivalence": "unavailable",
                        "evidence_refs": (
                            [f"{stream_path}#/terminal/state"]
                            if stream_path is not None
                            else []
                        ),
                    }
        represented_ttft = [
            record
            for record in records[1:]
            if isinstance(record, dict)
            and record.get("metric_id") == TTFT_METRIC_ID
        ]
        if represented_ttft and expected_ttft is None:
            errors.append(
                f"{label} TTFT must not be represented without streaming evidence"
            )
        if not streaming_evidence_flag and represented_ttft:
            errors.append(
                f"{label} TTFT must not be represented for non-streaming evidence"
            )
        if (
            expected_ttft is not None
            and isinstance(evidence, tuple)
            and len(evidence) == 2
            and isinstance(evidence[1], Mapping)
            and expected_ttft.get("availability") == "available"
        ):
            req_channel = evidence[1].get("first_token_channel")
            if req_channel is not None and isinstance(stream_evidence, Mapping):
                stream_first = stream_evidence.get("first_token")
                stream_channel = (
                    stream_first.get("channel")
                    if isinstance(stream_first, Mapping)
                    else None
                )
                if req_channel != stream_channel:
                    errors.append(
                        f"{label} request-evidence first_token_channel differs "
                        "from stream evidence"
                    )
        expected_tail = expected_peak_records + (
            [expected_ttft] if expected_ttft is not None else []
        )
        if records[1:] != expected_tail:
            errors.append(
                f"{label}.metrics records differ from the preserved evidence "
                "(peak VRAM records differ or TTFT mismatch)"
            )

    observations, primary = (
        taxonomy.get("observations"),
        taxonomy.get("primary_by_execution"),
    )
    if (
        taxonomy.get("schema_version") != FAILURE_TAXONOMY_SCHEMA
        or not isinstance(observations, list)
        or not isinstance(primary, list)
    ):
        return errors + [
            "failure_taxonomy schema_version, observations, or "
            "primary_by_execution is invalid"
        ]
    observation_ids: set[str] = set()
    observation_executions: dict[str, str] = {}
    for index, observation in enumerate(observations):
        label = f"failure_taxonomy.observations[{index}]"
        if not isinstance(observation, Mapping):
            errors.append(f"{label} must be an object")
            continue
        observation_id, execution_ref = (
            observation.get("failure_observation_id"),
            observation.get("execution_ref"),
        )
        if (
            not isinstance(observation_id, str)
            or not observation_id
            or observation_id in observation_ids
            or execution_ref not in known_executions
        ):
            errors.append(f"{label} has invalid identity or execution reference")
        observation_ids.add(str(observation_id))
        observation_executions[str(observation_id)] = str(execution_ref)
        evidence = request_evidence_by_execution.get(str(execution_ref))
        expected_ref = f"{evidence[0]}#/failure_class" if evidence else None
        failure_class = evidence[1].get("failure_class") if evidence else None
        if (
            observation.get("attempt_id") != _ATTEMPT_ID
            or observation.get("retry_of_attempt_id") is not None
            or observation.get("execution_state") != "terminal"
            or not isinstance(observation.get("evidence_basis"), Mapping)
            or observation.get("source_fact_refs") != [expected_ref]
        ):
            errors.append(f"{label} has invalid structure or evidence reference")
        if observation.get("category") != _vllm_failure_category(failure_class):
            errors.append(f"{label}.category differs from request evidence")
    primary_executions: set[str] = set()
    for index, entry in enumerate(primary):
        label = f"failure_taxonomy.primary_by_execution[{index}]"
        if (
            not isinstance(entry, Mapping)
            or entry.get("execution_ref") not in known_executions
            or entry.get("execution_ref") in primary_executions
        ):
            errors.append(f"{label} must uniquely reference a prompt result")
            continue
        execution_ref, state, observation_id = (
            entry["execution_ref"],
            entry.get("state"),
            entry.get("primary_observation_id"),
        )
        primary_executions.add(str(execution_ref))
        if str(execution_ref) in failed_executions:
            if (
                state != "classified"
                or observation_executions.get(str(observation_id)) != execution_ref
            ):
                errors.append(
                    f"{label} failed execution must reference its classification"
                )
        elif state != "none" or observation_id is not None:
            errors.append(f"{label} completed execution must have no classification")
    if primary_executions != known_executions:
        errors.append("failure_taxonomy must classify every prompt execution")
    return errors
