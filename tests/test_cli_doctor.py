from pathlib import Path

from typer.testing import CliRunner

from llmgauge.cli import app

runner = CliRunner()


def test_doctor_without_config_passes() -> None:
    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 0
    assert "LLMGauge Doctor" in result.output
    assert "Built-in suites" in result.output
    assert "Config" in result.output


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
