from __future__ import annotations

import json
from pathlib import Path

import pytest

from external_benchmark_fixtures import (
    official_arc_challenge_results,
    official_gsm8k_results,
    official_hellaswag_results,
    official_humaneval_results,
    official_mbpp_results,
    official_truthfulqa_mc2_results,
    official_winogrande_results,
    write_conflicting_humaneval_file,
    write_grouped_file,
    write_json,
    write_lookalike_mmlu_pro_file,
    write_nested_group_file,
    write_official_bundle1_file,
    write_official_humaneval_file,
    write_official_mmlu_file,
    write_single_task_file,
)
from llmgauge.core.agent_harness import require_native_result
from llmgauge.core.bundle1 import (
    BUNDLE1_MEMBERS,
    HARNESS_COMMIT,
    HARNESS_TAG,
    MMLU_SUBJECT_TASK_IDS,
    qualify_bundle1,
)
from llmgauge.core.compare import build_compare_report
from llmgauge.core.export_index import build_run_index_item
from llmgauge.core.external_benchmark import (
    EVIDENCE_RELATIVE_PATH,
    REPORT_RELATIVE_PATH,
    import_lm_eval_harness_results,
    load_external_benchmark_evidence,
)
from llmgauge.core.external_benchmark_report import (
    ExternalBenchmarkReportError,
    write_external_benchmark_report,
)
from llmgauge.core.public_export import export_public_run
from llmgauge.core.reports import build_markdown_report
from llmgauge.core.result_validation import validate_result_dir
from llmgauge.core.run_fingerprint import run_fingerprint_value
from llmgauge.core.scoring import build_score_template


def _read_result(result_dir: Path) -> dict:
    return json.loads((result_dir / "llmgauge-result.json").read_text(encoding="utf-8"))


def _read_evidence(result_dir: Path):
    result = _read_result(result_dir)
    return load_external_benchmark_evidence(
        result_dir, result["external_benchmark_evidence"]
    )


def _import(source: Path, destination: Path):
    import_lm_eval_harness_results(source, destination)
    return _read_evidence(destination)


def _member_status(qualification, member_id: str) -> str:
    return next(
        item.status for item in qualification.members if item.member_id == member_id
    )


def test_nested_official_group_shape_imports(tmp_path: Path) -> None:
    source = write_nested_group_file(tmp_path / "source")
    evidence = _import(source, tmp_path / "result")
    group_ids = {item.group_id for item in evidence.groups}
    task_ids = {item.task_id for item in evidence.tasks}
    assert group_ids == {"parent_group", "child_group"}
    assert task_ids == {"leaf_a", "leaf_b"}
    parent = next(item for item in evidence.groups if item.group_id == "parent_group")
    assert parent.subtask_ids == ["child_group"]
    assert all(item.metric_name != "sample_len" for item in parent.metrics)


def test_official_mmlu_group_qualifies(tmp_path: Path) -> None:
    source = write_official_mmlu_file(tmp_path / "source")
    evidence = _import(source, tmp_path / "result")
    assert {item.task_id for item in evidence.tasks} == set(MMLU_SUBJECT_TASK_IDS)
    qualification = qualify_bundle1(evidence)
    assert _member_status(qualification, "mmlu") == "qualified"
    assert all(
        _member_status(qualification, item.member_id) == "unqualified"
        for item in BUNDLE1_MEMBERS
        if item.member_id != "mmlu"
    )


def test_two_subject_mmlu_fixture_is_valid_but_not_qualified(tmp_path: Path) -> None:
    source = write_grouped_file(tmp_path / "source")
    evidence = _import(source, tmp_path / "result")
    assert validate_result_dir(tmp_path / "result") == []
    qualification = qualify_bundle1(evidence)
    assert _member_status(qualification, "mmlu") == "conflicting"
    assert qualification.overall_status == "conflicting"


def test_each_official_task_member_qualifies(tmp_path: Path) -> None:
    cases = {
        "arc_challenge": official_arc_challenge_results,
        "hellaswag": official_hellaswag_results,
        "winogrande": official_winogrande_results,
        "truthfulqa_mc2": official_truthfulqa_mc2_results,
        "gsm8k": official_gsm8k_results,
        "humaneval": official_humaneval_results,
        "mbpp": official_mbpp_results,
    }
    for member_id, builder in cases.items():
        source = write_json(tmp_path / member_id / "results.json", builder())
        evidence = _import(source, tmp_path / f"{member_id}-result")
        qualification = qualify_bundle1(evidence)
        assert _member_status(qualification, member_id) == "qualified", member_id
        assert qualification.overall_status == "unqualified"


def test_all_eight_bundle1_members_qualify_together(tmp_path: Path) -> None:
    source = write_official_bundle1_file(tmp_path / "source")
    evidence = _import(source, tmp_path / "result")
    qualification = qualify_bundle1(evidence)
    assert qualification.harness_tag == HARNESS_TAG
    assert qualification.harness_commit == HARNESS_COMMIT
    assert qualification.harness_pin_match == "matched"
    assert {item.member_id for item in qualification.members} == {
        item.member_id for item in BUNDLE1_MEMBERS
    }
    assert all(item.status == "qualified" for item in qualification.members)
    assert qualification.overall_status == "qualified"
    dumped = json.dumps(evidence.model_dump(mode="json"))
    assert "llmgauge.bundle1" not in dumped


def test_lookalike_identity_stays_unqualified(tmp_path: Path) -> None:
    source = write_lookalike_mmlu_pro_file(tmp_path / "source")
    evidence = _import(source, tmp_path / "result")
    qualification = qualify_bundle1(evidence)
    assert _member_status(qualification, "mmlu") == "unqualified"
    assert qualification.overall_status == "unqualified"


def test_conflicting_humaneval_identity(tmp_path: Path) -> None:
    source = write_conflicting_humaneval_file(tmp_path / "source")
    evidence = _import(source, tmp_path / "result")
    qualification = qualify_bundle1(evidence)
    assert _member_status(qualification, "humaneval") == "conflicting"
    assert qualification.overall_status == "conflicting"


def test_generic_hellaswag_import_is_not_bundle1_completion(tmp_path: Path) -> None:
    source = write_single_task_file(tmp_path / "source")
    evidence = _import(source, tmp_path / "result")
    qualification = qualify_bundle1(evidence)
    assert _member_status(qualification, "hellaswag") == "qualified"
    assert qualification.overall_status == "unqualified"
    assert any(item.status == "unqualified" for item in qualification.members)


def test_humaneval_import_and_report_do_not_execute_code(tmp_path: Path) -> None:
    source = write_official_humaneval_file(tmp_path / "source")
    destination = tmp_path / "result"
    evidence = _import(source, destination)
    path, qualification = write_external_benchmark_report(destination)
    report = path.read_text(encoding="utf-8")
    assert _member_status(qualification, "humaneval") == "qualified"
    assert evidence.tasks[0].task_id == "humaneval"
    assert "did not execute candidate code" in report
    assert "--confirm_run_unsafe_code" in report
    assert not any(destination.rglob("*.py"))


def test_report_writes_isolated_derivative(tmp_path: Path) -> None:
    source = write_official_bundle1_file(tmp_path / "source")
    destination = tmp_path / "result"
    import_lm_eval_harness_results(source, destination)
    before = _read_result(destination)
    first = run_fingerprint_value(destination, before)
    path, qualification = write_external_benchmark_report(destination)
    after = _read_result(destination)
    assert path == destination / REPORT_RELATIVE_PATH
    report = path.read_text(encoding="utf-8")
    assert qualification.overall_status == "qualified"
    assert "Bundle 1 qualification" in report
    assert "does not invent a universal score" in report
    assert "HumanEval" in report
    assert "MBPP" in report
    assert after["external_benchmark_evidence"] == before["external_benchmark_evidence"]
    assert run_fingerprint_value(destination, after) == first
    assert validate_result_dir(destination) == []


def test_report_rejects_tampered_evidence(tmp_path: Path) -> None:
    source = write_official_mmlu_file(tmp_path / "source")
    destination = tmp_path / "result"
    import_lm_eval_harness_results(source, destination)
    evidence_path = destination / EVIDENCE_RELATIVE_PATH
    data = json.loads(evidence_path.read_text(encoding="utf-8"))
    data["tasks"][0]["task_id"] = "tampered"
    encoded = (
        json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode("utf-8")
    evidence_path.write_bytes(encoded)
    with pytest.raises(ExternalBenchmarkReportError):
        write_external_benchmark_report(destination)
    assert not (destination / REPORT_RELATIVE_PATH).exists()


def test_report_rejects_native_result(tmp_path: Path) -> None:
    result_dir = tmp_path / "native"
    result_dir.mkdir()
    (result_dir / "llmgauge-result.json").write_text(
        json.dumps({"schema_version": "llmgauge.result.v0", "results": []}) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ExternalBenchmarkReportError, match="not imported"):
        write_external_benchmark_report(result_dir)


def test_native_consumers_still_reject_external_results(tmp_path: Path) -> None:
    source = write_official_bundle1_file(tmp_path / "source")
    destination = tmp_path / "result"
    import_lm_eval_harness_results(source, destination)
    write_external_benchmark_report(destination)
    result = _read_result(destination)
    with pytest.raises(ValueError, match="benchmark report"):
        require_native_result(result, consumer="Native report generation")
    with pytest.raises(ValueError, match="external benchmark"):
        build_score_template(result)
    with pytest.raises(ValueError, match="external benchmark"):
        build_markdown_report(result)
    with pytest.raises(ValueError, match="external benchmark"):
        build_compare_report([result, result])
    with pytest.raises(ValueError, match="external benchmark"):
        build_run_index_item(destination)
    with pytest.raises(ValueError, match="external benchmark"):
        export_public_run(destination, tmp_path / "public")
    assert not (tmp_path / "public").exists()
