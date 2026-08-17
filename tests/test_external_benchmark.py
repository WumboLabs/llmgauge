from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from external_benchmark_fixtures import (
    single_task_results,
    write_grouped_file,
    write_json,
    write_malformed_metrics_file,
    write_missing_optional_file,
    write_multi_task_tree,
    write_single_task_file,
    write_unsafe_tree,
)
from llmgauge.core.agent_harness import require_native_result
from llmgauge.core.compare import build_compare_report
from llmgauge.core.export_index import build_run_index_item
from llmgauge.core.external_benchmark import (
    EVIDENCE_RELATIVE_PATH,
    EVIDENCE_SCHEMA_VERSION,
    SOURCE_RELATIVE_DIR,
    SOURCE_TYPE,
    ExternalBenchmarkEvidence,
    ExternalBenchmarkImportError,
    evidence_identity,
    immutable_external_benchmark_payload,
    import_lm_eval_harness_results,
    load_external_benchmark_evidence,
    source_package_sha256,
)
from llmgauge.core.public_export import export_public_run
from llmgauge.core.reports import build_markdown_report
from llmgauge.core.result_validation import validate_result_dir
from llmgauge.core.run_fingerprint import (
    RUN_FINGERPRINT_SCHEMA_VERSION,
    RUN_FINGERPRINT_SCHEMA_VERSION_V2,
    attach_run_fingerprint,
    build_run_fingerprint_payload,
    run_fingerprint_value,
    verify_run_fingerprint,
)
from llmgauge.core.scoring import build_score_template
from test_run_fingerprint import _write_fingerprintable_run


def _read_result(result_dir: Path) -> dict[str, Any]:
    return json.loads((result_dir / "llmgauge-result.json").read_text(encoding="utf-8"))


def _read_evidence(result_dir: Path) -> ExternalBenchmarkEvidence:
    result = _read_result(result_dir)
    return load_external_benchmark_evidence(
        result_dir, result["external_benchmark_evidence"]
    )


def _rewrite_evidence(result_dir: Path, mutate) -> dict[str, Any]:
    evidence_path = result_dir / EVIDENCE_RELATIVE_PATH
    data = json.loads(evidence_path.read_text(encoding="utf-8"))
    mutate(data)
    encoded = (
        json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode("utf-8")
    evidence_path.write_bytes(encoded)
    result = _read_result(result_dir)
    result["external_benchmark_evidence"]["sha256"] = hashlib.sha256(
        encoded
    ).hexdigest()
    (result_dir / "llmgauge-result.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return result


def test_import_single_task_file(tmp_path: Path) -> None:
    source = write_single_task_file(tmp_path / "source")
    destination = tmp_path / "result"

    outcome = import_lm_eval_harness_results(source, destination)

    assert outcome.outcome == "completed"
    evidence = _read_evidence(destination)
    assert evidence.schema_version == EVIDENCE_SCHEMA_VERSION
    assert evidence.source_type == SOURCE_TYPE
    assert evidence.evaluation_class == "external_text_benchmark"
    assert [task.task_id for task in evidence.tasks] == ["hellaswag"]
    metric_names = [item.metric_name for item in evidence.tasks[0].metrics]
    assert metric_names == ["acc,none", "acc_norm,none"]
    acc = next(
        item for item in evidence.tasks[0].metrics if item.metric_name == "acc,none"
    )
    assert acc.value == 0.85
    assert acc.stderr.value == 0.01
    assert acc.higher_is_better.value is True
    assert evidence.model.hf_id.value == "org/demo-model"
    assert evidence.harness.version.value == "0.4.8"
    assert (destination / SOURCE_RELATIVE_DIR / "results.json").is_file()
    assert (
        source.read_bytes()
        == (destination / SOURCE_RELATIVE_DIR / "results.json").read_bytes()
    )
    assert validate_result_dir(destination) == []


def test_import_preserves_source_bytes(tmp_path: Path) -> None:
    source = write_single_task_file(tmp_path / "source")
    original = source.read_bytes()
    destination = tmp_path / "result"

    import_lm_eval_harness_results(source, destination)

    assert source.read_bytes() == original


def test_import_multi_task_tree(tmp_path: Path) -> None:
    source = write_multi_task_tree(tmp_path / "source")
    destination = tmp_path / "result"

    import_lm_eval_harness_results(source, destination)

    evidence = _read_evidence(destination)
    assert {task.task_id for task in evidence.tasks} == {
        "arc_challenge",
        "gsm8k",
        "hellaswag",
        "humaneval",
    }
    humaneval = next(task for task in evidence.tasks if task.task_id == "humaneval")
    assert [item.metric_name for item in humaneval.metrics] == ["pass_at_1,none"]
    gsm8k = next(task for task in evidence.tasks if task.task_id == "gsm8k")
    assert gsm8k.metrics[0].metric_name == "exact_match,flexible-extract"
    roles = {item.role for item in evidence.source_inventory}
    assert roles == {"results_json", "config", "log", "samples"}
    assert validate_result_dir(destination) == []


def test_import_grouped_native_aggregation(tmp_path: Path) -> None:
    source = write_grouped_file(tmp_path / "source")
    destination = tmp_path / "result"

    import_lm_eval_harness_results(source, destination)

    evidence = _read_evidence(destination)
    assert [task.task_id for task in evidence.tasks] == [
        "mmlu_abstract_algebra",
        "mmlu_anatomy",
    ]
    assert [group.group_id for group in evidence.groups] == ["mmlu"]
    assert evidence.groups[0].metrics[0].metric_name == "acc,none"
    assert evidence.groups[0].metrics[0].value == 0.43
    assert evidence.groups[0].subtask_ids == ["mmlu_abstract_algebra", "mmlu_anatomy"]


def test_import_missing_optional_provenance(tmp_path: Path) -> None:
    source = write_missing_optional_file(tmp_path / "source")
    destination = tmp_path / "result"

    import_lm_eval_harness_results(source, destination)

    evidence = _read_evidence(destination)
    assert evidence.harness.version.availability == "absent"
    assert evidence.model.hf_id.availability == "absent"
    assert evidence.seeds.random_seed.availability == "absent"
    assert evidence.tasks[0].n_shot.availability == "absent"
    assert evidence.tasks[0].dataset_path.availability == "absent"
    assert validate_result_dir(destination) == []


def test_import_does_not_invent_hf_id_from_path(tmp_path: Path) -> None:
    payload = single_task_results()
    payload["model_name"] = "/models/demo.gguf"
    payload["model_source"] = "local"
    source = write_json(tmp_path / "source" / "results.json", payload)
    destination = tmp_path / "result"

    import_lm_eval_harness_results(source, destination)

    evidence = _read_evidence(destination)
    assert evidence.model.model_name.value == "/models/demo.gguf"
    assert evidence.model.hf_id.availability == "absent"


def test_malformed_metrics_fail_closed(tmp_path: Path) -> None:
    source = write_malformed_metrics_file(tmp_path / "source")
    destination = tmp_path / "result"

    with pytest.raises(ExternalBenchmarkImportError, match="malformed") as exc:
        import_lm_eval_harness_results(source, destination)

    assert exc.value.outcome == "malformed_source"
    assert not destination.exists()


def test_unsafe_symlink_tree_fails_closed(tmp_path: Path) -> None:
    source = write_unsafe_tree(tmp_path / "source")
    destination = tmp_path / "result"

    with pytest.raises(ExternalBenchmarkImportError, match="symlink"):
        import_lm_eval_harness_results(source, destination)
    assert not destination.exists()


def test_llmgauge_result_is_unsupported_source(tmp_path: Path) -> None:
    source = write_json(
        tmp_path / "source.json",
        {
            "schema_version": "llmgauge.result.v0",
            "results": {"ignored": {"acc,none": 1.0}},
        },
    )
    destination = tmp_path / "result"

    with pytest.raises(ExternalBenchmarkImportError, match="LLMGauge artifact") as exc:
        import_lm_eval_harness_results(source, destination)
    assert exc.value.outcome == "unsupported_source"


def test_shard_trace_is_unsupported_source(tmp_path: Path) -> None:
    source = write_json(
        tmp_path / "source.json",
        {"question_id": "q1", "results": [{"score": 1}]},
    )
    destination = tmp_path / "result"

    with pytest.raises(ExternalBenchmarkImportError, match="lm_eval_harness_results"):
        import_lm_eval_harness_results(source, destination)


def test_conflicting_results_json_fails(tmp_path: Path) -> None:
    write_json(tmp_path / "source" / "results.json", single_task_results())
    write_json(tmp_path / "source" / "results_other.json", single_task_results())
    destination = tmp_path / "result"

    with pytest.raises(ExternalBenchmarkImportError, match="conflicting results JSON"):
        import_lm_eval_harness_results(tmp_path / "source", destination)


def test_identical_reimport_is_unchanged(tmp_path: Path) -> None:
    source = write_single_task_file(tmp_path / "source")
    destination = tmp_path / "result"
    first = import_lm_eval_harness_results(source, destination)
    second = import_lm_eval_harness_results(source, destination)

    assert first.outcome == "completed"
    assert second.outcome == "already_imported"
    assert first.evidence_id == second.evidence_id


def test_conflicting_destination_fails(tmp_path: Path) -> None:
    source = write_single_task_file(tmp_path / "source")
    destination = tmp_path / "result"
    destination.mkdir()
    sentinel = destination / "keep.txt"
    sentinel.write_text("unchanged", encoding="utf-8")

    with pytest.raises(ExternalBenchmarkImportError, match="conflicting"):
        import_lm_eval_harness_results(source, destination)
    assert sentinel.read_text(encoding="utf-8") == "unchanged"


def test_dry_run_writes_nothing(tmp_path: Path) -> None:
    source = write_single_task_file(tmp_path / "source")
    destination = tmp_path / "result"

    outcome = import_lm_eval_harness_results(source, destination, dry_run=True)

    assert outcome.outcome == "dry_run"
    assert not destination.exists()
    assert not list(tmp_path.glob(".result.external-benchmark-import-*"))


def test_source_integrity_tamper_is_detected(tmp_path: Path) -> None:
    source = write_single_task_file(tmp_path / "source")
    destination = tmp_path / "result"
    import_lm_eval_harness_results(source, destination)
    contained = destination / SOURCE_RELATIVE_DIR / "results.json"
    payload = json.loads(contained.read_text(encoding="utf-8"))
    payload["results"]["hellaswag"]["acc,none"] = 0.01
    contained.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    errors = validate_result_dir(destination)
    assert any("hash mismatch" in item or "disagrees" in item for item in errors)


def test_normalized_metric_tamper_is_detected(tmp_path: Path) -> None:
    source = write_single_task_file(tmp_path / "source")
    destination = tmp_path / "result"
    import_lm_eval_harness_results(source, destination)

    def mutate(data: dict[str, Any]) -> None:
        data["tasks"][0]["metrics"][0]["value"] = 0.01
        data["evidence_id"] = evidence_identity(
            ExternalBenchmarkEvidence.model_validate(data)
        )

    result = _rewrite_evidence(destination, mutate)
    result["external_benchmark_evidence"]["evidence_id"] = json.loads(
        (destination / EVIDENCE_RELATIVE_PATH).read_text(encoding="utf-8")
    )["evidence_id"]
    (destination / "llmgauge-result.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    errors = validate_result_dir(destination)
    assert any("disagrees" in item or "evidence_id" in item for item in errors)


def test_mixed_agent_harness_reference_is_rejected(tmp_path: Path) -> None:
    source = write_single_task_file(tmp_path / "source")
    destination = tmp_path / "result"
    import_lm_eval_harness_results(source, destination)
    result = _read_result(destination)
    result["agent_harness_evidence"] = {
        "schema_version": "llmgauge.agent_harness_evidence.v0",
        "contract_version": "0.1.0",
        "evidence_class": "external_agent_environment",
        "evidence_id": "sha256:" + "a" * 64,
        "path": "agent-harness/evidence.json",
        "sha256": "b" * 64,
    }
    (destination / "llmgauge-result.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    errors = validate_result_dir(destination)
    assert any("Agent Harness" in item for item in errors)


def test_native_prompt_results_cannot_mix(tmp_path: Path) -> None:
    source = write_single_task_file(tmp_path / "source")
    destination = tmp_path / "result"
    import_lm_eval_harness_results(source, destination)
    result = _read_result(destination)
    result["results"] = [
        {
            "prompt_id": "prompt",
            "category": "honesty",
            "status": "completed",
            "raw_prompt_path": "raw/prompt.prompt.md",
            "raw_output_path": "raw/prompt.output.txt",
            "stderr_log_path": "logs/prompt.stderr.log",
            "exit_status": 0,
            "metrics": {},
        }
    ]
    (destination / "llmgauge-result.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    errors = validate_result_dir(destination)
    assert any("empty native results" in item for item in errors)


def test_fingerprint_is_v2_and_stable(tmp_path: Path) -> None:
    source = write_single_task_file(tmp_path / "source")
    destination = tmp_path / "result"
    import_lm_eval_harness_results(source, destination)
    result = _read_result(destination)
    fingerprint = result["run_fingerprint"]
    assert fingerprint["schema_version"] == RUN_FINGERPRINT_SCHEMA_VERSION_V2
    assert verify_run_fingerprint(destination, result) == []
    payload = build_run_fingerprint_payload(destination, result)
    assert payload["external_benchmark_evidence"]["source_type"] == SOURCE_TYPE
    assert "imported_at" not in json.dumps(payload)
    first = run_fingerprint_value(destination, result)
    result["run"]["timestamp_utc"] = "1999-01-01T00:00:00+00:00"
    assert run_fingerprint_value(destination, result) == first


def test_historical_v0_fingerprint_still_verifies(tmp_path: Path) -> None:
    result_dir, result = _write_fingerprintable_run(tmp_path)
    attach_run_fingerprint(result_dir, result)
    assert result["run_fingerprint"]["schema_version"] == RUN_FINGERPRINT_SCHEMA_VERSION
    (result_dir / "llmgauge-result.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    assert validate_result_dir(result_dir) == []
    assert verify_run_fingerprint(result_dir, result) == []


def test_legacy_native_result_remains_valid(tmp_path: Path) -> None:
    result_dir, result = _write_fingerprintable_run(tmp_path)
    (result_dir / "llmgauge-result.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    assert validate_result_dir(result_dir) == []


def test_native_consumers_reject_imported_benchmark(tmp_path: Path) -> None:
    source = write_single_task_file(tmp_path / "source")
    destination = tmp_path / "result"
    import_lm_eval_harness_results(source, destination)
    result = _read_result(destination)

    with pytest.raises(ValueError, match="external benchmark"):
        require_native_result(result, consumer="Native scoring")
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


def test_source_package_digest_uses_contract_projection(tmp_path: Path) -> None:
    source = write_single_task_file(tmp_path / "source")
    destination = tmp_path / "result"
    import_lm_eval_harness_results(source, destination)
    evidence = _read_evidence(destination)
    assert evidence.source_package_sha256 == source_package_sha256(
        evidence.source_inventory
    )
    payload = immutable_external_benchmark_payload(evidence)
    assert (
        payload["source_members"][0]["byte_count"]
        == evidence.source_inventory[0].byte_count
    )
    assert "imported_at" not in payload


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "external_benchmark"


def test_repository_fixtures_cover_supported_and_malformed_shapes(
    tmp_path: Path,
) -> None:
    good = import_lm_eval_harness_results(
        FIXTURE_DIR / "single_task_results.json",
        tmp_path / "single",
    )
    missing = import_lm_eval_harness_results(
        FIXTURE_DIR / "missing_optional_results.json",
        tmp_path / "missing",
    )
    assert good.outcome == "completed"
    assert missing.outcome == "completed"
    assert _read_evidence(tmp_path / "missing").harness.version.availability == "absent"
    with pytest.raises(ExternalBenchmarkImportError, match="malformed"):
        import_lm_eval_harness_results(
            FIXTURE_DIR / "malformed_metrics.json",
            tmp_path / "bad",
        )
