from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


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
    return load_yaml_file(path)


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
    models = data.get("models", {})
    if not isinstance(models, dict):
        raise ValueError("Model profiles file field 'models' must be a mapping")

    return models


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
