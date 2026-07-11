from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

RUN_FINGERPRINT_SCHEMA_VERSION = "llmgauge.run_fingerprint.v0"
RUN_FINGERPRINT_PAYLOAD_VERSION = "llmgauge.run_fingerprint_payload.v0"
RUN_FINGERPRINT_FIELD = "run_fingerprint"

_SHA256_HEX_RE = re.compile(r"^[0-9a-f]{64}$")
_FINGERPRINT_VALUE_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


class FingerprintUnavailable(ValueError):
    """Raised when required private evidence is unavailable."""


def canonical_payload_bytes(payload: Mapping[str, Any]) -> bytes:
    """Serialize a run-fingerprint payload to deterministic UTF-8 JSON bytes."""

    return json.dumps(
        payload,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _sha256_is_available(value: Any) -> bool:
    return isinstance(value, str) and bool(_SHA256_HEX_RE.fullmatch(value))


def _artifact_sha256(result_dir: Path, relative_path: Any, *, label: str) -> str:
    if relative_path is None:
        raise FingerprintUnavailable(f"{label} path is missing")
    if not isinstance(relative_path, str) or not relative_path:
        raise FingerprintUnavailable(f"{label} path must be a non-empty string")

    path = Path(relative_path)
    if path.is_absolute() or ".." in path.parts:
        raise FingerprintUnavailable(f"{label} path must be relative: {relative_path}")

    try:
        boundary = result_dir.resolve(strict=True)
    except OSError:
        raise FingerprintUnavailable("result directory is unreadable") from None

    cursor = result_dir
    try:
        for part in path.parts:
            cursor = cursor / part
            if cursor.is_symlink():
                raise FingerprintUnavailable(
                    f"{label} artifact path escapes result directory: "
                    f"{relative_path}"
                )
        if not cursor.is_file():
            raise FingerprintUnavailable(
                f"{label} artifact is missing: {relative_path}"
            )

        resolved = cursor.resolve(strict=True)
        try:
            resolved.relative_to(boundary)
        except ValueError:
            raise FingerprintUnavailable(
                f"{label} artifact path escapes result directory: "
                f"{relative_path}"
            ) from None

        digest = hashlib.sha256()
        with cursor.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except FingerprintUnavailable:
        raise
    except OSError:
        raise FingerprintUnavailable(
            f"{label} artifact is unreadable: {relative_path}"
        ) from None


def _selected_mapping(source: Mapping[str, Any], keys: list[str]) -> dict[str, Any]:
    return {key: source.get(key) for key in keys}


def _model_identity(model: Mapping[str, Any]) -> dict[str, Any]:
    provenance = model.get("provenance")
    if not isinstance(provenance, Mapping):
        raise FingerprintUnavailable("model provenance is unavailable")
    if not _sha256_is_available(provenance.get("sha256")):
        raise FingerprintUnavailable("model SHA-256 provenance is unavailable")

    return {
        "model_id": model.get("model_id"),
        "model_source": model.get("model_source"),
        "model_profile": model.get("model_profile"),
        "label": model.get("label"),
        "family": model.get("family"),
        "role": model.get("role"),
        "quant": model.get("quant"),
        "provenance": _selected_mapping(
            provenance,
            [
                "source_type",
                "filename",
                "file_size_bytes",
                "sha256",
                "status",
            ],
        ),
    }


def _backend_identity(runtime: Mapping[str, Any]) -> dict[str, Any]:
    provenance = runtime.get("backend_provenance")
    if not isinstance(provenance, Mapping):
        raise FingerprintUnavailable("backend provenance is unavailable")
    if not _sha256_is_available(provenance.get("executable_sha256")):
        raise FingerprintUnavailable("backend executable SHA-256 is unavailable")

    return {
        "backend": runtime.get("backend"),
        "provenance": _selected_mapping(
            provenance,
            [
                "backend_name",
                "executable_filename",
                "executable_file_size_bytes",
                "executable_sha256",
                "status",
                "reported_version",
                "commit",
                "build_number",
                "build_type",
                "build_metadata",
                "discovery_status",
            ],
        ),
    }


def _runtime_settings(runtime: Mapping[str, Any]) -> dict[str, Any]:
    # Material generation / execution knobs only.
    # Excluded from common result runtime blob: runtime_label (label),
    # vram_min_headroom_warn_mib (warning threshold), local paths
    # (llama_cli, config_path, model_profiles_path), command argv (prompt
    # and paths), runtime_command_* capture flags/paths, and
    # backend_provenance (handled under backend identity).
    return _selected_mapping(
        runtime,
        [
            "ctx_size",
            "max_tokens",
            "temperature",
            "top_p",
            "batch_size",
            "ubatch_size",
            "gpu_layers",
            "flash_attn",
            "reasoning_mode",
        ],
    )


def _prompt_evidence(
    result_dir: Path,
    prompt_result: Mapping[str, Any],
    *,
    index: int,
) -> dict[str, Any]:
    prompt_id = prompt_result.get("prompt_id")
    label = str(prompt_id) if isinstance(prompt_id, str) and prompt_id else f"results[{index}]"
    artifact_hashes = {
        "raw_prompt": _artifact_sha256(
            result_dir,
            prompt_result.get("raw_prompt_path"),
            label=f"{label}.raw_prompt_path",
        ),
        "raw_output": _artifact_sha256(
            result_dir,
            prompt_result.get("raw_output_path"),
            label=f"{label}.raw_output_path",
        ),
        "stderr_log": _artifact_sha256(
            result_dir,
            prompt_result.get("stderr_log_path"),
            label=f"{label}.stderr_log_path",
        ),
    }
    if prompt_result.get("vram_samples_path"):
        artifact_hashes["vram_samples"] = _artifact_sha256(
            result_dir,
            prompt_result.get("vram_samples_path"),
            label=f"{label}.vram_samples_path",
        )

    return {
        "prompt_id": prompt_id,
        "title": prompt_result.get("title"),
        "category": prompt_result.get("category"),
        "status": prompt_result.get("status"),
        "exit_status": prompt_result.get("exit_status"),
        "artifact_paths": {
            "raw_prompt_path": prompt_result.get("raw_prompt_path"),
            "raw_output_path": prompt_result.get("raw_output_path"),
            "stderr_log_path": prompt_result.get("stderr_log_path"),
            "vram_samples_path": prompt_result.get("vram_samples_path"),
        },
        "artifact_sha256": artifact_hashes,
    }


def build_run_fingerprint_payload(
    result_dir: Path,
    result: Mapping[str, Any],
) -> dict[str, Any]:
    """Build the canonical private-evidence payload without hashing the payload."""

    model = result.get("model")
    runtime = result.get("runtime")
    suite = result.get("suite")
    results = result.get("results")
    if not isinstance(model, Mapping):
        raise FingerprintUnavailable("model metadata is unavailable")
    if not isinstance(runtime, Mapping):
        raise FingerprintUnavailable("runtime metadata is unavailable")
    if not isinstance(suite, Mapping):
        raise FingerprintUnavailable("suite metadata is unavailable")
    if not isinstance(results, list):
        raise FingerprintUnavailable("prompt results are unavailable")

    prompt_evidence: list[dict[str, Any]] = []
    for index, prompt_result in enumerate(results):
        if not isinstance(prompt_result, Mapping):
            raise FingerprintUnavailable(f"results[{index}] metadata is unavailable")
        prompt_evidence.append(
            _prompt_evidence(result_dir, prompt_result, index=index)
        )

    return {
        "schema_version": RUN_FINGERPRINT_PAYLOAD_VERSION,
        "result_schema_version": result.get("schema_version"),
        "llmgauge_version": result.get("llmgauge_version"),
        "model": _model_identity(model),
        "backend": _backend_identity(runtime),
        "runtime_settings": _runtime_settings(runtime),
        "suite": _selected_mapping(
            suite,
            ["suite_id", "suite_version", "prompt_count", "include", "only"],
        ),
        "prompts": prompt_evidence,
        "policy": {
            "run_id": "excluded",
            "timestamp_utc": "excluded",
            "paths": "relative_artifact_references_only",
            "scores": "excluded",
            "reports": "excluded",
            "cleaned_outputs": "excluded",
        },
    }


def run_fingerprint_value(result_dir: Path, result: Mapping[str, Any]) -> str:
    payload = build_run_fingerprint_payload(result_dir, result)
    return "sha256:" + hashlib.sha256(canonical_payload_bytes(payload)).hexdigest()


def build_run_fingerprint_metadata(
    result_dir: Path,
    result: Mapping[str, Any],
) -> dict[str, str]:
    return {
        "schema_version": RUN_FINGERPRINT_SCHEMA_VERSION,
        "algorithm": "sha256",
        "value": run_fingerprint_value(result_dir, result),
    }


def attach_run_fingerprint(
    result_dir: Path,
    result: dict[str, Any],
) -> dict[str, Any] | None:
    """Attach a fingerprint when the required private evidence is available."""

    try:
        fingerprint = build_run_fingerprint_metadata(result_dir, result)
    except FingerprintUnavailable:
        return None
    result[RUN_FINGERPRINT_FIELD] = fingerprint
    return fingerprint


def verify_run_fingerprint(
    result_dir: Path,
    result: Mapping[str, Any],
) -> list[str]:
    fingerprint = result.get(RUN_FINGERPRINT_FIELD)
    if fingerprint is None:
        return []
    if not isinstance(fingerprint, Mapping):
        return ["run_fingerprint must be an object"]

    errors: list[str] = []
    if fingerprint.get("schema_version") != RUN_FINGERPRINT_SCHEMA_VERSION:
        errors.append(
            "run_fingerprint.schema_version must be "
            f"{RUN_FINGERPRINT_SCHEMA_VERSION}"
        )
    if fingerprint.get("algorithm") != "sha256":
        errors.append("run_fingerprint.algorithm must be sha256")

    value = fingerprint.get("value")
    if not isinstance(value, str) or not _FINGERPRINT_VALUE_RE.fullmatch(value):
        errors.append("run_fingerprint.value must be sha256:<64 lowercase hex>")

    if errors:
        return errors

    try:
        expected = run_fingerprint_value(result_dir, result)
    except FingerprintUnavailable as exc:
        return [f"run_fingerprint cannot be verified: {exc}"]

    if value != expected:
        return ["run_fingerprint.value does not match canonical run evidence"]
    return []
