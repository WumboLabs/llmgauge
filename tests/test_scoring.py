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


def test_build_score_template() -> None:
    result = _sample_result()
    template = build_score_template(result)

    assert template["schema_version"] == "llmgauge.scores.v0"
    assert template["run_id"] == "test-run"
    assert "honesty-unknown-tool" in template["scores"]
    assert template["scores"]["honesty-unknown-tool"]["overall_trust"] is None


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
    entry["failure_labels"] = ["hallucinated_tool"]
    entry["good_labels"] = ["good_verification"]
    entry["reviewer_notes"] = "Useful but imperfect."
    entry["verdict"] = "mixed pass"

    updated = apply_scores(result, scores)
    prompt_score = updated["results"][0]["score"]

    assert prompt_score["prompt_total"] == 7.0
    assert prompt_score["prompt_max"] == 10.0
    assert prompt_score["prompt_average"] == 3.5
    assert updated["summary"]["manual_score_total"] == 7.0
    assert updated["summary"]["manual_score_max"] == 10.0
    assert updated["summary"]["manual_score_average"] == 3.5
    assert updated["summary"]["failure_labels"]["hallucinated_tool"] == 1
    assert updated["summary"]["good_labels"]["good_verification"] == 1

def test_build_score_template_includes_rubric_metadata() -> None:
    result = _sample_result()
    template = build_score_template(result)

    assert template["scale"] == "0-5"
    assert template["rubric_id"] == "default-manual-v0"
    assert template["rubric_version"] == "0.1.0"
    assert "overall_trust" in template["dimensions"]
    assert "needs_review" in template["allowed_verdicts"]
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
    scores["scores"]["honesty-unknown-tool"]["failure_labels"] = ["ok", 123]

    errors = validate_scores(result, scores)

    assert errors
    assert "failure_labels entries must be strings" in errors[0]


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
