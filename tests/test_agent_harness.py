from __future__ import annotations

import copy
import hashlib
import json
import os
import socket
import subprocess
from pathlib import Path
from typing import Any

import pytest

import llmgauge.core.agent_harness as agent_harness
from agent_harness_fixtures import (
    add_blob_reference,
    completed_records,
    write_session,
    write_synthetic_omp_session,
)
from llmgauge.core.agent_harness import (
    EVIDENCE_RELATIVE_PATH,
    MAX_OBJECT_BYTES,
    OBJECTS_RELATIVE_DIR,
    SESSION_RELATIVE_PATH,
    AgentHarnessEvidence,
    AgentHarnessImportError,
    evidence_identity,
    immutable_mapping_projection,
    import_agent_harness_session,
    load_agent_harness_evidence,
)
from llmgauge.core.compare import build_compare_report
from llmgauge.core.export_index import build_run_index_item
from llmgauge.core.public_export import export_public_run
from llmgauge.core.reports import build_markdown_report
from llmgauge.core.result_validation import validate_result_dir
from llmgauge.core.run_fingerprint import (
    attach_run_fingerprint,
    build_run_fingerprint_payload,
    run_fingerprint_value,
)
from llmgauge.core.scoring import build_score_template
from test_run_fingerprint import _write_fingerprintable_run


def _read_result(result_dir: Path) -> dict[str, Any]:
    return json.loads((result_dir / "llmgauge-result.json").read_text(encoding="utf-8"))


def _read_evidence(result_dir: Path) -> AgentHarnessEvidence:
    result = _read_result(result_dir)
    return load_agent_harness_evidence(result_dir, result["agent_harness_evidence"])


def _rewrite_evidence(
    result_dir: Path,
    mutate,
    *,
    recompute_identity: bool = False,
) -> dict[str, Any]:
    evidence_path = result_dir / EVIDENCE_RELATIVE_PATH
    data = json.loads(evidence_path.read_text(encoding="utf-8"))
    mutate(data)
    if recompute_identity:
        evidence = AgentHarnessEvidence.model_validate(data)
        evidence.evidence_id = evidence_identity(evidence)
        data = evidence.model_dump(mode="json")
    encoded = (
        json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode("utf-8")
    evidence_path.write_bytes(encoded)
    result = _read_result(result_dir)
    result["agent_harness_evidence"]["sha256"] = hashlib.sha256(encoded).hexdigest()
    if recompute_identity:
        result["agent_harness_evidence"]["evidence_id"] = data["evidence_id"]
    (result_dir / "llmgauge-result.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return result


_MISSING = object()


def _records_with_model_change(
    resolved_model_is_fallback: object = _MISSING,
    *,
    extra_fields: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    records = completed_records()
    model_change: dict[str, Any] = {
        "type": "model_change",
        "id": "model-change-1",
        "parentId": "e001",
        "timestamp": "2026-08-12T00:00:01.500Z",
        "model": "synthetic-model",
        "role": "default",
    }
    if resolved_model_is_fallback is not _MISSING:
        model_change["resolvedModelIsFallback"] = resolved_model_is_fallback
    if extra_fields:
        model_change.update(extra_fields)
    return [records[0], model_change, *records[1:]]


def test_valid_import_is_self_contained_and_structurally_valid(tmp_path: Path) -> None:
    synthetic = write_synthetic_omp_session(tmp_path / "source", physical_title=True)
    source_bytes = synthetic.source.read_bytes()
    result_dir = tmp_path / "result"

    outcome = import_agent_harness_session(synthetic.source, result_dir)

    assert outcome.outcome == "completed"
    assert (result_dir / SESSION_RELATIVE_PATH).read_bytes() == source_bytes
    assert validate_result_dir(result_dir) == []
    result = _read_result(result_dir)
    evidence = _read_evidence(result_dir)
    assert result["results"] == []
    assert result["runtime"] == {}
    assert result["suite"] == {}
    assert "transcript" not in result
    assert not (result_dir / "report.md").exists()
    assert evidence.schema_version == "llmgauge.agent_harness_evidence.v0"
    assert evidence.contract_version == "0.1.0"
    assert evidence.source.source_format_version == 3
    assert evidence.source_session_outcome == "unknown"
    assert evidence.source_completeness == "complete"
    assert evidence.tool_lifecycles[0].lifecycle_state == "completed"
    assert evidence.tool_lifecycles[0].output_complete is True
    assert all(event.kind != "assistant_final_answer" for event in evidence.trajectory)
    assert "stdout" not in json.dumps(evidence.model_dump(mode="json"))
    assert "stderr" not in json.dumps(evidence.model_dump(mode="json"))


@pytest.mark.parametrize(
    ("fallback_value", "expected_value"),
    [(_MISSING, None), (False, False), (True, True)],
    ids=["omitted", "false", "true"],
)
def test_model_change_fallback_fact_is_optional_and_preserved(
    tmp_path: Path,
    fallback_value: object,
    expected_value: bool | None,
) -> None:
    source = write_session(
        tmp_path / "source",
        _records_with_model_change(fallback_value),
    )
    result_dir = tmp_path / "result"

    import_agent_harness_session(source, result_dir)

    assert validate_result_dir(result_dir) == []
    evidence = _read_evidence(result_dir)
    observation = next(
        item
        for item in evidence.model_observations
        if item.source_entry_id == "model-change-1"
    )
    evidence_data = json.loads(
        (result_dir / EVIDENCE_RELATIVE_PATH).read_text(encoding="utf-8")
    )
    normalized = next(
        item
        for item in evidence_data["model_observations"]
        if item["source_entry_id"] == "model-change-1"
    )
    if expected_value is None:
        assert observation.resolved_model_is_fallback is None
        assert "resolved_model_is_fallback" not in normalized
    else:
        assert observation.resolved_model_is_fallback is not None
        assert observation.resolved_model_is_fallback.availability == "available"
        assert observation.resolved_model_is_fallback.value is expected_value
        assert (
            observation.resolved_model_is_fallback.source_entry_id == "model-change-1"
        )
        assert normalized["resolved_model_is_fallback"] == {
            "availability": "available",
            "source_entry_id": "model-change-1",
            "value": expected_value,
        }


@pytest.mark.parametrize(
    "fallback_value",
    ["false", 0, 1, None, {}, []],
    ids=["string", "integer-zero", "integer-one", "null", "object", "array"],
)
def test_model_change_fallback_fact_rejects_non_booleans(
    tmp_path: Path, fallback_value: object
) -> None:
    source = write_session(
        tmp_path / "source",
        _records_with_model_change(fallback_value),
    )

    with pytest.raises(AgentHarnessImportError) as captured:
        import_agent_harness_session(source, tmp_path / "result")

    assert captured.value.outcome == "malformed_source"
    assert not (tmp_path / "result").exists()


def test_model_change_fallback_fact_keeps_unknown_fields_fail_closed(
    tmp_path: Path,
) -> None:
    source = write_session(
        tmp_path / "source",
        _records_with_model_change(
            False,
            extra_fields={"unsupportedFutureField": False},
        ),
    )

    with pytest.raises(AgentHarnessImportError) as captured:
        import_agent_harness_session(source, tmp_path / "result")

    assert captured.value.outcome == "unsupported_source"
    assert not (tmp_path / "result").exists()


def test_model_change_fallback_fact_binds_normalized_identity(
    tmp_path: Path,
) -> None:
    false_source_one = write_session(
        tmp_path / "false-source-one",
        _records_with_model_change(False),
    )
    false_source_two = write_session(
        tmp_path / "false-source-two",
        _records_with_model_change(False),
    )
    true_source = write_session(
        tmp_path / "true-source",
        _records_with_model_change(True),
    )
    omitted_source = write_session(
        tmp_path / "omitted-source",
        _records_with_model_change(),
    )
    result_dirs = {
        "false_one": tmp_path / "false-result-one",
        "false_two": tmp_path / "false-result-two",
        "true": tmp_path / "true-result",
        "omitted": tmp_path / "omitted-result",
    }
    for source, result_dir in (
        (false_source_one, result_dirs["false_one"]),
        (false_source_two, result_dirs["false_two"]),
        (true_source, result_dirs["true"]),
        (omitted_source, result_dirs["omitted"]),
    ):
        import_agent_harness_session(source, result_dir)

    false_one = _read_evidence(result_dirs["false_one"])
    false_two = _read_evidence(result_dirs["false_two"])
    true = _read_evidence(result_dirs["true"])
    omitted = _read_evidence(result_dirs["omitted"])
    assert false_one.imported_session_id == false_two.imported_session_id
    assert false_one.evidence_id == false_two.evidence_id
    assert run_fingerprint_value(
        result_dirs["false_one"], _read_result(result_dirs["false_one"])
    ) == run_fingerprint_value(
        result_dirs["false_two"], _read_result(result_dirs["false_two"])
    )

    false_mapping = immutable_mapping_projection(false_one)
    false_observation = next(
        item
        for item in false_mapping["model_observations"]
        if item["source_entry_id"] == "model-change-1"
    )
    omitted_mapping = immutable_mapping_projection(omitted)
    omitted_observation = next(
        item
        for item in omitted_mapping["model_observations"]
        if item["source_entry_id"] == "model-change-1"
    )
    assert false_observation["resolved_model_is_fallback"]["value"] is False
    assert "resolved_model_is_fallback" not in omitted_observation

    assert false_one.imported_session_id != true.imported_session_id
    assert false_one.evidence_id != true.evidence_id
    assert false_one.evidence_id != omitted.evidence_id
    assert run_fingerprint_value(
        result_dirs["false_one"], _read_result(result_dirs["false_one"])
    ) != run_fingerprint_value(result_dirs["true"], _read_result(result_dirs["true"]))

    changed_mapping = false_one.model_copy(deep=True)
    changed_observation = next(
        item
        for item in changed_mapping.model_observations
        if item.source_entry_id == "model-change-1"
    )
    assert changed_observation.resolved_model_is_fallback is not None
    changed_observation.resolved_model_is_fallback.value = True
    assert evidence_identity(changed_mapping) != false_one.evidence_id


@pytest.mark.parametrize("version", [1, 2, 4, None, "3"])
def test_only_exact_integer_omp_v3_is_admitted(
    tmp_path: Path, version: int | str | None
) -> None:
    source = write_session(tmp_path / "source", completed_records(), version=version)

    with pytest.raises(AgentHarnessImportError) as captured:
        import_agent_harness_session(source, tmp_path / "result")

    assert captured.value.outcome == "unsupported_source"
    assert not (tmp_path / "result").exists()


def test_malformed_jsonl_and_duplicate_keys_are_rejected(tmp_path: Path) -> None:
    malformed = tmp_path / "malformed.jsonl"
    malformed.write_text('{"type":"session","version":3\n', encoding="utf-8")
    duplicate = tmp_path / "duplicate.jsonl"
    duplicate.write_text(
        '{"type":"session","version":3,"id":"a","id":"b",'
        '"timestamp":"2026-08-12T00:00:00Z","cwd":"/synthetic"}\n',
        encoding="utf-8",
    )

    for source in (malformed, duplicate):
        with pytest.raises(AgentHarnessImportError) as captured:
            import_agent_harness_session(source, tmp_path / f"result-{source.stem}")
        assert captured.value.outcome == "malformed_source"


def test_malformed_required_record_and_unknown_entry_are_rejected(
    tmp_path: Path,
) -> None:
    malformed_records = completed_records()
    del malformed_records[1]["message"]["role"]
    malformed = write_session(tmp_path / "malformed", malformed_records)
    unknown_records = completed_records()
    unknown_records[1]["type"] = "future_required_entry"
    unknown = write_session(tmp_path / "unknown", unknown_records)

    for source in (malformed, unknown):
        with pytest.raises(AgentHarnessImportError):
            import_agent_harness_session(
                source, tmp_path / f"result-{source.parent.name}"
            )


def test_session_and_referenced_artifact_bytes_are_preserved(tmp_path: Path) -> None:
    synthetic = write_synthetic_omp_session(tmp_path / "source", "referenced_object")
    source_bytes = synthetic.source.read_bytes()
    result_dir = tmp_path / "result"

    import_agent_harness_session(synthetic.source, result_dir)

    evidence = _read_evidence(result_dir)
    object_members = [
        item for item in evidence.source_inventory if item.role == "source_object"
    ]
    assert len(object_members) == 1
    member = object_members[0]
    assert member.path == f"{OBJECTS_RELATIVE_DIR}/{member.sha256}"
    assert (result_dir / member.path).read_bytes() == synthetic.referenced_bytes
    assert (result_dir / SESSION_RELATIVE_PATH).read_bytes() == source_bytes
    assert evidence.tool_lifecycles[0].full_output_member_id == member.member_id
    assert evidence.tool_lifecycles[0].output_complete is True


def test_blob_reference_requires_explicit_root_and_preserves_bytes(
    tmp_path: Path,
) -> None:
    synthetic = add_blob_reference(tmp_path / "source", completed_records())
    with pytest.raises(AgentHarnessImportError):
        import_agent_harness_session(synthetic.source, tmp_path / "missing-root")

    result_dir = tmp_path / "result"
    import_agent_harness_session(
        synthetic.source, result_dir, blob_dir=synthetic.blob_dir
    )

    evidence = _read_evidence(result_dir)
    member = next(
        item for item in evidence.source_inventory if item.role == "source_object"
    )
    assert (result_dir / member.path).read_bytes() == synthetic.referenced_bytes
    assert evidence.source_references[0].declared_sha256 == member.sha256


def test_source_package_and_evidence_identity_are_location_independent(
    tmp_path: Path,
) -> None:
    first_source = write_synthetic_omp_session(tmp_path / "one" / "source").source
    second_source = write_synthetic_omp_session(tmp_path / "two" / "source").source
    first_result = tmp_path / "first-result"
    second_result = tmp_path / "second-result"

    import_agent_harness_session(first_source, first_result)
    import_agent_harness_session(second_source, second_result)

    first = _read_evidence(first_result)
    second = _read_evidence(second_result)
    assert first.source_package_sha256 == second.source_package_sha256
    assert first.imported_session_id == second.imported_session_id
    assert first.evidence_id == second.evidence_id
    assert run_fingerprint_value(first_result, _read_result(first_result)) == (
        run_fingerprint_value(second_result, _read_result(second_result))
    )


@pytest.mark.parametrize(
    ("constant", "value"),
    [
        ("MAX_SESSION_BYTES", 64),
        ("MAX_JSONL_LINE_BYTES", 32),
        ("MAX_EVENT_COUNT", 1),
    ],
)
def test_session_line_and_event_bounds_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, constant: str, value: int
) -> None:
    source = write_synthetic_omp_session(tmp_path / "source").source
    monkeypatch.setattr(agent_harness, constant, value)

    with pytest.raises(AgentHarnessImportError):
        import_agent_harness_session(source, tmp_path / "result")

    assert not (tmp_path / "result").exists()


def test_object_count_individual_and_total_bounds_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    count_source = add_blob_reference(tmp_path / "count", completed_records())
    monkeypatch.setattr(agent_harness, "MAX_REFERENCED_OBJECTS", 0)
    with pytest.raises(AgentHarnessImportError):
        import_agent_harness_session(
            count_source.source,
            tmp_path / "count-result",
            blob_dir=count_source.blob_dir,
        )

    monkeypatch.setattr(agent_harness, "MAX_REFERENCED_OBJECTS", 256)
    object_source = add_blob_reference(tmp_path / "object", completed_records())
    monkeypatch.setattr(agent_harness, "MAX_OBJECT_BYTES", 4)
    with pytest.raises(AgentHarnessImportError):
        import_agent_harness_session(
            object_source.source,
            tmp_path / "object-result",
            blob_dir=object_source.blob_dir,
        )

    monkeypatch.setattr(agent_harness, "MAX_OBJECT_BYTES", MAX_OBJECT_BYTES)
    total_source = add_blob_reference(tmp_path / "total", completed_records())
    monkeypatch.setattr(
        agent_harness,
        "MAX_TOTAL_SOURCE_BYTES",
        total_source.source.stat().st_size
        + len(total_source.referenced_bytes or b"")
        - 1,
    )
    with pytest.raises(AgentHarnessImportError):
        import_agent_harness_session(
            total_source.source,
            tmp_path / "total-result",
            blob_dir=total_source.blob_dir,
        )


def test_malformed_blob_traversal_and_absolute_reference_are_rejected(
    tmp_path: Path,
) -> None:
    for index, value in enumerate(("blob:../../escape", "blob:/absolute")):
        records = completed_records()
        records[1]["message"]["content"].append({"type": "image", "data": value})
        source = write_session(tmp_path / f"source-{index}", records)
        with pytest.raises(AgentHarnessImportError):
            import_agent_harness_session(source, tmp_path / f"result-{index}")


def test_symlink_special_file_and_overlap_are_rejected(tmp_path: Path) -> None:
    real = write_synthetic_omp_session(tmp_path / "real").source
    symlink_source = tmp_path / "session-link.jsonl"
    symlink_source.symlink_to(real)
    with pytest.raises(AgentHarnessImportError):
        import_agent_harness_session(symlink_source, tmp_path / "symlink-result")

    fifo_source = tmp_path / "session.fifo"
    os.mkfifo(fifo_source)
    with pytest.raises(AgentHarnessImportError):
        import_agent_harness_session(fifo_source, tmp_path / "fifo-source-result")

    blob_session = add_blob_reference(tmp_path / "blob", completed_records())
    digest = next(path.name for path in (blob_session.blob_dir or Path()).iterdir())
    blob_path = (blob_session.blob_dir or Path()) / digest
    target = tmp_path / "target"
    target.write_bytes(b"different")
    blob_path.unlink()
    blob_path.symlink_to(target)
    with pytest.raises(AgentHarnessImportError):
        import_agent_harness_session(
            blob_session.source,
            tmp_path / "blob-result",
            blob_dir=blob_session.blob_dir,
        )

    fifo_session = add_blob_reference(tmp_path / "fifo", completed_records())
    fifo_digest = next(
        path.name for path in (fifo_session.blob_dir or Path()).iterdir()
    )
    fifo_path = (fifo_session.blob_dir or Path()) / fifo_digest
    fifo_path.unlink()
    os.mkfifo(fifo_path)
    with pytest.raises(AgentHarnessImportError):
        import_agent_harness_session(
            fifo_session.source,
            tmp_path / "fifo-result",
            blob_dir=fifo_session.blob_dir,
        )

    overlap_source = write_synthetic_omp_session(tmp_path / "overlap").source
    with pytest.raises(AgentHarnessImportError):
        import_agent_harness_session(overlap_source, overlap_source.with_suffix(""))


def test_declared_blob_digest_mismatch_is_rejected(tmp_path: Path) -> None:
    synthetic = add_blob_reference(tmp_path / "source", completed_records())
    blob_path = next((synthetic.blob_dir or Path()).iterdir())
    blob_path.write_bytes(b"changed synthetic bytes")

    with pytest.raises(AgentHarnessImportError):
        import_agent_harness_session(
            synthetic.source, tmp_path / "result", blob_dir=synthetic.blob_dir
        )


def test_conflicting_artifact_authority_is_rejected(tmp_path: Path) -> None:
    synthetic = write_synthetic_omp_session(tmp_path / "source", "referenced_object")
    artifact_root = synthetic.source.with_suffix("")
    (artifact_root / "1.other.log").write_bytes(b"conflicting synthetic bytes")

    with pytest.raises(AgentHarnessImportError, match="missing or conflicting"):
        import_agent_harness_session(synthetic.source, tmp_path / "result")


def test_source_change_before_copy_fails_atomically(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = write_synthetic_omp_session(tmp_path / "source").source
    destination = tmp_path / "result"
    original_copy = agent_harness._copy_exact_file
    changed = False

    def mutate_then_copy(
        source_path: Path,
        destination_path: Path,
        *,
        expected_sha256: str,
        expected_size: int,
        limit: int,
        label: str,
    ) -> None:
        nonlocal changed
        if label == "source session" and not changed:
            source_path.write_bytes(source_path.read_bytes() + b"\n")
            changed = True
        original_copy(
            source_path,
            destination_path,
            expected_sha256=expected_sha256,
            expected_size=expected_size,
            limit=limit,
            label=label,
        )

    monkeypatch.setattr(agent_harness, "_copy_exact_file", mutate_then_copy)

    with pytest.raises(AgentHarnessImportError, match="changed before copy"):
        import_agent_harness_session(source, destination)
    assert not destination.exists()
    assert not list(tmp_path.glob(".result.agent-harness-import-*"))


def test_staging_creation_failure_releases_import_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = write_synthetic_omp_session(tmp_path / "source").source
    destination = tmp_path / "result"

    def fail_staging(*args: Any, **kwargs: Any) -> str:
        raise OSError("synthetic staging failure")

    monkeypatch.setattr(agent_harness.tempfile, "mkdtemp", fail_staging)

    with pytest.raises(OSError, match="synthetic staging failure"):
        import_agent_harness_session(source, destination)
    assert not destination.exists()
    assert not (tmp_path / ".result.agent-harness-import.lock").exists()


def test_import_is_read_only_and_repository_paths_are_inert(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = tmp_path / "observed-repository"
    repository.mkdir()
    sentinel = repository / "sentinel.txt"
    sentinel.write_text("unchanged", encoding="utf-8")
    source = write_session(
        tmp_path / "source",
        completed_records(command="git reset --hard synthetic"),
        header_updates={"cwd": str(repository)},
    )
    original_source = source.read_bytes()

    def forbidden(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("external execution or network use is forbidden")

    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(os, "system", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)

    result_dir = tmp_path / "result"
    import_agent_harness_session(source, result_dir)

    evidence = _read_evidence(result_dir)
    assert source.read_bytes() == original_source
    assert sentinel.read_text(encoding="utf-8") == "unchanged"
    assert evidence.repository_observations == []
    assert evidence.source.workspace_path.value == str(repository)
    assert any(
        lifecycle.arguments.get("command") == "git reset --hard synthetic"
        for lifecycle in evidence.tool_lifecycles
    )


@pytest.mark.parametrize(
    ("scenario", "tool_state", "source_outcome", "completeness"),
    [
        ("completed", "completed", "unknown", "complete"),
        ("failed", "failed", "failed", "complete"),
        ("partial", "completed", "unknown", "partial"),
        ("interrupted", "interrupted", "interrupted", "complete"),
        ("denied", "denied", "unknown", "complete"),
        ("timeout", "timed_out", "unknown", "complete"),
    ],
)
def test_source_and_tool_lifecycle_states_remain_independent(
    tmp_path: Path,
    scenario: str,
    tool_state: str,
    source_outcome: str,
    completeness: str,
) -> None:
    source = write_synthetic_omp_session(tmp_path / "source", scenario).source
    result_dir = tmp_path / "result"

    outcome = import_agent_harness_session(source, result_dir)
    evidence = _read_evidence(result_dir)

    assert outcome.outcome == "completed"
    assert evidence.import_outcome == "completed"
    assert evidence.validation_outcome == "passed"
    assert evidence.tool_lifecycles[0].lifecycle_state == tool_state
    assert evidence.source_session_outcome == source_outcome
    assert evidence.source_completeness == completeness
    if scenario == "partial":
        assert evidence.tool_lifecycles[0].output_complete is False
    if scenario == "interrupted":
        assert evidence.tool_lifecycles[0].terminal_event_id == "event:e007"
        assert evidence.tool_lifecycles[0].interrupted is True
    if scenario == "denied":
        assert evidence.tool_lifecycles[0].started_event_id is None
    assert evidence.scoreability == "not_assessed"


def test_repository_like_source_output_never_becomes_repository_authority(
    tmp_path: Path,
) -> None:
    for scenario in ("clean_repository", "dirty_repository"):
        source = write_synthetic_omp_session(tmp_path / scenario, scenario).source
        result_dir = tmp_path / f"result-{scenario}"
        import_agent_harness_session(source, result_dir)
        evidence = _read_evidence(result_dir)
        assert evidence.repository_observations == []
        assert evidence.source.workspace_path.availability == "available"


def test_optional_unavailable_facts_remain_explicit(tmp_path: Path) -> None:
    source = write_synthetic_omp_session(
        tmp_path / "source", "unavailable_optional"
    ).source
    result_dir = tmp_path / "result"

    import_agent_harness_session(source, result_dir)
    evidence = _read_evidence(result_dir)

    assert evidence.source.producer.version.availability == "unknown"
    assert evidence.source.selected_leaf.availability == "unknown"
    assert evidence.source.ended_at.availability == "absent"
    assert evidence.terminal.availability == "absent"
    assert evidence.source_session_outcome == "unknown"


@pytest.mark.parametrize(
    "mutation",
    [
        "credential_pin",
        "provider_cache_key",
        "provider_payload",
        "private_reasoning",
        "api_key",
        "private_key",
        "credential_url",
        "environment_dump",
    ],
)
def test_structurally_private_source_is_rejected(tmp_path: Path, mutation: str) -> None:
    records = completed_records()
    header_updates: dict[str, Any] = {}
    if mutation == "credential_pin":
        records.insert(
            1,
            {
                "type": "credential_pin",
                "id": "private",
                "parentId": "e001",
                "timestamp": "2026-08-12T00:00:01.500Z",
                "provider": "synthetic",
                "accountHash": "a" * 64,
            },
        )
        records[2]["parentId"] = "private"
    elif mutation == "provider_cache_key":
        header_updates["providerPromptCacheKey"] = "prohibited"
    elif mutation == "provider_payload":
        records[2]["message"]["providerPayload"] = {"opaque": "prohibited"}
    elif mutation == "private_reasoning":
        records[2]["message"]["content"].append(
            {"type": "thinking", "text": "prohibited"}
        )
    elif mutation == "api_key":
        records[1]["message"]["apiKey"] = "prohibited"
    elif mutation == "private_key":
        records[1]["message"]["content"][0]["text"] = (
            "-----BEGIN OPENSSH PRIVATE KEY-----"
        )
    elif mutation == "credential_url":
        records[1]["message"]["content"][0]["text"] = (
            "https://synthetic.invalid/path?token=prohibited"
        )
    else:
        records[1]["message"]["environment"] = {"UNRELATED": "prohibited"}
    source = write_session(tmp_path / "source", records, header_updates=header_updates)

    with pytest.raises(AgentHarnessImportError) as captured:
        import_agent_harness_session(source, tmp_path / "result")

    assert captured.value.outcome == "failed"
    assert not (tmp_path / "result").exists()


def test_valid_package_detects_source_member_mutation_and_missing_object(
    tmp_path: Path,
) -> None:
    source = write_synthetic_omp_session(tmp_path / "source").source
    result_dir = tmp_path / "result"
    import_agent_harness_session(source, result_dir)
    (result_dir / SESSION_RELATIVE_PATH).write_bytes(b"changed\n")
    errors = validate_result_dir(result_dir)
    assert any("hash mismatch" in error for error in errors)

    referenced = write_synthetic_omp_session(
        tmp_path / "referenced", "referenced_object"
    )
    referenced_result = tmp_path / "referenced-result"
    import_agent_harness_session(referenced.source, referenced_result)
    evidence = _read_evidence(referenced_result)
    object_member = next(
        item for item in evidence.source_inventory if item.role == "source_object"
    )
    (referenced_result / object_member.path).unlink()
    errors = validate_result_dir(referenced_result)
    assert any("missing artifact" in error for error in errors)


def test_validation_rejects_broken_reference_and_unsupported_identity(
    tmp_path: Path,
) -> None:
    source = write_synthetic_omp_session(tmp_path / "source").source
    reference_result = tmp_path / "reference-result"
    import_agent_harness_session(source, reference_result)
    result = _read_result(reference_result)
    result["agent_harness_evidence"]["sha256"] = "0" * 64
    (reference_result / "llmgauge-result.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    assert any("file hash" in error for error in validate_result_dir(reference_result))

    unsupported_result = tmp_path / "unsupported-result"
    import_agent_harness_session(source, unsupported_result)
    _rewrite_evidence(
        unsupported_result,
        lambda data: data["source"].__setitem__("source_format_version", 2),
    )
    assert any(
        "source_format_version" in error
        for error in validate_result_dir(unsupported_result)
    )


def test_validation_rejects_mapping_disagreement_and_native_confusion(
    tmp_path: Path,
) -> None:
    source = write_synthetic_omp_session(tmp_path / "source").source
    mapping_result = tmp_path / "mapping-result"
    import_agent_harness_session(source, mapping_result)

    def change_mapping(data: dict[str, Any]) -> None:
        data["trajectory"][0]["kind"] = "harness_event"

    _rewrite_evidence(mapping_result, change_mapping, recompute_identity=True)
    errors = validate_result_dir(mapping_result)
    assert any("trajectory disagrees" in error for error in errors)

    mixed_result = tmp_path / "mixed-result"
    import_agent_harness_session(source, mixed_result)
    result = _read_result(mixed_result)
    result["transcript"] = {
        "schema_version": "llmgauge.transcript.v0",
        "path": "transcript/transcript.json",
        "sha256": "0" * 64,
    }
    (mixed_result / "llmgauge-result.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    errors = validate_result_dir(mixed_result)
    assert any("cannot include a native transcript" in error for error in errors)


def test_imported_fingerprint_binds_source_bytes_objects_and_mapping(
    tmp_path: Path,
) -> None:
    first_source = write_synthetic_omp_session(tmp_path / "first-source").source
    first_result = tmp_path / "first-result"
    import_agent_harness_session(first_source, first_result)
    baseline = run_fingerprint_value(first_result, _read_result(first_result))

    changed_records = completed_records()
    changed_records[1]["message"]["content"][0]["text"] = "Changed source fact."
    changed_source = write_session(tmp_path / "changed-source", changed_records)
    changed_result = tmp_path / "changed-result"
    import_agent_harness_session(changed_source, changed_result)
    assert (
        run_fingerprint_value(changed_result, _read_result(changed_result)) != baseline
    )

    object_one = write_synthetic_omp_session(
        tmp_path / "object-one", "referenced_object"
    )
    object_two = write_synthetic_omp_session(
        tmp_path / "object-two", "referenced_object"
    )
    (object_two.source.with_suffix("") / "1.bash.log").write_bytes(
        b"different complete synthetic output\n"
    )
    object_one_result = tmp_path / "object-one-result"
    object_two_result = tmp_path / "object-two-result"
    import_agent_harness_session(object_one.source, object_one_result)
    import_agent_harness_session(object_two.source, object_two_result)
    assert run_fingerprint_value(
        object_one_result, _read_result(object_one_result)
    ) != run_fingerprint_value(object_two_result, _read_result(object_two_result))

    mapping_result = tmp_path / "mapping-result"
    import_agent_harness_session(first_source, mapping_result)
    mapping_baseline = run_fingerprint_value(
        mapping_result, _read_result(mapping_result)
    )
    mapping_data = _rewrite_evidence(
        mapping_result,
        lambda data: data.__setitem__("source_completeness", "partial"),
        recompute_identity=True,
    )
    mapping_data.pop("run_fingerprint", None)
    assert run_fingerprint_value(mapping_result, mapping_data) != mapping_baseline


def test_mutable_derivatives_do_not_change_imported_fingerprint(tmp_path: Path) -> None:
    source = write_synthetic_omp_session(tmp_path / "source").source
    result_dir = tmp_path / "result"
    import_agent_harness_session(source, result_dir)
    result = _read_result(result_dir)
    baseline = run_fingerprint_value(result_dir, result)

    (result_dir / "review.txt").write_text("mutable review", encoding="utf-8")
    changed = copy.deepcopy(result)
    changed["review"] = {"state": "reviewed"}
    changed["summary"]["manual_score_total"] = 5

    assert run_fingerprint_value(result_dir, changed) == baseline


def test_legacy_fingerprint_payload_is_unchanged_when_import_field_absent(
    tmp_path: Path,
) -> None:
    result_dir, result = _write_fingerprintable_run(tmp_path)
    with_none = copy.deepcopy(result)
    with_none["agent_harness_evidence"] = None

    assert build_run_fingerprint_payload(result_dir, result) == (
        build_run_fingerprint_payload(result_dir, with_none)
    )
    assert run_fingerprint_value(result_dir, result) == run_fingerprint_value(
        result_dir, with_none
    )


def test_atomic_success_failure_idempotence_and_conflict(tmp_path: Path) -> None:
    source = write_synthetic_omp_session(tmp_path / "source").source
    result_dir = tmp_path / "result"
    import_agent_harness_session(source, result_dir)
    before = {
        path.relative_to(result_dir).as_posix(): path.stat().st_mtime_ns
        for path in result_dir.rglob("*")
        if path.is_file()
    }

    second = import_agent_harness_session(source, result_dir)
    after = {
        path.relative_to(result_dir).as_posix(): path.stat().st_mtime_ns
        for path in result_dir.rglob("*")
        if path.is_file()
    }
    assert second.outcome == "already_imported"
    assert after == before

    malformed = tmp_path / "malformed.jsonl"
    malformed.write_text("not-json\n", encoding="utf-8")
    failed_destination = tmp_path / "failed-result"
    with pytest.raises(AgentHarnessImportError):
        import_agent_harness_session(malformed, failed_destination)
    assert not failed_destination.exists()
    assert not list(tmp_path.glob(".failed-result.agent-harness-import-*"))

    conflict = tmp_path / "conflict"
    conflict.mkdir()
    sentinel = conflict / "sentinel"
    sentinel.write_text("unchanged", encoding="utf-8")
    with pytest.raises(AgentHarnessImportError):
        import_agent_harness_session(source, conflict)
    assert sentinel.read_text(encoding="utf-8") == "unchanged"


def test_dry_run_performs_no_writes(tmp_path: Path) -> None:
    source = write_synthetic_omp_session(tmp_path / "source").source
    destination = tmp_path / "result"
    before = source.read_bytes()

    outcome = import_agent_harness_session(source, destination, dry_run=True)

    assert outcome.outcome == "dry_run"
    assert not destination.exists()
    assert source.read_bytes() == before
    assert not list(tmp_path.glob(".*.agent-harness-import-*"))


def test_native_consumers_fail_closed_for_imported_evidence(tmp_path: Path) -> None:
    source = write_synthetic_omp_session(tmp_path / "source").source
    result_dir = tmp_path / "result"
    import_agent_harness_session(source, result_dir)
    result = _read_result(result_dir)

    with pytest.raises(ValueError, match="Agent Harness"):
        build_score_template(result)
    with pytest.raises(ValueError, match="Agent Harness"):
        build_markdown_report(result)
    with pytest.raises(ValueError, match="Agent Harness"):
        build_compare_report([result, copy.deepcopy(result)])
    with pytest.raises(ValueError, match="Agent Harness"):
        build_run_index_item(result_dir)
    with pytest.raises(ValueError, match="Agent Harness"):
        export_public_run(result_dir, tmp_path / "public")
    assert not (tmp_path / "public").exists()


def test_run_fingerprint_verification_rejects_tampering(tmp_path: Path) -> None:
    source = write_synthetic_omp_session(tmp_path / "source").source
    result_dir = tmp_path / "result"
    import_agent_harness_session(source, result_dir)
    result = _read_result(result_dir)
    result["run_fingerprint"]["value"] = "sha256:" + "0" * 64
    (result_dir / "llmgauge-result.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    errors = validate_result_dir(result_dir)

    assert any("does not match canonical run evidence" in error for error in errors)


def test_imported_result_fingerprint_can_be_rebuilt_deterministically(
    tmp_path: Path,
) -> None:
    source = write_synthetic_omp_session(tmp_path / "source").source
    result_dir = tmp_path / "result"
    import_agent_harness_session(source, result_dir)
    result = _read_result(result_dir)
    original = result["run_fingerprint"]
    result.pop("run_fingerprint")

    rebuilt = attach_run_fingerprint(result_dir, result)

    assert rebuilt == original


def test_artifact_references_preserve_exact_pointers_and_deduplicate_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    records = completed_records(
        result_details={
            "artifactId": "1",
            "truncation": {"artifactId": "1", "reason": "direct spill"},
            "meta": {"truncation": {"artifactId": "1", "reason": "metadata spill"}},
        }
    )
    source = write_session(tmp_path / "source", records)
    artifact_bytes = b"one authoritative synthetic artifact\n"
    artifact_dir = source.with_suffix("")
    artifact_dir.mkdir()
    (artifact_dir / "1.bash.log").write_bytes(artifact_bytes)
    monkeypatch.setattr(
        agent_harness,
        "MAX_TOTAL_SOURCE_BYTES",
        source.stat().st_size + len(artifact_bytes),
    )

    result_dir = tmp_path / "result"
    import_agent_harness_session(source, result_dir)
    evidence = _read_evidence(result_dir)

    assert {item.source_pointer for item in evidence.source_references} == {
        "/message/details/artifactId",
        "/message/details/truncation/artifactId",
        "/message/details/meta/truncation/artifactId",
    }
    assert len({item.member_id for item in evidence.source_references}) == 1
    assert (
        len(
            [item for item in evidence.source_inventory if item.role == "source_object"]
        )
        == 1
    )


def test_artifact_directory_scan_is_bounded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    synthetic = write_synthetic_omp_session(tmp_path / "source", "referenced_object")
    (synthetic.source.with_suffix("") / "unrelated.log").write_bytes(b"unrelated")
    monkeypatch.setattr(agent_harness, "MAX_ARTIFACT_DIRECTORY_ENTRIES", 1)

    with pytest.raises(AgentHarnessImportError, match="entry limit"):
        import_agent_harness_session(synthetic.source, tmp_path / "result")


def test_stale_session_exit_is_not_terminal_authority(tmp_path: Path) -> None:
    records = completed_records()
    records.append(
        {
            "type": "title_change",
            "id": "e008",
            "parentId": "e007",
            "timestamp": "2026-08-12T00:00:08.000Z",
            "title": "Synthetic continuation",
            "source": "synthetic",
        }
    )
    source = write_session(tmp_path / "source", records)
    result_dir = tmp_path / "result"

    import_agent_harness_session(source, result_dir)
    evidence = _read_evidence(result_dir)

    assert evidence.terminal.availability == "absent"
    assert evidence.source_session_outcome == "unknown"
    assert evidence.source.ended_at.availability == "absent"
    stale_exit = next(
        item for item in evidence.trajectory if item.source_entry_id == "e007"
    )
    assert stale_exit.kind == "harness_event"


def test_model_visible_harness_context_is_preserved_in_trajectory(
    tmp_path: Path,
) -> None:
    records = completed_records()
    records[0]["systemPrompt"] = "Synthetic system instruction"
    terminal = records.pop()
    records.extend(
        [
            {
                "type": "branch_summary",
                "id": "e008",
                "parentId": "e006",
                "timestamp": "2026-08-12T00:00:08.000Z",
                "fromId": "e006",
                "summary": "Synthetic branch context",
            },
            {
                "type": "compaction",
                "id": "e009",
                "parentId": "e008",
                "timestamp": "2026-08-12T00:00:09.000Z",
                "summary": "Synthetic compacted context",
                "firstKeptEntryId": "e001",
                "tokensBefore": 42,
            },
            {
                "type": "ttsr_injection",
                "id": "e010",
                "parentId": "e009",
                "timestamp": "2026-08-12T00:00:10.000Z",
                "injectedRules": ["Synthetic injected rule"],
            },
        ]
    )
    terminal["parentId"] = "e010"
    records.append(terminal)
    source = write_session(tmp_path / "source", records)
    result_dir = tmp_path / "result"

    import_agent_harness_session(source, result_dir)
    evidence = _read_evidence(result_dir)
    by_role = {item.role: item for item in evidence.trajectory if item.role}

    assert by_role["system"].visibility == "model_visible"
    assert by_role["tools"].visibility == "model_visible"
    for role in ("branch_summary", "compaction", "ttsr_injection"):
        assert by_role[role].kind == "harness_message"
        assert by_role[role].visibility == "model_visible"


def test_nonzero_exit_without_error_flag_is_failed(tmp_path: Path) -> None:
    source = write_session(
        tmp_path / "source",
        completed_records(result_details={"exitCode": 9}, result_is_error=False),
    )
    result_dir = tmp_path / "result"

    import_agent_harness_session(source, result_dir)

    assert _read_evidence(result_dir).tool_lifecycles[0].lifecycle_state == "failed"


@pytest.mark.parametrize(
    "mutation",
    ["conflicting_flags", "denied_after_start", "start_before_request"],
)
def test_impossible_tool_lifecycles_are_rejected(tmp_path: Path, mutation: str) -> None:
    if mutation == "conflicting_flags":
        records = completed_records(
            result_details={"timedOut": True, "cancelled": True},
            result_is_error=True,
        )
    elif mutation == "denied_after_start":
        records = completed_records(
            result_details={"denied": True},
            result_is_error=True,
        )
    else:
        records = completed_records()
        start = records.pop(3)
        start["parentId"] = "e002"
        records[2]["parentId"] = "e004"
        records.insert(2, start)
    source = write_session(tmp_path / mutation, records)

    with pytest.raises(AgentHarnessImportError):
        import_agent_harness_session(source, tmp_path / f"result-{mutation}")


@pytest.mark.parametrize("private_case", ["title", "token", "environment"])
def test_structural_privacy_gate_covers_title_and_key_variants(
    tmp_path: Path, private_case: str
) -> None:
    records = completed_records()
    if private_case == "title":
        source = write_session(tmp_path / "title", records, physical_title=True)
        payload = source.read_bytes()
        first_newline = payload.index(b"\n")
        title = json.dumps(
            {
                "type": "title",
                "title": "https://synthetic-user:synthetic-pass@example.invalid/",
            },
            separators=(",", ":"),
        ).encode("utf-8")
        source.write_bytes(
            title + b" " * (first_newline - len(title)) + payload[first_newline:]
        )
    else:
        key = "githubToken" if private_case == "token" else "processEnvironment"
        value: Any = "synthetic-secret" if private_case == "token" else {"A": "B"}
        records[4]["message"]["details"][key] = value
        source = write_session(tmp_path / private_case, records)

    with pytest.raises(AgentHarnessImportError, match="prohibited|credential"):
        import_agent_harness_session(source, tmp_path / f"result-{private_case}")


def test_json_nesting_is_bounded(tmp_path: Path) -> None:
    records = completed_records()
    nested: dict[str, Any] = {}
    cursor = nested
    for _ in range(agent_harness.MAX_JSON_NESTING + 1):
        child: dict[str, Any] = {}
        cursor["nested"] = child
        cursor = child
    records[4]["message"]["details"]["nested"] = nested
    source = write_session(tmp_path / "source", records)

    with pytest.raises(AgentHarnessImportError, match="nesting exceeds"):
        import_agent_harness_session(source, tmp_path / "result")


def test_source_open_rejects_symlink_swap_race(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = write_synthetic_omp_session(tmp_path / "source").source
    replacement = write_synthetic_omp_session(tmp_path / "replacement").source
    original_open = agent_harness.os.open
    swapped = False

    def swap_before_open(path, flags, *args, **kwargs):
        nonlocal swapped
        if (
            not swapped
            and isinstance(path, (str, bytes, os.PathLike))
            and Path(path) == source
        ):
            source.unlink()
            source.symlink_to(replacement)
            swapped = True
        return original_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(agent_harness.os, "open", swap_before_open)

    with pytest.raises(AgentHarnessImportError):
        import_agent_harness_session(source, tmp_path / "result")
    assert not (tmp_path / "result").exists()


def test_untrusted_evidence_collection_and_total_byte_bounds(
    tmp_path: Path,
) -> None:
    reference_source = write_synthetic_omp_session(tmp_path / "reference-source").source
    reference_result = tmp_path / "reference-result"
    import_agent_harness_session(reference_source, reference_result)
    digest = "1" * 64

    def add_too_many_references(data: dict[str, Any]) -> None:
        data["source_references"] = [
            {
                "reference_id": f"ref:{index:064x}",
                "kind": "blob",
                "source_entry_id": "e002",
                "source_pointer": f"/message/content/{index}/data",
                "source_object_id": digest,
                "declared_sha256": digest,
                "member_id": f"object:{digest}",
                "availability": "available",
                "source_relationship": "blob_reference",
            }
            for index in range(agent_harness.MAX_REFERENCED_OBJECTS + 1)
        ]

    _rewrite_evidence(reference_result, add_too_many_references)
    reference_errors = validate_result_dir(reference_result)
    assert any("at most 256" in error for error in reference_errors)

    inventory_source = write_synthetic_omp_session(tmp_path / "inventory-source").source
    inventory_result = tmp_path / "inventory-result"
    import_agent_harness_session(inventory_source, inventory_result)

    def exceed_total_bytes(data: dict[str, Any]) -> None:
        for index in range(agent_harness.MAX_REFERENCED_OBJECTS):
            member_digest = f"{index + 1:064x}"
            data["source_inventory"].append(
                {
                    "member_id": f"object:{member_digest}",
                    "role": "source_object",
                    "path": (f"{agent_harness.OBJECTS_RELATIVE_DIR}/{member_digest}"),
                    "sha256": member_digest,
                    "byte_size": 1024 * 1024,
                    "availability": "available",
                    "source_relationship": "referenced_object",
                    "observed_source_path": None,
                }
            )

    _rewrite_evidence(inventory_result, exceed_total_bytes)
    inventory_errors = validate_result_dir(inventory_result)
    assert any("total source byte limit" in error for error in inventory_errors)


def test_imported_result_requires_schema_version_and_fingerprint(
    tmp_path: Path,
) -> None:
    source = write_synthetic_omp_session(tmp_path / "source").source
    result_dir = tmp_path / "result"
    import_agent_harness_session(source, result_dir)
    result = _read_result(result_dir)
    result["schema_version"] = "unsupported"
    result["llmgauge_version"] = "mismatched"
    result.pop("run_fingerprint")
    (result_dir / "llmgauge-result.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    errors = validate_result_dir(result_dir)

    assert any("schema_version must be llmgauge.result.v0" in error for error in errors)
    assert any("must match the importer version" in error for error in errors)
    assert any("requires a run_fingerprint" in error for error in errors)


def test_atomic_publish_never_replaces_racing_destination(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = write_synthetic_omp_session(tmp_path / "source").source
    destination = tmp_path / "result"
    original_publish = agent_harness._rename_directory_no_replace

    def race_publish(staging: Path, target: Path) -> None:
        target.mkdir()
        (target / "racer.txt").write_text("preserved", encoding="utf-8")
        original_publish(staging, target)

    monkeypatch.setattr(agent_harness, "_rename_directory_no_replace", race_publish)

    with pytest.raises(AgentHarnessImportError, match="destination appeared"):
        import_agent_harness_session(source, destination)
    assert (destination / "racer.txt").read_text(encoding="utf-8") == "preserved"
    assert not list(tmp_path.glob(".result.agent-harness-import-*"))
