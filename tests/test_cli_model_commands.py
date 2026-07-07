import re
from pathlib import Path

from typer.testing import CliRunner

from llmgauge.cli import app

runner = CliRunner()


def _strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


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


def test_model_list_accepts_model_profile_file_alias(tmp_path: Path) -> None:
    profiles_path = tmp_path / "model-profiles.yaml"
    profiles_path.write_text(
        """
schema_version: llmgauge.model_profiles.v0
models:
  alias_model:
    label: Alias Model
    path: /tmp/model.gguf
""".lstrip(),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        ["model", "list", "--model-profile-file", str(profiles_path)],
    )

    assert result.exit_code == 0, result.output
    assert "alias_model" in result.output
    assert "Alias Model" in result.output


def test_model_add_accepts_model_profile_file_alias(tmp_path: Path) -> None:
    profiles_path = tmp_path / "model-profiles.yaml"
    profiles_path.write_text(
        "schema_version: llmgauge.model_profiles.v0\nmodels: {}\n",
        encoding="utf-8",
    )
    model_path = tmp_path / "model.gguf"
    model_path.write_text("fake model\n", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "model",
            "add",
            "alias_added",
            "--path",
            str(model_path),
            "--model-profile-file",
            str(profiles_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Added model profile" in result.output
    assert "alias_added" in profiles_path.read_text(encoding="utf-8")


def test_model_help_lists_model_profile_file_alias() -> None:
    result = runner.invoke(app, ["model", "list", "--help"])

    assert result.exit_code == 0, result.output
    plain_output = _strip_ansi(result.output)
    assert "--model-profiles" in plain_output
    # Rich help truncates the second alias; the comma shows dual option names.
    assert ",--model-profi" in plain_output
    assert "Model profiles YAML to list" in plain_output


def test_model_list_accepts_both_model_profile_file_aliases(tmp_path: Path) -> None:
    profiles_path = tmp_path / "model-profiles.yaml"
    profiles_path.write_text(
        """
schema_version: llmgauge.model_profiles.v0
models:
  dual_alias_model:
    label: Dual Alias Model
    path: /tmp/model.gguf
""".lstrip(),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "model",
            "list",
            "--model-profiles",
            str(profiles_path),
            "--model-profile-file",
            str(profiles_path),
        ],
    )

    # Typer treats both flags as one option; the last value wins and the command succeeds.
    assert result.exit_code == 0, result.output
    assert "dual_alias_model" in result.output


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
