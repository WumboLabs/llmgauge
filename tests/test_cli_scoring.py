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
