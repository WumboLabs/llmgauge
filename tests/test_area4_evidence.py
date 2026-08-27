from __future__ import annotations

import json
from pathlib import Path

import pytest

from llmgauge.core.area4_evidence import (
    NATIVE_EXECUTION_EVIDENCE_SCHEMA,
    build_area4_evidence,
    build_native_execution_evidence,
)
from llmgauge.core.result_validation import validate_result_dir
from llmgauge.core.run_fingerprint import (
    RUN_FINGERPRINT_SCHEMA_VERSION,
    RUN_FINGERPRINT_SCHEMA_VERSION_V1,
    attach_run_fingerprint,
    verify_run_fingerprint,
)


def _base_result(
    tmp_path: Path, *, evidence: dict, vram_samples: list[dict] | None = None
) -> dict:
    (tmp_path / "raw").mkdir()
    (tmp_path / "logs").mkdir()
    (tmp_path / "native").mkdir()
    (tmp_path / "vram").mkdir()
    (tmp_path / "raw/prompt.prompt.md").write_text("prompt", encoding="utf-8")
    (tmp_path / "raw/prompt.output.txt").write_text("output", encoding="utf-8")
    (tmp_path / "logs/prompt.stderr.log").write_text("stderr", encoding="utf-8")
    (tmp_path / "native/prompt.execution.json").write_text(
        json.dumps(evidence), encoding="utf-8"
    )
    if vram_samples is not None:
        (tmp_path / "vram/prompt.samples.json").write_text(
            json.dumps(
                {
                    "schema_version": "llmgauge.vram.samples.v0",
                    "prompt_id": "prompt",
                    "samples": vram_samples,
                }
            ),
            encoding="utf-8",
        )
    prompt = {
        "prompt_id": "prompt",
        "title": "Prompt",
        "category": "test",
        "status": "completed" if evidence["failure"] is None else "failed",
        "raw_prompt_path": "raw/prompt.prompt.md",
        "raw_output_path": "raw/prompt.output.txt",
        "cleaned_output_path": "raw/prompt.output.txt",
        "stderr_log_path": "logs/prompt.stderr.log",
        "native_execution_evidence_path": "native/prompt.execution.json",
        "_area4_native_execution_evidence": evidence,
        "metrics": {},
        "vram": None,
        **(
            {
                "vram_samples_path": "vram/prompt.samples.json",
                "_area4_vram_samples": vram_samples,
            }
            if vram_samples is not None
            else {"vram_samples_path": None}
        ),
        "vram_guardrails": None,
        "score": None,
        "failure_labels": [],
        "notes": "",
        "exit_status": evidence["failure"]["exit_status"] if evidence["failure"] else 0,
        "error": None,
    }
    result = {
        "schema_version": "llmgauge.result.v0",
        "llmgauge_version": "0.72.0",
        "run": {
            "run_id": "run",
            "timestamp_utc": "2026-08-15T00:00:00+00:00",
            "status": prompt["status"],
            "result_dir": str(tmp_path),
        },
        "model": {
            "model_id": "model",
            "model_path": "redacted",
            "provenance": {
                "source_type": "test",
                "filename": "model.gguf",
                "file_size_bytes": 1,
                "sha256": "a" * 64,
                "status": "available",
            },
        },
        "runtime": {
            "backend": "llama.cpp",
            "max_tokens": 1,
            "batch_size": 1,
            "ubatch_size": 1,
            "backend_provenance": {
                "backend_name": "llama.cpp",
                "executable_filename": "llama-cli",
                "executable_file_size_bytes": 1,
                "executable_sha256": "b" * 64,
                "status": "available",
            },
        },
        "suite": {
            "suite_id": "suite",
            "suite_version": "1",
            "prompt_count": 1,
            "include": [],
            "only": ["prompt"],
        },
        "results": [prompt],
        "summary": {
            "completed": 1 if prompt["status"] == "completed" else 0,
            "failed": 1 if prompt["status"] == "failed" else 0,
        },
    }
    metrics, taxonomy = build_area4_evidence(
        prompt_results=result["results"],
        suite=result["suite"],
        runtime=result["runtime"],
    )
    prompt.pop("_area4_native_execution_evidence")
    prompt.pop("_area4_vram_samples", None)
    result["runtime_neutral_metrics"] = metrics
    result["failure_taxonomy"] = taxonomy
    return result


@pytest.mark.parametrize(
    ("stderr", "launch_error", "expected"),
    [
        ("llama_model_load: CUDA out of memory", None, "model_weight_load_oom"),
        ("llama_kv_cache_init: CUDA out of memory", None, "kv_cache_oom"),
        ("", "process_launch_failed", "runtime_environment_failure"),
        ("ordinary nonzero failure", None, "unclassified_unknown"),
    ],
)
def test_native_failure_taxonomy_categories(
    stderr: str, launch_error: str | None, expected: str
) -> None:
    evidence = build_native_execution_evidence(
        prompt_id="prompt",
        elapsed_seconds=0.5,
        stdout="",
        stderr=stderr,
        exit_status=1,
        timed_out=False,
        launch_error=launch_error,
    )
    metrics, taxonomy = build_area4_evidence(
        prompt_results=[
            {
                "prompt_id": "prompt",
                "status": "failed",
                "native_execution_evidence_path": "native/prompt.execution.json",
                "_area4_native_execution_evidence": evidence,
            }
        ],
        suite={"suite_id": "suite", "suite_version": "1"},
        runtime={"max_tokens": 1, "batch_size": 1, "ubatch_size": 1},
    )
    assert metrics["measurements"][0]["metrics"][0]["value"] == 0.5
    assert taxonomy["observations"][0]["category"] == expected
    assert taxonomy["primary_by_execution"] == [
        {
            "execution_ref": "results/0",
            "primary_observation_id": "native-failure-0",
            "state": "classified",
        }
    ]


def test_area4_result_validates_and_uses_v1_fingerprint(tmp_path: Path) -> None:
    evidence = build_native_execution_evidence(
        prompt_id="prompt",
        elapsed_seconds=1.25,
        stdout="answer",
        stderr="",
        exit_status=0,
        timed_out=False,
        launch_error=None,
    )
    result = _base_result(tmp_path, evidence=evidence)
    assert attach_run_fingerprint(tmp_path, result) is not None
    assert (
        result["run_fingerprint"]["schema_version"] == RUN_FINGERPRINT_SCHEMA_VERSION_V1
    )
    (tmp_path / "llmgauge-result.json").write_text(json.dumps(result), encoding="utf-8")
    assert validate_result_dir(tmp_path) == []


def test_area4_validation_rejects_bad_measurement_and_fingerprint(
    tmp_path: Path,
) -> None:
    evidence = build_native_execution_evidence(
        prompt_id="prompt",
        elapsed_seconds=1.25,
        stdout="answer",
        stderr="",
        exit_status=0,
        timed_out=False,
        launch_error=None,
    )
    result = _base_result(tmp_path, evidence=evidence)
    assert attach_run_fingerprint(tmp_path, result) is not None
    result["runtime_neutral_metrics"]["measurements"][0]["metrics"][0]["value"] = -1
    (tmp_path / "llmgauge-result.json").write_text(json.dumps(result), encoding="utf-8")
    errors = validate_result_dir(tmp_path)
    assert any("available value/provenance is invalid" in error for error in errors)
    assert any("does not match canonical run evidence" in error for error in errors)


def test_legacy_fingerprint_remains_v0(tmp_path: Path) -> None:
    evidence = build_native_execution_evidence(
        prompt_id="prompt",
        elapsed_seconds=None,
        stdout="",
        stderr="",
        exit_status=0,
        timed_out=False,
        launch_error=None,
    )
    result = _base_result(tmp_path, evidence=evidence)
    result.pop("runtime_neutral_metrics")
    result.pop("failure_taxonomy")
    assert attach_run_fingerprint(tmp_path, result) is not None
    assert result["run_fingerprint"]["schema_version"] == RUN_FINGERPRINT_SCHEMA_VERSION
    assert verify_run_fingerprint(tmp_path, result) == []
    assert evidence["schema_version"] == NATIVE_EXECUTION_EVIDENCE_SCHEMA


def test_area4_peak_vram_records_validate_and_fingerprint(tmp_path: Path) -> None:
    evidence = build_native_execution_evidence(
        prompt_id="prompt",
        elapsed_seconds=1.25,
        stdout="answer",
        stderr="",
        exit_status=0,
        timed_out=False,
        launch_error=None,
    )
    vram_samples = [
        {
            "timestamp_utc": "2026-08-26T00:00:00+00:00",
            "gpu_index": 0,
            "gpu_name": "Test GPU",
            "used_mib": 4000,
            "total_mib": 24564,
        },
        {
            "timestamp_utc": "2026-08-26T00:00:01+00:00",
            "gpu_index": 0,
            "gpu_name": "Test GPU",
            "used_mib": 8123,
            "total_mib": 24564,
        },
    ]
    result = _base_result(tmp_path, evidence=evidence, vram_samples=vram_samples)
    records = result["runtime_neutral_metrics"]["measurements"][0]["metrics"]
    assert len(records) == 2
    peak = records[1]
    assert peak["metric_id"] == "llmgauge.metric.v1.peak_vram"
    assert peak["value"] == 8123
    assert peak["unit"] == "MiB"
    assert peak["provenance"] == "calculated"
    assert peak["device_scope"] == {"gpu_index": 0, "gpu_name": "Test GPU"}
    assert peak["sample_count"] == 2
    assert attach_run_fingerprint(tmp_path, result) is not None
    assert (
        result["run_fingerprint"]["schema_version"] == RUN_FINGERPRINT_SCHEMA_VERSION_V1
    )
    (tmp_path / "llmgauge-result.json").write_text(json.dumps(result), encoding="utf-8")
    assert validate_result_dir(tmp_path) == []
    assert verify_run_fingerprint(tmp_path, result) == []


def test_area4_peak_vram_rejects_tampered_value(tmp_path: Path) -> None:
    evidence = build_native_execution_evidence(
        prompt_id="prompt",
        elapsed_seconds=1.25,
        stdout="answer",
        stderr="",
        exit_status=0,
        timed_out=False,
        launch_error=None,
    )
    vram_samples = [
        {
            "timestamp_utc": "2026-08-26T00:00:00+00:00",
            "gpu_index": 0,
            "gpu_name": "Test GPU",
            "used_mib": 8123,
            "total_mib": 24564,
        },
    ]
    result = _base_result(tmp_path, evidence=evidence, vram_samples=vram_samples)
    result["runtime_neutral_metrics"]["measurements"][0]["metrics"][1]["value"] = 9999
    (tmp_path / "llmgauge-result.json").write_text(json.dumps(result), encoding="utf-8")
    errors = validate_result_dir(tmp_path)
    assert any("peak VRAM records differ" in error for error in errors)


def test_area4_peak_vram_unavailable_when_capture_invalid(tmp_path: Path) -> None:
    evidence = build_native_execution_evidence(
        prompt_id="prompt",
        elapsed_seconds=1.25,
        stdout="answer",
        stderr="",
        exit_status=0,
        timed_out=False,
        launch_error=None,
    )
    result = _base_result(
        tmp_path,
        evidence=evidence,
        vram_samples=[{"gpu_index": 0, "gpu_name": "Test GPU", "used_mib": -5}],
    )
    records = result["runtime_neutral_metrics"]["measurements"][0]["metrics"]
    assert len(records) == 2
    peak = records[1]
    assert peak["availability"] == "unavailable"
    assert peak["value"] is None
    assert peak["provenance"] == "unavailable"
    (tmp_path / "llmgauge-result.json").write_text(json.dumps(result), encoding="utf-8")
    assert validate_result_dir(tmp_path) == []


def test_area4_without_vram_capture_keeps_single_record(tmp_path: Path) -> None:
    evidence = build_native_execution_evidence(
        prompt_id="prompt",
        elapsed_seconds=1.25,
        stdout="answer",
        stderr="",
        exit_status=0,
        timed_out=False,
        launch_error=None,
    )
    result = _base_result(tmp_path, evidence=evidence)
    records = result["runtime_neutral_metrics"]["measurements"][0]["metrics"]
    assert len(records) == 1
    assert records[0]["metric_id"] == "llmgauge.metric.v1.request_wall_time"
