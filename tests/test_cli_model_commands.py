from pathlib import Path

from typer.testing import CliRunner

from llmgauge.cli import app

runner = CliRunner()


def test_model_add_list_remove_flow(tmp_path: Path) -> None:
    profiles_path = tmp_path / "model-profiles.yaml"
    profiles_path.write_text(
        "schema_version: llmgauge.model_profiles.v0\nmodels: {}\n",
        encoding="utf-8",
    )
    model_path = tmp_path / "model.gguf"
    model_path.write_text("fake model\n", encoding="utf-8")

    add_result = runner.invoke(
        app,
        [
            "model",
            "add",
            "example_model",
            "--path",
            str(model_path),
            "--label",
            "Example Model",
            "--family",
            "TestFamily",
            "--quant",
            "Q4_K_M",
            "--model-profiles",
            str(profiles_path),
        ],
    )
    assert add_result.exit_code == 0, add_result.output
    assert "Added model profile" in add_result.output

    list_result = runner.invoke(
        app,
        ["model", "list", "--model-profiles", str(profiles_path)],
    )
    assert list_result.exit_code == 0, list_result.output
    assert "example_model" in list_result.output
    assert "Example Model" in list_result.output
    assert "ok" in list_result.output

    remove_result = runner.invoke(
        app,
        [
            "model",
            "remove",
            "example_model",
            "--model-profiles",
            str(profiles_path),
            "--yes",
        ],
    )
    assert remove_result.exit_code == 0, remove_result.output
    assert "Removed model profile" in remove_result.output


def test_model_update_changes_label(tmp_path: Path) -> None:
    profiles_path = tmp_path / "model-profiles.yaml"
    model_path = tmp_path / "model.gguf"
    model_path.write_text("fake model\n", encoding="utf-8")
    profiles_path.write_text(
        f"""schema_version: llmgauge.model_profiles.v0
models:
  example_model:
    label: Old Label
    path: {model_path}
""",
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "model",
            "update",
            "example_model",
            "--label",
            "New Label",
            "--model-profiles",
            str(profiles_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Updated model profile" in result.output
    assert "New Label" in profiles_path.read_text(encoding="utf-8")


def test_model_remove_requires_yes(tmp_path: Path) -> None:
    profiles_path = tmp_path / "model-profiles.yaml"
    profiles_path.write_text(
        """
schema_version: llmgauge.model_profiles.v0
models:
  removable_model:
    label: Removable Model
    path: /tmp/model.gguf
""".lstrip(),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        ["model", "remove", "removable_model", "--model-profiles", str(profiles_path)],
    )

    assert result.exit_code != 0
    assert "Pass" in result.output
    assert "confirm model profile removal" in result.output
    assert "removable_model" in profiles_path.read_text(encoding="utf-8")
