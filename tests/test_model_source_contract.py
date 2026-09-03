"""M1 runtime-neutral model source-kind contract tests.

Covers schema-level source-kind validation, the canonical effective-source-kind
resolver, and legacy GGUF/vLLM compatibility at the profile-document layer.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from llmgauge.core.schemas import (
    MODEL_SOURCE_KINDS,
    ModelProfileEntry,
    effective_source_kind,
    resolve_profile_source_status,
    validate_model_profiles_document,
)


# ---------------------------------------------------------------------------
# Legacy GGUF contract
# ---------------------------------------------------------------------------


def test_legacy_gguf_profile_validates_without_source_kind() -> None:
    entry = ModelProfileEntry(label="Foo", path="/tmp/foo.gguf")
    assert entry.source_kind is None
    dumped = entry.model_dump(exclude_none=True)
    assert "source_kind" not in dumped
    assert dumped == {"label": "Foo", "path": "/tmp/foo.gguf"}


def test_legacy_gguf_document_round_trips_without_injection() -> None:
    document = validate_model_profiles_document(
        {
            "schema_version": "llmgauge.model_profiles.v0",
            "models": {"foo": {"label": "Foo", "path": "/tmp/foo.gguf"}},
        }
    )
    entry = document.models["foo"]
    assert entry.source_kind is None
    assert "source_kind" not in entry.model_dump(exclude_none=True)


def test_legacy_blank_path_still_rejected() -> None:
    with pytest.raises(Exception, match="path must not be empty"):
        ModelProfileEntry(label="Foo", path="   ")


# ---------------------------------------------------------------------------
# Legacy vLLM contract
# ---------------------------------------------------------------------------


def test_legacy_vllm_profile_validates_without_source_kind() -> None:
    entry = ModelProfileEntry(
        backend="vllm", served_model="foo", vllm_endpoint="http://127.0.0.1:8000/v1"
    )
    dumped = entry.model_dump(exclude_none=True)
    assert "source_kind" not in dumped
    assert effective_source_kind(dumped) == "served_model_reference"


# ---------------------------------------------------------------------------
# Explicit source kinds
# ---------------------------------------------------------------------------


def test_explicit_gguf_file_profile_validates() -> None:
    entry = ModelProfileEntry(source_kind="gguf_file", path="/models/foo.gguf")
    assert entry.source_kind == "gguf_file"
    assert entry.model_dump(exclude_none=True)["source_kind"] == "gguf_file"


def test_explicit_checkpoint_directory_profile_validates() -> None:
    entry = ModelProfileEntry(source_kind="checkpoint_directory", path="/models/Qwen")
    assert entry.source_kind == "checkpoint_directory"


def test_checkpoint_directory_validation_does_not_touch_filesystem(
    tmp_path: Path,
) -> None:
    # A nonexistent path validates at the schema layer: M1 performs no
    # existence, content, or hashing checks in profile validation.
    entry = ModelProfileEntry(
        source_kind="checkpoint_directory", path=str(tmp_path / "absent-dir")
    )
    assert entry.source_kind == "checkpoint_directory"
    assert resolve_profile_source_status(entry.model_dump(exclude_none=True)) == (
        "missing-directory"
    )


def test_explicit_served_model_reference_profile_validates() -> None:
    entry = ModelProfileEntry(
        source_kind="served_model_reference", served_model="my-served-name"
    )
    assert entry.source_kind == "served_model_reference"


def test_source_kind_is_case_and_whitespace_normalized() -> None:
    entry = ModelProfileEntry(
        source_kind="  Checkpoint_Directory ", path="/models/Qwen"
    )
    assert entry.source_kind == "checkpoint_directory"


# ---------------------------------------------------------------------------
# Explicit source-shape contradictions fail closed
# ---------------------------------------------------------------------------


def test_gguf_file_without_path_fails() -> None:
    with pytest.raises(Exception, match="requires a non-empty local path"):
        ModelProfileEntry(source_kind="gguf_file")


def test_checkpoint_directory_without_path_fails() -> None:
    with pytest.raises(Exception, match="requires a non-empty local path"):
        ModelProfileEntry(source_kind="checkpoint_directory")


def test_served_model_reference_without_served_model_fails() -> None:
    with pytest.raises(Exception, match="requires a non-empty served_model"):
        ModelProfileEntry(source_kind="served_model_reference")


def test_served_model_reference_with_local_path_fails() -> None:
    with pytest.raises(Exception, match="does not accept a local path"):
        ModelProfileEntry(
            source_kind="served_model_reference",
            served_model="foo",
            path="/models/foo.gguf",
        )


# ---------------------------------------------------------------------------
# Unknown source kinds fail closed
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [
        "gguf",
        "hf",
        "huggingface",
        "safetensors",
        "vllm",
        "sglang",
        "arbitrary-string",
        "",
    ],
)
def test_unknown_source_kind_rejected(value: str) -> None:
    with pytest.raises(Exception, match="source_kind must be one of"):
        ModelProfileEntry(source_kind=value, path="/models/foo")


def test_document_validation_rejects_unknown_source_kind() -> None:
    with pytest.raises(Exception, match="source_kind must be one of"):
        validate_model_profiles_document(
            {
                "schema_version": "llmgauge.model_profiles.v0",
                "models": {
                    "bad": {"path": "/models/foo", "source_kind": "huggingface"}
                },
            }
        )


# ---------------------------------------------------------------------------
# Canonical effective-source-kind resolver
# ---------------------------------------------------------------------------


def test_effective_source_kind_explicit_wins_over_backend() -> None:
    # An explicit discriminator is authoritative even beside a backend field;
    # source kind and runtime backend remain separate concepts.
    kind = effective_source_kind(
        {"source_kind": "checkpoint_directory", "path": "/m", "backend": "llama.cpp"}
    )
    assert kind == "checkpoint_directory"


def test_effective_source_kind_legacy_inference_is_contractual() -> None:
    assert effective_source_kind({"path": "/models/foo.gguf"}) == "gguf_file"
    # A directory-shaped legacy path is NOT reinterpreted as a checkpoint.
    assert effective_source_kind({"path": "/models/Qwen"}) == "gguf_file"
    assert effective_source_kind({"backend": "vllm", "served_model": "x"}) == (
        "served_model_reference"
    )
    assert effective_source_kind({"backend": "llama.cpp", "path": "/m"}) == "gguf_file"
    assert effective_source_kind({}) == "gguf_file"


def test_effective_source_kind_rejects_unknown_explicit_value() -> None:
    with pytest.raises(ValueError, match="Unknown model source kind"):
        effective_source_kind({"source_kind": "sglang"})


def test_model_source_kinds_are_distinct_from_backends() -> None:
    assert "vllm" not in MODEL_SOURCE_KINDS
    assert "sglang" not in MODEL_SOURCE_KINDS
    assert "llama.cpp" not in MODEL_SOURCE_KINDS
    assert MODEL_SOURCE_KINDS == (
        "gguf_file",
        "checkpoint_directory",
        "served_model_reference",
    )


# ---------------------------------------------------------------------------
# Source status (model list truthfulness)
# ---------------------------------------------------------------------------


def test_source_status_for_served_reference_is_configured() -> None:
    status = resolve_profile_source_status({"backend": "vllm", "served_model": "foo"})
    assert status == "configured"


def test_source_status_checkpoint_directory(tmp_path: Path) -> None:
    ok = {"source_kind": "checkpoint_directory", "path": str(tmp_path)}
    missing = {"source_kind": "checkpoint_directory", "path": str(tmp_path / "nope")}
    file_path = tmp_path / "afile"
    file_path.write_text("x", encoding="utf-8")
    not_dir = {"source_kind": "checkpoint_directory", "path": str(file_path)}
    assert resolve_profile_source_status(ok) == "ok"
    assert resolve_profile_source_status(missing) == "missing-directory"
    assert resolve_profile_source_status(not_dir) == "not-a-directory"


def test_source_status_gguf_keeps_existing_vocabulary(tmp_path: Path) -> None:
    existing = tmp_path / "model.gguf"
    existing.write_text("x", encoding="utf-8")
    assert resolve_profile_source_status({"path": str(existing)}) == "ok"
    assert resolve_profile_source_status({"path": str(tmp_path / "gone.gguf")}) == (
        "missing-file"
    )
    assert resolve_profile_source_status({}) == "missing-path"


def test_checkpoint_directory_representation_inspects_no_contents(
    tmp_path: Path,
) -> None:
    # M1 performs no manifest, tokenizer, template, or shard inspection:
    # a directory with arbitrary (even nonsensical) contents is a valid
    # representation, and status depends only on the directory existing.
    junk = tmp_path / "not-a-checkpoint"
    junk.mkdir()
    (junk / "random.bin").write_bytes(b"\x00\x01garbage")
    (junk / "nested").mkdir()

    profile = {"source_kind": "checkpoint_directory", "path": str(junk)}
    entry = ModelProfileEntry.model_validate(profile)
    assert entry.source_kind == "checkpoint_directory"
    assert resolve_profile_source_status(profile) == "ok"
