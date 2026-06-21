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

ALLOWED_VERDICTS = [
    "",
    "pass",
    "mixed",
    "fail",
    "needs_review",
]


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


def build_score_template(result: dict[str, Any]) -> dict[str, Any]:
    scores: dict[str, Any] = {}

    for prompt_result in result.get("results", []):
        prompt_id = prompt_result["prompt_id"]
        scores[prompt_id] = {
            "factual_accuracy": None,
            "technical_correctness": None,
            "safety": None,
            "instruction_following": None,
            "uncertainty_honesty": None,
            "hallucination_severity": None,
            "practical_usefulness": None,
            "concision": None,
            "context_retention": None,
            "overall_trust": None,
            "failure_labels": [],
            "good_labels": [],
            "reviewer_notes": "",
            "score_rationale": "",
            "verdict": "",
        }

    return {
        "schema_version": SCORE_SCHEMA_VERSION,
        "run_id": result["run"]["run_id"],
        "scale": SCORE_SCALE,
        "rubric_id": "default-manual-v0",
        "rubric_version": "0.1.0",
        "dimensions": SCORE_DIMENSIONS,
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

        for field in SCORE_DIMENSIONS:
            error = _validate_score_value(prompt_id, field, score_entry.get(field))
            if error:
                errors.append(error)

        for label_field in ["failure_labels", "good_labels"]:
            labels = score_entry.get(label_field, [])
            if not isinstance(labels, list):
                errors.append(f"{prompt_id}.{label_field} must be a list")
                continue

            for label in labels:
                if not isinstance(label, str):
                    errors.append(f"{prompt_id}.{label_field} entries must be strings")

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

    manual_score_total = 0.0
    manual_score_max = 0.0
    scored_prompt_count = 0
    failure_label_counts: dict[str, int] = {}
    good_label_counts: dict[str, int] = {}

    for prompt_result in result.get("results", []):
        prompt_id = prompt_result["prompt_id"]
        score_entry = scores[prompt_id]

        dimension_scores = {field: score_entry.get(field) for field in SCORE_DIMENSIONS}

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
            "scale": SCORE_SCALE,
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
