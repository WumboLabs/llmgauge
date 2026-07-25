from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
import yaml

from llmgauge.core.suite import SuiteDefinitionError, load_suite, validate_suite


def _deterministic_scoring() -> dict[str, Any]:
    return {
        "role": "deterministic",
        "deterministic_check": {"id": "check-v0", "version": "0.1.0"},
    }


def _profile_prompt(prompt_id: str) -> dict[str, Any]:
    return {
        "id": prompt_id,
        "file": f"prompts/{prompt_id}.txt",
        "primary_capability": "instruction-following",
        "secondary_stressors": [],
        "scoring": _deterministic_scoring(),
        "fixtures": [],
    }


def _profile_manifest() -> dict[str, Any]:
    return {
        "schema_version": "llmgauge.suite.v0",
        "suite_id": "schema-test-v1",
        "suite_version": "0.1.0",
        "title": "Schema test",
        "default_profile": "core",
        "profiles": {
            "core": {"prompt_ids": ["prompt-a", "prompt-b"]},
            "smoke": {"prompt_ids": ["prompt-a"]},
        },
        "prompts": [_profile_prompt("prompt-a"), _profile_prompt("prompt-b")],
    }


def _load_manifest(tmp_path: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    suite_dir = tmp_path / "suite"
    suite_dir.mkdir()
    (suite_dir / "suite.yaml").write_text(
        yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8"
    )
    return load_suite(suite_dir)


def _assert_invalid(tmp_path: Path, manifest: dict[str, Any], expected: str) -> None:
    with pytest.raises(SuiteDefinitionError, match=expected):
        _load_manifest(tmp_path, manifest)


@pytest.mark.parametrize(
    "suite_dir",
    [
        "suites/core-v1",
        "suites/wumbolabs-practical-v1",
        "suites/wumbolabs-practical-use-v1",
        "suites/agent-backend-v1",
        "suites/context-v1",
        "src/llmgauge/builtin_suites/core-v1",
        "src/llmgauge/builtin_suites/wumbolabs-practical-v1",
        "src/llmgauge/builtin_suites/agent-backend-v1",
        "src/llmgauge/builtin_suites/context-v1",
    ],
)
def test_existing_manifest_loads_unchanged(suite_dir: str) -> None:
    manifest_path = Path(suite_dir) / "suite.yaml"
    expected = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))

    assert load_suite(Path(suite_dir)) == expected


def test_valid_minimal_profile_aware_manifest(tmp_path: Path) -> None:
    manifest = _profile_manifest()

    assert _load_manifest(tmp_path, manifest) == manifest


def test_profile_aware_manifest_requires_title(tmp_path: Path) -> None:
    manifest = _profile_manifest()
    del manifest["title"]

    _assert_invalid(tmp_path, manifest, "profile-aware manifest requires title")


def test_unknown_top_level_and_prompt_fields_are_preserved(tmp_path: Path) -> None:
    manifest = _profile_manifest()
    manifest["extension"] = {"enabled": True}
    manifest["prompts"][0]["extension"] = "preserved"

    loaded = _load_manifest(tmp_path, manifest)

    assert loaded["extension"] == {"enabled": True}
    assert loaded["prompts"][0]["extension"] == "preserved"


@pytest.mark.parametrize("missing", ["profiles", "default_profile"])
def test_profiles_and_default_profile_must_appear_together(
    tmp_path: Path, missing: str
) -> None:
    manifest = _profile_manifest()
    del manifest[missing]

    _assert_invalid(
        tmp_path, manifest, "profiles and default_profile must appear together"
    )


def test_profiles_must_be_non_empty(tmp_path: Path) -> None:
    manifest = _profile_manifest()
    manifest["profiles"] = {}

    _assert_invalid(tmp_path, manifest, "profiles must be a non-empty mapping")


@pytest.mark.parametrize("profile_name", ["", "has space", "slash/name"])
def test_profile_names_must_be_identifiers(tmp_path: Path, profile_name: str) -> None:
    manifest = _profile_manifest()
    manifest["profiles"] = {profile_name: {"prompt_ids": ["prompt-a"]}}
    manifest["default_profile"] = profile_name

    _assert_invalid(tmp_path, manifest, "must be a non-empty identifier")


def test_profile_members_must_be_non_empty(tmp_path: Path) -> None:
    manifest = _profile_manifest()
    manifest["profiles"]["smoke"]["prompt_ids"] = []

    _assert_invalid(tmp_path, manifest, "must be a non-empty list")


def test_default_profile_must_be_declared(tmp_path: Path) -> None:
    manifest = _profile_manifest()
    manifest["default_profile"] = "missing"

    _assert_invalid(tmp_path, manifest, "default_profile must name a declared profile")


def test_profile_members_must_reference_prompts(tmp_path: Path) -> None:
    manifest = _profile_manifest()
    manifest["profiles"]["smoke"]["prompt_ids"] = ["unknown"]

    _assert_invalid(tmp_path, manifest, "references an unknown prompt ID")


def test_profile_members_must_be_unique(tmp_path: Path) -> None:
    manifest = _profile_manifest()
    manifest["profiles"]["core"]["prompt_ids"] = ["prompt-a", "prompt-a"]

    _assert_invalid(tmp_path, manifest, "must not contain duplicate prompt IDs")


def test_profile_members_must_preserve_manifest_order(tmp_path: Path) -> None:
    manifest = _profile_manifest()
    manifest["profiles"]["core"]["prompt_ids"] = ["prompt-b", "prompt-a"]

    _assert_invalid(tmp_path, manifest, "must preserve canonical prompt order")


def test_prompt_ids_must_be_unique(tmp_path: Path) -> None:
    manifest = _profile_manifest()
    manifest["prompts"][1]["id"] = "prompt-a"

    _assert_invalid(tmp_path, manifest, "prompt IDs must be unique")


@pytest.mark.parametrize(
    "field", ["primary_capability", "secondary_stressors", "scoring", "fixtures"]
)
def test_profile_aware_prompts_require_complete_metadata(
    tmp_path: Path, field: str
) -> None:
    manifest = _profile_manifest()
    del manifest["prompts"][0][field]

    _assert_invalid(tmp_path, manifest, f"requires {field}")


def test_legacy_prompts_do_not_accept_profile_metadata(tmp_path: Path) -> None:
    manifest = _profile_manifest()
    del manifest["profiles"]
    del manifest["default_profile"]

    _assert_invalid(tmp_path, manifest, "must not declare profile-aware metadata")


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        ("primary_capability", "unknown", "Input should be"),
        ("secondary_stressors", ["unknown"], "Input should be"),
        ("scoring", {"role": "unknown"}, "Input should be"),
    ],
)
def test_controlled_metadata_rejects_unknown_values(
    tmp_path: Path, field: str, value: Any, expected: str
) -> None:
    manifest = _profile_manifest()
    manifest["prompts"][0][field] = value

    _assert_invalid(tmp_path, manifest, expected)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("primary_capability", 1),
        ("secondary_stressors", "noise"),
        ("scoring", []),
        ("fixtures", {}),
    ],
)
def test_profile_metadata_rejects_malformed_types(
    tmp_path: Path, field: str, value: Any
) -> None:
    manifest = _profile_manifest()
    manifest["prompts"][0][field] = value

    _assert_invalid(tmp_path, manifest, "valid")


def test_secondary_stressors_must_be_unique(tmp_path: Path) -> None:
    manifest = _profile_manifest()
    manifest["prompts"][0]["secondary_stressors"] = ["noise", "noise"]

    _assert_invalid(
        tmp_path, manifest, "secondary_stressors must not contain duplicates"
    )


@pytest.mark.parametrize(
    ("scoring", "expected"),
    [
        ({"role": "deterministic"}, "requires deterministic_check"),
        (
            {
                "role": "deterministic",
                "deterministic_check": {"id": "check-v0", "version": "0.1.0"},
                "manual_rubric": {"id": "rubric-v0", "version": "0.1.0"},
            },
            "forbids manual_rubric and hybrid_rule",
        ),
        ({"role": "manual"}, "requires manual_rubric"),
        (
            {
                "role": "manual",
                "manual_rubric": {"id": "rubric-v0", "version": "0.1.0"},
                "deterministic_check": {"id": "check-v0", "version": "0.1.0"},
            },
            "forbids deterministic_check and hybrid_rule",
        ),
        (
            {
                "role": "hybrid",
                "deterministic_check": {"id": "check-v0", "version": "0.1.0"},
                "hybrid_rule": "side-by-side",
            },
            "requires deterministic_check and manual_rubric",
        ),
        (
            {
                "role": "hybrid",
                "deterministic_check": {"id": "check-v0", "version": "0.1.0"},
                "manual_rubric": {"id": "rubric-v0", "version": "0.1.0"},
            },
            "requires hybrid_rule 'side-by-side'",
        ),
        (
            {
                "role": "hybrid",
                "deterministic_check": {"id": "check-v0", "version": "0.1.0"},
                "manual_rubric": {"id": "rubric-v0", "version": "0.1.0"},
                "hybrid_rule": "blended",
            },
            "Input should be 'side-by-side'",
        ),
    ],
)
def test_scoring_role_reference_cardinality(
    tmp_path: Path, scoring: dict[str, Any], expected: str
) -> None:
    manifest = _profile_manifest()
    manifest["prompts"][0]["scoring"] = scoring

    _assert_invalid(tmp_path, manifest, expected)


def test_all_scoring_roles_accept_their_required_references(tmp_path: Path) -> None:
    manifest = _profile_manifest()
    manifest["prompts"][0]["scoring"] = {
        "role": "manual",
        "manual_rubric": {"id": "rubric-v0", "version": "0.1.0"},
    }
    manifest["prompts"][1]["scoring"] = {
        "role": "hybrid",
        "deterministic_check": {"id": "check-v0", "version": "0.1.0"},
        "manual_rubric": {"id": "rubric-v0", "version": "0.1.0"},
        "hybrid_rule": "side-by-side",
    }

    assert _load_manifest(tmp_path, manifest) == manifest


@pytest.mark.parametrize("bad_id", ["", "has space", "slash/name"])
def test_logical_reference_ids_must_be_identifiers(tmp_path: Path, bad_id: str) -> None:
    manifest = _profile_manifest()
    manifest["prompts"][0]["scoring"]["deterministic_check"]["id"] = bad_id

    _assert_invalid(tmp_path, manifest, "must be a non-empty identifier")


@pytest.mark.parametrize("bad_version", ["", "1", "1.2", "v1.2.3", "1.2.3.4", "01.2.3"])
def test_logical_reference_versions_must_be_semantic(
    tmp_path: Path, bad_version: str
) -> None:
    manifest = _profile_manifest()
    manifest["prompts"][0]["scoring"]["deterministic_check"]["version"] = bad_version

    _assert_invalid(tmp_path, manifest, "must use MAJOR.MINOR.PATCH form")


@pytest.mark.parametrize(
    "path",
    [
        "",
        "/absolute/file.txt",
        "https://example.test/file.txt",
        "C:/fixture.txt",
        "fixtures\\file.txt",
        "fixtures//file.txt",
        "./fixtures/file.txt",
        "fixtures/../file.txt",
        "fixtures/./file.txt",
        "fixtures/",
        "fixtures/\nfile.txt",
    ],
)
def test_fixture_paths_reject_malformed_and_unsafe_values(
    tmp_path: Path, path: str
) -> None:
    manifest = _profile_manifest()
    manifest["prompts"][0]["fixtures"] = [
        {"id": "fixture-v0", "version": "0.1.0", "path": path}
    ]

    _assert_invalid(tmp_path, manifest, "Value error")


def test_fixture_reference_identity_and_version_are_validated(tmp_path: Path) -> None:
    manifest = _profile_manifest()
    manifest["prompts"][0]["fixtures"] = [
        {"id": "not valid", "version": "v1", "path": "fixtures/input.txt"}
    ]

    with pytest.raises(SuiteDefinitionError) as exc_info:
        _load_manifest(tmp_path, manifest)

    message = str(exc_info.value)
    assert "must be a non-empty identifier" in message
    assert "must use MAJOR.MINOR.PATCH form" in message


def test_fixture_logical_references_must_be_unique(tmp_path: Path) -> None:
    manifest = _profile_manifest()
    fixture = {"id": "fixture-v0", "version": "0.1.0", "path": "fixtures/a.txt"}
    manifest["prompts"][0]["fixtures"] = [fixture, deepcopy(fixture)]

    _assert_invalid(
        tmp_path, manifest, r"fixture \(id, version\) references must be unique"
    )


@pytest.mark.parametrize(
    "owner",
    ["profile", "scoring", "deterministic_check", "manual_rubric", "fixture"],
)
def test_contract_owned_objects_reject_unknown_fields(
    tmp_path: Path, owner: str
) -> None:
    manifest = _profile_manifest()
    if owner == "profile":
        manifest["profiles"]["core"]["unknown"] = True
    elif owner == "scoring":
        manifest["prompts"][0]["scoring"]["unknown"] = True
    elif owner == "deterministic_check":
        manifest["prompts"][0]["scoring"]["deterministic_check"]["unknown"] = True
    elif owner == "manual_rubric":
        manifest["prompts"][0]["scoring"] = {
            "role": "manual",
            "manual_rubric": {
                "id": "rubric-v0",
                "version": "0.1.0",
                "unknown": True,
            },
        }
    else:
        manifest["prompts"][0]["fixtures"] = [
            {
                "id": "fixture-v0",
                "version": "0.1.0",
                "path": "fixtures/input.txt",
                "unknown": True,
            }
        ]

    _assert_invalid(tmp_path, manifest, "Extra inputs are not permitted")


def test_unsupported_manifest_schema_fails_closed(tmp_path: Path) -> None:
    manifest = _profile_manifest()
    manifest["schema_version"] = "llmgauge.suite.v1"

    _assert_invalid(tmp_path, manifest, "Input should be 'llmgauge.suite.v0'")


def test_duplicate_yaml_mapping_keys_fail_closed(tmp_path: Path) -> None:
    suite_dir = tmp_path / "suite"
    suite_dir.mkdir()
    (suite_dir / "suite.yaml").write_text(
        """
schema_version: llmgauge.suite.v0
suite_id: first
suite_id: second
suite_version: 0.1.0
title: Duplicate mapping
prompts: []
""".lstrip(),
        encoding="utf-8",
    )

    with pytest.raises(SuiteDefinitionError, match="duplicate mapping key"):
        load_suite(suite_dir)


def test_malformed_yaml_has_bounded_private_safe_diagnostic(tmp_path: Path) -> None:
    suite_dir = tmp_path / "suite"
    suite_dir.mkdir()
    private_values = [
        "PRIVATE_RAW_YAML",
        "/home/private-user/models/model.gguf",
        "PRIVATE_PROMPT_CONTENT",
        "PRIVATE_ENVIRONMENT_VALUE",
    ]
    (suite_dir / "suite.yaml").write_text(
        "schema_version: [PRIVATE_RAW_YAML\n"
        "path: /home/private-user/models/model.gguf\n"
        "prompt: PRIVATE_PROMPT_CONTENT\n"
        "environment: PRIVATE_ENVIRONMENT_VALUE\n",
        encoding="utf-8",
    )

    with pytest.raises(SuiteDefinitionError) as exc_info:
        load_suite(suite_dir)

    assert exc_info.value.diagnostics == ("yaml: malformed YAML",)
    assert validate_suite(suite_dir) == ["yaml: malformed YAML"]
    assert len(str(exc_info.value)) <= 512
    for private_value in private_values:
        assert private_value not in str(exc_info.value)


def test_rendered_validation_diagnostic_has_one_total_bound(tmp_path: Path) -> None:
    manifest = _profile_manifest()
    manifest["profiles"]["core"]["x" * 1_000] = True

    with pytest.raises(SuiteDefinitionError) as exc_info:
        _load_manifest(tmp_path, manifest)

    assert len(exc_info.value.diagnostics) == 1
    assert len(exc_info.value.diagnostics[0]) == 512
    assert len(str(exc_info.value)) == 512


def test_validation_diagnostics_are_truncated_at_one_hundred(
    tmp_path: Path,
) -> None:
    manifest = _profile_manifest()
    manifest["prompts"] = [None] * 101

    with pytest.raises(SuiteDefinitionError) as exc_info:
        _load_manifest(tmp_path, manifest)

    diagnostics = exc_info.value.diagnostics
    assert len(diagnostics) == 100
    assert diagnostics[-1] == "diagnostics-truncated: additional errors omitted"
    assert all(len(diagnostic) <= 512 for diagnostic in diagnostics)


def test_suite_identity_aliases_are_not_accepted(tmp_path: Path) -> None:
    manifest = _profile_manifest()
    manifest["schema"] = manifest.pop("schema_version")
    manifest["id"] = manifest.pop("suite_id")
    manifest["version"] = manifest.pop("suite_version")

    with pytest.raises(SuiteDefinitionError) as exc_info:
        _load_manifest(tmp_path, manifest)

    message = str(exc_info.value)
    assert "schema_version" in message
    assert "suite_id" in message
    assert "suite_version" in message
