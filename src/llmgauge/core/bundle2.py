"""Bundle 2 qualification for official lm-evaluation-harness identities.

Mirrors :mod:`llmgauge.core.bundle1` for MMLU-Pro, GPQA (n-shot), and IFEval
at the same v0.4.12 harness pin. Qualification is computed at report and
inspection time from imported source-backed facts; it is never written into
``external-benchmark/evidence.json``. LLMGauge stays read-only.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any


from llmgauge.core.bundle1 import (
    HARNESS_COMMIT,
    HARNESS_REPOSITORY,
    HARNESS_TAG,
    Bundle1Member,
    MemberQualification,
    QualificationStatus,
    _group_by_id,
    _harness_pin_match,
    _has_required_metrics,
    _task_by_id,
    _task_contract_conflicts,
)
from llmgauge.core.external_benchmark import ExternalBenchmarkEvidence

BUNDLE2_QUALIFICATION_ID = "llmgauge.bundle2.v0"
BUNDLE2_QUALIFICATION_VERSION = "0.1.0"
QUALIFICATION_DATE = "2026-08-26"

# Official mmlu_pro subject list from lm_eval/tasks/mmlu_pro/_mmlu_pro.yaml
# at tag v0.4.12 (order preserved).
MMLU_PRO_SUBJECTS: tuple[str, ...] = (
    "biology",
    "business",
    "chemistry",
    "computer_science",
    "economics",
    "engineering",
    "health",
    "history",
    "law",
    "math",
    "other",
    "philosophy",
    "physics",
    "psychology",
)
MMLU_PRO_TASK_IDS: tuple[str, ...] = tuple(
    f"mmlu_pro_{subject}" for subject in MMLU_PRO_SUBJECTS
)

# Official GPQA n-shot tasks at v0.4.12. The cot_* , zeroshot, and generative
# variants are distinct lookalike identities, not this member.
GPQA_N_SHOT_TASK_IDS: tuple[str, ...] = (
    "gpqa_diamond_n_shot",
    "gpqa_extended_n_shot",
    "gpqa_main_n_shot",
)


def _member(
    *,
    public_name: str,
    member_id: str,
    identity_kind: Any,
    task_or_group_id: str,
    source_paths: tuple[str, ...],
    dataset_path: str | None,
    dataset_name: str | None,
    split: str | None,
    output_type: str,
    num_fewshot: int | None,
    required_metric_bases: tuple[frozenset[str], ...],
    task_version: str | None,
    group_version: str | None,
    notes: str,
) -> Bundle1Member:
    return Bundle1Member(
        public_name=public_name,
        member_id=member_id,
        identity_kind=identity_kind,
        task_or_group_id=task_or_group_id,
        source_paths=source_paths,
        dataset_path=dataset_path,
        dataset_name=dataset_name,
        split=split,
        output_type=output_type,
        num_fewshot=num_fewshot,
        fewshot_must_be_pinned=num_fewshot is not None,
        required_metric_bases=required_metric_bases,
        aggregation="mean",
        task_version=task_version,
        group_version=group_version,
        dataset_revision=None,
        unsafe_code=False,
        notes=notes,
    )


BUNDLE2_MEMBERS: tuple[Bundle1Member, ...] = (
    _member(
        public_name="MMLU-Pro",
        member_id="mmlu_pro",
        identity_kind="group",
        task_or_group_id="mmlu_pro",
        source_paths=(
            "lm_eval/tasks/mmlu_pro/README.md",
            "lm_eval/tasks/mmlu_pro/_mmlu_pro.yaml",
            "lm_eval/tasks/mmlu_pro/_default_template_yaml",
            "lm_eval/tasks/mmlu_pro/mmlu_pro_biology.yaml",
        ),
        dataset_path="TIGER-Lab/MMLU-Pro",
        dataset_name=None,
        split="test",
        output_type="generate_until",
        num_fewshot=None,
        required_metric_bases=(frozenset({"exact_match"}),),
        task_version=None,
        group_version="2.0",
        notes=(
            "Group mmlu_pro over its 14 official subjects. Official scoring "
            "requires the custom-extract filter over exact_match; a result "
            "scored without that filter is conflicting. Distinct from plain "
            "mmlu and all Flan/generative lookalikes."
        ),
    ),
    _member(
        public_name="GPQA Diamond (n-shot)",
        member_id="gpqa_diamond_n_shot",
        identity_kind="task",
        task_or_group_id="gpqa_diamond_n_shot",
        source_paths=(
            "lm_eval/tasks/gpqa/README.md",
            "lm_eval/tasks/gpqa/n_shot/_gpqa_n_shot_yaml",
            "lm_eval/tasks/gpqa/n_shot/gpqa_diamond_n_shot.yaml",
        ),
        dataset_path="Idavidrein/gpqa",
        dataset_name="gpqa_diamond",
        split=None,
        output_type="multiple_choice",
        num_fewshot=None,
        required_metric_bases=(frozenset({"acc"}), frozenset({"acc_norm"})),
        task_version="2.2",
        group_version=None,
        notes=(
            "Gated upstream dataset: operators must accept the Idavidrein/gpqa "
            "terms with their own Hugging Face token. LLMGauge imports "
            "already-produced results only and never downloads the dataset. "
            "Distinct from gpqa_{main,extended}_n_shot and every cot_*, "
            "zeroshot, or generative variant."
        ),
    ),
    _member(
        public_name="GPQA Extended (n-shot)",
        member_id="gpqa_extended_n_shot",
        identity_kind="task",
        task_or_group_id="gpqa_extended_n_shot",
        source_paths=(
            "lm_eval/tasks/gpqa/README.md",
            "lm_eval/tasks/gpqa/n_shot/_gpqa_n_shot_yaml",
            "lm_eval/tasks/gpqa/n_shot/gpqa_extended_n_shot.yaml",
        ),
        dataset_path="Idavidrein/gpqa",
        dataset_name="gpqa_extended",
        split=None,
        output_type="multiple_choice",
        num_fewshot=None,
        required_metric_bases=(frozenset({"acc"}), frozenset({"acc_norm"})),
        task_version="2.2",
        group_version=None,
        notes=("Same gated-dataset boundary as the other GPQA n-shot members."),
    ),
    _member(
        public_name="GPQA Main (n-shot)",
        member_id="gpqa_main_n_shot",
        identity_kind="task",
        task_or_group_id="gpqa_main_n_shot",
        source_paths=(
            "lm_eval/tasks/gpqa/README.md",
            "lm_eval/tasks/gpqa/n_shot/_gpqa_n_shot_yaml",
            "lm_eval/tasks/gpqa/n_shot/gpqa_main_n_shot.yaml",
        ),
        dataset_path="Idavidrein/gpqa",
        dataset_name="gpqa_main",
        split=None,
        output_type="multiple_choice",
        num_fewshot=None,
        required_metric_bases=(frozenset({"acc"}), frozenset({"acc_norm"})),
        task_version="2.2",
        group_version=None,
        notes=("Same gated-dataset boundary as the other GPQA n-shot members."),
    ),
    _member(
        public_name="IFEval",
        member_id="ifeval",
        identity_kind="task",
        task_or_group_id="ifeval",
        source_paths=(
            "lm_eval/tasks/ifeval/README.md",
            "lm_eval/tasks/ifeval/ifeval.yaml",
        ),
        dataset_path="google/IFEval",
        dataset_name=None,
        split="train",
        output_type="generate_until",
        num_fewshot=0,
        required_metric_bases=(
            frozenset({"prompt_level_strict_acc"}),
            frozenset({"inst_level_strict_acc"}),
            frozenset({"prompt_level_loose_acc"}),
            frozenset({"inst_level_loose_acc"}),
        ),
        task_version="4.0",
        group_version=None,
        notes=(
            "Official test data lives in the dataset train split; strict and "
            "loose prompt- and instruction-level accuracies are separate "
            "native metrics and must never be merged or renamed."
        ),
    ),
)

BUNDLE2_MEMBERS_BY_ID = {item.member_id: item for item in BUNDLE2_MEMBERS}

_MMLU_PRO_SUBJECT_MEMBER = _member(
    public_name="MMLU-Pro subject",
    member_id="mmlu_pro",
    identity_kind="task",
    task_or_group_id="",
    source_paths=(),
    dataset_path="TIGER-Lab/MMLU-Pro",
    dataset_name=None,
    split="test",
    output_type="generate_until",
    num_fewshot=5,
    required_metric_bases=(frozenset({"exact_match"}),),
    task_version="3.1",
    group_version=None,
    notes="",
)


def _qualify_mmlu_pro(evidence: ExternalBenchmarkEvidence) -> MemberQualification:
    member = BUNDLE2_MEMBERS_BY_ID["mmlu_pro"]
    group = _group_by_id(evidence, "mmlu_pro")
    if group is None:
        return MemberQualification(
            member_id=member.member_id,
            public_name=member.public_name,
            status="unqualified",
            reasons=("official group identity mmlu_pro is not present",),
            matched_identity=None,
        )
    conflicts: list[str] = []
    if set(group.subtask_ids) != set(MMLU_PRO_TASK_IDS):
        conflicts.append(
            "group mmlu_pro composition is not the 14 official subjects "
            f"{', '.join(MMLU_PRO_TASK_IDS)}"
        )
    if not _has_required_metrics(
        [item.metric_name for item in group.metrics], member.required_metric_bases
    ):
        conflicts.append("group mmlu_pro is missing official exact_match aggregation")
    elif not any(
        name.split(",", 1) == ["exact_match", "custom-extract"]
        for name in (item.metric_name for item in group.metrics)
    ):
        conflicts.append(
            "official custom-extract filter is not represented in the "
            "mmlu_pro aggregate"
        )
    for task_id in MMLU_PRO_TASK_IDS:
        task = _task_by_id(evidence, task_id)
        if task is None:
            conflicts.append(f"official subject {task_id} is absent")
            continue
        probe = replace(_MMLU_PRO_SUBJECT_MEMBER, task_or_group_id=task_id)
        conflicts.extend(_task_contract_conflicts(probe, task))
        if not any(
            name.split(",", 1) == ["exact_match", "custom-extract"]
            for name in (item.metric_name for item in task.metrics)
        ):
            conflicts.append(
                f"official subject {task_id} lacks the custom-extract filter"
            )
    if conflicts:
        return MemberQualification(
            member_id=member.member_id,
            public_name=member.public_name,
            status="conflicting",
            reasons=tuple(conflicts),
            matched_identity="mmlu_pro",
        )
    return MemberQualification(
        member_id=member.member_id,
        public_name=member.public_name,
        status="qualified",
        reasons=("exact official mmlu_pro group and 14 subjects",),
        matched_identity="mmlu_pro",
    )


@dataclass(frozen=True)
class Bundle2Qualification:
    """Result shape mirroring bundle1.Bundle1Qualification."""

    qualification_id: str = BUNDLE2_QUALIFICATION_ID
    qualification_version: str = BUNDLE2_QUALIFICATION_VERSION
    harness_repository: str = HARNESS_REPOSITORY
    harness_tag: str = HARNESS_TAG
    harness_commit: str = HARNESS_COMMIT
    qualification_date: str = QUALIFICATION_DATE
    overall_status: QualificationStatus = "unqualified"
    members: tuple[MemberQualification, ...] = ()
    harness_pin_match: Any = "absent"


def qualify_bundle2(evidence: ExternalBenchmarkEvidence) -> Bundle2Qualification:
    """Qualify imported evidence against the pinned Bundle 2 identities."""
    members: list[MemberQualification] = []
    for member in BUNDLE2_MEMBERS:
        if member.member_id == "mmlu_pro":
            members.append(_qualify_mmlu_pro(evidence))
        else:
            task = _task_by_id(evidence, member.task_or_group_id)
            if task is None:
                members.append(
                    MemberQualification(
                        member_id=member.member_id,
                        public_name=member.public_name,
                        status="unqualified",
                        reasons=(
                            "official task identity "
                            f"{member.task_or_group_id} is not present",
                        ),
                        matched_identity=None,
                    )
                )
                continue
            conflicts = _task_contract_conflicts(member, task)
            status: QualificationStatus = "conflicting" if conflicts else "qualified"
            reason = (
                tuple(conflicts)
                if conflicts
                else (f"exact official task identity {member.task_or_group_id}",)
            )
            members.append(
                MemberQualification(
                    member_id=member.member_id,
                    public_name=member.public_name,
                    status=status,
                    reasons=reason,
                    matched_identity=member.task_or_group_id,
                )
            )
    if any(item.status == "conflicting" for item in members):
        overall: QualificationStatus = "conflicting"
    elif all(item.status == "qualified" for item in members):
        overall = "qualified"
    else:
        overall = "unqualified"
    return Bundle2Qualification(
        overall_status=overall,
        members=tuple(members),
        harness_pin_match=_harness_pin_match(evidence),
    )
