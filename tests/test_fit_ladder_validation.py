from pathlib import Path

from llmgauge.core.artifacts import write_json
from llmgauge.core.fit_ladder_validation import validate_fit_ladder_dir


def _write_valid_child_result(path: Path, *, run_id: str, ctx_size: int) -> None:
    path.mkdir(parents=True)
    (path / "raw").mkdir()
    (path / "logs").mkdir()
    (path / "raw" / "prompt-a.prompt.md").write_text("prompt", encoding="utf-8")
    (path / "raw" / "prompt-a.output.txt").write_text("output", encoding="utf-8")
    (path / "logs" / "prompt-a.stderr.log").write_text("", encoding="utf-8")
    write_json(
        path / "llmgauge-result.json",
        {
            "schema_version": "llmgauge.result.v0",
            "llmgauge_version": "0.1.0",
            "run": {
                "run_id": run_id,
                "timestamp_utc": "2026-06-23T00:00:00+00:00",
                "status": "completed",
                "result_dir": str(path),
            },
            "model": {
                "model_id": "test-model",
                "model_profile": "test-profile",
                "model_path": "redacted",
                "model_path_policy": "redacted",
            },
            "runtime": {
                "backend": "llama.cpp",
                "ctx_size": ctx_size,
                "max_tokens": 100,
                "temperature": 0.2,
                "top_p": 0.95,
                "batch_size": 256,
                "ubatch_size": 64,
                "gpu_layers": 999,
                "command": [],
            },
            "suite": {
                "suite_id": "core-v1",
                "suite_version": "0.1.0",
                "suite_path": "suites/core-v1",
                "prompt_count": 1,
                "include": "honesty",
                "only": None,
            },
            "results": [
                {
                    "prompt_id": "prompt-a",
                    "title": "Prompt A",
                    "category": "honesty",
                    "status": "completed",
                    "raw_prompt_path": "raw/prompt-a.prompt.md",
                    "raw_output_path": "raw/prompt-a.output.txt",
                    "stderr_log_path": "logs/prompt-a.stderr.log",
                    "metrics": {},
                    "score": None,
                    "failure_labels": [],
                    "notes": "",
                    "exit_status": 0,
                    "error": None,
                }
            ],
            "summary": {
                "completed": 1,
                "failed": 0,
                "manual_score_total": None,
                "manual_score_max": None,
                "failure_labels": {},
            },
        },
    )
    (path / "report.md").write_text("# Report\n", encoding="utf-8")


def test_validate_fit_ladder_dir_accepts_completed_with_fallback(tmp_path: Path) -> None:
    fit_dir = tmp_path / "fit-a"
    attempt_1 = fit_dir / "attempt-01-ctx-65536"
    attempt_2 = fit_dir / "attempt-02-ctx-32768"
    attempt_1.mkdir(parents=True)
    _write_valid_child_result(attempt_2, run_id="attempt-02-ctx-32768", ctx_size=32768)

    write_json(
        fit_dir / "fit-ladder-summary.json",
        {
            "schema_version": "llmgauge.fit_ladder.v0",
            "fit_ladder_id": "fit-a",
            "requested_settings": {
                "suite_id": "core-v1",
                "include": "honesty",
                "only": None,
                "model_id": "test-model",
                "model_profile": "test-profile",
                "ctx_size": 65536,
                "batch_size": 256,
                "ubatch_size": 64,
                "gpu_layers": 999,
            },
            "retry_policy": {
                "fallback_order": ["context"],
                "fallback_contexts": [8192, 32768],
                "stop_on_first_completed": True,
                "gpu_layer_fallback": "explicit-only",
            },
            "selected_working_settings": {
                "ctx_size": 32768,
                "batch_size": 256,
                "ubatch_size": 64,
                "gpu_layers": 999,
                "attempt_id": "attempt-02",
            },
            "final_status": "completed_with_fallback",
            "summary": {
                "attempted": 2,
                "completed": 1,
                "failed": 1,
                "oom_detected": True,
                "fallback_changed_context": True,
            },
            "attempts": [
                {
                    "schema_version": "llmgauge.fit_attempt.v0",
                    "attempt_id": "attempt-01",
                    "ctx_size": 65536,
                    "batch_size": 256,
                    "ubatch_size": 64,
                    "gpu_layers": 999,
                    "status": "failed",
                    "failure_class": "oom",
                    "retryable": True,
                    "failure_reason": "out-of-memory marker detected",
                    "exit_status": 1,
                    "stderr_excerpt": "CUDA error: out of memory",
                    "result_dir": str(attempt_1),
                    "vram": None,
                },
                {
                    "schema_version": "llmgauge.fit_attempt.v0",
                    "attempt_id": "attempt-02",
                    "ctx_size": 32768,
                    "batch_size": 256,
                    "ubatch_size": 64,
                    "gpu_layers": 999,
                    "status": "completed",
                    "failure_class": None,
                    "retryable": False,
                    "failure_reason": "completed",
                    "exit_status": 0,
                    "stderr_excerpt": "",
                    "result_dir": str(attempt_2),
                    "vram": None,
                },
            ],
        },
    )

    assert validate_fit_ladder_dir(fit_dir) == []


def test_validate_fit_ladder_dir_rejects_missing_summary(tmp_path: Path) -> None:
    fit_dir = tmp_path / "fit-a"
    fit_dir.mkdir()

    errors = validate_fit_ladder_dir(fit_dir)

    assert "missing fit-ladder-summary.json" in errors


def test_validate_fit_ladder_dir_rejects_bad_counts(tmp_path: Path) -> None:
    fit_dir = tmp_path / "fit-a"
    fit_dir.mkdir()

    write_json(
        fit_dir / "fit-ladder-summary.json",
        {
            "schema_version": "llmgauge.fit_ladder.v0",
            "fit_ladder_id": "fit-a",
            "requested_settings": {"ctx_size": 65536},
            "retry_policy": {
                "fallback_order": ["context"],
                "fallback_contexts": [32768],
            },
            "selected_working_settings": None,
            "final_status": "failed",
            "summary": {
                "attempted": 2,
                "completed": 0,
                "failed": 0,
                "oom_detected": False,
                "fallback_changed_context": False,
            },
            "attempts": [],
        },
    )

    errors = validate_fit_ladder_dir(fit_dir)

    assert any("summary.attempted" in error for error in errors)


def test_validate_fit_ladder_dir_rejects_failed_attempt_without_stderr(
    tmp_path: Path,
) -> None:
    fit_dir = tmp_path / "fit-a"
    fit_dir.mkdir()

    write_json(
        fit_dir / "fit-ladder-summary.json",
        {
            "schema_version": "llmgauge.fit_ladder.v0",
            "fit_ladder_id": "fit-a",
            "requested_settings": {"ctx_size": 65536},
            "retry_policy": {
                "fallback_order": ["context"],
                "fallback_contexts": [32768],
            },
            "selected_working_settings": None,
            "final_status": "failed",
            "summary": {
                "attempted": 1,
                "completed": 0,
                "failed": 1,
                "oom_detected": False,
                "fallback_changed_context": False,
            },
            "attempts": [
                {
                    "schema_version": "llmgauge.fit_attempt.v0",
                    "attempt_id": "attempt-01",
                    "ctx_size": 65536,
                    "batch_size": 256,
                    "ubatch_size": 64,
                    "gpu_layers": 999,
                    "status": "failed",
                    "failure_class": "runtime_error",
                    "retryable": False,
                    "failure_reason": "runtime error",
                    "exit_status": 2,
                    "stderr_excerpt": "",
                    "result_dir": None,
                    "vram": None,
                }
            ],
        },
    )

    errors = validate_fit_ladder_dir(fit_dir)

    assert any("failed attempt must preserve stderr_excerpt" in error for error in errors)
