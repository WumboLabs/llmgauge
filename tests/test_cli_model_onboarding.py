from pathlib import Path

from typer.testing import CliRunner

import llmgauge.cli as cli
from llmgauge.cli import app

runner = CliRunner()


def test_list_model_profiles_shows_existing_and_missing_paths(tmp_path: Path) -> None:
    existing_model = tmp_path / "model.gguf"
    existing_model.write_text("fake model placeholder\n", encoding="utf-8")

    profiles_path = tmp_path / "model-profiles.yaml"
    profiles_path.write_text(
        f"""schema_version: llmgauge.model_profiles.v0
models:
  existing_model:
    label: Existing Model
    family: TestFamily
    role: test-role
    quant: Q4_K_M
    path: {existing_model}
  missing_model:
    label: Missing Model
    family: TestFamily
    role: missing-role
    quant: Q5_K_M
    path: {tmp_path / "missing.gguf"}
  no_path_model:
    label: No Path Model
""",
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        ["list-model-profiles", "--model-profiles", str(profiles_path)],
    )

    assert result.exit_code == 0
    assert "existing_model" in result.output
    assert "ok" in result.output
    assert "missing_model" in result.output
    assert "missing-file" in result.output
    assert "no_path_model" in result.output
    assert "missing-path" in result.output


def test_list_model_profiles_missing_file_fails(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["list-model-profiles", "--model-profiles", str(tmp_path / "missing.yaml")],
    )

    assert result.exit_code != 0
    assert "Model profiles file does not exist" in result.output


def test_init_config_creates_local_files(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    examples_dir = tmp_path / "examples" / "configs"
    examples_dir.mkdir(parents=True)
    (examples_dir / "llmgauge.example.yaml").write_text(
        "schema_version: llmgauge.config.v0\n",
        encoding="utf-8",
    )
    (examples_dir / "model-profiles.example.yaml").write_text(
        "schema_version: llmgauge.model_profiles.v0\nmodels: {}\n",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["init-config"])

    assert result.exit_code == 0
    assert (examples_dir / "llmgauge.local.yaml").exists()
    assert (examples_dir / "model-profiles.local.yaml").exists()
    assert "created" in result.output


def test_init_config_skips_existing_without_force(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    examples_dir = tmp_path / "examples" / "configs"
    examples_dir.mkdir(parents=True)
    (examples_dir / "llmgauge.example.yaml").write_text(
        "schema_version: llmgauge.config.v0\n",
        encoding="utf-8",
    )
    (examples_dir / "model-profiles.example.yaml").write_text(
        "schema_version: llmgauge.model_profiles.v0\nmodels: {}\n",
        encoding="utf-8",
    )
    local_config = examples_dir / "llmgauge.local.yaml"
    local_config.write_text("keep: true\n", encoding="utf-8")

    result = runner.invoke(app, ["init-config"])

    assert result.exit_code == 0
    assert "skipped" in result.output
    assert local_config.read_text(encoding="utf-8") == "keep: true\n"


def test_resolve_run_options_auto_detects_local_config_and_profiles(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    examples_dir = tmp_path / "examples" / "configs"
    examples_dir.mkdir(parents=True)

    llama_cli = tmp_path / "llama-cli"
    llama_cli.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    llama_cli.chmod(0o755)

    model_path = tmp_path / "model.gguf"
    model_path.write_text("fake model placeholder\n", encoding="utf-8")

    local_config = examples_dir / "llmgauge.local.yaml"
    local_config.write_text(
        f"""schema_version: llmgauge.config.v0
runtime:
  llama_cli: {llama_cli}
defaults:
  ctx_size: 12288
  max_tokens: 600
""",
        encoding="utf-8",
    )

    local_profiles = examples_dir / "model-profiles.local.yaml"
    local_profiles.write_text(
        f"""schema_version: llmgauge.model_profiles.v0
models:
  example_model:
    label: Example Model
    path: {model_path}
    temperature: 0.1
""",
        encoding="utf-8",
    )

    resolved = cli._resolve_run_options(
        model_id=None,
        model_profile="example_model",
        config_path=None,
        model_profiles_path=None,
        model_path=None,
        llama_cli=None,
        ctx=None,
        max_tokens=None,
        temp=None,
        top_p=None,
        batch=None,
        ubatch=None,
        gpu_layers=None,
    )

    assert resolved["config_path"].resolve() == local_config.resolve()
    assert resolved["model_profiles_path"].resolve() == local_profiles.resolve()
    assert resolved["model_id"] == "example_model"
    assert resolved["model_path"] == model_path
    assert resolved["llama_cli"] == llama_cli
    assert resolved["ctx"] == 12288
    assert resolved["max_tokens"] == 600
    assert resolved["temp"] == 0.1


def test_resolve_run_options_explicit_paths_override_local_defaults(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    examples_dir = tmp_path / "examples" / "configs"
    examples_dir.mkdir(parents=True)

    default_llama_cli = tmp_path / "default-llama-cli"
    default_llama_cli.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    default_llama_cli.chmod(0o755)

    explicit_llama_cli = tmp_path / "explicit-llama-cli"
    explicit_llama_cli.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    explicit_llama_cli.chmod(0o755)

    default_model = tmp_path / "default-model.gguf"
    default_model.write_text("fake model placeholder\n", encoding="utf-8")

    explicit_model = tmp_path / "explicit-model.gguf"
    explicit_model.write_text("fake model placeholder\n", encoding="utf-8")

    (examples_dir / "llmgauge.local.yaml").write_text(
        f"""schema_version: llmgauge.config.v0
runtime:
  llama_cli: {default_llama_cli}
defaults:
  ctx_size: 8192
""",
        encoding="utf-8",
    )
    (examples_dir / "model-profiles.local.yaml").write_text(
        f"""schema_version: llmgauge.model_profiles.v0
models:
  example_model:
    label: Default Model
    path: {default_model}
""",
        encoding="utf-8",
    )

    explicit_config = tmp_path / "explicit-config.yaml"
    explicit_config.write_text(
        f"""schema_version: llmgauge.config.v0
runtime:
  llama_cli: {explicit_llama_cli}
defaults:
  ctx_size: 16384
""",
        encoding="utf-8",
    )

    explicit_profiles = tmp_path / "explicit-profiles.yaml"
    explicit_profiles.write_text(
        f"""schema_version: llmgauge.model_profiles.v0
models:
  example_model:
    label: Explicit Model
    path: {explicit_model}
""",
        encoding="utf-8",
    )

    resolved = cli._resolve_run_options(
        model_id=None,
        model_profile="example_model",
        config_path=explicit_config,
        model_profiles_path=explicit_profiles,
        model_path=None,
        llama_cli=None,
        ctx=None,
        max_tokens=None,
        temp=None,
        top_p=None,
        batch=None,
        ubatch=None,
        gpu_layers=None,
    )

    assert resolved["config_path"] == explicit_config
    assert resolved["model_profiles_path"] == explicit_profiles
    assert resolved["model_path"] == explicit_model
    assert resolved["llama_cli"] == explicit_llama_cli
    assert resolved["ctx"] == 16384


def test_resolve_run_options_warns_when_model_id_matches_profile(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    examples_dir = tmp_path / "examples" / "configs"
    examples_dir.mkdir(parents=True)

    llama_cli = tmp_path / "llama-cli"
    llama_cli.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    llama_cli.chmod(0o755)

    model_path = tmp_path / "model.gguf"
    model_path.write_text("fake model placeholder\n", encoding="utf-8")

    (examples_dir / "llmgauge.local.yaml").write_text(
        f"""schema_version: llmgauge.config.v0
runtime:
  llama_cli: {llama_cli}
""",
        encoding="utf-8",
    )

    (examples_dir / "model-profiles.local.yaml").write_text(
        f"""schema_version: llmgauge.model_profiles.v0
models:
  example_model:
    label: Example Model
    path: {model_path}
""",
        encoding="utf-8",
    )

    try:
        cli._resolve_run_options(
            model_id="example_model",
            model_profile=None,
            config_path=None,
            model_profiles_path=None,
            model_path=None,
            llama_cli=None,
            ctx=None,
            max_tokens=None,
            temp=None,
            top_p=None,
            batch=None,
            ubatch=None,
            gpu_layers=None,
        )
    except Exception as exc:
        message = str(exc)
    else:
        message = ""

    assert "Model profile 'example_model' was provided with --model-id" in message
    assert "Use --model-profile example_model" in message
