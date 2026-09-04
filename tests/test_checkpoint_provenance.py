from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

import pytest

import llmgauge.core.checkpoint_provenance as checkpoint_module
from llmgauge.core.checkpoint_provenance import (
    CHECKPOINT_MANIFEST_SCHEMA_VERSION,
    CHECKPOINT_PROVENANCE_KIND,
    checkpoint_manifest_fingerprint,
    checkpoint_tokenizer_identity_fingerprint,
    collect_checkpoint_provenance,
)

CONFIG = b'{"architectures": ["TinyForCausalLM"], "model_type": "tiny"}'
TOKENIZER = b'{"tokenizer": "tiny"}'
TOKENIZER_CONFIG = b'{"chat_template": "hello {{ message }}"}'


def _write_checkpoint(
    root: Path,
    *,
    config: bytes | None = CONFIG,
    weights: dict[str, bytes] | None = None,
    index: dict[str, Any] | None = None,
    tokenizer: bytes | None = TOKENIZER,
    tokenizer_config: bytes | None = TOKENIZER_CONFIG,
    extra: dict[str, bytes] | None = None,
) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    if config is not None:
        (root / "config.json").write_bytes(config)
    if weights is None:
        weights = {"model.safetensors": b"weights-bytes"}
    for name, data in weights.items():
        (root / name).write_bytes(data)
    if index is not None:
        (root / "model.safetensors.index.json").write_text(
            json.dumps(index), encoding="utf-8"
        )
    if tokenizer is not None:
        (root / "tokenizer.json").write_bytes(tokenizer)
    if tokenizer_config is not None:
        (root / "tokenizer_config.json").write_bytes(tokenizer_config)
    for name, data in (extra or {}).items():
        (root / name).write_bytes(data)
    return root


def _collect(root: Path, cache: Path) -> dict[str, Any]:
    return collect_checkpoint_provenance(
        root, source_type="model_profile", cache_path=cache
    )


def _paths(record: dict[str, Any]) -> list[str]:
    return [entry["path"] for entry in record["manifest"]]


# --- canonical selection ---------------------------------------------------


def test_minimal_non_indexed_checkpoint_is_available(tmp_path: Path) -> None:
    root = _write_checkpoint(tmp_path / "ckpt")
    record = _collect(root, tmp_path / "cache.json")

    assert record["status"] == "available"
    assert record["provenance_kind"] == CHECKPOINT_PROVENANCE_KIND
    assert record["manifest_schema"] == CHECKPOINT_MANIFEST_SCHEMA_VERSION
    assert _paths(record) == [
        "config.json",
        "model.safetensors",
        "tokenizer.json",
        "tokenizer_config.json",
    ]
    assert record["fingerprint_eligible"] is True
    assert record["weight_file_count"] == 1


def test_indexed_checkpoint_selects_only_referenced_shards(tmp_path: Path) -> None:
    root = _write_checkpoint(
        tmp_path / "ckpt",
        weights={
            "model-00001-of-00002.safetensors": b"A",
            "model-00002-of-00002.safetensors": b"B",
            "model-00003-unrelated.safetensors": b"C",
        },
        index={
            "metadata": {"total_size": 2},
            "weight_map": {
                "layer.0": "model-00001-of-00002.safetensors",
                "layer.1": "model-00002-of-00002.safetensors",
            },
        },
        tokenizer=None,
        tokenizer_config=None,
    )
    record = _collect(root, tmp_path / "cache.json")

    assert record["status"] == "partial"  # no tokenizer/template
    assert "model-00003-unrelated.safetensors" not in _paths(record)
    assert _paths(record) == [
        "config.json",
        "model-00001-of-00002.safetensors",
        "model-00002-of-00002.safetensors",
        "model.safetensors.index.json",
    ]
    assert record["weight_file_count"] == 2


def test_entries_are_sorted_unique_and_carry_path_size_sha(tmp_path: Path) -> None:
    root = _write_checkpoint(
        tmp_path / "ckpt",
        weights={"b.safetensors": b"bb", "a.safetensors": b"a"},
    )
    record = _collect(root, tmp_path / "cache.json")
    paths = _paths(record)

    assert paths == sorted(paths)
    assert len(paths) == len(set(paths))
    for entry in record["manifest"]:
        assert set(entry) == {"path", "size", "sha256"}
        assert isinstance(entry["size"], int)
        assert (
            entry["sha256"]
            == hashlib.sha256((root / entry["path"]).read_bytes()).hexdigest()
        )


def test_ordering_is_independent_of_creation_order(tmp_path: Path) -> None:
    cache = tmp_path / "cache.json"
    first = _write_checkpoint(
        tmp_path / "a",
        weights={"z.safetensors": b"z", "y.safetensors": b"y"},
    )
    second = _write_checkpoint(
        tmp_path / "b",
        weights={"y.safetensors": b"y", "z.safetensors": b"z"},
    )
    a = _collect(first, cache)
    b = _collect(second, cache)
    assert _paths(a) == _paths(b)
    assert a["manifest_sha256"] == b["manifest_sha256"]


def test_unrelated_files_do_not_affect_identity(tmp_path: Path) -> None:
    root = _write_checkpoint(tmp_path / "ckpt")
    cache = tmp_path / "cache.json"
    before = _collect(root, cache)

    (root / "README.md").write_text("documentation", encoding="utf-8")
    (root / "LICENSE").write_text("MIT", encoding="utf-8")
    (root / "trainer_state.json").write_text("{}", encoding="utf-8")
    (root / "preprocessor_config.json").write_text("{}", encoding="utf-8")
    (root / "optimizer.pt").write_bytes(b"optimizer-state")
    after = _collect(root, cache)

    assert before["manifest_sha256"] == after["manifest_sha256"]
    assert before["public_fingerprint"] == after["public_fingerprint"]


# --- unavailable states ----------------------------------------------------


def test_missing_config_is_unavailable(tmp_path: Path) -> None:
    root = tmp_path / "ckpt"
    root.mkdir()
    (root / "model.safetensors").write_bytes(b"w")
    record = _collect(root, tmp_path / "cache.json")

    assert record["status"] == "unavailable"
    assert record["manifest"] is None
    assert record["public_fingerprint"] is None
    assert record["fingerprint_eligible"] is False
    assert "config.json" in record["reason"]


def test_no_weights_is_unavailable(tmp_path: Path) -> None:
    root = _write_checkpoint(tmp_path / "ckpt", weights={})
    record = _collect(root, tmp_path / "cache.json")

    assert record["status"] == "unavailable"
    assert "safetensors" in record["reason"]


def test_nonexistent_root_is_unavailable(tmp_path: Path) -> None:
    record = _collect(tmp_path / "absent", tmp_path / "cache.json")
    assert record["status"] == "unavailable"
    assert "directory" in record["reason"]


@pytest.mark.parametrize(
    ("shard_path", "reason_fragment"),
    [
        ("/etc/passwd", "relative path"),
        ("../../etc/passwd", "invalid path component"),
        ("sub/../escape.safetensors", "invalid path component"),
        ("", "non-empty string"),
        ("missing.safetensors", "missing"),
    ],
)
def test_index_path_attacks_fail_closed(
    tmp_path: Path, shard_path: str, reason_fragment: str
) -> None:
    root = _write_checkpoint(
        tmp_path / "ckpt",
        weights={"real.safetensors": b"w"},
        index={"weight_map": {"layer.0": shard_path}},
    )
    record = _collect(root, tmp_path / "cache.json")
    assert record["status"] == "unavailable"
    assert reason_fragment in record["reason"]


def test_malformed_index_is_unavailable(tmp_path: Path) -> None:
    root = _write_checkpoint(
        tmp_path / "ckpt",
        weights={"real.safetensors": b"w"},
    )
    (root / "model.safetensors.index.json").write_text("{not json", encoding="utf-8")
    record = _collect(root, tmp_path / "cache.json")
    assert record["status"] == "unavailable"
    assert "index" in record["reason"]


def test_index_without_weight_map_is_unavailable(tmp_path: Path) -> None:
    root = _write_checkpoint(
        tmp_path / "ckpt",
        weights={"real.safetensors": b"w"},
    )
    (root / "model.safetensors.index.json").write_text('{"foo": 1}', encoding="utf-8")
    record = _collect(root, tmp_path / "cache.json")
    assert record["status"] == "unavailable"
    assert "weight_map" in record["reason"]


def test_malformed_config_is_unavailable(tmp_path: Path) -> None:
    root = _write_checkpoint(tmp_path / "ckpt", config=b"{broken")
    record = _collect(root, tmp_path / "cache.json")
    assert record["status"] == "unavailable"
    assert "config.json" in record["reason"]


# --- fingerprint determinism ----------------------------------------------


def test_manifest_fingerprint_recomputes_from_entries(tmp_path: Path) -> None:
    root = _write_checkpoint(tmp_path / "ckpt")
    record = _collect(root, tmp_path / "cache.json")

    assert record["manifest_sha256"] == checkpoint_manifest_fingerprint(
        record["manifest"]
    )
    assert record["public_fingerprint"] == "sha256:" + record["manifest_sha256"][:16]
    assert len(record["manifest_sha256"]) == 64


def test_weight_change_changes_fingerprint(tmp_path: Path) -> None:
    root = _write_checkpoint(tmp_path / "ckpt")
    cache = tmp_path / "cache.json"
    before = _collect(root, cache)

    (root / "model.safetensors").write_bytes(b"changed-weights")
    after = _collect(root, cache)
    assert before["manifest_sha256"] != after["manifest_sha256"]


def test_config_change_changes_fingerprint(tmp_path: Path) -> None:
    root = _write_checkpoint(tmp_path / "ckpt")
    cache = tmp_path / "cache.json"
    before = _collect(root, cache)

    (root / "config.json").write_bytes(b'{"model_type": "other"}')
    after = _collect(root, cache)
    assert before["manifest_sha256"] != after["manifest_sha256"]


# --- tokenizer identity ----------------------------------------------------


def test_tokenizer_identity_is_deterministic_subset(tmp_path: Path) -> None:
    root = _write_checkpoint(tmp_path / "ckpt")
    record = _collect(root, tmp_path / "cache.json")

    identity = record["tokenizer_identity"]
    assert identity["status"] == "available"
    assert identity["files"] == ["tokenizer.json", "tokenizer_config.json"]
    by_path = {entry["path"]: entry for entry in record["manifest"]}
    selected = [by_path[name] for name in identity["files"]]
    assert identity["sha256"] == checkpoint_tokenizer_identity_fingerprint(selected)
    assert identity["public_fingerprint"] == "sha256:" + identity["sha256"][:16]


def test_no_tokenizer_is_partial(tmp_path: Path) -> None:
    root = _write_checkpoint(tmp_path / "ckpt", tokenizer=None, tokenizer_config=None)
    record = _collect(root, tmp_path / "cache.json")

    assert record["status"] == "partial"
    assert record["tokenizer_identity"]["status"] == "unavailable"
    assert record["fingerprint_eligible"] is False
    assert "tokenizer" in record["fingerprint_ineligible_reason"]


# --- chat-template identity ------------------------------------------------


def test_standalone_jinja_template_hashes_exact_bytes(tmp_path) -> None:
    template = "\u003c|im_start|\u003e{{ messages }}"
    root = _write_checkpoint(
        tmp_path / "ckpt", extra={"chat_template.jinja": template.encode("utf-8")}
    )
    record = _collect(root, tmp_path / "cache.json")

    identity = record["chat_template_identity"]
    assert identity["status"] == "available"
    assert identity["source"] == "chat_template.jinja"
    assert identity["selection_method"] == "standalone_file_bytes"
    assert identity["sha256"] == hashlib.sha256(template.encode("utf-8")).hexdigest()
    assert identity["public_fingerprint"] == "sha256:" + identity["sha256"][:16]


def test_embedded_single_string_template_is_deterministic(tmp_path) -> None:
    root = _write_checkpoint(tmp_path / "ckpt")
    record = _collect(root, tmp_path / "cache.json")

    identity = record["chat_template_identity"]
    assert identity["status"] == "available"
    assert identity["source"] == "tokenizer_config.json"
    assert identity["selection_method"] == "embedded_string"
    assert identity["encoding"] == "utf-8-exact-string"
    # The template string is hashed, not the whole tokenizer_config.json file.
    assert identity["sha256"] != hashlib.sha256(TOKENIZER_CONFIG).hexdigest()
    assert (
        identity["sha256"]
        == hashlib.sha256(
            json.loads(TOKENIZER_CONFIG)["chat_template"].encode("utf-8")
        ).hexdigest()
    )


def test_multiple_named_templates_are_partial_never_guessed(tmp_path) -> None:
    root = _write_checkpoint(
        tmp_path / "ckpt",
        tokenizer_config=json.dumps(
            {"chat_template": {"default": "a", "tool_use": "b"}}
        ).encode("utf-8"),
    )
    record = _collect(root, tmp_path / "cache.json")

    identity = record["chat_template_identity"]
    assert identity["status"] == "partial"
    assert identity["selection_method"] == "ambiguous"
    assert identity["sha256"] is None
    assert record["status"] == "partial"
    assert record["fingerprint_eligible"] is False


def test_template_config_without_template_is_partial(tmp_path) -> None:
    root = _write_checkpoint(
        tmp_path / "ckpt", tokenizer_config=b'{"no_template": true}'
    )
    record = _collect(root, tmp_path / "cache.json")
    assert record["chat_template_identity"]["status"] == "partial"
    assert record["chat_template_identity"]["sha256"] is None


def test_two_standalone_templates_are_ambiguous(tmp_path) -> None:
    root = _write_checkpoint(
        tmp_path / "ckpt",
        extra={
            "chat_template.jinja": b"one",
            "chat_template.json": b'{"chat_template": "two"}',
        },
    )
    record = _collect(root, tmp_path / "cache.json")
    identity = record["chat_template_identity"]
    assert identity["status"] == "partial"
    assert identity["selection_method"] == "ambiguous"
    # Both files remain part of the canonical manifest identity.
    assert "chat_template.jinja" in _paths(record)
    assert "chat_template.json" in _paths(record)


def test_json_container_template_hashes_string_not_container(tmp_path) -> None:
    payload = b'{"chat_template": "shared string"}'
    root = _write_checkpoint(
        tmp_path / "ckpt",
        tokenizer_config=b'{"other": 1}',
        extra={"chat_template.json": payload},
    )
    record = _collect(root, tmp_path / "cache.json")
    identity = record["chat_template_identity"]
    assert identity["status"] == "available"
    assert identity["selection_method"] == "json_field_string"
    assert identity["sha256"] == hashlib.sha256(b"shared string").hexdigest()


# --- quantization declaration ----------------------------------------------


def test_config_declared_quantization_is_captured(tmp_path) -> None:
    config = json.dumps(
        {
            "architectures": ["TinyForCausalLM"],
            "quantization_config": {"quant_method": "AWQ", "bits": 4},
        }
    ).encode("utf-8")
    root = _write_checkpoint(tmp_path / "ckpt", config=config)
    record = _collect(root, tmp_path / "cache.json")

    quantization = record["checkpoint_quantization"]
    assert quantization["status"] == "declared"
    assert quantization["method"] == "awq"
    assert quantization["sources"] == [
        {
            "file": "config.json",
            "field": "quantization_config.quant_method",
            "value": "awq",
        }
    ]
    assert record["status"] == "available"


def test_quantization_sidecar_is_admitted_and_hashed(tmp_path) -> None:
    root = _write_checkpoint(
        tmp_path / "ckpt",
        extra={"quantize_config.json": b'{"quant_method": "gptq", "bits": 4}'},
    )
    record = _collect(root, tmp_path / "cache.json")

    assert "quantize_config.json" in _paths(record)
    quantization = record["checkpoint_quantization"]
    assert quantization["status"] == "declared"
    assert quantization["method"] == "gptq"
    assert quantization["sources"][0]["file"] == "quantize_config.json"


def test_conflicting_quantization_declarations_are_partial(tmp_path) -> None:
    config = json.dumps({"quantization_config": {"quant_method": "awq"}}).encode(
        "utf-8"
    )
    root = _write_checkpoint(
        tmp_path / "ckpt",
        config=config,
        extra={"quantize_config.json": b'{"quant_method": "gptq"}'},
    )
    record = _collect(root, tmp_path / "cache.json")

    quantization = record["checkpoint_quantization"]
    assert quantization["status"] == "conflict"
    assert quantization["method"] is None
    assert len(quantization["sources"]) == 2
    assert record["status"] == "partial"
    assert record["fingerprint_eligible"] is False
    assert "disagree" in record["fingerprint_ineligible_reason"]


def test_unquantized_model_is_not_partial_for_missing_quant(tmp_path) -> None:
    root = _write_checkpoint(tmp_path / "ckpt")
    record = _collect(root, tmp_path / "cache.json")

    assert record["checkpoint_quantization"]["status"] == "absent"
    assert record["status"] == "available"
    assert record["fingerprint_eligible"] is True


def test_effective_quantization_is_always_unavailable(tmp_path) -> None:
    root = _write_checkpoint(tmp_path / "ckpt")
    record = _collect(root, tmp_path / "cache.json")
    assert record["effective_quantization"]["status"] == "unavailable"


def test_dtype_alone_never_declares_quantization(tmp_path) -> None:
    config = json.dumps({"torch_dtype": "fp8", "model_type": "tiny"}).encode("utf-8")
    root = _write_checkpoint(tmp_path / "ckpt", config=config)
    record = _collect(root, tmp_path / "cache.json")
    assert record["checkpoint_quantization"]["status"] == "absent"


# --- cache behavior ---------------------------------------------------------


def _cache_weight_entry(cache: Path, name: str = "model.safetensors") -> dict:
    data = json.loads(cache.read_text(encoding="utf-8"))
    for key, entry in data["entries"].items():
        if key.endswith(name):
            return entry
    raise AssertionError(f"no cache entry for {name}")


def _count_file_hash_calls(monkeypatch) -> list[int]:
    """Count no-argument hashlib.sha256() calls (per-file streaming hashes).

    Canonical-JSON fingerprinting calls sha256(data) with positional bytes;
    file hashing calls sha256() with no arguments.
    """

    counts = [0]
    original = checkpoint_module.hashlib.sha256

    def counted(*args, **kwargs):
        if not args and not kwargs:
            counts[0] += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(checkpoint_module.hashlib, "sha256", counted)
    return counts


def test_unchanged_files_reuse_cache(tmp_path, monkeypatch) -> None:
    root = _write_checkpoint(tmp_path / "ckpt")
    cache = tmp_path / "cache.json"
    _collect(root, cache)
    first_entry = _cache_weight_entry(cache)

    counts = _count_file_hash_calls(monkeypatch)
    second = _collect(root, cache)
    # Only the parsed-metadata files (config.json, tokenizer_config.json) are
    # re-read; the weight and tokenizer.json entries are cache hits.
    assert counts[0] == 2
    weight = next(
        entry for entry in second["manifest"] if entry["path"] == "model.safetensors"
    )
    assert weight["sha256"] == first_entry["sha256"]


def test_regular_file_change_invalidates_cache(tmp_path, monkeypatch) -> None:
    root = _write_checkpoint(tmp_path / "ckpt")
    cache = tmp_path / "cache.json"
    before = _collect(root, cache)

    # Same size, different content, forced mtime change: size-only validation
    # would wrongly hit the cache.
    (root / "model.safetensors").write_bytes(b"XXXXXXXXXXXXX")
    os.utime(root / "model.safetensors", ns=(0, 0))
    counts = _count_file_hash_calls(monkeypatch)
    after = _collect(root, cache)
    # config.json + tokenizer_config.json (parsed) + model.safetensors (rehash).
    assert counts[0] == 3
    assert before["manifest_sha256"] != after["manifest_sha256"]
    weight = next(
        entry for entry in after["manifest"] if entry["path"] == "model.safetensors"
    )
    assert weight["sha256"] == hashlib.sha256(b"XXXXXXXXXXXXX").hexdigest()


def test_malformed_cache_is_ignored(tmp_path) -> None:
    root = _write_checkpoint(tmp_path / "ckpt")
    cache = tmp_path / "cache.json"
    _collect(root, cache)
    cache.write_text("not json at all", encoding="utf-8")
    record = _collect(root, cache)
    assert record["status"] == "available"

    cache.write_text(json.dumps({"schema_version": "bogus", "entries": {}}), "utf-8")
    record = _collect(root, cache)
    assert record["status"] == "available"

    cache.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    record = _collect(root, cache)
    assert record["status"] == "available"


def test_corrupt_cache_entry_forces_rehash(tmp_path) -> None:
    root = _write_checkpoint(tmp_path / "ckpt")
    cache = tmp_path / "cache.json"
    _collect(root, cache)
    data = json.loads(cache.read_text(encoding="utf-8"))
    for key in data["entries"]:
        if key.endswith("model.safetensors"):
            data["entries"][key]["sha256"] = "z" * 64
    cache.write_text(json.dumps(data), encoding="utf-8")

    record = _collect(root, cache)
    weight_entry = next(
        entry for entry in record["manifest"] if entry["path"] == "model.safetensors"
    )
    assert weight_entry["sha256"] == hashlib.sha256(b"weights-bytes").hexdigest()


def test_cache_write_failure_keeps_provenance_valid(tmp_path, monkeypatch) -> None:
    root = _write_checkpoint(tmp_path / "ckpt")
    cache = tmp_path / "cache.json"

    def refuse(*args, **kwargs):
        raise OSError("cache filesystem is read-only")

    monkeypatch.setattr(checkpoint_module, "_write_checkpoint_cache", refuse)
    record = _collect(root, cache)
    assert record["status"] == "available"
    assert record["fingerprint_eligible"] is True
    assert not cache.exists()


def test_cache_never_stores_manifest_identity(tmp_path) -> None:
    root = _write_checkpoint(tmp_path / "ckpt")
    cache = tmp_path / "cache.json"
    _collect(root, cache)
    data = json.loads(cache.read_text(encoding="utf-8"))
    assert data["schema_version"] == "llmgauge.checkpoint_hash_cache.v0"
    for entry in data["entries"].values():
        # Cache entries are private acceleration state, not portable identity.
        assert "mtime_ns" in entry and "inode" in entry


# --- symlink semantics ------------------------------------------------------


def _symlinked_checkpoint(tmp_path: Path) -> tuple[Path, Path]:
    blobs = tmp_path / "blobs"
    blobs.mkdir()
    root = tmp_path / "snapshot"
    root.mkdir()
    files = {
        "config.json": CONFIG,
        "model.safetensors": b"weights-bytes",
        "tokenizer.json": TOKENIZER,
        "tokenizer_config.json": TOKENIZER_CONFIG,
    }
    for name, data in files.items():
        blob = blobs / hashlib.sha1(name.encode("utf-8")).hexdigest()
        blob.write_bytes(data)
        (root / name).symlink_to(os.path.relpath(blob, root))
    return root, blobs


def test_symlink_backed_checkpoint_is_supported(tmp_path) -> None:
    root, _ = _symlinked_checkpoint(tmp_path)
    record = _collect(root, tmp_path / "cache.json")

    assert record["status"] == "available"
    assert _paths(record) == [
        "config.json",
        "model.safetensors",
        "tokenizer.json",
        "tokenizer_config.json",
    ]
    entry = next(e for e in record["manifest"] if e["path"] == "model.safetensors")
    assert entry["size"] == len(b"weights-bytes")
    assert entry["sha256"] == hashlib.sha256(b"weights-bytes").hexdigest()
    # The logical path is recorded; the resolved blob path is not identity.
    assert "blobs" not in json.dumps(record["manifest"])


def test_symlink_retarget_invalidates_cache(tmp_path, monkeypatch) -> None:
    root, blobs = _symlinked_checkpoint(tmp_path)
    cache = tmp_path / "cache.json"
    before = _collect(root, cache)
    first_entry = _cache_weight_entry(cache)

    link = root / "model.safetensors"
    new_blob = blobs / "retargeted"
    new_blob.write_bytes(b"weights-bytes")  # identical content, new link identity
    link.unlink()
    link.symlink_to(os.path.relpath(new_blob, root))

    counts = _count_file_hash_calls(monkeypatch)
    after = _collect(root, cache)
    reused_entry = _cache_weight_entry(cache)
    # The link identity changed, so the cache must reject the stale entry and
    # rehash; the content digest (and therefore manifest identity) legitimately
    # stays equal because the target bytes are identical.
    assert reused_entry["link_target"] != first_entry["link_target"]
    assert counts[0] == 3  # parsed config/tokenizer_config + retargeted weight
    assert after["manifest_sha256"] == before["manifest_sha256"]


def test_symlink_target_content_change_invalidates_cache(tmp_path) -> None:
    root, blobs = _symlinked_checkpoint(tmp_path)
    cache = tmp_path / "cache.json"
    before = _collect(root, cache)

    target = (root / "model.safetensors").resolve()
    target.write_bytes(b"mutated-target-content")
    after = _collect(root, cache)
    assert after["manifest_sha256"] != before["manifest_sha256"]


def test_broken_symlink_fails_closed(tmp_path) -> None:
    root, blobs = _symlinked_checkpoint(tmp_path)
    (root / "tokenizer.json").unlink()
    (root / "tokenizer.json").symlink_to(blobs / "never-written")
    record = _collect(root, tmp_path / "cache.json")
    assert record["status"] == "unavailable"
    assert "broken" in record["reason"] or "invalid" in record["reason"]


def test_symlink_to_directory_fails_closed(tmp_path) -> None:
    root, _ = _symlinked_checkpoint(tmp_path)
    directory = tmp_path / "not-a-file"
    directory.mkdir()
    (root / "model.safetensors").unlink()
    (root / "model.safetensors").symlink_to(directory)
    record = _collect(root, tmp_path / "cache.json")
    assert record["status"] == "unavailable"
    assert "regular file" in record["reason"]


def test_symlink_loop_fails_closed(tmp_path) -> None:
    root, _ = _symlinked_checkpoint(tmp_path)
    link = root / "model.safetensors"
    link.unlink()
    link.symlink_to(root / "loop-a")
    (root / "loop-a").symlink_to(link)
    record = _collect(root, tmp_path / "cache.json")
    assert record["status"] == "unavailable"


# --- mutation during collection ---------------------------------------------


def test_file_change_during_hashing_fails_closed(tmp_path, monkeypatch) -> None:
    root = _write_checkpoint(tmp_path / "ckpt")
    cache = tmp_path / "cache.json"

    original_snapshot = checkpoint_module._identity_snapshot
    state = {"seen": 0}

    def mutating_snapshot(path: Path):
        if path.name == "model.safetensors":
            state["seen"] += 1
            # Snapshot order for the weight file: (1) selection probe,
            # (2) pre-hash, (3) post-hash. Mutate just before the post-hash
            # snapshot so the pre/post identities diverge.
            if state["seen"] == 3:
                path.write_bytes(b"mutated-mid-hash!!")
        return original_snapshot(path)

    monkeypatch.setattr(checkpoint_module, "_identity_snapshot", mutating_snapshot)
    record = _collect(root, cache)
    assert record["status"] == "unavailable"
    assert "changed" in record["reason"]


def test_index_change_during_collection_fails_closed(tmp_path, monkeypatch) -> None:
    root = _write_checkpoint(
        tmp_path / "ckpt",
        weights={"a.safetensors": b"A", "b.safetensors": b"B"},
        index={"weight_map": {"t0": "a.safetensors", "t1": "b.safetensors"}},
    )
    cache = tmp_path / "cache.json"

    original_snapshot = checkpoint_module._identity_snapshot
    state = {"tripped": False}

    def mutating_snapshot(path: Path):
        snapshot = original_snapshot(path)
        if (
            path.name == "model.safetensors.index.json"
            and not state["tripped"]
            and snapshot.get("size", 0) > 0
            and path.exists()
        ):
            # Trip once, late in collection: rewrite the index to drop a shard.
            state["tripped"] = True
            path.write_text(
                json.dumps({"weight_map": {"t0": "a.safetensors"}}), encoding="utf-8"
            )
        return snapshot

    monkeypatch.setattr(checkpoint_module, "_identity_snapshot", mutating_snapshot)
    record = _collect(root, cache)
    assert record["status"] == "unavailable"
    assert (
        "index" in record["reason"]
        or "selection" in record["reason"]
        or "changed" in record["reason"]
    )


# --- repository/revision identity -------------------------------------------


def test_hf_cache_layout_derives_repo_and_revision(tmp_path) -> None:
    revision = "c" * 40
    root = _write_checkpoint(
        tmp_path / "hub" / "models--TinyOrg--TinyModel" / "snapshots" / revision
    )
    record = _collect(root, tmp_path / "cache.json")
    assert record["repository_id"] == "TinyOrg/TinyModel"
    assert record["revision"] == revision
    assert record["repository_id_source"] == "hf_cache_snapshot_layout"
    assert str(tmp_path) not in json.dumps(record)


def test_arbitrary_directory_has_no_repo_identity(tmp_path) -> None:
    root = _write_checkpoint(tmp_path / "my-models" / "whatever")
    record = _collect(root, tmp_path / "cache.json")
    assert record["repository_id"] is None
    assert record["revision"] is None
    assert record["repository_id_source"] == "unknown"


def test_mutable_name_or_path_is_never_identity(tmp_path) -> None:
    config = json.dumps(
        {
            "_name_or_path": "/home/someone/private-copy",
            "model_type": "tiny",
        }
    ).encode("utf-8")
    root = _write_checkpoint(tmp_path / "ckpt", config=config)
    record = _collect(root, tmp_path / "cache.json")
    assert record["repository_id"] is None
    assert "/home/" not in json.dumps(record)


# --- architecture metadata ---------------------------------------------------


def test_architecture_from_explicit_fields(tmp_path) -> None:
    root = _write_checkpoint(tmp_path / "ckpt")
    record = _collect(root, tmp_path / "cache.json")
    assert record["architecture"] == "TinyForCausalLM"
    assert record["model_type"] == "tiny"


def test_ambiguous_architecture_is_unknown(tmp_path) -> None:
    config = json.dumps({"architectures": ["A", "B"]}).encode("utf-8")
    root = _write_checkpoint(tmp_path / "ckpt", config=config)
    record = _collect(root, tmp_path / "cache.json")
    assert record["architecture"] is None
    assert record["status"] == "available"  # descriptive metadata only


# --- privacy of the record ----------------------------------------------------


def test_record_never_persists_absolute_root(tmp_path) -> None:
    root = _write_checkpoint(tmp_path / "ckpt")
    record = _collect(root, tmp_path / "cache.json")
    serialized = json.dumps(record)
    assert str(tmp_path) not in serialized
    assert "/home/" not in serialized or "private" not in serialized


def test_auto_map_dependency_outside_allowlist_is_partial(tmp_path) -> None:
    config = json.dumps(
        {
            "architectures": ["CustomForCausalLM"],
            "auto_map": {"AutoModelForCausalLM": "modeling_custom.CustomModel"},
        }
    ).encode("utf-8")
    root = _write_checkpoint(tmp_path / "ckpt", config=config)
    record = _collect(root, tmp_path / "cache.json")

    # The manifest stays canonical (no ad hoc expansion of custom .py files),
    # but identity is knowingly incomplete: partial + ineligible.
    assert record["status"] == "partial"
    assert record["fingerprint_eligible"] is False
    assert "allowlist" in record["fingerprint_ineligible_reason"]
    assert not any(path.endswith(".py") for path in _paths(record))
