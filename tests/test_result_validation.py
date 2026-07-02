from pathlib import Path

from llmgauge.core.artifacts import write_json, write_text
from llmgauge.core.result_validation import validate_result_data, validate_result_dir


def _valid_result() -> dict:
    return {
        "schema_version": "llmgauge.result.v0",
        "llmgauge_version": "0.1.0",
        "run": {
            "run_id": "test-run",
            "status": "completed",
        },
        "model": {
            "model_id": "test-model",
            "model_path": "redacted",
            "model_path_policy": "redacted",
        },
        "runtime": {
            "backend": "llama.cpp",
        },
        "suite": {
            "suite_id": "core-v1",
            "prompt_count": 1,
        },
        "summary": {
            "completed": 1,
            "failed": 0,
        },
        "results": [
            {
                "prompt_id": "honesty-unknown-tool",
                "category": "honesty",
                "status": "completed",
                "raw_prompt_path": "raw/honesty-unknown-tool.prompt.md",
                "raw_output_path": "raw/honesty-unknown-tool.output.txt",
                "stderr_log_path": "logs/honesty-unknown-tool.stderr.log",
                "exit_status": 0,
                "metrics": {
                    "prompt_eval_tps": 100.0,
                    "generation_tps": 50.0,
                },
                "score": None,
            }
        ],
    }


def _write_valid_result_dir(tmp_path: Path) -> Path:
    result_dir = tmp_path / "result"
    (result_dir / "raw").mkdir(parents=True)
    (result_dir / "logs").mkdir(parents=True)

    write_text(result_dir / "raw/honesty-unknown-tool.prompt.md", "prompt")
    write_text(result_dir / "raw/honesty-unknown-tool.output.txt", "output")
    write_text(result_dir / "logs/honesty-unknown-tool.stderr.log", "stderr")
    write_json(result_dir / "llmgauge-result.json", _valid_result())

    return result_dir


def test_validate_result_dir_success(tmp_path: Path) -> None:
    result_dir = _write_valid_result_dir(tmp_path)

    assert validate_result_dir(result_dir) == []


def test_validate_result_data_rejects_missing_top_level_key(tmp_path: Path) -> None:
    data = _valid_result()
    del data["runtime"]

    errors = validate_result_data(tmp_path, data)

    assert "Missing top-level key: runtime" in errors


def test_validate_result_data_rejects_bad_summary_counts(tmp_path: Path) -> None:
    data = _valid_result()
    data["summary"]["completed"] = 99

    errors = validate_result_data(tmp_path, data)

    assert "summary.completed is 99, expected 1" in errors


def test_validate_result_data_rejects_unredacted_model_path(tmp_path: Path) -> None:
    data = _valid_result()
    data["model"]["model_path"] = "/home/user/private/model.gguf"

    errors = validate_result_data(tmp_path, data)

    assert "model.model_path must be redacted" in errors


def test_validate_result_data_rejects_duplicate_prompt_ids(tmp_path: Path) -> None:
    data = _valid_result()
    data["results"].append(dict(data["results"][0]))
    data["summary"]["completed"] = 2

    errors = validate_result_data(tmp_path, data)

    assert "Duplicate prompt_id: honesty-unknown-tool" in errors


def test_validate_result_data_rejects_missing_artifact(tmp_path: Path) -> None:
    data = _valid_result()

    errors = validate_result_data(tmp_path, data)

    assert any("missing artifact" in error for error in errors)


def test_validate_result_data_accepts_score_shape(tmp_path: Path) -> None:
    data = _valid_result()
    data["results"][0]["score"] = {
        "dimensions": {
            "safety": 4,
        },
        "failure_labels": [],
        "good_labels": ["good_verification"],
        "reviewer_notes": "Solid.",
    }

    errors = validate_result_data(tmp_path, data)

    assert not any("score" in error for error in errors)


def test_validate_result_data_accepts_optional_cleaned_output_path(tmp_path: Path) -> None:
    result_dir = _write_valid_result_dir(tmp_path)
    data = _valid_result()
    data["results"][0]["cleaned_output_path"] = (
        "cleaned/honesty-unknown-tool.output.txt"
    )
    write_text(result_dir / "cleaned/honesty-unknown-tool.output.txt", "cleaned output")

    errors = validate_result_data(result_dir, data)

    assert errors == []


def test_validate_result_data_rejects_missing_cleaned_output_path(tmp_path: Path) -> None:
    result_dir = _write_valid_result_dir(tmp_path)
    data = _valid_result()
    data["results"][0]["cleaned_output_path"] = (
        "cleaned/honesty-unknown-tool.output.txt"
    )

    errors = validate_result_data(result_dir, data)

    assert any("cleaned_output_path missing artifact" in error for error in errors)


def _write_minimal_result(tmp_path: Path) -> Path:
    result_dir = tmp_path / "result"
    result_dir.mkdir()

    (result_dir / "raw").mkdir()
    (result_dir / "logs").mkdir()

    (result_dir / "raw" / "honesty-unknown-tool.prompt.md").write_text(
        "prompt\n", encoding="utf-8"
    )
    (result_dir / "raw" / "honesty-unknown-tool.output.txt").write_text(
        "output\n", encoding="utf-8"
    )
    (result_dir / "logs" / "honesty-unknown-tool.stderr.log").write_text(
        "", encoding="utf-8"
    )

    return result_dir


def _load_result(result_dir: Path) -> dict:
    return {
        "schema_version": "llmgauge.result.v0",
        "llmgauge_version": "test",
        "run": {
            "run_id": "test-run",
            "status": "completed",
            "timestamp_utc": "2026-06-20T00:00:00+00:00",
        },
        "model": {
            "model_id": "test-model",
            "model_path": "[redacted]",
        },
        "runtime": {},
        "suite": {},
        "summary": {
            "completed": 1,
            "failed": 0,
        },
        "results": [
            {
                "prompt_id": "honesty-unknown-tool",
                "category": "honesty",
                "status": "completed",
                "raw_prompt_path": "raw/honesty-unknown-tool.prompt.md",
                "raw_output_path": "raw/honesty-unknown-tool.output.txt",
                "stderr_log_path": "logs/honesty-unknown-tool.stderr.log",
                "exit_status": 0,
                "metrics": {},
                "score": None,
            }
        ],
    }

def test_validate_result_data_accepts_hardened_score_metadata(tmp_path: Path) -> None:
    result_dir = _write_minimal_result(tmp_path)
    data = _load_result(result_dir)
    data["results"][0]["score"] = {
        "schema_version": "llmgauge.scores.v0",
        "scale": "0-5",
        "rubric_id": "default-manual-v0",
        "rubric_version": "0.1.0",
        "dimensions": {"safety": 4},
        "failure_labels": [],
        "good_labels": [],
        "reviewer_notes": "Reviewed.",
        "score_rationale": "Safe but incomplete.",
        "verdict": "mixed",
        "scoring_mode": "manual",
        "scorer_id": "human-reviewer",
        "scorer_version": "",
        "confidence": "",
        "evidence": ["Reviewed against raw output."],
        "warnings": [],
        "reviewed": True,
        "override_status": "none",
    }

    errors = validate_result_data(result_dir, data)

    assert not any("score" in error for error in errors)


def test_validate_result_data_rejects_non_string_score_rationale(tmp_path: Path) -> None:
    result_dir = _write_minimal_result(tmp_path)
    data = _load_result(result_dir)
    data["results"][0]["score"] = {
        "dimensions": {},
        "failure_labels": [],
        "good_labels": [],
        "reviewer_notes": "",
        "score_rationale": 123,
        "verdict": "",
    }

    errors = validate_result_data(result_dir, data)

    assert any("score.score_rationale must be a string" in error for error in errors)

def test_validate_result_data_rejects_invalid_score_provenance(tmp_path: Path) -> None:
    result_dir = _write_minimal_result(tmp_path)
    data = _load_result(result_dir)
    data["results"][0]["score"] = {
        "dimensions": {},
        "failure_labels": [],
        "good_labels": [],
        "reviewer_notes": "",
        "score_rationale": "",
        "verdict": "",
        "scoring_mode": 123,
        "evidence": ["valid evidence", 42],
        "warnings": "not-a-list",
        "reviewed": "yes",
    }

    errors = validate_result_data(result_dir, data)

    assert any("score.scoring_mode must be a string" in error for error in errors)
    assert any("score.evidence must be a list of strings" in error for error in errors)
    assert any("score.warnings must be a list of strings" in error for error in errors)
    assert any("score.reviewed must be a boolean" in error for error in errors)
