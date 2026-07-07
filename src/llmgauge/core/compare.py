from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_compare_result(result_dir: Path) -> dict[str, Any]:
    result_path = result_dir / "llmgauge-result.json"
    if not result_path.exists():
        raise FileNotFoundError(f"Missing result file: {result_path}")

    result = json.loads(result_path.read_text(encoding="utf-8"))
    result["_result_dir"] = str(result_dir)
    return result


def _fmt(value: Any) -> str:
    return "None" if value is None else str(value)


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


def _scored_results(result: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in result.get("results", []) if isinstance(item.get("score"), dict)]


def _scoring_status(result: dict[str, Any]) -> str:
    summary = result.get("summary", {})
    scored_results = _scored_results(result)
    scored_prompt_count = summary.get("scored_prompt_count")

    if not isinstance(scored_prompt_count, int):
        scored_prompt_count = sum(
            1
            for prompt_result in scored_results
            if isinstance(_score_average(prompt_result), int | float)
        )

    prompt_count = len(result.get("results", []))

    if scored_prompt_count == 0:
        if scored_results:
            return "review_metadata_only"
        return "unscored"
    if scored_prompt_count < prompt_count:
        return "partially_scored"
    return "scored"


def _scoring_provenance(scored_results: list[dict[str, Any]]) -> dict[str, Any]:
    mode_counts: dict[str, int] = {}
    reviewed_count = 0
    unreviewed_count = 0
    automatic_unreviewed_count = 0

    for prompt_result in scored_results:
        score = _score_dict(prompt_result)

        scoring_mode = score.get("scoring_mode")
        if not isinstance(scoring_mode, str) or not scoring_mode:
            scoring_mode = "manual"
        mode_counts[scoring_mode] = mode_counts.get(scoring_mode, 0) + 1

        reviewed = score.get("reviewed", True)
        if reviewed is False:
            unreviewed_count += 1
            if scoring_mode == "automatic_rules":
                automatic_unreviewed_count += 1
        else:
            reviewed_count += 1

    return {
        "mode_counts": mode_counts,
        "reviewed_count": reviewed_count,
        "unreviewed_count": unreviewed_count,
        "automatic_unreviewed_count": automatic_unreviewed_count,
    }


def _unique_nonempty_values(results: list[dict[str, Any]], getter) -> list[str]:
    values = sorted({value for value in (getter(result) for result in results) if value is not None})
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


def _build_publish_readiness_notes(results: list[dict[str, Any]]) -> list[str]:
    compared_runs = len(results)
    scoring_status_counts: dict[str, int] = {}
    runs_with_scored_prompts = 0
    runs_without_scored_prompts = 0
    runs_with_failed_prompts = 0
    runs_not_completed = 0
    total_unreviewed_scores = 0
    total_automatic_unreviewed_scores = 0
    total_artifact_gaps = 0

    for result in results:
        status = _scoring_status(result)
        scoring_status_counts[status] = scoring_status_counts.get(status, 0) + 1

        summary = result.get("summary", {})
        scored_prompt_count = summary.get("scored_prompt_count")
        if not isinstance(scored_prompt_count, int):
            scored_prompt_count = sum(
                1
                for prompt_result in _scored_results(result)
                if isinstance(_score_average(prompt_result), int | float)
            )

        if scored_prompt_count > 0:
            runs_with_scored_prompts += 1
        else:
            runs_without_scored_prompts += 1

        if summary.get("failed", 0):
            runs_with_failed_prompts += 1

        if result.get("run", {}).get("status") != "completed":
            runs_not_completed += 1

        provenance = _scoring_provenance(_scored_results(result))
        total_unreviewed_scores += provenance["unreviewed_count"]
        total_automatic_unreviewed_scores += provenance["automatic_unreviewed_count"]
        total_artifact_gaps += _completed_prompt_artifact_gaps(result)

    suite_ids = _unique_nonempty_values(
        results, lambda result: result.get("suite", {}).get("suite_id")
    )
    model_ids = _unique_nonempty_values(
        results, lambda result: result.get("model", {}).get("model_id")
    )
    ctx_sizes = _unique_nonempty_values(
        results, lambda result: result.get("runtime", {}).get("ctx_size")
    )
    max_tokens = _unique_nonempty_values(
        results, lambda result: result.get("runtime", {}).get("max_tokens")
    )
    temperatures = _unique_nonempty_values(
        results, lambda result: result.get("runtime", {}).get("temperature")
    )
    runtime_labels = _unique_nonempty_values(
        results, lambda result: result.get("runtime", {}).get("runtime_label")
    )

    prompt_sets = [_prompt_id_set(result) for result in results]
    shared_prompt_ids = set.intersection(*prompt_sets) if prompt_sets else set()
    all_prompt_ids = set.union(*prompt_sets) if prompt_sets else set()
    prompt_sets_differ = len({frozenset(prompt_set) for prompt_set in prompt_sets}) > 1

    mixed_suite = len(suite_ids) > 1
    mixed_model = len(model_ids) > 1
    mixed_runtime = any(
        len(values) > 1 for values in (ctx_sizes, max_tokens, temperatures, runtime_labels)
    )

    lines = [
        "## Publish Readiness Notes",
        "",
        "Comparison reports are evidence summaries for local review. They are not universal rankings, leaderboards, or automatic best-model declarations.",
        "",
        "- Compared runs: "
        f"{compared_runs}",
        "- Runs with scored prompts: "
        f"{runs_with_scored_prompts}",
        "- Runs without scored prompts: "
        f"{runs_without_scored_prompts}",
        "- Scoring status by run: "
        f"{_fmt_counts(scoring_status_counts)}",
        "- Runs with failed prompts: "
        f"{runs_with_failed_prompts}",
        "- Runs not completed: "
        f"{runs_not_completed}",
        "- Unreviewed applied scores: "
        f"{total_unreviewed_scores}",
        "- Unreviewed automatic-rule scores: "
        f"{total_automatic_unreviewed_scores}",
        "- Completed prompts missing raw or cleaned output paths: "
        f"{total_artifact_gaps}",
        "- Suite IDs in comparison: "
        f"{', '.join(suite_ids) if suite_ids else 'None'}",
        "- Model IDs in comparison: "
        f"{', '.join(model_ids) if model_ids else 'None'}",
        "- Shared prompt IDs across all runs: "
        f"{len(shared_prompt_ids)} of {len(all_prompt_ids)}",
        "- Prompt sets differ across runs: "
        f"{'yes' if prompt_sets_differ else 'no'}",
        "- Mixed suite IDs: "
        f"{'yes' if mixed_suite else 'no'}",
        "- Mixed model IDs: "
        f"{'yes' if mixed_model else 'no'}",
        "- Mixed runtime settings: "
        f"{'yes' if mixed_runtime else 'no'}",
        "",
        "### Claim boundaries",
        "",
        "- Manual scores are review metadata under the configured rubric, not objective truth.",
        "- Automatic-rule scores are assisted drafts unless reviewed; do not publish them as final human judgment.",
        "- Missing or partial scores mean this comparison cannot support quality-ranking claims.",
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
    if mixed_suite:
        limited_claims.append(
            "Suite IDs differ across runs, so prompt overlap and score meaning may not be directly comparable."
        )
    if mixed_runtime:
        limited_claims.append(
            "Runtime settings differ across runs, so speed and VRAM comparisons are not like-for-like."
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

    return lines


def build_compare_report(results: list[dict[str, Any]]) -> str:
    if len(results) < 2:
        raise ValueError("Need at least two result directories to compare")

    lines = [
        "# LLMGauge Comparison Report",
        "",
        "This report compares completed local evaluation runs. It does not declare a universal winner.",
        "",
        "## Interpretation Notes",
        "",
        "- Comparison reports summarize local evidence; they are not universal rankings or leaderboards.",
        "- Compare runs from the same suite and prompt subset when making quality claims.",
        "- Manual score averages are review metadata, not objective truth or automatic judgments.",
        "- Automatic-rule scores are assisted drafts unless reviewed and applied as reviewed metadata.",
        "- Missing scores mean this report cannot support quality-ranking claims.",
        "- Failure labels and low-trust prompts matter more than small average-score differences.",
        "- Speed and VRAM are hardware/runtime-specific operational metrics, not answer-quality scores.",
        "- Mixed suites, models, contexts, token budgets, or temperatures require careful interpretation.",
        "- Inspect raw and cleaned artifacts before making model-selection or public-proof decisions.",
        "",
    ]
    lines.extend(_build_publish_readiness_notes(results))
    lines.extend(
        [
            "## Runs",
            "",
            "| Run | Model | Suite | Status | Completed | Failed | Scored | Score total | Avg score | Peak VRAM MiB | Min VRAM Headroom MiB |",
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
            "| Run | Score total | Avg score | Scored prompts | Failure labels | Good labels | Lowest prompt | Highest prompt |",
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
            "| Run | Avg score | Verdict counts | Failure label count | Good label count | Lowest prompt |",
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
            "## Notes",
            "",
            "Scores are manual/local-context review metadata. Speed and VRAM metrics are operational metrics, not quality scores.",
            "Use this report as evidence for bounded public claims, not as a universal model ranking.",
            "",
        ]
    )

    return "\n".join(lines)
