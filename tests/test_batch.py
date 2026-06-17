from pathlib import Path

import pytest

from llmgauge.core.batch import (
    build_batch_report,
    build_batch_summary,
    load_batch_manifest,
    write_batch_report,
    write_batch_summary,
)


def test_load_batch_manifest_normalizes_valid_manifest(tmp_path: Path) -> None:
    manifest = tmp_path / "batch.yaml"
    manifest.write_text(
        "\n".join(
            [
                "schema_version: llmgauge.batch_manifest.v0",
                "batch_id: gemma4-agent-smoke",
                "suite: agent-backend-v1",
                "only: tool-honesty/fake-tool-resistance",
                "include: all",
                "max_tokens: 300",
                "models:",
                "  - gemma4_12b_qat_q4",
                "  - gemma4_12b_q5",
                "",
            ]
        ),
        encoding="utf-8",
    )

    data = load_batch_manifest(manifest)

    assert data["schema_version"] == "llmgauge.batch_manifest.v0"
    assert data["batch_id"] == "gemma4-agent-smoke"
    assert data["suite"] == "agent-backend-v1"
    assert data["only"] == "tool-honesty/fake-tool-resistance"
    assert data["include"] == "all"
    assert data["max_tokens"] == 300
    assert data["models"] == ["gemma4_12b_qat_q4", "gemma4_12b_q5"]


def test_load_batch_manifest_uses_file_stem_as_default_batch_id(
    tmp_path: Path,
) -> None:
    manifest = tmp_path / "default-id.yaml"
    manifest.write_text(
        "\n".join(
            [
                "schema_version: llmgauge.batch_manifest.v0",
                "suite: agent-backend-v1",
                "models:",
                "  - gemma4_12b_qat_q4",
                "",
            ]
        ),
        encoding="utf-8",
    )

    data = load_batch_manifest(manifest)

    assert data["batch_id"] == "default-id"
    assert data["include"] == "all"
    assert data["only"] is None
    assert data["max_tokens"] is None


def test_load_batch_manifest_rejects_duplicate_models(tmp_path: Path) -> None:
    manifest = tmp_path / "duplicate-models.yaml"
    manifest.write_text(
        "\n".join(
            [
                "schema_version: llmgauge.batch_manifest.v0",
                "suite: agent-backend-v1",
                "models:",
                "  - gemma4_12b_qat_q4",
                "  - gemma4_12b_qat_q4",
                "",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="duplicate"):
        load_batch_manifest(manifest)


def test_load_batch_manifest_rejects_missing_models(tmp_path: Path) -> None:
    manifest = tmp_path / "missing-models.yaml"
    manifest.write_text(
        "\n".join(
            [
                "schema_version: llmgauge.batch_manifest.v0",
                "suite: agent-backend-v1",
                "",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="models"):
        load_batch_manifest(manifest)


def test_build_batch_summary_counts_child_runs() -> None:
    summary = build_batch_summary(
        batch_id="batch-test",
        suite_id="agent-backend-v1",
        suite_path="suites/agent-backend-v1",
        include="all",
        only="tool-honesty/fake-tool-resistance",
        max_tokens=300,
        models=["gemma4_12b_qat_q4", "gemma4_12b_q5"],
        manifest_path="examples/batches/batch-test.yaml",
        child_runs=[
            {
                "model_profile": "gemma4_12b_qat_q4",
                "model_id": "gemma4_12b_qat_q4",
                "status": "completed",
                "result_dir": "results/batch/model-01-gemma4-12b-qat-q4",
                "completed": 1,
                "failed": 0,
                "error": None,
            },
            {
                "model_profile": "gemma4_12b_q5",
                "model_id": None,
                "status": "failed",
                "result_dir": "results/batch/model-02-gemma4-12b-q5",
                "completed": None,
                "failed": None,
                "error": "example failure",
            },
        ],
    )

    assert summary["schema_version"] == "llmgauge.batch_summary.v0"
    assert summary["summary"]["completed"] == 1
    assert summary["summary"]["failed"] == 1
    assert summary["summary"]["total"] == 2
    assert summary["execution"]["mode"] == "sequential"


def test_build_batch_report() -> None:
    summary = build_batch_summary(
        batch_id="batch-test",
        suite_id="agent-backend-v1",
        suite_path="suites/agent-backend-v1",
        include="all",
        only=None,
        max_tokens=None,
        models=["gemma4_12b_qat_q4"],
        manifest_path="examples/batches/batch-test.yaml",
        child_runs=[
            {
                "model_profile": "gemma4_12b_qat_q4",
                "model_id": "gemma4_12b_qat_q4",
                "status": "completed",
                "result_dir": "results/batch/model-01-gemma4-12b-qat-q4",
                "completed": 1,
                "failed": 0,
                "error": None,
            }
        ],
    )

    report = build_batch_report(summary)

    assert "# LLMGauge Model Batch: batch-test" in report
    assert "| gemma4_12b_qat_q4 | gemma4_12b_qat_q4 | completed |" in report
    assert "Model batch runs are sequential" in report
    assert "Batch manifests do not accept arbitrary model paths" in report


def test_write_batch_artifacts(tmp_path: Path) -> None:
    summary = build_batch_summary(
        batch_id="batch-test",
        suite_id="agent-backend-v1",
        suite_path="suites/agent-backend-v1",
        include="all",
        only=None,
        max_tokens=None,
        models=["gemma4_12b_qat_q4"],
        manifest_path="examples/batches/batch-test.yaml",
        child_runs=[
            {
                "model_profile": "gemma4_12b_qat_q4",
                "model_id": "gemma4_12b_qat_q4",
                "status": "completed",
                "result_dir": "model-01-gemma4-12b-qat-q4",
                "completed": 1,
                "failed": 0,
                "error": None,
            }
        ],
    )

    summary_path = write_batch_summary(tmp_path, summary)
    report_path = write_batch_report(tmp_path, summary)

    assert summary_path.exists()
    assert report_path.exists()
