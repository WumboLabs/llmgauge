import tomllib
from pathlib import Path

from typer.testing import CliRunner

from llmgauge import __version__
from llmgauge.cli import app

runner = CliRunner()


def test_version_command_prints_package_version() -> None:
    result = runner.invoke(app, ["version"])

    assert result.exit_code == 0
    assert f"llmgauge {__version__}" in result.output


def test_global_version_option_prints_package_version() -> None:
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert f"llmgauge {__version__}" in result.output


def test_pyproject_version_matches_runtime_version() -> None:
    pyproject = Path(__file__).parents[1] / "pyproject.toml"
    metadata = tomllib.loads(pyproject.read_text(encoding="utf-8"))

    assert metadata["project"]["version"] == __version__


def test_release_version_is_currently_pinned_to_0_75_0() -> None:
    assert __version__ == "0.75.0"
