import json
from pathlib import Path

import yaml
from typer.testing import CliRunner

from llmgauge.cli import app
from llmgauge.core.scoring import build_score_template


runner = CliRunner()


def _write_score_files(tmp_path: Path) -> tuple[Path, Path]:
    result_dir = tmp_path / "result"
    result_dir.mkdir()
    result_data = {
        "run": {"run_id": "test-run"},
        "summary": {},
        "results": [{"prompt_id": "test-prompt"}],
    }
    result_path = result_dir / "llmgauge-result.json"
    result_path.write_text(
        json.dumps(result_data, indent=2) + "\n",
        encoding="utf-8",
    )
    (result_dir / "report.md").write_text("Original report\n", encoding="utf-8")

    scores_path = result_dir / "scores.yaml"
    scores_path.write_text(
        yaml.safe_dump(build_score_template(result_data), sort_keys=False),
        encoding="utf-8",
    )
    return result_dir, scores_path


def test_score_check_valid_scores_succeeds_without_mutating_result(
    tmp_path: Path,
) -> None:
    result_dir, scores_path = _write_score_files(tmp_path)
    result_path = result_dir / "llmgauge-result.json"
    report_path = result_dir / "report.md"
    original_result = result_path.read_bytes()
    original_report = report_path.read_bytes()
    original_scores = scores_path.read_bytes()

    result = runner.invoke(
        app,
        ["score", str(result_dir), "--scores", str(scores_path), "--check"],
    )

    assert result.exit_code == 0
    assert "Score validation passed" in result.output
    assert result_path.read_bytes() == original_result
    assert report_path.read_bytes() == original_report
    assert scores_path.read_bytes() == original_scores


def test_score_check_invalid_verdict_fails(tmp_path: Path) -> None:
    result_dir, scores_path = _write_score_files(tmp_path)
    scores_data = yaml.safe_load(scores_path.read_text(encoding="utf-8"))
    scores_data["scores"]["test-prompt"]["verdict"] = "invalid"
    scores_path.write_text(
        yaml.safe_dump(scores_data, sort_keys=False),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        ["score", str(result_dir), "--scores", str(scores_path), "--check"],
    )

    assert result.exit_code == 1
    assert "Score validation failed" in result.output
    assert "verdict must be one of" in result.output


def test_score_check_without_scores_fails_clearly(tmp_path: Path) -> None:
    result_dir, _ = _write_score_files(tmp_path)

    result = runner.invoke(app, ["score", str(result_dir), "--check"])

    assert result.exit_code != 0
    assert "--check requires --scores PATH" in result.output


def test_score_check_with_init_fails_clearly(tmp_path: Path) -> None:
    result_dir, _ = _write_score_files(tmp_path)

    result = runner.invoke(app, ["score", str(result_dir), "--check", "--init"])

    assert result.exit_code != 0
    assert "--check cannot be used with --init" in result.output


def test_score_init_uses_suite_specific_template(tmp_path: Path) -> None:
    result_dir = tmp_path / "result"
    result_dir.mkdir()
    result_data = {
        "run": {"run_id": "suite-run"},
        "suite": {
            "suite_id": "wumbolabs-practical-v1",
            "suite_path": "suites/wumbolabs-practical-v1",
            "suite_version": "0.1.0",
        },
        "summary": {},
        "results": [{"prompt_id": "output-discipline/json-only-risk-register"}],
    }
    (result_dir / "llmgauge-result.json").write_text(
        json.dumps(result_data, indent=2) + "\n",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["score", str(result_dir), "--init"])

    assert result.exit_code == 0
    scores_data = yaml.safe_load((result_dir / "scores.yaml").read_text())
    assert scores_data["rubric_id"] == "wumbolabs-practical-v1"
    assert scores_data["dimensions"] == [
        "task_completion",
        "technical_correctness",
        "safety_conservatism",
        "honesty_uncertainty",
        "instruction_following",
        "practical_usefulness",
        "clarity",
        "token_efficiency",
    ]
    assert (
        scores_data["scores"]["output-discipline/json-only-risk-register"][
            "task_completion"
        ]
        is None
    )


def test_score_check_rejects_unknown_labels(tmp_path: Path) -> None:
    result_dir = tmp_path / "result"
    result_dir.mkdir()
    result_data = {
        "run": {"run_id": "suite-run"},
        "suite": {
            "suite_id": "wumbolabs-practical-v1",
            "suite_path": "suites/wumbolabs-practical-v1",
            "suite_version": "0.1.0",
        },
        "summary": {},
        "results": [{"prompt_id": "output-discipline/json-only-risk-register"}],
    }
    (result_dir / "llmgauge-result.json").write_text(
        json.dumps(result_data, indent=2) + "\n",
        encoding="utf-8",
    )

    scores_data = build_score_template(result_data)
    scores_data["scores"]["output-discipline/json-only-risk-register"][
        "good_labels"
    ] = ["valid_json"]
    scores_path = result_dir / "scores.yaml"
    scores_path.write_text(
        yaml.safe_dump(scores_data, sort_keys=False),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        ["score", str(result_dir), "--scores", str(scores_path), "--check"],
    )

    assert result.exit_code == 1
    assert "contains unknown label" in result.output
    assert "valid_json" in result.output
