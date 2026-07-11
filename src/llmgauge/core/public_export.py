from __future__ import annotations

import json
import re
import shutil
import tempfile
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from llmgauge.core.artifacts import write_json, write_text
from llmgauge.core.result_validation import load_result_json, validate_result_dir
from llmgauge.core.run_fingerprint import RUN_FINGERPRINT_FIELD

PUBLIC_EXPORT_SCHEMA_VERSION = "llmgauge.public_export.v0"
PUBLIC_EXPORT_MANIFEST_FILENAME = "public-export-manifest.json"
PROMPT_FROM_RAW_ARTIFACT = "PROMPT_FROM_RAW_ARTIFACT"
_STAGING_PREFIX = ".llmgauge-public-export-"

_SECRET_KEY_RE = re.compile(
    r"^(?:api[_-]?key|access[_-]?token|auth(?:orization)?|credential|password|secret|token)$",
    re.IGNORECASE,
)
_SECRET_VALUE_RE = re.compile(
    r"(?i)(\b(?:api[_-]?key|access[_-]?token|authorization|password|secret|token)\b\s*[:=]\s*)([^\s,;]+)"
)
_CREDENTIAL_URL_RE = re.compile(r"(?i)https?://[^\s/@]+:[^\s/@]+@[^\s]+")
_ABSOLUTE_PATH_RE = re.compile(r"(?<![A-Za-z0-9_:/])/(?!/)[^\s\"'<>`]+")
_WINDOWS_PATH_RE = re.compile(r"(?i)(?<![A-Za-z0-9])(?:[a-z]:\\|\\\\)[^\s\"'<>`]+")


def _utc_timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _sanitize_text(text: str, categories: set[str]) -> str:
    def replace_url(match: re.Match[str]) -> str:
        categories.add("credential_bearing_url")
        return "REDACTED_SECRET"

    def replace_secret(match: re.Match[str]) -> str:
        categories.add("secret_like_value")
        return f"{match.group(1)}REDACTED_SECRET"

    def replace_path(match: re.Match[str]) -> str:
        value = match.group(0)
        if value.startswith(("/home/", "/Users/", "/root/", "/private/")):
            categories.add("home_directory_path")
            return "REDACTED_HOME_PATH"
        categories.add("absolute_path")
        return "REDACTED_ABSOLUTE_PATH"

    text = _CREDENTIAL_URL_RE.sub(replace_url, text)
    text = _SECRET_VALUE_RE.sub(replace_secret, text)
    text = _ABSOLUTE_PATH_RE.sub(replace_path, text)
    text = _WINDOWS_PATH_RE.sub(replace_path, text)
    return text


def _sanitize_structured(
    value: Any,
    categories: set[str],
    key: str | None = None,
) -> Any:
    if key is not None and _SECRET_KEY_RE.match(key):
        categories.add("secret_like_metadata")
        return "REDACTED_SECRET"

    if isinstance(value, Mapping):
        sanitized: dict[str, Any] = {}
        for child_key, child_value in value.items():
            normalized_key = child_key if isinstance(child_key, str) else str(child_key)
            sanitized[normalized_key] = _sanitize_structured(
                child_value,
                categories,
                key=normalized_key,
            )
        return sanitized

    if isinstance(value, list):
        return [_sanitize_structured(item, categories) for item in value]

    if isinstance(value, str):
        return _sanitize_text(value, categories)

    return value


def _remove_full_hashes(value: Any, categories: set[str]) -> Any:
    if isinstance(value, Mapping):
        sanitized: dict[str, Any] = {}
        for child_key, child_value in value.items():
            normalized_key = child_key if isinstance(child_key, str) else str(child_key)
            if normalized_key in {"sha256", "executable_sha256"}:
                categories.add("full_local_sha256")
                continue
            sanitized[normalized_key] = _remove_full_hashes(child_value, categories)
        return sanitized

    if isinstance(value, list):
        return [_remove_full_hashes(item, categories) for item in value]

    return value


def _sanitize_command_argv(value: Any, categories: set[str]) -> Any:
    if not isinstance(value, list):
        return value

    sanitized: list[Any] = []
    replace_next = False
    for item in value:
        if replace_next:
            sanitized.append(PROMPT_FROM_RAW_ARTIFACT)
            categories.add("prompt_duplication")
            replace_next = False
            continue

        if isinstance(item, str) and item in {"-p", "--prompt", "--prompt-file"}:
            sanitized.append(item)
            replace_next = True
            continue

        if isinstance(item, str) and item.startswith(
            ("-p=", "--prompt=", "--prompt-file=")
        ):
            sanitized.append(item.split("=", 1)[0] + "=" + PROMPT_FROM_RAW_ARTIFACT)
            categories.add("prompt_duplication")
            continue

        if item == "__PROMPT_FROM_RAW_ARTIFACT__":
            sanitized.append(PROMPT_FROM_RAW_ARTIFACT)
        else:
            sanitized.append(item)
    return sanitized


def _sanitize_json_artifact(path: Path, output_path: Path, categories: set[str]) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    sanitized = _remove_full_hashes(_sanitize_structured(data, categories), categories)

    if path.name == "runtime-command.json" and isinstance(sanitized, dict):
        sanitized["command_argv"] = _sanitize_command_argv(
            sanitized.get("command_argv"), categories
        )
        sanitized["prompt_placeholder"] = PROMPT_FROM_RAW_ARTIFACT

    write_json(output_path, sanitized)


def _sanitize_result_json(path: Path, output_path: Path, categories: set[str]) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    sanitized = _remove_full_hashes(_sanitize_structured(data, categories), categories)

    if isinstance(sanitized, dict):
        sanitized.pop(RUN_FINGERPRINT_FIELD, None)
        runtime = sanitized.get("runtime")
        if isinstance(runtime, dict):
            runtime["command"] = _sanitize_command_argv(runtime.get("command"), categories)

    write_json(output_path, sanitized)


def _is_known_artifact(relative_path: Path) -> bool:
    if relative_path.as_posix() in {
        "llmgauge-result.json",
        "runtime-command.json",
        "report.md",
        "scores.yaml",
    }:
        return True

    if not relative_path.parts or relative_path.parts[0] not in {
        "raw",
        "cleaned",
        "logs",
        "vram",
    }:
        return False

    return relative_path.suffix.lower() in {
        ".md",
        ".txt",
        ".json",
        ".yaml",
        ".yml",
        ".log",
    }


def _candidate_files(source_dir: Path) -> tuple[list[Path], list[str]]:
    selected: list[Path] = []
    omitted: list[str] = []
    for path in sorted(source_dir.rglob("*")):
        if path.is_symlink():
            omitted.append(path.relative_to(source_dir).as_posix())
            continue
        if not path.is_file():
            continue
        relative_path = path.relative_to(source_dir)
        if _is_known_artifact(relative_path):
            selected.append(relative_path)
        else:
            omitted.append(relative_path.as_posix())
    return selected, omitted


def _copy_or_transform(
    source_dir: Path,
    output_dir: Path,
    relative_path: Path,
    categories: set[str],
) -> str:
    source_path = source_dir / relative_path
    output_path = output_dir / relative_path
    if relative_path.name == "llmgauge-result.json":
        _sanitize_result_json(source_path, output_path, categories)
        return "transformed"

    if relative_path.suffix.lower() == ".json":
        _sanitize_json_artifact(source_path, output_path, categories)
        return "transformed"

    text = source_path.read_text(encoding="utf-8", errors="replace")
    sanitized = _sanitize_text(text, categories)
    write_text(output_path, sanitized)
    return "transformed" if sanitized != text else "copied"


def _destination_is_inside_source(source_dir: Path, output_dir: Path) -> bool:
    try:
        output_dir.relative_to(source_dir)
    except ValueError:
        return False
    return True


def _check_output_destination(source_dir: Path, output_dir: Path) -> bool:
    if source_dir == output_dir:
        raise ValueError("Output directory must differ from the source run directory")
    if _destination_is_inside_source(source_dir, output_dir):
        raise ValueError(
            "Public export destination cannot be inside the source run directory"
        )

    if output_dir.exists():
        if not output_dir.is_dir():
            raise ValueError(f"Output path is not a directory: {output_dir}")
        if any(output_dir.iterdir()):
            raise ValueError(f"Refusing to overwrite non-empty output directory: {output_dir}")
        return True
    return False


def _create_staging_dir(output_dir: Path) -> Path:
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    return Path(
        tempfile.mkdtemp(
            prefix=f"{_STAGING_PREFIX}{output_dir.name}-",
            dir=output_dir.parent,
        )
    )


def _finalize_staged_export(
    staging_dir: Path,
    output_dir: Path,
    *,
    existing_empty_destination: bool,
) -> None:
    if existing_empty_destination:
        output_dir.rmdir()
    staging_dir.rename(output_dir)


def _build_public_export(source_dir: Path, output_dir: Path) -> dict[str, Any]:
    categories: set[str] = set()
    selected, omitted = _candidate_files(source_dir)
    copied: list[str] = []
    transformed: list[str] = []
    for relative_path in selected:
        disposition = _copy_or_transform(
            source_dir,
            output_dir,
            relative_path,
            categories,
        )
        if disposition == "copied":
            copied.append(relative_path.as_posix())
        else:
            transformed.append(relative_path.as_posix())

    source_result = load_result_json(source_dir)
    manifest = {
        "schema_version": PUBLIC_EXPORT_SCHEMA_VERSION,
        "source_artifact_type": source_result.get("schema_version"),
        "source_run_fingerprint": source_result.get(RUN_FINGERPRINT_FIELD),
        "files_copied": sorted(copied),
        "files_transformed": sorted(transformed),
        "files_omitted": sorted(omitted),
        "redaction_categories": sorted(categories),
        "exported_at_utc": _utc_timestamp(),
        "claim_boundary": (
            "Export sanitization is not answer-quality validation. Review the "
            "public export before publication."
        ),
        "source_run_fingerprint_boundary": (
            "The source run fingerprint identifies the canonical private evidence. "
            "It does not authenticate transformed public-export bytes."
        ),
    }
    write_json(output_dir / PUBLIC_EXPORT_MANIFEST_FILENAME, manifest)

    exported_validation_errors = validate_result_dir(output_dir)
    if exported_validation_errors:
        raise ValueError(
            "Public export failed structural validation: "
            + "; ".join(exported_validation_errors)
        )
    return manifest


def export_public_run(source_dir: Path, output_dir: Path) -> dict[str, Any]:
    """Create a sanitized public derivative of one structurally valid run."""

    source_dir = source_dir.expanduser().resolve()
    output_dir = output_dir.expanduser().resolve()
    existing_empty_destination = _check_output_destination(source_dir, output_dir)

    validation_errors = validate_result_dir(source_dir)
    if validation_errors:
        raise ValueError(
            "Source result validation failed: " + "; ".join(validation_errors)
        )

    staging_dir = _create_staging_dir(output_dir)
    try:
        manifest = _build_public_export(source_dir, staging_dir)
        _finalize_staged_export(
            staging_dir,
            output_dir,
            existing_empty_destination=existing_empty_destination,
        )
    except Exception:
        shutil.rmtree(staging_dir, ignore_errors=True)
        if existing_empty_destination and not output_dir.exists():
            output_dir.mkdir(parents=True, exist_ok=True)
        raise
    return manifest
