from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

RUN_FINGERPRINT_SCHEMA_VERSION = "llmgauge.run_fingerprint.v0"
RUN_FINGERPRINT_PAYLOAD_VERSION = "llmgauge.run_fingerprint_payload.v0"
RUN_FINGERPRINT_SCHEMA_VERSION_V1 = "llmgauge.run_fingerprint.v1"
RUN_FINGERPRINT_PAYLOAD_VERSION_V1 = "llmgauge.run_fingerprint_payload.v1"
RUN_FINGERPRINT_SCHEMA_VERSION_V2 = "llmgauge.run_fingerprint.v2"
RUN_FINGERPRINT_PAYLOAD_VERSION_V2 = "llmgauge.run_fingerprint_payload.v2"
RUN_FINGERPRINT_SCHEMA_VERSION_V3 = "llmgauge.run_fingerprint.v3"
RUN_FINGERPRINT_PAYLOAD_VERSION_V3 = "llmgauge.run_fingerprint_payload.v3"
RUN_FINGERPRINT_SCHEMA_VERSION_V4 = "llmgauge.run_fingerprint.v4"
RUN_FINGERPRINT_PAYLOAD_VERSION_V4 = "llmgauge.run_fingerprint_payload.v4"
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


def resolve_contained_result_artifact(
    result_dir: Path,
    relative_path: Any,
    *,
    label: str,
    require_file: bool = True,
) -> Path:
    """Resolve a result-relative artifact path with containment checks.

    Requires a non-empty relative path, rejects absolute paths and ``..``
    components, walks each path component rejecting symlinks, then confirms the
    resolved target remains inside the result directory via ``relative_to``.
    """
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
                    f"{label} artifact path escapes result directory: {relative_path}"
                )
        if require_file:
            if not cursor.is_file():
                raise FingerprintUnavailable(
                    f"{label} missing artifact: {relative_path}"
                )
            resolved = cursor.resolve(strict=True)
        else:
            if not cursor.exists():
                raise FingerprintUnavailable(
                    f"{label} missing artifact: {relative_path}"
                )
            resolved = cursor.resolve(strict=True)
        try:
            resolved.relative_to(boundary)
        except ValueError:
            raise FingerprintUnavailable(
                f"{label} artifact path escapes result directory: {relative_path}"
            ) from None
        return cursor
    except FingerprintUnavailable:
        raise
    except OSError:
        raise FingerprintUnavailable(
            f"{label} artifact is unreadable: {relative_path}"
        ) from None


def _artifact_sha256(result_dir: Path, relative_path: Any, *, label: str) -> str:
    cursor = resolve_contained_result_artifact(
        result_dir,
        relative_path,
        label=label,
        require_file=True,
    )
    try:
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


def _runtime_settings(
    runtime: Mapping[str, Any],
    *,
    include_extended_settings: bool = False,
    include_control_settings: bool = False,
) -> dict[str, Any]:
    # Material generation / execution knobs only.
    # Excluded from common result runtime blob: runtime_label (label),
    # vram_min_headroom_warn_mib (warning threshold), local paths
    # (llama_cli, config_path, model_profiles_path), command argv (prompt
    # and paths), runtime_command_* capture flags/paths, and
    # backend_provenance (handled under backend identity).
    fields = [
        "ctx_size",
        "max_tokens",
        "temperature",
        "top_p",
        "batch_size",
        "ubatch_size",
        "gpu_layers",
        "flash_attn",
        "reasoning_mode",
    ]
    if include_extended_settings:
        fields.extend(
            [
                "parallel_sequences",
                "top_k",
                "top_k_state",
                "seed",
                "seed_state",
                "kv_offload",
                "cache_type_k",
                "cache_type_k_state",
                "cache_type_v",
                "cache_type_v_state",
                "reasoning_effort",
                "reasoning_effort_state",
                "reasoning_budget",
                "reasoning_budget_state",
            ]
        )
    if include_control_settings:
        fields.extend(
            [
                "fit",
                "fit_state",
                "reasoning_preserve",
                "reasoning_preserve_state",
                "spec_type",
                "spec_type_state",
            ]
        )
    return _selected_mapping(runtime, fields)


def _prompt_evidence(
    result_dir: Path,
    prompt_result: Mapping[str, Any],
    *,
    index: int,
    include_native_execution_evidence: bool,
) -> dict[str, Any]:
    prompt_id = prompt_result.get("prompt_id")
    label = (
        str(prompt_id)
        if isinstance(prompt_id, str) and prompt_id
        else f"results[{index}]"
    )
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
    if include_native_execution_evidence:
        artifact_hashes["native_execution_evidence"] = _artifact_sha256(
            result_dir,
            prompt_result.get("native_execution_evidence_path"),
            label=f"{label}.native_execution_evidence_path",
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
            "native_execution_evidence_path": (
                prompt_result.get("native_execution_evidence_path")
                if include_native_execution_evidence
                else None
            ),
        },
        "artifact_sha256": artifact_hashes,
    }


def _area4_is_represented(result: Mapping[str, Any]) -> bool:
    return (
        result.get("runtime_neutral_metrics") is not None
        or result.get("failure_taxonomy") is not None
    )


def _external_benchmark_is_represented(result: Mapping[str, Any]) -> bool:
    return result.get("external_benchmark_evidence") is not None


def _extended_runtime_evidence_is_represented(result: Mapping[str, Any]) -> bool:
    runtime = result.get("runtime")
    return isinstance(runtime, Mapping) and any(
        field in runtime
        for field in (
            "top_k",
            "seed",
            "cache_type_k",
            "cache_type_v",
            "reasoning_effort",
            "reasoning_budget",
            "fit",
            "reasoning_preserve",
            "spec_type",
        )
    )


def _control_runtime_evidence_is_represented(result: Mapping[str, Any]) -> bool:
    runtime = result.get("runtime")
    return isinstance(runtime, Mapping) and any(
        field in runtime for field in ("fit", "reasoning_preserve", "spec_type")
    )


def _fingerprint_versions(result: Mapping[str, Any]) -> tuple[str, str]:
    if _control_runtime_evidence_is_represented(result):
        return RUN_FINGERPRINT_SCHEMA_VERSION_V4, RUN_FINGERPRINT_PAYLOAD_VERSION_V4
    if _extended_runtime_evidence_is_represented(result):
        return RUN_FINGERPRINT_SCHEMA_VERSION_V3, RUN_FINGERPRINT_PAYLOAD_VERSION_V3
    if _external_benchmark_is_represented(result):
        return RUN_FINGERPRINT_SCHEMA_VERSION_V2, RUN_FINGERPRINT_PAYLOAD_VERSION_V2
    if _area4_is_represented(result):
        return RUN_FINGERPRINT_SCHEMA_VERSION_V1, RUN_FINGERPRINT_PAYLOAD_VERSION_V1
    return RUN_FINGERPRINT_SCHEMA_VERSION, RUN_FINGERPRINT_PAYLOAD_VERSION


def build_run_fingerprint_payload(
    result_dir: Path,
    result: Mapping[str, Any],
    *,
    payload_version: str | None = None,
) -> dict[str, Any]:
    """Build the canonical private-evidence payload without hashing the payload."""

    _, resolved_payload_version = _fingerprint_versions(result)
    if payload_version is None:
        payload_version = resolved_payload_version
    include_area4 = payload_version == RUN_FINGERPRINT_PAYLOAD_VERSION_V1 or (
        payload_version
        in {
            RUN_FINGERPRINT_PAYLOAD_VERSION_V3,
            RUN_FINGERPRINT_PAYLOAD_VERSION_V4,
        }
        and _area4_is_represented(result)
    )
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
    external_reference = result.get("external_benchmark_evidence")
    if external_reference is not None:
        if payload_version not in {
            RUN_FINGERPRINT_PAYLOAD_VERSION_V2,
            RUN_FINGERPRINT_PAYLOAD_VERSION_V3,
            RUN_FINGERPRINT_PAYLOAD_VERSION_V4,
        }:
            raise FingerprintUnavailable(
                "external_benchmark_evidence requires a v2, v3, or v4 "
                "fingerprint payload"
            )
        if not isinstance(external_reference, Mapping):
            raise FingerprintUnavailable(
                "external_benchmark_evidence reference is unavailable"
            )
        from llmgauge.core.external_benchmark import (
            immutable_external_benchmark_payload,
            load_external_benchmark_evidence,
        )

        try:
            evidence = load_external_benchmark_evidence(result_dir, external_reference)
        except ValueError as exc:
            raise FingerprintUnavailable(
                f"external_benchmark_evidence is unavailable: {exc}"
            ) from None
        return {
            "schema_version": payload_version,
            "result_schema_version": result.get("schema_version"),
            "llmgauge_version": result.get("llmgauge_version"),
            "external_benchmark_evidence": immutable_external_benchmark_payload(
                evidence
            ),
            "policy": {
                "run_id": "excluded",
                "timestamp_utc": "excluded",
                "import_timestamp": "excluded",
                "external_locator": "excluded",
                "paths": "source_member_hashes_only",
                "scores": "excluded",
                "reports": "excluded",
                "comparisons": "excluded",
                "exports": "excluded",
                "localmaxxing": "excluded",
            },
        }
    agent_harness_reference = result.get("agent_harness_evidence")
    if agent_harness_reference is not None:
        if not isinstance(agent_harness_reference, Mapping):
            raise FingerprintUnavailable(
                "agent_harness_evidence reference is unavailable"
            )
        from llmgauge.core.agent_harness import (
            immutable_agent_harness_payload,
            load_agent_harness_evidence,
        )

        try:
            evidence = load_agent_harness_evidence(result_dir, agent_harness_reference)
        except ValueError as exc:
            raise FingerprintUnavailable(
                f"agent_harness_evidence is unavailable: {exc}"
            ) from None
        return {
            "schema_version": payload_version,
            "result_schema_version": result.get("schema_version"),
            "llmgauge_version": result.get("llmgauge_version"),
            "agent_harness_evidence": immutable_agent_harness_payload(evidence),
            "policy": {
                "run_id": "excluded",
                "timestamp_utc": "excluded",
                "paths": "source_member_hashes_only",
                "scores": "excluded",
                "reports": "excluded",
                "comparisons": "excluded",
                "exports": "excluded",
            },
        }

    prompt_evidence: list[dict[str, Any]] = []
    for index, prompt_result in enumerate(results):
        if not isinstance(prompt_result, Mapping):
            raise FingerprintUnavailable(f"results[{index}] metadata is unavailable")
        prompt_evidence.append(
            _prompt_evidence(
                result_dir,
                prompt_result,
                index=index,
                include_native_execution_evidence=include_area4,
            )
        )

    suite_identity = _selected_mapping(
        suite,
        ["suite_id", "suite_version", "prompt_count", "include", "only"],
    )
    if "selection" in suite:
        suite_identity["selection"] = suite.get("selection")

    payload = {
        "schema_version": payload_version,
        "result_schema_version": result.get("schema_version"),
        "llmgauge_version": result.get("llmgauge_version"),
        "model": _model_identity(model),
        "backend": _backend_identity(runtime),
        "runtime_settings": _runtime_settings(
            runtime,
            include_extended_settings=payload_version
            in {
                RUN_FINGERPRINT_PAYLOAD_VERSION_V3,
                RUN_FINGERPRINT_PAYLOAD_VERSION_V4,
            },
            include_control_settings=(
                payload_version == RUN_FINGERPRINT_PAYLOAD_VERSION_V4
                or (
                    payload_version == RUN_FINGERPRINT_PAYLOAD_VERSION_V3
                    and _control_runtime_evidence_is_represented(result)
                )
            ),
        ),
        "suite": suite_identity,
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
    if include_area4:
        runtime_neutral_metrics = result.get("runtime_neutral_metrics")
        failure_taxonomy = result.get("failure_taxonomy")
        if not isinstance(runtime_neutral_metrics, Mapping):
            raise FingerprintUnavailable("runtime_neutral_metrics is unavailable")
        if not isinstance(failure_taxonomy, Mapping):
            raise FingerprintUnavailable("failure_taxonomy is unavailable")
        payload["runtime_neutral_metrics"] = runtime_neutral_metrics
        payload["failure_taxonomy"] = failure_taxonomy
    if result.get("transcript") is not None:
        from llmgauge.core.multi_turn import (
            TranscriptDefinitionError,
            immutable_transcript_payload,
            load_transcript,
        )

        reference = result.get("transcript")
        if not isinstance(reference, Mapping):
            raise FingerprintUnavailable("transcript reference is unavailable")
        relative_path = reference.get("path")
        if not isinstance(relative_path, str):
            raise FingerprintUnavailable("transcript.path is unavailable")
        try:
            transcript = load_transcript(result_dir, relative_path)
        except TranscriptDefinitionError as exc:
            raise FingerprintUnavailable(f"transcript is unavailable: {exc}") from None
        payload["transcript"] = immutable_transcript_payload(transcript)
    return payload


def run_fingerprint_value(
    result_dir: Path,
    result: Mapping[str, Any],
    *,
    payload_version: str | None = None,
) -> str:
    payload = build_run_fingerprint_payload(
        result_dir, result, payload_version=payload_version
    )
    return "sha256:" + hashlib.sha256(canonical_payload_bytes(payload)).hexdigest()


def build_run_fingerprint_metadata(
    result_dir: Path,
    result: Mapping[str, Any],
) -> dict[str, str]:
    schema_version, payload_version = _fingerprint_versions(result)
    return {
        "schema_version": schema_version,
        "algorithm": "sha256",
        "value": run_fingerprint_value(
            result_dir, result, payload_version=payload_version
        ),
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
    schema_version = fingerprint.get("schema_version")
    if schema_version not in {
        RUN_FINGERPRINT_SCHEMA_VERSION,
        RUN_FINGERPRINT_SCHEMA_VERSION_V1,
        RUN_FINGERPRINT_SCHEMA_VERSION_V2,
        RUN_FINGERPRINT_SCHEMA_VERSION_V3,
        RUN_FINGERPRINT_SCHEMA_VERSION_V4,
    }:
        errors.append(
            "run_fingerprint.schema_version must be "
            f"{RUN_FINGERPRINT_SCHEMA_VERSION}, "
            f"{RUN_FINGERPRINT_SCHEMA_VERSION_V1}, "
            f"{RUN_FINGERPRINT_SCHEMA_VERSION_V2}, "
            f"{RUN_FINGERPRINT_SCHEMA_VERSION_V3}, or "
            f"{RUN_FINGERPRINT_SCHEMA_VERSION_V4}"
        )
    if fingerprint.get("algorithm") != "sha256":
        errors.append("run_fingerprint.algorithm must be sha256")

    value = fingerprint.get("value")
    if not isinstance(value, str) or not _FINGERPRINT_VALUE_RE.fullmatch(value):
        errors.append("run_fingerprint.value must be sha256:<64 lowercase hex>")

    if errors:
        return errors
    if _control_runtime_evidence_is_represented(result) and schema_version not in {
        RUN_FINGERPRINT_SCHEMA_VERSION_V3,
        RUN_FINGERPRINT_SCHEMA_VERSION_V4,
    }:
        errors.append(
            "llama.cpp control evidence requires a v3 or v4 run_fingerprint "
            "when represented"
        )
        return errors
    if _extended_runtime_evidence_is_represented(result) and schema_version not in {
        RUN_FINGERPRINT_SCHEMA_VERSION_V3,
        RUN_FINGERPRINT_SCHEMA_VERSION_V4,
    }:
        errors.append(
            "extended runtime evidence requires a v3 or v4 run_fingerprint "
            "when represented"
        )
        return errors
    if _external_benchmark_is_represented(result) and schema_version not in {
        RUN_FINGERPRINT_SCHEMA_VERSION_V2,
        RUN_FINGERPRINT_SCHEMA_VERSION_V3,
        RUN_FINGERPRINT_SCHEMA_VERSION_V4,
    }:
        errors.append(
            "external benchmark evidence requires a v2, v3, or v4 "
            "run_fingerprint when represented"
        )
        return errors
    if _area4_is_represented(result) and schema_version not in {
        RUN_FINGERPRINT_SCHEMA_VERSION_V1,
        RUN_FINGERPRINT_SCHEMA_VERSION_V3,
        RUN_FINGERPRINT_SCHEMA_VERSION_V4,
    }:
        errors.append(
            "Area 4 evidence requires a v1, v3, or v4 run_fingerprint when represented"
        )
        return errors

    if schema_version == RUN_FINGERPRINT_SCHEMA_VERSION_V4:
        payload_version = RUN_FINGERPRINT_PAYLOAD_VERSION_V4
    elif schema_version == RUN_FINGERPRINT_SCHEMA_VERSION_V3:
        payload_version = RUN_FINGERPRINT_PAYLOAD_VERSION_V3
    elif schema_version == RUN_FINGERPRINT_SCHEMA_VERSION_V2:
        payload_version = RUN_FINGERPRINT_PAYLOAD_VERSION_V2
    elif schema_version == RUN_FINGERPRINT_SCHEMA_VERSION_V1:
        payload_version = RUN_FINGERPRINT_PAYLOAD_VERSION_V1
    else:
        payload_version = RUN_FINGERPRINT_PAYLOAD_VERSION

    try:
        expected = run_fingerprint_value(
            result_dir,
            result,
            payload_version=payload_version,
        )
    except FingerprintUnavailable as exc:
        return [f"run_fingerprint cannot be verified: {exc}"]

    if value != expected:
        return ["run_fingerprint.value does not match canonical run evidence"]
    return []
