from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from llmgauge.core.external_benchmark import (
    ExternalBenchmarkEvidence,
    GroupAggregation,
    SourceFact,
    TaskEvidence,
)

BUNDLE1_QUALIFICATION_ID = "llmgauge.bundle1.v0"
BUNDLE1_QUALIFICATION_VERSION = "0.1.0"
HARNESS_FAMILY = "lm_eval"
HARNESS_REPOSITORY = "https://github.com/EleutherAI/lm-evaluation-harness"
HARNESS_TAG = "v0.4.12"
HARNESS_COMMIT = "6d642546f4688648fced259eb3302efd36ece5af"
QUALIFICATION_DATE = "2026-08-16"

QualificationStatus = Literal["qualified", "unqualified", "conflicting"]

# Official default-MMLU subject -> subgroup mapping from
# lm_eval/tasks/mmlu/_generate_configs.py at v0.4.12.
MMLU_SUBJECT_SUBGROUPS: dict[str, str] = {
    "abstract_algebra": "stem",
    "anatomy": "stem",
    "astronomy": "stem",
    "business_ethics": "other",
    "clinical_knowledge": "other",
    "college_biology": "stem",
    "college_chemistry": "stem",
    "college_computer_science": "stem",
    "college_mathematics": "stem",
    "college_medicine": "other",
    "college_physics": "stem",
    "computer_security": "stem",
    "conceptual_physics": "stem",
    "econometrics": "social_sciences",
    "electrical_engineering": "stem",
    "elementary_mathematics": "stem",
    "formal_logic": "humanities",
    "global_facts": "other",
    "high_school_biology": "stem",
    "high_school_chemistry": "stem",
    "high_school_computer_science": "stem",
    "high_school_european_history": "humanities",
    "high_school_geography": "social_sciences",
    "high_school_government_and_politics": "social_sciences",
    "high_school_macroeconomics": "social_sciences",
    "high_school_mathematics": "stem",
    "high_school_microeconomics": "social_sciences",
    "high_school_physics": "stem",
    "high_school_psychology": "social_sciences",
    "high_school_statistics": "stem",
    "high_school_us_history": "humanities",
    "high_school_world_history": "humanities",
    "human_aging": "other",
    "human_sexuality": "social_sciences",
    "international_law": "humanities",
    "jurisprudence": "humanities",
    "logical_fallacies": "humanities",
    "machine_learning": "stem",
    "management": "other",
    "marketing": "other",
    "medical_genetics": "other",
    "miscellaneous": "other",
    "moral_disputes": "humanities",
    "moral_scenarios": "humanities",
    "nutrition": "other",
    "philosophy": "humanities",
    "prehistory": "humanities",
    "professional_accounting": "other",
    "professional_law": "humanities",
    "professional_medicine": "other",
    "professional_psychology": "social_sciences",
    "public_relations": "social_sciences",
    "security_studies": "social_sciences",
    "sociology": "social_sciences",
    "us_foreign_policy": "social_sciences",
    "virology": "other",
    "world_religions": "humanities",
}

MMLU_SUBGROUP_ORDER = ("stem", "other", "social_sciences", "humanities")
MMLU_SUBJECT_TASK_IDS = tuple(f"mmlu_{subject}" for subject in MMLU_SUBJECT_SUBGROUPS)
MMLU_SUBGROUP_IDS = tuple(f"mmlu_{name}" for name in MMLU_SUBGROUP_ORDER)
MMLU_SUBGROUP_TASK_IDS: dict[str, tuple[str, ...]] = {
    f"mmlu_{name}": tuple(
        f"mmlu_{subject}"
        for subject, subgroup in MMLU_SUBJECT_SUBGROUPS.items()
        if subgroup == name
    )
    for name in MMLU_SUBGROUP_ORDER
}


@dataclass(frozen=True)
class Bundle1Member:
    public_name: str
    member_id: str
    identity_kind: Literal["group", "task"]
    task_or_group_id: str
    source_paths: tuple[str, ...]
    dataset_path: str | None
    dataset_name: str | None
    split: str | None
    output_type: str
    num_fewshot: int | None
    fewshot_must_be_pinned: bool
    required_metric_bases: tuple[frozenset[str], ...]
    aggregation: str
    task_version: str | None
    group_version: str | None
    dataset_revision: None
    unsafe_code: bool
    notes: str


BUNDLE1_MEMBERS: tuple[Bundle1Member, ...] = (
    Bundle1Member(
        public_name="MMLU",
        member_id="mmlu",
        identity_kind="group",
        task_or_group_id="mmlu",
        source_paths=(
            "lm_eval/tasks/mmlu/README.md",
            "lm_eval/tasks/mmlu/default/_mmlu.yaml",
            "lm_eval/tasks/mmlu/default/_default_template_yaml",
            "lm_eval/tasks/mmlu/_generate_configs.py",
        ),
        dataset_path="cais/mmlu",
        dataset_name=None,
        split="test",
        output_type="multiple_choice",
        num_fewshot=None,
        fewshot_must_be_pinned=True,
        required_metric_bases=(frozenset({"acc"}),),
        aggregation="mean weighted by size",
        task_version="1.0",
        group_version="2",
        dataset_revision=None,
        unsafe_code=False,
        notes=(
            "Original Hendrycks multiple-choice group `mmlu`. Distinct from "
            "`mmlu_continuation` and `mmlu_generative`. Subject dataset_name "
            "values are the 57 official subject slugs. Task YAML does not pin "
            "num_fewshot; invocation must record n-shot explicitly."
        ),
    ),
    Bundle1Member(
        public_name="ARC Challenge",
        member_id="arc_challenge",
        identity_kind="task",
        task_or_group_id="arc_challenge",
        source_paths=(
            "lm_eval/tasks/arc/README.md",
            "lm_eval/tasks/arc/arc_challenge.yaml",
            "lm_eval/tasks/arc/arc_easy.yaml",
        ),
        dataset_path="allenai/ai2_arc",
        dataset_name="ARC-Challenge",
        split="test",
        output_type="multiple_choice",
        num_fewshot=None,
        fewshot_must_be_pinned=True,
        required_metric_bases=(frozenset({"acc"}), frozenset({"acc_norm"})),
        aggregation="mean",
        task_version="1.0",
        group_version=None,
        dataset_revision=None,
        unsafe_code=False,
        notes=(
            "Includes `arc_easy.yaml`. Distinct from `arc_easy` and "
            "`arc_challenge_chat`. Task YAML does not pin num_fewshot."
        ),
    ),
    Bundle1Member(
        public_name="HellaSwag",
        member_id="hellaswag",
        identity_kind="task",
        task_or_group_id="hellaswag",
        source_paths=(
            "lm_eval/tasks/hellaswag/README.md",
            "lm_eval/tasks/hellaswag/hellaswag.yaml",
        ),
        dataset_path="Rowan/hellaswag",
        dataset_name=None,
        split="validation",
        output_type="multiple_choice",
        num_fewshot=None,
        fewshot_must_be_pinned=True,
        required_metric_bases=(frozenset({"acc"}), frozenset({"acc_norm"})),
        aggregation="mean",
        task_version="1.0",
        group_version=None,
        dataset_revision=None,
        unsafe_code=False,
        notes="Preserve acc and acc_norm separately. Task YAML does not pin num_fewshot.",
    ),
    Bundle1Member(
        public_name="WinoGrande",
        member_id="winogrande",
        identity_kind="task",
        task_or_group_id="winogrande",
        source_paths=(
            "lm_eval/tasks/winogrande/README.md",
            "lm_eval/tasks/winogrande/default.yaml",
        ),
        dataset_path="allenai/winogrande",
        dataset_name="winogrande_xl",
        split="validation",
        output_type="multiple_choice",
        num_fewshot=None,
        fewshot_must_be_pinned=True,
        required_metric_bases=(frozenset({"acc"}),),
        aggregation="mean",
        task_version="1.0",
        group_version=None,
        dataset_revision=None,
        unsafe_code=False,
        notes="Partial-evaluation formulation. Task YAML does not pin num_fewshot.",
    ),
    Bundle1Member(
        public_name="TruthfulQA MC2",
        member_id="truthfulqa_mc2",
        identity_kind="task",
        task_or_group_id="truthfulqa_mc2",
        source_paths=(
            "lm_eval/tasks/truthfulqa/README.md",
            "lm_eval/tasks/truthfulqa/truthfulqa_mc2.yaml",
            "lm_eval/tasks/truthfulqa/truthfulqa_mc1.yaml",
        ),
        dataset_path="truthfulqa/truthful_qa",
        dataset_name="multiple_choice",
        split="validation",
        output_type="multiple_choice",
        num_fewshot=0,
        fewshot_must_be_pinned=False,
        required_metric_bases=(frozenset({"acc"}),),
        aggregation="mean",
        task_version="3.0",
        group_version=None,
        dataset_revision=None,
        unsafe_code=False,
        notes="Distinct from truthfulqa_mc1 and truthfulqa_gen. YAML pins num_fewshot 0.",
    ),
    Bundle1Member(
        public_name="GSM8K",
        member_id="gsm8k",
        identity_kind="task",
        task_or_group_id="gsm8k",
        source_paths=(
            "lm_eval/tasks/gsm8k/README.md",
            "lm_eval/tasks/gsm8k/gsm8k.yaml",
        ),
        dataset_path="openai/gsm8k",
        dataset_name="main",
        split="test",
        output_type="generate_until",
        num_fewshot=5,
        fewshot_must_be_pinned=False,
        required_metric_bases=(frozenset({"exact_match"}),),
        aggregation="mean",
        task_version="3.0",
        group_version=None,
        dataset_revision=None,
        unsafe_code=False,
        notes=(
            "Official filters are strict-match and flexible-extract. Distinct "
            "from gsm8k_cot and gsm8k_cot_llama. YAML pins num_fewshot 5."
        ),
    ),
    Bundle1Member(
        public_name="HumanEval",
        member_id="humaneval",
        identity_kind="task",
        task_or_group_id="humaneval",
        source_paths=(
            "lm_eval/tasks/humaneval/README.md",
            "lm_eval/tasks/humaneval/humaneval.yaml",
            "lm_eval/tasks/humaneval/utils.py",
        ),
        dataset_path="openai/openai_humaneval",
        dataset_name=None,
        split="test",
        output_type="generate_until",
        num_fewshot=0,
        fewshot_must_be_pinned=False,
        required_metric_bases=(frozenset({"pass_at_k", "pass_at_1", "pass@1"}),),
        aggregation="mean",
        task_version="1.0",
        group_version=None,
        dataset_revision=None,
        unsafe_code=True,
        notes=(
            "pass@1 via utils.pass_at_k with k=[1]. Distinct from humaneval_64, "
            "humaneval_instruct, and humaneval_plus. YAML sets unsafe_code: true."
        ),
    ),
    Bundle1Member(
        public_name="MBPP",
        member_id="mbpp",
        identity_kind="task",
        task_or_group_id="mbpp",
        source_paths=(
            "lm_eval/tasks/mbpp/README.md",
            "lm_eval/tasks/mbpp/mbpp.yaml",
            "lm_eval/tasks/mbpp/utils.py",
        ),
        dataset_path="google-research-datasets/mbpp",
        dataset_name="full",
        split="test",
        output_type="generate_until",
        num_fewshot=3,
        fewshot_must_be_pinned=False,
        required_metric_bases=(frozenset({"pass_at_1", "pass@1"}),),
        aggregation="mean",
        task_version="1.0",
        group_version=None,
        dataset_revision=None,
        unsafe_code=True,
        notes=(
            "pass@1 via utils.pass_at_1. Distinct from mbpp_plus and "
            "mbpp_instruct. YAML sets unsafe_code: true and pins num_fewshot 3."
        ),
    ),
)

BUNDLE1_MEMBERS_BY_ID = {item.member_id: item for item in BUNDLE1_MEMBERS}


@dataclass(frozen=True)
class MemberQualification:
    member_id: str
    public_name: str
    status: QualificationStatus
    reasons: tuple[str, ...]
    matched_identity: str | None


@dataclass(frozen=True)
class Bundle1Qualification:
    qualification_id: str
    qualification_version: str
    harness_repository: str
    harness_tag: str
    harness_commit: str
    qualification_date: str
    overall_status: QualificationStatus
    members: tuple[MemberQualification, ...]
    harness_pin_match: Literal["matched", "absent", "different"]


def _metric_base(name: str) -> str:
    return name.split(",", 1)[0]


def _available_value(fact: SourceFact) -> Any | None:
    if fact.availability != "available":
        return None
    return fact.value


def _has_required_metrics(
    metric_names: list[str], required: tuple[frozenset[str], ...]
) -> bool:
    bases = {_metric_base(name) for name in metric_names}
    return all(not option.isdisjoint(bases) for option in required)


def _fact_conflicts(fact: SourceFact, expected: Any) -> bool:
    value = _available_value(fact)
    if value is None:
        return False
    return value != expected


def _task_by_id(
    evidence: ExternalBenchmarkEvidence, task_id: str
) -> TaskEvidence | None:
    for item in evidence.tasks:
        if item.task_id == task_id:
            return item
    return None


def _group_by_id(
    evidence: ExternalBenchmarkEvidence, group_id: str
) -> GroupAggregation | None:
    for item in evidence.groups:
        if item.group_id == group_id:
            return item
    return None


def _task_contract_conflicts(member: Bundle1Member, task: TaskEvidence) -> list[str]:
    conflicts: list[str] = []
    if member.dataset_path is not None and _fact_conflicts(
        task.dataset_path, member.dataset_path
    ):
        conflicts.append(
            f"dataset_path {task.dataset_path.value!r} is not {member.dataset_path!r}"
        )
    if member.dataset_name is not None and _fact_conflicts(
        task.dataset_name, member.dataset_name
    ):
        conflicts.append(
            f"dataset_name {task.dataset_name.value!r} is not {member.dataset_name!r}"
        )
    if member.split is not None and _fact_conflicts(task.split, member.split):
        conflicts.append(f"split {task.split.value!r} is not {member.split!r}")
    if _fact_conflicts(task.output_type, member.output_type):
        conflicts.append(
            f"output_type {task.output_type.value!r} is not {member.output_type!r}"
        )
    if member.num_fewshot is not None and _fact_conflicts(
        task.n_shot, member.num_fewshot
    ):
        conflicts.append(
            f"n_shot {task.n_shot.value!r} is not the pinned {member.num_fewshot}"
        )
    if member.task_version is not None and _fact_conflicts(
        task.version, member.task_version
    ):
        version = task.version.value
        if str(version) != str(member.task_version):
            conflicts.append(
                f"task version {version!r} is not the pinned {member.task_version!r}"
            )
    if not _has_required_metrics(
        [item.metric_name for item in task.metrics],
        member.required_metric_bases,
    ):
        conflicts.append("required native metrics are missing")
    return conflicts


def _mmlu_subject_conflicts(task: TaskEvidence) -> list[str]:
    if not task.task_id.startswith("mmlu_"):
        return [f"{task.task_id} is not an official mmlu subject"]
    subject = task.task_id.removeprefix("mmlu_")
    if subject not in MMLU_SUBJECT_SUBGROUPS:
        return [f"{task.task_id} is not an official default mmlu subject"]
    probe = Bundle1Member(
        public_name="MMLU subject",
        member_id="mmlu",
        identity_kind="task",
        task_or_group_id=task.task_id,
        source_paths=(),
        dataset_path="cais/mmlu",
        dataset_name=subject,
        split="test",
        output_type="multiple_choice",
        num_fewshot=None,
        fewshot_must_be_pinned=True,
        required_metric_bases=(frozenset({"acc"}),),
        aggregation="mean",
        task_version="1.0",
        group_version=None,
        dataset_revision=None,
        unsafe_code=False,
        notes="",
    )
    return _task_contract_conflicts(probe, task)


def _qualify_mmlu(evidence: ExternalBenchmarkEvidence) -> MemberQualification:
    member = BUNDLE1_MEMBERS_BY_ID["mmlu"]
    group = _group_by_id(evidence, "mmlu")
    if group is None:
        return MemberQualification(
            member_id=member.member_id,
            public_name=member.public_name,
            status="unqualified",
            reasons=("official group identity mmlu is not present",),
            matched_identity=None,
        )
    conflicts: list[str] = []
    expected_children = set(MMLU_SUBGROUP_IDS)
    actual_children = set(group.subtask_ids)
    if actual_children != expected_children:
        conflicts.append(
            "group mmlu composition is not the four official subgroups "
            f"{', '.join(MMLU_SUBGROUP_IDS)}"
        )
    if not _has_required_metrics(
        [item.metric_name for item in group.metrics],
        member.required_metric_bases,
    ):
        conflicts.append("group mmlu is missing official acc aggregation")
    for subgroup_id, expected_tasks in MMLU_SUBGROUP_TASK_IDS.items():
        subgroup = _group_by_id(evidence, subgroup_id)
        if subgroup is None:
            conflicts.append(f"official subgroup {subgroup_id} is absent")
            continue
        if set(subgroup.subtask_ids) != set(expected_tasks):
            conflicts.append(
                f"subgroup {subgroup_id} does not contain its official subjects"
            )
        if not _has_required_metrics(
            [item.metric_name for item in subgroup.metrics],
            member.required_metric_bases,
        ):
            conflicts.append(f"subgroup {subgroup_id} is missing official acc")
        for task_id in expected_tasks:
            task = _task_by_id(evidence, task_id)
            if task is None:
                conflicts.append(f"official subject {task_id} is absent")
                continue
            conflicts.extend(_mmlu_subject_conflicts(task))
    if conflicts:
        return MemberQualification(
            member_id=member.member_id,
            public_name=member.public_name,
            status="conflicting",
            reasons=tuple(conflicts),
            matched_identity="mmlu",
        )
    return MemberQualification(
        member_id=member.member_id,
        public_name=member.public_name,
        status="qualified",
        reasons=("exact official mmlu group, subgroups, and 57 subjects",),
        matched_identity="mmlu",
    )


def _qualify_task_member(
    evidence: ExternalBenchmarkEvidence, member: Bundle1Member
) -> MemberQualification:
    task = _task_by_id(evidence, member.task_or_group_id)
    if task is None:
        return MemberQualification(
            member_id=member.member_id,
            public_name=member.public_name,
            status="unqualified",
            reasons=(
                f"official task identity {member.task_or_group_id} is not present",
            ),
            matched_identity=None,
        )
    conflicts = _task_contract_conflicts(member, task)
    if conflicts:
        return MemberQualification(
            member_id=member.member_id,
            public_name=member.public_name,
            status="conflicting",
            reasons=tuple(conflicts),
            matched_identity=member.task_or_group_id,
        )
    return MemberQualification(
        member_id=member.member_id,
        public_name=member.public_name,
        status="qualified",
        reasons=(f"exact official task identity {member.task_or_group_id}",),
        matched_identity=member.task_or_group_id,
    )


def _git_hash_matches_pin(hash_text: str | None) -> bool:
    if hash_text is None:
        return True
    text = hash_text.strip()
    if not text:
        return False
    if HARNESS_COMMIT.startswith(text):
        return True
    if text.lstrip("v") == HARNESS_TAG.lstrip("v"):
        return True
    marker = "-g"
    if marker in text:
        abbrev = text.rsplit(marker, 1)[-1].split("-", 1)[0]
        if len(abbrev) >= 7 and all(
            character in "0123456789abcdefABCDEF" for character in abbrev
        ):
            return HARNESS_COMMIT.startswith(abbrev.lower())
    return False


def _harness_pin_match(
    evidence: ExternalBenchmarkEvidence,
) -> Literal["matched", "absent", "different"]:
    version = _available_value(evidence.harness.version)
    git_hash = _available_value(evidence.harness.git_hash)
    if version is None and git_hash is None:
        return "absent"
    version_text = str(version) if version is not None else None
    hash_text = str(git_hash) if git_hash is not None else None
    version_ok = version_text is None or version_text.lstrip("v") == HARNESS_TAG.lstrip(
        "v"
    )
    hash_ok = hash_text is None or _git_hash_matches_pin(hash_text)
    if version_ok and hash_ok:
        if version_text is not None or hash_text is not None:
            if version_text is not None and hash_text is not None:
                return "matched"
            return "matched"
    if not version_ok or not hash_ok:
        return "different"
    return "absent"


def qualify_bundle1(evidence: ExternalBenchmarkEvidence) -> Bundle1Qualification:
    members: list[MemberQualification] = []
    for member in BUNDLE1_MEMBERS:
        if member.member_id == "mmlu":
            members.append(_qualify_mmlu(evidence))
        else:
            members.append(_qualify_task_member(evidence, member))
    if any(item.status == "conflicting" for item in members):
        overall: QualificationStatus = "conflicting"
    elif all(item.status == "qualified" for item in members):
        overall = "qualified"
    else:
        overall = "unqualified"
    return Bundle1Qualification(
        qualification_id=BUNDLE1_QUALIFICATION_ID,
        qualification_version=BUNDLE1_QUALIFICATION_VERSION,
        harness_repository=HARNESS_REPOSITORY,
        harness_tag=HARNESS_TAG,
        harness_commit=HARNESS_COMMIT,
        qualification_date=QUALIFICATION_DATE,
        overall_status=overall,
        members=tuple(members),
        harness_pin_match=_harness_pin_match(evidence),
    )
