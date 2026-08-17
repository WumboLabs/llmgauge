from __future__ import annotations

import json
from pathlib import Path

from llmgauge.core.artifacts import write_text
from llmgauge.core.bundle1 import (
    BUNDLE1_MEMBERS_BY_ID,
    Bundle1Qualification,
    qualify_bundle1,
)
from llmgauge.core.external_benchmark import (
    EVIDENCE_RELATIVE_PATH,
    REPORT_RELATIVE_PATH,
    ExternalBenchmarkEvidence,
    NativeMetric,
    SourceFact,
    load_external_benchmark_evidence,
)
from llmgauge.core.result_validation import load_result_json, validate_result_dir


class ExternalBenchmarkReportError(ValueError):
    """Bounded failure while building a read-only external-benchmark report."""


def _format_fact(fact: SourceFact) -> str:
    if fact.availability == "available":
        return json.dumps(fact.value, ensure_ascii=False, sort_keys=True)
    return fact.availability


def _format_metric(metric: NativeMetric) -> str:
    stderr = _format_fact(metric.stderr)
    direction = _format_fact(metric.higher_is_better)
    aggregation = _format_fact(metric.aggregation)
    return (
        f"`{metric.metric_name}`={metric.value} "
        f"(stderr={stderr}; higher_is_better={direction}; aggregation={aggregation})"
    )


def _status_label(status: str) -> str:
    return {
        "qualified": "qualified",
        "unqualified": "imported but not Bundle 1-qualified",
        "conflicting": "conflicting or malformed identity",
    }[status]


def _load_validated_evidence(result_dir: Path) -> ExternalBenchmarkEvidence:
    try:
        result = load_result_json(result_dir)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise ExternalBenchmarkReportError("result could not be read") from exc
    if result.get("external_benchmark_evidence") is None:
        raise ExternalBenchmarkReportError(
            "result is not imported external benchmark evidence"
        )
    errors = validate_result_dir(result_dir)
    if errors:
        raise ExternalBenchmarkReportError("; ".join(errors))
    try:
        return load_external_benchmark_evidence(
            result_dir, result["external_benchmark_evidence"]
        )
    except ValueError as exc:
        raise ExternalBenchmarkReportError(str(exc)) from exc


def build_external_benchmark_report(
    evidence: ExternalBenchmarkEvidence,
    *,
    qualification: Bundle1Qualification | None = None,
) -> str:
    qualification = qualification or qualify_bundle1(evidence)
    member_lines = []
    for item in qualification.members:
        member = BUNDLE1_MEMBERS_BY_ID[item.member_id]
        identity = item.matched_identity or member.task_or_group_id
        reasons = "; ".join(item.reasons)
        member_lines.append(
            f"- {item.public_name} (`{identity}`): {_status_label(item.status)}. {reasons}."
        )
    task_lines = []
    for task in evidence.tasks:
        metrics = "; ".join(_format_metric(item) for item in task.metrics)
        task_lines.append(
            f"- `{task.task_id}`: n_shot={_format_fact(task.n_shot)}; "
            f"dataset_path={_format_fact(task.dataset_path)}; "
            f"dataset_name={_format_fact(task.dataset_name)}; "
            f"split={_format_fact(task.split)}; "
            f"output_type={_format_fact(task.output_type)}; "
            f"version={_format_fact(task.version)}; metrics: {metrics}"
        )
    group_lines = []
    for group in evidence.groups:
        if group.metrics:
            metrics = "; ".join(_format_metric(item) for item in group.metrics)
        else:
            metrics = "no aggregated metrics recorded"
        children = ", ".join(f"`{item}`" for item in group.subtask_ids)
        group_lines.append(f"- `{group.group_id}` members {children}; {metrics}")
    code_members = [
        item
        for item in qualification.members
        if BUNDLE1_MEMBERS_BY_ID[item.member_id].unsafe_code
        and item.status != "unqualified"
    ]
    if code_members:
        names = ", ".join(item.public_name for item in code_members)
        execution_line = (
            f"- {names} source metrics were produced upstream. Official "
            "HumanEval/MBPP tasks set `unsafe_code: true` and require "
            "`--confirm_run_unsafe_code` because they execute generated "
            "Python. LLMGauge imported already-produced results only and "
            "did not execute candidate code, invoke benchmark tests, or "
            "run `code_eval`."
        )
    else:
        execution_line = (
            "- LLMGauge did not execute generated code, invoke benchmark "
            "tests, or contact a network while building this report."
        )
    return "\n".join(
        [
            "# External Benchmark Report",
            "",
            "This is a read-only summary of imported EleutherAI "
            "`lm-evaluation-harness` evidence. It is not a native LLMGauge "
            "quality score, ranking, model recommendation, or publication "
            "decision.",
            "",
            "## 1. Source and containment",
            f"- Evidence path: `{EVIDENCE_RELATIVE_PATH}`.",
            f"- Evidence ID: `{evidence.evidence_id}`.",
            f"- Source package SHA-256: `{evidence.source_package_sha256}`.",
            f"- Importer: `{evidence.importer.importer_id}` {evidence.importer.version}.",
            f"- Imported at: {evidence.importer.imported_at}.",
            f"- Evaluation class: `{evidence.evaluation_class}`.",
            f"- Source type: `{evidence.source_type}`.",
            f"- Harness family: `{evidence.harness.family}`.",
            f"- Harness version: {_format_fact(evidence.harness.version)}.",
            f"- Harness git hash: {_format_fact(evidence.harness.git_hash)}.",
            f"- Model name: {_format_fact(evidence.model.model_name)}.",
            f"- Model source: {_format_fact(evidence.model.model_source)}.",
            f"- Hugging Face ID: {_format_fact(evidence.model.hf_id)}.",
            f"- Validation outcome: `{evidence.validation_outcome}`.",
            f"- Scoreability: `{evidence.scoreability}`.",
            f"- Publication readiness: `{evidence.publication_readiness}`.",
            "",
            "## 2. Bundle 1 qualification",
            f"- Qualification ID: `{qualification.qualification_id}` "
            f"{qualification.qualification_version}.",
            f"- Official pin: {qualification.harness_repository} "
            f"`{qualification.harness_tag}` "
            f"(`{qualification.harness_commit}`), dated "
            f"{qualification.qualification_date}.",
            f"- Harness pin match: `{qualification.harness_pin_match}`.",
            f"- Overall Bundle 1 status: "
            f"`{_status_label(qualification.overall_status)}`.",
            "- Qualification is computed at report time and is not written "
            "into `evidence.json`.",
            *member_lines,
            "",
            "## 3. Imported tasks and native metrics",
            *task_lines,
            "",
            "## 4. Group aggregations",
            *(group_lines or ["- No group aggregations were imported."]),
            "",
            "## 5. Claim boundaries",
            "- This report does not invent a universal score or weighted total.",
            "- Native metric names remain untranslated. Metrics from different "
            "benchmarks are not equivalent.",
            "- Missing metadata is reported as unavailable; it is not repaired.",
            "- A qualified identity is not a quality, safety, or ranking claim.",
            "- An imported-but-unqualified result remains valid generic lm-eval evidence.",
            "- A conflicting identity is not reinterpreted as the official member.",
            execution_line,
            "- Native `score`, `report`, `compare`, export-index, and "
            "public-export paths must not consume this result.",
            "",
        ]
    )


def write_external_benchmark_report(
    result_dir: Path,
) -> tuple[Path, Bundle1Qualification]:
    evidence = _load_validated_evidence(result_dir)
    qualification = qualify_bundle1(evidence)
    report = build_external_benchmark_report(evidence, qualification=qualification)
    path = result_dir / REPORT_RELATIVE_PATH
    write_text(path, report)
    return path, qualification
