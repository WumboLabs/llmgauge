import hashlib
import json
from pathlib import Path

import llmgauge.core.identity as identity


def test_hash_model_file_is_deterministic_and_cached(tmp_path: Path, monkeypatch) -> None:
    model_path = tmp_path / "model.bin"
    model_path.write_bytes(b"small test model")
    cache_path = tmp_path / "cache.json"
    expected_digest = hashlib.sha256(b"small test model").hexdigest()
    original_sha256 = identity.hashlib.sha256
    calls = 0

    def counted_sha256(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original_sha256(*args, **kwargs)

    monkeypatch.setattr(identity.hashlib, "sha256", counted_sha256)

    first = identity.hash_model_file(model_path, cache_path=cache_path)
    second = identity.hash_model_file(model_path, cache_path=cache_path)

    assert first == (len(b"small test model"), expected_digest)
    assert second == first
    assert calls == 1


def test_hash_model_file_invalidates_after_file_change(tmp_path: Path) -> None:
    model_path = tmp_path / "model.bin"
    cache_path = tmp_path / "cache.json"
    model_path.write_bytes(b"first")
    first = identity.hash_model_file(model_path, cache_path=cache_path)

    model_path.write_bytes(b"second content")
    second = identity.hash_model_file(model_path, cache_path=cache_path)

    assert first[1] != second[1]
    assert second[0] == len(b"second content")


def test_hash_model_file_force_rehash_bypasses_cache(
    tmp_path: Path, monkeypatch
) -> None:
    model_path = tmp_path / "model.bin"
    cache_path = tmp_path / "cache.json"
    model_path.write_bytes(b"content")
    identity.hash_model_file(model_path, cache_path=cache_path)
    original_sha256 = identity.hashlib.sha256
    calls = 0

    def counted_sha256(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original_sha256(*args, **kwargs)

    monkeypatch.setattr(identity.hashlib, "sha256", counted_sha256)
    identity.hash_model_file(model_path, cache_path=cache_path, force_rehash=True)

    assert calls == 1


def test_corrupt_cache_is_recovered(tmp_path: Path) -> None:
    model_path = tmp_path / "model.bin"
    cache_path = tmp_path / "cache.json"
    model_path.write_bytes(b"content")
    cache_path.write_text("not json", encoding="utf-8")

    size, digest = identity.hash_model_file(model_path, cache_path=cache_path)

    assert size == len(b"content")
    assert digest == hashlib.sha256(b"content").hexdigest()
    assert json.loads(cache_path.read_text(encoding="utf-8"))["entries"]


def test_cache_replacement_is_atomic(tmp_path: Path, monkeypatch) -> None:
    model_path = tmp_path / "model.bin"
    cache_path = tmp_path / "cache.json"
    model_path.write_bytes(b"content")
    replacements: list[tuple[Path, Path]] = []
    original_replace = identity.os.replace

    def record_replace(source, destination):
        replacements.append((Path(source), Path(destination)))
        return original_replace(source, destination)

    monkeypatch.setattr(identity.os, "replace", record_replace)
    identity.hash_model_file(model_path, cache_path=cache_path)

    assert replacements
    assert replacements[0][1] == cache_path
    assert not replacements[0][0].exists()


def test_public_fingerprint_is_stable_and_excludes_model_path(tmp_path: Path) -> None:
    digest = hashlib.sha256(b"content").hexdigest()
    first = identity.collect_model_provenance(
        tmp_path / "model.bin",
        source_type="direct_model_path",
    )
    (tmp_path / "model.bin").write_bytes(b"content")
    second = identity.collect_model_provenance(
        tmp_path / "model.bin",
        source_type="direct_model_path",
        cache_path=tmp_path / "cache.json",
    )

    assert first["status"] == "unavailable"
    assert second["public_fingerprint"] == identity.public_model_fingerprint(digest)
    assert str(tmp_path) not in second["public_fingerprint"]


def test_model_provenance_has_explicit_unavailable_state(tmp_path: Path) -> None:
    provenance = identity.collect_model_provenance(
        tmp_path / "missing.bin",
        source_type="model_profile",
    )

    assert provenance["status"] == "unavailable"
    assert provenance["sha256"] is None
    assert provenance["warning"].startswith("Model provenance unavailable:")


def test_backend_provenance_hashes_executable_with_shared_cache(tmp_path: Path) -> None:
    model_path = tmp_path / "model.bin"
    executable_path = tmp_path / "llama-cli"
    cache_path = tmp_path / "cache.json"
    model_path.write_bytes(b"model")
    executable_path.write_bytes(b"executable")

    model_size, model_digest = identity.hash_model_file(
        model_path, cache_path=cache_path
    )
    backend = identity.collect_backend_provenance(
        executable_path, cache_path=cache_path
    )

    assert model_size == 5
    assert model_digest == hashlib.sha256(b"model").hexdigest()
    assert backend["status"] == "available"
    assert backend["backend_name"] == "llama.cpp"
    assert backend["executable_filename"] == "llama-cli"
    assert backend["executable_file_size_bytes"] == len(b"executable")
    assert backend["executable_sha256"] == hashlib.sha256(b"executable").hexdigest()


def test_backend_provenance_cache_hit_and_invalidation(
    tmp_path: Path, monkeypatch
) -> None:
    executable_path = tmp_path / "llama-cli"
    cache_path = tmp_path / "cache.json"
    executable_path.write_bytes(b"first")
    original_sha256 = identity.hashlib.sha256
    calls = 0

    def counted_sha256(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original_sha256(*args, **kwargs)

    monkeypatch.setattr(identity.hashlib, "sha256", counted_sha256)

    first = identity.collect_backend_provenance(
        executable_path, cache_path=cache_path
    )
    second = identity.collect_backend_provenance(
        executable_path, cache_path=cache_path
    )
    executable_path.write_bytes(b"second executable")
    changed = identity.collect_backend_provenance(
        executable_path, cache_path=cache_path
    )

    assert second["executable_sha256"] == first["executable_sha256"]
    assert changed["executable_sha256"] != first["executable_sha256"]
    assert calls == 2


def test_backend_public_fingerprint_is_deterministic_and_path_free(
    tmp_path: Path,
) -> None:
    executable_path = tmp_path / "private" / "llama-cli"
    executable_path.parent.mkdir()
    executable_path.write_bytes(b"executable")

    first = identity.collect_backend_provenance(
        executable_path, cache_path=tmp_path / "one.json"
    )
    second = identity.collect_backend_provenance(
        executable_path, cache_path=tmp_path / "two.json"
    )

    assert first["public_executable_fingerprint"] == second[
        "public_executable_fingerprint"
    ]
    assert str(tmp_path) not in first["public_executable_fingerprint"]


def test_backend_provenance_reports_identity_change_during_hash(
    tmp_path: Path, monkeypatch
) -> None:
    executable_path = tmp_path / "llama-cli"
    executable_path.write_bytes(b"executable")
    original_file_identity = identity._file_identity
    initial_identity = original_file_identity(executable_path)
    changed_identity = {**initial_identity, "mtime_ns": initial_identity["mtime_ns"] + 1}
    calls = 0

    def changing_file_identity(path: Path) -> dict[str, object]:
        nonlocal calls
        calls += 1
        return initial_identity if calls == 1 else changed_identity

    monkeypatch.setattr(identity, "_file_identity", changing_file_identity)
    provenance = identity.collect_backend_provenance(
        executable_path, cache_path=tmp_path / "cache.json"
    )

    assert provenance["status"] == "unavailable"
    assert "changed while it was being hashed" in provenance["warning"]


def test_backend_provenance_reports_missing_executable(tmp_path: Path) -> None:
    provenance = identity.collect_backend_provenance(
        tmp_path / "missing-llama-cli",
        cache_path=tmp_path / "cache.json",
    )

    assert provenance["status"] == "unavailable"
    assert provenance["executable_filename"] == "missing-llama-cli"
    assert provenance["executable_sha256"] is None
    assert provenance["warning"].startswith("Executable provenance unavailable:")


def test_hash_model_file_rejects_file_identity_change_during_hash(
    tmp_path: Path, monkeypatch
) -> None:
    model_path = tmp_path / "model.bin"
    cache_path = tmp_path / "cache.json"
    model_path.write_bytes(b"content")

    original_file_identity = identity._file_identity
    initial_identity = original_file_identity(model_path)
    changed_identity = {**initial_identity, "mtime_ns": initial_identity["mtime_ns"] + 1}
    calls = 0

    def changing_file_identity(path: Path) -> dict[str, object]:
        nonlocal calls
        calls += 1
        return initial_identity if calls == 1 else changed_identity

    monkeypatch.setattr(identity, "_file_identity", changing_file_identity)

    try:
        identity.hash_model_file(model_path, cache_path=cache_path)
    except OSError as exc:
        assert str(exc) == "model file changed while it was being hashed"
    else:
        raise AssertionError("expected file identity change to reject the hash")

    assert not cache_path.exists()
