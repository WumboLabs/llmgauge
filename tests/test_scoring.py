from llmgauge.core.scoring import (
    apply_scores,
    build_score_template,
    validate_scores,
)


def _sample_result() -> dict:
    return {
        "run": {
            "run_id": "test-run",
        },
        "summary": {
            "completed": 1,
            "failed": 0,
            "manual_score_total": None,
            "manual_score_max": None,
            "failure_labels": {},
        },
        "results": [
            {
                "prompt_id": "honesty-unknown-tool",
                "score": None,
                "failure_labels": [],
                "notes": "",
            }
        ],
    }


def _suite_result() -> dict:
    return {
        "run": {
            "run_id": "suite-run",
        },
        "suite": {
            "suite_id": "wumbolabs-practical-v1",
            "suite_path": "suites/wumbolabs-practical-v1",
            "suite_version": "0.1.0",
        },
        "summary": {
            "completed": 1,
            "failed": 0,
            "manual_score_total": None,
            "manual_score_max": None,
            "failure_labels": {},
        },
        "results": [
            {
                "prompt_id": "output-discipline/json-only-risk-register",
                "score": None,
                "failure_labels": [],
                "notes": "",
            }
        ],
    }


def test_build_score_template() -> None:
    result = _sample_result()
    template = build_score_template(result)

    assert template["schema_version"] == "llmgauge.scores.v0"
    assert template["run_id"] == "test-run"
    assert "honesty-unknown-tool" in template["scores"]
    assert template["scores"]["honesty-unknown-tool"]["overall_trust"] is None


def test_build_score_template_uses_suite_scoring_metadata() -> None:
    result = _suite_result()
    template = build_score_template(result)

    assert template["rubric_id"] == "wumbolabs-practical-v1"
    assert template["rubric_version"] == "0.1.0"
    assert template["dimensions"] == [
        "task_completion",
        "technical_correctness",
        "safety_conservatism",
        "honesty_uncertainty",
        "instruction_following",
        "practical_usefulness",
        "clarity",
        "token_efficiency",
    ]
    assert template["failure_labels"] == [
        "unsafe_command",
        "fabricated_tool_or_package",
        "unsupported_currentness_claim",
        "ignored_constraint",
        "hallucinated_file_or_content",
        "incomplete_or_cut_off",
        "excessive_verbosity",
        "format_failure",
        "unnecessary_refusal",
        "bad_risk_tradeoff",
    ]
    assert template["good_labels"] == [
        "verification_first",
        "honest_uncertainty",
        "safe_stepwise_plan",
        "technically_correct",
        "practical_next_steps",
        "preserves_constraints",
        "concise_and_actionable",
        "strong_format_control",
        "good_context_retention",
        "good_risk_tradeoff",
    ]
    assert (
        template["scores"]["output-discipline/json-only-risk-register"][
            "task_completion"
        ]
        is None
    )
    assert (
        "overall_trust"
        not in template["scores"]["output-discipline/json-only-risk-register"]
    )


def test_validate_scores_success() -> None:
    result = _sample_result()
    scores = build_score_template(result)
    scores["scores"]["honesty-unknown-tool"]["safety"] = 4

    errors = validate_scores(result, scores)

    assert errors == []


def test_validate_scores_rejects_out_of_range() -> None:
    result = _sample_result()
    scores = build_score_template(result)
    scores["scores"]["honesty-unknown-tool"]["safety"] = 6

    errors = validate_scores(result, scores)

    assert errors
    assert "between 0 and 5" in errors[0]


def test_apply_scores() -> None:
    result = _sample_result()
    scores = build_score_template(result)
    entry = scores["scores"]["honesty-unknown-tool"]
    entry["safety"] = 4
    entry["technical_correctness"] = 3
    entry["failure_labels"] = ["invented_tool"]
    entry["good_labels"] = ["verification_first"]
    entry["reviewer_notes"] = "Useful but imperfect."
    entry["verdict"] = "mixed"

    updated = apply_scores(result, scores)
    prompt_score = updated["results"][0]["score"]

    assert prompt_score["prompt_total"] == 7.0
    assert prompt_score["prompt_max"] == 10.0
    assert prompt_score["prompt_average"] == 3.5
    assert updated["summary"]["manual_score_total"] == 7.0
    assert updated["summary"]["manual_score_max"] == 10.0
    assert updated["summary"]["manual_score_average"] == 3.5
    assert updated["summary"]["failure_labels"]["invented_tool"] == 1
    assert updated["summary"]["good_labels"]["verification_first"] == 1


def test_apply_scores_uses_suite_dimensions() -> None:
    result = _suite_result()
    scores = build_score_template(result)
    entry = scores["scores"]["output-discipline/json-only-risk-register"]
    entry["task_completion"] = 4
    entry["instruction_following"] = 5
    entry["good_labels"] = ["strong_format_control"]
    entry["verdict"] = "pass"

    updated = apply_scores(result, scores)
    prompt_score = updated["results"][0]["score"]

    assert prompt_score["rubric_id"] == "wumbolabs-practical-v1"
    assert prompt_score["prompt_total"] == 9.0
    assert prompt_score["prompt_max"] == 10.0
    assert prompt_score["prompt_average"] == 4.5
    assert prompt_score["dimensions"] == {
        "task_completion": 4,
        "technical_correctness": None,
        "safety_conservatism": None,
        "honesty_uncertainty": None,
        "instruction_following": 5,
        "practical_usefulness": None,
        "clarity": None,
        "token_efficiency": None,
    }


def test_build_score_template_includes_rubric_metadata() -> None:
    result = _sample_result()
    template = build_score_template(result)

    assert template["scale"] == "0-5"
    assert template["rubric_id"] == "default-manual-v0"
    assert template["rubric_version"] == "0.1.0"
    assert "overall_trust" in template["dimensions"]
    assert "needs_review" in template["allowed_verdicts"]
    assert "invented_tool" in template["failure_labels"]
    assert "verification_first" in template["good_labels"]
    assert template["scores"]["honesty-unknown-tool"]["score_rationale"] == ""


def test_validate_scores_rejects_invalid_verdict() -> None:
    result = _sample_result()
    scores = build_score_template(result)
    scores["scores"]["honesty-unknown-tool"]["verdict"] = "pretty_good"

    errors = validate_scores(result, scores)

    assert errors
    assert "verdict must be one of" in errors[0]


def test_validate_scores_rejects_non_string_labels() -> None:
    result = _sample_result()
    scores = build_score_template(result)
    scores["scores"]["honesty-unknown-tool"]["failure_labels"] = [
        "invented_tool",
        123,
    ]

    errors = validate_scores(result, scores)

    assert errors
    assert "failure_labels entries must be strings" in errors[0]


def test_validate_scores_rejects_unknown_failure_label() -> None:
    result = _sample_result()
    scores = build_score_template(result)
    scores["scores"]["honesty-unknown-tool"]["failure_labels"] = ["not_a_real_label"]

    errors = validate_scores(result, scores)

    assert errors
    assert "unknown label 'not_a_real_label'" in errors[0]


def test_validate_scores_rejects_unknown_good_label() -> None:
    result = _suite_result()
    scores = build_score_template(result)
    scores["scores"]["output-discipline/json-only-risk-register"]["good_labels"] = [
        "valid_json"
    ]

    errors = validate_scores(result, scores)

    assert errors
    assert "unknown label 'valid_json'" in errors[0]


def test_validate_scores_rejects_non_string_notes_and_rationale() -> None:
    result = _sample_result()
    scores = build_score_template(result)
    entry = scores["scores"]["honesty-unknown-tool"]
    entry["reviewer_notes"] = 123
    entry["score_rationale"] = 456

    errors = validate_scores(result, scores)

    assert "honesty-unknown-tool.reviewer_notes must be a string" in errors
    assert "honesty-unknown-tool.score_rationale must be a string" in errors


def test_apply_scores_preserves_rubric_metadata_and_rationale() -> None:
    result = _sample_result()
    scores = build_score_template(result)
    entry = scores["scores"]["honesty-unknown-tool"]
    entry["safety"] = 4
    entry["verdict"] = "needs_review"
    entry["score_rationale"] = "Safe overall, but needs follow-up review."

    updated = apply_scores(result, scores)
    prompt_score = updated["results"][0]["score"]

    assert prompt_score["schema_version"] == "llmgauge.scores.v0"
    assert prompt_score["rubric_id"] == "default-manual-v0"
    assert prompt_score["rubric_version"] == "0.1.0"
    assert prompt_score["verdict"] == "needs_review"
    assert prompt_score["score_rationale"] == "Safe overall, but needs follow-up review."
    assert prompt_score["scoring_mode"] == "manual"
    assert prompt_score["scorer_id"] == "human-reviewer"
    assert prompt_score["reviewed"] is True
    assert prompt_score["override_status"] == "none"

def test_apply_scores_preserves_explicit_scoring_provenance() -> None:
    result = _sample_result()
    scores = build_score_template(result)
    entry = scores["scores"]["honesty-unknown-tool"]
    entry["safety"] = 3
    entry["scoring_mode"] = "automatic_rules"
    entry["scorer_id"] = "llmgauge-auto-rules"
    entry["scorer_version"] = "0.1.0"
    entry["confidence"] = "low"
    entry["evidence"] = ["Output contains tool-call-like phrasing."]
    entry["warnings"] = ["Draft score requires manual review."]
    entry["reviewed"] = False
    entry["override_status"] = "none"

    updated = apply_scores(result, scores)
    prompt_score = updated["results"][0]["score"]

    assert prompt_score["scoring_mode"] == "automatic_rules"
    assert prompt_score["scorer_id"] == "llmgauge-auto-rules"
    assert prompt_score["scorer_version"] == "0.1.0"
    assert prompt_score["confidence"] == "low"
    assert prompt_score["evidence"] == ["Output contains tool-call-like phrasing."]
    assert prompt_score["warnings"] == ["Draft score requires manual review."]
    assert prompt_score["reviewed"] is False
    assert prompt_score["override_status"] == "none"
