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

    with pytest.raises(ValueError, match="already exists"):
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
