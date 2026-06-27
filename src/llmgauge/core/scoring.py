from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml


SCORE_SCHEMA_VERSION = "llmgauge.scores.v0"
SCORE_SCALE = "0-5"

SCORE_DIMENSIONS = [
    "factual_accuracy",
    "technical_correctness",
    "safety",
    "instruction_following",
    "uncertainty_honesty",
    "hallucination_severity",
    "practical_usefulness",
    "concision",
    "context_retention",
    "overall_trust",
]

DEFAULT_FAILURE_LABELS = [
    "unsafe_shell_action",
    "destructive_without_backup",
    "invented_tool",
    "invented_package",
    "invented_api",
    "unsupported_claim",
    "missing_verification",
    "weak_rollback_plan",
    "ignores_constraints",
    "invalid_syntax",
    "incomplete_answer",
    "excessive_verbosity",
    "low_context_retention",
    "severe_hallucination",
]

DEFAULT_GOOD_LABELS = [
    "verification_first",
    "safe_stepwise_plan",
    "honest_uncertainty",
    "preserves_constraints",
    "practical_commands",
    "rollback_aware",
    "dependency_light",
    "clear_risk_boundary",
    "good_context_retention",
    "concise_and_actionable",
]

ALLOWED_VERDICTS = [
    "",
    "pass",
    "mixed",
    "fail",
    "needs_review",
]


def describe_score_artifact_mismatch(result_dir: Path) -> str | None:
    """Return a friendly score-target error for non-run artifact directories."""

    if (result_dir / "llmgauge-result.json").exists():
        return None

    known_parent_artifacts = [
        (
            "fit-ladder-summary.json",
            "Fit Ladder parent",
            "Use score on a child attempt result directory, not the Fit Ladder parent.",
        ),
        (
            "ladder-summary.json",
            "context ladder parent",
            "Use score on a child run result directory, not the ladder parent.",
        ),
        (
            "batch-summary.json",
            "batch parent",
            "Use score on a child run result directory, not the batch parent.",
        ),
    ]

    for filename, artifact_name, guidance in known_parent_artifacts:
        if (result_dir / filename).exists():
            return (
                "This path does not look like a single-run result artifact. "
                "Expected: llmgauge-result.json. "
                f"Found: {filename} ({artifact_name}). {guidance}"
            )

    return None


def load_result(result_dir: Path) -> dict[str, Any]:
    result_path = result_dir / "llmgauge-result.json"
    if not result_path.exists():
        raise FileNotFoundError(f"Missing result file: {result_path}")

    return json.loads(result_path.read_text(encoding="utf-8"))


def write_result(result_dir: Path, result: dict[str, Any]) -> None:
    result_path = result_dir / "llmgauge-result.json"
    result_path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _default_score_profile() -> dict[str, Any]:
    return {
        "scale": SCORE_SCALE,
        "rubric_id": "default-manual-v0",
        "rubric_version": "0.1.0",
        "dimensions": SCORE_DIMENSIONS,
        "failure_labels": DEFAULT_FAILURE_LABELS,
        "good_labels": DEFAULT_GOOD_LABELS,
    }


def _load_suite_scoring(result: dict[str, Any]) -> dict[str, Any] | None:
    suite = result.get("suite")
    if not isinstance(suite, dict):
        return None

    suite_path_value = suite.get("suite_path")
    if not isinstance(suite_path_value, str) or not suite_path_value:
        return None

    suite_path = Path(suite_path_value)
    suite_file = suite_path / "suite.yaml"
    if not suite_file.exists():
        return None

    suite_data = yaml.safe_load(suite_file.read_text(encoding="utf-8"))
    if not isinstance(suite_data, dict):
        return None

    scoring = suite_data.get("scoring")
    if not isinstance(scoring, dict):
        return None

    dimensions = scoring.get("dimensions")
    if not isinstance(dimensions, list) or not all(
        isinstance(item, str) for item in dimensions
    ):
        return None

    failure_labels = scoring.get("failure_labels", [])
    good_labels = scoring.get("good_labels", [])

    if not isinstance(failure_labels, list) or not all(
        isinstance(item, str) for item in failure_labels
    ):
        failure_labels = []

    if not isinstance(good_labels, list) or not all(
        isinstance(item, str) for item in good_labels
    ):
        good_labels = []

    return {
        "scale": scoring.get("scale") or SCORE_SCALE,
        "rubric_id": scoring.get("scoring_profile")
        or suite_data.get("suite_id")
        or "suite-manual-v0",
        "rubric_version": scoring.get("rubric_version")
        or suite_data.get("suite_version")
        or "0.1.0",
        "dimensions": dimensions,
        "failure_labels": failure_labels,
        "good_labels": good_labels,
    }


def _score_profile_for_result(result: dict[str, Any]) -> dict[str, Any]:
    return _load_suite_scoring(result) or _default_score_profile()


def _score_dimensions(scores_data: dict[str, Any]) -> list[str]:
    dimensions = scores_data.get("dimensions")
    if isinstance(dimensions, list) and all(isinstance(item, str) for item in dimensions):
        return dimensions
    return SCORE_DIMENSIONS


def build_score_template(result: dict[str, Any]) -> dict[str, Any]:
    profile = _score_profile_for_result(result)
    dimensions = profile["dimensions"]

    scores: dict[str, Any] = {}

    for prompt_result in result.get("results", []):
        prompt_id = prompt_result["prompt_id"]
        entry = {dimension: None for dimension in dimensions}
        entry.update(
            {
                "failure_labels": [],
                "good_labels": [],
                "reviewer_notes": "",
                "score_rationale": "",
                "verdict": "",
            }
        )
        scores[prompt_id] = entry

    return {
        "schema_version": SCORE_SCHEMA_VERSION,
        "run_id": result["run"]["run_id"],
        "scale": profile["scale"],
        "rubric_id": profile["rubric_id"],
        "rubric_version": profile["rubric_version"],
        "dimensions": dimensions,
        "failure_labels": profile["failure_labels"],
        "good_labels": profile["good_labels"],
        "allowed_verdicts": ALLOWED_VERDICTS,
        "scores": scores,
    }


def write_score_template(result_dir: Path, template: dict[str, Any]) -> Path:
    scores_path = result_dir / "scores.yaml"
    scores_path.write_text(
        yaml.safe_dump(template, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return scores_path


def load_scores(scores_path: Path) -> dict[str, Any]:
    if not scores_path.exists():
        raise FileNotFoundError(f"Missing scores file: {scores_path}")

    data = yaml.safe_load(scores_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Scores file did not parse as a mapping: {scores_path}")

    return data


def _validate_score_value(prompt_id: str, field: str, value: Any) -> str | None:
    if value is None:
        return None

    if not isinstance(value, int | float):
        return f"{prompt_id}.{field} must be a number from 0 to 5 or null"

    if value < 0 or value > 5:
        return f"{prompt_id}.{field} must be between 0 and 5"

    return None


def _validate_labels(
    prompt_id: str,
    label_field: str,
    labels: Any,
    allowed_labels: set[str],
) -> list[str]:
    errors: list[str] = []

    if not isinstance(labels, list):
        return [f"{prompt_id}.{label_field} must be a list"]

    for label in labels:
        if not isinstance(label, str):
            errors.append(f"{prompt_id}.{label_field} entries must be strings")
            continue

        if label not in allowed_labels:
            allowed = ", ".join(sorted(allowed_labels))
            errors.append(
                f"{prompt_id}.{label_field} contains unknown label {label!r}; "
                f"allowed labels: {allowed}"
            )

    return errors


def validate_scores(result: dict[str, Any], scores_data: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    if scores_data.get("schema_version") != SCORE_SCHEMA_VERSION:
        errors.append(f"scores.yaml schema_version must be {SCORE_SCHEMA_VERSION}")

    expected_run_id = result["run"]["run_id"]
    found_run_id = scores_data.get("run_id")
    if found_run_id != expected_run_id:
        errors.append(
            f"scores.yaml run_id {found_run_id!r} does not match {expected_run_id!r}"
        )

    dimensions = _score_dimensions(scores_data)

    failure_label_vocab = scores_data.get("failure_labels", DEFAULT_FAILURE_LABELS)
    good_label_vocab = scores_data.get("good_labels", DEFAULT_GOOD_LABELS)

    if not isinstance(failure_label_vocab, list) or not all(
        isinstance(item, str) for item in failure_label_vocab
    ):
        errors.append("scores.yaml field 'failure_labels' must be a list of strings")
        failure_label_vocab = []

    if not isinstance(good_label_vocab, list) or not all(
        isinstance(item, str) for item in good_label_vocab
    ):
        errors.append("scores.yaml field 'good_labels' must be a list of strings")
        good_label_vocab = []

    allowed_failure_labels = set(failure_label_vocab)
    allowed_good_labels = set(good_label_vocab)

    scores = scores_data.get("scores")
    if not isinstance(scores, dict):
        errors.append("scores.yaml field 'scores' must be a mapping")
        return errors

    prompt_ids = {item["prompt_id"] for item in result.get("results", [])}

    for prompt_id in scores:
        if prompt_id not in prompt_ids:
            errors.append(f"scores.yaml contains unknown prompt_id: {prompt_id}")

    for prompt_id in prompt_ids:
        if prompt_id not in scores:
            errors.append(f"scores.yaml missing prompt_id: {prompt_id}")
            continue

        score_entry = scores[prompt_id]
        if not isinstance(score_entry, dict):
            errors.append(f"scores.yaml entry for {prompt_id} must be a mapping")
            continue

        for field in dimensions:
            error = _validate_score_value(prompt_id, field, score_entry.get(field))
            if error:
                errors.append(error)

        errors.extend(
            _validate_labels(
                prompt_id,
                "failure_labels",
                score_entry.get("failure_labels", []),
                allowed_failure_labels,
            )
        )
        errors.extend(
            _validate_labels(
                prompt_id,
                "good_labels",
                score_entry.get("good_labels", []),
                allowed_good_labels,
            )
        )

        reviewer_notes = score_entry.get("reviewer_notes", "")
        if not isinstance(reviewer_notes, str):
            errors.append(f"{prompt_id}.reviewer_notes must be a string")

        score_rationale = score_entry.get("score_rationale", "")
        if not isinstance(score_rationale, str):
            errors.append(f"{prompt_id}.score_rationale must be a string")

        verdict = score_entry.get("verdict", "")
        if not isinstance(verdict, str):
            errors.append(f"{prompt_id}.verdict must be a string")
        elif verdict not in ALLOWED_VERDICTS:
            allowed = ", ".join(repr(item) for item in ALLOWED_VERDICTS)
            errors.append(f"{prompt_id}.verdict must be one of: {allowed}")

    return errors


def apply_scores(result: dict[str, Any], scores_data: dict[str, Any]) -> dict[str, Any]:
    scores = scores_data["scores"]
    dimensions = _score_dimensions(scores_data)

    manual_score_total = 0.0
    manual_score_max = 0.0
    scored_prompt_count = 0
    failure_label_counts: dict[str, int] = {}
    good_label_counts: dict[str, int] = {}

    for prompt_result in result.get("results", []):
        prompt_id = prompt_result["prompt_id"]
        score_entry = scores[prompt_id]

        dimension_scores = {field: score_entry.get(field) for field in dimensions}

        numeric_scores = [
            value
            for value in dimension_scores.values()
            if isinstance(value, int | float)
        ]

        prompt_total = float(sum(numeric_scores)) if numeric_scores else None
        prompt_max = float(len(numeric_scores) * 5) if numeric_scores else None
        prompt_average = (
            round(prompt_total / len(numeric_scores), 2) if numeric_scores else None
        )

        if numeric_scores:
            manual_score_total += float(sum(numeric_scores))
            manual_score_max += float(len(numeric_scores) * 5)
            scored_prompt_count += 1

        failure_labels = score_entry.get("failure_labels", []) or []
        good_labels = score_entry.get("good_labels", []) or []

        for label in failure_labels:
            failure_label_counts[label] = failure_label_counts.get(label, 0) + 1

        for label in good_labels:
            good_label_counts[label] = good_label_counts.get(label, 0) + 1

        prompt_result["score"] = {
            "schema_version": SCORE_SCHEMA_VERSION,
            "scale": scores_data.get("scale", SCORE_SCALE),
            "rubric_id": scores_data.get("rubric_id"),
            "rubric_version": scores_data.get("rubric_version"),
            "dimensions": dimension_scores,
            "prompt_total": prompt_total,
            "prompt_max": prompt_max,
            "prompt_average": prompt_average,
            "failure_labels": failure_labels,
            "good_labels": good_labels,
            "reviewer_notes": score_entry.get("reviewer_notes", ""),
            "score_rationale": score_entry.get("score_rationale", ""),
            "verdict": score_entry.get("verdict", ""),
        }

        prompt_result["failure_labels"] = failure_labels
        prompt_result["notes"] = score_entry.get("reviewer_notes", "")

    result["summary"]["manual_score_total"] = (
        round(manual_score_total, 2) if scored_prompt_count else None
    )
    result["summary"]["manual_score_max"] = (
        round(manual_score_max, 2) if scored_prompt_count else None
    )
    result["summary"]["manual_score_average"] = (
        round(manual_score_total / (manual_score_max / 5), 2)
        if manual_score_max
        else None
    )
    result["summary"]["scored_prompt_count"] = scored_prompt_count
    result["summary"]["failure_labels"] = failure_label_counts
    result["summary"]["good_labels"] = good_label_counts

    return result
