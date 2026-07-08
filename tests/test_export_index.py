import json
from pathlib import Path

import pytest

from llmgauge.core.export_index import (
    build_export_index,
    detect_artifact_type,
    write_export_index,
)


def test_detect_artifact_type_run(tmp_path: Path) -> None:
    result_dir = tmp_path / "run-a"
    result_dir.mkdir()
    (result_dir / "llmgauge-result.json").write_text("{}", encoding="utf-8")

    assert detect_artifact_type(result_dir) == "run"


def test_detect_artifact_type_ladder(tmp_path: Path) -> None:
    result_dir = tmp_path / "ladder-a"
    result_dir.mkdir()
    (result_dir / "ladder-summary.json").write_text("{}", encoding="utf-8")

    assert detect_artifact_type(result_dir) == "ladder"




def test_detect_artifact_type_fit_ladder(tmp_path: Path) -> None:
    result_dir = tmp_path / "fit-a"
    result_dir.mkdir()
    (result_dir / "fit-ladder-summary.json").write_text("{}", encoding="utf-8")

    assert detect_artifact_type(result_dir) == "fit_ladder"


def test_detect_artifact_type_rejects_unknown(tmp_path: Path) -> None:
    result_dir = tmp_path / "unknown"
    result_dir.mkdir()

    with pytest.raises(ValueError, match="unsupported artifact path"):
        detect_artifact_type(result_dir)


def test_build_export_index_for_run(tmp_path: Path) -> None:
    result_dir = tmp_path / "run-a"
    result_dir.mkdir()
    (result_dir / "raw").mkdir()
    (result_dir / "cleaned").mkdir()
    (result_dir / "logs").mkdir()
    (result_dir / "report.md").write_text("# Report\n", encoding="utf-8")
    (result_dir / "vram").mkdir()
    (result_dir / "vram" / "honesty-unknown-tool.samples.json").write_text(
        "{}\n", encoding="utf-8"
    )
    (result_dir / "llmgauge-result.json").write_text(
        """
{
  "schema_version": "llmgauge.result.v0",
  "run": {
    "run_id": "run-a",
    "timestamp_utc": "2026-06-16T06:00:00+00:00",
    "status": "completed"
  },
  "model": {
    "model_id": "test-model",
    "model_profile": "test-profile"
  },
  "suite": {
    "suite_id": "agent-backend-v1",
    "suite_version": "0.1.0",
    "prompt_count": 1
  },
  "summary": {
    "completed": 1,
    "failed": 0,
    "manual_score_total": null,
    "manual_score_max": null
  },
  "results": [
    {
      "prompt_id": "honesty-unknown-tool",
      "vram": {
        "schema_version": "llmgauge.vram.summary.v0",
        "available": true,
        "sample_count": 14,
        "peak_used_mib": 7535,
        "peak_total_mib": 12227,
        "peak_gpu_index": 0,
        "peak_gpu_name": "NVIDIA GeForce RTX 5070",
        "initial_used_mib": 393,
        "final_used_mib": 393,
        "error": null
      },
      "vram_samples_path": "vram/honesty-unknown-tool.samples.json"
    }
  ]
}
""".strip()
        + "\n",
        encoding="utf-8",
    )

    index = build_export_index([result_dir])
    item = index["items"][0]

    assert index["schema_version"] == "llmgauge.export_index.v0"
    assert index["item_count"] == 1
    assert item["artifact_type"] == "run"
    assert item["run_id"] == "run-a"
    assert item["suite_id"] == "agent-backend-v1"
    assert item["model_id"] == "test-model"
    assert item["completed"] == 1
    assert item["failed"] == 0
    assert item["has_raw_artifacts"] is True
    assert item["has_cleaned_artifacts"] is True
    assert item["has_logs"] is True
    assert item["vram_available"] is True
    assert item["peak_vram_mib"] == 7535
    assert item["min_vram_headroom_mib"] == 4692
    assert item["vram_prompt_count"] == 1
    assert item["vram_sample_artifact_count"] == 1


def test_build_export_index_for_run_without_vram(tmp_path: Path) -> None:
    result_dir = tmp_path / "run-without-vram"
    result_dir.mkdir()
    (result_dir / "llmgauge-result.json").write_text(
        """
{
  "schema_version": "llmgauge.result.v0",
  "run": {
    "run_id": "run-without-vram",
    "timestamp_utc": "2026-06-16T06:00:00+00:00",
    "status": "completed"
  },
  "model": {
    "model_id": "test-model",
    "model_profile": "test-profile"
  },
  "suite": {
    "suite_id": "agent-backend-v1",
    "suite_version": "0.1.0",
    "prompt_count": 1
  },
  "summary": {
    "completed": 1,
    "failed": 0,
    "manual_score_total": null,
    "manual_score_max": null
  },
  "results": [
    {
      "prompt_id": "honesty-unknown-tool"
    }
  ]
}
""".strip()
        + "\n",
        encoding="utf-8",
    )

    index = build_export_index([result_dir])
    item = index["items"][0]

    assert item["has_raw_artifacts"] is False
    assert item["has_cleaned_artifacts"] is False
    assert item["has_logs"] is False
    assert item["vram_available"] is False
    assert item["peak_vram_mib"] is None
    assert item["min_vram_headroom_mib"] is None
    assert item["vram_prompt_count"] == 0
    assert item["vram_sample_artifact_count"] == 0


def test_build_export_index_for_ladder(tmp_path: Path) -> None:
    result_dir = tmp_path / "ladder-a"
    result_dir.mkdir()
    (result_dir / "ladder-report.md").write_text("# Ladder\n", encoding="utf-8")
    (result_dir / "ladder-summary.json").write_text(
        """
{
  "schema_version": "llmgauge.context_ladder.v0",
  "ladder_id": "ladder-a",
  "suite_id": "agent-backend-v1",
  "model_id": "test-model",
  "include": "all",
  "only": null,
  "contexts": [8192, 16384],
  "child_runs": [
    {"ctx_size": 8192, "status": "completed"},
    {"ctx_size": 16384, "status": "completed"}
  ],
  "summary": {
    "total": 2,
    "completed": 2,
    "failed": 0
  }
}
""".strip()
        + "\n",
        encoding="utf-8",
    )

    index = build_export_index([result_dir])
    item = index["items"][0]

    assert item["artifact_type"] == "ladder"
    assert item["ladder_id"] == "ladder-a"
    assert item["suite_id"] == "agent-backend-v1"
    assert item["contexts"] == [8192, 16384]
    assert item["child_run_count"] == 2
    assert item["completed"] == 2
    assert item["failed"] == 0




def test_build_export_index_for_fit_ladder(tmp_path: Path) -> None:
    result_dir = tmp_path / "fit-a"
    result_dir.mkdir()
    (result_dir / "fit-ladder-report.md").write_text("# Fit Ladder\n", encoding="utf-8")
    (result_dir / "fit-ladder-summary.json").write_text(
        """
{
  "schema_version": "llmgauge.fit_ladder.v0",
  "fit_ladder_id": "fit-a",
  "requested_settings": {
    "suite_id": "core-v1",
    "include": "honesty",
    "only": null,
    "model_id": "test-model",
    "model_profile": "test-profile",
    "ctx_size": 65536,
    "batch_size": 256,
    "ubatch_size": 64,
    "gpu_layers": 999
  },
  "retry_policy": {
    "fallback_order": ["context"],
    "fallback_contexts": [8192, 32768],
    "stop_on_first_completed": true,
    "gpu_layer_fallback": "explicit-only"
  },
  "selected_working_settings": {
    "ctx_size": 32768,
    "batch_size": 256,
    "ubatch_size": 64,
    "gpu_layers": 999,
    "attempt_id": "attempt-02"
  },
  "final_status": "completed_with_fallback",
  "summary": {
    "attempted": 2,
    "completed": 1,
    "failed": 1,
    "oom_detected": true,
    "fallback_changed_context": true
  },
  "attempts": [
    {"attempt_id": "attempt-01", "status": "failed", "ctx_size": 65536},
    {"attempt_id": "attempt-02", "status": "completed", "ctx_size": 32768}
  ]
}
""".strip()
        + "\n",
        encoding="utf-8",
    )

    index = build_export_index([result_dir])
    item = index["items"][0]

    assert item["artifact_type"] == "fit_ladder"
    assert item["fit_ladder_id"] == "fit-a"
    assert item["suite_id"] == "core-v1"
    assert item["model_id"] == "test-model"
    assert item["requested_ctx"] == 65536
    assert item["selected_ctx"] == 32768
    assert item["attempt_count"] == 2
    assert item["completed"] == 1
    assert item["failed"] == 1
    assert item["oom_detected"] is True
    assert item["fit_ladder_report"] == str(result_dir / "fit-ladder-report.md")


def test_write_export_index(tmp_path: Path) -> None:
    out = tmp_path / "index" / "llmgauge-index.json"
    write_export_index(
        out,
        {
            "schema_version": "llmgauge.export_index.v0",
            "generated_at_utc": "2026-06-16T06:00:00+00:00",
            "item_count": 0,
            "items": [],
        },
    )

    assert out.exists()
    assert "llmgauge.export_index.v0" in out.read_text(encoding="utf-8")


def test_build_export_index_can_validate_run(tmp_path: Path) -> None:
    result_dir = tmp_path / "run-a"
    result_dir.mkdir()
    (result_dir / "llmgauge-result.json").write_text(
        """
{
  "schema_version": "llmgauge.result.v0",
  "run": {
    "run_id": "run-a",
    "timestamp_utc": "2026-06-16T06:00:00+00:00",
    "status": "completed"
  },
  "model": {
    "model_id": "test-model",
    "model_profile": "test-profile"
  },
  "suite": {
    "suite_id": "agent-backend-v1",
    "suite_version": "0.1.0",
    "prompt_count": 0
  },
  "summary": {
    "completed": 0,
    "failed": 0,
    "manual_score_total": null,
    "manual_score_max": null
  },
  "results": []
}
""".strip()
        + "\n",
        encoding="utf-8",
    )

    index = build_export_index([result_dir], validate=True)
    item = index["items"][0]

    assert index["validation_checked"] is True
    assert item["validation"]["checked"] is True
    assert item["validation"]["status"] == "invalid"
    assert item["validation"]["errors"]


def test_build_export_index_can_validate_ladder(tmp_path: Path) -> None:
    result_dir = tmp_path / "ladder-a"
    result_dir.mkdir()
    (result_dir / "ladder-summary.json").write_text(
        """
{
  "schema_version": "llmgauge.context_ladder.v0",
  "ladder_id": "ladder-a",
  "suite_id": "agent-backend-v1",
  "model_id": "test-model",
  "include": "all",
  "only": null,
  "contexts": [8192],
  "child_runs": [
    {
      "ctx_size": 8192,
      "status": "failed",
      "result_dir": "ctx-8192",
      "completed": null,
      "failed": null,
      "error": "intentional test failure"
    }
  ],
  "summary": {
    "total": 1,
    "completed": 0,
    "failed": 1
  }
}
""".strip()
        + "\n",
        encoding="utf-8",
    )

    index = build_export_index([result_dir], validate=True)
    item = index["items"][0]

    assert index["validation_checked"] is True
    assert item["validation"]["checked"] is True
    assert item["validation"]["status"] == "valid"
    assert item["validation"]["errors"] == []


def test_detect_artifact_type_batch(tmp_path: Path) -> None:
    result_dir = tmp_path / "batch-a"
    result_dir.mkdir()
    (result_dir / "batch-summary.json").write_text("{}", encoding="utf-8")

    assert detect_artifact_type(result_dir) == "batch"


def test_build_export_index_for_batch(tmp_path: Path) -> None:
    result_dir = tmp_path / "batch-a"
    result_dir.mkdir()
    (result_dir / "batch-report.md").write_text("# Batch\n", encoding="utf-8")
    (result_dir / "batch-summary.json").write_text(
        """
{
  "schema_version": "llmgauge.batch_summary.v0",
  "batch_id": "batch-a",
  "manifest_path": "tmp/batch-a.yaml",
  "suite_id": "agent-backend-v1",
  "suite_path": "suites/agent-backend-v1",
  "include": "all",
  "only": "tool-honesty/fake-tool-resistance",
  "max_tokens": 300,
  "models": ["model-a", "model-b"],
  "execution": {
    "mode": "sequential",
    "model_reference_policy": "manifest model entries are model profile names only",
    "parallelism": "disabled"
  },
  "child_runs": [
    {
      "model_profile": "model-a",
      "model_id": "model-a",
      "status": "completed",
      "result_dir": "model-01-model-a",
      "completed": 1,
      "failed": 0,
      "error": null
    },
    {
      "model_profile": "model-b",
      "model_id": null,
      "status": "failed",
      "result_dir": "model-02-model-b",
      "completed": null,
      "failed": null,
      "error": "intentional test failure"
    }
  ],
  "summary": {
    "total": 2,
    "completed": 1,
    "failed": 1
  }
}
""".strip()
        + "\n",
        encoding="utf-8",
    )

    index = build_export_index([result_dir])
    item = index["items"][0]

    assert item["artifact_type"] == "batch"
    assert item["batch_id"] == "batch-a"
    assert item["suite_id"] == "agent-backend-v1"
    assert item["models"] == ["model-a", "model-b"]
    assert item["model_count"] == 2
    assert item["child_run_count"] == 2
    assert item["completed"] == 1
    assert item["failed"] == 1
    assert item["total"] == 2
    assert item["has_child_runs"] is True
    assert item["has_completed_child_runs"] is True
    assert item["has_failed_child_runs"] is True
    assert item["batch_report"] == str(result_dir / "batch-report.md")


def test_build_export_index_can_validate_batch(tmp_path: Path) -> None:
    result_dir = tmp_path / "batch-a"
    result_dir.mkdir()
    (result_dir / "batch-summary.json").write_text(
        """
{
  "schema_version": "llmgauge.batch_summary.v0",
  "batch_id": "batch-a",
  "manifest_path": "tmp/batch-a.yaml",
  "suite_id": "agent-backend-v1",
  "suite_path": "suites/agent-backend-v1",
  "include": "all",
  "only": null,
  "max_tokens": 300,
  "models": ["missing-model"],
  "execution": {
    "mode": "sequential",
    "model_reference_policy": "manifest model entries are model profile names only",
    "parallelism": "disabled"
  },
  "child_runs": [
    {
      "model_profile": "missing-model",
      "model_id": null,
      "status": "failed",
      "result_dir": "model-01-missing-model",
      "completed": null,
      "failed": null,
      "error": "intentional test failure"
    }
  ],
  "summary": {
    "total": 1,
    "completed": 0,
    "failed": 1
  }
}
""".strip()
        + "\n",
        encoding="utf-8",
    )

    index = build_export_index([result_dir], validate=True)
    item = index["items"][0]

    assert index["validation_checked"] is True
    assert item["validation"]["checked"] is True
    assert item["validation"]["status"] == "valid"
    assert item["validation"]["errors"] == []


def test_build_export_index_includes_scored_run_public_proof_metadata(
    tmp_path: Path,
) -> None:
    result_dir = tmp_path / "scored-run"
    result_dir.mkdir()
    (result_dir / "llmgauge-result.json").write_text(
        """
{
  "schema_version": "llmgauge.result.v0",
  "run": {
    "run_id": "scored-run",
    "timestamp_utc": "2026-06-23T02:25:51+00:00",
    "status": "completed"
  },
  "model": {
    "model_id": "test-model",
    "model_profile": "test-profile"
  },
  "suite": {
    "suite_id": "wumbolabs-practical-v1",
    "suite_version": "0.1.0",
    "prompt_count": 2
  },
  "summary": {
    "completed": 2,
    "failed": 0,
    "manual_score_total": 62.0,
    "manual_score_max": 80.0,
    "manual_score_average": 3.88,
    "scored_prompt_count": 2,
    "failure_labels": {
      "ignored_constraint": 1
    },
    "good_labels": {
      "strong_format_control": 1
    }
  },
  "results": [
    {
      "prompt_id": "prompt-a",
      "score": {
        "schema_version": "llmgauge.scores.v0",
        "rubric_id": "wumbolabs-practical-v1",
        "rubric_version": "0.1.0",
        "verdict": "pass",
        "prompt_average": 4.5,
        "failure_labels": [],
        "good_labels": ["strong_format_control"],
        "dimensions": {}
      }
    },
    {
      "prompt_id": "prompt-b",
      "score": {
        "schema_version": "llmgauge.scores.v0",
        "rubric_id": "wumbolabs-practical-v1",
        "rubric_version": "0.1.0",
        "verdict": "mixed",
        "prompt_average": 3.25,
        "failure_labels": ["ignored_constraint"],
        "good_labels": [],
        "dimensions": {}
      }
    }
  ]
}
""".strip()
        + "\n",
        encoding="utf-8",
    )

    index = build_export_index([result_dir])
    item = index["items"][0]

    assert item["scoring_status"] == "scored"
    assert item["scored_prompt_count"] == 2
    assert item["manual_score_average"] == 3.88
    assert item["failure_labels"] == {"ignored_constraint": 1}
    assert item["good_labels"] == {"strong_format_control": 1}
    assert item["verdict_counts"] == {"pass": 1, "mixed": 1}
    assert item["scoring_mode_counts"] == {"manual": 2}
    assert item["rubric_id"] == "wumbolabs-practical-v1"
    assert item["rubric_version"] == "0.1.0"
    assert item["score_schema_version"] == "llmgauge.scores.v0"


def test_build_export_index_marks_partially_scored_run(tmp_path: Path) -> None:
    result_dir = tmp_path / "partially-scored-run"
    result_dir.mkdir()
    (result_dir / "llmgauge-result.json").write_text(
        """
{
  "schema_version": "llmgauge.result.v0",
  "run": {
    "run_id": "partially-scored-run",
    "timestamp_utc": "2026-06-23T02:25:51+00:00",
    "status": "completed"
  },
  "model": {
    "model_id": "test-model",
    "model_profile": "test-profile"
  },
  "suite": {
    "suite_id": "wumbolabs-practical-v1",
    "suite_version": "0.1.0",
    "prompt_count": 2
  },
  "summary": {
    "completed": 2,
    "failed": 0,
    "manual_score_total": 20.0,
    "manual_score_max": 40.0
  },
  "results": [
    {
      "prompt_id": "prompt-a",
      "score": {
        "schema_version": "llmgauge.scores.v0",
        "rubric_id": "wumbolabs-practical-v1",
        "rubric_version": "0.1.0",
        "verdict": "fail",
        "prompt_average": 2.0,
        "failure_labels": [],
        "good_labels": [],
        "dimensions": {}
      }
    },
    {
      "prompt_id": "prompt-b",
      "score": null
    }
  ]
}
""".strip()
        + "\n",
        encoding="utf-8",
    )

    index = build_export_index([result_dir])
    item = index["items"][0]

    assert item["scoring_status"] == "partially_scored"
    assert item["scored_prompt_count"] == 1
    assert item["verdict_counts"] == {"fail": 1}
    assert item["scoring_mode_counts"] == {"manual": 1}


def test_build_export_index_marks_unscored_run(tmp_path: Path) -> None:
    result_dir = tmp_path / "unscored-run"
    result_dir.mkdir()
    (result_dir / "llmgauge-result.json").write_text(
        """
{
  "schema_version": "llmgauge.result.v0",
  "run": {
    "run_id": "unscored-run",
    "timestamp_utc": "2026-06-23T02:25:51+00:00",
    "status": "completed"
  },
  "model": {
    "model_id": "test-model",
    "model_profile": "test-profile"
  },
  "suite": {
    "suite_id": "wumbolabs-practical-v1",
    "suite_version": "0.1.0",
    "prompt_count": 1
  },
  "summary": {
    "completed": 1,
    "failed": 0,
    "manual_score_total": null,
    "manual_score_max": null
  },
  "results": [
    {
      "prompt_id": "prompt-a",
      "score": null
    }
  ]
}
""".strip()
        + "\n",
        encoding="utf-8",
    )

    index = build_export_index([result_dir])
    item = index["items"][0]

    assert item["scoring_status"] == "unscored"
    assert item["scored_prompt_count"] == 0
    assert item["manual_score_average"] is None
    assert item["failure_labels"] == {}
    assert item["good_labels"] == {}
    assert item["verdict_counts"] == {}
    assert item["scoring_mode_counts"] == {}
    assert item["rubric_id"] is None

def test_build_export_index_counts_explicit_scoring_modes(tmp_path: Path) -> None:
    result_dir = tmp_path / "scored-run"
    result_dir.mkdir()

    result_data = {
        "schema_version": "llmgauge.result.v0",
        "run": {
            "run_id": "scored-run",
            "status": "completed",
            "timestamp_utc": "2026-06-26T00:00:00Z",
        },
        "model": {"model_id": "model-a", "model_profile": "profile-a"},
        "runtime": {},
        "suite": {
            "suite_id": "core-v1",
            "suite_version": "0.1.0",
            "prompt_count": 2,
        },
        "summary": {
            "prompt_count": 2,
            "completed": 2,
            "failed": 0,
            "scored_prompt_count": 2,
            "manual_score_average": 4.0,
            "manual_score_total": 40.0,
            "manual_score_max": 50.0,
        },
        "results": [
            {
                "prompt_id": "prompt-a",
                "status": "completed",
                "score": {
                    "schema_version": "llmgauge.scores.v0",
                    "rubric_id": "default-manual-v0",
                    "rubric_version": "0.1.0",
                    "scoring_mode": "manual",
                    "verdict": "pass",
                },
            },
            {
                "prompt_id": "prompt-b",
                "status": "completed",
                "score": {
                    "schema_version": "llmgauge.scores.v0",
                    "rubric_id": "default-manual-v0",
                    "rubric_version": "0.1.0",
                    "scoring_mode": "automatic_rules",
                    "verdict": "needs_review",
                    "reviewed": False,
                },
            },
        ],
    }

    (result_dir / "llmgauge-result.json").write_text(
        json.dumps(result_data, indent=2) + "\n",
        encoding="utf-8",
    )

    index = build_export_index([result_dir])
    item = index["items"][0]

    assert item["scoring_mode_counts"] == {"manual": 1, "automatic_rules": 1}
    assert item["verdict_counts"] == {"pass": 1, "needs_review": 1}
    assert item["needs_review_verdict_count"] == 1
    assert item["unreviewed_score_count"] == 1


def test_build_export_index_marks_review_metadata_only_run(tmp_path: Path) -> None:
    result_dir = tmp_path / "metadata-only-run"
    result_dir.mkdir()
    (result_dir / "llmgauge-result.json").write_text(
        """
{
  "schema_version": "llmgauge.result.v0",
  "run": {
    "run_id": "metadata-only-run",
    "timestamp_utc": "2026-06-23T02:25:51+00:00",
    "status": "completed"
  },
  "model": {
    "model_id": "test-model",
    "model_profile": "test-profile"
  },
  "suite": {
    "suite_id": "core-v1",
    "suite_version": "0.1.0",
    "prompt_count": 1
  },
  "summary": {
    "completed": 1,
    "failed": 0,
    "manual_score_average": null
  },
  "results": [
    {
      "prompt_id": "prompt-a",
      "score": {
        "schema_version": "llmgauge.scores.v0",
        "rubric_id": "default-manual-v0",
        "rubric_version": "0.1.0",
        "verdict": "needs_review",
        "prompt_average": null,
        "score_rationale": "",
        "scoring_mode": "automatic_rules",
        "reviewed": false
      }
    }
  ]
}
""".strip()
        + "\n",
        encoding="utf-8",
    )

    index = build_export_index([result_dir])
    item = index["items"][0]

    assert item["scoring_status"] == "review_metadata_only"
    assert item["score_entry_count"] == 1
    assert item["scored_prompt_count"] == 0
    assert item["needs_review_verdict_count"] == 1
    assert item["unreviewed_score_count"] == 1
    assert item["missing_score_rationale_count"] == 1
