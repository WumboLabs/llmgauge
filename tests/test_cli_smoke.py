import re
from pathlib import Path

from typer.testing import CliRunner

from llmgauge.cli import app

runner = CliRunner()


def _strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def _write_templates(root: Path) -> None:
    examples_dir = root / "examples" / "configs"
    examples_dir.mkdir(parents=True)
    (examples_dir / "llmgauge.example.yaml").write_text(
        "schema_version: llmgauge.config.v0\n",
        encoding="utf-8",
    )
    (examples_dir / "model-profiles.example.yaml").write_text(
        "schema_version: llmgauge.model_profiles.v0\nmodels: {}\n",
        encoding="utf-8",
    )


def test_smoke_without_config_passes_with_warnings(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "empty-xdg"))

    result = runner.invoke(app, ["smoke"])
    plain_output = _strip_ansi(result.output)

    assert result.exit_code == 0
    assert "LLMGauge Smoke Check" in plain_output
    assert "Config" in plain_output
    assert "skip" in plain_output
    assert "Skipped" in plain_output
    assert "llmgauge init" in plain_output
    assert "Smoke check passed with warnings" in plain_output
    assert "Next steps:" in plain_output


def test_smoke_with_user_config_and_profile_passes(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg-config"))
    _write_templates(tmp_path)

    llama_cli = tmp_path / "llama-cli"
    llama_cli.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    llama_cli.chmod(0o755)

    model_path = tmp_path / "model.gguf"
    model_path.write_text("fake model placeholder\n", encoding="utf-8")

    user_config_dir = tmp_path / "xdg-config" / "llmgauge"
    user_config_dir.mkdir(parents=True)

    (user_config_dir / "config.yaml").write_text(
        f"""schema_version: llmgauge.config.v0
runtime:
  llama_cli: {llama_cli}
""",
        encoding="utf-8",
    )

    (user_config_dir / "model-profiles.yaml").write_text(
        f"""schema_version: llmgauge.model_profiles.v0
models:
  example_model:
    label: Example Model
    path: {model_path}
""",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["smoke", "--model-profile", "example_model"])

    assert result.exit_code == 0
    assert "LLMGauge Smoke Check" in result.output
    assert "Selected model profile" in result.output
    assert "Model file" in result.output
    assert "Smoke check passed" in result.output
    assert "passed with warnings" not in result.output


def test_smoke_fails_for_missing_selected_model_file(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg-config"))
    _write_templates(tmp_path)

    llama_cli = tmp_path / "llama-cli"
    llama_cli.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    llama_cli.chmod(0o755)

    user_config_dir = tmp_path / "xdg-config" / "llmgauge"
    user_config_dir.mkdir(parents=True)

    (user_config_dir / "config.yaml").write_text(
        f"""schema_version: llmgauge.config.v0
runtime:
  llama_cli: {llama_cli}
""",
        encoding="utf-8",
    )

    (user_config_dir / "model-profiles.yaml").write_text(
        f"""schema_version: llmgauge.model_profiles.v0
models:
  missing_model:
    label: Missing Model
    path: {tmp_path / "missing.gguf"}
""",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["smoke", "--model-profile", "missing_model"])

    assert result.exit_code == 1
    assert "Model file" in result.output
    assert "Path does not exist" in result.output
    assert "Smoke check failed" in result.output


def test_smoke_with_placeholder_paths_passes_with_warnings(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg-config"))
    _write_templates(tmp_path)

    user_config_dir = tmp_path / "xdg-config" / "llmgauge"
    user_config_dir.mkdir(parents=True)

    (user_config_dir / "config.yaml").write_text(
        """schema_version: llmgauge.config.v0
runtime:
  llama_cli: /path/to/llama-cli
""",
        encoding="utf-8",
    )

    (user_config_dir / "model-profiles.yaml").write_text(
        """schema_version: llmgauge.model_profiles.v0
models:
  placeholder_model:
    label: Placeholder Model
    path: /path/to/model.gguf
""",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["smoke", "--model-profile", "placeholder_model"])
    plain_output = _strip_ansi(result.output)

    assert result.exit_code == 0
    assert "llama-cli" in plain_output
    assert "Model file" in plain_output
    assert "Placeholder path" in plain_output
    assert "Smoke check passed with warnings" in plain_output


def test_smoke_with_model_profile_but_no_profiles_fails_clearly(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "empty-xdg"))

    result = runner.invoke(app, ["smoke", "--model-profile", "example_model"])
    plain_output = _strip_ansi(result.output)

    assert result.exit_code == 1
    assert "Selected model profile" in plain_output
    assert "Cannot check profile" in plain_output
    assert "Next steps:" in plain_output