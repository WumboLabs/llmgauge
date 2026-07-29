from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
import yaml
from typer.testing import CliRunner

from llmgauge.cli import app
from llmgauge.core.scoring import (
    apply_scores,
    build_auto_score_draft,
    build_score_template,
    validate_scores,
)
from llmgauge.core.static_scoring import (
    CODING_CORE_APPLICABILITY,
    CODING_CORE_DIMENSIONS,
    DETERMINISTIC_METHODS,
    HYBRID_COMPOSITIONS,
    MANUAL_RUBRICS,
    StaticScoringError,
    apply_deterministic_check,
    compose_hybrid_score,
    manual_review_state,
)
from llmgauge.core.suite import (
    NormalizedLogicalReference,
    NormalizedSuite,
    load_normalized_suite,
)

REPOSITORY_ROOT = Path(__file__).parents[1]
CODING_SUITE_ROOT = REPOSITORY_ROOT / "suites" / "coding-core-v1"
PROMPT_IDS = tuple(CODING_CORE_APPLICABILITY)
RUNNER = CliRunner()

PATCH_PASS = """*** Begin Patch
*** Update File: src/config.py
@@
-old
+new
*** Update File: tests/test_config.py
@@
 old
+new
*** End Patch
"""
CODE_PASS = """```python
def test_contract():
    assert True
```
"""
JSON_PASS: dict[str, Any] = {
    "change_id": "CFG-017",
    "summary": "Reject boolean port values while retaining the declared integer range.",
    "files": [
        {"path": "src/config.py", "action": "modify"},
        {"path": "tests/test_config.py", "action": "modify"},
    ],
    "behavior": {
        "before": "True is accepted as port 1.",
        "after": "Booleans are rejected and integers from 1 through 65535 remain accepted.",
    },
    "verification": [
        {
            "check": "focused-tests",
            "status": "not_run",
            "reason": "No tests were run in the supplied scenario.",
        },
        {
            "check": "static-review",
            "status": "not_run",
            "reason": "No review was run in the supplied scenario.",
        },
    ],
    "uncertainties": [
        "The unspecified invalid-value exception message remains unknown."
    ],
}


def _suite(root: Path = CODING_SUITE_ROOT) -> NormalizedSuite:
    return load_normalized_suite(root)


def _evidence_status(result: dict[str, Any], property_name: str) -> str:
    return next(
        item["status"]
        for item in result["evidence"]
        if item["property"] == property_name
    )


def _coding_result(
    suite_root: Path = CODING_SUITE_ROOT,
    prompt_ids: tuple[str, ...] = PROMPT_IDS,
) -> dict[str, Any]:
    return {
        "run": {"run_id": "coding-static-scoring"},
        "suite": {
            "suite_id": "coding-core-v1",
            "suite_version": "0.1.0",
            "suite_path": str(suite_root),
        },
        "summary": {},
        "results": [
            {
                "prompt_id": prompt_id,
                "status": "completed",
                "score": None,
                "failure_labels": [],
                "notes": "",
            }
            for prompt_id in prompt_ids
        ],
    }


def _fully_reviewed_entry(prompt_id: str, score: int = 4) -> dict[str, Any]:
    entry = {dimension: score for dimension in CODING_CORE_APPLICABILITY[prompt_id]}
    entry.update(
        {
            "failure_labels": [],
            "good_labels": [],
            "reviewer_notes": "",
            "score_rationale": "Reviewed against the preserved prompt and raw response.",
            "verdict": "pass",
            "scoring_mode": "manual",
            "scorer_id": "reviewer-a",
            "scorer_version": "",
            "confidence": "",
            "evidence": ["Preserved prompt and raw response."],
            "warnings": [],
            "reviewed": True,
            "override_status": "none",
        }
    )
    return entry


def _copy_deterministic(result: dict[str, Any]) -> dict[str, Any]:
    return {
        **result,
        "evidence": [dict(item) for item in result["evidence"]],
    }


def _replace_prompt_check(
    suite: NormalizedSuite,
    prompt_id: str,
    reference: NormalizedLogicalReference,
) -> NormalizedSuite:
    prompts = []
    selected_prompts = []
    for prompt in suite.prompts:
        changed = prompt
        if prompt.id == prompt_id:
            assert prompt.scoring is not None
            changed = replace(
                prompt,
                scoring=replace(prompt.scoring, deterministic_check=reference),
            )
        prompts.append(changed)
        if prompt.id in suite.selected_prompt_ids:
            selected_prompts.append(changed)
    return replace(
        suite,
        prompts=tuple(prompts),
        selected_prompts=tuple(selected_prompts),
    )


def test_exact_static_scoring_method_registration() -> None:
    assert DETERMINISTIC_METHODS == {
        ("coding-core-bounded-patch-envelope-v0", "0.1.0"),
        ("coding-core-code-only-tests-envelope-v0", "0.1.0"),
        ("coding-core-closed-json-record-v0", "0.1.0"),
    }
    assert MANUAL_RUBRICS == {("coding-core-manual-v0", "0.1.0")}
    assert HYBRID_COMPOSITIONS == {("coding-core-side-by-side-v0", "0.1.0")}


@pytest.mark.parametrize(
    ("reference", "message"),
    [
        (
            NormalizedLogicalReference(id="unknown-check", version="0.1.0"),
            "unsupported-method",
        ),
        (
            NormalizedLogicalReference(
                id="coding-core-bounded-patch-envelope-v0", version="0.2.0"
            ),
            "unsupported-method",
        ),
        (
            NormalizedLogicalReference(
                id="coding-core-code-only-tests-envelope-v0", version="0.1.0"
            ),
            "prompt-method-mismatch",
        ),
    ],
)
def test_unsupported_or_mismatched_check_fails_closed(
    reference: NormalizedLogicalReference,
    message: str,
) -> None:
    suite = _replace_prompt_check(
        _suite(), "patch/bounded-cross-file-change", reference
    )

    with pytest.raises(StaticScoringError, match=message):
        apply_deterministic_check(suite, "patch/bounded-cross-file-change", PATCH_PASS)


def test_manual_prompt_has_no_deterministic_check() -> None:
    with pytest.raises(StaticScoringError, match="prompt-method-mismatch"):
        apply_deterministic_check(_suite(), "debug/state-transition-defect", "response")


def test_bounded_patch_check_passes_without_applying_patch() -> None:
    result = apply_deterministic_check(
        _suite(), "patch/bounded-cross-file-change", PATCH_PASS
    )

    assert result["outcome"] == "pass"
    assert result["check_id"] == "coding-core-bounded-patch-envelope-v0"
    assert result["check_version"] == "0.1.0"
    assert result["response_form_id"] == "coding-core-bounded-patch-form-v0"


@pytest.mark.parametrize(
    ("response", "property_name"),
    [
        ("prose\n" + PATCH_PASS, "patch-envelope"),
        (
            PATCH_PASS.replace("*** Begin Patch", "```\n*** Begin Patch"),
            "markdown-fence",
        ),
        (
            "*** Begin Patch\n*** Add File: src/config.py\n@@\n+new\n*** End Patch\n",
            "update-only",
        ),
        (
            "*** Begin Patch\nprose\n*** Update File: src/config.py\n@@\n+new\n*** End Patch\n",
            "extra-content",
        ),
        (
            "*** Begin Patch\n*** Update File: src/config.py\n+new\n*** End Patch\n",
            "hunk-presence",
        ),
        (
            "*** Begin Patch\n*** Update File: src/config.py\n@@\ninvalid\n*** End Patch\n",
            "hunk-line-prefixes",
        ),
        (
            PATCH_PASS.replace(
                "*** Update File: tests/test_config.py",
                "*** Update File: src/config.py",
            ),
            "duplicate-paths",
        ),
        (
            PATCH_PASS.replace("src/config.py", "/src/config.py", 1),
            "absolute-paths",
        ),
        (
            PATCH_PASS.replace("src/config.py", "src/../config.py", 1),
            "path-traversal",
        ),
        (
            PATCH_PASS.replace("src/config.py", "src/other.py", 1),
            "declared-paths",
        ),
        (
            "*** Begin Patch\n*** Update File: src/config.py\n@@\n*** End Patch\n",
            "hunk-content",
        ),
    ],
)
def test_bounded_patch_structural_failures(
    response: str,
    property_name: str,
) -> None:
    result = apply_deterministic_check(
        _suite(), "patch/bounded-cross-file-change", response
    )

    assert result["outcome"] == "fail"
    assert _evidence_status(result, property_name) == "fail"


@pytest.mark.parametrize(
    ("response", "property_name"),
    [
        ("prose\n" + CODE_PASS, "code-envelope"),
        (CODE_PASS.replace("```python", "```py"), "language-tag"),
        (CODE_PASS + "```python\npass\n```\n", "fenced-block-count"),
        ("```python\n\n```\n", "code-content"),
        (
            "```python\n*** Begin Patch\n*** End Patch\n```\n",
            "second-artifact",
        ),
    ],
)
def test_code_only_check_rejects_malformed_envelopes(
    response: str,
    property_name: str,
) -> None:
    result = apply_deterministic_check(
        _suite(), "tests/behavioral-contract-cases", response
    )

    assert result["outcome"] == "fail"
    assert _evidence_status(result, property_name) == "fail"


def test_code_only_check_passes_without_parsing_or_running_code() -> None:
    result = apply_deterministic_check(
        _suite(), "tests/behavioral-contract-cases", CODE_PASS
    )

    assert result["outcome"] == "pass"
    assert result["check_id"] == "coding-core-code-only-tests-envelope-v0"


def test_closed_json_check_passes_exact_contract() -> None:
    result = apply_deterministic_check(
        _suite(),
        "structured/closed-json-change-record",
        json.dumps(JSON_PASS),
    )

    assert result["outcome"] == "pass"
    assert result["check_id"] == "coding-core-closed-json-record-v0"


@pytest.mark.parametrize(
    ("mutator", "property_name"),
    [
        (lambda value: "prose\n" + json.dumps(value), "json-parse"),
        (
            lambda value: json.dumps(value).replace(
                '"change_id": "CFG-017"',
                '"change_id": "CFG-017", "change_id": "CFG-017"',
                1,
            ),
            "json-parse",
        ),
        (
            lambda value: json.dumps({**value, "summary": float("nan")}),
            "json-parse",
        ),
        (
            lambda value: json.dumps({"summary": value["summary"], **value}),
            "top-level-keys",
        ),
        (lambda value: json.dumps({**value, "extra": True}), "top-level-keys"),
        (lambda value: json.dumps({**value, "summary": None}), "null-values"),
        (lambda value: json.dumps({**value, "change_id": "CFG-018"}), "change-id"),
        (lambda value: json.dumps({**value, "summary": "x" * 121}), "summary"),
        (
            lambda value: json.dumps(
                {**value, "files": list(reversed(value["files"]))}
            ),
            "files",
        ),
        (
            lambda value: json.dumps(
                {**value, "behavior": {"after": "x", "before": "y"}}
            ),
            "behavior",
        ),
        (
            lambda value: json.dumps(
                {
                    **value,
                    "verification": [
                        {"check": "focused-tests", "status": "pass", "reason": "ran"},
                        value["verification"][1],
                    ],
                }
            ),
            "verification",
        ),
        (
            lambda value: json.dumps({**value, "uncertainties": ["Unknown."]}),
            "uncertainties",
        ),
        (
            lambda value: json.dumps(
                {**value, "summary": "See https://example.invalid"}
            ),
            "forbidden-string-content",
        ),
    ],
)
def test_closed_json_check_rejects_closed_contract_failures(
    mutator: Any,
    property_name: str,
) -> None:
    result = apply_deterministic_check(
        _suite(),
        "structured/closed-json-change-record",
        mutator(JSON_PASS),
    )

    assert result["outcome"] == "fail"
    assert _evidence_status(result, property_name) == "fail"


def test_deterministic_outcomes_keep_not_run_error_and_fail_distinct(
    tmp_path: Path,
) -> None:
    suite = _suite()
    not_run = apply_deterministic_check(
        suite,
        "tests/behavioral-contract-cases",
        None,
        generation_failed=True,
    )
    empty_after_failure = apply_deterministic_check(
        suite,
        "tests/behavioral-contract-cases",
        "",
        generation_failed=True,
    )
    failed = apply_deterministic_check(suite, "tests/behavioral-contract-cases", "")
    bounded_error = apply_deterministic_check(
        suite, "tests/behavioral-contract-cases", "x" * 1_000_001
    )

    selected_root = tmp_path / "selected-suite"
    shutil.copytree(CODING_SUITE_ROOT, selected_root)
    form_path = (
        selected_root
        / "response-forms"
        / "v0.1.0"
        / "coding-core-code-only-tests-form-v0.json"
    )
    form_path.unlink()
    resource_error = apply_deterministic_check(
        _suite(selected_root), "tests/behavioral-contract-cases", CODE_PASS
    )

    assert not_run["outcome"] == "not_run"
    assert "generation failure" in not_run["evidence"][0]["detail"]
    assert not_run["evidence"][0]["status"] == "not_run"
    assert empty_after_failure["outcome"] == "not_run"
    assert failed["outcome"] == "fail"
    assert bounded_error["outcome"] == "error"
    assert bounded_error["error_classification"] == "resource-bound"
    assert resource_error["outcome"] == "error"
    assert resource_error["error_classification"] == "response-form-unavailable"
    assert str(selected_root) not in json.dumps(resource_error)


def test_selected_root_has_no_second_root_or_network_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected_root = tmp_path / "selected-suite"
    shutil.copytree(CODING_SUITE_ROOT, selected_root)
    (
        selected_root
        / "response-forms"
        / "v0.1.0"
        / "coding-core-closed-json-record-form-v0.json"
    ).unlink()

    def forbidden_network(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("network access is forbidden")

    monkeypatch.setattr(socket, "create_connection", forbidden_network)
    monkeypatch.chdir(REPOSITORY_ROOT)
    result = apply_deterministic_check(
        _suite(selected_root),
        "structured/closed-json-change-record",
        json.dumps(JSON_PASS),
    )

    assert result["outcome"] == "error"
    assert result["error_classification"] == "response-form-unavailable"
    assert str(selected_root) not in json.dumps(result)
    assert str(CODING_SUITE_ROOT) not in json.dumps(result)


def test_static_checks_do_not_execute_generated_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("generated content execution is forbidden")

    suite = _suite()

    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(os, "system", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr("importlib.import_module", forbidden)
    monkeypatch.setattr(Path, "write_text", forbidden)

    assert (
        apply_deterministic_check(suite, "patch/bounded-cross-file-change", PATCH_PASS)[
            "outcome"
        ]
        == "pass"
    )
    assert (
        apply_deterministic_check(suite, "tests/behavioral-contract-cases", CODE_PASS)[
            "outcome"
        ]
        == "pass"
    )
    assert (
        apply_deterministic_check(
            suite,
            "structured/closed-json-change-record",
            json.dumps(JSON_PASS),
        )["outcome"]
        == "pass"
    )


def test_manual_template_has_exact_dimensions_for_all_eight_prompts() -> None:
    template = build_score_template(_coding_result())

    assert template["rubric_id"] == "coding-core-manual-v0"
    assert template["rubric_version"] == "0.1.0"
    assert tuple(template["dimensions"]) == CODING_CORE_DIMENSIONS
    for prompt_id, applicable in CODING_CORE_APPLICABILITY.items():
        entry = template["scores"][prompt_id]
        present_dimensions = tuple(
            dimension for dimension in CODING_CORE_DIMENSIONS if dimension in entry
        )
        assert present_dimensions == applicable
        assert entry["reviewed"] is False
        assert entry["scorer_id"] == ""


def test_coding_auto_draft_never_infers_semantic_scores() -> None:
    result = _coding_result(prompt_ids=("shell/safe-repository-maintenance",))
    result["results"][0]["cleaned_output"] = "sudo rm -rf / --no-preserve-root"

    draft = build_auto_score_draft(result)
    entry = draft["scores"]["shell/safe-repository-maintenance"]

    assert all(
        entry[dimension] is None
        for dimension in CODING_CORE_APPLICABILITY["shell/safe-repository-maintenance"]
    )
    assert entry["reviewed"] is False
    assert entry["verdict"] == "needs_review"
    assert entry["confidence"] == "not_scored"


def test_manual_score_validation_supports_review_states_and_applicability() -> None:
    prompt_id = "debug/state-transition-defect"
    result = _coding_result(prompt_ids=(prompt_id,))
    template = build_score_template(result)
    assert validate_scores(result, template) == []
    assert manual_review_state(prompt_id, template["scores"][prompt_id]) == "unreviewed"

    partial = build_score_template(result)
    partial_entry = partial["scores"][prompt_id]
    partial_entry["diagnosis_accuracy"] = 3
    partial_entry.update(
        {
            "reviewed": True,
            "scorer_id": "reviewer-a",
            "score_rationale": "Only the diagnosis evidence was scoreable.",
            "verdict": "needs_review",
        }
    )
    assert validate_scores(result, partial) == []
    assert manual_review_state(prompt_id, partial_entry) == "partial"

    unscoreable = build_score_template(result)
    unscoreable_entry = unscoreable["scores"][prompt_id]
    unscoreable_entry.update(
        {
            "reviewed": True,
            "scorer_id": "reviewer-a",
            "score_rationale": "No preserved response evidence is available.",
            "verdict": "needs_review",
        }
    )
    assert validate_scores(result, unscoreable) == []
    assert manual_review_state(prompt_id, unscoreable_entry) == "unscoreable"

    reviewed = build_score_template(result)
    reviewed["scores"][prompt_id] = _fully_reviewed_entry(prompt_id)
    assert validate_scores(result, reviewed) == []
    assert manual_review_state(prompt_id, reviewed["scores"][prompt_id]) == "reviewed"
    assert manual_review_state(prompt_id, None) == "missing"


def test_manual_score_validation_fails_closed_for_rubric_and_review_errors() -> None:
    prompt_id = "debug/state-transition-defect"
    result = _coding_result(prompt_ids=(prompt_id,))

    wrong_rubric = build_score_template(result)
    wrong_rubric["rubric_version"] = "0.2.0"
    assert any(
        "does not match" in error for error in validate_scores(result, wrong_rubric)
    )

    missing_rationale = build_score_template(result)
    missing_rationale["scores"][prompt_id] = _fully_reviewed_entry(prompt_id)
    missing_rationale["scores"][prompt_id]["score_rationale"] = ""
    assert any(
        "score_rationale is required" in error
        for error in validate_scores(result, missing_rationale)
    )

    non_applicable = build_score_template(result)
    non_applicable["scores"][prompt_id]["shell_operational_safety"] = 0
    assert any(
        "not applicable" in error for error in validate_scores(result, non_applicable)
    )

    boolean_score = build_score_template(result)
    boolean_score["scores"][prompt_id]["diagnosis_accuracy"] = True
    assert any(
        "must be a number" in error for error in validate_scores(result, boolean_score)
    )
    non_finite_score = build_score_template(result)
    non_finite_score["scores"][prompt_id]["diagnosis_accuracy"] = float("nan")
    assert any(
        "must be between" in error
        for error in validate_scores(result, non_finite_score)
    )


def test_apply_scores_preserves_prompt_evidence_without_profile_aggregation() -> None:
    result = _coding_result()
    scores = build_score_template(result)
    for prompt_id in PROMPT_IDS:
        scores["scores"][prompt_id] = _fully_reviewed_entry(prompt_id)

    assert validate_scores(result, scores) == []
    updated = apply_scores(result, scores)

    assert updated["summary"]["manual_score_total"] is None
    assert updated["summary"]["manual_score_max"] is None
    assert updated["summary"]["manual_score_average"] is None
    assert updated["summary"]["scored_prompt_count"] == 8
    first_score = updated["results"][0]["score"]
    assert first_score["prompt_average"] == 4.0
    assert tuple(first_score["dimensions"]) == CODING_CORE_APPLICABILITY[PROMPT_IDS[0]]
    assert first_score["rubric_id"] == "coding-core-manual-v0"
    assert first_score["scorer_id"] == "reviewer-a"
    assert manual_review_state(PROMPT_IDS[0], first_score) == "reviewed"


def test_composition_rejects_fabricated_pass_without_evidence() -> None:
    suite = _suite()
    prompt_id = "patch/bounded-cross-file-change"
    fabricated = _copy_deterministic(
        apply_deterministic_check(suite, prompt_id, PATCH_PASS)
    )
    fabricated["evidence"] = []

    with pytest.raises(StaticScoringError, match="invalid-deterministic-component"):
        compose_hybrid_score(
            suite, prompt_id, fabricated, _fully_reviewed_entry(prompt_id)
        )


@pytest.mark.parametrize(
    ("field", "value", "remove"),
    [
        ("response_form_id", None, True),
        ("response_form_id", "wrong-form", False),
        ("response_form_version", "0.2.0", False),
    ],
)
def test_composition_rejects_missing_or_mismatched_response_form(
    field: str,
    value: str | None,
    remove: bool,
) -> None:
    suite = _suite()
    prompt_id = "patch/bounded-cross-file-change"
    record = _copy_deterministic(
        apply_deterministic_check(suite, prompt_id, PATCH_PASS)
    )
    if remove:
        record.pop(field)
    else:
        record[field] = value

    with pytest.raises(StaticScoringError, match="invalid-deterministic-component"):
        compose_hybrid_score(suite, prompt_id, record, _fully_reviewed_entry(prompt_id))


def test_composition_deterministic_diagnostic_is_bounded_and_public_safe() -> None:
    suite = _suite()
    prompt_id = "patch/bounded-cross-file-change"
    record = _copy_deterministic(
        apply_deterministic_check(suite, prompt_id, PATCH_PASS)
    )
    record["raw_response"] = "RAW-RESPONSE-CONTENT"
    record["physical_path"] = "PRIVATE-PATH"

    with pytest.raises(StaticScoringError) as exc_info:
        compose_hybrid_score(suite, prompt_id, record, _fully_reviewed_entry(prompt_id))

    diagnostic = str(exc_info.value)
    assert diagnostic == (
        "invalid-deterministic-component: deterministic component is malformed "
        "or inconsistent"
    )
    assert "RAW-RESPONSE-CONTENT" not in diagnostic
    assert "PRIVATE-PATH" not in diagnostic


@pytest.mark.parametrize(
    "evidence",
    [
        "not-a-list",
        [{}],
        [{"property": "patch-envelope", "status": "unknown", "detail": "bad"}],
        [{"property": "patch-envelope", "status": "pass"}],
        [
            {
                "property": "patch-envelope",
                "status": "pass",
                "detail": "ok",
                "extra": "unsupported",
            }
        ],
        [
            {
                "property": "x" * 129,
                "status": "pass",
                "detail": "ok",
            }
        ],
        [
            {
                "property": "patch-envelope",
                "status": "pass",
                "detail": "x" * 257,
            }
        ],
        [
            {"property": "patch-envelope", "status": "pass", "detail": "ok"}
            for _ in range(33)
        ],
    ],
)
def test_composition_rejects_malformed_deterministic_evidence(
    evidence: Any,
) -> None:
    suite = _suite()
    prompt_id = "patch/bounded-cross-file-change"
    record = _copy_deterministic(
        apply_deterministic_check(suite, prompt_id, PATCH_PASS)
    )
    record["evidence"] = evidence

    with pytest.raises(StaticScoringError, match="invalid-deterministic-component"):
        compose_hybrid_score(suite, prompt_id, record, _fully_reviewed_entry(prompt_id))


@pytest.mark.parametrize(
    ("outcome", "error_classification", "status"),
    [
        ("pass", "resource-bound", "pass"),
        ("fail", None, "pass"),
        ("error", None, "error"),
        ("error", "unsupported-error", "error"),
        ("not_run", None, "pass"),
        ([], None, "pass"),
        ("error", [], "error"),
    ],
)
def test_composition_rejects_inconsistent_deterministic_outcome(
    outcome: Any,
    error_classification: Any,
    status: str,
) -> None:
    suite = _suite()
    prompt_id = "patch/bounded-cross-file-change"
    record = _copy_deterministic(
        apply_deterministic_check(suite, prompt_id, PATCH_PASS)
    )
    record["outcome"] = outcome
    record["error_classification"] = error_classification
    record["evidence"] = [
        {
            "property": "patch-envelope",
            "status": status,
            "detail": "bounded synthetic evidence",
        }
    ]

    with pytest.raises(StaticScoringError, match="invalid-deterministic-component"):
        compose_hybrid_score(suite, prompt_id, record, _fully_reviewed_entry(prompt_id))


@pytest.mark.parametrize(
    "invalid_value",
    [True, -1, 6, float("nan"), float("inf"), float("-inf")],
)
def test_invalid_manual_values_cannot_complete_hybrid(
    invalid_value: Any,
) -> None:
    suite = _suite()
    prompt_id = "patch/bounded-cross-file-change"
    manual = _fully_reviewed_entry(prompt_id)
    manual[CODING_CORE_APPLICABILITY[prompt_id][0]] = invalid_value

    composition = compose_hybrid_score(
        suite,
        prompt_id,
        apply_deterministic_check(suite, prompt_id, PATCH_PASS),
        manual,
    )

    assert composition["complete"] is False
    assert composition["manual_component"]["review_state"] == "partial"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("scorer_id", ""),
        ("score_rationale", ""),
        ("verdict", "needs_review"),
        ("verdict", "unsupported"),
        ("verdict", []),
    ],
)
def test_missing_manual_provenance_cannot_complete_hybrid(
    field: str,
    value: Any,
) -> None:
    suite = _suite()
    prompt_id = "patch/bounded-cross-file-change"
    manual = _fully_reviewed_entry(prompt_id)
    manual[field] = value

    composition = compose_hybrid_score(
        suite,
        prompt_id,
        apply_deterministic_check(suite, prompt_id, PATCH_PASS),
        manual,
    )

    assert composition["complete"] is False
    assert composition["manual_component"]["review_state"] == "partial"


def test_side_by_side_composition_is_independent_and_non_numeric() -> None:
    suite = _suite()
    prompt_id = "patch/bounded-cross-file-change"
    passed = apply_deterministic_check(suite, prompt_id, PATCH_PASS)
    failed = apply_deterministic_check(suite, prompt_id, "malformed")
    reviewed_entry = _fully_reviewed_entry(prompt_id)

    passed_composition = compose_hybrid_score(suite, prompt_id, passed, reviewed_entry)
    failed_composition = compose_hybrid_score(suite, prompt_id, failed, reviewed_entry)
    missing_manual = compose_hybrid_score(suite, prompt_id, passed, None)

    assert passed_composition["complete"] is True
    assert failed_composition["complete"] is True
    assert failed_composition["deterministic_result"]["outcome"] == "fail"
    assert failed_composition["manual_component"]["verdict"] == "pass"
    assert missing_manual["complete"] is False
    assert missing_manual["manual_component"]["review_state"] == "missing"
    assert not any("score" in key or "average" in key for key in passed_composition)


def test_side_by_side_error_not_run_and_partial_are_incomplete() -> None:
    suite = _suite()
    prompt_id = "tests/behavioral-contract-cases"
    not_run = apply_deterministic_check(suite, prompt_id, None)
    error = apply_deterministic_check(suite, prompt_id, "x" * 1_000_001)
    partial = _fully_reviewed_entry(prompt_id)
    partial[CODING_CORE_APPLICABILITY[prompt_id][-1]] = None
    partial["verdict"] = "needs_review"
    unreviewed = _fully_reviewed_entry(prompt_id)
    unreviewed["reviewed"] = False
    unscoreable = _fully_reviewed_entry(prompt_id)
    for dimension in CODING_CORE_APPLICABILITY[prompt_id]:
        unscoreable[dimension] = None
    unscoreable["verdict"] = "needs_review"

    assert (
        compose_hybrid_score(
            suite, prompt_id, not_run, _fully_reviewed_entry(prompt_id)
        )["complete"]
        is False
    )
    assert (
        compose_hybrid_score(suite, prompt_id, error, _fully_reviewed_entry(prompt_id))[
            "complete"
        ]
        is False
    )
    composition = compose_hybrid_score(
        suite,
        prompt_id,
        apply_deterministic_check(suite, prompt_id, CODE_PASS),
        partial,
    )
    assert composition["complete"] is False
    assert composition["manual_component"]["review_state"] == "partial"
    unreviewed_composition = compose_hybrid_score(
        suite,
        prompt_id,
        apply_deterministic_check(suite, prompt_id, CODE_PASS),
        unreviewed,
    )
    unscoreable_composition = compose_hybrid_score(
        suite,
        prompt_id,
        apply_deterministic_check(suite, prompt_id, CODE_PASS),
        unscoreable,
    )
    assert unreviewed_composition["complete"] is False
    assert unreviewed_composition["manual_component"]["review_state"] == "unreviewed"
    assert unscoreable_composition["complete"] is False
    assert unscoreable_composition["manual_component"]["review_state"] == "unscoreable"


def test_existing_default_scoring_contract_remains_compatible() -> None:
    result = {
        "run": {"run_id": "legacy"},
        "summary": {},
        "results": [{"prompt_id": "honesty-unknown-tool"}],
    }
    template = build_score_template(result)
    entry = template["scores"]["honesty-unknown-tool"]

    assert template["rubric_id"] == "default-manual-v0"
    assert "overall_trust" in entry
    assert "reviewed" not in entry
    assert validate_scores(result, template) == []


def test_cli_scoring_uses_isolated_coding_template_and_validation(
    tmp_path: Path,
) -> None:
    suite_root = tmp_path / "suite"
    shutil.copytree(CODING_SUITE_ROOT, suite_root)
    result_dir = tmp_path / "result"
    result_dir.mkdir()
    result_data = _coding_result(
        suite_root=suite_root,
        prompt_ids=("structured/closed-json-change-record",),
    )
    (result_dir / "llmgauge-result.json").write_text(
        json.dumps(result_data, indent=2) + "\n", encoding="utf-8"
    )

    initialized = RUNNER.invoke(app, ["score", str(result_dir), "--init"])
    assert initialized.exit_code == 0
    scores_path = result_dir / "scores.yaml"
    scores = yaml.safe_load(scores_path.read_text(encoding="utf-8"))
    assert scores["rubric_id"] == "coding-core-manual-v0"
    assert (
        tuple(
            dimension
            for dimension in CODING_CORE_DIMENSIONS
            if dimension in scores["scores"]["structured/closed-json-change-record"]
        )
        == CODING_CORE_APPLICABILITY["structured/closed-json-change-record"]
    )

    checked = RUNNER.invoke(
        app,
        ["score", str(result_dir), "--scores", str(scores_path), "--check"],
    )
    assert checked.exit_code == 0
    assert "Score validation passed" in checked.output
