"""Bounded local checkpoint-directory provenance collection (M2).

Implements the accepted ``checkpoint_directory`` identity contract from
docs/FIRST_CLASS_RUNTIME_ARCHITECTURE.md §4.2 and
docs/VLLM_RUNTIME_CONTRACT.md (Directory-model provenance): a non-recursive
canonical file manifest, identity-validated per-file SHA-256 hashing with a
separate directory cache, tokenizer and chat-template identity,
checkpoint-declared quantization evidence, and an explicit run-fingerprint
eligibility decision.

Collection is local and offline only: no network access, no repository
resolution, no runtime execution. The absolute checkpoint root is never part
of portable identity; manifest entries carry normalized model-root-relative
paths, byte sizes, and full SHA-256 values.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
import tempfile
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

from llmgauge.core.identity import (
    canonical_sha256,
    public_model_fingerprint,
)

CHECKPOINT_MANIFEST_SCHEMA_VERSION = "llmgauge.checkpoint_directory_manifest.v0"
CHECKPOINT_TOKENIZER_IDENTITY_VERSION = "llmgauge.checkpoint_tokenizer_identity.v0"
CHECKPOINT_HASH_CACHE_VERSION = "llmgauge.checkpoint_hash_cache.v0"
CHECKPOINT_PROVENANCE_KIND = "checkpoint_directory_manifest"

#: Maximum byte size of a metadata file that is read and parsed during
#: selection. Larger files are rejected fail-closed as pathological.
MAX_PARSED_METADATA_BYTES = 8 * 1024 * 1024

#: Hard bound on the canonical manifest size, guarding against accidental
#: recursive selection.
MAX_MANIFEST_ENTRIES = 4096

CONFIG_FILENAME = "config.json"
GENERATION_CONFIG_FILENAME = "generation_config.json"
WEIGHTS_INDEX_FILENAME = "model.safetensors.index.json"
SAFETENSORS_SUFFIX = ".safetensors"

QUANTIZATION_SIDECAR_FILENAMES: tuple[str, ...] = (
    "quantize_config.json",
    "quantization_config.json",
    "compression_config.json",
)
TOKENIZER_FILENAMES: tuple[str, ...] = (
    "tokenizer.json",
    "tokenizer.model",
    "tokenizer_config.json",
    "special_tokens_map.json",
    "added_tokens.json",
)
STANDALONE_TEMPLATE_FILENAMES: tuple[str, ...] = (
    "chat_template.jinja",
    "chat_template.json",
)

_CHAT_TEMPLATE_EMBEDDING_FILENAME = "tokenizer_config.json"

#: Files whose bytes are parsed to drive selection or descriptive identity.
#: These are always read fresh (never served from the hash cache) so parsed
#: content and hashed bytes come from one identity-validated read.
_PARSED_METADATA_FILENAMES: frozenset[str] = frozenset(
    {
        CONFIG_FILENAME,
        WEIGHTS_INDEX_FILENAME,
        *QUANTIZATION_SIDECAR_FILENAMES,
        _CHAT_TEMPLATE_EMBEDDING_FILENAME,
        "chat_template.json",
    }
)


class CheckpointProvenanceUnavailable(Exception):
    """Internal fail-closed signal with a precise unavailable reason."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def checkpoint_hash_cache_path() -> Path:
    """Return the user-owned cache path for checkpoint-directory file hashes."""

    cache_home = os.environ.get("XDG_CACHE_HOME")
    root = Path(cache_home) if cache_home else Path.home() / ".cache"
    return root / "llmgauge" / "checkpoint-hash-cache-v0.json"


def checkpoint_manifest_payload(
    entries: list[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build the canonical fingerprint payload for ordered manifest entries."""

    return {
        "schema_version": CHECKPOINT_MANIFEST_SCHEMA_VERSION,
        "entries": [
            {
                "path": entry["path"],
                "size": entry["size"],
                "sha256": entry["sha256"],
            }
            for entry in entries
        ],
    }


def checkpoint_manifest_fingerprint(entries: list[Mapping[str, Any]]) -> str:
    """Return the full SHA-256 over the canonical manifest payload."""

    return canonical_sha256(checkpoint_manifest_payload(entries))


def checkpoint_tokenizer_identity_payload(
    entries: list[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build the canonical tokenizer-identity payload from tokenizer entries."""

    return {
        "schema_version": CHECKPOINT_TOKENIZER_IDENTITY_VERSION,
        "entries": [
            {
                "path": entry["path"],
                "size": entry["size"],
                "sha256": entry["sha256"],
            }
            for entry in entries
        ],
    }


def checkpoint_tokenizer_identity_fingerprint(entries: list[Mapping[str, Any]]) -> str:
    """Return the full SHA-256 over the canonical tokenizer-identity payload."""

    return canonical_sha256(checkpoint_tokenizer_identity_payload(entries))


# ---------------------------------------------------------------------------
# Selection path safety
# ---------------------------------------------------------------------------


def normalize_selected_relative_path(raw: Any, *, label: str) -> str:
    """Validate one index-supplied or allowlisted relative path.

    Rejects empty, absolute, drive-qualified, backslash, ``.``, ``..``, and
    otherwise malformed paths. Returns the normalized POSIX relative path.
    """

    if not isinstance(raw, str) or not raw.strip():
        raise CheckpointProvenanceUnavailable(f"{label} must be a non-empty string")
    if "\\" in raw or "\x00" in raw:
        raise CheckpointProvenanceUnavailable(f"{label} contains invalid characters")
    candidate = PurePosixPath(raw)
    if candidate.is_absolute() or (
        len(candidate.parts) > 1 and candidate.parts[1] == ":"
    ):
        raise CheckpointProvenanceUnavailable(
            f"{label} must be a relative path: {raw!r}"
        )
    parts: list[str] = []
    for part in raw.split("/"):
        if part in {"", ".", ".."}:
            raise CheckpointProvenanceUnavailable(
                f"{label} contains an invalid path component: {raw!r}"
            )
        parts.append(part)
    return "/".join(parts)


# ---------------------------------------------------------------------------
# File identity snapshots and the separate checkpoint cache
# ---------------------------------------------------------------------------


def _identity_snapshot(logical_path: Path) -> dict[str, Any]:
    """Snapshot one selected logical path for identity validation.

    Records the link's own ``lstat`` identity plus raw target when the
    selected path is a symlink, and the final target's regular-file identity.
    The snapshot is private cache-validation metadata only; it is never part
    of the canonical manifest or the portable provenance record.
    """

    try:
        link_stat = logical_path.lstat()
    except OSError as exc:
        raise CheckpointProvenanceUnavailable(
            f"selected path is missing: {logical_path.name} ({exc.strerror or exc})"
        ) from None
    snapshot: dict[str, Any] = {
        "logical_path": str(logical_path),
        "size": link_stat.st_size,
        "mtime_ns": link_stat.st_mtime_ns,
        "device": link_stat.st_dev,
        "inode": link_stat.st_ino,
    }
    if stat.S_ISLNK(link_stat.st_mode):
        try:
            snapshot["link_target"] = os.readlink(logical_path)
            final_stat = logical_path.stat()
        except OSError as exc:
            raise CheckpointProvenanceUnavailable(
                f"selected symlink is broken or invalid: {logical_path.name} "
                f"({exc.strerror or exc})"
            ) from None
        if not stat.S_ISREG(final_stat.st_mode):
            raise CheckpointProvenanceUnavailable(
                f"selected symlink does not resolve to a regular file: "
                f"{logical_path.name}"
            )
        snapshot["final_size"] = final_stat.st_size
        snapshot["final_mtime_ns"] = final_stat.st_mtime_ns
        snapshot["final_device"] = final_stat.st_dev
        snapshot["final_inode"] = final_stat.st_ino
        # The manifest size is the content size addressed by the logical path.
        snapshot["size"] = final_stat.st_size
    elif not stat.S_ISREG(link_stat.st_mode):
        raise CheckpointProvenanceUnavailable(
            f"selected path is not a regular file or symlink: {logical_path.name}"
        )
    return snapshot


def _load_checkpoint_cache(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return {"schema_version": CHECKPOINT_HASH_CACHE_VERSION, "entries": {}}

    if (
        not isinstance(data, dict)
        or data.get("schema_version") != CHECKPOINT_HASH_CACHE_VERSION
        or not isinstance(data.get("entries"), dict)
    ):
        return {"schema_version": CHECKPOINT_HASH_CACHE_VERSION, "entries": {}}
    return data


def _cache_entry_matches(entry: Any, snapshot: Mapping[str, Any]) -> bool:
    if not isinstance(entry, dict) or entry.get("algorithm") != "sha256":
        return False
    for field, value in snapshot.items():
        if entry.get(field) != value:
            return False
    digest = entry.get("sha256")
    return (
        isinstance(digest, str)
        and len(digest) == 64
        and all(character in "0123456789abcdef" for character in digest)
    )


def _write_checkpoint_cache(path: Path, data: dict[str, Any]) -> None:
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


def _hash_selected_file(
    logical_path: Path,
    *,
    cache: dict[str, Any],
    force_rehash: bool,
    parsed_metadata: bool,
) -> tuple[dict[str, Any], str, bytes | None]:
    """Return ``(pre_snapshot, sha256, bytes_if_read)`` for one selection.

    Identity is validated before and after the read; a change during hashing
    fails closed. Parsed-metadata files are always read fresh so parsed
    content and hashed bytes come from one identity-validated read.
    """

    snapshot = _identity_snapshot(logical_path)
    if parsed_metadata and snapshot["size"] > MAX_PARSED_METADATA_BYTES:
        raise CheckpointProvenanceUnavailable(
            f"metadata file exceeds the bounded parse size: {logical_path.name}"
        )

    entries = cache["entries"]
    cache_key = snapshot["logical_path"]
    cached = entries.get(cache_key)
    if (
        not force_rehash
        and not parsed_metadata
        and _cache_entry_matches(cached, snapshot)
    ):
        return snapshot, cached["sha256"], None

    digest = hashlib.sha256()
    data: bytes | None = None
    try:
        with logical_path.open("rb") as handle:
            if parsed_metadata:
                data = handle.read(MAX_PARSED_METADATA_BYTES + 1)
                digest.update(data)
            else:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
    except OSError as exc:
        raise CheckpointProvenanceUnavailable(
            f"selected file is unreadable: {logical_path.name} ({exc.strerror or exc})"
        ) from None

    if data is not None and len(data) > MAX_PARSED_METADATA_BYTES:
        raise CheckpointProvenanceUnavailable(
            f"metadata file exceeds the bounded parse size: {logical_path.name}"
        )

    final_snapshot = _identity_snapshot(logical_path)
    if final_snapshot != snapshot:
        raise CheckpointProvenanceUnavailable(
            f"selected file changed while it was being hashed: {logical_path.name}"
        )

    sha256 = digest.hexdigest()
    entries[cache_key] = {
        **final_snapshot,
        "algorithm": "sha256",
        "sha256": sha256,
        "updated_at_utc": datetime.now(UTC).replace(microsecond=0).isoformat(),
    }
    return snapshot, sha256, data


# ---------------------------------------------------------------------------
# Canonical selection
# ---------------------------------------------------------------------------


def _root_level_names(root: Path) -> set[str]:
    try:
        return {entry.name for entry in os.scandir(root)}
    except OSError as exc:
        raise CheckpointProvenanceUnavailable(
            f"checkpoint root is not readable: {exc.strerror or exc}"
        ) from None


def _optional_present(names: set[str], allowlist: tuple[str, ...]) -> list[str]:
    return sorted(name for name in allowlist if name in names)


def _select_weight_paths(
    root: Path,
    names: set[str],
    index_bytes: bytes | None,
) -> tuple[list[str], int]:
    """Return the selected weight relative paths and the shard count.

    With an index: exactly the unique paths referenced by its ``weight_map``
    (the index file itself is selected separately). Without an index:
    deterministically sorted root-level ``*.safetensors`` files. At least one
    weight file is required.
    """

    if index_bytes is not None:
        try:
            index = json.loads(index_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise CheckpointProvenanceUnavailable(
                "weights index is not valid JSON"
            ) from None
        if not isinstance(index, dict):
            raise CheckpointProvenanceUnavailable("weights index is not a JSON object")
        weight_map = index.get("weight_map")
        if not isinstance(weight_map, dict) or not weight_map:
            raise CheckpointProvenanceUnavailable(
                "weights index has no non-empty weight_map object"
            )
        shards: set[str] = set()
        for tensor_name, raw_path in weight_map.items():
            if not isinstance(tensor_name, str) or not tensor_name:
                raise CheckpointProvenanceUnavailable(
                    "weights index has a malformed tensor key"
                )
            relative = normalize_selected_relative_path(
                raw_path,
                label=f"weights index path for {tensor_name!r}",
            )
            # Reject missing/broken/directory/non-regular shards fail-closed.
            _identity_snapshot(root / relative)
            shards.add(relative)
        if not shards:
            raise CheckpointProvenanceUnavailable(
                "weights index references no shard files"
            )
        return sorted(shards), len(shards)

    selected: list[str] = []
    for name in sorted(names):
        if not name.endswith(SAFETENSORS_SUFFIX):
            continue
        # A directory named *.safetensors is not an admitted weight file;
        # broken links and non-regular files fail honestly in the snapshot.
        _identity_snapshot(root / name)
        selected.append(name)
    if not selected:
        raise CheckpointProvenanceUnavailable(
            "no admitted root-level safetensors weight files were found"
        )
    return selected, len(selected)


# ---------------------------------------------------------------------------
# Metadata extraction (bounded, conservative)
# ---------------------------------------------------------------------------


def _parse_json_object(
    data: bytes | None,
    *,
    filename: str,
    required: bool,
) -> dict[str, Any] | None:
    if data is None:
        if required:
            raise CheckpointProvenanceUnavailable(f"{filename} could not be read")
        return None
    try:
        parsed = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        if required:
            raise CheckpointProvenanceUnavailable(
                f"{filename} is not valid JSON"
            ) from None
        return None
    if not isinstance(parsed, dict):
        if required:
            raise CheckpointProvenanceUnavailable(f"{filename} is not a JSON object")
        return None
    return parsed


def _extract_architecture(
    config: Mapping[str, Any],
) -> tuple[str | None, str | None]:
    architectures = config.get("architectures")
    architecture: str | None = None
    if isinstance(architectures, list) and len(architectures) == 1:
        only = architectures[0]
        if isinstance(only, str) and only.strip():
            architecture = only.strip()
    model_type = config.get("model_type")
    if isinstance(model_type, str) and model_type.strip():
        model_type = model_type.strip()
    else:
        model_type = None
    return architecture, model_type


def _quant_method_from(mapping: Mapping[str, Any]) -> str | None:
    value = mapping.get("quant_method")
    if isinstance(value, str) and value.strip():
        return value.strip().lower()
    return None


def _extract_declared_quantization(
    parsed: Mapping[str, bytes | None],
    manifest_paths: set[str],
) -> dict[str, Any]:
    """Bounded checkpoint-declared quantization evidence.

    Only explicit hashed metadata fields are read: ``config.json``
    ``quantization_config.quant_method`` and the admitted quantization
    sidecars' explicit ``quant_method`` values. No filename/size/dtype
    inference is performed.
    """

    sources: list[dict[str, str]] = []

    config = _parse_json_object(
        parsed.get(CONFIG_FILENAME), filename=CONFIG_FILENAME, required=True
    )
    assert config is not None
    config_quant = config.get("quantization_config")
    if isinstance(config_quant, dict):
        method = _quant_method_from(config_quant)
        if method:
            sources.append(
                {
                    "file": CONFIG_FILENAME,
                    "field": "quantization_config.quant_method",
                    "value": method,
                }
            )

    for sidecar in QUANTIZATION_SIDECAR_FILENAMES:
        if sidecar not in manifest_paths:
            continue
        data = _parse_json_object(parsed.get(sidecar), filename=sidecar, required=False)
        if data is None:
            continue
        method = _quant_method_from(data)
        field = "quant_method"
        if method is None and isinstance(data.get("quantization_config"), dict):
            method = _quant_method_from(data["quantization_config"])
            field = "quantization_config.quant_method"
        if method:
            sources.append({"file": sidecar, "field": field, "value": method})

    values = sorted({source["value"] for source in sources})
    if not sources:
        return {"status": "absent", "method": None, "sources": []}
    if len(values) > 1:
        return {
            "status": "conflict",
            "method": None,
            "sources": sources,
        }
    return {"status": "declared", "method": values[0], "sources": sources}


def _single_template_string(container: Mapping[str, Any]) -> str | None:
    """Return the container's single deterministic template string, if any."""

    template = container.get("chat_template")
    if isinstance(template, str) and template:
        return template
    return None


def _template_identity(
    *,
    status: str,
    source: str | None,
    selection_method: str,
    encoding: str | None,
    sha256: str | None,
    warning: str | None = None,
) -> dict[str, Any]:
    return {
        "status": status,
        "source": source,
        "selection_method": selection_method,
        "encoding": encoding,
        "sha256": sha256,
        "public_fingerprint": public_model_fingerprint(sha256) if sha256 else None,
        "warning": warning,
    }


def _extract_template_identity(
    parsed: Mapping[str, bytes | None],
    manifest: Mapping[str, Mapping[str, Any]],
    present_names: set[str],
    warnings: list[str],
) -> dict[str, Any]:
    """Conservative chat-template identity; ambiguous selection is never guessed."""

    standalone = [
        name for name in STANDALONE_TEMPLATE_FILENAMES if name in present_names
    ]
    if len(standalone) > 1:
        return _template_identity(
            status="partial",
            source=None,
            selection_method="ambiguous",
            encoding=None,
            sha256=None,
            warning=(
                "multiple standalone chat-template files are present; "
                "M2 does not guess runtime template precedence"
            ),
        )
    if standalone:
        name = standalone[0]
        entry = manifest[name]
        if name == "chat_template.jinja":
            if _CHAT_TEMPLATE_EMBEDDING_FILENAME in present_names:
                warnings.append(
                    "an embedded tokenizer_config.json chat template is also "
                    "declared; the standalone chat_template.jinja bytes were "
                    "hashed as the checkpoint-declared template"
                )
            return _template_identity(
                status="available",
                source=name,
                selection_method="standalone_file_bytes",
                encoding="exact-file-bytes",
                sha256=entry["sha256"],
            )
        # chat_template.json: hash the exact extracted template string, not
        # the container file.
        container = _parse_json_object(parsed.get(name), filename=name, required=False)
        template = _single_template_string(container) if container else None
        if template is None:
            return _template_identity(
                status="partial",
                source=name,
                selection_method="ambiguous",
                encoding=None,
                sha256=None,
                warning=(
                    f"{name} does not contain exactly one deterministic chat "
                    "template string"
                ),
            )
        return _template_identity(
            status="available",
            source=name,
            selection_method="json_field_string",
            encoding="utf-8-exact-string",
            sha256=hashlib.sha256(template.encode("utf-8")).hexdigest(),
        )

    tokenizer_config = _parse_json_object(
        parsed.get(_CHAT_TEMPLATE_EMBEDDING_FILENAME),
        filename=_CHAT_TEMPLATE_EMBEDDING_FILENAME,
        required=False,
    )
    if tokenizer_config is None:
        return _template_identity(
            status="unavailable",
            source=None,
            selection_method="none",
            encoding=None,
            sha256=None,
            warning="no admitted chat-template source was found",
        )
    template = _single_template_string(tokenizer_config)
    if template is None:
        declared = "chat_template" in tokenizer_config
        return _template_identity(
            status="partial",
            source=_CHAT_TEMPLATE_EMBEDDING_FILENAME,
            selection_method="ambiguous",
            encoding=None,
            sha256=None,
            warning=(
                "tokenizer_config.json declares multiple or non-string chat "
                "templates; M2 does not guess runtime template precedence"
                if declared
                else "tokenizer_config.json declares no chat template"
            ),
        )
    return _template_identity(
        status="available",
        source=_CHAT_TEMPLATE_EMBEDDING_FILENAME,
        selection_method="embedded_string",
        encoding="utf-8-exact-string",
        sha256=hashlib.sha256(template.encode("utf-8")).hexdigest(),
    )


# ---------------------------------------------------------------------------
# Repository/revision identity (local HF cache layout only; never networked)
# ---------------------------------------------------------------------------

_HEX40 = frozenset("0123456789abcdef")


def _derive_hf_snapshot_identity(
    root: Path,
) -> tuple[str | None, str | None, str]:
    """Conservatively derive repo id + immutable revision from HF cache layout.

    Recognizes only ``<dir>/models--<org>--<name>/snapshots/<40-hex>/``. The
    local absolute path itself is never persisted. Returns
    ``(repository_id, revision, source)``.
    """

    parent = root.parent
    grandparent = parent.parent
    if parent.name != "snapshots" or not grandparent.name.startswith("models--"):
        return None, None, "unknown"
    revision = root.name
    if len(revision) != 40 or any(character not in _HEX40 for character in revision):
        return None, None, "unknown"
    remainder = grandparent.name[len("models--") :]
    if "--" not in remainder:
        return None, None, "unknown"
    org, _, name = remainder.partition("--")
    if not org or not name:
        return None, None, "unknown"
    return f"{org}/{name}", revision, "hf_cache_snapshot_layout"


# ---------------------------------------------------------------------------
# Public collection API
# ---------------------------------------------------------------------------


def _unavailable_record(source_type: str, reason: str) -> dict[str, Any]:
    return {
        "source_type": source_type,
        "provenance_kind": CHECKPOINT_PROVENANCE_KIND,
        "status": "unavailable",
        "reason": reason,
        "warnings": [reason],
        "manifest_schema": CHECKPOINT_MANIFEST_SCHEMA_VERSION,
        "manifest": None,
        "manifest_sha256": None,
        "public_fingerprint": None,
        "entry_count": None,
        "weight_file_count": None,
        "architecture": None,
        "model_type": None,
        "repository_id": None,
        "revision": None,
        "repository_id_source": "unknown",
        "tokenizer_identity": {
            "status": "unavailable",
            "files": [],
            "sha256": None,
            "public_fingerprint": None,
        },
        "chat_template_identity": _template_identity(
            status="unavailable",
            source=None,
            selection_method="none",
            encoding=None,
            sha256=None,
        ),
        "checkpoint_quantization": {"status": "unknown", "method": None, "sources": []},
        "effective_quantization": {
            "status": "unavailable",
            "reason": "M2 has no runtime observation; effective quantization is unknown",
        },
        "fingerprint_eligible": False,
        "fingerprint_ineligible_reason": reason,
    }


def collect_checkpoint_provenance(
    root: Path,
    *,
    source_type: str,
    cache_path: Path | None = None,
    force_rehash: bool = False,
) -> dict[str, Any]:
    """Collect bounded checkpoint-directory provenance from a local root.

    Never raises for collection failures: an untrustworthy identity returns
    an ``unavailable`` record with a precise reason (fail closed). The
    absolute checkpoint root path is never persisted in the returned record.
    """

    try:
        return _collect_checkpoint_provenance(
            root,
            source_type=source_type,
            cache_path=cache_path,
            force_rehash=force_rehash,
        )
    except CheckpointProvenanceUnavailable as exc:
        return _unavailable_record(source_type, exc.reason)
    except OSError as exc:
        return _unavailable_record(
            source_type, f"checkpoint collection failed: {exc.strerror or exc}"
        )


def _collect_checkpoint_provenance(
    root: Path,
    *,
    source_type: str,
    cache_path: Path | None,
    force_rehash: bool,
) -> dict[str, Any]:
    logical_root = Path(os.path.abspath(os.path.expanduser(str(root))))
    if not logical_root.is_dir():
        raise CheckpointProvenanceUnavailable("checkpoint root is not a directory")

    names = _root_level_names(logical_root)
    if CONFIG_FILENAME not in names:
        raise CheckpointProvenanceUnavailable(
            "config.json is missing from the checkpoint root"
        )

    cache_path = cache_path or checkpoint_hash_cache_path()
    cache = _load_checkpoint_cache(cache_path)

    # --- collect selection ---------------------------------------------------
    selection: list[str] = [CONFIG_FILENAME]
    if GENERATION_CONFIG_FILENAME in names:
        selection.append(GENERATION_CONFIG_FILENAME)

    index_present = WEIGHTS_INDEX_FILENAME in names
    parsed_metadata: dict[str, bytes | None] = {}
    index_snapshot: dict[str, Any] | None = None
    index_sha256: str | None = None
    index_bytes: bytes | None = None
    if index_present:
        index_snapshot, index_sha256, index_bytes = _hash_selected_file(
            logical_root / WEIGHTS_INDEX_FILENAME,
            cache=cache,
            force_rehash=force_rehash,
            parsed_metadata=True,
        )
        parsed_metadata[WEIGHTS_INDEX_FILENAME] = index_bytes
        selection.append(WEIGHTS_INDEX_FILENAME)

    weight_paths, weight_count = _select_weight_paths(
        logical_root, names, index_bytes if index_present else None
    )
    selection.extend(weight_paths)

    for sidecar in QUANTIZATION_SIDECAR_FILENAMES:
        if sidecar in names:
            selection.append(sidecar)
    selection.extend(_optional_present(names, TOKENIZER_FILENAMES))
    selection.extend(_optional_present(names, STANDALONE_TEMPLATE_FILENAMES))

    normalized = [
        normalize_selected_relative_path(path, label=f"selected path {path!r}")
        for path in selection
    ]
    if len(set(normalized)) != len(normalized):
        raise CheckpointProvenanceUnavailable(
            "canonical selection contains duplicate normalized paths"
        )
    if len(normalized) > MAX_MANIFEST_ENTRIES:
        raise CheckpointProvenanceUnavailable(
            "canonical selection exceeds the bounded manifest entry limit"
        )
    selection = sorted(set(normalized))

    # --- hash ----------------------------------------------------------------
    manifest_by_path: dict[str, dict[str, Any]] = {}
    pre_snapshots: dict[str, dict[str, Any]] = {}
    if index_present and index_snapshot is not None and index_sha256 is not None:
        pre_snapshots[WEIGHTS_INDEX_FILENAME] = index_snapshot
        manifest_by_path[WEIGHTS_INDEX_FILENAME] = {
            "path": WEIGHTS_INDEX_FILENAME,
            "size": index_snapshot["size"],
            "sha256": index_sha256,
        }
    for relative in selection:
        if relative in manifest_by_path:
            continue
        parsed = relative in _PARSED_METADATA_FILENAMES
        snapshot, sha256, data = _hash_selected_file(
            logical_root / relative,
            cache=cache,
            force_rehash=force_rehash,
            parsed_metadata=parsed,
        )
        pre_snapshots[relative] = snapshot
        manifest_by_path[relative] = {
            "path": relative,
            "size": snapshot["size"],
            "sha256": sha256,
        }
        if parsed:
            parsed_metadata[relative] = data

    # --- revalidate selection-driving state before finalizing ----------------
    post_names = _root_level_names(logical_root)
    if post_names != names:
        raise CheckpointProvenanceUnavailable(
            "checkpoint root contents changed during collection"
        )
    if index_present:
        recheck_snapshot, _, recheck_bytes = _hash_selected_file(
            logical_root / WEIGHTS_INDEX_FILENAME,
            cache=cache,
            force_rehash=True,
            parsed_metadata=True,
        )
        if recheck_snapshot != index_snapshot or recheck_bytes != index_bytes:
            raise CheckpointProvenanceUnavailable(
                "weights index changed during collection"
            )
        revalidated_weights, revalidated_count = _select_weight_paths(
            logical_root, post_names, recheck_bytes
        )
        if revalidated_weights != weight_paths or revalidated_count != weight_count:
            raise CheckpointProvenanceUnavailable(
                "weights selection changed during collection"
            )
    for relative, snapshot in pre_snapshots.items():
        if _identity_snapshot(logical_root / relative) != snapshot:
            raise CheckpointProvenanceUnavailable(
                f"selected file changed during collection: {relative}"
            )

    # --- cache persistence (failure never invalidates computed hashes) -------
    try:
        _write_checkpoint_cache(cache_path, cache)
    except OSError:
        pass

    # --- identity construction ------------------------------------------------
    entries = [manifest_by_path[relative] for relative in selection]
    manifest_paths = set(manifest_by_path)

    config = _parse_json_object(
        parsed_metadata.get(CONFIG_FILENAME), filename=CONFIG_FILENAME, required=True
    )
    assert config is not None
    architecture, model_type = _extract_architecture(config)

    warnings: list[str] = []
    tokenizer_files = sorted(
        relative
        for relative in manifest_paths
        if PurePosixPath(relative).name in TOKENIZER_FILENAMES
    )
    if tokenizer_files:
        tokenizer_entries = [manifest_by_path[relative] for relative in tokenizer_files]
        tokenizer_sha256 = checkpoint_tokenizer_identity_fingerprint(tokenizer_entries)
        tokenizer_identity = {
            "status": "available",
            "files": tokenizer_files,
            "sha256": tokenizer_sha256,
            "public_fingerprint": public_model_fingerprint(tokenizer_sha256),
        }
    else:
        tokenizer_identity = {
            "status": "unavailable",
            "files": [],
            "sha256": None,
            "public_fingerprint": None,
        }
        warnings.append("no admitted tokenizer files are present")

    template_identity = _extract_template_identity(
        parsed_metadata, manifest_by_path, names, warnings
    )

    quantization = _extract_declared_quantization(parsed_metadata, manifest_paths)
    if quantization["status"] == "conflict":
        warnings.append("checkpoint quantization declarations disagree")

    # An explicit auto_map declaration means the checkpoint depends on
    # custom modeling/tokenizer code outside the admitted canonical allowlist.
    # The manifest stays canonical (never ad hoc expanded), but identity is
    # knowingly incomplete: status becomes partial.
    depends_on_unadmitted_code = isinstance(config.get("auto_map"), dict) and bool(
        config.get("auto_map")
    )
    if depends_on_unadmitted_code:
        warnings.append(
            "config.json declares auto_map custom code outside the admitted "
            "canonical file allowlist"
        )

    repository_id, revision, repository_source = _derive_hf_snapshot_identity(
        logical_root
    )

    manifest_sha256 = checkpoint_manifest_fingerprint(entries)
    public_fingerprint = public_model_fingerprint(manifest_sha256)

    partial = (
        tokenizer_identity["status"] != "available"
        or template_identity["status"] != "available"
        or quantization["status"] == "conflict"
        or depends_on_unadmitted_code
    )
    status = "partial" if partial else "available"
    eligible = status == "available"
    ineligible_reason: str | None = None
    if not eligible:
        blockers: list[str] = []
        if tokenizer_identity["status"] != "available":
            blockers.append("tokenizer identity is incomplete")
        if template_identity["status"] != "available":
            blockers.append("chat-template identity is ambiguous or unavailable")
        if quantization["status"] == "conflict":
            blockers.append("checkpoint quantization declarations disagree")
        if depends_on_unadmitted_code:
            blockers.append(
                "checkpoint depends on custom code outside the admitted "
                "canonical allowlist"
            )
        ineligible_reason = "canonical checkpoint identity is incomplete: " + "; ".join(
            blockers
        )

    return {
        "source_type": source_type,
        "provenance_kind": CHECKPOINT_PROVENANCE_KIND,
        "status": status,
        "reason": None,
        "warnings": warnings,
        "manifest_schema": CHECKPOINT_MANIFEST_SCHEMA_VERSION,
        "manifest": entries,
        "manifest_sha256": manifest_sha256,
        "public_fingerprint": public_fingerprint,
        "entry_count": len(entries),
        "weight_file_count": weight_count,
        "architecture": architecture,
        "model_type": model_type,
        "repository_id": repository_id,
        "revision": revision,
        "repository_id_source": repository_source,
        "tokenizer_identity": tokenizer_identity,
        "chat_template_identity": template_identity,
        "checkpoint_quantization": quantization,
        "effective_quantization": {
            "status": "unavailable",
            "reason": "M2 has no runtime observation; effective quantization is unknown",
        },
        "fingerprint_eligible": eligible,
        "fingerprint_ineligible_reason": ineligible_reason,
    }
