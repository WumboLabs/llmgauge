"""Focused tests for the bounded concurrent VRAM sampler.

Covers the request-window sampler lifecycle (start/stop/join on all paths),
probe failure isolation, and the deterministic per-device peak calculation
over preserved samples used by the vLLM Area 4 builder.
"""

from __future__ import annotations

import time

from llmgauge.core.area4_evidence import (
    VLLM_PEAK_VRAM_BOUNDARY,
    _peak_vram_metric_records,
    build_vllm_area4_evidence,
)
from llmgauge.core.vram import VramSampler


def _probe(
    samples: list[list[dict]],
    errors: list[str | None] | None = None,
):
    """Build a probe callable returning successive canned reports.

    An `errors` entry at call index N makes only call N report unavailable
    with that error. Calls beyond the canned lists repeat the final report
    so workers never exhaust input.
    """
    errors = [None] * len(samples) if errors is None else errors
    state = {"index": 0}

    def probe() -> dict:
        index = min(state["index"], len(samples) - 1)
        state["index"] += 1
        error = errors[index] if index < len(errors) else None
        if error is not None:
            return {
                "schema_version": "llmgauge.vram.sample.v0",
                "available": False,
                "source": "nvidia-smi",
                "timestamp_utc": "2026-08-29T00:00:00+00:00",
                "samples": [],
                "error": error,
            }
        return {
            "schema_version": "llmgauge.vram.sample.v0",
            "available": True,
            "source": "nvidia-smi",
            "timestamp_utc": "2026-08-29T00:00:00+00:00",
            "samples": samples[index],
        }

    return probe


def _sample(gpu_index: int, gpu_name: str, used_mib: int) -> dict:
    return {
        "timestamp_utc": "2026-08-29T00:00:00+00:00",
        "gpu_index": gpu_index,
        "gpu_name": gpu_name,
        "used_mib": used_mib,
        "total_mib": 12227,
    }


# ---------------------------------------------------------------------------
# Sampler lifecycle
# ---------------------------------------------------------------------------


def test_sampler_start_takes_initial_sample_and_starts_worker() -> None:
    probe = _probe([[_sample(0, "GPU A", 1000)]])
    sampler = VramSampler(interval_seconds=0.05, probe=probe)
    sampler.start()
    assert sampler.is_alive() is True
    samples, errors = sampler.stop()
    assert sampler.is_alive() is False
    assert errors == []
    assert samples[0]["used_mib"] == 1000
    assert samples[0]["gpu_index"] == 0


def test_sampler_stop_takes_final_sample_and_joins() -> None:
    probe = _probe([[_sample(0, "GPU A", 1000)], [_sample(0, "GPU A", 2000)]])
    sampler = VramSampler(interval_seconds=0.05, probe=probe)
    sampler.start()
    time.sleep(0.12)
    samples, errors = sampler.stop()
    assert errors == []
    used = [item["used_mib"] for item in samples]
    # Initial sample + periodic sample(s) + final sample; ordered by capture.
    assert used[0] == 1000
    assert used[-1] == 2000
    assert len(used) >= 3
    assert sampler.is_alive() is False


def test_sampler_stop_before_start_is_safe() -> None:
    sampler = VramSampler(interval_seconds=0.05, probe=_probe([[]]))
    samples, _errors = sampler.stop()
    assert samples == []
    assert sampler.is_alive() is False


def test_sampler_collects_probe_errors_without_raising() -> None:
    probe = _probe(
        [[], [_sample(0, "GPU A", 1000)]],
        errors=["nvidia-smi timed out"],
    )
    sampler = VramSampler(interval_seconds=0.05, probe=probe)
    sampler.start()
    time.sleep(0.12)
    samples, errors = sampler.stop()
    assert any("nvidia-smi timed out" in err for err in errors)
    assert any(item["used_mib"] == 1000 for item in samples)


def test_sampler_survives_raising_probe() -> None:
    def probe() -> dict:
        raise OSError("boom")

    sampler = VramSampler(interval_seconds=0.05, probe=probe)
    sampler.start()
    samples, errors = sampler.stop()
    assert samples == []
    assert any("VRAM probe raised" in err for err in errors)
    assert sampler.is_alive() is False


def test_sampler_worker_stops_on_success_path() -> None:
    sampler = VramSampler(
        interval_seconds=0.02,
        probe=_probe([[_sample(0, "GPU A", 1000)]]),
    )
    sampler.start()
    sampler.stop()
    assert sampler.is_alive() is False


def test_sampler_ignores_malformed_probe_report() -> None:
    def probe() -> dict:
        return {"available": True, "samples": "not-a-list"}

    sampler = VramSampler(interval_seconds=0.05, probe=probe)
    sampler.start()
    samples, errors = sampler.stop()
    assert samples == []
    assert any("without a non-empty sample list" in err for err in errors)


# ---------------------------------------------------------------------------
# Peak calculation over preserved samples
# ---------------------------------------------------------------------------


def test_peak_calculation_single_device() -> None:
    samples = [
        _sample(0, "GPU A", 1000),
        _sample(0, "GPU A", 1200),
        _sample(0, "GPU A", 1100),
    ]
    records = _peak_vram_metric_records(samples, "vram/p1.samples.json")
    assert len(records) == 1
    record = records[0]
    assert record["value"] == 1200
    assert record["availability"] == "available"
    assert record["provenance"] == "calculated"
    assert record["unit"] == "MiB"
    assert record["device_scope"] == {"gpu_index": 0, "gpu_name": "GPU A"}
    assert record["sample_count"] == 3
    assert record["evidence_refs"] == ["vram/p1.samples.json#/samples"]


def test_peak_calculation_two_devices_independent() -> None:
    samples = [
        _sample(0, "GPU A", 1000),
        _sample(0, "GPU A", 1300),
        _sample(1, "GPU B", 2000),
        _sample(1, "GPU B", 2400),
    ]
    records = _peak_vram_metric_records(samples, "vram/p1.samples.json")
    by_index = {record["device_scope"]["gpu_index"]: record for record in records}
    assert set(by_index) == {0, 1}
    assert by_index[0]["value"] == 1300
    assert by_index[1]["value"] == 2400


def test_peak_in_middle_not_final_sample() -> None:
    samples = [
        _sample(0, "GPU A", 1000),
        _sample(0, "GPU A", 3000),
        _sample(0, "GPU A", 800),
    ]
    records = _peak_vram_metric_records(samples, "vram/p1.samples.json")
    assert records[0]["value"] == 3000


def test_no_samples_yields_unavailable_not_zero() -> None:
    records = _peak_vram_metric_records([], "vram/p1.samples.json")
    assert len(records) == 1
    record = records[0]
    assert record["availability"] == "unavailable"
    assert record["value"] is None
    assert record["provenance"] == "unavailable"
    assert record["sample_count"] == 0
    assert record["device_scope"] is None


def test_malformed_samples_fail_safe() -> None:
    records = _peak_vram_metric_records(
        [{"gpu_index": "bad", "used_mib": "bad"}, {"gpu_index": 0}],
        "vram/p1.samples.json",
    )
    assert len(records) == 1
    assert records[0]["availability"] == "unavailable"


def test_vllm_boundary_distinct_from_native() -> None:
    records = _peak_vram_metric_records(
        [_sample(0, "GPU A", 1000)],
        "vram/p1.samples.json",
        boundary=VLLM_PEAK_VRAM_BOUNDARY,
    )
    assert records[0]["boundary"] == VLLM_PEAK_VRAM_BOUNDARY


# ---------------------------------------------------------------------------
# vLLM Area 4 builder with request-window samples
# ---------------------------------------------------------------------------


def _prompt_entry(prompt_id: str, wall: float, samples: list[dict] | None) -> dict:
    evidence = {
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
    return {
        "prompt_id": prompt_id,
        "title": prompt_id,
        "category": "test",
        "status": "completed",
        "raw_prompt_path": f"raw/{prompt_id}.prompt.md",
        "raw_output_path": f"raw/{prompt_id}.output.txt",
        "cleaned_output_path": f"raw/{prompt_id}.output.txt",
        "stderr_log_path": f"logs/{prompt_id}.stderr.log",
        "request_evidence_path": f"request/{prompt_id}.json",
        "_area4_vllm_request_evidence": evidence,
        "metrics": {
            "request_wall_time_seconds": wall,
            "end_to_end_completion_tps": None,
        },
        "vram": None,
        "vram_samples_path": (
            f"vram/{prompt_id}.samples.json" if samples is not None else None
        ),
        "_area4_vram_samples": samples if samples is not None else None,
        "vram_guardrails": None,
        "score": None,
        "failure_labels": [],
        "notes": "",
        "exit_status": 0,
        "error": None,
        "failure_class": None,
        "failure_detail": None,
        "finish_reason": "stop",
    }


def _suite() -> dict:
    return {"suite_id": "core-v1", "suite_version": "1", "prompt_count": 1}


def _runtime() -> dict:
    return {"backend": "vllm", "max_tokens": 32, "temperature": 0.2, "top_p": 0.95}


def test_builder_emits_request_window_peak_records() -> None:
    prompt = _prompt_entry(
        "p1",
        1.25,
        [_sample(0, "GPU A", 1000), _sample(0, "GPU A", 1200)],
    )
    metrics, _ = build_vllm_area4_evidence(
        prompt_results=[prompt],  # type: ignore[arg-type]
        suite=_suite(),
        runtime=_runtime(),
    )
    records = metrics["measurements"][0]["metrics"]
    assert len(records) == 2
    peak = records[1]
    assert peak["metric_id"] == "llmgauge.metric.v1.peak_vram"
    assert peak["value"] == 1200
    assert peak["availability"] == "available"
    assert peak["provenance"] == "calculated"
    assert peak["boundary"] == VLLM_PEAK_VRAM_BOUNDARY
    assert peak["device_scope"] == {"gpu_index": 0, "gpu_name": "GPU A"}
    assert peak["sample_count"] == 2
    assert peak["evidence_refs"] == ["vram/p1.samples.json#/samples"]


def test_builder_unavailable_peak_when_sampler_had_no_samples() -> None:
    prompt = _prompt_entry("p1", 1.25, [])
    metrics, _ = build_vllm_area4_evidence(
        prompt_results=[prompt],  # type: ignore[arg-type]
        suite=_suite(),
        runtime=_runtime(),
    )
    peak = metrics["measurements"][0]["metrics"][1]
    assert peak["availability"] == "unavailable"
    assert peak["value"] is None


def test_builder_no_peak_record_without_artifact() -> None:
    prompt = _prompt_entry("p1", 1.25, None)
    metrics, _ = build_vllm_area4_evidence(
        prompt_results=[prompt],  # type: ignore[arg-type]
        suite=_suite(),
        runtime=_runtime(),
    )
    records = metrics["measurements"][0]["metrics"]
    assert len(records) == 1
    assert records[0]["metric_id"] == "llmgauge.metric.v1.request_wall_time"


def test_builder_no_peak_record_for_untransmitted_request() -> None:
    prompt = _prompt_entry("p1", 1.25, [_sample(0, "GPU A", 1000)])
    prompt["status"] = "failed"
    prompt["exit_status"] = 1
    prompt["_area4_vllm_request_evidence"]["request_transmitted"] = False
    metrics, _ = build_vllm_area4_evidence(
        prompt_results=[prompt],  # type: ignore[arg-type]
        suite=_suite(),
        runtime=_runtime(),
    )
    records = metrics["measurements"][0]["metrics"]
    assert len(records) == 1
