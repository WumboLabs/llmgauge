from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from llmgauge.core.agent_harness import import_agent_harness_session
from llmgauge.core.agent_session_review import (
    AgentSessionReviewError,
    REVIEW_PATH,
    TEMPLATE_PATH,
    _producer_version_summary,
    apply_review,
    build_report,
    build_template,
    load_review,
    validate_review,
    write_report,
    write_template,
)
from llmgauge.core.run_fingerprint import run_fingerprint_value
from llmgauge.core.scoring import load_result
from agent_harness_fixtures import write_synthetic_omp_session


def imported_result(tmp_path: Path, scenario: str = "completed") -> Path:
    source = write_synthetic_omp_session(tmp_path / "source", scenario=scenario)
    result = tmp_path / "result"
    import_agent_harness_session(source.source, result)
    return result


def candidate(result: Path) -> dict[str, object]:
    review = build_template(result)
    review.update(
        {
            "reviewer": {"reviewer_id": "reviewer-1"},
            "reviewed_at_utc": "2026-08-13T00:00:00Z",
        }
    )
    review["scoreability"] = {
        "value": "scoreable",
        "required_evidence_basis": [
            {
                "basis_id": "terminal",
                "target": "task_completion_evidence",
                "state": "sufficient",
                "rationale": "Contained terminal evidence is available.",
                "source_references": [
                    {
                        "reference_type": "source_terminal",
                        "reference_id": "source_terminal",
                    }
                ],
                "applicability_mismatch": None,
            }
        ],
    }
    review["review_state"] = "reviewed"
    review["findings"] = [
        {
            "finding_id": "finding-1",
            "finding_kind": "judgment",
            "target": "task_completion_evidence",
            "judgment_outcome": "mixed",
            "rationale": "Reviewer judgment based on the contained terminal.",
            "source_references": [
                {"reference_type": "source_terminal", "reference_id": "source_terminal"}
            ],
            "reviewer": {"reviewer_id": "reviewer-1"},
            "reviewed_at_utc": "2026-08-13T00:00:00Z",
            "evidence_completeness": review["evidence_completeness"],
            "attribution": {
                "values": ["harness_agent_policy"],
                "state": "observed",
                "rationale": None,
            },
            "limitations": [],
            "reviewer_tags": [],
        }
    ]
    return review


def test_template_candidate_apply_report_and_fingerprint(tmp_path: Path) -> None:
    result = imported_result(tmp_path)
    before = run_fingerprint_value(result, load_result(result))
    template = write_template(result, force=False)
    assert template == result / TEMPLATE_PATH
    validate_review(load_review(template), result, template=True)
    review = candidate(result)
    validate_review(review, result)
    apply_review(result, review, force=False)
    assert (result / REVIEW_PATH).exists()
    report = build_report(result)
    for section in range(1, 8):
        assert f"## {section}." in report
    assert "model alone" in report
    assert run_fingerprint_value(result, load_result(result)) == before


@pytest.mark.parametrize(
    "scoreability,state",
    [
        ("not_assessed", "not_started"),
        ("scoreable", "awaiting_review"),
        ("scoreable", "in_review"),
        ("scoreable", "reviewed"),
        ("scoreable", "incomplete_review"),
        ("unscoreable", "incomplete_review"),
        ("unscoreable", "unavailable"),
        ("not_applicable", "not_applicable"),
    ],
)
def test_legal_scoreability_states(
    tmp_path: Path, scoreability: str, state: str
) -> None:
    result = imported_result(tmp_path)
    review = candidate(result)
    review["review_state"] = state
    if scoreability == "not_assessed":
        review = build_template(result)
        review.update(
            {
                "reviewer": {"reviewer_id": "reviewer-1"},
                "reviewed_at_utc": "2026-08-13T00:00:00Z",
            }
        )
    elif scoreability == "unscoreable":
        review["scoreability"]["value"] = scoreability
        review["scoreability"]["required_evidence_basis"][0]["state"] = "missing"
        review["findings"] = []
    elif scoreability == "not_applicable":
        review["scoreability"]["value"] = scoreability
        basis = review["scoreability"]["required_evidence_basis"][0]
        basis.update(
            {
                "state": "target_method_mismatch",
                "applicability_mismatch": {
                    "kind": "target_method_mismatch",
                    "target": "task_completion_evidence",
                    "method_id": "agent-session-review-v0",
                    "method_version": "0.1.0",
                },
            }
        )
        review["findings"] = []
    validate_review(review, result)


def test_rejects_duplicate_unknown_wrong_reference_and_states(tmp_path: Path) -> None:
    result = imported_result(tmp_path)
    review = candidate(result)
    review["unknown"] = True
    with pytest.raises(AgentSessionReviewError):
        validate_review(review, result)
    review = candidate(result)
    review["findings"][0]["source_references"].append(
        {"reference_type": "source_terminal", "reference_id": "source_terminal"}
    )
    with pytest.raises(AgentSessionReviewError):
        validate_review(review, result)
    review = candidate(result)
    review["review_state"] = "unavailable"
    with pytest.raises(AgentSessionReviewError):
        validate_review(review, result)
    bad = tmp_path / "duplicate.json"
    bad.write_text('{"schema_version":"x","schema_version":"y"}', encoding="utf-8")
    with pytest.raises(AgentSessionReviewError, match="duplicate JSON key"):
        load_review(bad)


def test_resource_and_no_clobber_boundaries(tmp_path: Path) -> None:
    result = imported_result(tmp_path)
    write_template(result, force=False)
    with pytest.raises(AgentSessionReviewError, match="already exists"):
        write_template(result, force=False)
    large = tmp_path / "large.json"
    large.write_bytes(b"{" + b" " * 1_048_576 + b"}")
    with pytest.raises(AgentSessionReviewError, match="1048576"):
        load_review(large)
    deep = tmp_path / "deep.json"
    deep.write_text("[" * 66 + "]" * 66, encoding="utf-8")
    with pytest.raises(AgentSessionReviewError, match="nesting"):
        load_review(deep)


def test_report_fails_closed_on_invalid_canonical_review(tmp_path: Path) -> None:
    result = imported_result(tmp_path)
    path = result / REVIEW_PATH
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"invalid": True}), encoding="utf-8")
    with pytest.raises(AgentSessionReviewError):
        build_report(result)


def test_reviewer_objects_and_substantive_report_rendering(tmp_path: Path) -> None:
    result = imported_result(tmp_path)
    template = build_template(result)
    assert template["reviewer"] is None
    review = candidate(result)
    assert review["reviewer"] == {"reviewer_id": "reviewer-1"}
    assert review["findings"][0]["reviewer"] == {"reviewer_id": "reviewer-1"}
    validate_review(review, result)
    apply_review(result, review, force=False)
    report = build_report(result)
    for text in (
        "Source producer:",
        "Source run fingerprint: `represented`",
        "Source verifier outcome: `unavailable`",
        "Finding `finding-1`",
        "outcome `mixed`",
        "Reviewer judgment based on the contained terminal.",
        "harness_agent_policy",
        "evidence basis `terminal`",
        "finding `finding-1`",
    ):
        assert text in report
    review["reviewer"] = "reviewer-1"
    with pytest.raises(AgentSessionReviewError, match="reviewer"):
        validate_review(review, result)


def test_derivative_symlinks_and_invalid_review_preserve_report(tmp_path: Path) -> None:
    result = imported_result(tmp_path)
    report_path = write_report(result)
    original = report_path.read_bytes()
    review_dir = report_path.parent
    review_path = review_dir / REVIEW_PATH.name
    review_path.symlink_to(tmp_path / "outside.json")
    with pytest.raises(AgentSessionReviewError, match="must not be a symlink"):
        build_report(result)
    assert report_path.read_bytes() == original
    second = imported_result(tmp_path / "directory-symlink")
    (second / "agent-harness" / "review").symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(AgentSessionReviewError, match="review directory"):
        write_template(second, force=False)


def test_not_represented_fingerprint_binding(tmp_path: Path) -> None:
    result = imported_result(tmp_path)
    result_file = result / "llmgauge-result.json"
    data = json.loads(result_file.read_text(encoding="utf-8"))
    data.pop("run_fingerprint")
    result_file.write_text(json.dumps(data), encoding="utf-8")
    template = build_template(result)
    assert template["source"]["source_run_fingerprint_state"] == "not_represented"
    assert template["source"]["source_run_fingerprint"] is None
    validate_review(template, result, template=True)
    template["source"]["source_run_fingerprint_state"] = "represented"
    with pytest.raises(AgentSessionReviewError, match="not_represented"):
        validate_review(template, result, template=True)


def test_complete_evidence_allows_limited_not_assessable_findings(
    tmp_path: Path,
) -> None:
    result = imported_result(tmp_path)
    review = candidate(result)
    finding = review["findings"][0]
    finding["judgment_outcome"] = "not_assessable"
    finding["limitations"] = ["The preserved terminal does not assess this target."]
    validate_review(review, result)
    finding["limitations"] = []
    with pytest.raises(AgentSessionReviewError, match="limitations"):
        validate_review(review, result)
    finding["limitations"] = ["The preserved terminal does not assess this target."]
    finding["source_references"] = []
    with pytest.raises(AgentSessionReviewError, match="source references"):
        validate_review(review, result)


def test_complete_evidence_allows_evidence_limitation_annotation(
    tmp_path: Path,
) -> None:
    result = imported_result(tmp_path)
    review = candidate(result)
    review["declared_review_targets"].append("evidence_limitation")
    review["findings"].append(
        {
            "finding_id": "limitation-1",
            "finding_kind": "annotation",
            "target": "evidence_limitation",
            "judgment_outcome": None,
            "rationale": "The cited source does not establish the requested fact.",
            "source_references": [
                {"reference_type": "source_terminal", "reference_id": "source_terminal"}
            ],
            "reviewer": {"reviewer_id": "reviewer-1"},
            "reviewed_at_utc": "2026-08-13T00:00:00Z",
            "evidence_completeness": "complete",
            "attribution": {
                "values": ["missing_or_incomplete_evidence"],
                "state": "unavailable",
                "rationale": None,
            },
            "limitations": ["The required target evidence is unavailable."],
            "reviewer_tags": [],
        }
    )
    validate_review(review, result)


def test_partial_source_completeness_remains_bound(tmp_path: Path) -> None:
    result = imported_result(tmp_path, scenario="partial")
    review = candidate(result)
    review["findings"][0]["evidence_completeness"] = "partial"
    review["evidence_completeness"] = "partial"
    validate_review(review, result)


def test_producer_version_rendering_is_availability_bounded() -> None:
    available = _producer_version_summary(
        SimpleNamespace(availability="available", value="3.2.1")
    )
    unknown = _producer_version_summary(
        SimpleNamespace(availability="unknown", value="should-not-render")
    )
    assert "`3.2.1`" in available and "`available`" in available
    assert "`unknown`" in unknown and "should-not-render" not in unknown
