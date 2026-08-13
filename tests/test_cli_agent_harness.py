from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from agent_harness_fixtures import (
    completed_records,
    write_session,
    write_synthetic_omp_session,
)
from llmgauge.cli import app


runner = CliRunner()


def test_import_agent_harness_help() -> None:
    result = runner.invoke(app, ["import-agent-harness", "--help"])

    assert result.exit_code == 0
    assert "Local OMP v3 session JSONL file" in result.output
    assert "--blob-dir" in result.output
    assert "--dry-run" in result.output


def test_import_agent_harness_valid_source(tmp_path: Path) -> None:
    source = write_synthetic_omp_session(tmp_path / "source").source
    destination = tmp_path / "result"

    result = runner.invoke(app, ["import-agent-harness", str(source), str(destination)])

    assert result.exit_code == 0
    assert "Imported Agent Harness evidence" in result.output
    assert "does not prove task success" in result.output
    assert (destination / "llmgauge-result.json").is_file()


def test_import_agent_harness_unsupported_source(tmp_path: Path) -> None:
    source = write_session(tmp_path / "source", completed_records(), version=2)
    destination = tmp_path / "result"

    result = runner.invoke(app, ["import-agent-harness", str(source), str(destination)])

    assert result.exit_code == 1
    assert "unsupported_source" in result.output
    assert not destination.exists()


def test_import_agent_harness_malformed_source(tmp_path: Path) -> None:
    source = tmp_path / "source.jsonl"
    source.write_text("{not-json}\n", encoding="utf-8")
    destination = tmp_path / "result"

    result = runner.invoke(app, ["import-agent-harness", str(source), str(destination)])

    assert result.exit_code == 1
    assert "malformed_source" in result.output
    assert not destination.exists()


def test_import_agent_harness_identical_destination(tmp_path: Path) -> None:
    source = write_synthetic_omp_session(tmp_path / "source").source
    destination = tmp_path / "result"
    first = runner.invoke(app, ["import-agent-harness", str(source), str(destination)])

    result = runner.invoke(app, ["import-agent-harness", str(source), str(destination)])

    assert first.exit_code == 0
    assert result.exit_code == 0
    assert "Already imported" in result.output


def test_import_agent_harness_conflicting_destination(tmp_path: Path) -> None:
    source = write_synthetic_omp_session(tmp_path / "source").source
    destination = tmp_path / "result"
    destination.mkdir()
    sentinel = destination / "keep.txt"
    sentinel.write_text("unchanged", encoding="utf-8")

    result = runner.invoke(app, ["import-agent-harness", str(source), str(destination)])

    assert result.exit_code == 1
    assert "destination contains conflicting" in result.output
    assert sentinel.read_text(encoding="utf-8") == "unchanged"


def test_import_agent_harness_dry_run_writes_nothing(tmp_path: Path) -> None:
    source = write_synthetic_omp_session(tmp_path / "source").source
    destination = tmp_path / "result"

    result = runner.invoke(
        app,
        ["import-agent-harness", str(source), str(destination), "--dry-run"],
    )

    assert result.exit_code == 0
    assert "dry run wrote no artifacts" in result.output
    assert not destination.exists()
    assert not list(tmp_path.glob(".result.agent-harness-import-*"))


def test_import_agent_harness_malformed_source_id_is_bounded(
    tmp_path: Path,
) -> None:
    source = write_session(
        tmp_path / "source",
        completed_records(),
        header_updates={"id": "invalid source id"},
    )
    destination = tmp_path / "result"

    result = runner.invoke(app, ["import-agent-harness", str(source), str(destination)])

    assert result.exit_code == 1
    assert "malformed_source" in result.output
    assert "Traceback" not in result.output
    assert not destination.exists()
