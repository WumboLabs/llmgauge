from pathlib import Path

from typer.testing import CliRunner

from llmgauge.cli import app
from test_public_export import _write_run


runner = CliRunner()


def test_export_public_cli_success(tmp_path: Path) -> None:
    source_dir = _write_run(tmp_path)
    output_dir = tmp_path / "public"

    result = runner.invoke(app, ["export-public", str(source_dir), "--out", str(output_dir)])

    assert result.exit_code == 0, result.output
    assert "Wrote public export" in result.output
    assert (output_dir / "public-export-manifest.json").exists()


def test_export_public_cli_refuses_nonempty_output(tmp_path: Path) -> None:
    source_dir = _write_run(tmp_path)
    output_dir = tmp_path / "public"
    output_dir.mkdir()
    (output_dir / "existing.txt").write_text("existing", encoding="utf-8")

    result = runner.invoke(app, ["export-public", str(source_dir), "--out", str(output_dir)])

    assert result.exit_code == 1
    assert "non-empty" in result.output
