from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

CANONICAL_JSON_VERSION = "llmgauge.canonical_json.v0"
PROMPT_IDENTITY_VERSION = "llmgauge.prompt_identity.v0"
SUITE_IDENTITY_VERSION = "llmgauge.suite_identity.v0"
MODEL_HASH_CACHE_VERSION = "llmgauge.model_hash_cache.v0"
PUBLIC_FINGERPRINT_LENGTH = 16

_JSON_SCALAR_TYPES = (str, int, float, bool, type(None))


def _canonical_json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        normalized: dict[str, Any] = {}
        for key, child in value.items():
            if not isinstance(key, str):
                raise TypeError("canonical JSON mappings must use string keys")
            normalized[key] = _canonical_json_value(child)
        return normalized

    if isinstance(value, tuple):
        return [_canonical_json_value(child) for child in value]

    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [_canonical_json_value(child) for child in value]

    if isinstance(value, _JSON_SCALAR_TYPES):
        return value

    raise TypeError(f"unsupported canonical JSON value: {type(value).__name__}")


def canonical_json_bytes(value: Any) -> bytes:
    """Serialize evaluation identity payloads to deterministic JSON bytes."""

    normalized = _canonical_json_value(value)
    return json.dumps(
        normalized,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def model_hash_cache_path() -> Path:
    """Return the user-owned cache path for local model hashes."""

    cache_home = os.environ.get("XDG_CACHE_HOME")
    root = Path(cache_home) if cache_home else Path.home() / ".cache"
    return root / "llmgauge" / "hash-cache-v0.json"


def public_model_fingerprint(sha256: str) -> str:
    """Return a deterministic display fingerprint without local path data."""

    if len(sha256) != 64 or any(
        character not in "0123456789abcdef" for character in sha256
    ):
        raise ValueError("sha256 must be a lowercase 64-character hexadecimal digest")
    return f"sha256:{sha256[:PUBLIC_FINGERPRINT_LENGTH]}"


def _file_identity(path: Path) -> dict[str, Any]:
    resolved_path = path.expanduser().resolve()
    stat_result = resolved_path.stat()
    identity: dict[str, Any] = {
        "path": str(resolved_path),
        "size": stat_result.st_size,
        "mtime_ns": stat_result.st_mtime_ns,
    }
    if hasattr(stat_result, "st_dev"):
        identity["device"] = stat_result.st_dev
    if hasattr(stat_result, "st_ino"):
        identity["inode"] = stat_result.st_ino
    return identity


def _load_hash_cache(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return {"schema_version": MODEL_HASH_CACHE_VERSION, "entries": {}}

    if (
        not isinstance(data, dict)
        or data.get("schema_version") != MODEL_HASH_CACHE_VERSION
        or not isinstance(data.get("entries"), dict)
    ):
        return {"schema_version": MODEL_HASH_CACHE_VERSION, "entries": {}}
    return data


def _cache_entry_matches(entry: Any, identity: dict[str, Any]) -> bool:
    if not isinstance(entry, dict) or entry.get("algorithm") != "sha256":
        return False
    for field, value in identity.items():
        if entry.get(field) != value:
            return False
    digest = entry.get("sha256")
    return isinstance(digest, str) and len(digest) == 64 and all(
        character in "0123456789abcdef" for character in digest
    )


def _write_hash_cache(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            json.dump(data, temporary, indent=2, sort_keys=True)
            temporary.write("\n")
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def hash_model_file(
    path: Path,
    *,
    cache_path: Path | None = None,
    force_rehash: bool = False,
) -> tuple[int, str]:
    """Hash a local file, using an identity-validated cache unless bypassed."""

    resolved_path = path.expanduser().resolve()
    identity = _file_identity(resolved_path)
    cache_path = cache_path or model_hash_cache_path()
    cache = _load_hash_cache(cache_path)
    entries = cache["entries"]
    cache_key = identity["path"]
    cached = entries.get(cache_key)

    if not force_rehash and _cache_entry_matches(cached, identity):
        return identity["size"], cached["sha256"]

    digest = hashlib.sha256()
    with resolved_path.open("rb") as model_file:
        for chunk in iter(lambda: model_file.read(1024 * 1024), b""):
            digest.update(chunk)

    final_identity = _file_identity(resolved_path)
    if final_identity != identity:
        raise OSError("model file changed while it was being hashed")

    sha256 = digest.hexdigest()
    entries[cache_key] = {
        **final_identity,
        "algorithm": "sha256",
        "sha256": sha256,
        "updated_at_utc": datetime.now(UTC).replace(microsecond=0).isoformat(),
    }
    try:
        _write_hash_cache(cache_path, cache)
    except OSError:
        # The full hash remains valid even when the optional cache is unavailable.
        pass
    return identity["size"], sha256


def collect_model_provenance(
    path: Path,
    *,
    source_type: str,
    cache_path: Path | None = None,
    force_rehash: bool = False,
) -> dict[str, Any]:
    """Build additive model provenance, preserving an explicit unavailable state."""

    resolved_path = path.expanduser().resolve()
    provenance: dict[str, Any] = {
        "source_type": source_type,
        "filename": resolved_path.name,
        "file_size_bytes": None,
        "sha256": None,
        "public_fingerprint": None,
    }
    try:
        file_size, sha256 = hash_model_file(
            resolved_path,
            cache_path=cache_path,
            force_rehash=force_rehash,
        )
    except (OSError, ValueError) as exc:
        provenance.update(
            {
                "status": "unavailable",
                "warning": f"Model provenance unavailable: {exc}",
            }
        )
        return provenance

    provenance.update(
        {
            "status": "available",
            "file_size_bytes": file_size,
            "sha256": sha256,
            "public_fingerprint": public_model_fingerprint(sha256),
        }
    )
    return provenance


def prompt_definition_payload(
    *,
    prompt: Mapping[str, Any],
    prompt_text: str,
    system_text: str | None = None,
    output_contract: Any = None,
    scoring_rubric: Any = None,
    evaluation_metadata: Mapping[str, Any] | None = None,
    template_instructions: Any = None,
) -> dict[str, Any]:
    """Build the evaluation-relevant prompt identity payload."""

    return {
        "schema_version": PROMPT_IDENTITY_VERSION,
        "prompt": dict(prompt),
        "prompt_text": prompt_text,
        "system_text": system_text or "",
        "output_contract": output_contract,
        "scoring_rubric": scoring_rubric,
        "evaluation_metadata": dict(evaluation_metadata or {}),
        "template_instructions": template_instructions,
    }


def prompt_definition_identity(
    *,
    prompt: Mapping[str, Any],
    prompt_text: str,
    system_text: str | None = None,
    output_contract: Any = None,
    scoring_rubric: Any = None,
    evaluation_metadata: Mapping[str, Any] | None = None,
    template_instructions: Any = None,
) -> str:
    return canonical_sha256(
        prompt_definition_payload(
            prompt=prompt,
            prompt_text=prompt_text,
            system_text=system_text,
            output_contract=output_contract,
            scoring_rubric=scoring_rubric,
            evaluation_metadata=evaluation_metadata,
            template_instructions=template_instructions,
        )
    )


def suite_definition_payload(
    *,
    suite: Mapping[str, Any],
    prompt_identities: Mapping[str, str],
) -> dict[str, Any]:
    """Build the evaluation-relevant suite identity payload."""

    return {
        "schema_version": SUITE_IDENTITY_VERSION,
        "suite": dict(suite),
        "prompt_identities": dict(prompt_identities),
    }


def suite_definition_identity(
    *,
    suite: Mapping[str, Any],
    prompt_identities: Mapping[str, str],
) -> str:
    return canonical_sha256(
        suite_definition_payload(suite=suite, prompt_identities=prompt_identities)
    )
