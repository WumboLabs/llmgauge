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


def test_detect_artifact_type_rejects_unknown(tmp_path: Path) -> None:
    result_dir = tmp_path / "unknown"
    result_dir.mkdir()

    with pytest.raises(ValueError, match="unsupported artifact path"):
        detect_artifact_type(result_dir)


def test_build_export_index_for_run(tmp_path: Path) -> None:
    result_dir = tmp_path / "run-a"
    result_dir.mkdir()
    (result_dir / "raw").mkdir()
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
