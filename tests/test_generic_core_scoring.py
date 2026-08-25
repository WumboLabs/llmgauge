from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from llmgauge.core.generic_core_scoring import (
    apply_deterministic_check,
    compose_hybrid_score,
)
from llmgauge.core.suite import load_normalized_suite

ROOT = Path(__file__).parents[1]


@pytest.fixture(scope="module")
def suite():
    return load_normalized_suite(ROOT / "suites/generic-core-v1")


def _fixture(name: str) -> dict[str, object]:
    return json.loads(
        (ROOT / "suites/generic-core-v1/fixtures/v0.1.0" / name).read_text()
    )


def test_d1_and_d3_only_evaluate_declared_envelopes(suite) -> None:
    d1 = "1. Harborview repair clinic 18 October\n2. North Hall 09:30\n3. Registration free by 15 October"
    d3 = "Decisions\nThe review copy stays on the laptop.\nOpen questions\nWhich checklist applies?"
    assert (
        apply_deterministic_check(suite, "generic-core-instruction-rewrite-01", d1)[
            "outcome"
        ]
        == "pass"
    )
    assert (
        apply_deterministic_check(suite, "generic-core-summary-decision-log-01", d3)[
            "outcome"
        ]
        == "pass"
    )
    assert (
        apply_deterministic_check(
            suite, "generic-core-instruction-rewrite-01", "one line"
        )["outcome"]
        == "fail"
    )
    assert (
        apply_deterministic_check(
            suite, "generic-core-summary-decision-log-01", "Extra\ntext"
        )["outcome"]
        == "fail"
    )


@pytest.mark.parametrize(
    ("prompt_id", "fixture_path"),
    [
        ("generic-core-structured-json-01", "deterministic/typed-record-json.json"),
        ("generic-core-extraction-ledger-01", "deterministic/ledger-extraction.json"),
        ("generic-core-tool-record-lookup-01", "deterministic/tool-request.json"),
        (
            "generic-core-context-policy-reconcile-01",
            "bounded-context/reconciliation.json",
        ),
    ],
)
def test_closed_contract_checks_require_exact_json(
    suite, prompt_id: str, fixture_path: str
) -> None:
    fixture = _fixture(fixture_path)
    if "expected_value" in fixture:
        expected = fixture["expected_value"]
    elif "expected_request" in fixture:
        expected = fixture["expected_request"]
    else:
        expected = {"answers": fixture["answers"]}
    raw = json.dumps(expected, separators=(",", ":"))
    assert apply_deterministic_check(suite, prompt_id, raw)["outcome"] == "pass"
    assert (
        apply_deterministic_check(suite, prompt_id, raw + "\nexplanation")["outcome"]
        == "fail"
    )


def test_d5_is_not_run_and_cannot_become_a_pass(suite) -> None:
    result = apply_deterministic_check(
        suite,
        "generic-core-code-interval-merge-01",
        "def merge_intervals(xs): return xs",
    )
    assert result["outcome"] == "not_run"
    hybrid = compose_hybrid_score(
        suite, "generic-core-code-interval-merge-01", result, None
    )
    assert hybrid["complete"] is False
    assert hybrid["manual_component"]["review_state"] == "missing"


def test_d5_fail_closed_when_execution_authorization_is_not_false(
    suite, tmp_path: Path
) -> None:
    shutil.copytree(ROOT / "suites/generic-core-v1", tmp_path / "generic-core-v1")
    limits_path = (
        tmp_path / "generic-core-v1/fixtures/v0.1.0/coding/execution-limits.json"
    )
    limits = json.loads(limits_path.read_text())
    assert limits["execution_authorized"] is False
    limits["execution_authorized"] = True
    limits_path.write_text(json.dumps(limits))
    modified_suite = load_normalized_suite(tmp_path / "generic-core-v1")
    result = apply_deterministic_check(
        modified_suite,
        "generic-core-code-interval-merge-01",
        "def merge_intervals(intervals):\n    return sorted(intervals)",
    )
    assert result["outcome"] == "error"
    assert result["error_classification"] == "fixture-identity-mismatch"


def test_hybrid_components_remain_independent(suite) -> None:
    deterministic = apply_deterministic_check(
        suite,
        "generic-core-instruction-rewrite-01",
        "1. Harborview repair clinic 18 October\n2. North Hall 09:30\n3. Registration free by 15 October",
    )
    hybrid = compose_hybrid_score(
        suite, "generic-core-instruction-rewrite-01", deterministic, None
    )
    assert hybrid["deterministic_result"]["outcome"] == "pass"
    assert hybrid["manual_component"]["review_state"] == "missing"
    assert hybrid["complete"] is False
