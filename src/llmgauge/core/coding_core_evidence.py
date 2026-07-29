from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from llmgauge.core.static_scoring import (
    CODING_CORE_SUITE_ID,
    CODING_CORE_VERSION,
    applicable_manual_dimensions,
    apply_deterministic_check,
    compose_hybrid_score,
    manual_review_state,
)
from llmgauge.core.suite import NormalizedPrompt, NormalizedSuite, ScoringRole


def is_coding_core_suite(suite: NormalizedSuite) -> bool:
    return (
        suite.suite_id == CODING_CORE_SUITE_ID
        and suite.suite_version == CODING_CORE_VERSION
    )


def build_portable_selection(suite: NormalizedSuite) -> dict[str, Any] | None:
    if not is_coding_core_suite(suite):
        return None
    return {
        "kind": suite.selection_kind,
        "selected_profile": suite.selected_profile,
        "selected_prompt_ids": list(suite.selected_prompt_ids),
        "canonical_prompt_ids": list(suite.canonical_prompt_ids),
        "default_profile": suite.default_profile,
    }


def _logical_reference(reference: Any) -> dict[str, str]:
    return {"id": reference.id, "version": reference.version}


def build_method_provenance(prompt: NormalizedPrompt) -> dict[str, Any]:
    response_form = prompt.response_form
    scoring = prompt.scoring
    if response_form is None or scoring is None or scoring.manual_rubric is None:
        raise ValueError(
            "prompt-method-mismatch: Coding Core prompt method provenance is incomplete"
        )

    scoring_method: dict[str, Any] = {
        "role": scoring.role.value,
        "manual_rubric": _logical_reference(scoring.manual_rubric),
    }
    if scoring.deterministic_check is not None:
        scoring_method["deterministic_check"] = _logical_reference(
            scoring.deterministic_check
        )
    if scoring.hybrid_composition is not None:
        scoring_method["hybrid_composition"] = _logical_reference(
            scoring.hybrid_composition
        )

    return {
        "response_form": {
            "category": response_form.category.value,
            "id": response_form.definition.id,
            "version": response_form.definition.version,
        },
        "scoring_method": scoring_method,
    }


def build_manual_review(
    prompt: NormalizedPrompt,
    score_entry: Mapping[str, Any] | None,
) -> dict[str, Any]:
    scoring = prompt.scoring
    if scoring is None or scoring.manual_rubric is None:
        raise ValueError(
            "prompt-method-mismatch: Coding Core manual rubric provenance is incomplete"
        )
    state = manual_review_state(prompt.id, score_entry)
    return {
        "rubric_id": scoring.manual_rubric.id,
        "rubric_version": scoring.manual_rubric.version,
        "applicable_dimensions": list(applicable_manual_dimensions(prompt.id)),
        "review_state": state,
        "reviewed": state == "reviewed",
        "verdict": score_entry.get("verdict") if score_entry is not None else None,
    }


def build_prompt_evidence(
    suite: NormalizedSuite,
    prompt: NormalizedPrompt,
    raw_response: str | None,
    *,
    generation_failed: bool,
) -> dict[str, Any] | None:
    if not is_coding_core_suite(suite):
        return None

    evidence = {
        **build_method_provenance(prompt),
        "manual_review": build_manual_review(prompt, None),
    }
    scoring = prompt.scoring
    if scoring is None:
        raise ValueError(
            "prompt-method-mismatch: Coding Core prompt scoring method is absent"
        )
    if scoring.role is ScoringRole.MANUAL:
        return evidence
    if scoring.role is not ScoringRole.HYBRID:
        raise ValueError(
            "prompt-method-mismatch: Coding Core scoring role is unsupported"
        )

    deterministic = apply_deterministic_check(
        suite,
        prompt.id,
        raw_response,
        generation_failed=generation_failed,
    )
    evidence["deterministic_result"] = deterministic
    evidence["hybrid_composition"] = compose_hybrid_score(
        suite,
        prompt.id,
        deterministic,
        None,
    )
    return evidence
