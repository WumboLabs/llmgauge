from __future__ import annotations

from copy import deepcopy

import pytest

from llmgauge.core.sampling_profiles import (
    SamplingProfileError,
    canonical_settings_sha256,
    resolve_sampling_profile,
    validate_runtime_profile,
)


def test_builtin_profile_has_deterministic_canonical_identity() -> None:
    first = resolve_sampling_profile({}, "controlled-deterministic-v1")
    second = resolve_sampling_profile({}, "controlled-deterministic-v1")

    assert first == second
    assert first is not None
    assert first["profile_kind"] == "controlled"
    assert first["canonical_settings_sha256"] == canonical_settings_sha256(
        first["settings"]
    )


def test_custom_profile_requires_closed_canonical_settings() -> None:
    with pytest.raises(
        SamplingProfileError, match="must contain exactly supported keys"
    ):
        resolve_sampling_profile(
            {
                "sampling_profiles": {
                    "bad": {
                        "profile_version": "1",
                        "profile_kind": "controlled",
                        "settings": {"temperature": 0.0},
                    }
                }
            },
            "bad",
        )


def test_runtime_profile_rejects_hash_and_runtime_contradictions() -> None:
    profile = resolve_sampling_profile({}, "controlled-deterministic-v1")
    assert profile is not None
    evidence = {**profile, "overrides": []}
    runtime = deepcopy(profile["settings"])

    assert validate_runtime_profile(evidence, runtime) == []
    evidence["canonical_settings_sha256"] = "0" * 64
    assert "does not match settings" in validate_runtime_profile(evidence, runtime)[0]

    evidence["canonical_settings_sha256"] = profile["canonical_settings_sha256"]
    runtime["temperature"] = 0.8
    assert (
        "disagrees with runtime.temperature"
        in validate_runtime_profile(evidence, runtime)[0]
    )


def test_runtime_profile_allows_recorded_cli_override() -> None:
    profile = resolve_sampling_profile({}, "controlled-deterministic-v1")
    assert profile is not None
    evidence = {**profile, "overrides": ["temperature"]}
    runtime = {**profile["settings"], "temperature": 0.8}

    assert validate_runtime_profile(evidence, runtime) == []
