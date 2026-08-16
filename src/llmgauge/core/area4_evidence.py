from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any, Mapping

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


def native_execution_ref(index: int) -> str:
    return f"results/{index}"


def native_measurement_id(index: int) -> str:
    return f"native-single-turn-{index}"


def _failure_category(failure: Mapping[str, Any]) -> str:
    if failure.get("phase") == "model_weight_load" and failure.get("oom") is True:
        return "model_weight_load_oom"
    if failure.get("phase") == "kv_cache" and failure.get("oom") is True:
        return "kv_cache_oom"
    if failure.get("launch_error") == "process_launch_failed":
        return "runtime_environment_failure"
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
    return {
        "schema_version": NATIVE_EXECUTION_EVIDENCE_SCHEMA,
        "prompt_id": prompt_id,
        "request_wall_time_seconds": float(elapsed_seconds) if valid_elapsed else None,
        "request_wall_time_boundary": "process_launch_to_terminal_output_receipt",
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
                "execution_placement": {"requested": "unknown", "observed": "unknown"},
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
    errors: list[str] = []
    runtime = data.get("runtime")
    if not isinstance(runtime, Mapping) or runtime.get("backend") != "llama.cpp":
        errors.append("Area 4 evidence is supported only for native llama.cpp results")
    if (
        data.get("transcript") is not None
        or data.get("agent_harness_evidence") is not None
    ):
        errors.append(
            "Area 4 evidence is unsupported for transcript or Agent Harness results"
        )
    prompt_results = data.get("results")
    if not isinstance(prompt_results, list):
        return errors + ["Area 4 evidence requires prompt results"]
    known_executions = {
        native_execution_ref(index) for index in range(len(prompt_results))
    }
    native = _load_native_evidence(result_dir, prompt_results, errors)

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
        records = measurement.get("metrics")
        if (
            not isinstance(records, list)
            or len(records) != 1
            or not isinstance(records[0], Mapping)
        ):
            errors.append(f"{label}.metrics must contain one record")
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
