import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
from typing import Any
import zipfile

from typer.testing import CliRunner
import pytest

from llmgauge.cli import app
from llmgauge.core import suite_paths
from llmgauge.core.suite import (
    NormalizedSuite,
    SuiteDefinitionError,
    load_normalized_suite,
    load_suite,
    validate_suite,
)
from llmgauge.core.suite_paths import resolve_suite_path, suite_aliases_for


REPOSITORY_ROOT = Path(__file__).parents[1]
SUITE_ID = "coding-core-v1"
SOURCE_ROOT = REPOSITORY_ROOT / "suites" / SUITE_ID
PACKAGE_ROOT = REPOSITORY_ROOT / "src/llmgauge/builtin_suites" / SUITE_ID
FORM_ROOT = Path("response-forms/v0.1.0")
PROMPT_FILES = (
    Path("prompts/debug-state-transition-defect.md"),
    Path("prompts/patch-bounded-cross-file-change.md"),
    Path("prompts/tests-behavioral-contract-cases.md"),
    Path("prompts/diagnosis-supplied-failure-output.md"),
    Path("prompts/shell-safe-repository-maintenance.md"),
    Path("prompts/api-closed-evidence-integration.md"),
    Path("prompts/scope-distractor-aware-change-plan.md"),
    Path("prompts/structured-closed-json-change-record.md"),
)
FORM_FILES = (
    FORM_ROOT / "coding-core-explanation-plus-code-form-v0.json",
    FORM_ROOT / "coding-core-bounded-patch-form-v0.json",
    FORM_ROOT / "coding-core-code-only-tests-form-v0.json",
    FORM_ROOT / "coding-core-explanation-only-form-v0.json",
    FORM_ROOT / "coding-core-closed-json-record-form-v0.json",
)
EXPECTED_FILES = frozenset((Path("suite.yaml"), *PROMPT_FILES, *FORM_FILES))
CORE_IDS = (
    "debug/state-transition-defect",
    "patch/bounded-cross-file-change",
    "tests/behavioral-contract-cases",
    "diagnosis/supplied-failure-output",
    "shell/safe-repository-maintenance",
    "api/closed-evidence-integration",
    "scope/distractor-aware-change-plan",
    "structured/closed-json-change-record",
)
SMOKE_IDS = (
    "debug/state-transition-defect",
    "patch/bounded-cross-file-change",
    "shell/safe-repository-maintenance",
    "structured/closed-json-change-record",
)
PROMPT_CONTRACTS = (
    (
        CORE_IDS[0],
        "supplied-code-debugging",
        "debugging",
        ("scope-control", "dependency-api-uncertainty"),
        "explanation-plus-code",
        "coding-core-explanation-plus-code-form-v0",
        None,
    ),
    (
        CORE_IDS[1],
        "minimal-patch-generation",
        "minimal-patch-generation",
        ("scope-control", "structured-output-compliance"),
        "bounded-patch",
        "coding-core-bounded-patch-form-v0",
        "coding-core-bounded-patch-envelope-v0",
    ),
    (
        CORE_IDS[2],
        "test-design-and-creation",
        "test-creation",
        ("scope-control", "structured-output-compliance"),
        "code-only",
        "coding-core-code-only-tests-form-v0",
        "coding-core-code-only-tests-envelope-v0",
    ),
    (
        CORE_IDS[3],
        "failure-output-diagnosis",
        "failure-diagnosis",
        ("debugging", "scope-control", "dependency-api-uncertainty"),
        "explanation-only",
        "coding-core-explanation-only-form-v0",
        None,
    ),
    (
        CORE_IDS[4],
        "safe-command-recommendation",
        "shell-command-safety",
        ("scope-control", "dependency-api-uncertainty"),
        "explanation-only",
        "coding-core-explanation-only-form-v0",
        None,
    ),
    (
        CORE_IDS[5],
        "dependency-api-uncertainty",
        "dependency-api-uncertainty",
        ("scope-control", "debugging"),
        "explanation-plus-code",
        "coding-core-explanation-plus-code-form-v0",
        None,
    ),
    (
        CORE_IDS[6],
        "scoped-change-planning",
        "scope-control",
        ("minimal-patch-generation", "dependency-api-uncertainty"),
        "explanation-only",
        "coding-core-explanation-only-form-v0",
        None,
    ),
    (
        CORE_IDS[7],
        "structured-coding-response",
        "structured-output-compliance",
        ("scope-control", "instruction-compliance"),
        "closed-json-record",
        "coding-core-closed-json-record-form-v0",
        "coding-core-closed-json-record-v0",
    ),
)


def _files_below(root: Path) -> frozenset[Path]:
    return frozenset(
        path.relative_to(root) for path in root.rglob("*") if path.is_file()
    )


def _reference_value(reference: Any) -> tuple[str, str] | None:
    if reference is None:
        return None
    return reference.id, reference.version


def _portable_identity(suite: NormalizedSuite) -> tuple[Any, ...]:
    return (
        suite.schema_version,
        suite.suite_id,
        suite.suite_version,
        suite.title,
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
                prompt.task_family,
                prompt.primary_capability,
                prompt.secondary_stressors,
                prompt.interaction_mode,
                prompt.execution_mode,
                (
                    prompt.response_form.category,
                    _reference_value(prompt.response_form.definition),
                ),
                (
                    prompt.scoring.role,
                    _reference_value(prompt.scoring.deterministic_check),
                    _reference_value(prompt.scoring.manual_rubric),
                    prompt.scoring.hybrid_rule,
                    _reference_value(prompt.scoring.hybrid_composition),
                ),
                tuple(
                    (fixture.id, fixture.version, fixture.path)
                    for fixture in prompt.fixtures
                ),
            )
            for prompt in suite.prompts
            if prompt.response_form is not None and prompt.scoring is not None
        ),
    )


@pytest.fixture(scope="module")
def built_distributions(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    dist_dir = tmp_path_factory.mktemp("coding-core-dist")
    subprocess.run(
        ["uv", "build", "--out-dir", str(dist_dir)],
        cwd=REPOSITORY_ROOT,
        check=True,
        timeout=120,
    )
    return next(dist_dir.glob("*.whl")), next(dist_dir.glob("*.tar.gz"))


def test_source_and_package_inventories_are_exact_byte_identical_mirrors() -> None:
    assert _files_below(SOURCE_ROOT) == EXPECTED_FILES
    assert _files_below(PACKAGE_ROOT) == EXPECTED_FILES
    for relative_path in EXPECTED_FILES:
        assert (SOURCE_ROOT / relative_path).read_bytes() == (
            PACKAGE_ROOT / relative_path
        ).read_bytes()


def test_manifest_validates_and_normalizes_exact_contract() -> None:
    assert validate_suite(SOURCE_ROOT) == []
    suite = load_normalized_suite(SOURCE_ROOT)

    assert suite.schema_version == "llmgauge.suite.v0"
    assert suite.suite_id == SUITE_ID
    assert suite.suite_version == "0.1.0"
    assert suite.default_profile == "core"
    assert suite.selected_profile == "core"
    assert suite.canonical_prompt_ids == CORE_IDS
    assert tuple(suite.profiles) == ("smoke", "core")
    assert suite.profiles == {"smoke": SMOKE_IDS, "core": CORE_IDS}
    assert suite.selected_prompt_ids == CORE_IDS

    for prompt, contract in zip(suite.prompts, PROMPT_CONTRACTS, strict=True):
        (
            prompt_id,
            task_family,
            capability,
            stressors,
            category,
            definition_id,
            deterministic_id,
        ) = contract
        assert prompt.id == prompt_id
        assert prompt.task_family.value == task_family
        assert prompt.primary_capability.value == capability
        assert tuple(value.value for value in prompt.secondary_stressors) == stressors
        assert prompt.interaction_mode.value == "static-single-turn"
        assert prompt.execution_mode.value == "none"
        assert prompt.response_form is not None
        assert prompt.response_form.category.value == category
        assert _reference_value(prompt.response_form.definition) == (
            definition_id,
            "0.1.0",
        )
        assert prompt.scoring is not None
        assert _reference_value(prompt.scoring.manual_rubric) == (
            "coding-core-manual-v0",
            "0.1.0",
        )
        assert prompt.fixtures == ()
        assert prompt.resolved_file.is_relative_to(SOURCE_ROOT.resolve())
        assert prompt.resolved_file.is_file()
        if deterministic_id is None:
            assert prompt.scoring.role.value == "manual"
            assert prompt.scoring.deterministic_check is None
            assert prompt.scoring.hybrid_rule is None
            assert prompt.scoring.hybrid_composition is None
        else:
            assert prompt.scoring.role.value == "hybrid"
            assert _reference_value(prompt.scoring.deterministic_check) == (
                deterministic_id,
                "0.1.0",
            )
            assert prompt.scoring.hybrid_rule == "side-by-side"
            assert _reference_value(prompt.scoring.hybrid_composition) == (
                "coding-core-side-by-side-v0",
                "0.1.0",
            )


def test_response_form_references_are_owned_versioned_resources() -> None:
    suite = load_normalized_suite(SOURCE_ROOT)
    referenced = {
        prompt.response_form.definition.id
        for prompt in suite.prompts
        if prompt.response_form is not None
    }
    resources = {
        json.loads((SOURCE_ROOT / relative_path).read_text(encoding="utf-8"))[
            "resource_id"
        ]: relative_path
        for relative_path in FORM_FILES
    }

    assert referenced == set(resources)
    for resource_id, relative_path in resources.items():
        payload = json.loads((SOURCE_ROOT / relative_path).read_text(encoding="utf-8"))
        assert payload["resource_id"] == resource_id
        assert payload["version"] == "0.1.0"
        assert payload["category"] in {
            "explanation-plus-code",
            "bounded-patch",
            "code-only",
            "explanation-only",
            "closed-json-record",
        }
        assert "allowed_envelope" in payload
        assert payload["malformed_or_extra_output"]


def test_editable_and_packaged_suites_have_portable_normalized_equivalence() -> None:
    editable = load_normalized_suite(SOURCE_ROOT)
    packaged = load_normalized_suite(PACKAGE_ROOT)

    assert editable.suite_root != packaged.suite_root
    assert _portable_identity(editable) == _portable_identity(packaged)
    assert [prompt.resolved_file.read_bytes() for prompt in editable.prompts] == [
        prompt.resolved_file.read_bytes() for prompt in packaged.prompts
    ]


def test_missing_packaged_prompt_fails_without_source_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    packaged_root = tmp_path / "builtin_suites"
    packaged_suite = packaged_root / SUITE_ID
    shutil.copytree(PACKAGE_ROOT, packaged_suite)
    missing = packaged_suite / PROMPT_FILES[0]
    missing.unlink()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(suite_paths, "builtin_suites_dir", lambda: packaged_root)

    resolved = resolve_suite_path(Path(SUITE_ID))
    assert resolved == packaged_suite
    with pytest.raises(SuiteDefinitionError, match="missing-resource"):
        load_normalized_suite(resolved)
    assert not missing.exists()


def test_no_alias_repair_role_or_execution_declaration() -> None:
    manifest = load_suite(SOURCE_ROOT)
    prompt_ids = tuple(prompt["id"] for prompt in manifest["prompts"])

    assert suite_aliases_for(SUITE_ID) == ()
    assert set(manifest["profiles"]) == {"smoke", "core"}
    assert "full" not in manifest["profiles"]
    assert "repair/prior-response-test-feedback" not in prompt_ids
    assert len(prompt_ids) == len(set(prompt_ids)) == 8
    assert all(
        prompt["interaction_mode"] == "static-single-turn"
        for prompt in manifest["prompts"]
    )
    assert all(prompt["execution_mode"] == "none" for prompt in manifest["prompts"])


def test_prompt_content_is_bounded_portable_and_non_executing() -> None:
    scenario_markers = (
        "Job.finish",
        "request_timeout_ms",
        "SequenceGate",
        "rustc 1.77.2",
        "build/cache/",
        "packetbox==2.4.0",
        "CSV-export correction",
        "CFG-017",
    )
    contents = [
        (SOURCE_ROOT / relative_path).read_text(encoding="utf-8")
        for relative_path in PROMPT_FILES
    ]

    for content, marker in zip(contents, scenario_markers, strict=True):
        lowered = content.lower()
        assert marker in content
        assert "## task" in lowered
        assert "## response form" in lowered
        assert "coding-core-" in content
        assert "will not" in lowered or "nothing will" in lowered
        assert "execut" in lowered
        assert "http://" not in lowered
        assert "https://" not in lowered
        assert "www." not in lowered
        assert "/home/" not in lowered
        assert "c:\\" not in lowered
        assert "akia" not in lowered
        assert "begin private key" not in lowered
        assert "password=" not in lowered
        assert "api_key=" not in lowered

    for index, marker in enumerate(scenario_markers):
        assert sum(marker in content for content in contents) == 1, index


def test_existing_suites_and_historical_source_only_boundary_remain_intact() -> None:
    historical = REPOSITORY_ROOT / "suites/wumbolabs-practical-use-v1"
    assert (historical / "suite.yaml").is_file()
    assert not (
        REPOSITORY_ROOT / "src/llmgauge/builtin_suites/wumbolabs-practical-use-v1"
    ).exists()
    assert validate_suite(REPOSITORY_ROOT / "suites/core-v1") == []
    assert validate_suite(REPOSITORY_ROOT / "suites/wumbolabs-practical-v1") == []
    assert _files_below(REPOSITORY_ROOT / "suites/generic-core-v1") == _files_below(
        REPOSITORY_ROOT / "src/llmgauge/builtin_suites/generic-core-v1"
    )


def test_cli_lists_and_validates_coding_core() -> None:
    runner = CliRunner()
    listed = runner.invoke(app, ["list-suites"])
    validated = runner.invoke(app, ["validate-suite", SUITE_ID])

    assert listed.exit_code == 0
    assert SUITE_ID in listed.stdout
    assert validated.exit_code == 0
    assert validated.stdout == f"OK {SUITE_ID} (8 prompts)\n"


def test_wheel_and_sdist_include_exact_coding_core_files(
    built_distributions: tuple[Path, Path],
) -> None:
    wheel, sdist = built_distributions
    wheel_prefix = f"llmgauge/builtin_suites/{SUITE_ID}/"
    with zipfile.ZipFile(wheel) as archive:
        wheel_files = {
            Path(name.removeprefix(wheel_prefix))
            for name in archive.namelist()
            if name.startswith(wheel_prefix) and not name.endswith("/")
        }
        assert wheel_files == EXPECTED_FILES
        assert not any(
            "wumbolabs-practical-use-v1" in name for name in archive.namelist()
        )

    with tarfile.open(sdist, "r:gz") as archive:
        package_marker = f"/src/llmgauge/builtin_suites/{SUITE_ID}/"
        sdist_files = {
            Path(member.name.split(package_marker, 1)[1])
            for member in archive.getmembers()
            if member.isfile() and package_marker in member.name
        }
        assert sdist_files == EXPECTED_FILES
        assert not any(
            "wumbolabs-practical-use-v1" in member.name
            for member in archive.getmembers()
        )


def test_isolated_wheel_install_discovers_and_loads_coding_core(
    built_distributions: tuple[Path, Path], tmp_path: Path
) -> None:
    wheel, _ = built_distributions
    target = tmp_path / "installed"
    subprocess.run(
        [
            "uv",
            "pip",
            "install",
            "--python",
            os.fspath(Path(os.sys.executable)),
            "--target",
            os.fspath(target),
            "--no-deps",
            os.fspath(wheel),
        ],
        cwd=tmp_path,
        check=True,
        timeout=120,
    )
    script = f"""
import os
from pathlib import Path
import sys
sys.path.insert(0, {os.fspath(target)!r})
os.chdir({os.fspath(tmp_path)!r})
from llmgauge.core.suite import load_normalized_suite
from llmgauge.core.suite_paths import resolve_suite_path
root = resolve_suite_path(Path({SUITE_ID!r}))
suite = load_normalized_suite(root)
assert suite.suite_id == {SUITE_ID!r}
assert suite.selected_profile == 'core'
assert len(suite.prompts) == 8
print(root.name, len(suite.prompts))
"""
    completed = subprocess.run(
        [os.sys.executable, "-I", "-c", script],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.stdout.strip() == f"{SUITE_ID} 8"
