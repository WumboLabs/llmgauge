from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import Any, Literal

from llmgauge.core.suite import NormalizedPrompt, NormalizedSuite, ScoringRole

GENERIC_CORE_SUITE_ID = "generic-core-v1"
GENERIC_CORE_VERSION = "0.1.0"
GENERIC_CORE_MANUAL_RUBRIC_ID = "default-manual-v0"
GENERIC_CORE_SIDE_BY_SIDE_ID = "generic-core-side-by-side-v0"
Outcome = Literal["pass", "fail", "error", "not_run"]
_MAX_RESPONSE_CHARS = 1_000_000
_MAX_EVIDENCE_ITEMS = 32

_CHECKS = {
    "generic-core-constraint-envelope-v0": "generic-core-instruction-rewrite-01",
    "generic-core-typed-record-json-v0": "generic-core-structured-json-01",
    "generic-core-summary-envelope-v0": "generic-core-summary-decision-log-01",
    "generic-core-ledger-extraction-v0": "generic-core-extraction-ledger-01",
    "generic-core-interval-function-v0": "generic-core-code-interval-merge-01",
    "generic-core-tool-request-v0": "generic-core-tool-record-lookup-01",
    "generic-core-context-reconciliation-v0": "generic-core-context-policy-reconcile-01",
}
_MANUAL_DIMENSIONS = {
    "generic-core-instruction-rewrite-01": (
        "instruction_following",
        "factual_accuracy",
        "context_retention",
        "concision",
    ),
    "generic-core-honesty-evidence-gap-01": (
        "uncertainty_honesty",
        "factual_accuracy",
        "hallucination_severity",
        "overall_trust",
    ),
    "generic-core-summary-decision-log-01": (
        "factual_accuracy",
        "instruction_following",
        "context_retention",
        "concision",
    ),
    "generic-core-plan-dependencies-01": (
        "instruction_following",
        "technical_correctness",
        "safety",
        "practical_usefulness",
        "overall_trust",
    ),
    "generic-core-explain-cache-protocol-01": (
        "factual_accuracy",
        "technical_correctness",
        "concision",
        "practical_usefulness",
    ),
    "generic-core-code-interval-merge-01": (
        "technical_correctness",
        "instruction_following",
        "practical_usefulness",
        "overall_trust",
    ),
    "generic-core-review-window-average-01": (
        "factual_accuracy",
        "technical_correctness",
        "instruction_following",
        "practical_usefulness",
        "overall_trust",
    ),
    "generic-core-troubleshoot-staged-pipeline-01": (
        "technical_correctness",
        "uncertainty_honesty",
        "safety",
        "practical_usefulness",
        "overall_trust",
    ),
    "generic-core-safety-risky-heating-01": (
        "safety",
        "instruction_following",
        "factual_accuracy",
        "practical_usefulness",
        "overall_trust",
    ),
}


def is_generic_core_suite(suite: NormalizedSuite) -> bool:
    return (
        suite.suite_id == GENERIC_CORE_SUITE_ID
        and suite.suite_version == GENERIC_CORE_VERSION
    )


def _evidence(property_name: str, status: Outcome, detail: str) -> dict[str, str]:
    return {"property": property_name, "status": status, "detail": detail[:256]}


def _json(text: str) -> Any:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate object key")
            result[key] = value
        return result

    return json.loads(
        text,
        object_pairs_hook=reject_duplicates,
        parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)),
    )


def _same(value: Any, expected: Any) -> bool:
    if type(value) is not type(expected):
        return False
    if isinstance(value, dict):
        return list(value) == list(expected) and all(
            _same(value[key], expected[key]) for key in value
        )
    if isinstance(value, list):
        return len(value) == len(expected) and all(
            _same(left, right) for left, right in zip(value, expected, strict=True)
        )
    return value == expected


def _prompt(suite: NormalizedSuite, prompt_id: str) -> NormalizedPrompt:
    if not is_generic_core_suite(suite):
        raise ValueError(
            "unsupported-suite: Generic Core suite ID/version is unsupported"
        )
    prompt = next((item for item in suite.prompts if item.id == prompt_id), None)
    if prompt is None:
        raise ValueError("unsupported-prompt: Generic Core prompt is unsupported")
    return prompt


def _fixture(
    suite: NormalizedSuite, prompt: NormalizedPrompt, fixture_id: str
) -> Mapping[str, Any]:
    fixture = next(
        (item for item in prompt.fixtures or () if item.id == fixture_id), None
    )
    if fixture is None or fixture.version != GENERIC_CORE_VERSION:
        raise ValueError("fixture-unavailable")
    candidate = suite.suite_root / fixture.path
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(suite.suite_root)
        data = _json(resolved.read_text(encoding="utf-8"))
    except (
        OSError,
        RuntimeError,
        UnicodeError,
        ValueError,
        json.JSONDecodeError,
    ) as error:
        raise ValueError("fixture-unavailable") from error
    if (
        not isinstance(data, dict)
        or data.get("resource_id") != fixture_id
        or data.get("version") != GENERIC_CORE_VERSION
    ):
        raise ValueError("fixture-identity-mismatch")
    return data


def _closed_json(
    raw_response: str, fixture: Mapping[str, Any], property_name: str
) -> list[dict[str, str]]:
    try:
        value = _json(raw_response)
    except (json.JSONDecodeError, ValueError):
        return [
            _evidence(
                "json",
                "fail",
                "response must be one valid JSON value with no extra prose",
            )
        ]
    if "expected_value" in fixture:
        expected = fixture["expected_value"]
    elif "expected_request" in fixture:
        expected = fixture["expected_request"]
    else:
        expected = {"answers": fixture["answers"]}
    return [
        _evidence(
            property_name,
            "pass" if _same(value, expected) else "fail",
            "response matches the closed versioned JSON contract"
            if _same(value, expected)
            else "response differs from the closed versioned JSON contract",
        )
    ]


def _constraint(raw_response: str, fixture: Mapping[str, Any]) -> list[dict[str, str]]:
    response = fixture["response"]
    fields = fixture["literal_fields"]
    lines = raw_response.splitlines()
    evidence: list[dict[str, str]] = [
        _evidence(
            "line-count",
            "pass" if len(lines) == response["line_count"] else "fail",
            "response has the required number of lines"
            if len(lines) == response["line_count"]
            else "response has an invalid line count",
        )
    ]
    for index, line in enumerate(lines[: response["line_count"]]):
        prefix = f"{index + 1}."
        evidence.append(
            _evidence(
                f"numbering-{index + 1}",
                "pass" if line.startswith(prefix) else "fail",
                "line has required decimal-period numbering"
                if line.startswith(prefix)
                else "line lacks required decimal-period numbering",
            )
        )
        words = re.findall(r"\S+", line[len(prefix) :])
        evidence.append(
            _evidence(
                f"word-bound-{index + 1}",
                "pass" if len(words) <= response["max_words_per_line"] else "fail",
                "line is within the declared word bound"
                if len(words) <= response["max_words_per_line"]
                else "line exceeds the declared word bound",
            )
        )
        for field in response["required_line_fields"][index]:
            expected = fields[field]
            evidence.append(
                _evidence(
                    f"literal-{field}",
                    "pass" if expected in line else "fail",
                    "required fixture literal is present"
                    if expected in line
                    else "required fixture literal is absent",
                )
            )
    return evidence


def _summary(raw_response: str, fixture: Mapping[str, Any]) -> list[dict[str, str]]:
    response = fixture["response"]
    lines = raw_response.splitlines()
    headings = [line.strip() for line in lines if line.strip() in response["sections"]]
    other_headings = [
        line.strip()
        for line in lines
        if re.fullmatch(r"[A-Za-z][A-Za-z ]*", line.strip())
        and line.strip() not in response["sections"]
    ]
    words = re.findall(r"\S+", raw_response)
    return [
        _evidence(
            "sections",
            "pass" if headings == response["sections"] else "fail",
            "required sections appear exactly in declared order"
            if headings == response["sections"]
            else "required section structure is invalid",
        ),
        _evidence(
            "additional-sections",
            "pass" if not other_headings else "fail",
            "response has no additional section headings"
            if not other_headings
            else "response has an additional section heading",
        ),
        _evidence(
            "word-bound",
            "pass" if len(words) <= response["max_total_words"] else "fail",
            "response is within the declared word bound"
            if len(words) <= response["max_total_words"]
            else "response exceeds the declared word bound",
        ),
    ]


def apply_deterministic_check(
    suite: NormalizedSuite,
    prompt_id: str,
    raw_response: str | None,
    *,
    generation_failed: bool = False,
) -> dict[str, Any]:
    prompt = _prompt(suite, prompt_id)
    scoring = prompt.scoring
    if scoring is None or scoring.deterministic_check is None:
        raise ValueError("prompt-method-mismatch: prompt has no deterministic check")
    check = scoring.deterministic_check
    if check.version != GENERIC_CORE_VERSION or _CHECKS.get(check.id) != prompt.id:
        raise ValueError(
            "unsupported-method: deterministic check ID/version is unsupported"
        )
    base = {
        "prompt_id": prompt.id,
        "check_id": check.id,
        "check_version": check.version,
    }
    if raw_response is None or (generation_failed and raw_response == ""):
        return {
            **base,
            "outcome": "not_run",
            "evidence": [
                _evidence(
                    "raw-response",
                    "not_run",
                    "raw response evidence is absent after generation failure"
                    if generation_failed
                    else "raw response evidence is absent",
                )
            ],
            "error_classification": None,
        }
    if not isinstance(raw_response, str):
        return {
            **base,
            "outcome": "error",
            "evidence": [
                _evidence(
                    "raw-response",
                    "error",
                    "raw response evidence has an unsupported type",
                )
            ],
            "error_classification": "invalid-input",
        }
    if len(raw_response) > _MAX_RESPONSE_CHARS:
        return {
            **base,
            "outcome": "error",
            "evidence": [
                _evidence(
                    "raw-response",
                    "error",
                    "raw response exceeds the local parsing bound",
                )
            ],
            "error_classification": "resource-bound",
        }
    if check.id == "generic-core-interval-function-v0":
        limits = _fixture(suite, prompt, "generic-core-interval-execution-limits-v0")
        if limits.get("execution_authorized") is not False:
            return {
                **base,
                "outcome": "error",
                "evidence": [
                    _evidence(
                        "execution-authorization",
                        "error",
                        "D5 execution authorization must remain false",
                    )
                ],
                "error_classification": "fixture-identity-mismatch",
            }
        return {
            **base,
            "outcome": "not_run",
            "evidence": [
                _evidence(
                    "execution",
                    "not_run",
                    "generated code execution is not authorized by the versioned resource",
                )
            ],
            "error_classification": None,
        }
    try:
        fixture = _fixture(suite, prompt, check.id)
        if check.id == "generic-core-constraint-envelope-v0":
            evidence = _constraint(raw_response, fixture)
        elif check.id == "generic-core-summary-envelope-v0":
            evidence = _summary(raw_response, fixture)
        else:
            evidence = _closed_json(raw_response, fixture, "closed-contract")
    except ValueError as error:
        return {
            **base,
            "outcome": "error",
            "evidence": [
                _evidence(
                    "fixture",
                    "error",
                    "selected versioned fixture is unavailable or invalid",
                )
            ],
            "error_classification": str(error),
        }
    outcome: Outcome = (
        "fail" if any(item["status"] == "fail" for item in evidence) else "pass"
    )
    return {
        **base,
        "outcome": outcome,
        "evidence": evidence[:_MAX_EVIDENCE_ITEMS],
        "error_classification": None,
    }


def manual_review_state(prompt_id: str, score_entry: Mapping[str, Any] | None) -> str:
    dimensions = _MANUAL_DIMENSIONS.get(prompt_id)
    if dimensions is None:
        raise ValueError(
            "unsupported-prompt: Generic Core manual rubric prompt is unsupported"
        )
    if score_entry is None:
        return "missing"
    if not isinstance(score_entry, Mapping):
        raise ValueError("invalid-manual-component: manual component is malformed")
    if score_entry.get("reviewed") is not True:
        return "unreviewed"
    values = score_entry.get("dimensions", score_entry)
    if not isinstance(values, Mapping):
        raise ValueError("invalid-manual-component: manual component is malformed")
    valid = sum(
        not isinstance(values.get(name), bool)
        and isinstance(values.get(name), int | float)
        and 0 <= values[name] <= 5
        for name in dimensions
    )
    if (
        valid == len(dimensions)
        and score_entry.get("verdict") in {"pass", "mixed", "fail"}
        and isinstance(score_entry.get("score_rationale"), str)
        and score_entry["score_rationale"].strip()
        and isinstance(score_entry.get("scorer_id"), str)
        and score_entry["scorer_id"].strip()
    ):
        return "reviewed"
    return "partial" if valid else "unscoreable"


def compose_hybrid_score(
    suite: NormalizedSuite,
    prompt_id: str,
    deterministic_result: Mapping[str, Any],
    manual_score_entry: Mapping[str, Any] | None,
) -> dict[str, Any]:
    prompt = _prompt(suite, prompt_id)
    if (
        prompt.scoring is None
        or prompt.scoring.role is not ScoringRole.HYBRID
        or prompt.scoring.hybrid_rule != "side-by-side"
    ):
        raise ValueError(
            "prompt-method-mismatch: prompt has no supported hybrid composition"
        )
    expected = apply_deterministic_check(suite, prompt_id, None)
    required = set(expected)
    if (
        not isinstance(deterministic_result, Mapping)
        or set(deterministic_result) != required
        or deterministic_result.get("prompt_id") != prompt_id
        or deterministic_result.get("check_id") != prompt.scoring.deterministic_check.id
        or deterministic_result.get("check_version") != GENERIC_CORE_VERSION
        or deterministic_result.get("outcome")
        not in {"pass", "fail", "error", "not_run"}
    ):
        raise ValueError(
            "invalid-deterministic-component: deterministic component is malformed or inconsistent"
        )
    state = manual_review_state(prompt_id, manual_score_entry)
    return {
        "prompt_id": prompt_id,
        "composition_id": GENERIC_CORE_SIDE_BY_SIDE_ID,
        "composition_version": GENERIC_CORE_VERSION,
        "deterministic_result": dict(deterministic_result),
        "manual_component": {
            "rubric_id": GENERIC_CORE_MANUAL_RUBRIC_ID,
            "rubric_version": GENERIC_CORE_VERSION,
            "review_state": state,
            "reviewed": state == "reviewed",
            "verdict": manual_score_entry.get("verdict")
            if manual_score_entry
            else None,
        },
        "complete": deterministic_result["outcome"] in {"pass", "fail"}
        and state == "reviewed",
    }
