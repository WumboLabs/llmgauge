from __future__ import annotations

import getpass
import json
import re
import shutil
import socket
import tempfile
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

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
_ABSOLUTE_PATH_RE = re.compile(r"(?<![A-Za-z0-9_:/#])/(?!/)[^\s\"'<>`]+")
_WINDOWS_PATH_RE = re.compile(r"(?i)(?<![A-Za-z0-9])(?:[a-z]:\\|\\\\)[^\s\"'<>`]+")
_FULL_HASH_SEGMENT_RE = re.compile(
    r"(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])", re.IGNORECASE
)
_PROVENANCE_FILENAME_KEYS = {"filename", "executable_filename"}
_PUBLIC_API_ROUTES = frozenset({"/version", "/v1/models", "/v1/chat/completions"})
_REASONING_MARKER_RE = re.compile(r"<\s*/?\s*think(?:\s[^>]*)?>", re.IGNORECASE)
_LOOPBACK_ENDPOINT_RE = re.compile(
    r"(?i)(?:https?://)?(?:127(?:\.\d{1,3}){3}|localhost|\[?::1\]?)(?::\d+)?"
)
_PRIVATE_REASONING_KEYS = frozenset(
    {
        "private_reasoning",
        "reasoning",
        "reasoning_content",
        "reasoning_delta",
        "reasoning_deltas",
        "reasoning_text",
        "redacted_thinking",
        "thinking",
    }
)
_GENERATED_TEXT_KEYS = frozenset(
    {"completion_text", "generated_text", "output_text", "response_text"}
)
_PRIVATE_TOKEN_ID_KEYS = frozenset(
    {
        "output_token_ids",
        "prompt_token_ids",
        "reasoning_token_ids",
        "return_token_ids",
        "token_ids",
    }
)
_PRIVATE_EMBEDDED_EVIDENCE_PREFIX = "_area4_"
_TTFT_METRIC_ID = "llmgauge.metric.v1.time_to_first_token"
_TTFT_PRIVATE_KEYS = frozenset(
    {
        "first_token",
        "first_token_channel",
        "first_token_elapsed_seconds",
        "first_token_event_index",
        "stream_evidence_path",
        "stream_terminal_state",
        "time_to_first_token_seconds",
    }
)
_TTFT_REPORT_PREFIXES = ("- TTFT", "- First token channel:")
_ENDPOINT_IDENTITY_PRIVATE_KEYS = frozenset(
    {
        "address",
        "host",
        "hostname",
        "ip",
        "port",
        "raw_url",
        "socket_address",
        "url",
    }
)
_ENDPOINT_VALUE_KEYS = frozenset(
    {
        "endpoint_address",
        "endpoint_host",
        "endpoint_port",
        "endpoint_url",
        "raw_url",
        "socket_address",
        "vllm_endpoint",
    }
)


def _local_usernames() -> tuple[str, ...]:
    usernames = {Path.home().name.strip()}
    try:
        usernames.add(getpass.getuser().strip())
    except OSError:
        pass
    return tuple(sorted(username for username in usernames if username))


_LOCAL_HOSTNAME = socket.gethostname().strip()
_LOCAL_USERNAMES = _local_usernames()


def _utc_timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _redact_local_identifier(
    text: str,
    identifier: str,
    replacement: str,
    category: str,
    categories: set[str],
) -> str:
    if len(identifier) < 3:
        return text
    pattern = re.compile(
        rf"(?<![A-Za-z0-9_-]){re.escape(identifier)}(?![A-Za-z0-9_-])",
        re.IGNORECASE,
    )
    sanitized, count = pattern.subn(replacement, text)
    if count:
        categories.add(category)
    return sanitized


def _sanitize_text(
    text: str,
    categories: set[str],
    *,
    endpoint_values: tuple[str, ...] = (),
    generated_output: bool = False,
) -> str:
    if generated_output and _REASONING_MARKER_RE.search(text):
        categories.add("generated_reasoning_omitted")
        return ""

    def replace_url(match: re.Match[str]) -> str:
        categories.add("credential_bearing_url")
        return "REDACTED_SECRET"

    def replace_secret(match: re.Match[str]) -> str:
        categories.add("secret_like_value")
        return f"{match.group(1)}REDACTED_SECRET"

    def replace_path(match: re.Match[str]) -> str:
        value = match.group(0)
        route = value.rstrip(".,;:!?)]}")
        if route in _PUBLIC_API_ROUTES:
            return value
        if value.startswith(("/home/", "/Users/", "/root/", "/private/")):
            categories.add("home_directory_path")
            return "REDACTED_HOME_PATH"
        categories.add("absolute_path")
        return "REDACTED_ABSOLUTE_PATH"

    text = _redact_local_identifier(
        text,
        _LOCAL_HOSTNAME,
        "REDACTED_HOSTNAME",
        "local_hostname",
        categories,
    )
    for username in _LOCAL_USERNAMES:
        text = _redact_local_identifier(
            text,
            username,
            "REDACTED_USERNAME",
            "local_username",
            categories,
        )
    for endpoint_value in endpoint_values:
        text = _redact_local_identifier(
            text,
            endpoint_value,
            "REDACTED_LOCAL_ENDPOINT",
            "local_endpoint_identity",
            categories,
        )
    text = _CREDENTIAL_URL_RE.sub(replace_url, text)
    text = _SECRET_VALUE_RE.sub(replace_secret, text)
    text = _ABSOLUTE_PATH_RE.sub(replace_path, text)
    text = _WINDOWS_PATH_RE.sub(replace_path, text)
    return text


def _sanitize_structured(
    value: Any,
    categories: set[str],
    key: str | None = None,
    *,
    endpoint_values: tuple[str, ...] = (),
) -> Any:
    if key is not None and _SECRET_KEY_RE.match(key):
        categories.add("secret_like_metadata")
        return "REDACTED_SECRET"

    if key in _PROVENANCE_FILENAME_KEYS and isinstance(value, str):
        sanitized, count = _FULL_HASH_SEGMENT_RE.subn("REDACTED_FULL_HASH", value)
        if count:
            categories.add("filename_full_sha256")
        return sanitized

    if isinstance(value, Mapping):
        sanitized: dict[str, Any] = {}
        for child_key, child_value in value.items():
            normalized_key = child_key if isinstance(child_key, str) else str(child_key)
            if normalized_key.startswith(_PRIVATE_EMBEDDED_EVIDENCE_PREFIX):
                categories.add("private_embedded_evidence_omitted")
                continue
            if normalized_key in _PRIVATE_REASONING_KEYS:
                categories.add("structured_reasoning_omitted")
                continue
            if normalized_key in _PRIVATE_TOKEN_ID_KEYS:
                categories.add("private_token_identifiers_omitted")
                continue
            if normalized_key in _ENDPOINT_VALUE_KEYS:
                categories.add("vllm_endpoint_field_omitted")
                continue
            sanitized_child = _sanitize_structured(
                child_value,
                categories,
                key=normalized_key,
                endpoint_values=endpoint_values,
            )
            if normalized_key == "endpoint_identity":
                sanitized_child = _sanitize_endpoint_identity(
                    sanitized_child,
                    categories,
                )
            sanitized[normalized_key] = sanitized_child
        return sanitized

    if isinstance(value, list):
        return [
            _sanitize_structured(
                item,
                categories,
                endpoint_values=endpoint_values,
            )
            for item in value
        ]

    if isinstance(value, str):
        return _sanitize_text(
            value,
            categories,
            endpoint_values=endpoint_values,
            generated_output=(
                key in _GENERATED_TEXT_KEYS
                or _REASONING_MARKER_RE.search(value) is not None
            ),
        )

    if (
        isinstance(value, int)
        and not isinstance(value, bool)
        and str(value) in endpoint_values
    ):
        categories.add("local_endpoint_identity")
        return "REDACTED_LOCAL_ENDPOINT"

    return value


def _sanitize_public_ttft(value: Any, categories: set[str]) -> Any:
    """Remove every admitted V1 TTFT projection from structured public data."""
    omit = object()

    def visit(item: Any, *, key: str | None = None) -> Any:
        if key in _TTFT_PRIVATE_KEYS:
            categories.add("area4_ttft_omitted")
            categories.add("vllm_stream_evidence_omitted")
            return omit

        if isinstance(item, Mapping):
            if item.get("metric_id") == _TTFT_METRIC_ID:
                categories.add("area4_ttft_omitted")
                return omit
            sanitized: dict[str, Any] = {}
            for child_key, child_value in item.items():
                normalized_key = (
                    child_key if isinstance(child_key, str) else str(child_key)
                )
                child = visit(child_value, key=normalized_key)
                if child is not omit:
                    sanitized[normalized_key] = child
            return sanitized

        if isinstance(item, list):
            sanitized_items: list[Any] = []
            for child_value in item:
                child = visit(child_value)
                if child is not omit:
                    sanitized_items.append(child)
            return sanitized_items

        return item

    sanitized = visit(value)
    return None if sanitized is omit else sanitized


def _record_endpoint_value(value: Any, private_values: set[str]) -> None:
    if isinstance(value, bool) or value is None:
        return
    if isinstance(value, int):
        private_values.add(str(value))
        return
    if not isinstance(value, str):
        return
    text = value.strip()
    if len(text) < 3:
        return
    private_values.add(text)
    if "://" not in text:
        return
    try:
        parsed = urlsplit(text)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError:
        return
    if hostname:
        private_values.add(hostname)
    if port is not None:
        private_values.add(str(port))
        if hostname:
            private_values.add(f"{hostname}:{port}")
    if parsed.netloc:
        private_values.add(parsed.netloc)


def _collect_endpoint_values(
    value: Any,
    private_values: set[str],
    *,
    in_endpoint_identity: bool = False,
) -> None:
    if isinstance(value, Mapping):
        for child_key, child_value in value.items():
            normalized_key = child_key if isinstance(child_key, str) else str(child_key)
            child_in_identity = (
                in_endpoint_identity or normalized_key == "endpoint_identity"
            )
            if (
                child_in_identity and normalized_key in _ENDPOINT_IDENTITY_PRIVATE_KEYS
            ) or normalized_key in _ENDPOINT_VALUE_KEYS:
                _record_endpoint_value(child_value, private_values)
            _collect_endpoint_values(
                child_value,
                private_values,
                in_endpoint_identity=child_in_identity,
            )
        return
    if isinstance(value, list):
        for child_value in value:
            _collect_endpoint_values(
                child_value,
                private_values,
                in_endpoint_identity=in_endpoint_identity,
            )


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


def _project_public_checkpoint_identity(data: Any, categories: set[str]) -> Any:
    """Replace private checkpoint-directory provenance with a public projection.

    Directory provenance is content-default-deny for public export: the whole
    private ``model.provenance`` block (ordered manifest entries, full
    per-file SHA-256 values, the full manifest fingerprint, and any reason
    strings that may quote local filenames) is removed and replaced by a
    bounded ``model.checkpoint_identity`` projection carrying only shortened
    fingerprints, statuses, and sanitized descriptive identifiers. The
    private source directory is never mutated.
    """

    if not isinstance(data, dict):
        return data
    model = data.get("model")
    if not isinstance(model, dict):
        return data
    provenance = model.get("provenance")
    if (
        not isinstance(provenance, dict)
        or provenance.get("provenance_kind") != "checkpoint_directory_manifest"
    ):
        return data

    categories.add("private_checkpoint_manifest_omitted")

    def _short_fingerprint(value: Any) -> str | None:
        return value if isinstance(value, str) and value.startswith("sha256:") else None

    tokenizer_identity = provenance.get("tokenizer_identity")
    tokenizer_identity = (
        tokenizer_identity if isinstance(tokenizer_identity, dict) else {}
    )
    template_identity = provenance.get("chat_template_identity")
    template_identity = template_identity if isinstance(template_identity, dict) else {}
    quantization = provenance.get("checkpoint_quantization")
    quantization = quantization if isinstance(quantization, dict) else {}

    projection: dict[str, Any] = {
        "source_type": provenance.get("source_type"),
        "provenance_kind": provenance.get("provenance_kind"),
        "status": provenance.get("status"),
        "public_fingerprint": _short_fingerprint(provenance.get("public_fingerprint")),
        "entry_count": provenance.get("entry_count"),
        "weight_file_count": provenance.get("weight_file_count"),
        "architecture": provenance.get("architecture"),
        "model_type": provenance.get("model_type"),
        "repository_id": provenance.get("repository_id"),
        "revision": provenance.get("revision"),
        "repository_id_source": provenance.get("repository_id_source"),
        "fingerprint_eligible": provenance.get("fingerprint_eligible"),
        "tokenizer_identity": {
            "status": tokenizer_identity.get("status"),
            "public_fingerprint": _short_fingerprint(
                tokenizer_identity.get("public_fingerprint")
            ),
        },
        "chat_template_identity": {
            "status": template_identity.get("status"),
            "selection_method": template_identity.get("selection_method"),
            "public_fingerprint": _short_fingerprint(
                template_identity.get("public_fingerprint")
            ),
        },
        "checkpoint_quantization": {
            "status": quantization.get("status"),
            "method": quantization.get("method"),
        },
        "effective_quantization_status": "unavailable",
    }
    warnings = provenance.get("warnings")
    if isinstance(warnings, list):
        projection["warnings"] = [
            warning for warning in warnings if isinstance(warning, str)
        ]
    model.pop("provenance", None)
    model["checkpoint_identity"] = projection
    return data


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


def _sanitize_json_artifact(
    path: Path,
    output_path: Path,
    categories: set[str],
    endpoint_values: tuple[str, ...],
) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    sanitized = _sanitize_public_ttft(data, categories)
    sanitized = _sanitize_structured(
        sanitized,
        categories,
        endpoint_values=endpoint_values,
    )
    sanitized = _remove_full_hashes(sanitized, categories)

    if path.name == "runtime-command.json" and isinstance(sanitized, dict):
        sanitized["command_argv"] = _sanitize_command_argv(
            sanitized.get("command_argv"), categories
        )
        sanitized["prompt_placeholder"] = PROMPT_FROM_RAW_ARTIFACT

    if path.name == "vllm-runtime-evidence.json" and isinstance(sanitized, dict):
        if "endpoint_identity" in sanitized:
            sanitized["endpoint_identity"] = _sanitize_endpoint_identity(
                sanitized.get("endpoint_identity"),
                categories,
            )
        for key in (
            "address",
            "endpoint_host",
            "endpoint_port",
            "endpoint_url",
            "headers",
            "host",
            "hostname",
            "ip",
            "port",
            "proxy",
            "raw_url",
            "response_body",
            "socket_address",
            "url",
            "vllm_endpoint",
        ):
            if key in sanitized:
                sanitized.pop(key, None)
                categories.add("vllm_sensitive_evidence_field")

    if (
        path.parent.name == "request"
        and path.suffix.lower() == ".json"
        and isinstance(sanitized, dict)
    ):
        if "endpoint_identity" in sanitized:
            sanitized["endpoint_identity"] = _sanitize_endpoint_identity(
                sanitized.get("endpoint_identity"),
                categories,
            )
        for key in (
            "address",
            "endpoint_host",
            "endpoint_port",
            "endpoint_url",
            "headers",
            "host",
            "hostname",
            "ip",
            "port",
            "proxy",
            "raw_url",
            "request_body",
            "response_body",
            "socket_address",
            "url",
            "vllm_endpoint",
        ):
            if key in sanitized:
                sanitized.pop(key, None)
                categories.add("vllm_sensitive_request_field")

    write_json(output_path, sanitized)


def _sanitize_endpoint_identity(value: Any, categories: set[str]) -> Any:
    """Keep only coarse, non-identifying endpoint methodology."""
    if not isinstance(value, dict):
        if value is not None:
            categories.add("vllm_endpoint_field_omitted")
        return {}
    allowed = {
        "scheme": value.get("scheme"),
        "loopback_class": value.get("loopback_class"),
        "proxy_bypass_policy": value.get("proxy_bypass_policy"),
    }
    for key in value:
        if key not in allowed:
            categories.add("vllm_endpoint_field_omitted")
    return {key: item for key, item in allowed.items() if item is not None}


def _sanitize_vllm_runtime_fields(
    runtime: dict[str, Any], categories: set[str]
) -> None:
    if "endpoint_identity" in runtime:
        runtime["endpoint_identity"] = _sanitize_endpoint_identity(
            runtime.get("endpoint_identity"),
            categories,
        )
    for key in (
        "address",
        "endpoint_address",
        "endpoint_host",
        "endpoint_port",
        "endpoint_url",
        "host",
        "hostname",
        "ip",
        "port",
        "raw_url",
        "socket_address",
        "vllm_endpoint",
        "headers",
        "proxy",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "NO_PROXY",
    ):
        if key in runtime:
            runtime.pop(key, None)
            categories.add("vllm_sensitive_runtime_field")


def _sanitize_result_json(
    path: Path,
    output_path: Path,
    categories: set[str],
    endpoint_values: tuple[str, ...],
) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    data = _project_public_checkpoint_identity(data, categories)
    sanitized = _sanitize_public_ttft(data, categories)
    sanitized = _sanitize_structured(
        sanitized,
        categories,
        endpoint_values=endpoint_values,
    )
    sanitized = _remove_full_hashes(sanitized, categories)

    if isinstance(sanitized, dict):
        sanitized.pop(RUN_FINGERPRINT_FIELD, None)
        runtime = sanitized.get("runtime")
        if isinstance(runtime, dict):
            runtime["command"] = _sanitize_command_argv(
                runtime.get("command"), categories
            )
            _sanitize_vllm_runtime_fields(runtime, categories)
            backend_provenance = runtime.get("backend_provenance")
            if isinstance(backend_provenance, dict) and "endpoint_identity" in (
                backend_provenance
            ):
                backend_provenance["endpoint_identity"] = _sanitize_endpoint_identity(
                    backend_provenance.get("endpoint_identity"),
                    categories,
                )

    write_json(output_path, sanitized)


def _is_known_artifact(relative_path: Path) -> bool:
    if relative_path.as_posix() in {
        "llmgauge-result.json",
        "runtime-command.json",
        "vllm-runtime-evidence.json",
        "report.md",
        "scores.yaml",
    }:
        return True

    if not relative_path.parts or relative_path.parts[0] not in {
        "raw",
        "cleaned",
        "logs",
        "vram",
        "request",
        "native",
    }:
        return False

    # Private raw stream evidence (token IDs, content deltas, reasoning text)
    # is never projected into public export.
    if relative_path.parts[0] == "request" and relative_path.name.endswith(
        ".stream.json"
    ):
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


def _source_endpoint_values(
    source_dir: Path,
    selected: list[Path],
) -> tuple[str, ...]:
    private_values: set[str] = set()
    for relative_path in selected:
        if relative_path.suffix.lower() != ".json":
            continue
        data = json.loads((source_dir / relative_path).read_text(encoding="utf-8"))
        _collect_endpoint_values(data, private_values)
    return tuple(sorted(private_values, key=lambda item: (-len(item), item)))


def _prompt_artifact_paths(
    source_result: Mapping[str, Any],
    field_names: tuple[str, ...],
) -> frozenset[str]:
    paths: set[str] = set()
    prompt_results = source_result.get("results")
    if not isinstance(prompt_results, list):
        return frozenset()
    for prompt_result in prompt_results:
        if not isinstance(prompt_result, Mapping):
            continue
        for field_name in field_names:
            value = prompt_result.get(field_name)
            if isinstance(value, str) and value:
                paths.add(Path(value).as_posix())
    return frozenset(paths)


def _strip_ttft_report_lines(text: str) -> str:
    """Remove TTFT presentation lines from a private report for public export."""
    keep: list[str] = []
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        if stripped.startswith(_TTFT_REPORT_PREFIXES):
            continue
        keep.append(line)
    return "".join(keep)


def _copy_or_transform(
    source_dir: Path,
    output_dir: Path,
    relative_path: Path,
    categories: set[str],
    endpoint_values: tuple[str, ...],
    raw_prompt_paths: frozenset[str],
    generated_output_paths: frozenset[str],
) -> str:
    source_path = source_dir / relative_path
    output_path = output_dir / relative_path
    if relative_path.name == "llmgauge-result.json":
        _sanitize_result_json(
            source_path,
            output_path,
            categories,
            endpoint_values,
        )
        return "transformed"

    if relative_path.suffix.lower() == ".json":
        _sanitize_json_artifact(
            source_path,
            output_path,
            categories,
            endpoint_values,
        )
        return "transformed"

    original = source_path.read_text(encoding="utf-8", errors="replace")
    text = original
    if relative_path.name == "report.md":
        text = _strip_ttft_report_lines(text)
        if text != original:
            categories.add("area4_ttft_omitted")
    relative_path_text = relative_path.as_posix()
    sanitized = _sanitize_text(
        text,
        categories,
        endpoint_values=endpoint_values,
        generated_output=(
            relative_path_text in generated_output_paths
            or relative_path_text not in raw_prompt_paths
        ),
    )
    write_text(output_path, sanitized)
    return "transformed" if sanitized != original else "copied"


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
            raise ValueError(
                f"Refusing to overwrite non-empty output directory: {output_dir}"
            )
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


def _manifest_path_set(
    manifest: Mapping[str, Any],
    key: str,
    errors: list[str],
) -> set[str]:
    value = manifest.get(key)
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        errors.append(f"public export manifest {key} must be a list of strings")
        return set()
    return set(value)


def _scan_public_structured(
    value: Any,
    *,
    location: str,
    errors: list[str],
    in_endpoint_identity: bool = False,
) -> None:
    if isinstance(value, Mapping):
        if value.get("metric_id") == _TTFT_METRIC_ID:
            errors.append(f"public export TTFT metric projection remains at {location}")
        if value.get("provenance_kind") == "checkpoint_directory_manifest":
            for private_key in ("manifest", "manifest_sha256"):
                if private_key in value:
                    errors.append(
                        "public export private checkpoint manifest evidence "
                        f"remains at {location}.{private_key}"
                    )
        for child_key, child_value in value.items():
            normalized_key = child_key if isinstance(child_key, str) else str(child_key)
            child_location = f"{location}.{normalized_key}"
            if normalized_key == "manifest_sha256":
                errors.append(
                    "public export private checkpoint manifest hash remains at "
                    f"{child_location}"
                )
            if normalized_key.startswith(_PRIVATE_EMBEDDED_EVIDENCE_PREFIX):
                errors.append(
                    "public export embedded private evidence remains at "
                    f"{child_location}"
                )
            if normalized_key in _TTFT_PRIVATE_KEYS:
                errors.append(
                    f"public export TTFT projection remains at {child_location}"
                )
            if normalized_key in _PRIVATE_REASONING_KEYS:
                errors.append(
                    f"public export structured reasoning remains at {child_location}"
                )
            if normalized_key in _PRIVATE_TOKEN_ID_KEYS:
                errors.append(
                    f"public export private token IDs remain at {child_location}"
                )
            child_in_endpoint_identity = (
                in_endpoint_identity or normalized_key == "endpoint_identity"
            )
            if (
                child_in_endpoint_identity
                and normalized_key in _ENDPOINT_IDENTITY_PRIVATE_KEYS
            ) or normalized_key in _ENDPOINT_VALUE_KEYS:
                errors.append(
                    f"public export local endpoint identity remains at {child_location}"
                )
            _scan_public_structured(
                child_value,
                location=child_location,
                errors=errors,
                in_endpoint_identity=child_in_endpoint_identity,
            )
        return

    if isinstance(value, list):
        for index, child_value in enumerate(value):
            _scan_public_structured(
                child_value,
                location=f"{location}[{index}]",
                errors=errors,
                in_endpoint_identity=in_endpoint_identity,
            )
        return

    if isinstance(value, str) and _REASONING_MARKER_RE.search(value):
        errors.append(f"public export generated reasoning marker remains at {location}")


def validate_public_export_privacy(
    result_dir: Path,
    result_data: Mapping[str, Any],
) -> list[str]:
    """Validate represented V1 public-export privacy and manifest claims."""
    manifest_path = result_dir / PUBLIC_EXPORT_MANIFEST_FILENAME
    if not manifest_path.exists():
        return []

    errors: list[str] = []
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ["public export manifest is not readable valid JSON"]
    if not isinstance(manifest, dict):
        return ["public export manifest must be a JSON object"]
    if manifest.get("schema_version") != PUBLIC_EXPORT_SCHEMA_VERSION:
        errors.append(
            "public export manifest schema_version must be "
            f"{PUBLIC_EXPORT_SCHEMA_VERSION}"
        )

    copied = _manifest_path_set(manifest, "files_copied", errors)
    transformed = _manifest_path_set(manifest, "files_transformed", errors)
    omitted = _manifest_path_set(manifest, "files_omitted", errors)
    _manifest_path_set(manifest, "redaction_categories", errors)
    if copied & transformed:
        errors.append("public export manifest copies and transforms the same file")
    if (copied | transformed) & omitted:
        errors.append("public export manifest both includes and omits the same file")

    represented = copied | transformed
    actual: set[str] = set()
    for path in result_dir.rglob("*"):
        if path.is_symlink():
            errors.append(
                "public export derivative contains a symbolic link: "
                f"{path.relative_to(result_dir).as_posix()}"
            )
            continue
        if not path.is_file():
            continue
        relative_path = path.relative_to(result_dir).as_posix()
        if relative_path != PUBLIC_EXPORT_MANIFEST_FILENAME:
            actual.add(relative_path)

    for relative_path in sorted(represented - actual):
        errors.append(f"public export manifest includes missing file: {relative_path}")
    for relative_path in sorted(actual - represented):
        errors.append(f"public export manifest omits represented file: {relative_path}")
    for relative_path in sorted(omitted & actual):
        errors.append(
            f"public export manifest claims omitted file is present: {relative_path}"
        )

    raw_prompt_paths = _prompt_artifact_paths(result_data, ("raw_prompt_path",))
    generated_output_paths = _prompt_artifact_paths(
        result_data,
        ("raw_output_path", "cleaned_output_path"),
    )
    for relative_path in sorted(actual):
        path = result_dir / relative_path
        if path.name.endswith(".stream.json"):
            errors.append(
                f"public export private stream artifact remains: {relative_path}"
            )
        if path.suffix.lower() == ".json":
            try:
                structured = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                errors.append(
                    f"public export represented JSON is invalid: {relative_path}"
                )
                continue
            _scan_public_structured(
                structured,
                location=relative_path,
                errors=errors,
            )
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        reasoning_sensitive = (
            relative_path in generated_output_paths
            or relative_path not in raw_prompt_paths
        )
        if reasoning_sensitive and _REASONING_MARKER_RE.search(text):
            errors.append(
                f"public export generated reasoning marker remains in {relative_path}"
            )
        if relative_path == "report.md":
            if _strip_ttft_report_lines(text) != text:
                errors.append("public export TTFT report projection remains")
            if _LOOPBACK_ENDPOINT_RE.search(text):
                errors.append(
                    "public export local endpoint identity remains in report.md"
                )

    return errors


def _build_public_export(source_dir: Path, output_dir: Path) -> dict[str, Any]:
    categories: set[str] = set()
    source_result = load_result_json(source_dir)
    selected, omitted = _candidate_files(source_dir)
    endpoint_values = _source_endpoint_values(source_dir, selected)
    raw_prompt_paths = _prompt_artifact_paths(source_result, ("raw_prompt_path",))
    generated_output_paths = _prompt_artifact_paths(
        source_result,
        ("raw_output_path", "cleaned_output_path"),
    )
    copied: list[str] = []
    transformed: list[str] = []
    for relative_path in selected:
        disposition = _copy_or_transform(
            source_dir,
            output_dir,
            relative_path,
            categories,
            endpoint_values,
            raw_prompt_paths,
            generated_output_paths,
        )
        if disposition == "copied":
            copied.append(relative_path.as_posix())
        else:
            transformed.append(relative_path.as_posix())
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
    source_result = load_result_json(source_dir)
    from llmgauge.core.agent_harness import require_native_result

    require_native_result(source_result, consumer="Public export")

    if source_result.get("transcript") is not None:
        raise ValueError(
            "Native multi-turn public export is not implemented; current "
            "single-turn sanitization cannot reinterpret transcript evidence"
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
