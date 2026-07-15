from __future__ import annotations

from typing import Any

from llmgauge.core.scoring import (
    scored_prompt_results,
    scoring_evidence_summary,
    scoring_status_for_result,
)

_MISSING = object()


def _fmt(value: Any) -> str:
    return "None" if value is None else str(value)


def _fmt_optional_throughput(value: Any = _MISSING) -> str:
    if value is _MISSING:
        return "-"
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "-"
    if isinstance(value, int | float):
        return str(value)
    return "-"


def _fmt_endpoint_identity(identity: Any) -> str:
    if not isinstance(identity, dict):
        return "unknown"
    scheme = identity.get("scheme") or "unknown"
    loopback = identity.get("loopback_class") or "unknown"
    port = identity.get("port")
    port_text = str(port) if port is not None else "unknown"
    return f"{scheme} loopback_class={loopback} port={port_text}"


def _runtime_section_lines(runtime: dict[str, Any]) -> list[str]:
    backend = runtime.get("backend") or "unknown"
    lines = [f"- Backend: {backend}"]

    if backend == "vllm":
        lines.extend(
            [
                f"- Lifecycle ownership: {runtime.get('lifecycle_ownership') or 'external_operator'}",
                f"- Endpoint identity: {_fmt_endpoint_identity(runtime.get('endpoint_identity'))}",
                f"- Requested served model: {runtime.get('requested_served_model') or 'unknown'}",
                f"- Observed served model: {runtime.get('observed_served_model') or 'unknown'}",
                f"- Connect timeout s: {runtime.get('connect_timeout_seconds', 'unknown')}",
                f"- Request timeout s: {runtime.get('request_timeout_seconds', 'unknown')}",
                f"- Max response bytes: {runtime.get('max_response_bytes', 'unknown')}",
                f"- Context (requested): {runtime.get('ctx_size', 'unknown')}",
                f"- Max tokens: {runtime.get('max_tokens')}",
                f"- Temperature: {runtime.get('temperature')}",
                f"- Top-p: {runtime.get('top_p')}",
                f"- Runtime label: {runtime.get('runtime_label') or 'unknown'}",
                f"- Reasoning mode: {runtime.get('reasoning_mode') or 'unknown'}",
                f"- Streaming: {runtime.get('streaming', False)}",
                f"- Authentication: {runtime.get('authentication') or 'none'}",
                f"- Proxy bypass policy: {runtime.get('proxy_bypass_policy') or 'unknown'}",
                (
                    "- vLLM runtime evidence: captured"
                    if runtime.get("vllm_runtime_evidence_captured")
                    else "- vLLM runtime evidence: missing"
                ),
                (
                    f"- vLLM runtime evidence artifact: `{runtime['vllm_runtime_evidence_path']}`"
                    if runtime.get("vllm_runtime_evidence_path")
                    else "- vLLM runtime evidence artifact: not recorded"
                ),
                "- Command metadata: not used for vLLM (HTTP request evidence is separate)",
                "- Cross-runtime note: token counts and throughput are not claimed equivalent to llama.cpp.",
            ]
        )
        return lines

    lines.extend(
        [
            f"- llama-cli: {runtime.get('llama_cli', 'unknown')}",
            f"- Context: {runtime.get('ctx_size')}",
            f"- Max tokens: {runtime.get('max_tokens')}",
            f"- Temperature: {runtime.get('temperature')}",
            f"- Top-p: {runtime.get('top_p')}",
            f"- Batch: {runtime.get('batch_size')}",
            f"- UBatch: {runtime.get('ubatch_size')}",
            f"- GPU layers: {runtime.get('gpu_layers')}",
            f"- Flash attention: {runtime.get('flash_attn', 'unknown')}",
            f"- Runtime label: {runtime.get('runtime_label') or 'unknown'}",
            f"- Reasoning mode: {runtime.get('reasoning_mode') or 'unknown'}",
            (
                "- Command metadata: captured"
                if runtime.get("runtime_command_captured")
                else "- Command metadata: missing"
            ),
            (
                f"- Command artifact: `{runtime['runtime_command_path']}`"
                if runtime.get("runtime_command_path")
                else "- Command artifact: not recorded"
            ),
        ]
    )
    return lines


def _score_dict(prompt_result: dict[str, Any]) -> dict[str, Any]:
    score = prompt_result.get("score")
    return score if isinstance(score, dict) else {}


def _score_average(prompt_result: dict[str, Any]) -> Any:
    return _score_dict(prompt_result).get("prompt_average")


def _verdict_counts(scored_results: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}

    for prompt_result in scored_results:
        verdict = _score_dict(prompt_result).get("verdict")
        if isinstance(verdict, str) and verdict:
            counts[verdict] = counts.get(verdict, 0) + 1

    return counts


def _fmt_counts(counts: dict[str, int]) -> str:
    if not counts:
        return "None"

    return ", ".join(f"{label}: {count}" for label, count in sorted(counts.items()))


def _scoring_provenance(
    scored_results: list[dict[str, Any]],
) -> dict[str, Any]:
    mode_counts: dict[str, int] = {}
    reviewed_count = 0
    unreviewed_count = 0
    scorer_ids: set[str] = set()

    for prompt_result in scored_results:
        score = _score_dict(prompt_result)

        scoring_mode = score.get("scoring_mode")
        if not isinstance(scoring_mode, str) or not scoring_mode:
            scoring_mode = "manual"
        mode_counts[scoring_mode] = mode_counts.get(scoring_mode, 0) + 1

        reviewed = score.get("reviewed", True)
        if reviewed is False:
            unreviewed_count += 1
        else:
            reviewed_count += 1

        scorer_id = score.get("scorer_id")
        if isinstance(scorer_id, str) and scorer_id:
            scorer_ids.add(scorer_id)

    return {
        "mode_counts": mode_counts,
        "reviewed_count": reviewed_count,
        "unreviewed_count": unreviewed_count,
        "scorer_ids": sorted(scorer_ids),
    }


def _fmt_scorer_ids(scorer_ids: list[str]) -> str:
    return ", ".join(scorer_ids) if scorer_ids else "None"


def _top_label_counts(labels: dict[str, Any], *, limit: int = 3) -> str:
    numeric_labels = [
        (label, count)
        for label, count in labels.items()
        if isinstance(label, str) and isinstance(count, int)
    ]

    if not numeric_labels:
        return "None"

    top = sorted(numeric_labels, key=lambda item: (-item[1], item[0]))[:limit]
    return ", ".join(f"{label}: {count}" for label, count in top)


def _prompt_score_extreme(
    scored_results: list[dict[str, Any]],
    *,
    highest: bool,
) -> str:
    prompt_scores: list[tuple[str, float]] = []

    for prompt_result in scored_results:
        average = _score_average(prompt_result)
        if isinstance(average, int | float):
            prompt_scores.append((prompt_result["prompt_id"], float(average)))

    if not prompt_scores:
        return "None"

    prompt_id, score = (max if highest else min)(
        prompt_scores,
        key=lambda item: item[1],
    )
    return f"{prompt_id} ({score:g} / 5)"


def _fmt_optional_mib(value: Any) -> str:
    return "-" if value is None else str(value)


def _vram_peak_used_mib(prompt_result: dict[str, Any]) -> int | None:
    vram = prompt_result.get("vram")
    if not isinstance(vram, dict) or not vram.get("available"):
        return None

    peak_used_mib = vram.get("peak_used_mib")
    if not isinstance(peak_used_mib, int):
        return None

    return peak_used_mib


def _build_report_scope_section() -> list[str]:
    return [
        "## Report Scope",
        "",
        "Use this report for:",
        "- Bounded public claims about this run under the disclosed model, suite, and runtime settings.",
        "- Prompt-level output review using the raw and cleaned artifacts cited below.",
        "- Score and rationale review when scoring is complete and manually reviewed.",
        "- Operational signals such as speed and VRAM under the tested hardware.",
        "",
        "Do not use this report for:",
        "- Universal model rankings, winner declarations, or production-readiness proof.",
        "- Quality-ranking claims when scoring is unscored, partial, review-metadata-only, or unreviewed.",
        "- Publishing automatic-rule drafts as final human judgment without manual review.",
        "- Claims about untested prompts, hardware, or runtime settings.",
        "",
    ]


def _result_peak_vram_mib(result: dict[str, Any]) -> int | None:
    values = [
        peak
        for peak in (
            _vram_peak_used_mib(prompt_result)
            for prompt_result in result.get("results", [])
        )
        if peak is not None
    ]
    return max(values) if values else None


def _result_min_vram_headroom_mib(result: dict[str, Any]) -> int | None:
    values = [
        headroom
        for headroom in (
            _vram_headroom_mib(prompt_result)
            for prompt_result in result.get("results", [])
        )
        if headroom is not None
    ]
    return min(values) if values else None


def _build_evidence_summary(result: dict[str, Any]) -> list[str]:
    run = result["run"]
    model = result["model"]
    runtime = result["runtime"]
    suite = result["suite"]
    summary = result["summary"]
    evidence = scoring_evidence_summary(result)

    peak_vram = _result_peak_vram_mib(result)
    min_headroom = _result_min_vram_headroom_mib(result)
    run_fingerprint = result.get("run_fingerprint")
    fingerprint_value = (
        run_fingerprint.get("value")
        if isinstance(run_fingerprint, dict)
        else None
    )

    lines = [
        "## Evidence Summary",
        "",
        f"- Run ID: {run['run_id']}",
        f"- Run status: {run['status']}",
        f"- Timestamp UTC: {run['timestamp_utc']}",
        f"- Model ID: {model['model_id']}",
        f"- Suite: {suite['suite_id']} ({suite['suite_version']})",
        f"- Prompts completed: {summary['completed']} of {suite['prompt_count']}",
        f"- Prompts failed: {summary['failed']}",
        f"- Scoring status: {evidence['scoring_status']}",
        f"- Scored prompts: {evidence['scored_prompt_count']} of {evidence['prompt_count']}",
        (
            f"- Manual score average: {summary.get('manual_score_average')} / 5"
            if summary.get("manual_score_average") is not None
            else "- Manual score average: None"
        ),
        f"- Runtime: {runtime['backend']}, ctx={runtime.get('ctx_size', 'unknown')}, max_tokens={runtime['max_tokens']}, temp={runtime['temperature']}, top_p={runtime['top_p']}",
        f"- Model source: {model.get('model_source') or 'unknown'}",
        f"- Runtime label: {runtime.get('runtime_label') or 'unknown'}",
        f"- Reasoning mode: {runtime.get('reasoning_mode') or 'unknown'}",
        (
            f"- Flash attention: {runtime.get('flash_attn', 'unknown')}"
            if runtime.get("backend") != "vllm"
            else "- Flash attention: not applicable (vLLM external server)"
        ),
        f"- Peak VRAM MiB: {_fmt_optional_mib(peak_vram)}",
        f"- Min VRAM headroom MiB: {_fmt_optional_mib(min_headroom)}",
        (
            f"- Run evidence fingerprint: `{fingerprint_value}`"
            if fingerprint_value
            else "- Run evidence fingerprint: not recorded"
        ),
        "- Fingerprint boundary: identifies canonical private source evidence, not model quality or a unique execution instance.",
        "- Inspect raw and cleaned outputs in **Prompt Artifact Audit** before publication.",
        "",
    ]

    return lines


def _artifact_path_line(path: str | None, *, label: str, missing_note: str) -> str:
    if path:
        return f"- {label}: `{path}`"
    return f"- {label}: {missing_note}"


def _score_audit_lines(prompt_result: dict[str, Any]) -> list[str]:
    score = _score_dict(prompt_result)
    if not score:
        return ["- Score audit: unscored"]

    lines = [
        f"- Score average: {_fmt(score.get('prompt_average'))} / 5",
        f"- Verdict: {score.get('verdict') or 'None'}",
    ]

    failure_labels = score.get("failure_labels", [])
    good_labels = score.get("good_labels", [])
    lines.append(
        f"- Failure labels: {', '.join(failure_labels) if failure_labels else 'None'}"
    )
    lines.append(
        f"- Good labels: {', '.join(good_labels) if good_labels else 'None'}"
    )

    score_rationale = score.get("score_rationale", "")
    if score_rationale:
        lines.append(f"- Score rationale: {score_rationale}")
    else:
        lines.append("- Score rationale: missing (weakens auditability for public claims)")

    reviewer_notes = score.get("reviewer_notes", "")
    if reviewer_notes:
        lines.append(f"- Reviewer notes: {reviewer_notes}")

    scoring_mode = score.get("scoring_mode")
    if isinstance(scoring_mode, str) and scoring_mode:
        lines.append(f"- Scoring mode: {scoring_mode}")

    if score.get("reviewed") is False:
        lines.append(
            "- Review status: unreviewed assisted draft (not final human judgment)"
        )

    return lines


def _build_audit_checklist(result: dict[str, Any]) -> list[str]:
    evidence = scoring_evidence_summary(result)
    artifact_gaps = _completed_prompt_artifact_gaps(result)

    lines = [
        "## Audit Checklist",
        "",
        "Use this checklist before citing this run in a public report:",
        "",
        "1. Run `validate-result` on this directory to confirm structure and on-disk references.",
        "2. Inspect raw outputs in `raw/` for each cited prompt (source audit evidence).",
        "3. Use cleaned outputs in `cleaned/` for readable review when present (derived; does not replace raw).",
        "4. Check stderr logs in `logs/` when exit status or output quality is uncertain.",
        "5. Review score rationales in **Prompt Artifact Audit** when making quality claims.",
        "6. Read **Publish Readiness Notes** for claim boundaries.",
        "",
        "Retain for audit:",
        "- `llmgauge-result.json`, raw outputs, stderr logs, and `scores.yaml` when manually scored.",
        "- `report.md` for human review; regenerate after scoring changes.",
        "",
    ]

    if artifact_gaps:
        lines.append(
            f"- Warning: {artifact_gaps} completed prompt(s) are missing raw or cleaned output paths in metadata."
        )
        lines.append("")

    if evidence["scoring_status"] == "unscored":
        lines.append("- This run is unscored; quality claims require manual scoring first.")
        lines.append("")

    if evidence["unreviewed_score_count"]:
        lines.append(
            "- Some applied scores are unreviewed assisted drafts; finish manual review before publication."
        )
        lines.append("")

    return lines


def _build_prompt_artifact_audit(result: dict[str, Any]) -> list[str]:
    lines = [
        "## Prompt Artifact Audit",
        "",
        "Paths are relative to this result directory.",
        "",
        "- Raw prompts and raw outputs are source audit evidence.",
        "- Cleaned outputs are derived review aids and do not replace raw outputs.",
        "- Stderr logs are diagnostic evidence.",
        "- VRAM samples are operational telemetry captured locally.",
        "- Scores are review metadata; trace public claims to raw/cleaned outputs and rationales below.",
        "",
        "| Prompt | Status | Raw output | Cleaned output | Stderr log | Request evidence | VRAM samples |",
        "|---|---|---|---|---|---|---|",
    ]

    for prompt_result in result.get("results", []):
        prompt_id = prompt_result["prompt_id"]
        status = prompt_result.get("status", "unknown")
        raw_output = prompt_result.get("raw_output_path")
        cleaned_output = prompt_result.get("cleaned_output_path")
        stderr_log = prompt_result.get("stderr_log_path")
        request_evidence = prompt_result.get("request_evidence_path")
        vram_samples = prompt_result.get("vram_samples_path")

        if status == "completed" and not raw_output:
            raw_cell = "missing"
        elif raw_output:
            raw_cell = f"`{raw_output}`"
        else:
            raw_cell = "n/a"

        if status == "completed" and not cleaned_output:
            cleaned_cell = "not available"
        elif cleaned_output:
            cleaned_cell = f"`{cleaned_output}`"
        else:
            cleaned_cell = "n/a"

        if stderr_log:
            stderr_cell = f"`{stderr_log}`"
        else:
            stderr_cell = "missing" if status == "completed" else "n/a"

        if request_evidence:
            request_cell = f"`{request_evidence}`"
        else:
            request_cell = "-"

        if vram_samples:
            vram_cell = f"`{vram_samples}`"
        else:
            vram_cell = "-"

        lines.append(
            "| "
            f"{prompt_id} | "
            f"{status} | "
            f"{raw_cell} | "
            f"{cleaned_cell} | "
            f"{stderr_cell} | "
            f"{request_cell} | "
            f"{vram_cell} |"
        )

    lines.append("")

    for prompt_result in result.get("results", []):
        prompt_id = prompt_result["prompt_id"]
        status = prompt_result.get("status", "unknown")
        category = prompt_result.get("category") or "uncategorized"

        lines.extend(
            [
                f"### {prompt_id} ({category}, {status})",
                "",
                _artifact_path_line(
                    prompt_result.get("raw_prompt_path"),
                    label="Raw prompt (source)",
                    missing_note="missing",
                ),
                _artifact_path_line(
                    prompt_result.get("raw_output_path"),
                    label="Raw output (source audit evidence)",
                    missing_note="missing (weakens auditability)",
                ),
                _artifact_path_line(
                    prompt_result.get("cleaned_output_path"),
                    label="Cleaned output (derived review aid)",
                    missing_note="not available (use raw output for audit; older artifacts may omit cleaned paths)",
                ),
                _artifact_path_line(
                    prompt_result.get("stderr_log_path"),
                    label="Stderr log (diagnostic evidence)",
                    missing_note="missing",
                ),
                _artifact_path_line(
                    prompt_result.get("request_evidence_path"),
                    label="Request evidence (vLLM HTTP, optional)",
                    missing_note="not captured",
                ),
            ]
        )

        finish_reason = prompt_result.get("finish_reason")
        metrics = prompt_result.get("metrics")
        if finish_reason is None and isinstance(metrics, dict):
            finish_reason = metrics.get("finish_reason")
        if finish_reason:
            lines.append(f"- Finish reason: {finish_reason}")
        failure_class = prompt_result.get("failure_class")
        if failure_class:
            lines.append(f"- Failure class: {failure_class}")
        if isinstance(metrics, dict):
            wall = metrics.get("request_wall_time_seconds")
            if wall is not None:
                lines.append(f"- Request wall time s: {wall}")
            e2e = metrics.get("end_to_end_completion_tps")
            if e2e is not None:
                lines.append(
                    f"- End-to-end completion throughput (tok/s): {e2e} "
                    "(not decode-only; not claimed equivalent to llama.cpp)"
                )
            if metrics.get("prompt_eval_tokens") is not None:
                lines.append(
                    f"- Prompt tokens (backend-reported): {metrics.get('prompt_eval_tokens')}"
                )
            if metrics.get("generation_tokens") is not None:
                lines.append(
                    f"- Completion tokens (backend-reported): {metrics.get('generation_tokens')}"
                )

        vram_samples = prompt_result.get("vram_samples_path")
        if vram_samples:
            lines.append(
                f"- VRAM samples (operational telemetry): `{vram_samples}`"
            )
        else:
            lines.append("- VRAM samples (operational telemetry): not captured")

        lines.append("")
        lines.extend(_score_audit_lines(prompt_result))
        lines.append("")

    return lines


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


def _build_single_run_publish_readiness_notes(result: dict[str, Any]) -> list[str]:
    evidence = scoring_evidence_summary(result)
    summary = result.get("summary", {})
    artifact_gaps = _completed_prompt_artifact_gaps(result)

    lines = [
        "## Publish Readiness Notes",
        "",
        "Single-run reports summarize local evidence for review. They are not universal rankings, leaderboards, or automatic recommendations.",
        "",
        f"- Scoring status: {evidence['scoring_status']}",
        f"- Scored prompts: {evidence['scored_prompt_count']} of {evidence['prompt_count']}",
        f"- Score entries present: {evidence['score_entry_count']}",
        f"- Needs-review verdicts: {evidence['needs_review_verdict_count']}",
        f"- Unreviewed applied scores: {evidence['unreviewed_score_count']}",
        f"- Unreviewed automatic-rule scores: {evidence['automatic_unreviewed_count']}",
        f"- Scored prompts missing score rationale: {evidence['missing_score_rationale_count']}",
        f"- Completed prompts missing raw or cleaned output paths: {artifact_gaps}",
        f"- Failed prompts: {summary.get('failed', 0)}",
        "",
        "### Claim boundaries",
        "",
        "- Manual scores are review metadata under the configured rubric, not objective truth.",
        "- Automatic-rule scores are assisted drafts unless reviewed; do not publish them as final human judgment.",
        "- Missing, partial, or review-metadata-only scores weaken quality-ranking claims.",
        "- `needs_review` verdicts mean the prompt is not ready for ranking-style publication claims.",
        "- Speed and VRAM numbers are hardware/runtime-specific operational signals, not answer-quality scores.",
        "",
    ]

    limited_claims: list[str] = []
    if evidence["scoring_status"] == "unscored":
        limited_claims.append(
            "This run has no scored prompts, so it cannot support quality-ranking claims."
        )
    if evidence["scoring_status"] in {"partially_scored", "review_metadata_only"}:
        limited_claims.append(
            "Scoring is incomplete or metadata-only, so publication claims should stay narrow."
        )
    if evidence["unreviewed_score_count"]:
        limited_claims.append(
            "Some applied scores are unreviewed assisted drafts and need manual review before public use."
        )
    if evidence["needs_review_verdict_count"]:
        limited_claims.append(
            "Some scored prompts still have `needs_review` verdicts and should be resolved before publication."
        )
    if evidence["missing_score_rationale_count"]:
        limited_claims.append(
            "Some scored prompts are missing `score_rationale`, which weakens auditability for public claims."
        )
    if artifact_gaps:
        limited_claims.append(
            "Some completed prompts are missing raw or cleaned output paths, which weakens auditability."
        )
    if summary.get("failed", 0):
        limited_claims.append(
            "This run contains failed prompts and should not be treated as full-suite evidence."
        )

    if limited_claims:
        lines.extend(["### Limited or unsupported public claims", ""])
        lines.extend(f"- {claim}" for claim in limited_claims)
        lines.append("")

    return lines


def _vram_headroom_mib(prompt_result: dict[str, Any]) -> int | None:
    vram = prompt_result.get("vram")
    if not isinstance(vram, dict) or not vram.get("available"):
        return None

    peak_used_mib = vram.get("peak_used_mib")
    peak_total_mib = vram.get("peak_total_mib")
    if not isinstance(peak_used_mib, int) or not isinstance(peak_total_mib, int):
        return None

    return peak_total_mib - peak_used_mib


def build_markdown_report(result: dict[str, Any]) -> str:
    run = result["run"]
    model = result["model"]
    runtime = result["runtime"]
    suite = result["suite"]
    summary = result["summary"]
    scored_results = scored_prompt_results(result)

    lines = [
        f"# LLMGauge Report: {run['run_id']}",
        "",
        "This report summarizes local evaluation evidence for review. It is not a universal ranking, model recommendation, or production-readiness proof.",
        "",
    ]

    lines.extend(_build_report_scope_section())
    lines.extend(_build_evidence_summary(result))
    lines.extend(_build_single_run_publish_readiness_notes(result))

    lines.extend(
        [
            "## Test Configuration",
            "",
            "### Run",
            "",
            f"- Status: {run['status']}",
            f"- Timestamp UTC: {run['timestamp_utc']}",
            f"- Suite: {suite['suite_id']} ({suite['suite_version']})",
            f"- Prompt count: {suite['prompt_count']}",
            f"- Completed: {summary['completed']}",
            f"- Failed: {summary['failed']}",
            "",
            "### Model",
            "",
            f"- Model ID: {model['model_id']}",
            f"- Model source: {model.get('model_source') or 'unknown'}",
            f"- Model profile: {model.get('model_profile') or 'None'}",
            f"- Model path policy: {model['model_path_policy']}",
            "",
            "### Runtime",
            "",
            *(_runtime_section_lines(runtime)),
            "",
        ]
    )

    failure_labels = summary.get("failure_labels", {})
    good_labels = summary.get("good_labels", {})

    if summary.get("scored_prompt_count"):
        lines.extend(
            [
                "## Score Summary",
                "",
                "Manual scores are review metadata on a 0-5 scale, not objective quality proof.",
                "",
                f"- Scored prompts: {summary.get('scored_prompt_count')}",
                f"- Manual score total: {summary.get('manual_score_total')}",
                f"- Manual score max: {summary.get('manual_score_max')}",
                f"- Manual score average: {summary.get('manual_score_average')} / 5",
                "",
            ]
        )

        if failure_labels:
            lines.extend(["### Failure Labels", ""])
            for label, count in sorted(failure_labels.items()):
                lines.append(f"- {label}: {count}")
            lines.append("")

        if good_labels:
            lines.extend(["### Good Labels", ""])
            for label, count in sorted(good_labels.items()):
                lines.append(f"- {label}: {count}")
            lines.append("")

    if scored_results:
        provenance = _scoring_provenance(scored_results)
        lines.extend(
            [
                "## Scored Interpretation",
                "",
                f"- Scoring status: {scoring_status_for_result(result)}",
                f"- Verdict counts: {_fmt_counts(_verdict_counts(scored_results))}",
                f"- Highest scored prompt: {_prompt_score_extreme(scored_results, highest=True)}",
                f"- Lowest scored prompt: {_prompt_score_extreme(scored_results, highest=False)}",
                f"- Most common failure labels: {_top_label_counts(failure_labels)}",
                f"- Most common good labels: {_top_label_counts(good_labels)}",
                "- Claim boundary: scores summarize this run under the configured rubric; they are not universal model rankings or recommendations.",
                "",
                "### Scoring Provenance",
                "",
                f"- Scoring modes: {_fmt_counts(provenance['mode_counts'])}",
                f"- Reviewed scores: {provenance['reviewed_count']}",
                f"- Unreviewed scores: {provenance['unreviewed_count']}",
                f"- Scorer IDs: {_fmt_scorer_ids(provenance['scorer_ids'])}",
                "",
            ]
        )

        if provenance["unreviewed_count"]:
            lines.extend(
                [
                    "- Warning: some applied scores are unreviewed assisted drafts. Treat them as review-required metadata.",
                    "",
                ]
            )

    lines.extend(
        [
            "## Prompt Results",
            "",
            "Score avg values are manual review metadata when present. Speed and VRAM columns are operational signals.",
            "",
            "| Prompt | Category | Status | Score avg (0-5) | Prompt tok/s | Generation tok/s | E2E completion tok/s | Wall s | Finish | Failure | Peak VRAM MiB | VRAM Headroom MiB | Exit |",
            "|---|---|---:|---:|---:|---:|---:|---:|---|---|---:|---:|---:|",
        ]
    )

    for prompt_result in result["results"]:
        metrics = prompt_result.get("metrics")
        if not isinstance(metrics, dict):
            metrics = {}
        finish = prompt_result.get("finish_reason")
        if finish is None:
            finish = metrics.get("finish_reason")
        failure = prompt_result.get("failure_class") or ""
        wall = metrics.get("request_wall_time_seconds", _MISSING)
        if wall is _MISSING or wall is None:
            wall_cell = "-"
        else:
            wall_cell = _fmt(wall)
        lines.append(
            "| "
            f"{prompt_result['prompt_id']} | "
            f"{prompt_result.get('category') or ''} | "
            f"{prompt_result['status']} | "
            f"{_fmt(_score_average(prompt_result))} | "
            f"{_fmt_optional_throughput(metrics.get('prompt_eval_tps', _MISSING))} | "
            f"{_fmt_optional_throughput(metrics.get('generation_tps', _MISSING))} | "
            f"{_fmt_optional_throughput(metrics.get('end_to_end_completion_tps', _MISSING))} | "
            f"{wall_cell} | "
            f"{finish or '-'} | "
            f"{failure or '-'} | "
            f"{_fmt_optional_mib(_vram_peak_used_mib(prompt_result))} | "
            f"{_fmt_optional_mib(_vram_headroom_mib(prompt_result))} | "
            f"{prompt_result['exit_status']} |"
        )

    lines.extend(_build_audit_checklist(result))
    lines.extend(_build_prompt_artifact_audit(result))

    lines.extend(
        [
            "## Artifact integration",
            "",
            "- `llmgauge-result.json` is the machine-readable source of truth for run metadata and applied scores.",
            "- This `report.md` is the single-run human review artifact; read **Publish Readiness Notes** before publication.",
            "- Regenerate this report after `score --scores` or other updates to `llmgauge-result.json`.",
            "- Use `compare` for multi-run evidence summaries across result directories.",
            "- Use `export-index` for machine-readable importer metadata; it mirrors scoring evidence fields but is not a model recommendation.",
            "",
            "## Notes",
            "",
            "Raw model outputs are preserved separately and are not cleaned or filtered.",
            "",
        ]
    )

    return "\n".join(lines)
