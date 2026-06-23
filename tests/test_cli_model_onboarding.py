from pathlib import Path

from typer.testing import CliRunner

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
