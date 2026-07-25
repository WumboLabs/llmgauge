from collections.abc import Callable
from pathlib import Path
import os
from typing import Any

import pytest
import yaml

from llmgauge.core.suite import (
    NormalizedSuite,
    SuiteDefinitionError,
    load_normalized_suite,
    load_suite,
)


def _prompt(prompt_id: str, *, fixture: bool = False) -> dict[str, Any]:
    return {
        "id": prompt_id,
        "file": f"prompts/{prompt_id}.txt",
        "primary_capability": "instruction-following",
        "secondary_stressors": [],
        "scoring": {
            "role": "manual",
            "manual_rubric": {"id": "default-manual-v0", "version": "0.1.0"},
        },
        "fixtures": (
            [
                {
                    "id": "fixture-data-v0",
                    "version": "0.1.0",
                    "path": "fixtures/data.json",
                }
            ]
            if fixture
            else []
        ),
    }


def _profile_manifest() -> dict[str, Any]:
    return {
        "schema_version": "llmgauge.suite.v0",
        "suite_id": "profile-suite-v1",
        "suite_version": "0.1.0",
        "title": "Profile suite",
        "default_profile": "core",
        "profiles": {
            "core": {"prompt_ids": ["prompt-a", "prompt-b", "prompt-c"]},
            "smoke": {"prompt_ids": ["prompt-a", "prompt-c"]},
        },
        "prompts": [
            _prompt("prompt-a", fixture=True),
            _prompt("prompt-b"),
            _prompt("prompt-c"),
        ],
        "extension": {"preserved": [1, 2]},
    }


def _write_suite(root: Path, manifest: dict[str, Any]) -> Path:
    root.mkdir(parents=True)
    (root / "suite.yaml").write_text(yaml.safe_dump(manifest), encoding="utf-8")
    for prompt in manifest["prompts"]:
        prompt_path = root / prompt["file"]
        prompt_path.parent.mkdir(parents=True, exist_ok=True)
        prompt_path.write_text(f"source for {prompt['id']}\n", encoding="utf-8")
        for fixture in prompt.get("fixtures", []):
            fixture_path = root / fixture["path"]
            fixture_path.parent.mkdir(parents=True, exist_ok=True)
            fixture_path.write_text('{"fixture": true}\n', encoding="utf-8")
    return root


def _profile_suite(tmp_path: Path) -> Path:
    return _write_suite(tmp_path / "suite", _profile_manifest())


def _portable_identity(suite: NormalizedSuite) -> tuple[Any, ...]:
    return (
        suite.schema_version,
        suite.suite_id,
        suite.suite_version,
        suite.canonical_prompt_ids,
        tuple(suite.profiles.items()),
        suite.default_profile,
        suite.selected_profile,
        suite.selection_kind,
        suite.selected_prompt_ids,
        tuple(
            (
                prompt.id,
                prompt.file,
                tuple(
                    (fixture.id, fixture.version, fixture.path)
                    for fixture in prompt.fixtures
                ),
            )
            for prompt in suite.prompts
        ),
    )


def test_legacy_suite_defaults_to_all_prompts_in_manifest_order() -> None:
    suite_dir = Path("suites/core-v1")
    raw = load_suite(suite_dir)

    normalized = load_normalized_suite(suite_dir)

    expected = tuple(prompt["id"] for prompt in raw["prompts"])
    assert normalized.canonical_prompt_ids == expected
    assert normalized.selected_prompt_ids == expected
    assert normalized.profiles == {}
    assert normalized.default_profile is None
    assert normalized.selected_profile is None
    assert normalized.selection_kind == "legacy-all"
    assert not normalized.is_complete_named_profile
    assert not normalized.is_custom_subset
    assert normalized.selected_prompts == normalized.prompts


def test_profile_aware_suite_selects_declared_default(tmp_path: Path) -> None:
    normalized = load_normalized_suite(_profile_suite(tmp_path))

    assert normalized.selected_profile == "core"
    assert normalized.selection_kind == "profile"
    assert normalized.is_complete_named_profile
    assert normalized.selected_prompt_ids == ("prompt-a", "prompt-b", "prompt-c")


def test_explicit_profile_preserves_exact_declared_order(tmp_path: Path) -> None:
    normalized = load_normalized_suite(_profile_suite(tmp_path), profile="smoke")

    assert normalized.canonical_prompt_ids == ("prompt-a", "prompt-b", "prompt-c")
    assert normalized.profiles["smoke"] == ("prompt-a", "prompt-c")
    assert normalized.selected_prompt_ids == ("prompt-a", "prompt-c")
    assert tuple(prompt.id for prompt in normalized.selected_prompts) == (
        "prompt-a",
        "prompt-c",
    )
    assert normalized.selected_prompts[0] is normalized.prompts[0]


def test_unknown_profile_fails_without_fallback(tmp_path: Path) -> None:
    with pytest.raises(SuiteDefinitionError, match="unknown-profile"):
        load_normalized_suite(_profile_suite(tmp_path), profile="missing")


def test_profile_request_against_legacy_suite_fails() -> None:
    with pytest.raises(SuiteDefinitionError, match="legacy-profile-selection"):
        load_normalized_suite(Path("suites/core-v1"), profile="core")


def test_custom_subset_is_disclosed_and_preserves_canonical_order(
    tmp_path: Path,
) -> None:
    normalized = load_normalized_suite(
        _profile_suite(tmp_path), prompt_ids=("prompt-a", "prompt-c")
    )

    assert normalized.selected_profile is None
    assert normalized.selection_kind == "custom"
    assert normalized.is_custom_subset
    assert not normalized.is_complete_named_profile
    assert normalized.selected_prompt_ids == ("prompt-a", "prompt-c")


@pytest.mark.parametrize(
    ("prompt_ids", "profile", "expected"),
    [
        ((), None, "custom-selection-empty"),
        (("prompt-a", "prompt-a"), None, "custom-selection-duplicate"),
        (("prompt-a", "missing"), None, "custom-selection-unknown"),
        (("prompt-c", "prompt-a"), None, "custom-selection-order"),
        (("prompt-a",), "core", "selection-conflict"),
    ],
)
def test_invalid_custom_subsets_fail_closed(
    tmp_path: Path,
    prompt_ids: tuple[str, ...],
    profile: str | None,
    expected: str,
) -> None:
    with pytest.raises(SuiteDefinitionError, match=expected):
        load_normalized_suite(
            _profile_suite(tmp_path), profile=profile, prompt_ids=prompt_ids
        )


def test_prompt_and_fixture_references_resolve_without_losing_portable_paths(
    tmp_path: Path,
) -> None:
    normalized = load_normalized_suite(_profile_suite(tmp_path))
    prompt = normalized.prompts[0]
    fixture = prompt.fixtures[0]

    assert prompt.file == "prompts/prompt-a.txt"
    assert prompt.resolved_file.read_bytes() == b"source for prompt-a\n"
    assert prompt.resolved_file.is_relative_to(normalized.suite_root)
    assert fixture.path == "fixtures/data.json"
    assert fixture.resolved_path.read_bytes() == b'{"fixture": true}\n'
    assert fixture.resolved_path.is_relative_to(normalized.suite_root)
    assert normalized.metadata["extension"]["preserved"] == (1, 2)


@pytest.mark.parametrize("target_kind", ["missing", "directory", "fifo"])
def test_non_regular_prompt_targets_fail_closed(
    tmp_path: Path, target_kind: str
) -> None:
    suite_dir = _profile_suite(tmp_path)
    target = suite_dir / "prompts/prompt-a.txt"
    target.unlink()
    if target_kind == "directory":
        target.mkdir()
    elif target_kind == "fifo":
        os.mkfifo(target)

    expected = (
        "missing-resource" if target_kind == "missing" else "non-regular-resource"
    )
    with pytest.raises(SuiteDefinitionError, match=expected):
        load_normalized_suite(suite_dir)


def test_missing_fixture_target_fails_closed(tmp_path: Path) -> None:
    suite_dir = _profile_suite(tmp_path)
    (suite_dir / "fixtures/data.json").unlink()

    with pytest.raises(SuiteDefinitionError, match="missing-resource"):
        load_normalized_suite(suite_dir)


@pytest.mark.parametrize(
    "unsafe_path",
    [
        "/tmp/prompt.txt",
        "../prompt.txt",
        "prompts/../prompt.txt",
        "https://example.invalid/prompt.txt",
        "C:/prompt.txt",
        "prompts\\prompt.txt",
        "prompts//prompt.txt",
        "./prompts/prompt.txt",
    ],
)
def test_unsafe_prompt_paths_fail_lexically(tmp_path: Path, unsafe_path: str) -> None:
    manifest = _profile_manifest()
    manifest["prompts"][0]["file"] = unsafe_path
    suite_dir = _write_suite(tmp_path / "suite", manifest)

    with pytest.raises(SuiteDefinitionError, match="invalid-relative-path"):
        load_normalized_suite(suite_dir)


def test_symlink_escape_fails_after_resolution(tmp_path: Path) -> None:
    suite_dir = _profile_suite(tmp_path)
    outside = tmp_path / "outside.txt"
    outside.write_text("private\n", encoding="utf-8")
    prompt_path = suite_dir / "prompts/prompt-a.txt"
    prompt_path.unlink()
    prompt_path.symlink_to(outside)

    with pytest.raises(SuiteDefinitionError, match="symlink-escape") as exc_info:
        load_normalized_suite(suite_dir)

    assert str(outside) not in str(exc_info.value)


def test_editable_and_packaged_mirrors_have_same_portable_normalization() -> None:
    editable = load_normalized_suite(Path("suites/core-v1"))
    packaged = load_normalized_suite(Path("src/llmgauge/builtin_suites/core-v1"))

    assert editable.suite_root != packaged.suite_root
    assert _portable_identity(editable) == _portable_identity(packaged)
    assert [prompt.resolved_file.read_bytes() for prompt in editable.prompts] == [
        prompt.resolved_file.read_bytes() for prompt in packaged.prompts
    ]


def test_profile_and_fixture_identity_is_portable_across_physical_roots(
    tmp_path: Path,
) -> None:
    manifest = _profile_manifest()
    editable = load_normalized_suite(
        _write_suite(tmp_path / "editable" / "profile-suite-v1", manifest),
        profile="smoke",
    )
    packaged = load_normalized_suite(
        _write_suite(tmp_path / "package" / "profile-suite-v1", manifest),
        profile="smoke",
    )

    assert editable.suite_root != packaged.suite_root
    assert _portable_identity(editable) == _portable_identity(packaged)
    assert [prompt.resolved_file.read_bytes() for prompt in editable.prompts] == [
        prompt.resolved_file.read_bytes() for prompt in packaged.prompts
    ]
    assert [
        fixture.resolved_path.read_bytes()
        for prompt in editable.prompts
        for fixture in prompt.fixtures
    ] == [
        fixture.resolved_path.read_bytes()
        for prompt in packaged.prompts
        for fixture in prompt.fixtures
    ]


@pytest.mark.parametrize(
    "suite_name",
    [
        "core-v1",
        "context-v1",
        "agent-backend-v1",
        "wumbolabs-practical-v1",
        "wumbolabs-practical-use-v1",
    ],
)
def test_current_suites_retain_legacy_all_normalization(suite_name: str) -> None:
    suite_dir = Path("suites") / suite_name
    raw = load_suite(suite_dir)

    normalized = load_normalized_suite(suite_dir)

    assert normalized.suite_id == raw["suite_id"]
    assert normalized.suite_version == raw["suite_version"]
    assert normalized.selection_kind == "legacy-all"
    assert normalized.selected_prompt_ids == tuple(
        prompt["id"] for prompt in raw["prompts"]
    )


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        (
            lambda manifest: manifest["profiles"].update(
                {"extended": {"prompt_ids": ["prompt-a"]}}
            ),
            "generic-core-profiles",
        ),
        (
            lambda manifest: manifest.update({"default_profile": "smoke"}),
            "generic-core-default-profile",
        ),
        (
            lambda manifest: manifest["profiles"].update(
                {"core": {"prompt_ids": ["prompt-a", "prompt-b"]}}
            ),
            "generic-core-core-membership",
        ),
        (
            lambda manifest: manifest["profiles"].update(
                {"smoke": {"prompt_ids": ["prompt-a", "prompt-b", "prompt-c"]}}
            ),
            "generic-core-smoke-membership",
        ),
    ],
)
def test_generic_core_profile_invariants_are_suite_specific(
    tmp_path: Path,
    mutate: Callable[[dict[str, Any]], None],
    expected: str,
) -> None:
    manifest = _profile_manifest()
    manifest["suite_id"] = "generic-core-v1"
    mutate(manifest)
    suite_dir = _write_suite(tmp_path / "suite", manifest)

    with pytest.raises(SuiteDefinitionError, match=expected):
        load_normalized_suite(suite_dir)


def test_valid_generic_core_profiles_use_inventory_not_hard_coded_ids(
    tmp_path: Path,
) -> None:
    manifest = _profile_manifest()
    manifest["suite_id"] = "generic-core-v1"

    normalized = load_normalized_suite(_write_suite(tmp_path / "suite", manifest))

    assert normalized.profiles["core"] == normalized.canonical_prompt_ids
    assert normalized.profiles["smoke"] == ("prompt-a", "prompt-c")
