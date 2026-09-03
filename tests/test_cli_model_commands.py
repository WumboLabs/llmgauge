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


def test_model_list_without_profiles_file_suggests_init(monkeypatch) -> None:
    monkeypatch.setattr(
        "llmgauge.commands.models.default_model_profiles_path",
        lambda explicit: explicit,
    )

    result = runner.invoke(app, ["model", "list"])
    plain_output = _strip_ansi(result.output)

    assert result.exit_code != 0
    assert "No model profiles file found" in plain_output
    assert "llmgauge init" in plain_output
    assert "--model-profile-file" in plain_output


def test_model_list_invalid_profiles_file_reports_validation_context(
    tmp_path: Path,
) -> None:
    profiles_path = tmp_path / "model-profiles.yaml"
    profiles_path.write_text(
        "schema_version: llmgauge.model_profiles.v0\nmodels: bad\n",
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        ["model", "list", "--model-profile-file", str(profiles_path)],
    )

    assert result.exit_code != 0
    assert "Invalid model profiles file" in result.output


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


# ---------------------------------------------------------------------------
# M1 runtime-neutral source-kind CLI behavior
# ---------------------------------------------------------------------------


def test_model_add_legacy_shape_still_requires_path(tmp_path: Path) -> None:
    profiles_path = tmp_path / "model-profiles.yaml"
    profiles_path.write_text(
        "schema_version: llmgauge.model_profiles.v0\nmodels: {}\n",
        encoding="utf-8",
    )

    result = runner.invoke(
        app, ["model", "add", "no_path", "--model-profiles", str(profiles_path)]
    )

    assert result.exit_code != 0
    assert "--path" in result.output


def test_model_add_legacy_shape_rejects_directory(tmp_path: Path) -> None:
    profiles_path = tmp_path / "model-profiles.yaml"
    profiles_path.write_text(
        "schema_version: llmgauge.model_profiles.v0\nmodels: {}\n",
        encoding="utf-8",
    )
    checkpoint_dir = tmp_path / "Qwen-Native"
    checkpoint_dir.mkdir()

    result = runner.invoke(
        app,
        [
            "model",
            "add",
            "legacy_dir",
            "--path",
            str(checkpoint_dir),
            "--model-profiles",
            str(profiles_path),
        ],
    )

    # Legacy no-discriminator --path remains contractual GGUF file semantics:
    # a directory is rejected, never reinterpreted as a checkpoint.
    assert result.exit_code != 0
    assert "not a file" in result.output
    assert "legacy_dir" not in profiles_path.read_text(encoding="utf-8")


def test_model_add_explicit_gguf_file(tmp_path: Path) -> None:
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
            "explicit_gguf",
            "--source-kind",
            "gguf_file",
            "--path",
            str(model_path),
            "--model-profiles",
            str(profiles_path),
        ],
    )

    assert result.exit_code == 0, result.output
    stored = profiles_path.read_text(encoding="utf-8")
    assert "source_kind: gguf_file" in stored


def test_model_add_explicit_gguf_file_rejects_directory(tmp_path: Path) -> None:
    profiles_path = tmp_path / "model-profiles.yaml"
    profiles_path.write_text(
        "schema_version: llmgauge.model_profiles.v0\nmodels: {}\n",
        encoding="utf-8",
    )
    some_dir = tmp_path / "adir"
    some_dir.mkdir()

    result = runner.invoke(
        app,
        [
            "model",
            "add",
            "bad_gguf",
            "--source-kind",
            "gguf_file",
            "--path",
            str(some_dir),
            "--model-profiles",
            str(profiles_path),
        ],
    )

    assert result.exit_code != 0
    assert "not a file" in result.output


def test_model_add_checkpoint_directory(tmp_path: Path) -> None:
    profiles_path = tmp_path / "model-profiles.yaml"
    profiles_path.write_text(
        "schema_version: llmgauge.model_profiles.v0\nmodels: {}\n",
        encoding="utf-8",
    )
    checkpoint_dir = tmp_path / "Qwen-Native"
    checkpoint_dir.mkdir()

    result = runner.invoke(
        app,
        [
            "model",
            "add",
            "native_model",
            "--source-kind",
            "checkpoint_directory",
            "--path",
            str(checkpoint_dir),
            "--model-profiles",
            str(profiles_path),
        ],
    )

    assert result.exit_code == 0, result.output
    stored = profiles_path.read_text(encoding="utf-8")
    assert "source_kind: checkpoint_directory" in stored
    assert str(checkpoint_dir) in stored


def test_model_add_checkpoint_directory_rejects_file(tmp_path: Path) -> None:
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
            "bad_ckpt",
            "--source-kind",
            "checkpoint_directory",
            "--path",
            str(model_path),
            "--model-profiles",
            str(profiles_path),
        ],
    )

    assert result.exit_code != 0
    assert "not a directory" in result.output


def test_model_add_checkpoint_directory_requires_existing_path(tmp_path: Path) -> None:
    profiles_path = tmp_path / "model-profiles.yaml"
    profiles_path.write_text(
        "schema_version: llmgauge.model_profiles.v0\nmodels: {}\n",
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "model",
            "add",
            "absent_ckpt",
            "--source-kind",
            "checkpoint_directory",
            "--path",
            str(tmp_path / "absent"),
            "--model-profiles",
            str(profiles_path),
        ],
    )

    assert result.exit_code != 0
    assert "Checkpoint directory does not exist" in result.output


def test_model_add_served_model_reference(tmp_path: Path) -> None:
    profiles_path = tmp_path / "model-profiles.yaml"
    profiles_path.write_text(
        "schema_version: llmgauge.model_profiles.v0\nmodels: {}\n",
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "model",
            "add",
            "served_model",
            "--source-kind",
            "served_model_reference",
            "--served-model",
            "my-served-name",
            "--model-profiles",
            str(profiles_path),
        ],
    )

    assert result.exit_code == 0, result.output
    stored = profiles_path.read_text(encoding="utf-8")
    assert "source_kind: served_model_reference" in stored
    assert "served_model: my-served-name" in stored


def test_model_add_served_reference_requires_served_model(tmp_path: Path) -> None:
    profiles_path = tmp_path / "model-profiles.yaml"
    profiles_path.write_text(
        "schema_version: llmgauge.model_profiles.v0\nmodels: {}\n",
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "model",
            "add",
            "served_bad",
            "--source-kind",
            "served_model_reference",
            "--model-profiles",
            str(profiles_path),
        ],
    )

    assert result.exit_code != 0
    assert "requires --served-model" in result.output


def test_model_add_served_reference_rejects_path(tmp_path: Path) -> None:
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
            "served_bad",
            "--source-kind",
            "served_model_reference",
            "--served-model",
            "x",
            "--path",
            str(model_path),
            "--model-profiles",
            str(profiles_path),
        ],
    )

    assert result.exit_code != 0
    assert "does not accept --path" in result.output


def test_model_add_rejects_unknown_source_kind(tmp_path: Path) -> None:
    profiles_path = tmp_path / "model-profiles.yaml"
    profiles_path.write_text(
        "schema_version: llmgauge.model_profiles.v0\nmodels: {}\n",
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "model",
            "add",
            "bad_kind",
            "--source-kind",
            "sglang",
            "--path",
            str(tmp_path),
            "--model-profiles",
            str(profiles_path),
        ],
    )

    assert result.exit_code != 0
    assert "source_kind must be one of" in result.output


def test_model_add_does_not_require_backend(tmp_path: Path) -> None:
    # Model identity and runtime selection stay separate: adding a
    # checkpoint-directory profile needs no backend flag and stores none.
    profiles_path = tmp_path / "model-profiles.yaml"
    profiles_path.write_text(
        "schema_version: llmgauge.model_profiles.v0\nmodels: {}\n",
        encoding="utf-8",
    )
    checkpoint_dir = tmp_path / "Qwen-Native"
    checkpoint_dir.mkdir()

    result = runner.invoke(
        app,
        [
            "model",
            "add",
            "neutral_model",
            "--source-kind",
            "checkpoint_directory",
            "--path",
            str(checkpoint_dir),
            "--model-profiles",
            str(profiles_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "backend" not in profiles_path.read_text(encoding="utf-8")


def test_model_list_distinguishes_source_kinds(tmp_path: Path) -> None:
    profiles_path = tmp_path / "model-profiles.yaml"
    gguf = tmp_path / "model.gguf"
    gguf.write_text("fake model\n", encoding="utf-8")
    checkpoint_dir = tmp_path / "Qwen-Native"
    checkpoint_dir.mkdir()
    profiles_path.write_text(
        f"""schema_version: llmgauge.model_profiles.v0
models:
  legacy_gguf:
    label: Legacy Gguf
    path: {gguf}
  explicit_gguf:
    label: Explicit Gguf
    source_kind: gguf_file
    path: {gguf}
  native_ckpt:
    label: Native Ckpt
    source_kind: checkpoint_directory
    path: {checkpoint_dir}
  served_ref:
    label: Served Ref
    source_kind: served_model_reference
    served_model: my-served-name
  legacy_vllm:
    label: Legacy Vllm
    backend: vllm
    served_model: legacy-serve
""",
        encoding="utf-8",
    )

    result = runner.invoke(
        app, ["model", "list", "--model-profiles", str(profiles_path)]
    )

    assert result.exit_code == 0, result.output
    assert "Source Kind" in result.output
    assert "Source Status" in result.output
    assert "gguf_file" in result.output
    assert "checkpoint_directory" in result.output
    assert "served_model_reference" in result.output
    # Conservative served status: never "verified"/"available".
    assert "configured" in result.output
    assert "verified" not in result.output
    assert "available" not in result.output


def test_model_update_source_kind_and_served_model(tmp_path: Path) -> None:
    profiles_path = tmp_path / "model-profiles.yaml"
    gguf = tmp_path / "model.gguf"
    gguf.write_text("fake model\n", encoding="utf-8")
    profiles_path.write_text(
        f"""schema_version: llmgauge.model_profiles.v0
models:
  upd_model:
    label: Upd Model
    path: {gguf}
""",
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "model",
            "update",
            "upd_model",
            "--source-kind",
            "gguf_file",
            "--model-profiles",
            str(profiles_path),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "source_kind: gguf_file" in profiles_path.read_text(encoding="utf-8")

    served_result = runner.invoke(
        app,
        [
            "model",
            "update",
            "upd_model",
            "--source-kind",
            "served_model_reference",
            "--served-model",
            "renamed-serve",
            "--model-profiles",
            str(profiles_path),
        ],
    )
    # The profile still carries a local path, so the incompatible switch must
    # fail closed instead of silently producing a contradictory profile.
    assert served_result.exit_code != 0
    assert "invalid" in served_result.output
    assert "source_kind: served_model_reference" not in profiles_path.read_text(
        encoding="utf-8"
    )


def test_model_update_checkpoint_path_uses_directory_rule(tmp_path: Path) -> None:
    profiles_path = tmp_path / "model-profiles.yaml"
    checkpoint_dir = tmp_path / "Qwen-Native"
    checkpoint_dir.mkdir()
    profiles_path.write_text(
        f"""schema_version: llmgauge.model_profiles.v0
models:
  ckpt_model:
    label: Ckpt Model
    source_kind: checkpoint_directory
    path: {tmp_path / "absent"}
""",
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "model",
            "update",
            "ckpt_model",
            "--path",
            str(checkpoint_dir),
            "--model-profiles",
            str(profiles_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert str(checkpoint_dir) in profiles_path.read_text(encoding="utf-8")

    (checkpoint_dir / "notadir.txt").write_text("x", encoding="utf-8")
    file_result = runner.invoke(
        app,
        [
            "model",
            "update",
            "ckpt_model",
            "--path",
            str(checkpoint_dir / "notadir.txt"),
            "--model-profiles",
            str(profiles_path),
        ],
    )
    assert file_result.exit_code != 0
    assert "not a directory" in file_result.output
