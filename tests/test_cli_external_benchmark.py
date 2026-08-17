from __future__ import annotations

import json
import re
from pathlib import Path

from typer.testing import CliRunner

from external_benchmark_fixtures import (
    write_malformed_metrics_file,
    write_official_bundle1_file,
    write_single_task_file,
)
from llmgauge.cli import app

runner = CliRunner()
_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def _normalize_cli_output(value: str) -> str:
    return " ".join(_ANSI_ESCAPE_RE.sub("", value).split())


def test_benchmark_help() -> None:
    result = runner.invoke(app, ["benchmark", "--help"])

    assert result.exit_code == 0
    output = _normalize_cli_output(result.output)
    assert "import" in output
    assert "validate" in output
    assert "report" in output
    assert "localmaxxing" not in output.lower() or "speed" not in output.lower()


def test_benchmark_import_help() -> None:
    result = runner.invoke(app, ["benchmark", "import", "--help"])

    assert result.exit_code == 0
    output = _normalize_cli_output(result.output)
    assert "--dry-run" in output


def test_benchmark_import_then_validate(tmp_path: Path) -> None:
    source = write_single_task_file(tmp_path / "source")
    destination = tmp_path / "result"

    imported = runner.invoke(
        app, ["benchmark", "import", str(source), str(destination)]
    )
    validated = runner.invoke(app, ["benchmark", "validate", str(destination)])
    native_validate = runner.invoke(app, ["validate-result", str(destination)])

    assert imported.exit_code == 0
    assert "Imported external benchmark evidence" in imported.output
    assert "official acceptance" in imported.output
    assert validated.exit_code == 0
    assert "Structural validation passed" in validated.output
    assert native_validate.exit_code == 0
    assert (destination / "llmgauge-result.json").is_file()
    result = json.loads(
        (destination / "llmgauge-result.json").read_text(encoding="utf-8")
    )
    assert result["external_benchmark_evidence"]["schema_version"] == (
        "llmgauge.external_benchmark_evidence.v0"
    )


def test_benchmark_import_malformed_source(tmp_path: Path) -> None:
    source = write_malformed_metrics_file(tmp_path / "source")
    destination = tmp_path / "result"

    result = runner.invoke(app, ["benchmark", "import", str(source), str(destination)])

    assert result.exit_code == 1
    assert "malformed_source" in result.output
    assert not destination.exists()


def test_benchmark_import_dry_run(tmp_path: Path) -> None:
    source = write_single_task_file(tmp_path / "source")
    destination = tmp_path / "result"

    result = runner.invoke(
        app, ["benchmark", "import", str(source), str(destination), "--dry-run"]
    )

    assert result.exit_code == 0
    assert "dry run wrote no artifacts" in result.output
    assert not destination.exists()


def test_benchmark_validate_rejects_native_result(tmp_path: Path) -> None:
    result_dir = tmp_path / "native"
    result_dir.mkdir()
    (result_dir / "llmgauge-result.json").write_text(
        json.dumps(
            {
                "schema_version": "llmgauge.result.v0",
                "results": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["benchmark", "validate", str(result_dir)])

    assert result.exit_code == 1
    assert "not imported external benchmark" in _normalize_cli_output(result.output)


def test_benchmark_import_validate_report(tmp_path: Path) -> None:
    source = write_official_bundle1_file(tmp_path / "source")
    destination = tmp_path / "result"

    imported = runner.invoke(
        app, ["benchmark", "import", str(source), str(destination)]
    )
    validated = runner.invoke(app, ["benchmark", "validate", str(destination)])
    reported = runner.invoke(app, ["benchmark", "report", str(destination)])

    assert imported.exit_code == 0
    assert validated.exit_code == 0
    assert reported.exit_code == 0
    assert "Wrote external benchmark report" in reported.output
    assert "qualified" in reported.output
    report = (destination / "external-benchmark" / "report.md").read_text(
        encoding="utf-8"
    )
    assert "Bundle 1 qualification" in report
    assert "did not execute candidate code" in report


def test_benchmark_report_help() -> None:
    result = runner.invoke(app, ["benchmark", "report", "--help"])

    assert result.exit_code == 0
    assert "read-only" in _normalize_cli_output(result.output).lower()


def test_benchmark_report_rejects_native_result(tmp_path: Path) -> None:
    result_dir = tmp_path / "native"
    result_dir.mkdir()
    (result_dir / "llmgauge-result.json").write_text(
        json.dumps({"schema_version": "llmgauge.result.v0", "results": []}) + "\n",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["benchmark", "report", str(result_dir)])

    assert result.exit_code == 1
    assert "not imported external benchmark" in _normalize_cli_output(result.output)
