from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from llmgauge.cli import app
from llmgauge.core import localmaxxing as lmx


def artifact() -> dict:
    return lmx.make_artifact(
        hf_id="Qwen/Qwen3-8B",
        quantization="Q4_K_M",
        model_path="model.gguf",
        engine_version="b10449",
        backend="cuda",
        hardware={"hwClass": "DISCRETE_GPU", "gpuName": "RTX", "vramGb": 12},
        command="llama-bench -m model.gguf",
        executable="llama-bench",
        measurements=[
            {"tok_s_out": 10.0, "tok_s_prefill": 100.0},
            {"tok_s_out": 20.0, "tok_s_prefill": 200.0},
            {"tok_s_out": 30.0, "tok_s_prefill": 300.0},
            {"tok_s_out": 40.0, "tok_s_prefill": 400.0},
            {"tok_s_out": 50.0, "tok_s_prefill": 500.0},
        ],
    )


def test_artifact_fingerprint_and_export() -> None:
    value = artifact()
    valid, errors, ineligible = lmx.validate_artifact(value)
    assert valid and not errors and not ineligible
    assert "context_length" not in value["workload"]
    payload = lmx.export_payload(value)
    assert payload == {
        "hfId": "Qwen/Qwen3-8B",
        "modelRevision": "main",
        "hardware": value["hardware"],
        "engineName": "llama.cpp",
        "engineVersion": "b10449",
        "backend": "cuda",
        "quantization": "Q4_K_M",
        "promptTokens": 512,
        "outputTokens": 128,
        "batchSize": 1,
        "tokSOut": 30.0,
        "tokSPrefill": 300.0,
        "engineFlags": {"commandSnippet": "llama-bench -m model.gguf"},
        "notes": (
            "LLMGauge localmaxxing-llama-cpp-v1; one warmup excluded; "
            "five measured repetitions; full-GPU llama.cpp."
        ),
    }


def test_tamper_and_ineligibility_fail_closed() -> None:
    value = artifact()
    value["aggregate"]["tok_s_out"] = 5
    valid, errors, _ = lmx.validate_artifact(value)
    assert not valid and "artifact fingerprint mismatch" in errors
    value = artifact()
    value["aggregate"]["tok_s_out"] = 31.0
    value["fingerprint"] = lmx.fingerprint(value)
    valid, errors, _ = lmx.validate_artifact(value)
    assert not valid and "arithmetic mean" in errors[0]
    value = artifact()
    value["model"]["hf_id"] = None
    value["fingerprint"] = lmx.fingerprint(value)
    valid, _, ineligible = lmx.validate_artifact(value)
    assert valid and "missing canonical HuggingFace ID" in ineligible
    with pytest.raises(ValueError, match="ineligible"):
        lmx.export_payload(value)


def test_submit_refuses_without_confirmation(tmp_path) -> None:
    path = tmp_path / "benchmark.json"
    path.write_text(json.dumps(artifact()))
    result = CliRunner().invoke(app, ["localmaxxing", "submit", str(path)])
    assert result.exit_code == 2
    assert "public confirmation required" in result.output


def test_validate_and_export_are_offline(tmp_path, monkeypatch) -> None:
    path = tmp_path / "benchmark.json"
    path.write_text(json.dumps(artifact()))
    monkeypatch.setattr(lmx, "request_api", lambda *args: pytest.fail("network called"))
    runner = CliRunner()
    assert runner.invoke(app, ["localmaxxing", "validate", str(path)]).exit_code == 0
    result = runner.invoke(app, ["localmaxxing", "export", str(path)])
    assert result.exit_code == 0 and "tokSOut" in result.output


def test_atomic_publication_preserves_evidence_and_refuses_overwrite(tmp_path) -> None:
    destination = tmp_path / "result"
    path = lmx.save_artifact(
        artifact(), destination, {"exit_status": 0, "stdout": "[]"}
    )
    assert path.exists()
    assert (destination / "execution-evidence.json").exists()
    with pytest.raises(FileExistsError):
        lmx.save_artifact(artifact(), destination)


def test_online_request_requires_key_and_checks_context(monkeypatch) -> None:
    monkeypatch.delenv("LOCALMAXXING_API_KEY", raising=False)
    with pytest.raises(ValueError, match="LOCALMAXXING_API_KEY"):
        lmx.checked_online_request(artifact())
    monkeypatch.setenv("LOCALMAXXING_API_KEY", "secret-not-persisted")
    calls: list[tuple[str, object, object]] = []

    def request(path, payload=None, api_key=None):
        calls.append((path, payload, api_key))
        if path == "/api/openapi.json":
            return {
                "info": {"version": lmx.API_VERSION},
                "paths": {lmx.DRY_RUN_PATH: {}, lmx.SUBMIT_PATH: {}},
            }
        if path == lmx.AGENT_CONTEXT_PATH:
            return {
                "_meta": {
                    "dryRunEndpoint": "https://www.localmaxxing.com/api/speed-tests/dry-run"
                }
            }
        return {"valid": True}

    monkeypatch.setattr(lmx, "request_api", request)
    assert lmx.checked_online_request(artifact()) == {"valid": True}
    assert calls[-1][0] == lmx.DRY_RUN_PATH
    assert "secret-not-persisted" not in str(artifact())


def test_enriched_metrics_validate_and_export() -> None:
    value = artifact()
    samples = [
        {
            "timestamp_monotonic": float(index),
            "memory_used_mib": 1000.0 + index,
            "power_draw_w": 100.0 + index,
            "utilization_gpu_pct": 50.0 + index,
            "temperature_c": 60.0 + index,
        }
        for index in range(5)
    ]
    value.update(
        {
            "combined_measurements": [40.0 + index for index in range(5)],
            "ttft": {
                "samples_ms": [10.0 + index for index in range(5)],
                "mean_ms": 12.0,
            },
            "telemetry": lmx.summarize_telemetry(samples, 0.2),
            "runtime": {
                "gpu_placement": "full_gpu",
                "gpu_layers_requested": -1,
                "split_mode": "layer",
                "kv_cache": {"type_k": "f16", "type_v": "f16"},
                "flash_attention_requested": "auto",
            },
        }
    )
    value["aggregate"]["tok_s_total"] = 42.0
    value["fingerprint"] = lmx.fingerprint(value)
    valid, errors, _ = lmx.validate_artifact(value)
    assert valid, errors
    payload = lmx.export_payload(value)
    assert payload["tokSTotal"] == 42.0
    assert payload["ttftMs"] == 12.0
    assert payload["peakVramGb"] == 1004.0 / 1024
    assert payload["engineFlags"] == {
        "commandSnippet": "llama-bench -m model.gguf",
        "splitMode": "layer",
        "kvCacheDtype": "fp16",
    }
    assert "flashAttn" not in payload["engineFlags"]


def test_telemetry_and_combined_reject_invalid_aggregates() -> None:
    value = artifact()
    value["combined_measurements"] = [1.0] * 5
    value["aggregate"]["tok_s_total"] = 2.0
    value["fingerprint"] = lmx.fingerprint(value)
    valid, errors, _ = lmx.validate_artifact(value)
    assert not valid and "combined throughput" in errors[0]
    with pytest.raises(ValueError, match="combined throughput"):
        lmx.parse_llama_bench_combined_json("[]")


def test_runtime_metadata_preserves_unproven_flash_and_distinct_kv() -> None:
    output = json.dumps(
        [
            {
                "n_gpu_layers": -1,
                "n_batch": 2048,
                "n_ubatch": 512,
                "split_mode": "layer",
                "main_gpu": 0,
                "no_kv_offload": False,
                "type_k": "f16",
                "type_v": "q8_0",
                "flash_attn": -1,
                "devices": "auto",
                "load_mode": "auto",
            }
        ]
    )
    runtime = lmx.llama_bench_runtime_metadata(output)
    assert runtime["gpu_placement"] == "full_gpu"
    assert runtime["flash_attention_requested"] == "auto"
    assert runtime["kv_cache"] == {"type_k": "f16", "type_v": "q8_0"}
