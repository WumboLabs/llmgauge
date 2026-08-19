from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from llmgauge.core.generic_core_scoring import (
    GENERIC_CORE_MANUAL_RUBRIC_ID,
    GENERIC_CORE_VERSION,
    apply_deterministic_check,
    compose_hybrid_score,
    is_generic_core_suite,
    manual_review_state,
)
from llmgauge.core.suite import NormalizedPrompt, NormalizedSuite, ScoringRole


def build_portable_selection(suite: NormalizedSuite) -> dict[str, Any] | None:
    if not is_generic_core_suite(suite):
        return None
    return {
        "kind": suite.selection_kind,
        "selected_profile": suite.selected_profile,
        "selected_prompt_ids": list(suite.selected_prompt_ids),
        "canonical_prompt_ids": list(suite.canonical_prompt_ids),
        "default_profile": suite.default_profile,
    }


def build_method_provenance(prompt: NormalizedPrompt) -> dict[str, Any]:
    scoring = prompt.scoring
    if scoring is None:
        raise ValueError(
            "prompt-method-mismatch: Generic Core prompt scoring is incomplete"
        )
    method: dict[str, Any] = {"role": scoring.role.value}
    if scoring.deterministic_check is not None:
        method["deterministic_check"] = {
            "id": scoring.deterministic_check.id,
            "version": scoring.deterministic_check.version,
        }
    if scoring.manual_rubric is not None:
        method["manual_rubric"] = {
            "id": scoring.manual_rubric.id,
            "version": scoring.manual_rubric.version,
        }
    if scoring.hybrid_rule is not None:
        method["hybrid_rule"] = scoring.hybrid_rule
    return {
        "scoring_method": method,
        "fixture_references": [
            {"id": item.id, "version": item.version} for item in prompt.fixtures or ()
        ],
    }


def build_manual_review(
    prompt: NormalizedPrompt, score_entry: Mapping[str, Any] | None
) -> dict[str, Any]:
    if prompt.scoring is None or prompt.scoring.manual_rubric is None:
        raise ValueError(
            "prompt-method-mismatch: Generic Core prompt has no manual rubric"
        )
    state = manual_review_state(prompt.id, score_entry)
    return {
        "rubric_id": GENERIC_CORE_MANUAL_RUBRIC_ID,
        "rubric_version": GENERIC_CORE_VERSION,
        "review_state": state,
        "reviewed": state == "reviewed",
        "verdict": score_entry.get("verdict") if score_entry else None,
    }


def build_prompt_evidence(
    suite: NormalizedSuite,
    prompt: NormalizedPrompt,
    raw_response: str | None,
    *,
    generation_failed: bool,
) -> dict[str, Any] | None:
    if not is_generic_core_suite(suite):
        return None
    evidence = {**build_method_provenance(prompt)}
    scoring = prompt.scoring
    if scoring is None:
        raise ValueError(
            "prompt-method-mismatch: Generic Core prompt scoring is absent"
        )
    if scoring.role is ScoringRole.MANUAL:
        evidence["manual_review"] = build_manual_review(prompt, None)
        return evidence
    deterministic = apply_deterministic_check(
        suite, prompt.id, raw_response, generation_failed=generation_failed
    )
    evidence["deterministic_result"] = deterministic
    if scoring.role is ScoringRole.HYBRID:
        evidence["manual_review"] = build_manual_review(prompt, None)
        evidence["hybrid_composition"] = compose_hybrid_score(
            suite, prompt.id, deterministic, None
        )
    return evidence
