from pathlib import Path

from llmgauge.core.artifacts import write_json
from llmgauge.core.ladder_validation import validate_ladder_dir


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
                "timestamp_utc": "2026-06-16T06:00:00+00:00",
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


def test_validate_ladder_dir_accepts_valid_ladder(tmp_path: Path) -> None:
    ladder_dir = tmp_path / "ladder-a"
    ladder_dir.mkdir()

    child_8192 = ladder_dir / "ctx-8192"
    child_12288 = ladder_dir / "ctx-12288"

    _write_valid_child_result(child_8192, run_id="ctx-8192", ctx_size=8192)
    _write_valid_child_result(child_12288, run_id="ctx-12288", ctx_size=12288)

    write_json(
        ladder_dir / "ladder-summary.json",
        {
            "schema_version": "llmgauge.context_ladder.v0",
            "ladder_id": "ladder-a",
            "suite_id": "agent-backend-v1",
            "model_id": "test-model",
            "include": "all",
            "only": None,
            "contexts": [8192, 12288],
            "child_runs": [
                {
                    "ctx_size": 8192,
                    "status": "completed",
                    "result_dir": str(child_8192),
                    "completed": 1,
                    "failed": 0,
                    "error": None,
                },
                {
                    "ctx_size": 12288,
                    "status": "completed",
                    "result_dir": str(child_12288),
                    "completed": 1,
                    "failed": 0,
                    "error": None,
                },
            ],
            "summary": {
                "total": 2,
                "completed": 2,
                "failed": 0,
            },
        },
    )

    assert validate_ladder_dir(ladder_dir) == []


def test_validate_ladder_dir_rejects_missing_summary(tmp_path: Path) -> None:
    ladder_dir = tmp_path / "ladder-a"
    ladder_dir.mkdir()

    errors = validate_ladder_dir(ladder_dir)

    assert "missing ladder-summary.json" in errors


def test_validate_ladder_dir_rejects_bad_counts(tmp_path: Path) -> None:
    ladder_dir = tmp_path / "ladder-a"
    ladder_dir.mkdir()

    write_json(
        ladder_dir / "ladder-summary.json",
        {
            "schema_version": "llmgauge.context_ladder.v0",
            "contexts": [8192],
            "child_runs": [
                {
                    "ctx_size": 8192,
                    "status": "completed",
                    "result_dir": str(ladder_dir / "ctx-8192"),
                    "completed": 1,
                    "failed": 0,
                    "error": None,
                }
            ],
            "summary": {
                "total": 2,
                "completed": 2,
                "failed": 0,
            },
        },
    )

    errors = validate_ladder_dir(ladder_dir)

    assert any("summary.total" in error for error in errors)
    assert any("summary.completed" in error for error in errors)


def test_validate_ladder_dir_requires_failed_child_error(tmp_path: Path) -> None:
    ladder_dir = tmp_path / "ladder-a"
    ladder_dir.mkdir()

    write_json(
        ladder_dir / "ladder-summary.json",
        {
            "schema_version": "llmgauge.context_ladder.v0",
            "contexts": [8192],
            "child_runs": [
                {
                    "ctx_size": 8192,
                    "status": "failed",
                    "result_dir": str(ladder_dir / "ctx-8192"),
                    "completed": None,
                    "failed": None,
                    "error": None,
                }
            ],
            "summary": {
                "total": 1,
                "completed": 0,
                "failed": 1,
            },
        },
    )

    errors = validate_ladder_dir(ladder_dir)

    assert any("failed child run must preserve error text" in error for error in errors)
