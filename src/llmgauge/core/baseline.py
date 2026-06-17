from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


BASELINE_SCHEMA_VERSION = "llmgauge.baseline.v0"
SUPPORTED_BASELINE_MODES = {"checklist", "exact"}


def load_baseline(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Missing baseline file: {path}")

    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Baseline file did not parse as a mapping: {path}")

    return data


def validate_baseline(baseline: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    if baseline.get("schema_version") != BASELINE_SCHEMA_VERSION:
        errors.append(f"schema_version must be {BASELINE_SCHEMA_VERSION}")

    prompt_id = baseline.get("prompt_id")
    if not isinstance(prompt_id, str) or not prompt_id.strip():
        errors.append("prompt_id must be a non-empty string")

    mode = baseline.get("mode")
    if mode not in SUPPORTED_BASELINE_MODES:
        supported = ", ".join(sorted(SUPPORTED_BASELINE_MODES))
        errors.append(f"mode must be one of: {supported}")

    for field in [
        "must_include",
        "must_not_include",
        "hard_fail_if",
        "suggested_good_labels",
        "suggested_failure_labels",
    ]:
        value = baseline.get(field, [])
        if not isinstance(value, list):
            errors.append(f"{field} must be a list")
            continue

        for index, item in enumerate(value):
            if not isinstance(item, str) or not item.strip():
                errors.append(f"{field}[{index}] must be a non-empty string")

    return errors


def normalize_for_baseline_match(text: str) -> str:
    return " ".join(text.casefold().split())


def _contains_normalized(output_text: str, needle: str) -> bool:
    normalized_output = normalize_for_baseline_match(output_text)
    normalized_needle = normalize_for_baseline_match(needle)
    return normalized_needle in normalized_output


def check_output_against_baseline(
    *,
    prompt_id: str,
    output_text: str,
    baseline: dict[str, Any],
) -> dict[str, Any]:
    errors = validate_baseline(baseline)
    if errors:
        return {
            "prompt_id": prompt_id,
            "baseline_prompt_id": baseline.get("prompt_id"),
            "status": "invalid_baseline",
            "errors": errors,
            "missing_required": [],
            "forbidden_present": [],
            "hard_failures": [],
            "suggested_good_labels": [],
            "suggested_failure_labels": ["invalid_baseline"],
        }

    baseline_prompt_id = baseline["prompt_id"]
    if baseline_prompt_id != prompt_id:
        return {
            "prompt_id": prompt_id,
            "baseline_prompt_id": baseline_prompt_id,
            "status": "wrong_prompt",
            "errors": [
                f"baseline prompt_id {baseline_prompt_id!r} does not match {prompt_id!r}"
            ],
            "missing_required": [],
            "forbidden_present": [],
            "hard_failures": [],
            "suggested_good_labels": [],
            "suggested_failure_labels": ["wrong_prompt_baseline"],
        }

    must_include = baseline.get("must_include", [])
    must_not_include = baseline.get("must_not_include", [])
    hard_fail_if = baseline.get("hard_fail_if", [])

    missing_required = [
        item for item in must_include if not _contains_normalized(output_text, item)
    ]
    forbidden_present = [
        item for item in must_not_include if _contains_normalized(output_text, item)
    ]
    hard_failures = [
        item for item in hard_fail_if if _contains_normalized(output_text, item)
    ]

    if hard_failures:
        status = "fail"
    elif missing_required or forbidden_present:
        status = "mixed"
    else:
        status = "pass"

    suggested_good_labels = list(baseline.get("suggested_good_labels", []))
    suggested_failure_labels = list(baseline.get("suggested_failure_labels", []))

    if missing_required:
        suggested_failure_labels.append("missing_required_baseline_item")
    if forbidden_present:
        suggested_failure_labels.append("forbidden_baseline_item_present")
    if hard_failures:
        suggested_failure_labels.append("baseline_hard_fail")

    return {
        "prompt_id": prompt_id,
        "baseline_prompt_id": baseline_prompt_id,
        "status": status,
        "errors": [],
        "missing_required": missing_required,
        "forbidden_present": forbidden_present,
        "hard_failures": hard_failures,
        "suggested_good_labels": sorted(set(suggested_good_labels)),
        "suggested_failure_labels": sorted(set(suggested_failure_labels)),
    }


def baseline_path_for_prompt(suite_dir: Path, prompt_id: str) -> Path:
    safe_prompt_id = prompt_id.replace("/", "__")
    return suite_dir / "baselines" / f"{safe_prompt_id}.yaml"


def load_suite_baselines(suite_dir: Path) -> dict[str, dict[str, Any]]:
    baselines_dir = suite_dir / "baselines"
    if not baselines_dir.exists():
        return {}

    baselines: dict[str, dict[str, Any]] = {}
    for baseline_file in sorted(baselines_dir.glob("*.yaml")):
        baseline = load_baseline(baseline_file)
        prompt_id = baseline.get("prompt_id")
        if isinstance(prompt_id, str) and prompt_id:
            baselines[prompt_id] = baseline

    return baselines


def output_text_for_prompt_result(
    result_dir: Path, prompt_result: dict[str, Any]
) -> str:
    output_path = prompt_result.get("output_path")
    if not isinstance(output_path, str) or not output_path:
        return ""

    path = result_dir / output_path
    if not path.exists():
        return ""

    return path.read_text(encoding="utf-8", errors="replace")


def check_result_against_baselines(
    *,
    result_dir: Path,
    suite_dir: Path,
    result: dict[str, Any],
) -> dict[str, Any]:
    baselines = load_suite_baselines(suite_dir)
    checks: list[dict[str, Any]] = []

    for prompt_result in result.get("results", []):
        prompt_id = prompt_result.get("prompt_id")
        if not isinstance(prompt_id, str) or not prompt_id:
            continue

        baseline = baselines.get(prompt_id)
        if baseline is None:
            checks.append(
                {
                    "prompt_id": prompt_id,
                    "status": "missing_baseline",
                    "errors": [],
                    "missing_required": [],
                    "forbidden_present": [],
                    "hard_failures": [],
                    "suggested_good_labels": [],
                    "suggested_failure_labels": ["missing_baseline"],
                }
            )
            continue

        output_text = output_text_for_prompt_result(result_dir, prompt_result)
        checks.append(
            check_output_against_baseline(
                prompt_id=prompt_id,
                output_text=output_text,
                baseline=baseline,
            )
        )

    status_counts: dict[str, int] = {}
    for check in checks:
        status = str(check.get("status", "unknown"))
        status_counts[status] = status_counts.get(status, 0) + 1

    return {
        "schema_version": "llmgauge.baseline_check.v0",
        "run_id": result.get("run", {}).get("run_id"),
        "suite_id": result.get("suite", {}).get("suite_id"),
        "result_dir": str(result_dir),
        "suite_dir": str(suite_dir),
        "status_counts": status_counts,
        "checks": checks,
    }
