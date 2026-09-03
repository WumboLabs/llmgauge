from pathlib import Path

import pytest
import yaml

from llmgauge.core.model_profiles_store import (
    add_model_profile,
    load_model_profiles_document,
    remove_model_profile,
    update_model_profile,
)
from llmgauge.core.schemas import validate_model_profiles_document


def test_validate_model_profiles_rejects_invalid_models_mapping() -> None:
    with pytest.raises(Exception):
        validate_model_profiles_document(
            {"schema_version": "llmgauge.model_profiles.v0", "models": "bad"}
        )


def test_load_model_profiles_document_reports_invalid_file_label(
    tmp_path: Path,
) -> None:
    profiles_path = tmp_path / "model-profiles.yaml"
    profiles_path.write_text(
        "schema_version: llmgauge.model_profiles.v0\nmodels: bad\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Invalid model profiles file"):
        load_model_profiles_document(profiles_path)


def test_add_and_list_model_profile_round_trip(tmp_path: Path) -> None:
    profiles_path = tmp_path / "model-profiles.yaml"
    model_path = tmp_path / "model.gguf"
    model_path.write_text("fake model\n", encoding="utf-8")

    add_model_profile(
        profiles_path,
        profile_name="example_model",
        model_path=model_path,
        label="Example Model",
        family="Test",
        quant="Q4_K_M",
    )

    document = load_model_profiles_document(profiles_path)
    assert "example_model" in document.models
    assert document.models["example_model"].path == str(model_path)

    raw = yaml.safe_load(profiles_path.read_text(encoding="utf-8"))
    assert raw["schema_version"] == "llmgauge.model_profiles.v0"


def test_add_model_profile_rejects_duplicate_without_force(tmp_path: Path) -> None:
    profiles_path = tmp_path / "model-profiles.yaml"
    model_path = tmp_path / "model.gguf"
    model_path.write_text("fake model\n", encoding="utf-8")

    add_model_profile(
        profiles_path,
        profile_name="dup_model",
        model_path=model_path,
    )

    with pytest.raises(ValueError, match="pass --force to replace it"):
        add_model_profile(
            profiles_path,
            profile_name="dup_model",
            model_path=model_path,
        )


def test_update_and_remove_model_profile(tmp_path: Path) -> None:
    profiles_path = tmp_path / "model-profiles.yaml"
    model_path = tmp_path / "model.gguf"
    model_path.write_text("fake model\n", encoding="utf-8")

    add_model_profile(
        profiles_path,
        profile_name="mutable_model",
        model_path=model_path,
        label="Old Label",
    )

    update_model_profile(
        profiles_path,
        profile_name="mutable_model",
        label="New Label",
    )

    document = load_model_profiles_document(profiles_path)
    assert document.models["mutable_model"].label == "New Label"

    remove_model_profile(profiles_path, profile_name="mutable_model")
    document = load_model_profiles_document(profiles_path)
    assert "mutable_model" not in document.models


def test_update_model_profile_reports_missing_profile_name(tmp_path: Path) -> None:
    profiles_path = tmp_path / "model-profiles.yaml"
    profiles_path.write_text(
        "schema_version: llmgauge.model_profiles.v0\nmodels: {}\n",
        encoding="utf-8",
    )

    with pytest.raises(
        KeyError,
        match="No model profile named 'missing_model' in the profiles file",
    ):
        update_model_profile(
            profiles_path,
            profile_name="missing_model",
            label="Should Fail",
        )


def test_update_model_profile_preserves_extra_fields(tmp_path: Path) -> None:
    profiles_path = tmp_path / "model-profiles.yaml"
    profiles_path.write_text(
        """
schema_version: llmgauge.model_profiles.v0
models:
  existing_model:
    label: Existing Model
    path: /tmp/model.gguf
    extra_custom_field: keep-me
""".lstrip(),
        encoding="utf-8",
    )

    update_model_profile(
        profiles_path,
        profile_name="existing_model",
        label="Updated Model",
    )

    updated = load_model_profiles_document(profiles_path)
    profile = updated.models["existing_model"].model_dump(exclude_none=True)
    assert profile["label"] == "Updated Model"
    assert profile["extra_custom_field"] == "keep-me"


# ---------------------------------------------------------------------------
# M1 runtime-neutral source-kind behavior
# ---------------------------------------------------------------------------


def test_add_model_profile_legacy_call_stores_no_source_kind(tmp_path: Path) -> None:
    profiles_path = tmp_path / "model-profiles.yaml"
    model_path = tmp_path / "model.gguf"
    model_path.write_text("fake model\n", encoding="utf-8")

    add_model_profile(
        profiles_path,
        profile_name="legacy_model",
        model_path=model_path,
    )

    raw = yaml.safe_load(profiles_path.read_text(encoding="utf-8"))
    assert "source_kind" not in raw["models"]["legacy_model"]
    assert raw["models"]["legacy_model"]["path"] == str(model_path)


def test_add_model_profile_requires_locator_without_source_kind(
    tmp_path: Path,
) -> None:
    profiles_path = tmp_path / "model-profiles.yaml"

    with pytest.raises(
        ValueError, match="Provide model_path or an explicit source_kind"
    ):
        add_model_profile(profiles_path, profile_name="empty_model")


def test_add_model_profile_checkpoint_directory_serializes_source_kind(
    tmp_path: Path,
) -> None:
    profiles_path = tmp_path / "model-profiles.yaml"
    checkpoint_dir = tmp_path / "Qwen-Native"
    checkpoint_dir.mkdir()

    add_model_profile(
        profiles_path,
        profile_name="native_model",
        model_path=checkpoint_dir,
        source_kind="checkpoint_directory",
    )

    raw = yaml.safe_load(profiles_path.read_text(encoding="utf-8"))
    entry = raw["models"]["native_model"]
    assert entry["source_kind"] == "checkpoint_directory"
    assert entry["path"] == str(checkpoint_dir)


def test_add_model_profile_served_reference_serializes_source_kind(
    tmp_path: Path,
) -> None:
    profiles_path = tmp_path / "model-profiles.yaml"

    add_model_profile(
        profiles_path,
        profile_name="served_model",
        source_kind="served_model_reference",
        served_model="my-served-name",
    )

    raw = yaml.safe_load(profiles_path.read_text(encoding="utf-8"))
    entry = raw["models"]["served_model"]
    assert entry["source_kind"] == "served_model_reference"
    assert entry["served_model"] == "my-served-name"
    assert "path" not in entry


def test_add_model_profile_rejects_invalid_source_kind(tmp_path: Path) -> None:
    profiles_path = tmp_path / "model-profiles.yaml"

    with pytest.raises(ValueError, match="source_kind must be one of"):
        add_model_profile(
            profiles_path,
            profile_name="bad_model",
            model_path=tmp_path / "x",
            source_kind="huggingface",
        )


def test_update_model_profile_can_pin_source_kind(tmp_path: Path) -> None:
    profiles_path = tmp_path / "model-profiles.yaml"
    model_path = tmp_path / "model.gguf"
    model_path.write_text("fake model\n", encoding="utf-8")
    add_model_profile(
        profiles_path,
        profile_name="pin_model",
        model_path=model_path,
    )

    update_model_profile(
        profiles_path,
        profile_name="pin_model",
        source_kind="gguf_file",
    )

    raw = yaml.safe_load(profiles_path.read_text(encoding="utf-8"))
    assert raw["models"]["pin_model"]["source_kind"] == "gguf_file"


def test_update_model_profile_can_set_served_model(tmp_path: Path) -> None:
    profiles_path = tmp_path / "model-profiles.yaml"
    add_model_profile(
        profiles_path,
        profile_name="served_update",
        source_kind="served_model_reference",
        served_model="old-name",
    )

    update_model_profile(
        profiles_path,
        profile_name="served_update",
        served_model="new-name",
    )

    raw = yaml.safe_load(profiles_path.read_text(encoding="utf-8"))
    assert raw["models"]["served_update"]["served_model"] == "new-name"


def test_update_model_profile_incompatible_switch_fails_closed(
    tmp_path: Path,
) -> None:
    profiles_path = tmp_path / "model-profiles.yaml"
    model_path = tmp_path / "model.gguf"
    model_path.write_text("fake model\n", encoding="utf-8")
    add_model_profile(
        profiles_path,
        profile_name="switch_model",
        model_path=model_path,
    )

    # Switching a path-bearing profile to served_model_reference cannot be
    # done safely with "None means unchanged" semantics: fail closed and keep
    # the stored profile untouched.
    with pytest.raises(ValueError, match="would make model profile .* invalid"):
        update_model_profile(
            profiles_path,
            profile_name="switch_model",
            source_kind="served_model_reference",
            served_model="remote",
        )

    raw = yaml.safe_load(profiles_path.read_text(encoding="utf-8"))
    assert "source_kind" not in raw["models"]["switch_model"]
    assert raw["models"]["switch_model"]["path"] == str(model_path)


def test_update_model_profile_rejects_unknown_source_kind(tmp_path: Path) -> None:
    profiles_path = tmp_path / "model-profiles.yaml"
    model_path = tmp_path / "model.gguf"
    model_path.write_text("fake model\n", encoding="utf-8")
    add_model_profile(
        profiles_path,
        profile_name="bad_update",
        model_path=model_path,
    )

    with pytest.raises(ValueError, match="source_kind must be one of"):
        update_model_profile(
            profiles_path,
            profile_name="bad_update",
            source_kind="sglang",
        )
