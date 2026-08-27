from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Any, Mapping

PROFILE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_PROFILE_KINDS = frozenset({"controlled", "vendor_aligned"})
_REASONING_MODES = frozenset({"off", "on", "auto", "default"})
_REASONING_EFFORTS = frozenset(
    {"default", "minimal", "low", "medium", "high", "xhigh", "max"}
)
_PROFILE_SETTING_KEYS = (
    "min_p",
    "reasoning_budget",
    "reasoning_effort",
    "reasoning_mode",
    "seed",
    "temperature",
    "top_k",
    "top_p",
)

_BUILTIN_PROFILES: dict[str, dict[str, Any]] = {
    "controlled-deterministic-v1": {
        "profile_version": "1",
        "profile_kind": "controlled",
        "settings": {
            "min_p": None,
            "reasoning_budget": None,
            "reasoning_effort": None,
            "reasoning_mode": "off",
            "seed": 1,
            "temperature": 0.0,
            "top_k": 0,
            "top_p": 1.0,
        },
    },
    "deepseek-r1-v1": {
        "profile_version": "1",
        "profile_kind": "vendor_aligned",
        "settings": {
            "min_p": None,
            "reasoning_budget": None,
            "reasoning_effort": None,
            "reasoning_mode": "default",
            "seed": None,
            "temperature": 0.6,
            "top_k": None,
            "top_p": 0.95,
        },
    },
    "gemma-4-instruct-v1": {
        "profile_version": "1",
        "profile_kind": "vendor_aligned",
        "settings": {
            "min_p": None,
            "reasoning_budget": None,
            "reasoning_effort": None,
            "reasoning_mode": "default",
            "seed": None,
            "temperature": 1.0,
            "top_k": 64,
            "top_p": 0.95,
        },
    },
    "qwen3-nonthinking-v1": {
        "profile_version": "1",
        "profile_kind": "vendor_aligned",
        "settings": {
            "min_p": 0.0,
            "reasoning_budget": None,
            "reasoning_effort": None,
            "reasoning_mode": "off",
            "seed": None,
            "temperature": 0.7,
            "top_k": 20,
            "top_p": 0.8,
        },
    },
    "qwen3-thinking-v1": {
        "profile_version": "1",
        "profile_kind": "vendor_aligned",
        "settings": {
            "min_p": 0.0,
            "reasoning_budget": None,
            "reasoning_effort": None,
            "reasoning_mode": "on",
            "seed": None,
            "temperature": 0.6,
            "top_k": 20,
            "top_p": 0.95,
        },
    },
}


def builtin_sampling_profile_ids() -> tuple[str, ...]:
    return tuple(_BUILTIN_PROFILES)


class SamplingProfileError(ValueError):
    """Raised when a reasoning/sampling profile is malformed or unavailable."""


def canonical_settings_bytes(settings: Mapping[str, Any]) -> bytes:
    return json.dumps(
        dict(settings),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def canonical_settings_sha256(settings: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_settings_bytes(settings)).hexdigest()


def _require_identifier(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not PROFILE_ID_RE.fullmatch(value):
        raise SamplingProfileError(
            f"{field} must match [A-Za-z0-9][A-Za-z0-9._-]{{0,127}}"
        )
    return value


def _finite_number(value: Any, *, field: str, minimum: float | None = None) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, int | float)
        or not math.isfinite(value)
    ):
        raise SamplingProfileError(f"{field} must be a finite number")
    resolved = float(value)
    if minimum is not None and resolved < minimum:
        raise SamplingProfileError(f"{field} must be at least {minimum:g}")
    return resolved


def _optional_int(value: Any, *, field: str, minimum: int | None = None) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise SamplingProfileError(f"{field} must be an integer or null")
    if minimum is not None and value < minimum:
        raise SamplingProfileError(f"{field} must be at least {minimum}")
    return value


def normalize_profile_settings(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise SamplingProfileError("settings must be an object")
    keys = set(value)
    expected = set(_PROFILE_SETTING_KEYS)
    if keys != expected:
        missing = sorted(expected - keys)
        unknown = sorted(keys - expected)
        details = []
        if missing:
            details.append(f"missing {', '.join(missing)}")
        if unknown:
            details.append(f"unsupported {', '.join(unknown)}")
        raise SamplingProfileError(
            "settings must contain exactly supported keys: " + "; ".join(details)
        )

    reasoning_mode = value["reasoning_mode"]
    if reasoning_mode not in _REASONING_MODES:
        raise SamplingProfileError(
            "settings.reasoning_mode must be off, on, auto, or default"
        )
    reasoning_effort = value["reasoning_effort"]
    if reasoning_effort is not None and reasoning_effort not in _REASONING_EFFORTS:
        raise SamplingProfileError(
            "settings.reasoning_effort must be a supported effort or null"
        )
    return {
        "min_p": (
            None
            if value["min_p"] is None
            else _finite_number(value["min_p"], field="settings.min_p", minimum=0)
        ),
        "reasoning_budget": _optional_int(
            value["reasoning_budget"], field="settings.reasoning_budget", minimum=-1
        ),
        "reasoning_effort": reasoning_effort,
        "reasoning_mode": reasoning_mode,
        "seed": _optional_int(value["seed"], field="settings.seed"),
        "temperature": _finite_number(
            value["temperature"], field="settings.temperature"
        ),
        "top_k": _optional_int(value["top_k"], field="settings.top_k", minimum=0),
        "top_p": _finite_number(value["top_p"], field="settings.top_p", minimum=0),
    }


def normalize_sampling_profile(
    profile_id: str,
    definition: Any,
    *,
    source: str,
) -> dict[str, Any]:
    _require_identifier(profile_id, field="profile_id")
    if source not in {"builtin", "config"}:
        raise SamplingProfileError("profile source must be builtin or config")
    if not isinstance(definition, Mapping):
        raise SamplingProfileError(f"sampling profile {profile_id!r} must be an object")
    expected = {"profile_version", "profile_kind", "settings"}
    if set(definition) != expected:
        raise SamplingProfileError(
            f"sampling profile {profile_id!r} must contain exactly: "
            "profile_version, profile_kind, settings"
        )
    profile_version = _require_identifier(
        definition["profile_version"], field="profile_version"
    )
    profile_kind = definition["profile_kind"]
    if profile_kind not in _PROFILE_KINDS:
        raise SamplingProfileError("profile_kind must be controlled or vendor_aligned")
    settings = normalize_profile_settings(definition["settings"])
    return {
        "profile_id": profile_id,
        "profile_version": profile_version,
        "profile_kind": profile_kind,
        "canonical_settings_sha256": canonical_settings_sha256(settings),
        "settings": settings,
        "source": source,
    }


def resolve_sampling_profile(
    config: Mapping[str, Any], profile_id: str | None
) -> dict[str, Any] | None:
    if profile_id is None:
        return None
    _require_identifier(profile_id, field="sampling_profile")
    configured = config.get("sampling_profiles")
    if configured is not None and not isinstance(configured, Mapping):
        raise SamplingProfileError("sampling_profiles must be a mapping")
    if profile_id in _BUILTIN_PROFILES:
        if configured is not None and profile_id in configured:
            raise SamplingProfileError(
                f"sampling profile {profile_id!r} cannot shadow a built-in profile"
            )
        return normalize_sampling_profile(
            profile_id, _BUILTIN_PROFILES[profile_id], source="builtin"
        )
    if not isinstance(configured, Mapping) or profile_id not in configured:
        raise SamplingProfileError(f"Sampling profile not found: {profile_id}")
    return normalize_sampling_profile(
        profile_id, configured[profile_id], source="config"
    )


def profile_runtime_settings(profile: Mapping[str, Any] | None) -> Mapping[str, Any]:
    if profile is None:
        return {}
    settings = profile.get("settings")
    if not isinstance(settings, Mapping):
        raise SamplingProfileError("resolved sampling profile settings are unavailable")
    return settings


def runtime_profile_evidence(
    profile: Mapping[str, Any] | None, overrides: list[str]
) -> dict[str, Any] | None:
    if profile is None:
        return None
    if any(key not in _PROFILE_SETTING_KEYS for key in overrides):
        raise SamplingProfileError("profile overrides contain an unsupported setting")
    return {**profile, "overrides": sorted(set(overrides))}


def validate_runtime_profile(value: Any, runtime: Mapping[str, Any]) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, Mapping):
        return ["runtime.profile must be an object"]
    expected = {
        "profile_id",
        "profile_version",
        "profile_kind",
        "canonical_settings_sha256",
        "settings",
        "source",
        "overrides",
    }
    if set(value) != expected:
        return ["runtime.profile must contain exactly the canonical profile fields"]
    try:
        normalized = normalize_sampling_profile(
            value["profile_id"],
            {
                "profile_version": value["profile_version"],
                "profile_kind": value["profile_kind"],
                "settings": value["settings"],
            },
            source=value["source"],
        )
    except SamplingProfileError as exc:
        return [f"runtime.profile is invalid: {exc}"]
    errors: list[str] = []
    if value["canonical_settings_sha256"] != normalized["canonical_settings_sha256"]:
        errors.append(
            "runtime.profile.canonical_settings_sha256 does not match settings"
        )
    overrides = value["overrides"]
    if (
        not isinstance(overrides, list)
        or any(
            not isinstance(key, str) or key not in _PROFILE_SETTING_KEYS
            for key in overrides
        )
        or overrides != sorted(set(overrides))
    ):
        errors.append("runtime.profile.overrides must be sorted supported setting keys")
        return errors
    for setting in _PROFILE_SETTING_KEYS:
        if (
            setting not in overrides
            and runtime.get(setting) != normalized["settings"][setting]
        ):
            errors.append(
                f"runtime.profile settings.{setting} disagrees with runtime.{setting}"
            )
    return errors
