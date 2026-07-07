from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from llmgauge.core.schemas import (
    format_validation_error,
    validate_llmgauge_config_document,
    validate_model_profiles_document,
)


def load_yaml_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Config file does not exist: {path}")

    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if data is None:
        return {}

    if not isinstance(data, dict):
        raise ValueError(f"Config file did not parse as a mapping: {path}")

    return data


def load_llmgauge_config(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}

    data = load_yaml_file(path)
    try:
        validate_llmgauge_config_document(data)
    except Exception as exc:
        raise ValueError(
            format_validation_error(exc, label="Invalid config file")
        ) from exc

    return data


def get_config_value(
    config: dict[str, Any], dotted_key: str, default: Any = None
) -> Any:
    current: Any = config
    for part in dotted_key.split("."):
        if not isinstance(current, dict) or part not in current:
            return default
        current = current[part]
    return current


def load_model_profiles(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}

    data = load_yaml_file(path)
    try:
        document = validate_model_profiles_document(data)
    except Exception as exc:
        raise ValueError(
            format_validation_error(exc, label="Invalid model profiles file")
        ) from exc

    return {
        name: entry.model_dump(exclude_none=True)
        for name, entry in document.models.items()
    }


def resolve_model_profile(
    profiles: dict[str, Any],
    profile_name: str | None,
) -> dict[str, Any]:
    if profile_name is None:
        return {}

    if profile_name not in profiles:
        raise KeyError(f"Model profile not found: {profile_name}")

    profile = profiles[profile_name]
    if not isinstance(profile, dict):
        raise ValueError(f"Model profile must be a mapping: {profile_name}")

    resolved = dict(profile)
    resolved["profile_name"] = profile_name
    return resolved


def coalesce(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None
