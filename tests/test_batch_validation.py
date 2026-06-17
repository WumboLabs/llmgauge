from pathlib import Path

from llmgauge.core.artifacts import write_json
from llmgauge.core.batch_validation import validate_batch_dir


def _write_valid_child_result(path: Path, *, run_id: str, model_profile: str) -> None:
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
                "timestamp_utc": "2026-06-16T06:00:00+00:00",
                "status": "completed",
                "result_dir": str(path),
            },
            "model": {
                "model_id": model_profile,
                "model_profile": model_profile,
                "model_path": "redacted",
                "model_path_policy": "redacted",
            },
            "runtime": {
                "backend": "llama.cpp",
                "ctx_size": 8192,
                "max_tokens": 100,
                "temperature": 0.2,
                "top_p": 0.95,
                "batch_size": 256,
                "ubatch_size": 64,
                "gpu_layers": 999,
                "command": [],
            },
            "suite": {
                "suite_id": "agent-backend-v1",
                "suite_version": "0.1.0",
                "suite_path": "suites/agent-backend-v1",
                "prompt_count": 1,
                "include": "all",
                "only": None,
            },
            "results": [
                {
                    "prompt_id": "prompt-a",
                    "title": "Prompt A",
                    "category": "test",
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


def _write_batch_summary(
    batch_dir: Path,
    *,
    child_runs: list[dict],
    models: list[str],
    completed: int,
    failed: int,
) -> None:
    write_json(
        batch_dir / "batch-summary.json",
        {
            "schema_version": "llmgauge.batch_summary.v0",
            "batch_id": "batch-a",
            "manifest_path": "tmp/batch-a.yaml",
            "suite_id": "agent-backend-v1",
            "suite_path": "suites/agent-backend-v1",
            "include": "all",
            "only": None,
            "max_tokens": 300,
            "models": models,
            "execution": {
                "mode": "sequential",
                "model_reference_policy": "manifest model entries are model profile names only",
                "parallelism": "disabled",
            },
            "summary": {
                "total": len(child_runs),
                "completed": completed,
                "failed": failed,
            },
            "child_runs": child_runs,
        },
    )


def test_validate_batch_dir_accepts_valid_completed_batch(tmp_path: Path) -> None:
    batch_dir = tmp_path / "batch-a"
    batch_dir.mkdir()

    child = batch_dir / "model-01-test-model"
    _write_valid_child_result(
        child, run_id="model-01-test-model", model_profile="test-model"
    )

    _write_batch_summary(
        batch_dir,
        models=["test-model"],
        completed=1,
        failed=0,
        child_runs=[
            {
                "model_profile": "test-model",
                "model_id": "test-model",
                "status": "completed",
                "result_dir": str(child),
                "completed": 1,
                "failed": 0,
                "error": None,
            }
        ],
    )

    assert validate_batch_dir(batch_dir) == []


def test_validate_batch_dir_accepts_failed_child_with_error(tmp_path: Path) -> None:
    batch_dir = tmp_path / "batch-a"
    batch_dir.mkdir()

    _write_batch_summary(
        batch_dir,
        models=["missing-model"],
        completed=0,
        failed=1,
        child_runs=[
            {
                "model_profile": "missing-model",
                "model_id": None,
                "status": "failed",
                "result_dir": str(batch_dir / "model-01-missing-model"),
                "completed": None,
                "failed": None,
                "error": "Model path does not exist",
            }
        ],
    )

    assert validate_batch_dir(batch_dir) == []


def test_validate_batch_dir_rejects_missing_summary(tmp_path: Path) -> None:
    batch_dir = tmp_path / "batch-a"
    batch_dir.mkdir()

    errors = validate_batch_dir(batch_dir)

    assert "missing batch-summary.json" in errors


def test_validate_batch_dir_rejects_bad_counts(tmp_path: Path) -> None:
    batch_dir = tmp_path / "batch-a"
    batch_dir.mkdir()

    _write_batch_summary(
        batch_dir,
        models=["test-model"],
        completed=2,
        failed=0,
        child_runs=[
            {
                "model_profile": "test-model",
                "model_id": "test-model",
                "status": "completed",
                "result_dir": str(batch_dir / "model-01-test-model"),
                "completed": 1,
                "failed": 0,
                "error": None,
            }
        ],
    )

    errors = validate_batch_dir(batch_dir)

    assert any("summary.completed" in error for error in errors)


def test_validate_batch_dir_rejects_failed_child_without_error(tmp_path: Path) -> None:
    batch_dir = tmp_path / "batch-a"
    batch_dir.mkdir()

    _write_batch_summary(
        batch_dir,
        models=["missing-model"],
        completed=0,
        failed=1,
        child_runs=[
            {
                "model_profile": "missing-model",
                "model_id": None,
                "status": "failed",
                "result_dir": str(batch_dir / "model-01-missing-model"),
                "completed": None,
                "failed": None,
                "error": None,
            }
        ],
    )

    errors = validate_batch_dir(batch_dir)

    assert any("failed child run must preserve error text" in error for error in errors)


def test_validate_batch_dir_rejects_model_order_mismatch(tmp_path: Path) -> None:
    batch_dir = tmp_path / "batch-a"
    batch_dir.mkdir()

    _write_batch_summary(
        batch_dir,
        models=["model-a", "model-b"],
        completed=0,
        failed=2,
        child_runs=[
            {
                "model_profile": "model-b",
                "model_id": None,
                "status": "failed",
                "result_dir": str(batch_dir / "model-01-model-b"),
                "completed": None,
                "failed": None,
                "error": "example failure",
            },
            {
                "model_profile": "model-a",
                "model_id": None,
                "status": "failed",
                "result_dir": str(batch_dir / "model-02-model-a"),
                "completed": None,
                "failed": None,
                "error": "example failure",
            },
        ],
    )

    errors = validate_batch_dir(batch_dir)

    assert any(
        "models do not match child_runs model_profile order" in error
        for error in errors
    )


def test_validate_batch_dir_rejects_invalid_completed_child_result(
    tmp_path: Path,
) -> None:
    batch_dir = tmp_path / "batch-a"
    batch_dir.mkdir()

    child = batch_dir / "model-01-test-model"
    child.mkdir()

    _write_batch_summary(
        batch_dir,
        models=["test-model"],
        completed=1,
        failed=0,
        child_runs=[
            {
                "model_profile": "test-model",
                "model_id": "test-model",
                "status": "completed",
                "result_dir": str(child),
                "completed": 1,
                "failed": 0,
                "error": None,
            }
        ],
    )

    errors = validate_batch_dir(batch_dir)

    assert any("Missing result file" in error for error in errors)
