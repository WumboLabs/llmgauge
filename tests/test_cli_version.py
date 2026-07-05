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
