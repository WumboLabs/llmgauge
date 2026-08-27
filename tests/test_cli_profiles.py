from __future__ import annotations

import re

from typer.testing import CliRunner

from llmgauge.cli import app
from llmgauge.core import sampling_profiles
from llmgauge.core.sampling_profiles import (
    builtin_sampling_profile_ids,
    resolve_sampling_profile,
)

runner = CliRunner()
_CLI_ENV = {"COLUMNS": "200", "NO_COLOR": "1"}


def _plain(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def _invoke(*args: str):
    return runner.invoke(app, list(args), env=_CLI_ENV)


def test_profiles_list_shows_builtin_inventory_in_stable_order() -> None:
    first = _invoke("profiles", "list")
    second = _invoke("profiles", "list")

    assert first.exit_code == 0, first.output
    assert second.exit_code == 0, second.output
    output = _plain(first.output)
    assert output == _plain(second.output)
    assert "Profile ID" in output
    assert "Version" in output
    assert "Kind" in output
    assert "Source" in output

    profile_ids = builtin_sampling_profile_ids()
    for profile_id in profile_ids:
        assert profile_id in output

    profiles = [resolve_sampling_profile({}, profile_id) for profile_id in profile_ids]
    assert all(profile is not None for profile in profiles)
    expected_order = [
        profile["profile_id"]
        for profile in sorted(
            profiles,
            key=lambda profile: (
                profile["profile_kind"] != "controlled",
                profile["profile_kind"],
                profile["profile_id"],
            ),
        )
    ]
    positions = [output.index(profile_id) for profile_id in expected_order]
    assert positions == sorted(positions)
    assert "controlled" in output
    assert output.count("vendor_aligned") >= 4
    assert output.count("builtin") == len(profile_ids)


def test_profiles_show_controlled_definition() -> None:
    profile_id = "controlled-deterministic-v1"
    profile = resolve_sampling_profile({}, profile_id)
    assert profile is not None

    result = _invoke("profiles", "show", profile_id)

    assert result.exit_code == 0, result.output
    output = _plain(result.output)
    assert f"Profile ID: {profile_id}" in output
    assert "Version: 1" in output
    assert "Kind: controlled" in output
    assert "Source: builtin" in output
    assert profile["canonical_settings_sha256"] in output
    for setting in (
        "min_p: runtime default",
        "reasoning_budget: runtime default",
        "reasoning_effort: runtime default",
        "reasoning_mode: off",
        "seed: 1",
        "temperature: 0.0",
        "top_k: 0",
        "top_p: 1.0",
    ):
        assert setting in output
    assert "Claim boundary:" in output
    assert "does not prove semantic model reasoning or runtime behavior" in output
    assert "Qualification sources:" not in output


def test_profiles_show_vendor_definition_and_claim_boundary() -> None:
    profile_id = "qwen3-thinking-v1"
    profile = resolve_sampling_profile({}, profile_id)
    assert profile is not None

    result = _invoke("profiles", "show", profile_id)

    assert result.exit_code == 0, result.output
    output = _plain(result.output)
    assert f"Profile ID: {profile_id}" in output
    assert "Version: 1" in output
    assert "Kind: vendor_aligned" in output
    assert "Source: builtin" in output
    assert profile["canonical_settings_sha256"] in output
    for setting in (
        "min_p: 0.0",
        "reasoning_budget: runtime default",
        "reasoning_effort: runtime default",
        "reasoning_mode: on",
        "seed: runtime default",
        "temperature: 0.6",
        "top_k: 20",
        "top_p: 0.95",
    ):
        assert setting in output
    assert "operator-declared rather than verified" in output
    assert "not vendor endorsement" in output
    assert "vendor-hosted inference" in output
    assert "VENDOR_ALIGNED_SAMPLING_PROFILES.md" in output
    assert "compatible" not in output.lower()
    assert "best" not in output.lower()
    assert "optimal" not in output.lower()


def test_profiles_show_unknown_fails_cleanly() -> None:
    result = _invoke("profiles", "show", "absent-profile")

    assert result.exit_code == 2
    combined = (result.output or "") + (result.stderr or "")
    assert "Sampling profile not found: absent-profile" in _plain(combined)
    assert "Traceback" not in combined


def test_profiles_commands_follow_canonical_registry(monkeypatch) -> None:
    profile_id = "future-controlled-v2"
    monkeypatch.setitem(
        sampling_profiles._BUILTIN_PROFILES,
        profile_id,
        {
            "profile_version": "2",
            "profile_kind": "controlled",
            "settings": {
                "min_p": None,
                "reasoning_budget": None,
                "reasoning_effort": None,
                "reasoning_mode": "auto",
                "seed": 7,
                "temperature": 0.3,
                "top_k": 8,
                "top_p": 0.9,
            },
        },
    )

    listed = _invoke("profiles", "list")
    shown = _invoke("profiles", "show", profile_id)

    assert listed.exit_code == 0, listed.output
    assert profile_id in _plain(listed.output)
    assert shown.exit_code == 0, shown.output
    show_output = _plain(shown.output)
    assert "Version: 2" in show_output
    assert "reasoning_mode: auto" in show_output
    assert "temperature: 0.3" in show_output


def test_profiles_help_is_discoverable() -> None:
    root_help = _invoke("--help")
    group_help = _invoke("profiles", "--help")
    list_help = _invoke("profiles", "list", "--help")
    show_help = _invoke("profiles", "show", "--help")

    for result in (root_help, group_help, list_help, show_help):
        assert result.exit_code == 0, result.output
    assert "profiles" in _plain(root_help.output)
    group_output = _plain(group_help.output)
    assert "list" in group_output
    assert "show" in group_output
    assert "built-in reasoning/sampling profiles" in _plain(list_help.output)
    assert "exact requested controls" in _plain(show_help.output)
