import pytest

from llmgauge.core.fit_ladder import (
    build_context_fallback_plan,
    build_fit_attempt_plan,
    build_fit_attempt_record,
    build_fit_ladder_summary,
    classify_fit_failure,
)


def test_build_context_fallback_plan_starts_with_requested_context() -> None:
    assert build_context_fallback_plan(
        requested_ctx=65536,
        fallback_contexts=[8192, 16384, 32768, 65536],
    ) == [65536, 32768, 16384, 8192]


def test_build_context_fallback_plan_includes_non_ladder_requested_context() -> None:
    assert build_context_fallback_plan(
        requested_ctx=24576,
        fallback_contexts=[8192, 16384, 32768],
    ) == [24576, 16384, 8192]


def test_build_context_fallback_plan_rejects_nonpositive_context() -> None:
    with pytest.raises(ValueError, match="requested_ctx must be positive"):
        build_context_fallback_plan(
            requested_ctx=0,
            fallback_contexts=[8192],
        )


def test_build_fit_attempt_plan_records_context_fallback_axis() -> None:
    attempts = build_fit_attempt_plan(
        requested_ctx=32768,
        fallback_contexts=[8192, 16384, 32768],
        batch_size=256,
        ubatch_size=64,
        gpu_layers=999,
    )

    assert [attempt["ctx_size"] for attempt in attempts] == [32768, 16384, 8192]
    assert attempts[0]["is_requested_settings"] is True
    assert attempts[0]["fallback_axes"] == []
    assert attempts[1]["fallback_axes"] == ["context"]


def test_classify_fit_failure_detects_oom() -> None:
    classification = classify_fit_failure(
        exit_status=1,
        stderr="llama.cpp failed: CUDA error: out of memory",
    )

    assert classification["status"] == "failed"
    assert classification["failure_class"] == "oom"
    assert classification["retryable"] is True


def test_classify_fit_failure_detects_process_killed() -> None:
    classification = classify_fit_failure(
        exit_status=137,
        stderr="Killed",
    )

    assert classification["failure_class"] == "process_killed"
    assert classification["retryable"] is True


def test_classify_fit_failure_records_generic_runtime_error() -> None:
    classification = classify_fit_failure(
        exit_status=2,
        stderr="unknown command line option",
    )

    assert classification["failure_class"] == "runtime_error"
    assert classification["retryable"] is False


def test_build_fit_attempt_record_preserves_failure_metadata() -> None:
    record = build_fit_attempt_record(
        attempt_id="attempt-01",
        ctx_size=65536,
        batch_size=256,
        ubatch_size=64,
        gpu_layers=999,
        exit_status=1,
        stderr="CUDA malloc failed: out of memory",
        result_dir="results/fit/attempt-01",
        vram_summary={"available": True, "peak_used_mib": 12000},
    )

    assert record["schema_version"] == "llmgauge.fit_attempt.v0"
    assert record["status"] == "failed"
    assert record["failure_class"] == "oom"
    assert record["retryable"] is True
    assert record["result_dir"] == "results/fit/attempt-01"
    assert record["vram"]["peak_used_mib"] == 12000


def test_build_fit_ladder_summary_selects_first_completed_attempt() -> None:
    attempts = [
        build_fit_attempt_record(
            attempt_id="attempt-01",
            ctx_size=65536,
            batch_size=256,
            ubatch_size=64,
            gpu_layers=999,
            exit_status=1,
            stderr="CUDA error: out of memory",
        ),
        build_fit_attempt_record(
            attempt_id="attempt-02",
            ctx_size=32768,
            batch_size=256,
            ubatch_size=64,
            gpu_layers=999,
            exit_status=0,
            stdout="ok",
        ),
    ]

    summary = build_fit_ladder_summary(
        fit_ladder_id="fit-test",
        requested_settings={
            "ctx_size": 65536,
            "batch_size": 256,
            "ubatch_size": 64,
            "gpu_layers": 999,
        },
        retry_policy={
            "fallback_order": ["context"],
            "gpu_layer_fallback": "explicit-only",
        },
        attempts=attempts,
    )

    assert summary["schema_version"] == "llmgauge.fit_ladder.v0"
    assert summary["final_status"] == "completed_with_fallback"
    assert summary["selected_working_settings"]["ctx_size"] == 32768
    assert summary["summary"]["attempted"] == 2
    assert summary["summary"]["failed"] == 1
    assert summary["summary"]["oom_detected"] is True
    assert summary["summary"]["fallback_changed_context"] is True


def test_build_fit_ladder_summary_records_total_failure() -> None:
    attempts = [
        build_fit_attempt_record(
            attempt_id="attempt-01",
            ctx_size=32768,
            batch_size=256,
            ubatch_size=64,
            gpu_layers=999,
            exit_status=1,
            stderr="runtime failure",
        ),
    ]

    summary = build_fit_ladder_summary(
        fit_ladder_id="fit-failed",
        requested_settings={"ctx_size": 32768},
        retry_policy={"fallback_order": ["context"]},
        attempts=attempts,
    )

    assert summary["final_status"] == "failed"
    assert summary["selected_working_settings"] is None
    assert summary["summary"]["completed"] == 0
