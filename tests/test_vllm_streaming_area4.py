"""Area 4 streaming TTFT integration tests (builder, validator, report, export).

Builds synthetic stream evidence directly and through the synthetic SSE
server; validates the neutral TTFT metric records, recomputation, VRAM
coexistence, reporting, comparison, and public-export privacy.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from llmgauge.core.area4_evidence import (
    TTFT_BOUNDARY,
    TTFT_METRIC_ID,
    VLLM_STREAM_EVIDENCE_SCHEMA,
    build_vllm_area4_evidence,
)
from llmgauge.core.compare import compare_results, load_compare_result
from llmgauge.core.public_export import export_public_run
from llmgauge.core.reports import build_markdown_report
from llmgauge.core.result_validation import validate_result_dir
from llmgauge.core.run_fingerprint import _prompt_evidence
from llmgauge.runners.vllm_external import (
    OBSERVATION_METHOD,
    STREAM_TRANSPORT_MODE,
)


def _stream_evidence(
    *,
    events: list[dict[str, Any]] | None = None,
    first_token: dict[str, Any] | None = None,
    terminal_state: str = "done_received",
    vllm_version: str = "0.27.1",
) -> dict[str, Any]:
    events = events if events is not None else []
    return {
        "schema_version": VLLM_STREAM_EVIDENCE_SCHEMA,
        "transport_mode": STREAM_TRANSPORT_MODE,
        "streaming": True,
        "observation_method": OBSERVATION_METHOD,
        "vllm_version": vllm_version,
        "vllm_version_source": "server_/version",
        "version_qualification": {
            "admitted": True,
            "rule": "observed_version_exact_0.27.1",
            "observed_vllm_version": vllm_version,
        },
        "return_token_ids": True,
        "stream_options": {"include_usage": True},
        "request_start_relationship": "elapsed_seconds_since_transmit_start",
        "events": events,
        "first_token": first_token,
        "terminal": {
            "state": terminal_state,
            "finish_reason": "stop",
            "usage_present": True,
            "done_received": terminal_state == "done_received",
            "server_error": False,
            "malformed_event_index": None,
        },
        "failure": {"class": None, "detail": None},
    }


def _event(
    index: int, elapsed: float, count: int, trigger: bool = False
) -> dict[str, Any]:
    return {
        "index": index,
        "elapsed_seconds": elapsed,
        "kind": "data",
        "data": "{}",
        "token_ids_count": count,
        "ttft_trigger": trigger,
    }


def _token_stream_evidence() -> dict[str, Any]:
    return _stream_evidence(
        events=[
            _event(0, 0.01, 0),
            _event(1, 0.284, 1, trigger=True),
            _event(2, 1.1, 1),
        ],
        first_token={
            "event_index": 1,
            "elapsed_seconds": 0.284,
            "channel": "content",
            "token_ids_in_event": 1,
        },
    )


def _no_token_stream_evidence() -> dict[str, Any]:
    return _stream_evidence(
        events=[
            _event(0, 0.01, 0),
            _event(1, 0.5, 0),
        ],
        first_token=None,
    )


def _stream_request_evidence(wall: float = 2.43) -> dict[str, Any]:
    return {
        "schema_version": "llmgauge.vllm_request_evidence.v0",
        "lifecycle_ownership": "external_operator",
        "streaming": True,
        "transport_mode": STREAM_TRANSPORT_MODE,
        "observation_method": OBSERVATION_METHOD,
        "return_token_ids": True,
        "stream_options": {"include_usage": True},
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
        "time_to_first_token_seconds": 0.284,
        "first_token_channel": "content",
        "first_token_event_index": 1,
        "stream_terminal_state": "done_received",
    }


def _non_stream_request_evidence(wall: float = 2.43) -> dict[str, Any]:
    evidence = _stream_request_evidence(wall)
    evidence["streaming"] = False
    for field in (
        "transport_mode",
        "observation_method",
        "return_token_ids",
        "stream_options",
        "time_to_first_token_seconds",
        "first_token_channel",
        "first_token_event_index",
        "stream_terminal_state",
    ):
        evidence.pop(field, None)
    return evidence


def _no_event_stream_failure_request_evidence() -> dict[str, Any]:
    evidence = _stream_request_evidence()
    evidence.update(
        {
            "completion_tokens": None,
            "failure_class": "request_timeout",
            "failure_detail": "stream_timeout",
            "finish_reason": None,
            "time_to_first_token_seconds": None,
            "first_token_channel": None,
            "first_token_event_index": None,
            "stream_terminal_state": "timeout",
        }
    )
    return evidence


def _prompt_entry(
    prompt_id: str,
    evidence: dict[str, Any],
    stream_evidence: dict[str, Any] | None,
    *,
    vram_samples: list[dict[str, Any]] | None = None,
    vram_path: str | None = None,
) -> dict[str, Any]:
    failed = evidence.get("failure_class") is not None
    return {
        "prompt_id": prompt_id,
        "title": prompt_id,
        "category": "test",
        "status": "failed" if failed else "completed",
        "raw_prompt_path": f"raw/{prompt_id}.prompt.md",
        "raw_output_path": f"raw/{prompt_id}.output.txt",
        "cleaned_output_path": f"raw/{prompt_id}.output.txt",
        "stderr_log_path": f"logs/{prompt_id}.stderr.log",
        "request_evidence_path": f"request/{prompt_id}.json",
        "stream_evidence_path": (
            f"request/{prompt_id}.stream.json" if stream_evidence is not None else None
        ),
        "_area4_vllm_request_evidence": evidence,
        "_area4_vllm_stream_evidence": stream_evidence,
        "_area4_vram_samples": vram_samples,
        "metrics": {
            "request_wall_time_seconds": evidence.get("request_wall_time_seconds"),
            "end_to_end_completion_tps": None,
            "streaming": evidence.get("streaming", False),
            "time_to_first_token_seconds": evidence.get("time_to_first_token_seconds"),
            "first_token_channel": evidence.get("first_token_channel"),
        },
        "vram": None,
        "vram_samples_path": vram_path,
        "vram_guardrails": None,
        "score": None,
        "failure_labels": [],
        "notes": "",
        "exit_status": 1 if failed else 0,
        "error": evidence.get("failure_detail") if failed else None,
        "failure_class": evidence.get("failure_class"),
        "failure_detail": evidence.get("failure_detail"),
        "finish_reason": evidence.get("finish_reason"),
    }


def _vllm_result(
    prompt_entries: list[dict[str, Any]],
    *,
    streaming: bool = True,
) -> dict[str, Any]:
    runtime: dict[str, Any] = {
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
        "streaming": streaming,
        "transport_mode": STREAM_TRANSPORT_MODE if streaming else None,
        "vllm_streaming_evidence": streaming,
        "authentication": "none",
    }
    suite = {"suite_id": "core-v1", "suite_version": "1", "prompt_count": 1}
    completed = sum(1 for e in prompt_entries if e.get("status") == "completed")
    failed = len(prompt_entries) - completed
    result: dict[str, Any] = {
        "schema_version": "llmgauge.result.v0",
        "llmgauge_version": "0.76.0",
        "run": {
            "run_id": "vllm-stream-run",
            "timestamp_utc": "2026-08-29T00:00:00+00:00",
            "status": "completed" if failed == 0 else "failed",
            "result_dir": "vllm-stream-run",
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
        prompt_results=prompt_entries,
        suite=suite,
        runtime=runtime,
    )
    result["runtime_neutral_metrics"] = metrics
    result["failure_taxonomy"] = taxonomy
    return result


def _result_dir(tmp_path: Path, result: dict[str, Any]) -> Path:
    result_dir = tmp_path / str(result["run"]["run_id"])
    (result_dir / "raw").mkdir(parents=True)
    (result_dir / "logs").mkdir(parents=True)
    (result_dir / "request").mkdir(parents=True)
    for prompt in result["results"]:
        pid = prompt["prompt_id"]
        (result_dir / "raw" / f"{pid}.prompt.md").write_text("prompt", encoding="utf-8")
        (result_dir / "raw" / f"{pid}.output.txt").write_text(
            prompt.get("generated_text", "output"), encoding="utf-8"
        )
        (result_dir / "logs" / f"{pid}.stderr.log").write_text("ok", encoding="utf-8")
        (result_dir / "request" / f"{pid}.json").write_text(
            json.dumps(prompt["_area4_vllm_request_evidence"]), encoding="utf-8"
        )
        if prompt.get("_area4_vllm_stream_evidence") is not None:
            (result_dir / "request" / f"{pid}.stream.json").write_text(
                json.dumps(prompt["_area4_vllm_stream_evidence"]), encoding="utf-8"
            )
        if prompt.get("vram_samples_path"):
            (result_dir / "vram").mkdir(parents=True, exist_ok=True)
            (result_dir / prompt["vram_samples_path"]).write_text(
                json.dumps({"samples": prompt["_area4_vram_samples"]}), encoding="utf-8"
            )
    runtime = result.get("runtime")
    if isinstance(runtime, dict) and runtime.get("vllm_runtime_evidence_path"):
        (result_dir / "vllm-runtime-evidence.json").write_text(
            json.dumps(
                {
                    "schema_version": "llmgauge.vllm_runtime_evidence.v0",
                    "lifecycle_ownership": "external_operator",
                    "endpoint_identity": runtime.get("endpoint_identity", {}),
                    "requested_served_model": "test-model",
                    "observed_served_model": "test-model",
                    "vllm_version": "0.27.1",
                    "server_state": "ready",
                    "streaming": runtime.get("streaming", False),
                    "transport_mode": runtime.get("transport_mode"),
                    "observed_system_fingerprints": [],
                }
            ),
            encoding="utf-8",
        )
    from llmgauge.core.reports import build_markdown_report

    (result_dir / "llmgauge-result.json").write_text(
        json.dumps(result), encoding="utf-8"
    )
    (result_dir / "report.md").write_text(
        build_markdown_report(result, result_dir=result_dir), encoding="utf-8"
    )
    return result_dir


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------


def test_builder_emits_available_ttft_record() -> None:
    evidence = _stream_request_evidence()
    stream_ev = _token_stream_evidence()
    prompt = _prompt_entry("p1", evidence, stream_ev)
    result = _vllm_result([prompt])
    metrics = result["runtime_neutral_metrics"]["measurements"][0]
    ttft = [r for r in metrics["metrics"] if r["metric_id"] == TTFT_METRIC_ID]
    assert len(ttft) == 1
    assert ttft[0]["availability"] == "available"
    assert ttft[0]["value"] == 0.284
    assert ttft[0]["unit"] == "s"
    assert ttft[0]["provenance"] == "llmgauge_observed"
    assert ttft[0]["boundary"] == TTFT_BOUNDARY
    assert ttft[0]["equivalence"] == "unproven"
    assert ttft[0]["evidence_refs"] == [
        "request/p1.stream.json#/first_token/elapsed_seconds"
    ]


def test_builder_emits_unavailable_ttft_for_no_token_stream() -> None:
    evidence = _stream_request_evidence()
    evidence["time_to_first_token_seconds"] = None
    evidence["first_token_channel"] = None
    evidence["first_token_event_index"] = None
    stream_ev = _no_token_stream_evidence()
    prompt = _prompt_entry("p1", evidence, stream_ev)
    result = _vllm_result([prompt])
    metrics = result["runtime_neutral_metrics"]["measurements"][0]
    ttft = [r for r in metrics["metrics"] if r["metric_id"] == TTFT_METRIC_ID]
    assert len(ttft) == 1
    assert ttft[0]["availability"] == "unavailable"
    assert ttft[0]["value"] is None
    assert ttft[0]["provenance"] == "unavailable"
    assert ttft[0]["equivalence"] == "unavailable"


def test_builder_no_ttft_record_for_non_streaming() -> None:
    evidence = _stream_request_evidence()
    evidence["streaming"] = False
    evidence.pop("transport_mode", None)
    evidence.pop("observation_method", None)
    evidence.pop("return_token_ids", None)
    evidence.pop("stream_options", None)
    evidence.pop("time_to_first_token_seconds", None)
    evidence.pop("first_token_channel", None)
    evidence.pop("first_token_event_index", None)
    evidence.pop("stream_terminal_state", None)
    prompt = _prompt_entry("p1", evidence, None)
    result = _vllm_result([prompt], streaming=False)
    metrics = result["runtime_neutral_metrics"]["measurements"][0]
    ttft = [r for r in metrics["metrics"] if r["metric_id"] == TTFT_METRIC_ID]
    assert ttft == []


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------


def test_validator_accepts_streaming_ttft(tmp_path: Path) -> None:
    evidence = _stream_request_evidence()
    prompt = _prompt_entry("p1", evidence, _token_stream_evidence())
    result = _vllm_result([prompt])
    result_dir = _result_dir(tmp_path, result)
    assert validate_result_dir(result_dir) == []


def test_validator_rejects_real_streaming_runtime_contradiction(
    tmp_path: Path,
) -> None:
    prompt = _prompt_entry("p1", _stream_request_evidence(), _token_stream_evidence())
    result = _vllm_result([prompt])
    result["runtime"]["transport_mode"] = None
    result_dir = _result_dir(tmp_path, result)
    runtime_evidence_path = result_dir / "vllm-runtime-evidence.json"
    runtime_evidence = json.loads(runtime_evidence_path.read_text(encoding="utf-8"))
    runtime_evidence["streaming"] = False
    runtime_evidence.pop("transport_mode", None)
    runtime_evidence_path.write_text(json.dumps(runtime_evidence), encoding="utf-8")

    errors = validate_result_dir(result_dir)

    assert any("streaming" in error.lower() for error in errors)
    assert any(
        "request evidence.streaming differs from vLLM runtime evidence.streaming"
        in error
        for error in errors
    )


def test_validator_rejects_nonstream_runtime_with_streaming_runtime_evidence(
    tmp_path: Path,
) -> None:
    prompt = _prompt_entry("p1", _non_stream_request_evidence(), None)
    result = _vllm_result([prompt], streaming=False)
    result_dir = _result_dir(tmp_path, result)
    runtime_evidence_path = result_dir / "vllm-runtime-evidence.json"
    runtime_evidence = json.loads(runtime_evidence_path.read_text(encoding="utf-8"))
    runtime_evidence["streaming"] = True
    runtime_evidence["transport_mode"] = STREAM_TRANSPORT_MODE
    runtime_evidence_path.write_text(json.dumps(runtime_evidence), encoding="utf-8")

    errors = validate_result_dir(result_dir)

    assert any("runtime.streaming differs" in error for error in errors)
    assert any(
        "request evidence.streaming differs from vLLM runtime evidence.streaming"
        in error
        for error in errors
    )


def test_validator_rejects_streaming_runtime_without_transport(
    tmp_path: Path,
) -> None:
    prompt = _prompt_entry("p1", _stream_request_evidence(), _token_stream_evidence())
    result = _vllm_result([prompt])
    result["runtime"]["transport_mode"] = None
    result_dir = _result_dir(tmp_path, result)

    errors = validate_result_dir(result_dir)

    assert any("transport_mode" in error for error in errors)


def test_validator_rejects_streaming_runtime_with_wrong_transport(
    tmp_path: Path,
) -> None:
    prompt = _prompt_entry("p1", _stream_request_evidence(), _token_stream_evidence())
    result = _vllm_result([prompt])
    result["runtime"]["transport_mode"] = "openai_compatible_json"
    result_dir = _result_dir(tmp_path, result)

    errors = validate_result_dir(result_dir)

    assert any("transport_mode" in error for error in errors)


def test_validator_rejects_nonstream_request_in_streaming_run(
    tmp_path: Path,
) -> None:
    prompt = _prompt_entry("p1", _stream_request_evidence(), _token_stream_evidence())
    result = _vllm_result([prompt])
    result_dir = _result_dir(tmp_path, result)
    request_path = result_dir / "request/p1.json"
    request_evidence = json.loads(request_path.read_text(encoding="utf-8"))
    request_evidence["streaming"] = False
    request_evidence.pop("transport_mode", None)
    request_path.write_text(json.dumps(request_evidence), encoding="utf-8")

    errors = validate_result_dir(result_dir)

    assert any("request evidence.streaming differs" in error for error in errors)


def test_validator_rejects_stream_artifact_for_nonstream_request(
    tmp_path: Path,
) -> None:
    prompt = _prompt_entry("p1", _non_stream_request_evidence(), None)
    result = _vllm_result([prompt], streaming=False)
    result["results"][0]["stream_evidence_path"] = "request/p1.stream.json"
    result_dir = _result_dir(tmp_path, result)
    (result_dir / "request/p1.stream.json").write_text(
        json.dumps(_token_stream_evidence()),
        encoding="utf-8",
    )
    (result_dir / "llmgauge-result.json").write_text(
        json.dumps(result),
        encoding="utf-8",
    )

    errors = validate_result_dir(result_dir)

    assert any("stream evidence is incompatible" in error for error in errors)


def test_validator_rejects_ttft_metric_for_nonstreaming_run(
    tmp_path: Path,
) -> None:
    prompt = _prompt_entry("p1", _non_stream_request_evidence(), None)
    result = _vllm_result([prompt], streaming=False)
    result["runtime_neutral_metrics"]["measurements"][0]["metrics"].append(
        {
            "metric_id": TTFT_METRIC_ID,
            "native_metric_id": "time_to_first_token_seconds",
            "value": 0.1,
            "unit": "s",
            "availability": "available",
            "provenance": "llmgauge_observed",
            "boundary": TTFT_BOUNDARY,
            "equivalence": "unproven",
            "channel": "content",
            "evidence_refs": ["request/p1.stream.json#/first_token/elapsed_seconds"],
        }
    )
    result_dir = _result_dir(tmp_path, result)

    errors = validate_result_dir(result_dir)

    assert any("TTFT is incompatible" in error for error in errors)


def test_validator_accepts_pretransmission_streaming_capability_failure(
    tmp_path: Path,
) -> None:
    request_evidence = {
        "schema_version": "llmgauge.vllm_request_evidence.v0",
        "lifecycle_ownership": "external_operator",
        "skipped": True,
        "skip_reason": "streaming_ttft_version_unsupported",
        "failure_class": "unsupported_capability",
        "failure_detail": "streaming_ttft_unsupported",
        "endpoint_identity": {},
    }
    prompt = _prompt_entry("p1", request_evidence, None)
    result = _vllm_result([prompt])
    result_dir = _result_dir(tmp_path, result)

    assert validate_result_dir(result_dir) == []


def test_validator_accepts_no_event_streaming_failure_without_stream_artifact(
    tmp_path: Path,
) -> None:
    prompt = _prompt_entry(
        "p1",
        _no_event_stream_failure_request_evidence(),
        None,
    )
    result = _vllm_result([prompt])
    result_dir = _result_dir(tmp_path, result)

    assert validate_result_dir(result_dir) == []


def test_validator_requires_observation_for_transmitted_streaming_failure(
    tmp_path: Path,
) -> None:
    request_evidence = _no_event_stream_failure_request_evidence()
    request_evidence.pop("observation_method")
    prompt = _prompt_entry("p1", request_evidence, None)
    result = _vllm_result([prompt])
    result_dir = _result_dir(tmp_path, result)

    errors = validate_result_dir(result_dir)

    assert any("observation_method" in error for error in errors)


def test_validator_rejects_unqualified_streaming_runtime_without_stream_artifact(
    tmp_path: Path,
) -> None:
    prompt = _prompt_entry(
        "p1",
        _no_event_stream_failure_request_evidence(),
        None,
    )
    result = _vllm_result([prompt])
    result_dir = _result_dir(tmp_path, result)
    runtime_evidence_path = result_dir / "vllm-runtime-evidence.json"
    runtime_evidence = json.loads(runtime_evidence_path.read_text(encoding="utf-8"))
    runtime_evidence["vllm_version"] = "0.27.2"
    runtime_evidence_path.write_text(json.dumps(runtime_evidence), encoding="utf-8")

    errors = validate_result_dir(result_dir)

    assert any("streaming version is not qualified" in error for error in errors)


@pytest.mark.parametrize("with_ttft", [False, True], ids=["without-ttft", "with-ttft"])
def test_validator_accepts_consistent_midstream_failure(
    tmp_path: Path,
    with_ttft: bool,
) -> None:
    request_evidence = _stream_request_evidence()
    request_evidence.update(
        {
            "failure_class": "request_timeout",
            "failure_detail": "stream_timeout",
            "finish_reason": None,
            "stream_terminal_state": "timeout",
        }
    )
    if with_ttft:
        stream_evidence = _token_stream_evidence()
    else:
        request_evidence["time_to_first_token_seconds"] = None
        request_evidence["first_token_channel"] = None
        request_evidence["first_token_event_index"] = None
        stream_evidence = _no_token_stream_evidence()
    stream_evidence["terminal"].update(
        {
            "state": "timeout",
            "finish_reason": None,
            "done_received": False,
        }
    )
    stream_evidence["failure"] = {
        "class": "request_timeout",
        "detail": "stream_timeout",
    }
    prompt = _prompt_entry("p1", request_evidence, stream_evidence)
    result = _vllm_result([prompt])
    result_dir = _result_dir(tmp_path, result)

    assert validate_result_dir(result_dir) == []


def test_validator_rejects_forged_version_qualification(tmp_path: Path) -> None:
    """A stored admitted=true must not survive recomputation against the
    represented observed version; vLLM 0.99.0 is not qualified for V1."""
    evidence = _stream_request_evidence()
    stream_ev = _stream_evidence(
        events=[
            _event(0, 0.01, 0),
            _event(1, 0.284, 1, trigger=True),
        ],
        first_token={
            "event_index": 1,
            "elapsed_seconds": 0.284,
            "channel": "content",
            "token_ids_in_event": 1,
        },
        vllm_version="0.99.0",
    )
    # Forge the stored boolean and rule while keeping the observed version.
    stream_ev["version_qualification"] = {
        "admitted": True,
        "rule": "observed_version_exact_0.27.1",
        "observed_vllm_version": "0.99.0",
    }
    prompt = _prompt_entry("p1", evidence, stream_ev)
    result = _vllm_result([prompt])
    result_dir = _result_dir(tmp_path, result)
    errors = validate_result_dir(result_dir)
    assert any("version qualification" in err for err in errors)


def test_validator_rejects_qualification_version_mismatch(tmp_path: Path) -> None:
    """The qualification observed version must match the top-level stream
    vLLM version recorded in the artifact."""
    evidence = _stream_request_evidence()
    stream_ev = _token_stream_evidence()
    stream_ev["vllm_version"] = "0.27.2"
    prompt = _prompt_entry("p1", evidence, stream_ev)
    result = _vllm_result([prompt])
    result_dir = _result_dir(tmp_path, result)
    errors = validate_result_dir(result_dir)
    assert any("version qualification" in err for err in errors)


def test_validator_accepts_no_token_stream_unavailable_ttft(tmp_path: Path) -> None:
    evidence = _stream_request_evidence()
    evidence["time_to_first_token_seconds"] = None
    evidence["first_token_channel"] = None
    evidence["first_token_event_index"] = None
    prompt = _prompt_entry("p1", evidence, _no_token_stream_evidence())
    result = _vllm_result([prompt])
    result_dir = _result_dir(tmp_path, result)
    assert validate_result_dir(result_dir) == []


def test_validator_rejects_wrong_ttft_value(tmp_path: Path) -> None:
    evidence = _stream_request_evidence()
    prompt = _prompt_entry("p1", evidence, _token_stream_evidence())
    result = _vllm_result([prompt])
    # Tamper with the represented TTFT value after building.
    measurement = result["runtime_neutral_metrics"]["measurements"][0]
    for record in measurement["metrics"]:
        if record["metric_id"] == TTFT_METRIC_ID:
            record["value"] = 0.999
    result_dir = _result_dir(tmp_path, result)
    errors = validate_result_dir(result_dir)
    assert any("TTFT" in err or "records differ" in err for err in errors)


def test_validator_rejects_later_token_selected(tmp_path: Path) -> None:
    evidence = _stream_request_evidence()
    evidence["time_to_first_token_seconds"] = 1.1
    evidence["first_token_channel"] = "content"
    evidence["first_token_event_index"] = 2
    stream_ev = _stream_evidence(
        events=[
            _event(0, 0.01, 0),
            _event(1, 0.284, 1, trigger=True),
            _event(2, 1.1, 1, trigger=True),
        ],
        first_token={
            "event_index": 2,
            "elapsed_seconds": 1.1,
            "channel": "content",
            "token_ids_in_event": 1,
        },
    )
    prompt = _prompt_entry("p1", evidence, stream_ev)
    result = _vllm_result([prompt])
    result_dir = _result_dir(tmp_path, result)
    errors = validate_result_dir(result_dir)
    assert any("earlier token" in err for err in errors)


def test_validator_rejects_missing_stream_evidence(tmp_path: Path) -> None:
    evidence = _stream_request_evidence()
    prompt = _prompt_entry("p1", evidence, None)
    result = _vllm_result([prompt])
    result_dir = _result_dir(tmp_path, result)
    errors = validate_result_dir(result_dir)
    assert any("TTFT" in err or "stream" in err.lower() for err in errors)


def test_validator_rejects_ttft_for_non_streaming(tmp_path: Path) -> None:
    evidence = _stream_request_evidence()
    evidence["streaming"] = False
    evidence.pop("transport_mode", None)
    evidence.pop("observation_method", None)
    evidence.pop("return_token_ids", None)
    evidence.pop("stream_options", None)
    evidence.pop("time_to_first_token_seconds", None)
    evidence.pop("first_token_channel", None)
    evidence.pop("first_token_event_index", None)
    evidence.pop("stream_terminal_state", None)
    prompt = _prompt_entry("p1", evidence, None)
    result = _vllm_result([prompt], streaming=False)
    result_dir = _result_dir(tmp_path, result)
    assert validate_result_dir(result_dir) == []


def test_validator_malformed_token_ids_ttft_unavailable(tmp_path: Path) -> None:
    evidence = _stream_request_evidence()
    evidence["time_to_first_token_seconds"] = None
    evidence["first_token_channel"] = None
    evidence["first_token_event_index"] = None
    stream_ev = _stream_evidence(
        events=[_event(0, 0.01, 0)],
        first_token=None,
        terminal_state="malformed",
    )
    prompt = _prompt_entry("p1", evidence, stream_ev)
    result = _vllm_result([prompt])
    # Malformed token IDs: no first token -> TTFT unavailable -> validates cleanly.
    result_dir = _result_dir(tmp_path, result)
    measurement = result["runtime_neutral_metrics"]["measurements"][0]
    ttft = [r for r in measurement["metrics"] if r["metric_id"] == TTFT_METRIC_ID]
    assert len(ttft) == 1
    assert ttft[0]["availability"] == "unavailable"
    assert validate_result_dir(result_dir) == []


def test_validator_rejects_wrong_channel(tmp_path: Path) -> None:
    evidence = _stream_request_evidence()
    evidence["first_token_channel"] = "unknown_channel"
    prompt = _prompt_entry("p1", evidence, _token_stream_evidence())
    result = _vllm_result([prompt])
    result_dir = _result_dir(tmp_path, result)
    errors = validate_result_dir(result_dir)
    assert any("channel" in err for err in errors)


def test_streaming_with_vram_coexists(tmp_path: Path) -> None:
    evidence = _stream_request_evidence()
    vram_samples = [
        {
            "timestamp_utc": "2026-08-29T00:00:00+00:00",
            "gpu_index": 0,
            "gpu_name": "test",
            "used_mib": 1024,
            "total_mib": 12288,
        },
        {
            "timestamp_utc": "2026-08-29T00:00:01+00:00",
            "gpu_index": 0,
            "gpu_name": "test",
            "used_mib": 10824,
            "total_mib": 12288,
        },
    ]
    prompt = _prompt_entry(
        "p1",
        evidence,
        _token_stream_evidence(),
        vram_samples=vram_samples,
        vram_path="vram/p1.samples.json",
    )
    result = _vllm_result([prompt])
    measurement = result["runtime_neutral_metrics"]["measurements"][0]
    metric_ids = [r["metric_id"] for r in measurement["metrics"]]
    assert TTFT_METRIC_ID in metric_ids
    assert "llmgauge.metric.v1.peak_vram" in metric_ids
    assert "llmgauge.metric.v1.request_wall_time" in metric_ids
    result_dir = _result_dir(tmp_path, result)
    assert validate_result_dir(result_dir) == []


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def test_report_renders_ttft(tmp_path: Path) -> None:
    prompt = _prompt_entry("p1", _stream_request_evidence(), _token_stream_evidence())
    result = _vllm_result([prompt])
    result_dir = _result_dir(tmp_path, result)
    report = build_markdown_report(result, result_dir=result_dir)
    assert "TTFT: 0.284 s (available)" in report
    assert "TTFT provenance" in report
    assert "TTFT boundary" in report
    assert "First token channel: content" in report
    assert "vLLM SSE streaming" in report
    assert "- Streaming: True" in report
    assert f"- Transport mode: {STREAM_TRANSPORT_MODE}" in report


def test_report_never_labels_missing_streaming_transport_non_streaming(
    tmp_path: Path,
) -> None:
    prompt = _prompt_entry("p1", _stream_request_evidence(), _token_stream_evidence())
    result = _vllm_result([prompt])
    result["runtime"]["transport_mode"] = None
    result_dir = _result_dir(tmp_path, result)

    report = build_markdown_report(result, result_dir=result_dir)

    assert "- Streaming: True" in report
    assert "- Transport mode: non-streaming" not in report
    assert "unavailable (streaming transport metadata missing)" in report


def test_report_renders_unavailable_ttft(tmp_path: Path) -> None:
    evidence = _stream_request_evidence()
    evidence["time_to_first_token_seconds"] = None
    evidence["first_token_channel"] = None
    evidence["first_token_event_index"] = None
    prompt = _prompt_entry("p1", evidence, _no_token_stream_evidence())
    result = _vllm_result([prompt])
    result_dir = _result_dir(tmp_path, result)
    report = build_markdown_report(result, result_dir=result_dir)
    assert "TTFT: unavailable" in report


def test_report_non_streaming_ttft_line(tmp_path: Path) -> None:
    evidence = _stream_request_evidence()
    evidence["streaming"] = False
    evidence.pop("transport_mode", None)
    evidence.pop("observation_method", None)
    evidence.pop("return_token_ids", None)
    evidence.pop("stream_options", None)
    evidence.pop("time_to_first_token_seconds", None)
    evidence.pop("first_token_channel", None)
    evidence.pop("first_token_event_index", None)
    evidence.pop("stream_terminal_state", None)
    prompt = _prompt_entry("p1", evidence, None)
    result = _vllm_result([prompt], streaming=False)
    result_dir = _result_dir(tmp_path, result)
    report = build_markdown_report(result, result_dir=result_dir)
    assert "TTFT: unavailable (non-streaming transport)" in report
    assert "- Streaming: False" in report
    assert "- Transport mode: non-streaming" in report


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------


def test_comparison_discloses_streaming_and_ttft(tmp_path: Path) -> None:
    prompt = _prompt_entry("p1", _stream_request_evidence(), _token_stream_evidence())
    streaming_result = _vllm_result([prompt], streaming=True)
    streaming_dir = _result_dir(tmp_path / "a", streaming_result)

    non_stream_prompt = _prompt_entry("p1", _non_stream_request_evidence(), None)
    non_stream_result = _vllm_result([non_stream_prompt], streaming=False)
    non_stream_result["run"]["run_id"] = "vllm-control-run"
    non_stream_dir = _result_dir(tmp_path / "b", non_stream_result)

    report = compare_results(
        [
            load_compare_result(streaming_dir),
            load_compare_result(non_stream_dir),
        ]
    )

    assert "streaming" in report
    assert "non-streaming" in report
    assert "0.284" in report
    assert STREAM_TRANSPORT_MODE in report
    assert OBSERVATION_METHOD in report
    assert "not applicable" in report
    assert "not a universal ranking" in report


def test_comparison_rejects_contradictory_source_result(tmp_path: Path) -> None:
    prompt = _prompt_entry("p1", _stream_request_evidence(), _token_stream_evidence())
    result = _vllm_result([prompt])
    result_dir = _result_dir(tmp_path, result)
    runtime_evidence_path = result_dir / "vllm-runtime-evidence.json"
    runtime_evidence = json.loads(runtime_evidence_path.read_text(encoding="utf-8"))
    runtime_evidence["streaming"] = False
    runtime_evidence.pop("transport_mode", None)
    runtime_evidence_path.write_text(json.dumps(runtime_evidence), encoding="utf-8")

    with pytest.raises(ValueError, match="Source result validation failed"):
        load_compare_result(result_dir)


# ---------------------------------------------------------------------------
# Public export privacy
# ---------------------------------------------------------------------------


def test_public_export_omits_stream_evidence_and_ttft(tmp_path: Path) -> None:
    prompt = _prompt_entry("p1", _stream_request_evidence(), _token_stream_evidence())
    result = _vllm_result([prompt])
    result_dir = _result_dir(tmp_path, result)
    export_dir = tmp_path / "export"
    manifest = export_public_run(result_dir, export_dir)
    # Stream evidence file must be omitted (not transformed).
    assert not (export_dir / "request" / "p1.stream.json").exists()
    omitted = manifest.get("files_omitted", [])
    assert "request/p1.stream.json" in omitted
    # Exported result JSON must not contain TTFT records or stream refs.
    exported = json.loads(
        (export_dir / "llmgauge-result.json").read_text(encoding="utf-8")
    )
    measurements = exported["runtime_neutral_metrics"]["measurements"]
    for measurement in measurements:
        for record in measurement["metrics"]:
            assert record["metric_id"] != TTFT_METRIC_ID
    for prompt_result in exported["results"]:
        assert prompt_result.get("stream_evidence_path") is None
        assert prompt_result.get("time_to_first_token_seconds") is None
        assert prompt_result.get("first_token_channel") is None
    # Exported report must not leak TTFT lines.
    report_text = (export_dir / "report.md").read_text(encoding="utf-8")
    assert "TTFT" not in report_text
    # Exported request evidence must not carry stream refs or TTFT values.
    request_ev = json.loads(
        (export_dir / "request" / "p1.json").read_text(encoding="utf-8")
    )
    assert request_ev.get("stream_evidence_path") is None
    assert request_ev.get("time_to_first_token_seconds") is None
    assert request_ev["streaming"] is True  # transport mode stays disclosed
    assert request_ev["transport_mode"] == STREAM_TRANSPORT_MODE
    assert request_ev["observation_method"] == OBSERVATION_METHOD


# ---------------------------------------------------------------------------
# Fingerprint coverage
# ---------------------------------------------------------------------------


def test_fingerprint_payload_hashes_stream_evidence(tmp_path: Path) -> None:
    prompt = _prompt_entry("p1", _stream_request_evidence(), _token_stream_evidence())
    result = _vllm_result([prompt])
    result_dir = _result_dir(tmp_path, result)
    payload = _prompt_evidence(
        result_dir,
        result["results"][0],
        index=0,
        include_native_execution_evidence=True,
    )
    assert "stream_evidence" in payload["artifact_sha256"]
    assert payload["artifact_paths"]["stream_evidence_path"] == "request/p1.stream.json"
