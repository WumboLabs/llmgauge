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


def test_init_user_config_prints_safe_first_run_next_steps(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg-config"))

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

    result = runner.invoke(app, ["init"])

    assert result.exit_code == 0
    assert "llmgauge smoke" in result.output
    assert "llmgauge list-suites" in result.output
    assert "llmgauge run --dry-run" in result.output


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


def test_resolve_run_options_auto_detects_user_config_when_local_missing(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg-config"))

    user_config_dir = tmp_path / "xdg-config" / "llmgauge"
    user_config_dir.mkdir(parents=True)

    llama_cli = tmp_path / "llama-cli"
    llama_cli.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    llama_cli.chmod(0o755)

    model_path = tmp_path / "model.gguf"
    model_path.write_text("fake model placeholder\n", encoding="utf-8")

    user_config = user_config_dir / "config.yaml"
    user_config.write_text(
        f"""schema_version: llmgauge.config.v0
runtime:
  llama_cli: {llama_cli}
defaults:
  ctx_size: 24576
  max_tokens: 700
""",
        encoding="utf-8",
    )

    user_profiles = user_config_dir / "model-profiles.yaml"
    user_profiles.write_text(
        f"""schema_version: llmgauge.model_profiles.v0
models:
  user_model:
    label: User Model
    path: {model_path}
    temperature: 0.15
""",
        encoding="utf-8",
    )

    resolved = cli._resolve_run_options(
        model_id=None,
        model_profile="user_model",
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
        flash_attn=None,
        runtime_label=None,
    )

    assert resolved["config_path"].resolve() == user_config.resolve()
    assert resolved["model_profiles_path"].resolve() == user_profiles.resolve()
    assert resolved["model_id"] == "user_model"
    assert resolved["model_path"] == model_path
    assert resolved["llama_cli"] == llama_cli
    assert resolved["ctx"] == 24576
    assert resolved["max_tokens"] == 700
    assert resolved["temp"] == 0.15


def test_resolve_run_options_prefers_project_local_over_user_config(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg-config"))

    examples_dir = tmp_path / "examples" / "configs"
    examples_dir.mkdir(parents=True)

    user_config_dir = tmp_path / "xdg-config" / "llmgauge"
    user_config_dir.mkdir(parents=True)

    project_llama_cli = tmp_path / "project-llama-cli"
    project_llama_cli.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    project_llama_cli.chmod(0o755)

    user_llama_cli = tmp_path / "user-llama-cli"
    user_llama_cli.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    user_llama_cli.chmod(0o755)

    project_model = tmp_path / "project-model.gguf"
    project_model.write_text("fake model placeholder\n", encoding="utf-8")

    user_model = tmp_path / "user-model.gguf"
    user_model.write_text("fake model placeholder\n", encoding="utf-8")

    (examples_dir / "llmgauge.local.yaml").write_text(
        f"""schema_version: llmgauge.config.v0
runtime:
  llama_cli: {project_llama_cli}
defaults:
  ctx_size: 8192
""",
        encoding="utf-8",
    )
    (examples_dir / "model-profiles.local.yaml").write_text(
        f"""schema_version: llmgauge.model_profiles.v0
models:
  example_model:
    label: Project Model
    path: {project_model}
""",
        encoding="utf-8",
    )

    (user_config_dir / "config.yaml").write_text(
        f"""schema_version: llmgauge.config.v0
runtime:
  llama_cli: {user_llama_cli}
defaults:
  ctx_size: 32768
""",
        encoding="utf-8",
    )
    (user_config_dir / "model-profiles.yaml").write_text(
        f"""schema_version: llmgauge.model_profiles.v0
models:
  example_model:
    label: User Model
    path: {user_model}
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
        flash_attn=None,
        runtime_label=None,
    )

    assert resolved["config_path"].resolve() == (
        examples_dir / "llmgauge.local.yaml"
    ).resolve()
    assert resolved["model_profiles_path"].resolve() == (
        examples_dir / "model-profiles.local.yaml"
    ).resolve()
    assert resolved["model_path"] == project_model
    assert resolved["llama_cli"] == project_llama_cli
    assert resolved["ctx"] == 8192


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


def test_resolve_run_options_uses_flash_attn_from_profile_and_cli_override(
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
defaults:
  flash_attn: off
""",
        encoding="utf-8",
    )

    (examples_dir / "model-profiles.local.yaml").write_text(
        f"""schema_version: llmgauge.model_profiles.v0
models:
  example_model:
    label: Example Model
    path: {model_path}
    flash_attn: on
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
        flash_attn=None,
    )

    assert resolved["flash_attn"] == "on"

    overridden = cli._resolve_run_options(
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
        flash_attn="auto",
    )

    assert overridden["flash_attn"] == "auto"


def test_resolve_run_options_rejects_invalid_flash_attn(
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
            flash_attn="maybe",
        )
    except Exception as exc:
        message = str(exc)
    else:
        message = ""

    assert "flash_attn must be one of: auto, on, off" in message


def test_resolve_run_options_uses_runtime_label_from_profile_and_cli_override(
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
defaults:
  runtime_label: stock-reference
""",
        encoding="utf-8",
    )

    (examples_dir / "model-profiles.local.yaml").write_text(
        f"""schema_version: llmgauge.model_profiles.v0
models:
  example_model:
    label: Example Model
    path: {model_path}
    runtime_label: daily-tuned
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
        flash_attn=None,
        runtime_label=None,
    )

    assert resolved["runtime_label"] == "daily-tuned"

    overridden = cli._resolve_run_options(
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
        flash_attn=None,
        runtime_label="experimental",
    )

    assert overridden["runtime_label"] == "experimental"


def test_resolve_run_options_normalizes_blank_runtime_label(
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
        flash_attn=None,
        runtime_label="   ",
    )

    assert resolved["runtime_label"] is None

def test_init_creates_user_config_files(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg-config"))

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

    result = runner.invoke(app, ["init"])

    user_config_dir = tmp_path / "xdg-config" / "llmgauge"

    assert result.exit_code == 0
    assert (user_config_dir / "config.yaml").exists()
    assert (user_config_dir / "model-profiles.yaml").exists()
    assert "created" in result.output
    assert "Config directory" in result.output
    assert "llmgauge smoke" in result.output
    assert "llmgauge list-suites" in result.output
    assert "llmgauge run --dry-run" in result.output


def test_init_skips_existing_user_config_without_force(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg-config"))

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

    user_config_dir = tmp_path / "xdg-config" / "llmgauge"
    user_config_dir.mkdir(parents=True)
    user_config = user_config_dir / "config.yaml"
    user_config.write_text("keep: true\n", encoding="utf-8")

    result = runner.invoke(app, ["init"])

    assert result.exit_code == 0
    assert "skipped" in result.output
    assert user_config.read_text(encoding="utf-8") == "keep: true\n"


def test_init_force_overwrites_user_config(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg-config"))

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

    user_config_dir = tmp_path / "xdg-config" / "llmgauge"
    user_config_dir.mkdir(parents=True)
    user_config = user_config_dir / "config.yaml"
    user_config.write_text("replace: true\n", encoding="utf-8")

    result = runner.invoke(app, ["init", "--force"])

    assert result.exit_code == 0
    assert "created" in result.output
    assert user_config.read_text(encoding="utf-8") == (
        "schema_version: llmgauge.config.v0\n"
    )
