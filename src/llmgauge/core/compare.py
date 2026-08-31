from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from llmgauge.core.scoring import scoring_evidence_summary
from llmgauge.core.reports import _vllm_transport_display
from llmgauge.core.result_validation import _validate_vllm_transport_consistency
from llmgauge.core.run_fingerprint import (
    FingerprintUnavailable,
    resolve_contained_result_artifact,
)


def load_compare_result(result_dir: Path) -> dict[str, Any]:
    result_path = result_dir / "llmgauge-result.json"
    if not result_path.exists():
        raise FileNotFoundError(f"Missing result file: {result_path}")

    result = json.loads(result_path.read_text(encoding="utf-8"))
    transport_errors = _validate_vllm_transport_consistency(result_dir, result)
    if transport_errors:
        raise ValueError(
            "Source result validation failed: " + "; ".join(transport_errors[:5])
        )
    result["_result_dir"] = str(result_dir)
    observation_methods: set[str] = set()
    runtime = result.get("runtime")
    prompt_results = result.get("results")
    if (
        isinstance(runtime, dict)
        and runtime.get("backend") == "vllm"
        and isinstance(prompt_results, list)
    ):
        for prompt_result in prompt_results:
            if not isinstance(prompt_result, dict):
                continue
            request_path_value = prompt_result.get("request_evidence_path")
            if not isinstance(request_path_value, str) or not request_path_value:
                continue
            try:
                request_path = resolve_contained_result_artifact(
                    result_dir,
                    request_path_value,
                    label="comparison request evidence",
                    require_file=True,
                )
                request_evidence = json.loads(request_path.read_text(encoding="utf-8"))
            except (
                FingerprintUnavailable,
                OSError,
                UnicodeDecodeError,
                json.JSONDecodeError,
            ) as exc:
                raise ValueError(
                    "Comparison request evidence changed after source validation"
                ) from exc
            observation_method = (
                request_evidence.get("observation_method")
                if isinstance(request_evidence, dict)
                else None
            )
            if isinstance(observation_method, str) and observation_method:
                observation_methods.add(observation_method)
    result["_vllm_transport_observation_methods"] = sorted(observation_methods)
    return result


def compare_results(results: list[dict[str, Any]]) -> str:
    """Route a loaded result set to the accepted comparison surface.

    All-transcript sets use the bounded structural transcript comparison;
    mixed transcript/single-turn sets fail closed; single-turn sets keep the
    existing report unchanged.
    """
    transcript_flags = [result.get("transcript") is not None for result in results]
    if any(transcript_flags):
        if not all(transcript_flags):
            raise ValueError(
                "Comparing transcript-bearing results with single-turn "
                "results fails closed; transcripts and flattened single-turn "
                "evidence are different evaluation classes"
            )
        from llmgauge.core.transcript_compare import (
            build_transcript_compare_report,
        )

        return build_transcript_compare_report(results)
    return build_compare_report(results)


def _fmt(value: Any) -> str:
    return "None" if value is None else str(value)


def _vendor_aligned_profile_present(results: list[dict[str, Any]]) -> bool:
    return any(
        isinstance(result.get("runtime", {}).get("profile"), dict)
        and result.get("runtime", {}).get("profile", {}).get("profile_kind")
        == "vendor_aligned"
        for result in results
    )


def _score_dict(prompt_result: dict[str, Any]) -> dict[str, Any]:
    score = prompt_result.get("score")
    return score if isinstance(score, dict) else {}


def _score_average(prompt_result: dict[str, Any]) -> Any:
    return _score_dict(prompt_result).get("prompt_average")


def _score_dimension(prompt_result: dict[str, Any], dimension: str) -> Any:
    dimensions = _score_dict(prompt_result).get("dimensions", {})
    if not isinstance(dimensions, dict):
        return None
    return dimensions.get(dimension)


def _score_failure_labels(prompt_result: dict[str, Any]) -> list[str]:
    labels = _score_dict(prompt_result).get("failure_labels", [])
    return labels if isinstance(labels, list) else []


def _score_total_fraction(result: dict[str, Any]) -> str:
    summary = result.get("summary", {})
    total = summary.get("manual_score_total")
    maximum = summary.get("manual_score_max")
    if total is None or maximum is None:
        return "None"
    return f"{total}/{maximum}"


def _fmt_vram(value: Any) -> str:
    return "-" if value is None else str(value)


def _vram_peak_used_mib(prompt_result: dict[str, Any] | None) -> int | None:
    if prompt_result is None:
        return None

    vram = prompt_result.get("vram")
    if not isinstance(vram, dict) or not vram.get("available"):
        return None

    peak_used_mib = vram.get("peak_used_mib")
    if not isinstance(peak_used_mib, int):
        return None

    return peak_used_mib


def _vram_headroom_mib(prompt_result: dict[str, Any] | None) -> int | None:
    if prompt_result is None:
        return None

    vram = prompt_result.get("vram")
    if not isinstance(vram, dict) or not vram.get("available"):
        return None

    peak_used_mib = vram.get("peak_used_mib")
    peak_total_mib = vram.get("peak_total_mib")
    if not isinstance(peak_used_mib, int) or not isinstance(peak_total_mib, int):
        return None

    return peak_total_mib - peak_used_mib


def _result_peak_vram_mib(result: dict[str, Any]) -> int | None:
    values = [
        value
        for value in (
            _vram_peak_used_mib(prompt_result)
            for prompt_result in result.get("results", [])
        )
        if value is not None
    ]
    return max(values) if values else None


def _result_min_vram_headroom_mib(result: dict[str, Any]) -> int | None:
    values = [
        value
        for value in (
            _vram_headroom_mib(prompt_result)
            for prompt_result in result.get("results", [])
        )
        if value is not None
    ]
    return min(values) if values else None


def _prompt_verdict_cell(prompt_result: dict[str, Any]) -> str:
    score = _score_dict(prompt_result)
    if not score:
        return "None"

    verdict = _fmt(score.get("verdict") or None)
    trust = _fmt(_score_dimension(prompt_result, "overall_trust"))
    labels = _score_failure_labels(prompt_result)
    failures = ", ".join(labels) if labels else "None"
    return f"verdict={verdict}; trust={trust}; failures={failures}"


def _result_label(result: dict[str, Any]) -> str:
    model_id = result.get("model", {}).get("model_id", "unknown-model")
    run_id = result.get("run", {}).get("run_id", "unknown-run")
    return f"{model_id} ({run_id})"


def _prompt_map(result: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["prompt_id"]: item for item in result.get("results", [])}


def _collect_prompt_ids(results: list[dict[str, Any]]) -> list[str]:
    prompt_ids: set[str] = set()
    for result in results:
        prompt_ids.update(_prompt_map(result))
    return sorted(prompt_ids)


def _label_counts(result: dict[str, Any], key: str) -> dict[str, int]:
    summary = result.get("summary", {})
    value = summary.get(key, {})
    return value if isinstance(value, dict) else {}


def _label_total(result: dict[str, Any], key: str) -> int:
    return sum(_label_counts(result, key).values())


def _scored_prompt_averages(result: dict[str, Any]) -> list[tuple[str, float]]:
    scores: list[tuple[str, float]] = []
    for prompt_result in result.get("results", []):
        average = _score_average(prompt_result)
        if isinstance(average, int | float):
            scores.append((prompt_result["prompt_id"], float(average)))
    return scores


def _prompt_score_extreme(result: dict[str, Any], *, highest: bool) -> str:
    scores = _scored_prompt_averages(result)
    if not scores:
        return "None"

    prompt_id, average = (
        max(scores, key=lambda item: item[1])
        if highest
        else min(scores, key=lambda item: item[1])
    )
    return f"{prompt_id} ({average:g})"


def _result_average_generation_tps(result: dict[str, Any]) -> float | None:
    values = [
        metrics.get("generation_tps")
        for prompt_result in result.get("results", [])
        if isinstance((metrics := prompt_result.get("metrics", {})), dict)
        and isinstance(metrics.get("generation_tps"), int | float)
    ]
    if not values:
        return None
    return round(float(sum(values)) / len(values), 2)


def _result_average_prompt_eval_tps(result: dict[str, Any]) -> float | None:
    values = [
        metrics.get("prompt_eval_tps")
        for prompt_result in result.get("results", [])
        if isinstance((metrics := prompt_result.get("metrics", {})), dict)
        and isinstance(metrics.get("prompt_eval_tps"), int | float)
    ]
    if not values:
        return None
    return round(float(sum(values)) / len(values), 2)


def _result_verdict_counts(result: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for prompt_result in result.get("results", []):
        verdict = _score_dict(prompt_result).get("verdict")
        if not verdict:
            continue
        counts[str(verdict)] = counts.get(str(verdict), 0) + 1
    return counts


def _fmt_counts(counts: dict[str, int]) -> str:
    if not counts:
        return "None"
    return ", ".join(f"{key}: {value}" for key, value in sorted(counts.items()))


def _unique_nonempty_values(results: list[dict[str, Any]], getter) -> list[str]:
    values = sorted(
        {value for value in (getter(result) for result in results) if value is not None}
    )
    return values


def _prompt_id_set(result: dict[str, Any]) -> set[str]:
    return set(_prompt_map(result))


def _completed_prompt_artifact_gaps(result: dict[str, Any]) -> int:
    gaps = 0
    for prompt_result in result.get("results", []):
        if prompt_result.get("status") != "completed":
            continue
        if not prompt_result.get("raw_output_path"):
            gaps += 1
        if not prompt_result.get("cleaned_output_path"):
            gaps += 1
    return gaps


def _paired_runtime_group(field: str) -> Any:
    def extract(result: dict[str, Any]) -> str:
        runtime = result.get("runtime", {})
        return f"{runtime.get(field)!r} ({runtime.get(field + '_state', 'unknown')})"

    return extract


def _runtime_setting_groups(results: list[dict[str, Any]]) -> list[list[Any]]:
    """Unique requested-setting value groups across compared runs.

    Covers base generation settings plus the extended and control settings
    with their paired request-state labels. A group holding more than one
    distinct value means the compared runs differ on that setting and are not
    like-for-like at runtime level.
    """

    def plain(field: str) -> Any:
        return lambda result: result.get("runtime", {}).get(field)

    return [
        _unique_nonempty_values(results, plain("ctx_size")),
        _unique_nonempty_values(results, plain("max_tokens")),
        _unique_nonempty_values(results, plain("temperature")),
        _unique_nonempty_values(results, plain("runtime_label")),
        _unique_nonempty_values(results, plain("reasoning_mode")),
        _unique_nonempty_values(results, _paired_runtime_group("top_k")),
        _unique_nonempty_values(results, _paired_runtime_group("min_p")),
        _unique_nonempty_values(results, _paired_runtime_group("seed")),
        _unique_nonempty_values(results, _paired_runtime_group("cache_type_k")),
        _unique_nonempty_values(results, _paired_runtime_group("cache_type_v")),
        _unique_nonempty_values(results, _paired_runtime_group("reasoning_effort")),
        _unique_nonempty_values(results, _paired_runtime_group("reasoning_budget")),
        _unique_nonempty_values(results, _paired_runtime_group("fit")),
        _unique_nonempty_values(results, _paired_runtime_group("reasoning_preserve")),
        _unique_nonempty_values(results, _paired_runtime_group("spec_type")),
    ]


def _build_comparison_scope(results: list[dict[str, Any]]) -> list[str]:
    suite_ids = _unique_nonempty_values(
        results, lambda result: result.get("suite", {}).get("suite_id")
    )
    suite_versions = _unique_nonempty_values(
        results, lambda result: result.get("suite", {}).get("suite_version")
    )
    model_ids = _unique_nonempty_values(
        results, lambda result: result.get("model", {}).get("model_id")
    )
    top_ks = _unique_nonempty_values(
        results,
        lambda result: (
            f"{result.get('runtime', {}).get('top_k')!r} "
            f"({result.get('runtime', {}).get('top_k_state', 'unknown')})"
        ),
    )
    min_ps = _unique_nonempty_values(
        results,
        lambda result: (
            f"{result.get('runtime', {}).get('min_p')!r} "
            f"({result.get('runtime', {}).get('min_p_state', 'unknown')})"
        ),
    )
    seeds = _unique_nonempty_values(
        results,
        lambda result: (
            f"{result.get('runtime', {}).get('seed')!r} "
            f"({result.get('runtime', {}).get('seed_state', 'unknown')})"
        ),
    )
    cache_types_k = _unique_nonempty_values(
        results,
        lambda result: (
            f"{result.get('runtime', {}).get('cache_type_k')!r} "
            f"({result.get('runtime', {}).get('cache_type_k_state', 'unknown')})"
        ),
    )
    cache_types_v = _unique_nonempty_values(
        results,
        lambda result: (
            f"{result.get('runtime', {}).get('cache_type_v')!r} "
            f"({result.get('runtime', {}).get('cache_type_v_state', 'unknown')})"
        ),
    )
    reasoning_efforts = _unique_nonempty_values(
        results,
        lambda result: (
            f"{result.get('runtime', {}).get('reasoning_effort')!r} "
            f"({result.get('runtime', {}).get('reasoning_effort_state', 'unknown')})"
        ),
    )
    reasoning_budgets = _unique_nonempty_values(
        results,
        lambda result: (
            f"{result.get('runtime', {}).get('reasoning_budget')!r} "
            f"({result.get('runtime', {}).get('reasoning_budget_state', 'unknown')})"
        ),
    )
    fit_modes = _unique_nonempty_values(
        results,
        lambda result: (
            f"{result.get('runtime', {}).get('fit')!r} "
            f"({result.get('runtime', {}).get('fit_state', 'unknown')})"
        ),
    )
    reasoning_preserve_states = _unique_nonempty_values(
        results,
        lambda result: (
            f"{result.get('runtime', {}).get('reasoning_preserve')!r} "
            f"({result.get('runtime', {}).get('reasoning_preserve_state', 'unknown')})"
        ),
    )
    spec_types = _unique_nonempty_values(
        results,
        lambda result: (
            f"{result.get('runtime', {}).get('spec_type')!r} "
            f"({result.get('runtime', {}).get('spec_type_state', 'unknown')})"
        ),
    )

    reasoning_modes = _unique_nonempty_values(
        results, lambda result: result.get("runtime", {}).get("reasoning_mode")
    )
    profile_identities = _unique_nonempty_values(
        results,
        lambda result: (
            f"{result.get('runtime', {}).get('profile', {}).get('profile_id', 'none')} "
            f"v{result.get('runtime', {}).get('profile', {}).get('profile_version', 'none')} "
            f"({result.get('runtime', {}).get('profile', {}).get('canonical_settings_sha256', 'none')})"
            if isinstance(result.get("runtime", {}).get("profile"), dict)
            else "none"
        ),
    )
    vendor_aligned_present = _vendor_aligned_profile_present(results)

    prompt_sets = [_prompt_id_set(result) for result in results]
    shared_prompt_ids = set.intersection(*prompt_sets) if prompt_sets else set()
    all_prompt_ids = set.union(*prompt_sets) if prompt_sets else set()
    prompt_sets_differ = len({frozenset(prompt_set) for prompt_set in prompt_sets}) > 1

    mixed_suite = len(suite_ids) > 1
    mixed_suite_versions = len(suite_versions) > 1
    mixed_model = len(model_ids) > 1
    mixed_runtime = any(len(values) > 1 for values in _runtime_setting_groups(results))

    like_for_like = (
        not mixed_suite
        and not mixed_suite_versions
        and not mixed_runtime
        and not prompt_sets_differ
    )

    lines = [
        "## Comparison Scope",
        "",
        f"- Compared runs: {len(results)}",
        f"- Model IDs: {', '.join(model_ids) if model_ids else 'None'}",
        f"- Suite IDs: {', '.join(suite_ids) if suite_ids else 'None'}",
        f"- Suite versions: {', '.join(str(value) for value in suite_versions) if suite_versions else 'None'}",
        f"- Shared prompt IDs: {len(shared_prompt_ids)} of {len(all_prompt_ids)}",
        f"- Like-for-like quality comparison: {'yes' if like_for_like else 'no — see Publish Readiness Notes'}",
        (
            "- Reasoning mode: "
            f"{', '.join(map(str, reasoning_modes)) if reasoning_modes else 'unknown'}"
        ),
        (
            "- Sampling profile provenance: "
            f"{', '.join(map(str, profile_identities)) if profile_identities else 'none'}"
        ),
        (
            "- Top-k (value, request state): "
            f"{', '.join(map(str, top_ks)) if top_ks else 'unknown'}"
        ),
        (
            "- Min-p (value, request state): "
            f"{', '.join(map(str, min_ps)) if min_ps else 'unknown'}"
        ),
        (
            "- Seed (value, request state): "
            f"{', '.join(map(str, seeds)) if seeds else 'unknown'}"
        ),
        (
            "- KV cache K type (value, request state): "
            f"{', '.join(map(str, cache_types_k)) if cache_types_k else 'unknown'}"
        ),
        (
            "- KV cache V type (value, request state): "
            f"{', '.join(map(str, cache_types_v)) if cache_types_v else 'unknown'}"
        ),
        (
            "- Reasoning effort (value, request state): "
            f"{', '.join(map(str, reasoning_efforts)) if reasoning_efforts else 'unknown'}"
        ),
        (
            "- Reasoning budget (value, request state): "
            f"{', '.join(map(str, reasoning_budgets)) if reasoning_budgets else 'unknown'}"
        ),
        (
            "- Runtime fit (value, request state): "
            f"{', '.join(map(str, fit_modes)) if fit_modes else 'unknown'}"
        ),
        (
            "- Preserve reasoning (value, request state): "
            f"{', '.join(map(str, reasoning_preserve_states)) if reasoning_preserve_states else 'unknown'}"
        ),
        (
            "- Speculative type (value, request state): "
            f"{', '.join(map(str, spec_types)) if spec_types else 'unknown'}"
        ),
        "",
        "Use this comparison for:",
        "- Cross-run evidence review when runs share suite, prompt subset, and runtime settings.",
        "- Operational comparisons of speed and VRAM under disclosed settings.",
        "- Bounded public claims backed by reviewed scores and cited artifacts.",
        "",
        "Do not use this comparison for:",
        "- Universal model rankings, winner declarations, or production-readiness proof.",
        "- Quality-ranking claims across mixed suites, prompt subsets, or runtime settings.",
        "- Publishing unreviewed automatic-rule drafts as final human judgment.",
        "",
    ]
    if vendor_aligned_present:
        lines.insert(
            next(
                index
                for index, line in enumerate(lines)
                if line.startswith("- Sampling profile provenance:")
            )
            + 1,
            (
                "- Vendor-aligned profile disclosure: alignment is "
                "operator-declared from documented vendor settings; it is not "
                "vendor endorsement or verified semantic reasoning or runtime "
                "behavior."
            ),
        )

    if not like_for_like:
        caveats: list[str] = []
        if mixed_suite:
            caveats.append("Suite IDs differ across runs.")
        if mixed_suite_versions:
            caveats.append("Suite versions differ across runs.")
        if mixed_model:
            caveats.append(
                "Model IDs differ across runs (expected for model comparisons)."
            )
        if mixed_runtime:
            caveats.append("Runtime settings differ across runs.")
        if prompt_sets_differ:
            caveats.append("Prompt sets differ across runs.")
        if caveats:
            lines.extend(["Like-for-like caveats:", ""])
            lines.extend(f"- {caveat}" for caveat in caveats)
            lines.append("")

    return lines


def _build_publish_readiness_notes(results: list[dict[str, Any]]) -> list[str]:
    compared_runs = len(results)
    scoring_status_counts: dict[str, int] = {}
    runs_with_scored_prompts = 0
    runs_without_scored_prompts = 0
    runs_with_failed_prompts = 0
    runs_not_completed = 0
    total_unreviewed_scores = 0
    total_automatic_unreviewed_scores = 0
    total_needs_review_verdicts = 0
    total_missing_score_rationales = 0
    total_artifact_gaps = 0

    for result in results:
        evidence = scoring_evidence_summary(result)
        status = evidence["scoring_status"]
        scoring_status_counts[status] = scoring_status_counts.get(status, 0) + 1

        if evidence["scored_prompt_count"] > 0:
            runs_with_scored_prompts += 1
        else:
            runs_without_scored_prompts += 1

        summary = result.get("summary", {})
        if summary.get("failed", 0):
            runs_with_failed_prompts += 1

        if result.get("run", {}).get("status") != "completed":
            runs_not_completed += 1

        total_unreviewed_scores += evidence["unreviewed_score_count"]
        total_automatic_unreviewed_scores += evidence["automatic_unreviewed_count"]
        total_needs_review_verdicts += evidence["needs_review_verdict_count"]
        total_missing_score_rationales += evidence["missing_score_rationale_count"]
        total_artifact_gaps += _completed_prompt_artifact_gaps(result)

    suite_ids = _unique_nonempty_values(
        results, lambda result: result.get("suite", {}).get("suite_id")
    )
    suite_versions = _unique_nonempty_values(
        results, lambda result: result.get("suite", {}).get("suite_version")
    )
    model_ids = _unique_nonempty_values(
        results, lambda result: result.get("model", {}).get("model_id")
    )
    reasoning_mode_values = [
        result.get("runtime", {}).get("reasoning_mode") for result in results
    ]
    reasoning_mode_unknown_or_mixed = len(set(reasoning_mode_values)) > 1 or any(
        value is None or value in {"unknown", "default"}
        for value in reasoning_mode_values
    )

    prompt_sets = [_prompt_id_set(result) for result in results]
    shared_prompt_ids = set.intersection(*prompt_sets) if prompt_sets else set()
    all_prompt_ids = set.union(*prompt_sets) if prompt_sets else set()
    prompt_sets_differ = len({frozenset(prompt_set) for prompt_set in prompt_sets}) > 1

    mixed_suite = len(suite_ids) > 1
    mixed_suite_versions = len(suite_versions) > 1
    mixed_model = len(model_ids) > 1
    mixed_runtime = any(len(values) > 1 for values in _runtime_setting_groups(results))

    lines = [
        "## Publish Readiness Notes",
        "",
        "Comparison reports are evidence summaries for local review. They are not universal rankings, leaderboards, or automatic best-model declarations.",
        "",
        f"- Compared runs: {compared_runs}",
        f"- Runs with scored prompts: {runs_with_scored_prompts}",
        f"- Runs without scored prompts: {runs_without_scored_prompts}",
        f"- Scoring status by run: {_fmt_counts(scoring_status_counts)}",
        f"- Runs with failed prompts: {runs_with_failed_prompts}",
        f"- Runs not completed: {runs_not_completed}",
        f"- Unreviewed applied scores: {total_unreviewed_scores}",
        f"- Unreviewed automatic-rule scores: {total_automatic_unreviewed_scores}",
        f"- Needs-review verdicts across scored prompts: {total_needs_review_verdicts}",
        f"- Scored prompts missing score rationale: {total_missing_score_rationales}",
        "- Completed prompts missing raw or cleaned output paths: "
        f"{total_artifact_gaps}",
        f"- Suite IDs in comparison: {', '.join(suite_ids) if suite_ids else 'None'}",
        "- Suite versions in comparison: "
        f"{', '.join(str(value) for value in suite_versions) if suite_versions else 'None'}",
        f"- Model IDs in comparison: {', '.join(model_ids) if model_ids else 'None'}",
        "- Shared prompt IDs across all runs: "
        f"{len(shared_prompt_ids)} of {len(all_prompt_ids)}",
        f"- Prompt sets differ across runs: {'yes' if prompt_sets_differ else 'no'}",
        f"- Mixed suite IDs: {'yes' if mixed_suite else 'no'}",
        f"- Mixed suite versions: {'yes' if mixed_suite_versions else 'no'}",
        f"- Mixed model IDs: {'yes' if mixed_model else 'no'}",
        f"- Mixed runtime settings: {'yes' if mixed_runtime else 'no'}",
        "",
        "### Claim boundaries",
        "",
        "- Manual scores are review metadata under the configured rubric, not objective truth.",
        "- Automatic-rule scores are assisted drafts unless reviewed; do not publish them as final human judgment.",
        "- Missing, partial, or review-metadata-only scores weaken quality-comparison claims.",
        "- `needs_review` verdicts mean the prompt is not ready for ranking-style publication claims.",
        "- Speed and VRAM numbers are hardware/runtime-specific operational signals, not answer-quality scores.",
        "- Compare like-for-like runs when making quality claims: same suite, prompt subset, context, token budget, temperature, and scoring status when possible.",
        "- Mixed suites, models, prompt subsets, or runtime settings require careful interpretation and narrower public claims.",
        "",
    ]

    limited_claims: list[str] = []
    if runs_without_scored_prompts:
        limited_claims.append(
            "At least one run has no scored prompts, so quality comparisons are incomplete."
        )
    if scoring_status_counts.get("partially_scored", 0) or scoring_status_counts.get(
        "review_metadata_only", 0
    ):
        limited_claims.append(
            "Some runs are only partially scored or contain metadata-only score entries."
        )
    if total_unreviewed_scores:
        limited_claims.append(
            "Some applied scores are unreviewed assisted drafts and need manual review before public use."
        )
    if total_needs_review_verdicts:
        limited_claims.append(
            "Some scored prompts still have `needs_review` verdicts and should be resolved before publication."
        )
    if total_missing_score_rationales:
        limited_claims.append(
            "Some scored prompts are missing `score_rationale`, which weakens auditability for public claims."
        )
    if mixed_suite:
        limited_claims.append(
            "Suite IDs differ across runs, so prompt overlap and score meaning may not be directly comparable."
        )
    if mixed_suite_versions:
        limited_claims.append(
            "Suite versions differ across runs, so prompt or rubric changes may affect score meaning."
        )
    if mixed_runtime:
        limited_claims.append(
            "Runtime settings differ across runs, so speed and VRAM comparisons are not like-for-like."
        )
    if reasoning_mode_unknown_or_mixed:
        limited_claims.append(
            "Effective reasoning mode is unknown, unspecified, or differs across "
            "runs; this report cannot support claims that depend on reasoning "
            "behavior."
        )
    vendor_aligned_present = _vendor_aligned_profile_present(results)

    if vendor_aligned_present:
        limited_claims.append(
            "At least one run selected a vendor_aligned profile; alignment is "
            "operator-declared rather than verified, and does not prove vendor "
            "endorsement or semantic reasoning behavior."
        )

    if prompt_sets_differ:
        limited_claims.append(
            "Prompt sets differ across runs; missing prompt cells are expected and limit direct score comparison."
        )
    if runs_with_failed_prompts or runs_not_completed:
        limited_claims.append(
            "Some runs are incomplete or contain failed prompts and should not be treated as full evidence."
        )
    if total_artifact_gaps:
        limited_claims.append(
            "Some completed prompts are missing raw or cleaned output paths, which weakens auditability."
        )

    if limited_claims:
        lines.extend(["### Limited or unsupported public claims", ""])
        lines.extend(f"- {claim}" for claim in limited_claims)
        lines.append("")
    else:
        lines.extend(
            [
                "### Limited or unsupported public claims",
                "",
                "- No major mixed-set or scoring-coverage warnings were detected from available metadata.",
                "- Public claims should still cite raw/cleaned outputs, hardware, runtime settings, and scoring provenance.",
                "",
            ]
        )

    safe_claims: list[str] = []
    risky_claims = [
        "Universal best-model, winner, or definitive-ranking claims",
        "Daily-driver or production-ready recommendations from this comparison alone",
        "Quality-ranking claims when any run is unscored, partially scored, or review-metadata-only",
        "Publishing unreviewed automatic-rule drafts as final human judgment",
    ]

    if (
        runs_with_scored_prompts == compared_runs
        and not total_unreviewed_scores
        and not total_needs_review_verdicts
        and not mixed_suite
        and not mixed_runtime
        and not prompt_sets_differ
    ):
        safe_claims.append(
            "Bounded same-suite comparison claims under the disclosed hardware, runtime, suite, and scoring metadata"
        )
        safe_claims.append(
            "Recurring failure-label or prompt-level evidence when backed by reviewed scores and artifacts"
        )
    else:
        safe_claims.append(
            "Operational signals such as speed, VRAM, and artifact availability under disclosed settings"
        )
        safe_claims.append(
            "Narrow workflow-specific observations when tied to specific prompts and reviewed scores"
        )

    lines.extend(
        [
            "### Publication evidence summary",
            "",
            "Safer public claims for this comparison:",
            "",
        ]
    )
    lines.extend(f"- {claim}" for claim in safe_claims)
    lines.extend(
        [
            "",
            "Claims that are not supported from this comparison alone:",
            "",
        ]
    )
    lines.extend(f"- {claim}" for claim in risky_claims)
    lines.append("")

    return lines


def build_compare_report(results: list[dict[str, Any]]) -> str:
    if len(results) < 2:
        raise ValueError("Need at least two result directories to compare")
    from llmgauge.core.agent_harness import require_native_result

    for result in results:
        require_native_result(result, consumer="Native comparison")

    lines = [
        "# LLMGauge Comparison Report",
        "",
        "This report compares local evaluation runs for review. It is not a universal ranking, model recommendation, or production-readiness proof.",
        "",
    ]
    lines.extend(_build_comparison_scope(results))
    lines.extend(
        [
            "## Interpretation Notes",
            "",
            "- Comparison reports summarize local evidence; they are not universal rankings or leaderboards.",
            "- Compare like-for-like runs (same suite, prompt subset, context, token budget, temperature) for quality claims.",
            "- Manual score averages are review metadata, not objective truth or automatic judgments.",
            "- Automatic-rule scores are assisted drafts unless reviewed and applied as reviewed metadata.",
            "- Missing scores mean this report cannot support quality-ranking claims.",
            "- Failure labels and low-trust prompts matter more than small average-score differences.",
            "- Speed and VRAM are hardware/runtime-specific operational metrics, not answer-quality scores.",
            "- Inspect raw and cleaned artifacts before making public-proof decisions.",
            "",
        ]
    )
    if any(
        isinstance(result.get("runtime_neutral_metrics"), dict) for result in results
    ):
        lines.extend(
            [
                "## Runtime-neutral Area 4 evidence",
                "",
                "Runtime-neutral request wall time and TTFT share metric identities",
                "across runtimes only when the accepted boundary and workload",
                "equivalence requirements are met. Do not read equivalent values as proof",
                "of runtime equivalence; sampling boundaries may differ. TTFT is not",
                "declared equivalent across runs merely because both have the metric;",
                "streaming state is disclosed per run.",
                "",
                "| Run | Backend | Streaming | Transport / observation | Request wall time s | TTFT s | TTFT channel | Boundary | Placement observed | Peak VRAM MiB | VRAM boundary | VRAM device |",
                "|---|---|:--|---|---:|---:|---|---|---|---:|---|---|",
            ]
        )
        for result in results:
            run = result.get("run", {})
            runtime = result.get("runtime", {})
            backend = runtime.get("backend") if isinstance(runtime, dict) else ""
            metrics = result.get("runtime_neutral_metrics")
            measurements = (
                metrics.get("measurements") if isinstance(metrics, dict) else None
            )
            wall = None
            boundary = "unavailable"
            placement = "unavailable"
            peak_vram = None
            peak_vram_boundary = "unavailable"
            peak_vram_device = "unavailable"
            streaming: bool | None = None
            transport = (
                _vllm_transport_display(runtime)
                if isinstance(runtime, dict)
                else "unknown"
            )
            observation = "unavailable"
            ttft = None
            ttft_channel = "unavailable"
            if isinstance(runtime, dict) and isinstance(runtime.get("streaming"), bool):
                streaming = runtime["streaming"]
            if streaming is False:
                observation = "not applicable"
            elif streaming is True:
                methods = result.get("_vllm_transport_observation_methods")
                if isinstance(methods, list) and len(methods) == 1:
                    observation = str(methods[0])
            if isinstance(measurements, list) and measurements:
                first = measurements[0]
                if isinstance(first, dict):
                    records = first.get("metrics")
                    if isinstance(records, list) and records:
                        wall_record = records[0]
                        if isinstance(wall_record, dict):
                            if (
                                wall_record.get("availability") == "available"
                                and wall_record.get("value") is not None
                            ):
                                wall = wall_record.get("value")
                            boundary = wall_record.get("boundary", boundary)
                        for record in records[1:]:
                            if not isinstance(record, dict):
                                continue
                            if (
                                record.get("metric_id")
                                == "llmgauge.metric.v1.time_to_first_token"
                            ):
                                if (
                                    record.get("availability") == "available"
                                    and record.get("value") is not None
                                ):
                                    ttft = record.get("value")
                                ttft_channel = record.get("channel") or "unavailable"
                                continue
                            if (
                                record.get("metric_id")
                                != "llmgauge.metric.v1.peak_vram"
                            ):
                                continue
                            peak_vram_boundary = record.get("boundary", "unavailable")
                            if (
                                record.get("availability") == "available"
                                and record.get("value") is not None
                            ):
                                peak_vram = record.get("value")
                            device_scope = record.get("device_scope")
                            if (
                                isinstance(device_scope, dict)
                                and device_scope.get("gpu_index") is not None
                            ):
                                peak_vram_device = f"GPU {device_scope['gpu_index']}"
                    if isinstance(first.get("execution_placement"), dict):
                        placement = first["execution_placement"].get(
                            "observed", "unavailable"
                        )
            streaming_label = (
                "streaming"
                if streaming is True
                else "non-streaming"
                if streaming is False
                else "unknown"
            )
            lines.append(
                "| "
                f"{run.get('run_id')} | "
                f"{backend or 'unknown'} | "
                f"{streaming_label} | "
                f"{transport} / {observation} | "
                f"{'unavailable' if wall is None else wall} | "
                f"{'unavailable' if ttft is None else ttft} | "
                f"{ttft_channel} | "
                f"{boundary} | "
                f"{placement} | "
                f"{'unavailable' if peak_vram is None else peak_vram} | "
                f"{peak_vram_boundary} | "
                f"{peak_vram_device} |"
            )
        lines.append("")

    lines.extend(_build_publish_readiness_notes(results))
    lines.extend(
        [
            "## Runs",
            "",
            "| Run | Model | Suite | Status | Completed | Failed | Scored | Manual total | Manual avg (0-5) | Peak VRAM MiB | Min VRAM Headroom MiB |",
            "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )

    for result in results:
        run = result.get("run", {})
        model = result.get("model", {})
        suite = result.get("suite", {})
        summary = result.get("summary", {})

        lines.append(
            "| "
            f"{run.get('run_id')} | "
            f"{model.get('model_id')} | "
            f"{suite.get('suite_id')} | "
            f"{run.get('status')} | "
            f"{summary.get('completed')} | "
            f"{summary.get('failed')} | "
            f"{summary.get('scored_prompt_count')} | "
            f"{_score_total_fraction(result)} | "
            f"{summary.get('manual_score_average')} | "
            f"{_fmt_vram(_result_peak_vram_mib(result))} | "
            f"{_fmt_vram(_result_min_vram_headroom_mib(result))} |"
        )

    lines.extend(
        [
            "",
            "## Score Summary",
            "",
            "Manual score totals and averages are review metadata, not objective quality proof.",
            "",
            "| Run | Manual total | Manual avg (0-5) | Scored prompts | Failure labels | Good labels | Lowest prompt | Highest prompt |",
            "|---|---:|---:|---:|---:|---:|---|---|",
        ]
    )

    for result in results:
        summary = result.get("summary", {})
        lines.append(
            "| "
            f"{_result_label(result)} | "
            f"{_score_total_fraction(result)} | "
            f"{summary.get('manual_score_average')} | "
            f"{summary.get('scored_prompt_count')} | "
            f"{_label_total(result, 'failure_labels')} | "
            f"{_label_total(result, 'good_labels')} | "
            f"{_prompt_score_extreme(result, highest=False)} | "
            f"{_prompt_score_extreme(result, highest=True)} |"
        )

    lines.extend(
        [
            "",
            "## Quality Signals",
            "",
            "| Run | Manual avg (0-5) | Verdict counts | Failure label count | Good label count | Lowest prompt |",
            "|---|---:|---|---:|---:|---|",
        ]
    )

    for result in results:
        summary = result.get("summary", {})
        lines.append(
            "| "
            f"{_result_label(result)} | "
            f"{summary.get('manual_score_average')} | "
            f"{_fmt_counts(_result_verdict_counts(result))} | "
            f"{_label_total(result, 'failure_labels')} | "
            f"{_label_total(result, 'good_labels')} | "
            f"{_prompt_score_extreme(result, highest=False)} |"
        )

    lines.extend(
        [
            "",
            "## Performance Signals",
            "",
            "| Run | Avg generation tok/s | Avg prompt-eval tok/s | Peak VRAM MiB | Min VRAM Headroom MiB |",
            "|---|---:|---:|---:|---:|",
        ]
    )

    for result in results:
        lines.append(
            "| "
            f"{_result_label(result)} | "
            f"{_fmt_vram(_result_average_generation_tps(result))} | "
            f"{_fmt_vram(_result_average_prompt_eval_tps(result))} | "
            f"{_fmt_vram(_result_peak_vram_mib(result))} | "
            f"{_fmt_vram(_result_min_vram_headroom_mib(result))} |"
        )

    lines.extend(
        [
            "",
            "## Runtime",
            "",
            "| Run | Backend | Context | Max tokens | Temp | Top-p | Batch | UBatch | GPU layers | Flash attention | Runtime label |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|",
        ]
    )

    for result in results:
        runtime = result.get("runtime", {})
        lines.append(
            "| "
            f"{_result_label(result)} | "
            f"{runtime.get('backend')} | "
            f"{runtime.get('ctx_size')} | "
            f"{runtime.get('max_tokens')} | "
            f"{runtime.get('temperature')} | "
            f"{runtime.get('top_p')} | "
            f"{runtime.get('batch_size')} | "
            f"{runtime.get('ubatch_size')} | "
            f"{runtime.get('gpu_layers')} | "
            f"{runtime.get('flash_attn', 'unknown')} | "
            f"{runtime.get('runtime_label') or 'unknown'} |"
        )

    lines.extend(
        [
            "",
            "## Prompt Scores",
            "",
        ]
    )

    prompt_ids = _collect_prompt_ids(results)

    header = (
        "| Prompt | " + " | ".join(_result_label(result) for result in results) + " |"
    )
    separator = "|---|" + "|".join("---:" for _ in results) + "|"
    lines.extend([header, separator])

    prompt_maps = [_prompt_map(result) for result in results]

    for prompt_id in prompt_ids:
        row = [prompt_id]
        for prompt_lookup in prompt_maps:
            prompt_result = prompt_lookup.get(prompt_id)
            row.append(
                _fmt(_score_average(prompt_result)) if prompt_result else "missing"
            )
        lines.append("| " + " | ".join(row) + " |")

    lines.extend(
        [
            "",
            "## Prompt Verdicts",
            "",
        ]
    )

    lines.extend([header, separator])

    for prompt_id in prompt_ids:
        row = [prompt_id]
        for prompt_lookup in prompt_maps:
            prompt_result = prompt_lookup.get(prompt_id)
            row.append(
                _prompt_verdict_cell(prompt_result) if prompt_result else "missing"
            )
        lines.append("| " + " | ".join(row) + " |")

    lines.extend(
        [
            "",
            "## Generation Speed",
            "",
        ]
    )

    header = (
        "| Prompt | " + " | ".join(_result_label(result) for result in results) + " |"
    )
    separator = "|---|" + "|".join("---:" for _ in results) + "|"
    lines.extend([header, separator])

    for prompt_id in prompt_ids:
        row = [prompt_id]
        for prompt_lookup in prompt_maps:
            prompt_result = prompt_lookup.get(prompt_id)
            if not prompt_result:
                row.append("missing")
                continue
            metrics = prompt_result.get("metrics", {})
            row.append(_fmt(metrics.get("generation_tps")))
        lines.append("| " + " | ".join(row) + " |")

    lines.extend(
        [
            "",
            "## Prompt Eval Speed",
            "",
        ]
    )

    lines.extend([header, separator])

    for prompt_id in prompt_ids:
        row = [prompt_id]
        for prompt_lookup in prompt_maps:
            prompt_result = prompt_lookup.get(prompt_id)
            if not prompt_result:
                row.append("missing")
                continue
            metrics = prompt_result.get("metrics", {})
            row.append(_fmt(metrics.get("prompt_eval_tps")))
        lines.append("| " + " | ".join(row) + " |")

    lines.extend(
        [
            "",
            "## Peak VRAM MiB",
            "",
        ]
    )

    lines.extend([header, separator])

    for prompt_id in prompt_ids:
        row = [prompt_id]
        for prompt_lookup in prompt_maps:
            prompt_result = prompt_lookup.get(prompt_id)
            if not prompt_result:
                row.append("missing")
                continue
            row.append(_fmt_vram(_vram_peak_used_mib(prompt_result)))
        lines.append("| " + " | ".join(row) + " |")

    lines.extend(
        [
            "",
            "## VRAM Headroom MiB",
            "",
        ]
    )

    lines.extend([header, separator])

    for prompt_id in prompt_ids:
        row = [prompt_id]
        for prompt_lookup in prompt_maps:
            prompt_result = prompt_lookup.get(prompt_id)
            if not prompt_result:
                row.append("missing")
                continue
            row.append(_fmt_vram(_vram_headroom_mib(prompt_result)))
        lines.append("| " + " | ".join(row) + " |")

    lines.extend(
        [
            "",
            "## Failure Labels",
            "",
        ]
    )

    for result in results:
        counts = _label_counts(result, "failure_labels")
        lines.extend([f"### {_result_label(result)}", ""])
        if counts:
            for label, count in sorted(counts.items()):
                lines.append(f"- {label}: {count}")
        else:
            lines.append("- None")
        lines.append("")

    lines.extend(
        [
            "## Good Labels",
            "",
        ]
    )

    for result in results:
        counts = _label_counts(result, "good_labels")
        lines.extend([f"### {_result_label(result)}", ""])
        if counts:
            for label, count in sorted(counts.items()):
                lines.append(f"- {label}: {count}")
        else:
            lines.append("- None")
        lines.append("")

    lines.extend(
        [
            "## Artifact integration",
            "",
            "- Per-run `report.md` files remain the authoritative single-run review artifacts.",
            "- This comparison report summarizes multiple runs; read **Publish Readiness Notes** and **Publication evidence summary** before publication.",
            "- Regenerate this report after underlying runs are re-scored, re-validated, or otherwise changed.",
            "- Use `export-index` for machine-readable metadata (including `scoring_status` and publish-readiness fields) when feeding importers or summary workflows.",
            "- Export index does not replace per-run reports or this comparison report.",
            "",
            "## Notes",
            "",
            "Scores are manual/local-context review metadata. Speed and VRAM metrics are operational metrics, not quality scores.",
            "Use this report as evidence for bounded public claims, not as a universal model ranking.",
            "",
        ]
    )

    return "\n".join(lines)
