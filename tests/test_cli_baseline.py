from pathlib import Path

import yaml
from typer.testing import CliRunner

from llmgauge.cli import app


runner = CliRunner()


def test_baseline_check_command_passes(tmp_path: Path) -> None:
    suite_dir = tmp_path / "suite"
    baselines_dir = suite_dir / "baselines"
    baselines_dir.mkdir(parents=True)

    (suite_dir / "suite.yaml").write_text(
        yaml.safe_dump(
            {
                "schema_version": "llmgauge.suite.v0",
                "suite_id": "test-suite",
                "suite_version": "0.1.0",
                "title": "Test Suite",
                "prompts": [
                    {
                        "id": "honesty-unknown-tool",
                        "file": "prompts/test.md",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    prompt_file = suite_dir / "prompts" / "test.md"
    prompt_file.parent.mkdir()
    prompt_file.write_text("Prompt", encoding="utf-8")

    (baselines_dir / "honesty-unknown-tool.yaml").write_text(
        yaml.safe_dump(
            {
                "schema_version": "llmgauge.baseline.v0",
                "prompt_id": "honesty-unknown-tool",
                "mode": "checklist",
                "must_include": ["unknown tool"],
                "must_not_include": [],
                "hard_fail_if": [],
                "suggested_good_labels": ["fake_tool_resistance"],
                "suggested_failure_labels": [],
            }
        ),
        encoding="utf-8",
    )

    result_dir = tmp_path / "result"
    output_file = result_dir / "raw" / "honesty-unknown-tool.output.txt"
    output_file.parent.mkdir(parents=True)
    output_file.write_text("This is an unknown tool.", encoding="utf-8")

    (result_dir / "llmgauge-result.json").write_text(
        """{
  "run": {"run_id": "test-run"},
  "suite": {"suite_id": "test-suite"},
  "results": [
    {
      "prompt_id": "honesty-unknown-tool",
      "output_path": "raw/honesty-unknown-tool.output.txt"
    }
  ]
}
""",
        encoding="utf-8",
    )

    report_path = tmp_path / "baseline-check.json"

    result = runner.invoke(
        app,
        [
            "baseline-check",
            str(result_dir),
            "--suite",
            str(suite_dir),
            "--out",
            str(report_path),
        ],
    )

    assert result.exit_code == 0
    assert "LLMGauge Baseline Check" in result.output
    assert "honesty-unknown-tool" in result.output
    assert "pass" in result.output
    assert "Wrote baseline-check report" in result.output
    assert report_path.exists()


def test_baseline_check_command_can_fail_on_mixed(tmp_path: Path) -> None:
    suite_dir = tmp_path / "suite"
    baselines_dir = suite_dir / "baselines"
    baselines_dir.mkdir(parents=True)

    (suite_dir / "suite.yaml").write_text(
        yaml.safe_dump(
            {
                "schema_version": "llmgauge.suite.v0",
                "suite_id": "test-suite",
                "suite_version": "0.1.0",
                "title": "Test Suite",
                "prompts": [
                    {
                        "id": "honesty-unknown-tool",
                        "file": "prompts/test.md",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    prompt_file = suite_dir / "prompts" / "test.md"
    prompt_file.parent.mkdir()
    prompt_file.write_text("Prompt", encoding="utf-8")

    (baselines_dir / "honesty-unknown-tool.yaml").write_text(
        yaml.safe_dump(
            {
                "schema_version": "llmgauge.baseline.v0",
                "prompt_id": "honesty-unknown-tool",
                "mode": "checklist",
                "must_include": ["unknown tool", "verify first"],
                "must_not_include": [],
                "hard_fail_if": [],
                "suggested_good_labels": [],
                "suggested_failure_labels": ["missing_verification"],
            }
        ),
        encoding="utf-8",
    )

    result_dir = tmp_path / "result"
    output_file = result_dir / "raw" / "honesty-unknown-tool.output.txt"
    output_file.parent.mkdir(parents=True)
    output_file.write_text("This is an unknown tool.", encoding="utf-8")

    (result_dir / "llmgauge-result.json").write_text(
        """{
  "run": {"run_id": "test-run"},
  "suite": {"suite_id": "test-suite"},
  "results": [
    {
      "prompt_id": "honesty-unknown-tool",
      "output_path": "raw/honesty-unknown-tool.output.txt"
    }
  ]
}
""",
        encoding="utf-8",
    )

    default_result = runner.invoke(
        app,
        [
            "baseline-check",
            str(result_dir),
            "--suite",
            str(suite_dir),
        ],
    )
    assert default_result.exit_code == 0
    assert "mixed" in default_result.output

    strict_result = runner.invoke(
        app,
        [
            "baseline-check",
            str(result_dir),
            "--suite",
            str(suite_dir),
            "--fail-on-mixed",
        ],
    )
    assert strict_result.exit_code == 1
    assert "mixed" in strict_result.output
