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
