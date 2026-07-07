import re
from pathlib import Path

from typer.testing import CliRunner

from llmgauge.cli import app

runner = CliRunner()


def _strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def test_doctor_without_config_passes(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["doctor"])
    plain_output = _strip_ansi(result.output)

    assert result.exit_code == 0
    assert "LLMGauge Doctor" in plain_output
    assert "Built-in suites" in plain_output
    assert "Config" in plain_output
    assert "Skipped" in plain_output
    assert "llmgauge init" in plain_output
    assert "Next steps:" in plain_output


def test_doctor_without_profiles_notes_skipped_checks(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg-config"))

    user_config_dir = tmp_path / "xdg-config" / "llmgauge"
    user_config_dir.mkdir(parents=True)
    (user_config_dir / "config.yaml").write_text(
        "schema_version: llmgauge.config.v0\n",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["doctor"])
    plain_output = _strip_ansi(result.output)

    assert result.exit_code == 0
    assert "Model profiles" in plain_output
    assert "skip" in plain_output
    assert "Skipped" in plain_output
    assert "llmgauge model add" in plain_output


def test_doctor_with_model_profile_but_no_profiles_fails_clearly(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["doctor", "--model-profile", "example_model"])
    plain_output = _strip_ansi(result.output)

    assert result.exit_code == 1
    assert "Selected model profile" in plain_output
    assert "Cannot check profile" in plain_output
    assert "not loaded" in plain_output


def test_doctor_with_missing_config_fails(tmp_path: Path) -> None:
    result = runner.invoke(app, ["doctor", "--config", str(tmp_path / "missing.yaml")])

    assert result.exit_code == 1
    assert "Config" in result.output
    assert "does not exist" in result.output


def test_doctor_checks_config_profile_and_model_file(tmp_path: Path) -> None:
    llama_cli = tmp_path / "llama-cli"
    llama_cli.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    llama_cli.chmod(0o755)

    model_path = tmp_path / "model.gguf"
    model_path.write_text("fake model placeholder\n", encoding="utf-8")

    config_path = tmp_path / "llmgauge.yaml"
    config_path.write_text(
        f"""schema_version: llmgauge.config.v0
runtime:
  llama_cli: {llama_cli}
""",
        encoding="utf-8",
    )

    profiles_path = tmp_path / "model-profiles.yaml"
    profiles_path.write_text(
        f"""schema_version: llmgauge.model_profiles.v0
models:
  example_model:
    label: Example Model
    path: {model_path}
""",
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "doctor",
            "--config",
            str(config_path),
            "--model-profiles",
            str(profiles_path),
            "--model-profile",
            "example_model",
        ],
    )

    assert result.exit_code == 0
    assert "llama-cli" in result.output
    assert "Model profiles" in result.output
    assert "Selected model profile" in result.output
    assert "Model file" in result.output