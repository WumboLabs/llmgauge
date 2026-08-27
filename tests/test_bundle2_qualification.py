from __future__ import annotations

import json
from pathlib import Path

from external_benchmark_fixtures import (
    merge_lm_eval_results,
    official_task_results,
    write_json,
)
from llmgauge.core.bundle2 import (
    BUNDLE2_MEMBERS,
    MMLU_PRO_SUBJECTS,
    MMLU_PRO_TASK_IDS,
    qualify_bundle2,
)
from llmgauge.core.external_benchmark import (
    load_external_benchmark_evidence,
)
from llmgauge.core.result_validation import validate_result_dir


def _read_evidence(result_dir: Path):
    result = json.loads(
        (result_dir / "llmgauge-result.json").read_text(encoding="utf-8")
    )
    return load_external_benchmark_evidence(
        result_dir, result["external_benchmark_evidence"]
    )


def _import(source: Path, destination: Path):
    from llmgauge.core.external_benchmark import import_lm_eval_harness_results

    import_lm_eval_harness_results(source, destination)
    return _read_evidence(destination)


def _member_status(qualification, member_id: str) -> str:
    return next(
        item.status for item in qualification.members if item.member_id == member_id
    )


def _mmlu_pro_subject_results(subject: str) -> dict:
    return official_task_results(
        task_id=f"mmlu_pro_{subject}",
        dataset_path="TIGER-Lab/MMLU-Pro",
        dataset_name=None,
        split_key="test_split",
        split="test",
        num_fewshot=5,
        output_type="generate_until",
        metrics={"exact_match,custom-extract": 0.3},
        metric_names=["exact_match"],
        version=3.1,
    )


def official_mmlu_pro_results() -> dict:
    merged = merge_lm_eval_results(
        *(_mmlu_pro_subject_results(subject) for subject in MMLU_PRO_SUBJECTS)
    )
    merged["groups"]["mmlu_pro"] = {
        "alias": "mmlu_pro",
        "exact_match,custom-extract": 0.35,
    }
    merged["group_subtasks"]["mmlu_pro"] = list(MMLU_PRO_TASK_IDS)
    return merged


def official_gpqa_results(variant: str) -> dict:
    return official_task_results(
        task_id=f"gpqa_{variant}_n_shot",
        dataset_path="Idavidrein/gpqa",
        dataset_name=f"gpqa_{variant}",
        split_key="validation_split",
        split="train",
        num_fewshot=0,
        output_type="multiple_choice",
        metrics={"acc,none": 0.31, "acc_norm,none": 0.33},
        metric_names=["acc", "acc_norm"],
        version=2.2,
    )


def official_ifeval_results() -> dict:
    return official_task_results(
        task_id="ifeval",
        dataset_path="google/IFEval",
        dataset_name=None,
        split_key="test_split",
        split="train",
        num_fewshot=0,
        output_type="generate_until",
        metrics={
            "prompt_level_strict_acc,none": 0.42,
            "inst_level_strict_acc,none": 0.51,
            "prompt_level_loose_acc,none": 0.48,
            "inst_level_loose_acc,none": 0.57,
        },
        metric_names=[
            "prompt_level_strict_acc",
            "inst_level_strict_acc",
            "prompt_level_loose_acc",
            "inst_level_loose_acc",
        ],
        version=4.0,
    )


def write_official_bundle2_file(root: Path) -> Path:
    return write_json(
        root / "results.json",
        merge_lm_eval_results(
            official_mmlu_pro_results(),
            official_gpqa_results("diamond"),
            official_gpqa_results("extended"),
            official_gpqa_results("main"),
            official_ifeval_results(),
        ),
    )


def test_bundle2_all_members_qualify(tmp_path: Path) -> None:
    source = write_official_bundle2_file(tmp_path / "source")
    evidence = _import(source, tmp_path / "result")
    assert validate_result_dir(tmp_path / "result") == []
    qualification = qualify_bundle2(evidence)
    assert qualification.qualification_id == "llmgauge.bundle2.v0"
    assert qualification.harness_tag == "v0.4.12"
    assert qualification.harness_pin_match == "matched"
    assert qualification.overall_status == "qualified"
    assert all(item.status == "qualified" for item in qualification.members)
    assert len(qualification.members) == len(BUNDLE2_MEMBERS)


def test_bundle2_unqualified_when_members_absent(tmp_path: Path) -> None:
    source = tmp_path / "source"
    write_json(source / "results.json", official_ifeval_results())
    evidence = _import(source, tmp_path / "result")
    qualification = qualify_bundle2(evidence)
    assert _member_status(qualification, "ifeval") == "qualified"
    assert all(item.status == "unqualified" for item in qualification.members[:4])
    assert qualification.overall_status == "unqualified"


def test_mmlu_pro_without_custom_extract_filter_conflicts(tmp_path: Path) -> None:
    merged = official_mmlu_pro_results()
    for payload in merged["configs"].values():
        payload["metric_list"] = [
            {"metric": "exact_match", "aggregation": "mean", "higher_is_better": True}
        ]
    for entry in merged["results"].values():
        entry["exact_match,none"] = entry.pop("exact_match,custom-extract")
    merged["groups"]["mmlu_pro"] = {"alias": "mmlu_pro", "exact_match,none": 0.35}
    source = tmp_path / "source"
    write_json(
        source / "results.json",
        merge_lm_eval_results(merged, official_ifeval_results()),
    )
    evidence = _import(source, tmp_path / "result")
    qualification = qualify_bundle2(evidence)
    assert _member_status(qualification, "mmlu_pro") == "conflicting"
    assert any(
        "custom-extract" in reason
        for reason in next(
            item.reasons
            for item in qualification.members
            if item.member_id == "mmlu_pro"
        )
    )


def test_ifeval_with_missing_loose_metrics_conflicts(tmp_path: Path) -> None:
    payload = official_ifeval_results()
    payload["results"]["ifeval"] = {
        key: value
        for key, value in payload["results"]["ifeval"].items()
        if "loose" not in key
    }
    payload["configs"]["ifeval"]["metric_list"] = [
        {"metric": "prompt_level_strict_acc", "aggregation": "mean"},
        {"metric": "inst_level_strict_acc", "aggregation": "mean"},
    ]
    source = tmp_path / "source"
    write_json(
        source / "results.json",
        merge_lm_eval_results(payload, official_mmlu_pro_results()),
    )
    evidence = _import(source, tmp_path / "result")
    qualification = qualify_bundle2(evidence)
    assert _member_status(qualification, "ifeval") == "conflicting"


def test_gpqa_cot_lookalike_does_not_qualify(tmp_path: Path) -> None:
    lookalike = official_task_results(
        task_id="gpqa_diamond_cot_n_shot",
        dataset_path="Idavidrein/gpqa",
        dataset_name="gpqa_diamond",
        split_key="validation_split",
        split="train",
        num_fewshot=8,
        output_type="generate_until",
        metrics={"exact_match,none": 0.4},
        metric_names=["exact_match"],
        version=1.0,
    )
    source = tmp_path / "source"
    write_json(
        source / "results.json",
        merge_lm_eval_results(lookalike, official_mmlu_pro_results()),
    )
    evidence = _import(source, tmp_path / "result")
    qualification = qualify_bundle2(evidence)
    assert _member_status(qualification, "gpqa_diamond_n_shot") == "unqualified"
