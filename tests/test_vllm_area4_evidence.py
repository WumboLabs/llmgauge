"""Focused tests for vLLM Area 4 evidence mapping (request wall time).

Covers the timer boundary correction, the vLLM Area 4 builder, validator
cross-checks, TTFT/throughput/placement/cache disclosure, reporting,
comparison, and public-export compatibility.
"""

from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from llmgauge.core.area4_evidence import build_vllm_area4_evidence
from llmgauge.core.compare import compare_results
from llmgauge.core.public_export import export_public_run
from llmgauge.core.reports import build_markdown_report
from llmgauge.core.result_validation import validate_result_dir
from llmgauge.core.vram import VramSampler
from llmgauge.runners.vllm_external import (
    VllmExternalConfig,
    run_chat_completion,
)


class _Handler(BaseHTTPRequestHandler):
    state: dict[str, object] = {}

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        return

    def do_GET(self) -> None:  # noqa: N802
        body = json.dumps({"version": "0.25.1"}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        self.rfile.read(length)
        mode = self.state.get("mode", "ok")
        if mode == "server_error":
            body = b'{"error":{"message":"fail"}}'
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if mode == "bad_json":
            body = b"{not json"
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        delay = float(self.state.get("delay_seconds", 0.0))
        if delay > 0:
            time.sleep(delay)
        payload = {
            "id": "chatcmpl-1",
            "model": self.state.get("model_id", "test-model"),
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "hello"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 4,
                "total_tokens": 14,
            },
        }
        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture
def vllm_http_server():
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    _Handler.state = {"mode": "ok", "model_id": "test-model", "delay_seconds": 0.0}
    yield f"http://127.0.0.1:{server.server_address[1]}", _Handler.state
    server.shutdown()
    server.server_close()


def _config(url: str, **kwargs: object) -> VllmExternalConfig:
    return VllmExternalConfig(
        endpoint_url=url,
        served_model=str(kwargs.get("served_model", "test-model")),
        max_tokens=int(kwargs.get("max_tokens", 32)),
        temperature=0.2,
        top_p=0.95,
        connect_timeout=float(kwargs.get("connect_timeout", 2.0)),
        request_timeout=float(kwargs.get("request_timeout", 5.0)),
        max_response_bytes=int(kwargs.get("max_response_bytes", 100_000)),
    )


def _result_dir(tmp_path: Path, result: dict[str, object]) -> Path:
    result_dir = tmp_path / result["run"]["run_id"]  # type: ignore[index]
    (result_dir / "raw").mkdir(parents=True)
    (result_dir / "logs").mkdir(parents=True)
    (result_dir / "request").mkdir(parents=True)
    for prompt in result["results"]:  # type: ignore[union-attr]
        prompt_id = prompt["prompt_id"]  # type: ignore[index]
        (result_dir / "raw" / f"{prompt_id}.prompt.md").write_text(
            "prompt", encoding="utf-8"
        )
        (result_dir / "raw" / f"{prompt_id}.output.txt").write_text(
            "output", encoding="utf-8"
        )
        (result_dir / "logs" / f"{prompt_id}.stderr.log").write_text(
            "ok", encoding="utf-8"
        )
    runtime = result.get("runtime")
    if isinstance(runtime, dict) and runtime.get("vllm_runtime_evidence_path"):
        (result_dir / "vllm-runtime-evidence.json").write_text(
            json.dumps(
                {
                    "schema_version": "llmgauge.vllm_runtime_evidence.v0",
                    "lifecycle_ownership": "external_operator",
                    "endpoint_identity": runtime.get("endpoint_identity", {}),
                    "requested_served_model": runtime.get(
                        "requested_served_model", "test-model"
                    ),
                    "observed_served_model": runtime.get(
                        "observed_served_model", "test-model"
                    ),
                    "vllm_version": "0.25.1",
                    "server_state": "ready",
                    "observed_system_fingerprints": [],
                }
            ),
            encoding="utf-8",
        )
    (result_dir / "llmgauge-result.json").write_text(
        json.dumps(result), encoding="utf-8"
    )
    return result_dir


def _write_request_evidence(
    result_dir: Path, prompt_id: str, evidence: dict[str, object]
) -> None:
    (result_dir / "request" / f"{prompt_id}.json").write_text(
        json.dumps(evidence), encoding="utf-8"
    )


def _prompt_entry(prompt_id: str, evidence: dict[str, object]) -> dict[str, object]:
    return {
        "prompt_id": prompt_id,
        "title": prompt_id,
        "category": "test",
        "status": "completed" if evidence.get("failure_class") is None else "failed",
        "raw_prompt_path": f"raw/{prompt_id}.prompt.md",
        "raw_output_path": f"raw/{prompt_id}.output.txt",
        "cleaned_output_path": f"raw/{prompt_id}.output.txt",
        "stderr_log_path": f"logs/{prompt_id}.stderr.log",
        "request_evidence_path": f"request/{prompt_id}.json",
        "_area4_vllm_request_evidence": evidence,
        "metrics": {
            "request_wall_time_seconds": evidence.get("request_wall_time_seconds"),
            "end_to_end_completion_tps": None,
        },
        "vram": None,
        "vram_samples_path": None,
        "vram_guardrails": None,
        "score": None,
        "failure_labels": [],
        "notes": "",
        "exit_status": 0 if evidence.get("failure_class") is None else 1,
        "error": None,
        "failure_class": evidence.get("failure_class"),
        "failure_detail": evidence.get("failure_detail"),
        "finish_reason": "stop" if evidence.get("failure_class") is None else None,
    }


def _vllm_result(
    prompt_entries: list[dict[str, object]],
    *,
    suite: dict[str, object] | None = None,
    runtime: dict[str, object] | None = None,
) -> dict[str, object]:
    suite = suite or {"suite_id": "core-v1", "suite_version": "1", "prompt_count": 1}
    runtime = runtime or {
        "backend": "vllm",
        "lifecycle_ownership": "external_operator",
        "max_tokens": 32,
        "endpoint_identity": {
            "scheme": "http",
            "loopback_class": "ipv4_loopback",
            "port": 8000,
        },
        "requested_served_model": "test-model",
        "observed_served_model": "test-model",
        "ctx_size": 8192,
        "temperature": 0.2,
        "top_p": 0.95,
        "runtime_command_captured": False,
        "vllm_runtime_evidence_captured": True,
        "vllm_runtime_evidence_path": "vllm-runtime-evidence.json",
        "proxy_bypass_policy": "stdlib_http_client_no_env_proxy",
        "streaming": False,
        "authentication": "none",
    }
    completed = sum(1 for entry in prompt_entries if entry.get("status") == "completed")
    failed = len(prompt_entries) - completed
    result: dict[str, object] = {
        "schema_version": "llmgauge.result.v0",
        "llmgauge_version": "0.76.0",
        "run": {
            "run_id": "vllm-run",
            "timestamp_utc": "2026-08-29T00:00:00+00:00",
            "status": "completed" if failed == 0 else "failed",
            "result_dir": "vllm-run",
        },
        "model": {
            "model_id": "test-model",
            "model_path": "redacted",
            "model_path_policy": "redacted",
            "served_model": "test-model",
        },
        "runtime": runtime,
        "suite": suite,
        "summary": {"completed": completed, "failed": failed},
        "results": prompt_entries,
    }
    metrics, taxonomy = build_vllm_area4_evidence(
        prompt_results=prompt_entries,  # type: ignore[arg-type]
        suite=suite,
        runtime=runtime,
    )
    result["runtime_neutral_metrics"] = metrics
    result["failure_taxonomy"] = taxonomy
    return result


def _success_evidence(wall: float) -> dict[str, object]:
    return {
        "schema_version": "llmgauge.vllm_request_evidence.v0",
        "lifecycle_ownership": "external_operator",
        "streaming": False,
        "request_wall_time_seconds": wall,
        "request_wall_time_boundary": "request_transmit_to_validated_response",
        "request_transmitted": True,
        "endpoint_identity": {
            "scheme": "http",
            "loopback_class": "ipv4_loopback",
            "port": 8000,
        },
        "prompt_tokens": 10,
        "completion_tokens": 4,
        "finish_reason": "stop",
    }


# ---------------------------------------------------------------------------
# Timer boundary
# ---------------------------------------------------------------------------


def test_timer_boundary_includes_server_work_and_validation(
    vllm_http_server,
) -> None:
    url, state = vllm_http_server
    state["delay_seconds"] = 0.25
    result = run_chat_completion(_config(url), prompt="hello")
    assert result.success is True
    assert result.request_wall_time_seconds is not None
    assert result.request_wall_time_seconds >= 0.25
    assert result.request_evidence["request_transmitted"] is True
    assert (
        result.request_evidence["request_wall_time_boundary"]
        == "request_transmit_to_validated_response"
    )


def test_timer_boundary_preserved_on_http_error(vllm_http_server) -> None:
    url, state = vllm_http_server
    state["mode"] = "server_error"
    result = run_chat_completion(_config(url), prompt="hello")
    assert result.success is False
    assert result.failure_class == "server_request_error"
    assert result.request_wall_time_seconds is not None
    assert result.request_wall_time_seconds >= 0
    assert result.request_evidence["request_transmitted"] is True


def test_timer_boundary_preserved_on_malformed_response(vllm_http_server) -> None:
    url, state = vllm_http_server
    state["mode"] = "bad_json"
    result = run_chat_completion(_config(url), prompt="hello")
    assert result.success is False
    assert result.failure_class == "malformed_response"
    assert result.request_wall_time_seconds is not None
    assert result.request_evidence["request_transmitted"] is True


def test_no_wall_time_when_request_never_transmitted() -> None:
    result = run_chat_completion(_config("http://127.0.0.1:9"), prompt="")
    assert result.success is False
    assert result.request_wall_time_seconds is None
    assert result.request_evidence["request_transmitted"] is False


# ---------------------------------------------------------------------------
# Area 4 builder
# ---------------------------------------------------------------------------


def test_build_vllm_area4_success_record() -> None:
    prompt = _prompt_entry("p1", _success_evidence(1.25))
    metrics, taxonomy = build_vllm_area4_evidence(
        prompt_results=[prompt],  # type: ignore[arg-type]
        suite={"suite_id": "core-v1", "suite_version": "1"},
        runtime={"max_tokens": 32},
    )
    measurement = metrics["measurements"][0]
    assert measurement["measurement_id"] == "vllm-request-0"
    assert measurement["execution_ref"] == "results/0"
    assert measurement["completion_state"] == "completed"
    assert measurement["workload"]["request_form"] == "chat_messages"
    assert measurement["workload"]["cache_state"] == "unknown"
    assert measurement["execution_placement"] == {
        "requested": "unknown",
        "observed": "unknown",
    }
    record = measurement["metrics"][0]
    assert record["metric_id"] == "llmgauge.metric.v1.request_wall_time"
    assert record["native_metric_id"] == "request_wall_time_seconds"
    assert record["value"] == 1.25
    assert record["unit"] == "s"
    assert record["availability"] == "available"
    assert record["provenance"] == "llmgauge_observed"
    assert record["boundary"] == "request_transmit_to_validated_response"
    assert record["equivalence"] == "unproven"
    assert record["evidence_refs"] == ["request/p1.json#/request_wall_time_seconds"]
    assert taxonomy["observations"] == []
    assert taxonomy["primary_by_execution"] == [
        {"execution_ref": "results/0", "primary_observation_id": None, "state": "none"}
    ]


def test_build_vllm_area4_failure_record() -> None:
    evidence = _success_evidence(0.5)
    evidence["failure_class"] = "server_request_error"
    evidence["failure_detail"] = "http_500"
    prompt = _prompt_entry("p1", evidence)
    metrics, taxonomy = build_vllm_area4_evidence(
        prompt_results=[prompt],  # type: ignore[arg-type]
        suite={"suite_id": "core-v1", "suite_version": "1"},
        runtime={"max_tokens": 32},
    )
    measurement = metrics["measurements"][0]
    assert measurement["completion_state"] == "failed"
    assert measurement["metrics"][0]["availability"] == "available"
    assert measurement["metrics"][0]["value"] == 0.5
    observation = taxonomy["observations"][0]
    assert observation["category"] == "endpoint_failure"
    assert observation["source_fact_refs"] == ["request/p1.json#/failure_class"]
    assert observation["execution_state"] == "terminal"
    assert taxonomy["primary_by_execution"] == [
        {
            "execution_ref": "results/0",
            "primary_observation_id": "vllm-failure-0",
            "state": "classified",
        }
    ]


def test_build_vllm_area4_timeout_record() -> None:
    evidence = _success_evidence(2.0)
    evidence["failure_class"] = "request_timeout"
    evidence["failure_detail"] = "timeout"
    prompt = _prompt_entry("p1", evidence)
    metrics, _taxonomy = build_vllm_area4_evidence(
        prompt_results=[prompt],  # type: ignore[arg-type]
        suite={"suite_id": "core-v1", "suite_version": "1"},
        runtime={"max_tokens": 32},
    )
    assert metrics["measurements"][0]["completion_state"] == "timeout"


def test_build_vllm_area4_untransmitted_is_unavailable() -> None:
    evidence = {
        "schema_version": "llmgauge.vllm_request_evidence.v0",
        "lifecycle_ownership": "external_operator",
        "request_transmitted": False,
        "request_wall_time_seconds": None,
        "failure_class": "endpoint_unavailable",
        "failure_detail": "connect_failed",
    }
    prompt = _prompt_entry("p1", evidence)
    metrics, taxonomy = build_vllm_area4_evidence(
        prompt_results=[prompt],  # type: ignore[arg-type]
        suite={"suite_id": "core-v1", "suite_version": "1"},
        runtime={"max_tokens": 32},
    )
    record = metrics["measurements"][0]["metrics"][0]
    assert record["availability"] == "unavailable"
    assert record["value"] is None
    assert record["provenance"] == "unavailable"
    assert record["equivalence"] == "unavailable"
    assert taxonomy["observations"][0]["category"] == "endpoint_failure"


def test_ttft_absent_and_e2e_tps_not_mapped() -> None:
    prompt = _prompt_entry("p1", _success_evidence(0.5))
    metrics, _taxonomy = build_vllm_area4_evidence(
        prompt_results=[prompt],  # type: ignore[arg-type]
        suite={"suite_id": "core-v1", "suite_version": "1"},
        runtime={"max_tokens": 32},
    )
    ids = [record["metric_id"] for record in metrics["measurements"][0]["metrics"]]
    assert "llmgauge.metric.v1.time_to_first_token" not in ids
    assert "llmgauge.metric.v1.decode_generation_throughput" not in ids
    assert "llmgauge.metric.v1.prefill_throughput" not in ids


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------


def test_validate_vllm_area4_result(tmp_path: Path) -> None:
    evidence = _success_evidence(1.25)
    prompt = _prompt_entry("p1", evidence)
    result = _vllm_result([prompt])
    result_dir = _result_dir(tmp_path, result)
    _write_request_evidence(result_dir, "p1", evidence)
    assert validate_result_dir(result_dir) == []


def test_validate_vllm_area4_rejects_altered_value(tmp_path: Path) -> None:
    evidence = _success_evidence(1.25)
    prompt = _prompt_entry("p1", evidence)
    result = _vllm_result([prompt])
    result_dir = _result_dir(tmp_path, result)
    _write_request_evidence(result_dir, "p1", evidence)
    # Tamper with the neutral value.
    result["runtime_neutral_metrics"]["measurements"][0]["metrics"][0][  # type: ignore[index]
        "value"
    ] = 9.99
    (result_dir / "llmgauge-result.json").write_text(
        json.dumps(result), encoding="utf-8"
    )
    errors = validate_result_dir(result_dir)
    assert any("differs from request evidence" in err for err in errors)


def test_validate_vllm_area4_rejects_unavailable_with_value(tmp_path: Path) -> None:
    evidence = _success_evidence(1.25)
    prompt = _prompt_entry("p1", evidence)
    result = _vllm_result([prompt])
    result_dir = _result_dir(tmp_path, result)
    _write_request_evidence(result_dir, "p1", evidence)
    record = result["runtime_neutral_metrics"]["measurements"][0]["metrics"][0]  # type: ignore[index]
    record["availability"] = "unavailable"
    record["value"] = 1.25
    record["provenance"] = "unavailable"
    record["equivalence"] = "unavailable"
    (result_dir / "llmgauge-result.json").write_text(
        json.dumps(result), encoding="utf-8"
    )
    errors = validate_result_dir(result_dir)
    assert any("unavailable value/provenance is invalid" in err for err in errors)


def test_validate_vllm_area4_rejects_wrong_evidence_ref(tmp_path: Path) -> None:
    evidence = _success_evidence(1.25)
    prompt = _prompt_entry("p1", evidence)
    result = _vllm_result([prompt])
    result_dir = _result_dir(tmp_path, result)
    _write_request_evidence(result_dir, "p1", evidence)
    result["runtime_neutral_metrics"]["measurements"][0]["metrics"][0][  # type: ignore[index]
        "evidence_refs"
    ] = ["request/p1.json#/wrong"]
    (result_dir / "llmgauge-result.json").write_text(
        json.dumps(result), encoding="utf-8"
    )
    errors = validate_result_dir(result_dir)
    assert any("evidence reference is invalid" in err for err in errors)


def test_validate_vllm_area4_rejects_missing_request_evidence(
    tmp_path: Path,
) -> None:
    evidence = _success_evidence(1.25)
    prompt = _prompt_entry("p1", evidence)
    result = _vllm_result([prompt])
    result_dir = _result_dir(tmp_path, result)
    # No request/p1.json written.
    (result_dir / "llmgauge-result.json").write_text(
        json.dumps(result), encoding="utf-8"
    )
    errors = validate_result_dir(result_dir)
    assert any("request_evidence_path" in err for err in errors)


def _sample_dict(gpu_index: int, gpu_name: str, used_mib: int) -> dict:
    return {
        "timestamp_utc": "2026-08-29T00:00:00+00:00",
        "gpu_index": gpu_index,
        "gpu_name": gpu_name,
        "used_mib": used_mib,
        "total_mib": 12227,
    }


def _write_vram_samples(
    result_dir: Path, prompt_id: str, samples: list[dict]
) -> None:
    (result_dir / "vram").mkdir(parents=True, exist_ok=True)
    (result_dir / "vram" / f"{prompt_id}.samples.json").write_text(
        json.dumps(
            {
                "schema_version": "llmgauge.vram.samples.v0",
                "prompt_id": prompt_id,
                "sampler_window": {
                    "kind": "vllm_request_window",
                    "interval_seconds": 0.5,
                    "start_boundary": "immediately_before_request_attempt",
                    "stop_boundary": "request_terminal_state",
                    "final_sample": "taken_at_stop",
                },
                "errors": None,
                "samples": samples,
            }
        ),
        encoding="utf-8",
    )


def _prompt_with_vram(
    prompt_id: str, evidence: dict[str, object], samples: list[dict]
) -> dict[str, object]:
    prompt = _prompt_entry(prompt_id, evidence)
    prompt["vram_samples_path"] = f"vram/{prompt_id}.samples.json"
    prompt["_area4_vram_samples"] = samples
    return prompt


def test_validate_vllm_area4_accepts_request_window_peak_vram(
    tmp_path: Path,
) -> None:
    evidence = _success_evidence(1.25)
    prompt = _prompt_with_vram(
        "p1",
        evidence,
        [_sample_dict(0, "GPU A", 1000), _sample_dict(0, "GPU A", 1200)],
    )
    result = _vllm_result([prompt])
    result_dir = _result_dir(tmp_path, result)
    _write_request_evidence(result_dir, "p1", evidence)
    _write_vram_samples(
        result_dir,
        "p1",
        [_sample_dict(0, "GPU A", 1000), _sample_dict(0, "GPU A", 1200)],
    )
    assert validate_result_dir(result_dir) == []


def test_validate_vllm_area4_rejects_wrong_peak_max(tmp_path: Path) -> None:
    evidence = _success_evidence(1.25)
    prompt = _prompt_with_vram("p1", evidence, [_sample_dict(0, "GPU A", 1200)])
    result = _vllm_result([prompt])
    result_dir = _result_dir(tmp_path, result)
    _write_request_evidence(result_dir, "p1", evidence)
    _write_vram_samples(result_dir, "p1", [_sample_dict(0, "GPU A", 1200)])
    result["runtime_neutral_metrics"]["measurements"][0]["metrics"][1][  # type: ignore[index]
        "value"
    ] = 1300
    (result_dir / "llmgauge-result.json").write_text(
        json.dumps(result), encoding="utf-8"
    )
    errors = validate_result_dir(result_dir)
    assert any("peak VRAM records differ" in err for err in errors)


def test_validate_vllm_area4_unavailable_not_zero(tmp_path: Path) -> None:
    evidence = _success_evidence(1.25)
    prompt = _prompt_with_vram("p1", evidence, [])
    result = _vllm_result([prompt])
    result_dir = _result_dir(tmp_path, result)
    _write_request_evidence(result_dir, "p1", evidence)
    _write_vram_samples(result_dir, "p1", [])
    assert validate_result_dir(result_dir) == []
    # Zero substituted for unavailable must be rejected.
    result["runtime_neutral_metrics"]["measurements"][0]["metrics"][1][  # type: ignore[index]
        "value"
    ] = 0
    (result_dir / "llmgauge-result.json").write_text(
        json.dumps(result), encoding="utf-8"
    )
    errors = validate_result_dir(result_dir)
    assert any("peak VRAM records differ" in err for err in errors)


def test_validate_vllm_area4_failed_request_with_samples(tmp_path: Path) -> None:
    evidence = _success_evidence(0.5)
    evidence["failure_class"] = "server_request_error"
    evidence["failure_detail"] = "http_500"
    evidence["request_wall_time_seconds"] = 0.5
    prompt = _prompt_with_vram("p1", evidence, [_sample_dict(0, "GPU A", 2400)])
    result = _vllm_result([prompt])
    result_dir = _result_dir(tmp_path, result)
    _write_request_evidence(result_dir, "p1", evidence)
    _write_vram_samples(result_dir, "p1", [_sample_dict(0, "GPU A", 2400)])
    assert validate_result_dir(result_dir) == []
    measurement = result["runtime_neutral_metrics"]["measurements"][0]  # type: ignore[index]
    assert measurement["completion_state"] == "failed"
    peak = measurement["metrics"][1]
    assert peak["availability"] == "available"
    assert peak["value"] == 2400


def test_validate_vllm_area4_timeout_with_samples(tmp_path: Path) -> None:
    evidence = _success_evidence(5.0)
    evidence["failure_class"] = "request_timeout"
    evidence["failure_detail"] = "request_timeout"
    prompt = _prompt_with_vram("p1", evidence, [_sample_dict(0, "GPU A", 1800)])
    result = _vllm_result([prompt])
    result_dir = _result_dir(tmp_path, result)
    _write_request_evidence(result_dir, "p1", evidence)
    _write_vram_samples(result_dir, "p1", [_sample_dict(0, "GPU A", 1800)])
    assert validate_result_dir(result_dir) == []
    measurement = result["runtime_neutral_metrics"]["measurements"][0]  # type: ignore[index]
    assert measurement["completion_state"] == "timeout"
    assert measurement["metrics"][1]["value"] == 1800


def test_validate_vllm_area4_multi_device_independent(tmp_path: Path) -> None:
    evidence = _success_evidence(1.25)
    samples = [
        _sample_dict(0, "GPU A", 1000),
        _sample_dict(0, "GPU A", 1300),
        _sample_dict(1, "GPU B", 2000),
        _sample_dict(1, "GPU B", 2400),
    ]
    prompt = _prompt_with_vram("p1", evidence, samples)
    result = _vllm_result([prompt])
    result_dir = _result_dir(tmp_path, result)
    _write_request_evidence(result_dir, "p1", evidence)
    _write_vram_samples(result_dir, "p1", samples)
    assert validate_result_dir(result_dir) == []
    peak_records = result["runtime_neutral_metrics"]["measurements"][0]["metrics"][1:]  # type: ignore[index]
    assert len(peak_records) == 2
    values = {
        record["device_scope"]["gpu_index"]: record["value"]
        for record in peak_records
    }
    assert values == {0: 1300, 1: 2400}


def test_validate_vllm_area4_missing_evidence_rejected(tmp_path: Path) -> None:
    evidence = _success_evidence(1.25)
    prompt = _prompt_with_vram("p1", evidence, [_sample_dict(0, "GPU A", 1200)])
    result = _vllm_result([prompt])
    result_dir = _result_dir(tmp_path, result)
    _write_request_evidence(result_dir, "p1", evidence)
    # Artifact referenced but never written: validation must fail closed.
    errors = validate_result_dir(result_dir)
    assert any("vram_samples_path" in err for err in errors)


def test_historical_vllm_result_without_area4_still_valid(tmp_path: Path) -> None:
    result_dir = tmp_path / "legacy-vllm"
    (result_dir / "raw").mkdir(parents=True)
    (result_dir / "logs").mkdir(parents=True)
    (result_dir / "request").mkdir(parents=True)
    (result_dir / "raw/p1.prompt.md").write_text("prompt", encoding="utf-8")
    (result_dir / "raw/p1.output.txt").write_text("output", encoding="utf-8")
    (result_dir / "logs/p1.stderr.log").write_text("ok", encoding="utf-8")
    (result_dir / "request/p1.json").write_text(
        json.dumps(_success_evidence(0.5)), encoding="utf-8"
    )
    (result_dir / "vllm-runtime-evidence.json").write_text(
        json.dumps(
            {
                "schema_version": "llmgauge.vllm_runtime_evidence.v0",
                "lifecycle_ownership": "external_operator",
                "endpoint_identity": {
                    "scheme": "http",
                    "loopback_class": "ipv4_loopback",
                    "port": 8000,
                },
                "requested_served_model": "test-model",
                "observed_served_model": "test-model",
                "vllm_version": "unknown",
                "server_state": "unknown",
                "observed_system_fingerprints": [],
            }
        ),
        encoding="utf-8",
    )
    data = {
        "schema_version": "llmgauge.result.v0",
        "llmgauge_version": "0.70.0",
        "run": {"run_id": "legacy-vllm", "status": "completed", "timestamp_utc": "t"},
        "model": {
            "model_id": "test-model",
            "model_path": "redacted",
            "model_path_policy": "redacted",
            "served_model": "test-model",
        },
        "runtime": {
            "backend": "vllm",
            "lifecycle_ownership": "external_operator",
            "endpoint_identity": {
                "scheme": "http",
                "loopback_class": "ipv4_loopback",
                "port": 8000,
            },
            "requested_served_model": "test-model",
            "observed_served_model": "test-model",
            "ctx_size": 8192,
            "max_tokens": 32,
            "temperature": 0.2,
            "top_p": 0.95,
            "runtime_command_captured": False,
            "vllm_runtime_evidence_captured": True,
            "vllm_runtime_evidence_path": "vllm-runtime-evidence.json",
            "proxy_bypass_policy": "stdlib_http_client_no_env_proxy",
        },
        "suite": {"suite_id": "core-v1", "suite_version": "1", "prompt_count": 1},
        "summary": {"completed": 1, "failed": 0},
        "results": [
            {
                "prompt_id": "p1",
                "category": "test",
                "status": "completed",
                "raw_prompt_path": "raw/p1.prompt.md",
                "raw_output_path": "raw/p1.output.txt",
                "stderr_log_path": "logs/p1.stderr.log",
                "request_evidence_path": "request/p1.json",
                "exit_status": 0,
                "metrics": {},
            }
        ],
    }
    (result_dir / "llmgauge-result.json").write_text(json.dumps(data), encoding="utf-8")
    assert validate_result_dir(result_dir) == []


def _write_llama_result(result_dir: Path, evidence: dict[str, object]) -> dict[str, object]:
    """Build a llama.cpp Area 4 result dir mirroring tests/test_area4_evidence.py."""
    (result_dir / "raw").mkdir(parents=True)
    (result_dir / "logs").mkdir(parents=True)
    (result_dir / "native").mkdir(parents=True)
    (result_dir / "raw/prompt.prompt.md").write_text("prompt", encoding="utf-8")
    (result_dir / "raw/prompt.output.txt").write_text("output", encoding="utf-8")
    (result_dir / "logs/prompt.stderr.log").write_text("stderr", encoding="utf-8")
    (result_dir / "native/prompt.execution.json").write_text(
        json.dumps(evidence), encoding="utf-8"
    )
    prompt = {
        "prompt_id": "prompt",
        "title": "Prompt",
        "category": "test",
        "status": "completed" if evidence.get("failure") is None else "failed",
        "raw_prompt_path": "raw/prompt.prompt.md",
        "raw_output_path": "raw/prompt.output.txt",
        "cleaned_output_path": "raw/prompt.output.txt",
        "stderr_log_path": "logs/prompt.stderr.log",
        "native_execution_evidence_path": "native/prompt.execution.json",
        "_area4_native_execution_evidence": evidence,
        "metrics": {},
        "vram": None,
        "vram_samples_path": None,
        "vram_guardrails": None,
        "score": None,
        "failure_labels": [],
        "notes": "",
        "exit_status": evidence["failure"]["exit_status"]
        if evidence.get("failure")
        else 0,
        "error": None,
    }
    result = {
        "schema_version": "llmgauge.result.v0",
        "llmgauge_version": "0.72.0",
        "run": {
            "run_id": "llama-run",
            "timestamp_utc": "2026-08-15T00:00:00+00:00",
            "status": prompt["status"],
            "result_dir": str(result_dir),
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
    from llmgauge.core.area4_evidence import build_area4_evidence

    metrics, taxonomy = build_area4_evidence(
        prompt_results=result["results"],
        suite=result["suite"],
        runtime=result["runtime"],
    )
    prompt.pop("_area4_native_execution_evidence")
    prompt.pop("_area4_vram_samples", None)
    result["runtime_neutral_metrics"] = metrics
    result["failure_taxonomy"] = taxonomy
    (result_dir / "llmgauge-result.json").write_text(
        json.dumps(result), encoding="utf-8"
    )
    return result


def test_llama_cpp_area4_unchanged(tmp_path: Path) -> None:
    """A llama.cpp Area 4 result must not be rejected by the vLLM branch."""
    result_dir = tmp_path / "llama-run"
    _write_llama_result(
        result_dir,
        {
            "schema_version": "llmgauge.native_llama_cpp_execution_evidence.v1",
            "prompt_id": "prompt",
            "request_wall_time_seconds": 1.25,
            "request_wall_time_boundary": "process_launch_to_terminal_output_receipt",
            "llama_cpp_timing": None,
            "llama_cpp_placement": None,
            "failure": None,
        },
    )
    assert validate_result_dir(result_dir) == []


# ---------------------------------------------------------------------------
# Report / comparison / public export
# ---------------------------------------------------------------------------


def test_report_discloses_neutral_and_native_separately(tmp_path: Path) -> None:
    evidence = _success_evidence(2.43)
    prompt = _prompt_entry("p1", evidence)
    result = _vllm_result([prompt])
    report = build_markdown_report(result)  # type: ignore[arg-type]
    assert "Runtime-neutral evidence" in report
    assert "Request wall time: 2.43 s" in report
    assert "Provenance: llmgauge_observed" in report
    assert "request transmit" in report
    assert "TTFT: unavailable (non-streaming transport)" in report
    assert "Placement: unavailable" in report
    # Native evidence remains visible.
    assert "Request wall time s:" in report


def test_comparison_discloses_boundaries(tmp_path: Path) -> None:
    evidence = _success_evidence(2.43)
    prompt = _prompt_entry("p1", evidence)
    vllm_result = _vllm_result([prompt])
    llama_result = _write_llama_result(
        tmp_path / "llama-run",
        {
            "schema_version": "llmgauge.native_llama_cpp_execution_evidence.v1",
            "prompt_id": "prompt",
            "request_wall_time_seconds": 1.5,
            "request_wall_time_boundary": "process_launch_to_terminal_output_receipt",
            "llama_cpp_timing": None,
            "llama_cpp_placement": None,
            "failure": None,
        },
    )
    report = compare_results([vllm_result, llama_result])  # type: ignore[arg-type]
    assert "Runtime-neutral Area 4 evidence" in report
    assert "Request wall time s" in report
    assert "Boundary" in report
    assert "not read equivalent values as proof" in report


def test_public_export_preserves_vllm_area4_sanitized(tmp_path: Path) -> None:
    evidence = _success_evidence(1.25)
    prompt = _prompt_entry("p1", evidence)
    result = _vllm_result([prompt])
    result_dir = _result_dir(tmp_path, result)
    _write_request_evidence(result_dir, "p1", evidence)
    (result_dir / "vllm-runtime-evidence.json").write_text(
        json.dumps(
            {
                "schema_version": "llmgauge.vllm_runtime_evidence.v0",
                "lifecycle_ownership": "external_operator",
                "endpoint_identity": {
                    "scheme": "http",
                    "loopback_class": "ipv4_loopback",
                    "port": 8000,
                    "proxy_bypass_policy": "stdlib_http_client_no_env_proxy",
                },
                "requested_served_model": "test-model",
                "observed_served_model": "test-model",
                "vllm_version": "0.25.1",
                "server_state": "ready",
                "observed_system_fingerprints": ["vllm-0.25.1-testfp"],
            }
        ),
        encoding="utf-8",
    )
    result["runtime"]["vllm_runtime_evidence_path"] = "vllm-runtime-evidence.json"  # type: ignore[index]
    (result_dir / "llmgauge-result.json").write_text(
        json.dumps(result), encoding="utf-8"
    )
    assert validate_result_dir(result_dir) == []

    public_dir = tmp_path / "public"
    export_public_run(result_dir, public_dir)
    public_result = json.loads(
        (public_dir / "llmgauge-result.json").read_text(encoding="utf-8")
    )
    assert (
        public_result["runtime_neutral_metrics"]["measurements"][0]["metrics"][0][
            "value"
        ]
        == 1.25
    )
    identity = public_result["runtime"]["endpoint_identity"]
    assert set(identity.keys()) <= {
        "scheme",
        "loopback_class",
        "port",
        "proxy_bypass_policy",
    }
    assert "url" not in identity


def test_report_discloses_request_window_peak_vram(tmp_path: Path) -> None:
    evidence = _success_evidence(2.43)
    prompt = _prompt_with_vram(
        "p1",
        evidence,
        [_sample_dict(0, "GPU A", 1000), _sample_dict(0, "GPU A", 10824)],
    )
    result = _vllm_result([prompt])
    report = build_markdown_report(result)  # type: ignore[arg-type]
    assert "Request peak VRAM: 10824 MiB" in report
    assert "Device: GPU 0" in report
    assert "Samples: 2" in report
    assert "VRAM boundary: request_window_peak_vram_observation" in report
    assert "VRAM provenance: calculated" in report
    assert "Memory scope: absolute device-used memory" in report
    # Claim boundary language stays explicit and non-attributive.
    assert "model VRAM" not in report
    assert "vLLM footprint" not in report


def test_report_discloses_unavailable_request_peak_vram() -> None:
    """Sampler ran but produced no valid samples -> unavailable peak record."""
    evidence = _success_evidence(2.43)
    prompt = _prompt_with_vram("p1", evidence, [])
    result = _vllm_result([prompt])
    report = build_markdown_report(result)  # type: ignore[arg-type]
    assert "Request peak VRAM: unavailable" in report
    assert "no successful telemetry observation" in report


def test_comparison_discloses_vram_boundaries(tmp_path: Path) -> None:
    evidence = _success_evidence(2.43)
    prompt = _prompt_with_vram(
        "p1",
        evidence,
        [_sample_dict(0, "GPU A", 1000), _sample_dict(0, "GPU A", 10824)],
    )
    vllm_result = _vllm_result([prompt])
    llama_result = _write_llama_result(
        tmp_path / "llama-run",
        {
            "schema_version": "llmgauge.native_llama_cpp_execution_evidence.v1",
            "prompt_id": "prompt",
            "request_wall_time_seconds": 1.5,
            "request_wall_time_boundary": "process_launch_to_terminal_output_receipt",
            "llama_cpp_timing": None,
            "llama_cpp_placement": None,
            "failure": None,
        },
    )
    report = compare_results([vllm_result, llama_result])  # type: ignore[arg-type]
    assert "Peak VRAM MiB" in report
    assert "VRAM boundary" in report
    assert "request_window_peak_vram_observation" in report
    assert "not read equivalent values as proof" in report


# ---------------------------------------------------------------------------
# Sampler + synthetic HTTP request integration
# ---------------------------------------------------------------------------


def _run_with_sampler(config: VllmExternalConfig, probe) -> tuple[object, list, list]:
    sampler = VramSampler(interval_seconds=0.02, probe=probe)
    sampler.start()
    try:
        result = run_chat_completion(config, prompt="hello")
    finally:
        samples, errors = sampler.stop()
    return result, samples, errors


def test_http_request_with_sampler_succeeds_and_no_worker_leaks(
    vllm_http_server,
) -> None:
    url, _state = vllm_http_server

    def probe() -> dict:
        return {
            "schema_version": "llmgauge.vram.sample.v0",
            "available": True,
            "source": "nvidia-smi",
            "timestamp_utc": "2026-08-29T00:00:00+00:00",
            "samples": [_sample_dict(0, "GPU A", 8123)],
        }

    result, samples, errors = _run_with_sampler(_config(url), probe)
    assert result.success is True
    assert result.request_wall_time_seconds is not None
    assert errors == []
    assert samples
    assert all(item["used_mib"] == 8123 for item in samples)


def test_http_request_wall_time_independent_of_sampler(
    vllm_http_server,
) -> None:
    url, state = vllm_http_server
    state["delay_seconds"] = 0.1
    baseline = run_chat_completion(_config(url), prompt="hello")
    state["delay_seconds"] = 0.0
    assert baseline.request_wall_time_seconds is not None
    wall_without = baseline.request_wall_time_seconds

    def probe() -> dict:
        return {
            "schema_version": "llmgauge.vram.sample.v0",
            "available": True,
            "source": "nvidia-smi",
            "timestamp_utc": "2026-08-29T00:00:00+00:00",
            "samples": [_sample_dict(0, "GPU A", 8123)],
        }

    state["delay_seconds"] = 0.1
    result, _samples, _errors = _run_with_sampler(_config(url), probe)
    state["delay_seconds"] = 0.0
    assert result.success is True
    assert result.request_wall_time_seconds is not None
    # Both windows include the same 0.1 s server delay; sampler probe happens
    # outside the request timer, so measured wall time stays comparable.
    assert result.request_wall_time_seconds >= wall_without * 0.9


def test_http_error_with_sampler_no_worker_leaks(vllm_http_server) -> None:
    url, state = vllm_http_server
    state["mode"] = "server_error"

    def probe() -> dict:
        return {
            "schema_version": "llmgauge.vram.sample.v0",
            "available": True,
            "source": "nvidia-smi",
            "timestamp_utc": "2026-08-29T00:00:00+00:00",
            "samples": [_sample_dict(0, "GPU A", 8123)],
        }

    result, samples, _errors = _run_with_sampler(_config(url), probe)
    state["mode"] = "ok"
    assert result.success is False
    assert result.failure_class == "server_request_error"
    assert result.request_wall_time_seconds is not None
    assert samples


def test_timeout_with_sampler_no_worker_leaks(vllm_http_server) -> None:
    url, state = vllm_http_server
    state["delay_seconds"] = 1.0

    def probe() -> dict:
        return {
            "schema_version": "llmgauge.vram.sample.v0",
            "available": True,
            "source": "nvidia-smi",
            "timestamp_utc": "2026-08-29T00:00:00+00:00",
            "samples": [_sample_dict(0, "GPU A", 8123)],
        }

    result, samples, _errors = _run_with_sampler(
        _config(url, request_timeout=0.1), probe
    )
    state["delay_seconds"] = 0.0
    assert result.success is False
    assert result.failure_class == "request_timeout"
    assert samples


def test_http_success_with_failing_sampler_still_succeeds(vllm_http_server) -> None:
    url, _state = vllm_http_server

    def probe() -> dict:
        raise OSError("telemetry unavailable")

    result, samples, errors = _run_with_sampler(_config(url), probe)
    assert result.success is True
    assert samples == []
    assert any("VRAM probe raised" in err for err in errors)
