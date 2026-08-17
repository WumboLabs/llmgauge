from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return path


def single_task_results(
    *,
    include_optional: bool = True,
    extra_task: dict[str, Any] | None = None,
) -> dict[str, Any]:
    task = {
        "alias": "hellaswag",
        "acc,none": 0.85,
        "acc_stderr,none": 0.01,
        "acc_norm,none": 0.87,
        "acc_norm_stderr,none": 0.012,
    }
    payload: dict[str, Any] = {
        "results": {"hellaswag": task},
        "group_subtasks": {},
        "groups": {},
        "configs": {
            "hellaswag": {
                "task": "hellaswag",
                "dataset_path": "Rowan/hellaswag",
                "dataset_name": None,
                "test_split": "validation",
                "num_fewshot": 0,
                "output_type": "multiple_choice",
                "metric_list": [
                    {
                        "metric": "acc",
                        "aggregation": "mean",
                        "higher_is_better": True,
                    },
                    {
                        "metric": "acc_norm",
                        "aggregation": "mean",
                        "higher_is_better": True,
                    },
                ],
                "generation_kwargs": {"temperature": 0.0, "do_sample": False},
                "dataset_kwargs": {"revision": "main"},
                "metadata": {"version": 1.0},
            }
        },
        "versions": {"hellaswag": 1.0},
        "n-shot": {"hellaswag": 0},
        "higher_is_better": {"hellaswag": {"acc": True, "acc_norm": True}},
        "n-samples": {"hellaswag": {"original": 10042, "effective": 10042}},
        "config": {
            "model": "hf",
            "model_args": "pretrained=org/demo-model,dtype=float16",
            "batch_size": 8,
            "device": "cuda:0",
            "limit": None,
            "random_seed": 0,
            "numpy_random_seed": 1234,
            "torch_random_seed": 1234,
            "fewshot_random_seed": 1234,
        },
        "git_hash": "abc1234",
        "lm_eval_version": "0.4.8",
        "transformers_version": "4.40.0",
        "model_source": "hf",
        "model_name": "org/demo-model",
    }
    if extra_task is not None:
        payload["results"].update(extra_task)
    if not include_optional:
        for key in (
            "configs",
            "versions",
            "n-shot",
            "higher_is_better",
            "n-samples",
            "config",
            "git_hash",
            "lm_eval_version",
            "transformers_version",
            "model_source",
            "model_name",
        ):
            payload.pop(key, None)
    return payload


def multi_task_results() -> dict[str, Any]:
    payload = single_task_results()
    payload["results"]["arc_challenge"] = {
        "alias": "arc_challenge",
        "acc,none": 0.61,
        "acc_stderr,none": 0.014,
        "acc_norm,none": 0.64,
        "acc_norm_stderr,none": 0.014,
    }
    payload["results"]["gsm8k"] = {
        "alias": "gsm8k",
        "exact_match,flexible-extract": 0.42,
        "exact_match_stderr,flexible-extract": 0.02,
    }
    payload["results"]["humaneval"] = {
        "alias": "humaneval",
        "pass_at_1,none": 0.18,
        "pass_at_1_stderr,none": 0.03,
    }
    payload["configs"]["arc_challenge"] = {
        "task": "arc_challenge",
        "dataset_path": "ai2_arc",
        "dataset_name": "ARC-Challenge",
        "test_split": "test",
        "num_fewshot": 0,
        "output_type": "multiple_choice",
        "metric_list": [
            {"metric": "acc", "aggregation": "mean", "higher_is_better": True}
        ],
        "metadata": {"version": 1.0},
    }
    payload["configs"]["gsm8k"] = {
        "task": "gsm8k",
        "dataset_path": "gsm8k",
        "dataset_name": "main",
        "test_split": "test",
        "num_fewshot": 5,
        "output_type": "generate_until",
        "metric_list": [
            {"metric": "exact_match", "aggregation": "mean", "higher_is_better": True}
        ],
        "metadata": {"version": 3.0},
    }
    payload["configs"]["humaneval"] = {
        "task": "humaneval",
        "dataset_path": "openai_humaneval",
        "test_split": "test",
        "num_fewshot": 0,
        "output_type": "generate_until",
        "metric_list": [
            {"metric": "pass_at_1", "aggregation": "mean", "higher_is_better": True}
        ],
        "metadata": {"version": 1.0},
    }
    payload["versions"].update({"arc_challenge": 1.0, "gsm8k": 3.0, "humaneval": 1.0})
    payload["n-shot"].update({"arc_challenge": 0, "gsm8k": 5, "humaneval": 0})
    payload["higher_is_better"].update(
        {
            "arc_challenge": {"acc": True, "acc_norm": True},
            "gsm8k": {"exact_match": True},
            "humaneval": {"pass_at_1": True},
        }
    )
    payload["n-samples"].update(
        {
            "arc_challenge": {"original": 1172, "effective": 1172},
            "gsm8k": {"original": 1319, "effective": 1319},
            "humaneval": {"original": 164, "effective": 164},
        }
    )
    return payload


def grouped_mmlu_results() -> dict[str, Any]:
    payload = {
        "results": {
            "mmlu_abstract_algebra": {
                "alias": "abstract_algebra",
                "acc,none": 0.31,
                "acc_stderr,none": 0.04,
            },
            "mmlu_anatomy": {
                "alias": "anatomy",
                "acc,none": 0.55,
                "acc_stderr,none": 0.03,
            },
        },
        "groups": {
            "mmlu": {
                "alias": "mmlu",
                "acc,none": 0.43,
                "acc_stderr,none": 0.025,
            }
        },
        "group_subtasks": {"mmlu": ["mmlu_abstract_algebra", "mmlu_anatomy"]},
        "configs": {
            "mmlu_abstract_algebra": {
                "task": "mmlu_abstract_algebra",
                "dataset_path": "hails/mmlu_no_train",
                "dataset_name": "abstract_algebra",
                "test_split": "test",
                "num_fewshot": 5,
                "output_type": "multiple_choice",
                "metric_list": [
                    {"metric": "acc", "aggregation": "mean", "higher_is_better": True}
                ],
            },
            "mmlu_anatomy": {
                "task": "mmlu_anatomy",
                "dataset_path": "hails/mmlu_no_train",
                "dataset_name": "anatomy",
                "test_split": "test",
                "num_fewshot": 5,
                "output_type": "multiple_choice",
                "metric_list": [
                    {"metric": "acc", "aggregation": "mean", "higher_is_better": True}
                ],
            },
        },
        "n-shot": {"mmlu_abstract_algebra": 5, "mmlu_anatomy": 5},
        "higher_is_better": {
            "mmlu_abstract_algebra": {"acc": True},
            "mmlu_anatomy": {"acc": True},
            "mmlu": {"acc": True},
        },
        "n-samples": {
            "mmlu_abstract_algebra": {"original": 100, "effective": 100},
            "mmlu_anatomy": {"original": 135, "effective": 135},
        },
        "config": {"model": "hf", "model_args": "pretrained=org/demo-model"},
        "lm_eval_version": "0.4.8",
        "model_name": "org/demo-model",
        "model_source": "hf",
    }
    return payload


def malformed_metric_results() -> dict[str, Any]:
    payload = single_task_results()
    payload["results"]["hellaswag"]["acc,none"] = float("nan")
    return payload


def write_single_task_file(root: Path) -> Path:
    return write_json(root / "results.json", single_task_results())


def write_missing_optional_file(root: Path) -> Path:
    return write_json(
        root / "results.json", single_task_results(include_optional=False)
    )


def write_multi_task_tree(root: Path) -> Path:
    write_json(root / "results.json", multi_task_results())
    write_json(root / "config.json", {"note": "accompanying config"})
    (root / "eval.log").write_text("lm-eval completed\n", encoding="utf-8")
    (root / "samples_hellaswag.jsonl").write_text(
        json.dumps({"doc_id": 0, "acc": 1}) + "\n", encoding="utf-8"
    )
    return root


def write_grouped_file(root: Path) -> Path:
    return write_json(root / "results.json", grouped_mmlu_results())


def write_malformed_metrics_file(root: Path) -> Path:
    # Emit a literal NaN token so json.loads(parse_constant=...) can reject it.
    path = root / "results.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = single_task_results()
    text = json.dumps(payload, indent=2, sort_keys=True)
    text = text.replace('"acc,none": 0.85', '"acc,none": NaN')
    path.write_text(text + "\n", encoding="utf-8")
    return path


def write_unsafe_tree(root: Path) -> Path:
    write_json(root / "results.json", single_task_results())
    (root / "escape").symlink_to("/etc/passwd")
    return root


def _metric_block(
    *,
    alias: str,
    metrics: dict[str, float],
    include_sample_len: bool = False,
) -> dict[str, Any]:
    block: dict[str, Any] = {"alias": alias}
    block.update(metrics)
    if include_sample_len:
        block["sample_len"] = 100
    return block


def _task_config(
    *,
    task: str,
    dataset_path: str,
    dataset_name: str | None,
    split_key: str,
    split: str,
    num_fewshot: int | None,
    output_type: str,
    metrics: list[str],
    version: float | str,
) -> dict[str, Any]:
    config: dict[str, Any] = {
        "task": task,
        "dataset_path": dataset_path,
        "dataset_name": dataset_name,
        split_key: split,
        "output_type": output_type,
        "metric_list": [
            {"metric": name, "aggregation": "mean", "higher_is_better": True}
            for name in metrics
        ],
        "metadata": {"version": version},
    }
    if num_fewshot is not None:
        config["num_fewshot"] = num_fewshot
    return config


def nested_group_results() -> dict[str, Any]:
    return {
        "results": {
            "leaf_a": _metric_block(alias="leaf_a", metrics={"acc,none": 0.4}),
            "leaf_b": _metric_block(alias="leaf_b", metrics={"acc,none": 0.6}),
            "child_group": _metric_block(
                alias="child",
                metrics={"acc,none": 0.5, "sample_len": 2},
                include_sample_len=False,
            ),
            "parent_group": _metric_block(
                alias="parent",
                metrics={"acc,none": 0.5},
                include_sample_len=True,
            ),
        },
        "groups": {
            "child_group": {
                "alias": "child",
                "acc,none": 0.5,
                "acc_stderr,none": 0.01,
                "sample_len": 2,
            },
            "parent_group": {
                "alias": "parent",
                "acc,none": 0.5,
                "acc_stderr,none": 0.01,
                "sample_len": 2,
            },
        },
        "group_subtasks": {
            "parent_group": ["child_group"],
            "child_group": ["leaf_a", "leaf_b"],
        },
        "configs": {
            "leaf_a": _task_config(
                task="leaf_a",
                dataset_path="org/demo",
                dataset_name="a",
                split_key="test_split",
                split="test",
                num_fewshot=0,
                output_type="multiple_choice",
                metrics=["acc"],
                version=1.0,
            ),
            "leaf_b": _task_config(
                task="leaf_b",
                dataset_path="org/demo",
                dataset_name="b",
                split_key="test_split",
                split="test",
                num_fewshot=0,
                output_type="multiple_choice",
                metrics=["acc"],
                version=1.0,
            ),
        },
        "n-shot": {"leaf_a": 0, "leaf_b": 0},
        "versions": {"leaf_a": 1.0, "leaf_b": 1.0},
        "higher_is_better": {
            "leaf_a": {"acc": True},
            "leaf_b": {"acc": True},
            "child_group": {"acc": True},
            "parent_group": {"acc": True},
        },
        "config": {"model": "hf", "model_args": "pretrained=org/demo-model"},
        "lm_eval_version": "0.4.12",
        "git_hash": "6d642546f4688648fced259eb3302efd36ece5af",
        "model_name": "org/demo-model",
        "model_source": "hf",
    }


def official_mmlu_results() -> dict[str, Any]:
    from llmgauge.core.bundle1 import (
        MMLU_SUBJECT_SUBGROUPS,
        MMLU_SUBGROUP_IDS,
        MMLU_SUBGROUP_TASK_IDS,
    )

    results: dict[str, Any] = {}
    groups: dict[str, Any] = {}
    group_subtasks: dict[str, list[str]] = {"mmlu": list(MMLU_SUBGROUP_IDS)}
    configs: dict[str, Any] = {}
    n_shot: dict[str, int] = {}
    versions: dict[str, Any] = {}
    higher: dict[str, Any] = {"mmlu": {"acc": True}}
    n_samples: dict[str, Any] = {}
    for subgroup_id, task_ids in MMLU_SUBGROUP_TASK_IDS.items():
        group_subtasks[subgroup_id] = list(task_ids)
        groups[subgroup_id] = {
            "alias": subgroup_id.removeprefix("mmlu_"),
            "acc,none": 0.5,
            "acc_stderr,none": 0.01,
            "sample_len": len(task_ids),
            "sample_count": {"acc,none": len(task_ids)},
        }
        results[subgroup_id] = dict(groups[subgroup_id])
        higher[subgroup_id] = {"acc": True}
        for task_id in task_ids:
            subject = task_id.removeprefix("mmlu_")
            results[task_id] = {
                "alias": subject,
                "acc,none": 0.5,
                "acc_stderr,none": 0.02,
                "sample_len": 10,
            }
            configs[task_id] = _task_config(
                task=task_id,
                dataset_path="cais/mmlu",
                dataset_name=subject,
                split_key="test_split",
                split="test",
                num_fewshot=5,
                output_type="multiple_choice",
                metrics=["acc"],
                version=1.0,
            )
            n_shot[task_id] = 5
            versions[task_id] = 1.0
            higher[task_id] = {"acc": True}
            n_samples[task_id] = {"original": 10, "effective": 10}
    groups["mmlu"] = {
        "alias": "mmlu",
        "acc,none": 0.5,
        "acc_stderr,none": 0.01,
        "sample_len": len(MMLU_SUBJECT_SUBGROUPS),
        "sample_count": {"acc,none": len(MMLU_SUBJECT_SUBGROUPS)},
    }
    results["mmlu"] = dict(groups["mmlu"])
    return {
        "results": results,
        "groups": groups,
        "group_subtasks": group_subtasks,
        "configs": configs,
        "n-shot": n_shot,
        "versions": versions,
        "higher_is_better": higher,
        "n-samples": n_samples,
        "config": {"model": "hf", "model_args": "pretrained=org/demo-model"},
        "lm_eval_version": "0.4.12",
        "git_hash": "6d642546f4688648fced259eb3302efd36ece5af",
        "model_name": "org/demo-model",
        "model_source": "hf",
    }


OFFICIAL_V0412_GIT_DESCRIBE = "v0.4.10-81-g6d642546"


def official_v0412_writer_group_results() -> dict[str, Any]:
    leaf = {
        "alias": "leaf",
        "name": "writer_leaf",
        "sample_len": 1,
        "acc,none": 1.0,
        "acc_stderr,none": "N/A",
    }
    group = {
        "alias": "group",
        "name": "writer_group",
        "sample_len": 1,
        "acc,none": 1.0,
        "acc_stderr,none": "N/A",
        "sample_count": {"acc,none": 1},
    }
    return {
        "results": {"writer_leaf": leaf, "writer_group": dict(group)},
        "groups": {"writer_group": dict(group)},
        "group_subtasks": {"writer_group": ["writer_leaf"]},
        "configs": {
            "writer_leaf": _task_config(
                task="writer_leaf",
                dataset_path="example/dataset",
                dataset_name=None,
                split_key="validation_split",
                split="validation",
                num_fewshot=0,
                output_type="multiple_choice",
                metrics=["acc"],
                version=1.0,
            )
        },
        "n-shot": {"writer_leaf": 0},
        "versions": {"writer_leaf": 1.0},
        "higher_is_better": {
            "writer_leaf": {"acc": True},
            "writer_group": {"acc": True},
        },
        "n-samples": {"writer_leaf": {"original": 10, "effective": 1}},
        "config": {"model": "dummy", "model_args": "{}"},
        "lm_eval_version": "0.4.12",
        "git_hash": OFFICIAL_V0412_GIT_DESCRIBE,
        "model_name": "dummy",
        "model_source": "dummy",
    }


def write_official_v0412_writer_group_file(root: Path) -> Path:
    return write_json(root / "results.json", official_v0412_writer_group_results())


def official_task_results(
    *,
    task_id: str,
    dataset_path: str,
    dataset_name: str | None,
    split_key: str,
    split: str,
    num_fewshot: int,
    output_type: str,
    metrics: dict[str, float],
    metric_names: list[str],
    version: float | str,
) -> dict[str, Any]:
    payload = {
        "results": {
            task_id: _metric_block(
                alias=task_id, metrics=metrics, include_sample_len=True
            )
        },
        "groups": {},
        "group_subtasks": {},
        "configs": {
            task_id: _task_config(
                task=task_id,
                dataset_path=dataset_path,
                dataset_name=dataset_name,
                split_key=split_key,
                split=split,
                num_fewshot=num_fewshot,
                output_type=output_type,
                metrics=metric_names,
                version=version,
            )
        },
        "n-shot": {task_id: num_fewshot},
        "versions": {task_id: version},
        "higher_is_better": {task_id: {name: True for name in metric_names}},
        "n-samples": {task_id: {"original": 100, "effective": 100}},
        "config": {"model": "hf", "model_args": "pretrained=org/demo-model"},
        "lm_eval_version": "0.4.12",
        "git_hash": "6d642546f4688648fced259eb3302efd36ece5af",
        "model_name": "org/demo-model",
        "model_source": "hf",
    }
    return payload


def official_arc_challenge_results() -> dict[str, Any]:
    return official_task_results(
        task_id="arc_challenge",
        dataset_path="allenai/ai2_arc",
        dataset_name="ARC-Challenge",
        split_key="test_split",
        split="test",
        num_fewshot=25,
        output_type="multiple_choice",
        metrics={"acc,none": 0.5, "acc_norm,none": 0.52},
        metric_names=["acc", "acc_norm"],
        version=1.0,
    )


def official_hellaswag_results() -> dict[str, Any]:
    return official_task_results(
        task_id="hellaswag",
        dataset_path="Rowan/hellaswag",
        dataset_name=None,
        split_key="validation_split",
        split="validation",
        num_fewshot=10,
        output_type="multiple_choice",
        metrics={"acc,none": 0.7, "acc_norm,none": 0.72},
        metric_names=["acc", "acc_norm"],
        version=1.0,
    )


def official_winogrande_results() -> dict[str, Any]:
    return official_task_results(
        task_id="winogrande",
        dataset_path="allenai/winogrande",
        dataset_name="winogrande_xl",
        split_key="validation_split",
        split="validation",
        num_fewshot=5,
        output_type="multiple_choice",
        metrics={"acc,none": 0.68},
        metric_names=["acc"],
        version=1.0,
    )


def official_truthfulqa_mc2_results() -> dict[str, Any]:
    return official_task_results(
        task_id="truthfulqa_mc2",
        dataset_path="truthfulqa/truthful_qa",
        dataset_name="multiple_choice",
        split_key="validation_split",
        split="validation",
        num_fewshot=0,
        output_type="multiple_choice",
        metrics={"acc,none": 0.45},
        metric_names=["acc"],
        version=3.0,
    )


def official_gsm8k_results() -> dict[str, Any]:
    return official_task_results(
        task_id="gsm8k",
        dataset_path="openai/gsm8k",
        dataset_name="main",
        split_key="test_split",
        split="test",
        num_fewshot=5,
        output_type="generate_until",
        metrics={
            "exact_match,strict-match": 0.4,
            "exact_match,flexible-extract": 0.42,
        },
        metric_names=["exact_match"],
        version=3.0,
    )


def official_humaneval_results() -> dict[str, Any]:
    return official_task_results(
        task_id="humaneval",
        dataset_path="openai/openai_humaneval",
        dataset_name=None,
        split_key="test_split",
        split="test",
        num_fewshot=0,
        output_type="generate_until",
        metrics={"pass@1": 0.2},
        metric_names=["pass@1"],
        version=1.0,
    )


def official_mbpp_results() -> dict[str, Any]:
    return official_task_results(
        task_id="mbpp",
        dataset_path="google-research-datasets/mbpp",
        dataset_name="full",
        split_key="test_split",
        split="test",
        num_fewshot=3,
        output_type="generate_until",
        metrics={"pass@1": 0.3},
        metric_names=["pass@1"],
        version=1.0,
    )


def merge_lm_eval_results(*payloads: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {
        "results": {},
        "groups": {},
        "group_subtasks": {},
        "configs": {},
        "n-shot": {},
        "versions": {},
        "higher_is_better": {},
        "n-samples": {},
        "config": {"model": "hf", "model_args": "pretrained=org/demo-model"},
        "lm_eval_version": "0.4.12",
        "git_hash": "6d642546f4688648fced259eb3302efd36ece5af",
        "model_name": "org/demo-model",
        "model_source": "hf",
    }
    for payload in payloads:
        for key in (
            "results",
            "groups",
            "group_subtasks",
            "configs",
            "n-shot",
            "versions",
            "higher_is_better",
            "n-samples",
        ):
            value = payload.get(key)
            if isinstance(value, dict):
                merged[key].update(value)
    return merged


def official_bundle1_results() -> dict[str, Any]:
    return merge_lm_eval_results(
        official_mmlu_results(),
        official_arc_challenge_results(),
        official_hellaswag_results(),
        official_winogrande_results(),
        official_truthfulqa_mc2_results(),
        official_gsm8k_results(),
        official_humaneval_results(),
        official_mbpp_results(),
    )


def conflicting_humaneval_results() -> dict[str, Any]:
    payload = official_humaneval_results()
    payload["configs"]["humaneval"]["dataset_path"] = "evalplus/humanevalplus"
    return payload


def lookalike_mmlu_pro_results() -> dict[str, Any]:
    return official_task_results(
        task_id="mmlu_pro",
        dataset_path="TIGER-Lab/MMLU-Pro",
        dataset_name=None,
        split_key="test_split",
        split="test",
        num_fewshot=5,
        output_type="multiple_choice",
        metrics={"acc,none": 0.4},
        metric_names=["acc"],
        version=1.0,
    )


def write_nested_group_file(root: Path) -> Path:
    return write_json(root / "results.json", nested_group_results())


def write_official_bundle1_file(root: Path) -> Path:
    return write_json(root / "results.json", official_bundle1_results())


def write_official_humaneval_file(root: Path) -> Path:
    return write_json(root / "results.json", official_humaneval_results())


def write_conflicting_humaneval_file(root: Path) -> Path:
    return write_json(root / "results.json", conflicting_humaneval_results())


def write_lookalike_mmlu_pro_file(root: Path) -> Path:
    return write_json(root / "results.json", lookalike_mmlu_pro_results())


def write_official_mmlu_file(root: Path) -> Path:
    return write_json(root / "results.json", official_mmlu_results())
