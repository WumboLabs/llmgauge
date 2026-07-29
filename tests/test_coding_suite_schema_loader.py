from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
import yaml

from llmgauge.core.suite import SuiteDefinitionError, load_normalized_suite, load_suite


_VERSION = "0.1.0"
_PROMPT_CONTRACTS = (
    (
        "debug/state-transition-defect",
        "supplied-code-debugging",
        "debugging",
        ["scope-control", "dependency-api-uncertainty"],
        "explanation-plus-code",
        "coding-core-explanation-plus-code-form-v0",
        None,
    ),
    (
        "patch/bounded-cross-file-change",
        "minimal-patch-generation",
        "minimal-patch-generation",
        ["scope-control", "structured-output-compliance"],
        "bounded-patch",
        "coding-core-bounded-patch-form-v0",
        "coding-core-bounded-patch-envelope-v0",
    ),
    (
        "tests/behavioral-contract-cases",
        "test-design-and-creation",
        "test-creation",
        ["scope-control", "structured-output-compliance"],
        "code-only",
        "coding-core-code-only-tests-form-v0",
        "coding-core-code-only-tests-envelope-v0",
    ),
    (
        "diagnosis/supplied-failure-output",
        "failure-output-diagnosis",
        "failure-diagnosis",
        ["debugging", "scope-control", "dependency-api-uncertainty"],
        "explanation-only",
        "coding-core-explanation-only-form-v0",
        None,
    ),
    (
        "shell/safe-repository-maintenance",
        "safe-command-recommendation",
        "shell-command-safety",
        ["scope-control", "dependency-api-uncertainty"],
        "explanation-only",
        "coding-core-explanation-only-form-v0",
        None,
    ),
    (
        "api/closed-evidence-integration",
        "dependency-api-uncertainty",
        "dependency-api-uncertainty",
        ["scope-control", "debugging"],
        "explanation-plus-code",
        "coding-core-explanation-plus-code-form-v0",
        None,
    ),
    (
        "scope/distractor-aware-change-plan",
        "scoped-change-planning",
        "scope-control",
        ["minimal-patch-generation", "dependency-api-uncertainty"],
        "explanation-only",
        "coding-core-explanation-only-form-v0",
        None,
    ),
    (
        "structured/closed-json-change-record",
        "structured-coding-response",
        "structured-output-compliance",
        ["scope-control", "instruction-compliance"],
        "closed-json-record",
        "coding-core-closed-json-record-form-v0",
        "coding-core-closed-json-record-v0",
    ),
)
_CORE_IDS = [contract[0] for contract in _PROMPT_CONTRACTS]
_SMOKE_IDS = [
    "debug/state-transition-defect",
    "patch/bounded-cross-file-change",
    "shell/safe-repository-maintenance",
    "structured/closed-json-change-record",
]


def _reference(reference_id: str) -> dict[str, str]:
    return {"id": reference_id, "version": _VERSION}


def _coding_manifest() -> dict[str, Any]:
    prompts: list[dict[str, Any]] = []
    for index, contract in enumerate(_PROMPT_CONTRACTS):
        (
            prompt_id,
            task_family,
            primary_capability,
            secondary_stressors,
            response_category,
            response_definition_id,
            deterministic_check_id,
        ) = contract
        scoring: dict[str, Any] = {
            "role": "manual" if deterministic_check_id is None else "hybrid",
            "manual_rubric": _reference("coding-core-manual-v0"),
        }
        if deterministic_check_id is not None:
            scoring.update(
                {
                    "deterministic_check": _reference(deterministic_check_id),
                    "hybrid_rule": "side-by-side",
                    "hybrid_composition": _reference("coding-core-side-by-side-v0"),
                }
            )
        prompts.append(
            {
                "id": prompt_id,
                "file": f"prompts/role-{index + 1}.txt",
                "task_family": task_family,
                "primary_capability": primary_capability,
                "secondary_stressors": list(secondary_stressors),
                "interaction_mode": "static-single-turn",
                "execution_mode": "none",
                "response_form": {
                    "category": response_category,
                    "definition": _reference(response_definition_id),
                },
                "scoring": scoring,
                "fixtures": [],
            }
        )
    return {
        "schema_version": "llmgauge.suite.v0",
        "suite_id": "coding-core-v1",
        "suite_version": _VERSION,
        "title": "Coding Core test contract",
        "default_profile": "core",
        "profiles": {
            "smoke": {"prompt_ids": list(_SMOKE_IDS)},
            "core": {"prompt_ids": list(_CORE_IDS)},
        },
        "prompts": prompts,
    }


def _generic_manifest() -> dict[str, Any]:
    prompt = deepcopy(_coding_manifest()["prompts"][1])
    prompt["id"] = "generic-prompt"
    prompt["file"] = "prompts/generic.txt"
    return {
        "schema_version": "llmgauge.suite.v0",
        "suite_id": "generic-schema-test-v1",
        "suite_version": _VERSION,
        "title": "Generic schema test",
        "default_profile": "core",
        "profiles": {"core": {"prompt_ids": ["generic-prompt"]}},
        "prompts": [prompt],
    }


def _write_suite(root: Path, manifest: dict[str, Any]) -> Path:
    root.mkdir(parents=True)
    (root / "suite.yaml").write_text(
        yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8"
    )
    for prompt in manifest["prompts"]:
        prompt_file = root / prompt["file"]
        prompt_file.parent.mkdir(parents=True, exist_ok=True)
        prompt_file.write_text("isolated test prompt\n", encoding="utf-8")
    return root


def _assert_schema_invalid(
    tmp_path: Path, manifest: dict[str, Any], expected: str
) -> None:
    suite_dir = tmp_path / "suite"
    suite_dir.mkdir()
    (suite_dir / "suite.yaml").write_text(
        yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8"
    )
    with pytest.raises(SuiteDefinitionError, match=expected):
        load_suite(suite_dir)


def test_all_five_additive_fields_parse_and_normalize(tmp_path: Path) -> None:
    manifest = _generic_manifest()
    manifest["extension"] = {"preserved": True}
    manifest["prompts"][0]["extension"] = "preserved"

    normalized = load_normalized_suite(_write_suite(tmp_path / "suite", manifest))
    prompt = normalized.prompts[0]

    assert prompt.task_family == "minimal-patch-generation"
    assert prompt.interaction_mode == "static-single-turn"
    assert prompt.execution_mode == "none"
    assert prompt.response_form is not None
    assert prompt.response_form.category == "bounded-patch"
    assert prompt.response_form.definition.id == "coding-core-bounded-patch-form-v0"
    assert prompt.response_form.definition.version == _VERSION
    assert prompt.scoring is not None
    assert prompt.scoring.hybrid_composition is not None
    assert prompt.scoring.hybrid_composition.id == "coding-core-side-by-side-v0"
    assert prompt.scoring.hybrid_composition.version == _VERSION
    assert prompt.metadata == {"extension": "preserved"}
    assert normalized.metadata == {"extension": {"preserved": True}}


def test_legacy_manifest_may_use_optional_additive_prompt_fields(
    tmp_path: Path,
) -> None:
    manifest = {
        "schema_version": "llmgauge.suite.v0",
        "suite_id": "legacy-additive-test-v1",
        "suite_version": _VERSION,
        "prompts": [
            {
                "id": "legacy-prompt",
                "file": "prompts/legacy.txt",
                "task_family": "supplied-code-debugging",
                "interaction_mode": "static-single-turn",
                "execution_mode": "none",
                "response_form": {
                    "category": "explanation-plus-code",
                    "definition": _reference(
                        "coding-core-explanation-plus-code-form-v0"
                    ),
                },
            }
        ],
    }

    normalized = load_normalized_suite(_write_suite(tmp_path / "suite", manifest))

    assert normalized.selection_kind == "legacy-all"
    assert normalized.prompts[0].task_family == "supplied-code-debugging"
    assert normalized.prompts[0].response_form is not None


def test_additive_portable_identity_excludes_physical_roots(tmp_path: Path) -> None:
    manifest = _generic_manifest()
    first = load_normalized_suite(
        _write_suite(tmp_path / "editable" / "suite", manifest)
    )
    second = load_normalized_suite(
        _write_suite(tmp_path / "installed" / "suite", manifest)
    )

    def portable_identity(suite: Any) -> tuple[Any, ...]:
        prompt = suite.prompts[0]
        assert prompt.response_form is not None
        assert prompt.scoring is not None
        return (
            suite.schema_version,
            suite.suite_id,
            suite.suite_version,
            prompt.id,
            prompt.file,
            prompt.task_family,
            prompt.interaction_mode,
            prompt.execution_mode,
            prompt.response_form.category,
            prompt.response_form.definition,
            prompt.scoring.role,
            prompt.scoring.deterministic_check,
            prompt.scoring.manual_rubric,
            prompt.scoring.hybrid_rule,
            prompt.scoring.hybrid_composition,
        )

    identity = portable_identity(first)
    assert identity == portable_identity(second)
    assert str(first.suite_root) not in repr(identity)
    assert str(second.suite_root) not in repr(identity)


@pytest.mark.parametrize(
    "category",
    [
        "code-only",
        "explanation-plus-code",
        "explanation-only",
        "bounded-patch",
        "closed-json-record",
    ],
)
def test_generic_schema_accepts_each_response_form_category(
    tmp_path: Path, category: str
) -> None:
    manifest = _generic_manifest()
    manifest["prompts"][0]["response_form"]["category"] = category

    loaded = load_suite(_write_suite(tmp_path / "suite", manifest))

    assert loaded["prompts"][0]["response_form"]["category"] == category


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("unknown-form", "Input should be"),
        (7, "Input should be"),
    ],
)
def test_unknown_or_malformed_response_form_category_fails_closed(
    tmp_path: Path, value: Any, expected: str
) -> None:
    manifest = _generic_manifest()
    manifest["prompts"][0]["response_form"]["category"] = value

    _assert_schema_invalid(tmp_path, manifest, expected)


@pytest.mark.parametrize(
    ("owner", "expected"),
    [
        ("response_form", "Extra inputs are not permitted"),
        ("definition", "Extra inputs are not permitted"),
        ("hybrid_composition", "Extra inputs are not permitted"),
    ],
)
def test_new_contract_owned_objects_reject_unknown_fields(
    tmp_path: Path, owner: str, expected: str
) -> None:
    manifest = _generic_manifest()
    prompt = manifest["prompts"][0]
    if owner == "response_form":
        prompt["response_form"]["extension"] = True
    elif owner == "definition":
        prompt["response_form"]["definition"]["extension"] = True
    else:
        prompt["scoring"]["hybrid_composition"]["extension"] = True

    _assert_schema_invalid(tmp_path, manifest, expected)


@pytest.mark.parametrize(
    "mutation",
    [
        "missing-category",
        "missing-definition",
        "missing-definition-version",
        "missing-composition-id",
    ],
)
def test_new_closed_objects_require_their_complete_shape(
    tmp_path: Path, mutation: str
) -> None:
    manifest = _generic_manifest()
    prompt = manifest["prompts"][0]
    if mutation == "missing-category":
        prompt["response_form"].pop("category")
    elif mutation == "missing-definition":
        prompt["response_form"].pop("definition")
    elif mutation == "missing-definition-version":
        prompt["response_form"]["definition"].pop("version")
    else:
        prompt["scoring"]["hybrid_composition"].pop("id")

    _assert_schema_invalid(tmp_path, manifest, "Field required")


@pytest.mark.parametrize(
    ("owner", "field", "value", "expected"),
    [
        ("definition", "id", "slash/name", "non-empty identifier"),
        ("definition", "version", "v0.1.0", "MAJOR.MINOR.PATCH"),
        ("composition", "id", "", "non-empty identifier"),
        ("composition", "version", "0.1", "MAJOR.MINOR.PATCH"),
    ],
)
def test_new_logical_references_reject_malformed_identity(
    tmp_path: Path, owner: str, field: str, value: str, expected: str
) -> None:
    manifest = _generic_manifest()
    reference = (
        manifest["prompts"][0]["response_form"]["definition"]
        if owner == "definition"
        else manifest["prompts"][0]["scoring"]["hybrid_composition"]
    )
    reference[field] = value

    _assert_schema_invalid(tmp_path, manifest, expected)


def test_manual_scoring_forbids_hybrid_composition(tmp_path: Path) -> None:
    manifest = _generic_manifest()
    scoring = manifest["prompts"][0]["scoring"]
    scoring["role"] = "manual"
    scoring.pop("deterministic_check")
    scoring.pop("hybrid_rule")

    _assert_schema_invalid(tmp_path, manifest, "manual role forbids hybrid_composition")


def test_exact_coding_core_contract_loads_and_preserves_order(tmp_path: Path) -> None:
    normalized = load_normalized_suite(
        _write_suite(tmp_path / "suite", _coding_manifest())
    )

    assert normalized.canonical_prompt_ids == tuple(_CORE_IDS)
    assert tuple(normalized.profiles) == ("smoke", "core")
    assert normalized.profiles["smoke"] == tuple(_SMOKE_IDS)
    assert normalized.profiles["core"] == tuple(_CORE_IDS)
    assert normalized.default_profile == "core"
    assert normalized.selected_prompt_ids == tuple(_CORE_IDS)
    assert tuple(prompt.task_family for prompt in normalized.prompts) == tuple(
        contract[1] for contract in _PROMPT_CONTRACTS
    )
    assert tuple(prompt.primary_capability for prompt in normalized.prompts) == tuple(
        contract[2] for contract in _PROMPT_CONTRACTS
    )
    assert tuple(prompt.secondary_stressors for prompt in normalized.prompts) == tuple(
        tuple(contract[3]) for contract in _PROMPT_CONTRACTS
    )


def test_coding_exact_mappings_apply_only_to_version_0_1_0(tmp_path: Path) -> None:
    manifest = _coding_manifest()
    manifest["suite_version"] = "0.1.1"
    manifest["default_profile"] = "smoke"
    manifest["prompts"][1]["scoring"].pop("hybrid_composition")

    normalized = load_normalized_suite(_write_suite(tmp_path / "suite", manifest))

    assert normalized.suite_id == "coding-core-v1"
    assert normalized.suite_version == "0.1.1"
    assert normalized.selected_profile == "smoke"


@pytest.mark.parametrize(
    ("prompt_index", "field", "value", "expected"),
    [
        (0, "task_family", "minimal-patch-generation", "prompt-1-metadata"),
        (0, "primary_capability", "scope-control", "prompt-1-metadata"),
        (
            0,
            "secondary_stressors",
            ["dependency-api-uncertainty", "scope-control"],
            "prompt-1-metadata",
        ),
        (0, "interaction_mode", None, "prompt-1-interaction"),
        (0, "execution_mode", None, "prompt-1-execution"),
    ],
)
def test_coding_core_requires_exact_prompt_metadata(
    tmp_path: Path, prompt_index: int, field: str, value: Any, expected: str
) -> None:
    manifest = _coding_manifest()
    manifest["prompts"][prompt_index][field] = value

    suite_dir = _write_suite(tmp_path / "suite", manifest)
    with pytest.raises(SuiteDefinitionError, match=expected):
        load_normalized_suite(suite_dir)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("task_family", "unknown-family"),
        ("primary_capability", "unknown-capability"),
        ("secondary_stressors", ["unknown-stressor"]),
        ("interaction_mode", "multi-turn"),
        ("execution_mode", "sandboxed"),
    ],
)
def test_coding_controlled_fields_reject_unadmitted_values(
    tmp_path: Path, field: str, value: Any
) -> None:
    manifest = _coding_manifest()
    manifest["prompts"][0][field] = value

    _assert_schema_invalid(tmp_path, manifest, "Input should be")


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        ("response-category", "prompt-1-response-form"),
        ("response-reference", "prompt-1-response-form"),
        ("manual-reference", "prompt-1-manual-rubric"),
        ("deterministic-reference", "prompt-2-deterministic-check"),
        ("missing-composition", "prompt-2-hybrid-composition"),
        ("unsupported-composition", "prompt-2-hybrid-composition"),
    ],
)
def test_coding_response_and_scoring_references_are_exact(
    tmp_path: Path, mutation: str, expected: str
) -> None:
    manifest = _coding_manifest()
    if mutation == "response-category":
        manifest["prompts"][0]["response_form"]["category"] = "explanation-only"
    elif mutation == "response-reference":
        manifest["prompts"][0]["response_form"]["definition"]["id"] = "other-form-v0"
    elif mutation == "manual-reference":
        manifest["prompts"][0]["scoring"]["manual_rubric"]["id"] = "other-rubric-v0"
    elif mutation == "deterministic-reference":
        manifest["prompts"][1]["scoring"]["deterministic_check"]["id"] = (
            "other-check-v0"
        )
    elif mutation == "missing-composition":
        manifest["prompts"][1]["scoring"].pop("hybrid_composition")
    else:
        manifest["prompts"][1]["scoring"]["hybrid_composition"]["id"] = (
            "other-composition-v0"
        )

    suite_dir = _write_suite(tmp_path / "suite", manifest)
    with pytest.raises(SuiteDefinitionError, match=expected):
        load_normalized_suite(suite_dir)


def test_coding_manual_role_rejects_hybrid_fields(tmp_path: Path) -> None:
    manifest = _coding_manifest()
    manifest["prompts"][0]["scoring"]["hybrid_composition"] = _reference(
        "coding-core-side-by-side-v0"
    )

    _assert_schema_invalid(tmp_path, manifest, "manual role forbids hybrid_composition")


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        ("default", "coding-core-default-profile"),
        ("extra-profile", "coding-core-profiles"),
        ("smoke-members", "coding-core-smoke-membership"),
        ("smoke-order", "preserve canonical prompt order"),
        ("core-members", "coding-core-core-membership"),
        ("inventory-order", "coding-core-inventory"),
    ],
)
def test_coding_profiles_and_inventory_reject_mutation(
    tmp_path: Path, mutation: str, expected: str
) -> None:
    manifest = _coding_manifest()
    if mutation == "default":
        manifest["default_profile"] = "smoke"
    elif mutation == "extra-profile":
        manifest["profiles"]["full"] = {"prompt_ids": list(_CORE_IDS)}
    elif mutation == "smoke-members":
        manifest["profiles"]["smoke"]["prompt_ids"].pop()
    elif mutation == "smoke-order":
        smoke_ids = manifest["profiles"]["smoke"]["prompt_ids"]
        smoke_ids[0], smoke_ids[1] = smoke_ids[1], smoke_ids[0]
    elif mutation == "core-members":
        manifest["profiles"]["core"]["prompt_ids"].pop()
    else:
        manifest["prompts"][2], manifest["prompts"][3] = (
            manifest["prompts"][3],
            manifest["prompts"][2],
        )
        core_ids = manifest["profiles"]["core"]["prompt_ids"]
        core_ids[2], core_ids[3] = core_ids[3], core_ids[2]

    suite_dir = _write_suite(tmp_path / "suite", manifest)
    with pytest.raises(SuiteDefinitionError, match=expected):
        load_normalized_suite(suite_dir)


def test_repair_role_is_rejected_from_static_inventory(tmp_path: Path) -> None:
    manifest = _coding_manifest()
    repair_id = "repair/prior-response-test-feedback"
    replaced_id = manifest["prompts"][-1]["id"]
    manifest["prompts"][-1]["id"] = repair_id
    for profile in manifest["profiles"].values():
        profile["prompt_ids"] = [
            repair_id if prompt_id == replaced_id else prompt_id
            for prompt_id in profile["prompt_ids"]
        ]

    suite_dir = _write_suite(tmp_path / "suite", manifest)
    with pytest.raises(SuiteDefinitionError, match="coding-core-repair-role"):
        load_normalized_suite(suite_dir)


def test_repair_role_is_rejected_from_custom_selection(tmp_path: Path) -> None:
    suite_dir = _write_suite(tmp_path / "suite", _coding_manifest())

    with pytest.raises(SuiteDefinitionError, match="custom-selection-unknown"):
        load_normalized_suite(
            suite_dir, prompt_ids=["repair/prior-response-test-feedback"]
        )


def test_coding_diagnostics_do_not_echo_private_manifest_values(
    tmp_path: Path,
) -> None:
    manifest = _coding_manifest()
    private_value = "/home/private-user/private-role"
    replaced_id = manifest["prompts"][0]["id"]
    manifest["prompts"][0]["id"] = private_value
    for profile in manifest["profiles"].values():
        profile["prompt_ids"] = [
            private_value if prompt_id == replaced_id else prompt_id
            for prompt_id in profile["prompt_ids"]
        ]

    suite_dir = _write_suite(tmp_path / "suite", manifest)
    with pytest.raises(SuiteDefinitionError) as exc_info:
        load_normalized_suite(suite_dir)

    assert private_value not in str(exc_info.value)
    assert all(private_value not in item for item in exc_info.value.diagnostics)


def test_missing_coding_resource_has_no_second_root_fallback(tmp_path: Path) -> None:
    manifest = _coding_manifest()
    suite_dir = _write_suite(tmp_path / "selected", manifest)
    missing_file = suite_dir / manifest["prompts"][0]["file"]
    missing_file.unlink()
    fallback_file = tmp_path / "other" / manifest["prompts"][0]["file"]
    fallback_file.parent.mkdir(parents=True)
    fallback_file.write_text("must not be loaded\n", encoding="utf-8")

    with pytest.raises(SuiteDefinitionError, match="missing-resource") as exc_info:
        load_normalized_suite(suite_dir)

    message = str(exc_info.value)
    assert str(tmp_path) not in message
    assert "must not be loaded" not in message


def test_unreadable_coding_resource_has_public_safe_diagnostic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = _coding_manifest()
    suite_dir = _write_suite(tmp_path / "suite", manifest)
    unreadable_file = (suite_dir / manifest["prompts"][0]["file"]).resolve()
    original_open = Path.open

    def guarded_open(self: Path, *args: Any, **kwargs: Any) -> Any:
        if self == unreadable_file:
            raise PermissionError
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded_open)

    with pytest.raises(SuiteDefinitionError, match="unreadable-resource") as exc_info:
        load_normalized_suite(suite_dir)

    assert str(tmp_path) not in str(exc_info.value)
