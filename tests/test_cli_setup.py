import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

import llmgauge.commands.run_helpers as run_helpers
from llmgauge.cli import app
from llmgauge.core.config import load_llmgauge_config, load_model_profiles

runner = CliRunner()


def _strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def _user_config_dir(tmp_path: Path) -> Path:
    return tmp_path / "xdg-config" / "llmgauge"


def _make_executable(path: Path) -> Path:
    path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    path.chmod(0o755)
    return path


def _make_gguf(path: Path) -> Path:
    path.write_text("fake gguf placeholder\n", encoding="utf-8")
    return path


@pytest.fixture
def isolated_user_config(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg-config"))
    return tmp_path


def test_setup_help_exists() -> None:
    result = runner.invoke(app, ["setup", "--help"])
    plain_output = _strip_ansi(result.output)

    assert result.exit_code == 0
    assert "-scan" in plain_output
    assert "-non-interactive" in plain_output
    assert "-llama-cli" in plain_output


def test_setup_scan_is_read_only_and_exits_zero(
    isolated_user_config: Path,
) -> None:
    models_dir = isolated_user_config / "models"
    models_dir.mkdir()
    _make_gguf(models_dir / "scan_test.gguf")

    config_dir = _user_config_dir(isolated_user_config)
    config_dir.mkdir(parents=True)
    (config_dir / "config.yaml").write_text(
        "schema_version: llmgauge.config.v0\n",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["setup", "--scan"])
    plain_output = _strip_ansi(result.output)

    assert result.exit_code == 0
    assert "Read-only scan" in plain_output
    assert "No files were written" in plain_output
    assert "scan_test" in plain_output.replace("\n", "")
    assert (config_dir / "config.yaml").read_text(encoding="utf-8") == (
        "schema_version: llmgauge.config.v0\n"
    )


def test_setup_non_interactive_writes_config_and_profile(
    isolated_user_config: Path,
) -> None:
    llama_cli = _make_executable(isolated_user_config / "llama-cli")
    model_path = _make_gguf(isolated_user_config / "model.gguf")

    result = runner.invoke(
        app,
        [
            "setup",
            "--non-interactive",
            "--llama-cli",
            str(llama_cli),
            "--model-path",
            str(model_path),
            "--profile-name",
            "setup_smoke_model",
        ],
    )

    assert result.exit_code == 0, result.output

    config_path = _user_config_dir(isolated_user_config) / "config.yaml"
    profiles_path = _user_config_dir(isolated_user_config) / "model-profiles.yaml"

    assert config_path.exists()
    assert profiles_path.exists()

    config_data = load_llmgauge_config(config_path)
    profiles = load_model_profiles(profiles_path)

    assert str(llama_cli.resolve()) == config_data["runtime"]["llama_cli"]
    assert profiles["setup_smoke_model"]["path"] == str(model_path.resolve())
    assert "No model was launched" in result.output


def test_setup_non_interactive_missing_llama_cli_fails_clearly(
    isolated_user_config: Path,
) -> None:
    model_path = _make_gguf(isolated_user_config / "model.gguf")

    result = runner.invoke(
        app,
        [
            "setup",
            "--non-interactive",
            "--model-path",
            str(model_path),
            "--profile-name",
            "setup_model",
        ],
    )

    plain_output = _strip_ansi(result.output)

    assert result.exit_code != 0
    assert "llama-cli is required" in plain_output


def test_setup_non_interactive_missing_model_path_fails_clearly(
    isolated_user_config: Path,
) -> None:
    llama_cli = _make_executable(isolated_user_config / "llama-cli")
    models_dir = isolated_user_config / "empty-models"
    models_dir.mkdir()

    result = runner.invoke(
        app,
        [
            "setup",
            "--non-interactive",
            "--llama-cli",
            str(llama_cli),
            "--models-dir",
            str(models_dir),
        ],
    )

    assert result.exit_code != 0
    assert "No GGUF files found" in result.output


def test_setup_does_not_overwrite_existing_llama_cli_without_force(
    isolated_user_config: Path,
) -> None:
    existing_cli = _make_executable(isolated_user_config / "existing-llama-cli")
    replacement_cli = _make_executable(isolated_user_config / "replacement-llama-cli")

    config_dir = _user_config_dir(isolated_user_config)
    config_dir.mkdir(parents=True)
    (config_dir / "config.yaml").write_text(
        f"""schema_version: llmgauge.config.v0
runtime:
  llama_cli: {existing_cli}
""",
        encoding="utf-8",
    )
    (config_dir / "model-profiles.yaml").write_text(
        "schema_version: llmgauge.model_profiles.v0\nmodels: {}\n",
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "setup",
            "--non-interactive",
            "--llama-cli",
            str(replacement_cli),
        ],
    )

    plain_output = _strip_ansi(result.output)

    assert result.exit_code != 0
    assert "use --force" in plain_output
    config_data = load_llmgauge_config(config_dir / "config.yaml")
    assert config_data["runtime"]["llama_cli"] == str(existing_cli.resolve())


def test_setup_created_config_allows_doctor_and_smoke(
    isolated_user_config: Path,
) -> None:
    llama_cli = _make_executable(isolated_user_config / "llama-cli")
    model_path = _make_gguf(isolated_user_config / "model.gguf")

    setup_result = runner.invoke(
        app,
        [
            "setup",
            "--non-interactive",
            "--llama-cli",
            str(llama_cli),
            "--model-path",
            str(model_path),
            "--profile-name",
            "setup_smoke_model",
        ],
    )
    assert setup_result.exit_code == 0, setup_result.output

    doctor_result = runner.invoke(
        app,
        ["doctor", "--model-profile", "setup_smoke_model"],
    )
    assert doctor_result.exit_code == 0, doctor_result.output
    assert "llama-cli" in doctor_result.output
    assert "Model file" in doctor_result.output

    smoke_result = runner.invoke(
        app,
        ["smoke", "--model-profile", "setup_smoke_model"],
    )
    assert smoke_result.exit_code == 0, smoke_result.output
    assert "Smoke check passed" in smoke_result.output


def test_setup_created_profile_allows_run_dry_run(
    isolated_user_config: Path,
    monkeypatch,
) -> None:
    llama_cli = _make_executable(isolated_user_config / "llama-cli")
    model_path = _make_gguf(isolated_user_config / "model.gguf")

    setup_result = runner.invoke(
        app,
        [
            "setup",
            "--non-interactive",
            "--llama-cli",
            str(llama_cli),
            "--model-path",
            str(model_path),
            "--profile-name",
            "setup_smoke_model",
        ],
    )
    assert setup_result.exit_code == 0, setup_result.output

    def fake_run_llama_cpp(config, prompt):
        raise AssertionError("setup dry-run must not launch llama.cpp")

    monkeypatch.setattr(run_helpers, "run_llama_cpp", fake_run_llama_cpp)

    dry_run_result = runner.invoke(
        app,
        [
            "run",
            "--suite",
            "practical",
            "--only",
            "honesty-uncertainty/fake-package-currentness",
            "--model-profile",
            "setup_smoke_model",
            "--ctx",
            "8192",
            "--max-tokens",
            "800",
            "--temp",
            "0.2",
            "--dry-run",
        ],
    )

    assert dry_run_result.exit_code == 0, dry_run_result.output
    assert "Dry run complete" in dry_run_result.output
    assert not (isolated_user_config / "results").exists()


def test_setup_non_interactive_does_not_launch_model(
    isolated_user_config: Path,
    monkeypatch,
) -> None:
    llama_cli = _make_executable(isolated_user_config / "llama-cli")
    model_path = _make_gguf(isolated_user_config / "model.gguf")

    def fake_run_llama_cpp(config, prompt):
        raise AssertionError("setup must not launch llama.cpp")

    monkeypatch.setattr(run_helpers, "run_llama_cpp", fake_run_llama_cpp)

    result = runner.invoke(
        app,
        [
            "setup",
            "--non-interactive",
            "--llama-cli",
            str(llama_cli),
            "--model-path",
            str(model_path),
            "--profile-name",
            "setup_model",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "No model was launched" in result.output