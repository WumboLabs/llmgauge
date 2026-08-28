from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from typer.testing import CliRunner

import llmgauge.cli as cli
import llmgauge.core.transcript_public_export as tpe
from llmgauge.commands import run_helpers
from llmgauge.core.public_export import export_public_run
from llmgauge.core.run_fingerprint import attach_run_fingerprint
from llmgauge.core.transcript_public_export import (
    PUBLIC_TRANSCRIPT_COMPARISON_FILENAME,
    PUBLIC_TRANSCRIPT_COMPARISON_REPORT_FILENAME,
    PUBLIC_TRANSCRIPT_COMPARISON_SCHEMA_VERSION,
    PUBLIC_TRANSCRIPT_FILENAME,
    PUBLIC_TRANSCRIPT_REPORT_FILENAME,
    PUBLIC_TRANSCRIPT_SCHEMA_VERSION,
    TranscriptPublicExportError,
    build_public_transcript,
    build_public_transcript_comparison,
    export_public_transcript,
    export_public_transcript_comparison,
    load_public_transcript_pair,
    load_public_transcript_result,
    render_public_transcript_comparison_markdown,
    render_public_transcript_markdown,
    validate_public_projection,
    validate_public_transcript_projection,
)
from llmgauge.core.multi_turn import load_transcript
from llmgauge.core.transcript_compare import transcript_identity
from tests.test_multi_turn import (
    TASK_ID,
    _patch_identity,
    _resolved,
    _write_task,
)
from tests.test_public_export import _write_run

runner = CliRunner()

_COMPLETED_TASK: dict[str, Any] = {"feedback": False, "max_turns": 1}
_OK = [("the final answer text", "", 0)]
_FAILED = [("partial response body", "runtime exploded", 1)]

CANARY_URL = "http://operator:hunter2@registry.example.invalid/models/q3k7.gguf"
CANARY_HOME = "/home/privateuser/models/m5t9.gguf"
CANARY_HASH = "model-" + "f" * 64
CANARY_SLASH = "canary/model/slash"
CANARY_CONV = "conv-canary-4f2a"
CANARY_FEEDBACK = "Please apply the fix; token=sk-canary-feedback-9e7d"
CANARY_STDOUT = "answer citing /home/privateuser/secret.txt token=sk-canary-out-9e7d"
CANARY_STDERR = "warn https://user:pw@host.example.invalid/log"

_FULL_HASH_RE = re.compile(r"(?<![0-9a-fA-F])[0-9a-fA-F]{64}(?![0-9a-fA-F])")


def _run_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    *,
    task_kwargs: dict[str, Any],
    responses: list[tuple[str, str, int]],
    conversation_id: str,
    model_id: str | None = None,
    feedback_content: str | None = None,
    max_turns: int | None = None,
) -> Path:
    task_path = _write_task(tmp_path / f"{name}-task.json", **task_kwargs)
    if feedback_content is not None:
        task_data = json.loads(task_path.read_text(encoding="utf-8"))
        task_data["feedback"][0]["content"] = feedback_content
        task_path.write_text(json.dumps(task_data), encoding="utf-8")
    iterator = iter(responses)

    def fake_run(config, prompt, *, timeout_seconds):
        stdout, stderr, exit_status = next(iterator)
        return SimpleNamespace(
            command=[str(config.llama_cli)],
            stdout=stdout,
            stderr=stderr,
            exit_status=exit_status,
            timed_out=False,
            vram_samples=[],
            vram_summary=None,
        )

    monkeypatch.setattr(run_helpers, "run_llama_cpp", fake_run)
    _patch_identity(monkeypatch)
    resolved = _resolved()
    if model_id is not None:
        resolved["model_id"] = model_id
    result_dir = tmp_path / name
    run_helpers.execute_run(
        suite=Path("agent-backend-v1"),
        only=TASK_ID,
        include="all",
        resolved=resolved,
        out=result_dir,
        fail_on_failed_prompts=False,
        conversation_task=task_path,
        conversation_id=conversation_id,
        max_turns=max_turns,
    )
    return result_dir


def _pair(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    left_task: dict[str, Any],
    left_responses: list[tuple[str, str, int]],
    right_task: dict[str, Any],
    right_responses: list[tuple[str, str, int]],
    left_max_turns: int | None = None,
    right_max_turns: int | None = None,
) -> list[Path]:
    left = _run_result(
        tmp_path,
        monkeypatch,
        "left",
        task_kwargs=left_task,
        responses=left_responses,
        conversation_id="conversation-left",
        max_turns=left_max_turns,
    )
    right = _run_result(
        tmp_path,
        monkeypatch,
        "right",
        task_kwargs=right_task,
        responses=right_responses,
        conversation_id="conversation-right",
        max_turns=right_max_turns,
    )
    return [left, right]


def _projection_for(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    dirs: list[Path],
) -> dict[str, Any]:
    results, transcripts = load_public_transcript_pair(dirs)
    return build_public_transcript_comparison(results, transcripts)


def _copy_result(tmp_path: Path, source: Path, name: str) -> Path:
    destination = tmp_path / name
    shutil.copytree(source, destination)
    return destination


def _rewrite_result_json(directory: Path, mutate: Any) -> None:
    path = directory / "llmgauge-result.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    mutate(data)
    attach_run_fingerprint(directory, data)
    path.write_text(json.dumps(data), encoding="utf-8")


# ---------------------------------------------------------------------------
# Closed-world schema
# ---------------------------------------------------------------------------

_TOP_KEYS = {
    "schema_version",
    "generated_by",
    "created_at_utc",
    "source_artifact_types",
    "transcript_schema_versions",
    "eligibility",
    "classification",
    "runs",
    "redaction",
    "claim_boundary",
    "human_review_required_before_publication",
}
_NESTED = {
    "eligibility": {
        "eligible",
        "classification",
        "mismatched_identity_fields",
        "comparison_basis",
    },
    "classification": {"classification", "differing_facts", "completion_asymmetry"},
    "runs": {
        "slot",
        "model_label",
        "completion",
        "turns",
        "attempt_states",
        "feedback",
        "states",
        "event_order",
        "capture_health",
        "review_hooks",
    },
    "completion": {"completion_state", "completion_actor", "terminal_reason"},
    "turns": {
        "logical_model_turns",
        "model_attempts",
        "retries",
        "recoveries",
    },
    "attempt_states": {
        "sequence",
        "relationship",
        "attempt_state",
        "exit_status",
    },
    "feedback": {
        "declared",
        "supplied",
        "consumed",
        "supplied_unconsumed",
        "unreached",
        "plan",
    },
    "plan": {
        "ordinal",
        "after_model_turn",
        "lifecycle_state",
        "disposition_reason",
    },
    "states": {"state_transitions", "links"},
    "links": {"sequence", "previous_sequence", "caused_by_sequence"},
    "event_order": {
        "sequence",
        "kind",
        "role",
        "execution_status",
        "relationship",
    },
    "capture_health": {
        "truncated_artifacts",
        "partial_artifacts",
        "failed_artifacts",
        "redacted_artifacts",
    },
    "review_hooks": {
        "scoreability",
        "per_turn",
        "feedback_use",
        "correction",
        "recovery",
        "consistency",
        "final_response",
    },
    "model_label_substitutions": {"slot", "reason"},
    "redaction": {
        "policy",
        "categories",
        "model_label_substitutions",
        "omitted_field_classes",
    },
}


def _walk_keys(node: Any, key: str | None, path: str) -> None:
    if isinstance(node, dict):
        allowed = _TOP_KEYS if path == "$" else _NESTED.get(key or "", set())
        assert set(node) <= allowed, f"unexpected keys at {path}: {sorted(node)}"
        for child_key, child in node.items():
            _walk_keys(child, child_key, f"{path}.{child_key}")
        return
    if isinstance(node, list):
        for index, item in enumerate(node):
            _walk_keys(item, key, f"{path}[{index}]")


def test_projection_is_closed_world(tmp_path, monkeypatch) -> None:
    dirs = _pair(
        tmp_path,
        monkeypatch,
        left_task={"feedback": True, "max_turns": 2},
        left_responses=[("first", "", 0), ("corrected", "", 0)],
        right_task={"feedback": True, "max_turns": 2},
        right_responses=[("first", "", 0), ("corrected", "", 0)],
    )
    projection = _projection_for(tmp_path, monkeypatch, dirs)
    _walk_keys(projection, None, "$")
    validate_public_projection(projection)
    assert projection["schema_version"] == PUBLIC_TRANSCRIPT_COMPARISON_SCHEMA_VERSION
    assert [run["slot"] for run in projection["runs"]] == ["run-a", "run-b"]
    assert projection["human_review_required_before_publication"] is True
    assert projection["generated_by"] == "llmgauge"
    assert projection["source_artifact_types"] == [
        "llmgauge.result.v0",
        "llmgauge.result.v0",
    ]
    assert projection["transcript_schema_versions"] == [
        "llmgauge.transcript.v0",
        "llmgauge.transcript.v0",
    ]


def test_projection_carries_no_identity_values(tmp_path, monkeypatch) -> None:
    dirs = _pair(
        tmp_path,
        monkeypatch,
        left_task=_COMPLETED_TASK,
        left_responses=_OK,
        right_task=_COMPLETED_TASK,
        right_responses=_OK,
    )
    projection = _projection_for(tmp_path, monkeypatch, dirs)
    identity = transcript_identity(load_transcript(dirs[0]))
    encoded = json.dumps(projection)
    strings = set(re.findall(r'"([^"]*)"', encoded))
    for field in (
        "protocol_id",
        "task_id",
        "initial_state_id",
        "suite_id",
        "suite_version",
    ):
        assert identity[field] not in strings
    # conversation IDs and run IDs are never projected under any form
    assert "conversation-left" not in encoded
    assert "conversation-right" not in encoded
    assert dirs[0].name not in encoded
    assert TASK_ID not in encoded
    assert not _FULL_HASH_RE.search(encoded)
    # comparison basis names identity fields, not their values
    assert "task_id" in projection["eligibility"]["comparison_basis"]
    assert "initial_state_sha256" in projection["eligibility"]["comparison_basis"]


# ---------------------------------------------------------------------------
# Structural content
# ---------------------------------------------------------------------------


def test_event_order_preserves_roles_and_relationship(tmp_path, monkeypatch) -> None:
    dirs = _pair(
        tmp_path,
        monkeypatch,
        left_task={"feedback": False, "max_turns": 1, "attempts": 2},
        left_responses=[("bad bytes", "recovery failed", 1), ("corrected", "", 0)],
        right_task={"feedback": False, "max_turns": 1, "attempts": 2},
        right_responses=[("corrected", "", 0)],
    )
    projection = _projection_for(tmp_path, monkeypatch, dirs)
    run_a, run_b = projection["runs"]
    assert run_a["turns"]["model_attempts"] == 2
    assert run_a["turns"]["retries"] == 1
    assert run_b["turns"]["model_attempts"] == 1
    assert run_b["turns"]["retries"] == 0
    assert [a["relationship"] for a in run_a["attempt_states"]] == [
        "initial",
        "retry",
    ]
    assert [a["attempt_state"] for a in run_a["attempt_states"]] == [
        "failed",
        "completed",
    ]
    assert [a["exit_status"] for a in run_a["attempt_states"]] == [1, 0]
    kinds = [event["kind"] for event in run_a["event_order"]]
    assert kinds[0] == "task"
    assert kinds[-1] == "terminal"
    assert "user" in {event["role"] for event in run_a["event_order"]}
    assert "assistant" in {event["role"] for event in run_a["event_order"]}
    assert "protocol" in {event["role"] for event in run_a["event_order"]}
    attempt_events = [
        event for event in run_a["event_order"] if event["kind"] == "model_attempt"
    ]
    assert all("relationship" in event for event in attempt_events)
    assert all(
        "relationship" not in event
        for event in run_a["event_order"]
        if event["kind"] != "model_attempt"
    )
    assert projection["classification"]["classification"] == "structurally comparable"
    assert "model_attempts" in projection["classification"]["differing_facts"]
    assert projection["eligibility"]["eligible"] is True


def test_feedback_plan_projection_is_id_free(tmp_path, monkeypatch) -> None:
    dirs = _pair(
        tmp_path,
        monkeypatch,
        left_task={"feedback": True, "max_turns": 2},
        left_responses=[("first", "", 0), ("corrected", "", 0)],
        right_task={"feedback": True, "max_turns": 2},
        right_responses=[("first", "", 0), ("corrected", "", 0)],
    )
    projection = _projection_for(tmp_path, monkeypatch, dirs)
    feedback = projection["runs"][0]["feedback"]
    assert feedback["declared"] == 1
    assert feedback["supplied"] == 1
    assert feedback["consumed"] == 1
    assert feedback["supplied_unconsumed"] == 0
    assert feedback["unreached"] == 0
    assert feedback["plan"] == [
        {
            "ordinal": 1,
            "after_model_turn": 1,
            "lifecycle_state": "consumed",
            "disposition_reason": "consumed_by_model_turn",
        }
    ]
    assert "feedback-1" not in json.dumps(feedback)


def test_unreached_feedback_disposition(tmp_path, monkeypatch) -> None:
    dirs = _pair(
        tmp_path,
        monkeypatch,
        left_task={"feedback": True, "max_turns": 2, "feedback_after_turn": 2},
        left_responses=_OK,
        right_task={"feedback": True, "max_turns": 2},
        right_responses=_OK,
        left_max_turns=1,
        right_max_turns=1,
    )
    projection = _projection_for(tmp_path, monkeypatch, dirs)
    plan = projection["runs"][0]["feedback"]["plan"]
    assert plan[0]["lifecycle_state"] == "unreached"
    assert plan[0]["disposition_reason"] == "scheduling_point_not_reached"


def test_state_links_use_sequences_only(tmp_path, monkeypatch) -> None:
    dirs = _pair(
        tmp_path,
        monkeypatch,
        left_task=_COMPLETED_TASK,
        left_responses=_OK,
        right_task=_COMPLETED_TASK,
        right_responses=_OK,
    )
    projection = _projection_for(tmp_path, monkeypatch, dirs)
    states = projection["runs"][0]["states"]
    assert states["state_transitions"] >= 1
    for link in states["links"]:
        assert set(link) == {"sequence", "previous_sequence", "caused_by_sequence"}
    encoded = json.dumps(states)
    assert "initial-state" not in encoded
    assert "state-" not in encoded


# ---------------------------------------------------------------------------
# Classification regressions
# ---------------------------------------------------------------------------


def test_identical_structure_classification(tmp_path, monkeypatch) -> None:
    dirs = _pair(
        tmp_path,
        monkeypatch,
        left_task=_COMPLETED_TASK,
        left_responses=_OK,
        right_task=_COMPLETED_TASK,
        right_responses=_OK,
    )
    projection = _projection_for(tmp_path, monkeypatch, dirs)
    assert projection["eligibility"]["classification"] == "identical structure"
    assert projection["classification"]["differing_facts"] == []
    assert projection["classification"]["completion_asymmetry"] is False


def test_completion_asymmetry_is_boolean(tmp_path, monkeypatch) -> None:
    dirs = _pair(
        tmp_path,
        monkeypatch,
        left_task=_COMPLETED_TASK,
        left_responses=_OK,
        right_task=_COMPLETED_TASK,
        right_responses=_FAILED,
    )
    projection = _projection_for(tmp_path, monkeypatch, dirs)
    assert projection["eligibility"]["eligible"] is True
    assert projection["classification"]["classification"] == (
        "structurally incomparable"
    )
    assert projection["classification"]["completion_asymmetry"] is True
    # the raw joined asymmetry string from the private report is never projected
    assert "completed/completed; partial/runtime_failure" not in json.dumps(projection)


@pytest.mark.parametrize(
    ("left_task", "right_task", "expected_field", "right_responses"),
    [
        (
            {"feedback": True, "max_turns": 1},
            {"feedback": False, "max_turns": 1},
            "max_feedback_items",
            [("first", "", 0), ("second", "", 0)],
        ),
        (
            {"feedback": False, "max_turns": 1},
            {"feedback": False, "max_turns": 2},
            "effective_max_model_turns",
            [("first", "", 0), ("second", "", 0)],
        ),
        (
            {"feedback": False, "max_turns": 1},
            {"feedback": False, "max_turns": 1, "attempts": 2},
            "max_attempts_per_turn",
            _OK,
        ),
    ],
)
def test_identity_mismatch_is_disclosed_not_fatal(
    tmp_path, monkeypatch, left_task, right_task, expected_field, right_responses
) -> None:
    dirs = _pair(
        tmp_path,
        monkeypatch,
        left_task=left_task,
        left_responses=_OK,
        right_task=right_task,
        right_responses=right_responses,
    )
    out = tmp_path / "public"
    projection = export_public_transcript_comparison(dirs, out)
    assert projection["eligibility"]["eligible"] is False
    assert projection["eligibility"]["mismatched_identity_fields"] == [expected_field]
    assert projection["classification"]["classification"] == (
        "structurally incomparable"
    )
    assert (out / PUBLIC_TRANSCRIPT_COMPARISON_FILENAME).is_file()


# ---------------------------------------------------------------------------
# Model labels and redaction disclosure
# ---------------------------------------------------------------------------


def test_clean_model_label_is_projected(tmp_path, monkeypatch) -> None:
    dirs = _pair(
        tmp_path,
        monkeypatch,
        left_task=_COMPLETED_TASK,
        left_responses=_OK,
        right_task=_COMPLETED_TASK,
        right_responses=_OK,
    )
    projection = _projection_for(tmp_path, monkeypatch, dirs)
    assert [run["model_label"] for run in projection["runs"]] == [
        "test-model",
        "test-model",
    ]
    assert projection["redaction"]["categories"] == []
    assert projection["redaction"]["model_label_substitutions"] == []
    assert projection["redaction"]["policy"] == (
        "content-default-deny-allowlist-projection"
    )


def test_credential_url_model_label_is_redacted(tmp_path, monkeypatch) -> None:
    dirs = _pair(
        tmp_path,
        monkeypatch,
        left_task=_COMPLETED_TASK,
        left_responses=_OK,
        right_task=_COMPLETED_TASK,
        right_responses=_OK,
    )
    _rewrite_result_json(
        dirs[0],
        lambda data: data["model"].__setitem__("model_id", CANARY_URL),
    )
    projection = _projection_for(tmp_path, monkeypatch, dirs)
    run_a = projection["runs"][0]
    assert run_a["model_label"] == "REDACTED_SECRET"
    assert "credential_bearing_url" in projection["redaction"]["categories"]
    assert {"slot": "run-a", "reason": "sanitized_model_label"} in (
        projection["redaction"]["model_label_substitutions"]
    )
    assert CANARY_URL not in json.dumps(projection)
    assert "hunter2" not in json.dumps(projection)


def test_home_path_model_label_is_redacted(tmp_path, monkeypatch) -> None:
    dirs = _pair(
        tmp_path,
        monkeypatch,
        left_task=_COMPLETED_TASK,
        left_responses=_OK,
        right_task=_COMPLETED_TASK,
        right_responses=_OK,
    )
    _rewrite_result_json(
        dirs[1],
        lambda data: data["model"].__setitem__("model_id", CANARY_HOME),
    )
    projection = _projection_for(tmp_path, monkeypatch, dirs)
    assert projection["runs"][1]["model_label"] == "REDACTED_HOME_PATH"
    assert "home_directory_path" in projection["redaction"]["categories"]
    assert "privateuser" not in json.dumps(projection)


def test_full_hash_model_label_is_redacted(tmp_path, monkeypatch) -> None:
    dirs = _pair(
        tmp_path,
        monkeypatch,
        left_task=_COMPLETED_TASK,
        left_responses=_OK,
        right_task=_COMPLETED_TASK,
        right_responses=_OK,
    )
    _rewrite_result_json(
        dirs[0],
        lambda data: data["model"].__setitem__("model_id", CANARY_HASH),
    )
    projection = _projection_for(tmp_path, monkeypatch, dirs)
    assert projection["runs"][0]["model_label"] == "model-REDACTED_FULL_HASH"
    assert "full_local_sha256" in projection["redaction"]["categories"]
    assert not _FULL_HASH_RE.search(json.dumps(projection))


def test_invalid_label_falls_back_positionally(tmp_path, monkeypatch) -> None:
    dirs = _pair(
        tmp_path,
        monkeypatch,
        left_task=_COMPLETED_TASK,
        left_responses=_OK,
        right_task=_COMPLETED_TASK,
        right_responses=_OK,
    )
    _rewrite_result_json(
        dirs[0],
        lambda data: data["model"].__setitem__("model_id", CANARY_SLASH),
    )
    projection = _projection_for(tmp_path, monkeypatch, dirs)
    assert projection["runs"][0]["model_label"] == "Model A"
    assert {"slot": "run-a", "reason": "fallback_positional_label"} in (
        projection["redaction"]["model_label_substitutions"]
    )
    validate_public_projection(projection)


def test_missing_model_section_falls_back(tmp_path, monkeypatch) -> None:
    dirs = _pair(
        tmp_path,
        monkeypatch,
        left_task=_COMPLETED_TASK,
        left_responses=_OK,
        right_task=_COMPLETED_TASK,
        right_responses=_OK,
    )
    _rewrite_result_json(dirs[0], lambda data: data["model"].pop("model_id"))
    projection = _projection_for(tmp_path, monkeypatch, dirs)
    assert projection["runs"][0]["model_label"] == "Model A"


# ---------------------------------------------------------------------------
# Validator fail-closed behavior
# ---------------------------------------------------------------------------


def test_validator_rejects_unknown_keys(tmp_path, monkeypatch) -> None:
    dirs = _pair(
        tmp_path,
        monkeypatch,
        left_task=_COMPLETED_TASK,
        left_responses=_OK,
        right_task=_COMPLETED_TASK,
        right_responses=_OK,
    )
    projection = _projection_for(tmp_path, monkeypatch, dirs)
    projection["runs"][0]["conversation_id"] = "leak"
    with pytest.raises(
        TranscriptPublicExportError,
        match=r"closed-world violation at \$\.runs\[0\]: unexpected keys",
    ):
        validate_public_projection(projection)


def test_validator_rejects_raw_content_strings(tmp_path, monkeypatch) -> None:
    dirs = _pair(
        tmp_path,
        monkeypatch,
        left_task=_COMPLETED_TASK,
        left_responses=_OK,
        right_task=_COMPLETED_TASK,
        right_responses=_OK,
    )
    projection = _projection_for(tmp_path, monkeypatch, dirs)
    projection["runs"][0]["review_hooks"]["correction"] = (
        "the model said: here is your answer"
    )
    with pytest.raises(
        TranscriptPublicExportError,
        match="is not an allowed public value",
    ):
        validate_public_projection(projection)


def test_validator_rejects_absolute_path_strings(tmp_path, monkeypatch) -> None:
    dirs = _pair(
        tmp_path,
        monkeypatch,
        left_task=_COMPLETED_TASK,
        left_responses=_OK,
        right_task=_COMPLETED_TASK,
        right_responses=_OK,
    )
    projection = _projection_for(tmp_path, monkeypatch, dirs)
    projection["runs"][0]["model_label"] = "/home/privateuser/models/x.gguf"
    with pytest.raises(TranscriptPublicExportError, match="model_label"):
        validate_public_projection(projection)


def test_validator_rejects_raw_hash_labels(tmp_path, monkeypatch) -> None:
    dirs = _pair(
        tmp_path,
        monkeypatch,
        left_task=_COMPLETED_TASK,
        left_responses=_OK,
        right_task=_COMPLETED_TASK,
        right_responses=_OK,
    )
    projection = _projection_for(tmp_path, monkeypatch, dirs)
    projection["runs"][0]["model_label"] = "a" * 64
    with pytest.raises(TranscriptPublicExportError, match="model_label"):
        validate_public_projection(projection)


def test_build_requires_exactly_two(tmp_path, monkeypatch) -> None:
    dirs = _pair(
        tmp_path,
        monkeypatch,
        left_task=_COMPLETED_TASK,
        left_responses=_OK,
        right_task=_COMPLETED_TASK,
        right_responses=_OK,
    )
    results, transcripts = load_public_transcript_pair(dirs)
    with pytest.raises(TranscriptPublicExportError, match="exactly two results"):
        build_public_transcript_comparison(results[:1], transcripts[:1])


# ---------------------------------------------------------------------------
# Adversarial canary end-to-end export
# ---------------------------------------------------------------------------


def test_canary_export_leaks_nothing(tmp_path, monkeypatch) -> None:
    left = _run_result(
        tmp_path,
        monkeypatch,
        "left",
        task_kwargs={"feedback": True, "max_turns": 2},
        responses=[(CANARY_STDOUT, CANARY_STDERR, 0), (CANARY_STDOUT, "", 0)],
        conversation_id=CANARY_CONV,
        model_id=CANARY_URL,
        feedback_content=CANARY_FEEDBACK,
    )
    right = _run_result(
        tmp_path,
        monkeypatch,
        "right",
        task_kwargs={"feedback": True, "max_turns": 2},
        responses=[(CANARY_STDOUT, CANARY_STDERR, 1), ("corrected", "", 0)],
        conversation_id="conversation-right",
        model_id=CANARY_HASH,
        feedback_content=CANARY_FEEDBACK,
    )
    out = tmp_path / "public"
    projection = export_public_transcript_comparison([left, right], out)

    canaries = (
        CANARY_URL,
        CANARY_HOME,
        CANARY_HASH,
        CANARY_CONV,
        CANARY_FEEDBACK,
        CANARY_STDOUT,
        CANARY_STDERR,
        "hunter2",
        "sk-canary-feedback-9e7d",
        "sk-canary-out-9e7d",
        "privateuser",
        "secret.txt",
        "host.example.invalid",
        TASK_ID,
        left.name,
        right.name,
    )
    files = sorted(path for path in out.rglob("*") if path.is_file())
    assert sorted(path.name for path in files) == sorted(
        [
            PUBLIC_TRANSCRIPT_COMPARISON_FILENAME,
            PUBLIC_TRANSCRIPT_COMPARISON_REPORT_FILENAME,
        ]
    )
    for path in files:
        text = path.read_text(encoding="utf-8")
        for canary in canaries:
            assert canary not in text, f"canary {canary!r} found in {path.name}"
        assert not _FULL_HASH_RE.search(text), f"full hash found in {path.name}"
        assert "://" not in text
        assert not re.search(r"(?<![A-Za-z0-9_:/#])/(?!/)[A-Za-z0-9._-]", text)
    assert projection["redaction"]["categories"] == [
        "credential_bearing_url",
        "full_local_sha256",
    ]
    # sources are untouched
    assert (
        hashlib.sha256((left / "llmgauge-result.json").read_bytes()).hexdigest()
        != "0" * 64
    )


def test_export_writes_exactly_two_files_and_valid_json(tmp_path, monkeypatch) -> None:
    dirs = _pair(
        tmp_path,
        monkeypatch,
        left_task=_COMPLETED_TASK,
        left_responses=_OK,
        right_task=_COMPLETED_TASK,
        right_responses=_OK,
    )
    out = tmp_path / "public"
    projection = export_public_transcript_comparison(dirs, out)
    files = sorted(path.name for path in out.iterdir())
    assert files == sorted(
        [
            PUBLIC_TRANSCRIPT_COMPARISON_FILENAME,
            PUBLIC_TRANSCRIPT_COMPARISON_REPORT_FILENAME,
        ]
    )
    written = json.loads(
        (out / PUBLIC_TRANSCRIPT_COMPARISON_FILENAME).read_text(encoding="utf-8")
    )
    assert written == json.loads(json.dumps(projection))
    validate_public_projection(written)
    report = (out / PUBLIC_TRANSCRIPT_COMPARISON_REPORT_FILENAME).read_text(
        encoding="utf-8"
    )
    assert "Human review required before publication" in report
    assert "No session aggregate, winner, or quality verdict is computed." in report
    assert "## Run run-a — test-model" in report
    assert "| Sequence | Kind | Role | Execution status | Relationship |" in report
    assert "implies no universal rank" in report


def test_export_accepts_precreated_empty_destination(tmp_path, monkeypatch) -> None:
    dirs = _pair(
        tmp_path,
        monkeypatch,
        left_task=_COMPLETED_TASK,
        left_responses=_OK,
        right_task=_COMPLETED_TASK,
        right_responses=_OK,
    )
    out = tmp_path / "public"
    out.mkdir()
    export_public_transcript_comparison(dirs, out)
    assert (out / PUBLIC_TRANSCRIPT_COMPARISON_FILENAME).is_file()


def test_export_failure_removes_staging(tmp_path, monkeypatch) -> None:
    dirs = _pair(
        tmp_path,
        monkeypatch,
        left_task=_COMPLETED_TASK,
        left_responses=_OK,
        right_task=_COMPLETED_TASK,
        right_responses=_OK,
    )
    out = tmp_path / "public"

    def explode(projection: dict[str, Any]) -> str:
        raise RuntimeError("renderer failed")

    monkeypatch.setattr(tpe, "render_public_transcript_comparison_markdown", explode)
    with pytest.raises(RuntimeError, match="renderer failed"):
        export_public_transcript_comparison(dirs, out)
    assert not out.exists()
    assert not list(tmp_path.glob(".llmgauge-public-export-*"))


# ---------------------------------------------------------------------------
# Fail-closed admission
# ---------------------------------------------------------------------------


def test_single_directory_fails_closed(tmp_path, monkeypatch) -> None:
    dirs = _pair(
        tmp_path,
        monkeypatch,
        left_task=_COMPLETED_TASK,
        left_responses=_OK,
        right_task=_COMPLETED_TASK,
        right_responses=_OK,
    )
    out = tmp_path / "public"
    with pytest.raises(
        TranscriptPublicExportError, match="exactly two result directories"
    ):
        export_public_transcript_comparison(dirs[:1], out)
    assert not out.exists()


def test_missing_directory_fails_closed(tmp_path, monkeypatch) -> None:
    dirs = _pair(
        tmp_path,
        monkeypatch,
        left_task=_COMPLETED_TASK,
        left_responses=_OK,
        right_task=_COMPLETED_TASK,
        right_responses=_OK,
    )
    with pytest.raises(TranscriptPublicExportError, match="Missing result directory"):
        export_public_transcript_comparison(
            [dirs[0], tmp_path / "nope"], tmp_path / "public"
        )


def test_non_transcript_result_fails_closed(tmp_path, monkeypatch) -> None:
    dirs = _pair(
        tmp_path,
        monkeypatch,
        left_task=_COMPLETED_TASK,
        left_responses=_OK,
        right_task=_COMPLETED_TASK,
        right_responses=_OK,
    )
    flat = _write_run(tmp_path)
    with pytest.raises(
        TranscriptPublicExportError, match="requires transcript-bearing results"
    ):
        export_public_transcript_comparison([dirs[0], flat], tmp_path / "public")


def test_mutated_transcript_fails_closed(tmp_path, monkeypatch) -> None:
    dirs = _pair(
        tmp_path,
        monkeypatch,
        left_task=_COMPLETED_TASK,
        left_responses=_OK,
        right_task=_COMPLETED_TASK,
        right_responses=_OK,
    )
    tampered = _copy_result(tmp_path, dirs[1], "tampered")
    transcript_path = tampered / "transcript" / "transcript.json"
    data = json.loads(transcript_path.read_text(encoding="utf-8"))
    data["completion_state"] = "abandoned"
    transcript_path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(TranscriptPublicExportError, match="validation failed"):
        export_public_transcript_comparison([dirs[0], tampered], tmp_path / "public")


def test_imported_evidence_fails_closed(tmp_path, monkeypatch) -> None:
    dirs = _pair(
        tmp_path,
        monkeypatch,
        left_task=_COMPLETED_TASK,
        left_responses=_OK,
        right_task=_COMPLETED_TASK,
        right_responses=_OK,
    )
    imported = _copy_result(tmp_path, dirs[1], "imported")
    _rewrite_result_json(
        imported,
        lambda data: data.__setitem__(
            "agent_harness_evidence",
            {
                "schema_version": "llmgauge.agent_harness_evidence.v0",
                "contract_version": "0.1.0",
                "evidence_class": "external_agent_environment",
                "evidence_id": "sha256:" + "a" * 64,
                "path": "agent-harness/evidence.json",
                "sha256": "b" * 64,
            },
        ),
    )
    out = tmp_path / "public"
    with pytest.raises(TranscriptPublicExportError):
        export_public_transcript_comparison([dirs[0], imported], out)
    assert not out.exists()


def test_destination_equals_source_fails_closed(tmp_path, monkeypatch) -> None:
    dirs = _pair(
        tmp_path,
        monkeypatch,
        left_task=_COMPLETED_TASK,
        left_responses=_OK,
        right_task=_COMPLETED_TASK,
        right_responses=_OK,
    )
    with pytest.raises(TranscriptPublicExportError, match="must differ"):
        export_public_transcript_comparison(dirs, dirs[0])


def test_destination_inside_source_fails_closed(tmp_path, monkeypatch) -> None:
    dirs = _pair(
        tmp_path,
        monkeypatch,
        left_task=_COMPLETED_TASK,
        left_responses=_OK,
        right_task=_COMPLETED_TASK,
        right_responses=_OK,
    )
    with pytest.raises(TranscriptPublicExportError, match="inside"):
        export_public_transcript_comparison(dirs, dirs[0] / "public")


def test_nonempty_destination_fails_closed(tmp_path, monkeypatch) -> None:
    dirs = _pair(
        tmp_path,
        monkeypatch,
        left_task=_COMPLETED_TASK,
        left_responses=_OK,
        right_task=_COMPLETED_TASK,
        right_responses=_OK,
    )
    out = tmp_path / "public"
    out.mkdir()
    (out / "existing.txt").write_text("keep", encoding="utf-8")
    with pytest.raises(TranscriptPublicExportError, match="Refusing to overwrite"):
        export_public_transcript_comparison(dirs, out)
    assert (out / "existing.txt").read_text(encoding="utf-8") == "keep"


def test_file_destination_fails_closed(tmp_path, monkeypatch) -> None:
    dirs = _pair(
        tmp_path,
        monkeypatch,
        left_task=_COMPLETED_TASK,
        left_responses=_OK,
        right_task=_COMPLETED_TASK,
        right_responses=_OK,
    )
    out = tmp_path / "public"
    out.write_text("not a directory", encoding="utf-8")
    with pytest.raises(TranscriptPublicExportError, match="not a directory"):
        export_public_transcript_comparison(dirs, out)


def test_single_run_public_export_still_fails_closed(tmp_path, monkeypatch) -> None:
    dirs = _pair(
        tmp_path,
        monkeypatch,
        left_task=_COMPLETED_TASK,
        left_responses=_OK,
        right_task=_COMPLETED_TASK,
        right_responses=_OK,
    )
    with pytest.raises(ValueError, match="public export is not implemented"):
        export_public_run(dirs[0], tmp_path / "exported")


# ---------------------------------------------------------------------------
# CLI surface
# ---------------------------------------------------------------------------


def test_cli_success(tmp_path, monkeypatch) -> None:
    dirs = _pair(
        tmp_path,
        monkeypatch,
        left_task=_COMPLETED_TASK,
        left_responses=_OK,
        right_task=_COMPLETED_TASK,
        right_responses=_OK,
    )
    out = tmp_path / "public"
    exit_code = runner.invoke(
        cli.app,
        ["export-public-comparison", str(dirs[0]), str(dirs[1]), "--out", str(out)],
    )
    assert exit_code.exit_code == 0, exit_code.output
    assert "Wrote public transcript comparison" in exit_code.output
    assert "Review the public export before publication" in exit_code.output
    assert (out / PUBLIC_TRANSCRIPT_COMPARISON_FILENAME).is_file()
    assert (out / PUBLIC_TRANSCRIPT_COMPARISON_REPORT_FILENAME).is_file()


def test_cli_failure_writes_nothing(tmp_path, monkeypatch) -> None:
    dirs = _pair(
        tmp_path,
        monkeypatch,
        left_task=_COMPLETED_TASK,
        left_responses=_OK,
        right_task=_COMPLETED_TASK,
        right_responses=_OK,
    )
    out = tmp_path / "public"
    exit_code = runner.invoke(
        cli.app,
        [
            "export-public-comparison",
            str(dirs[0]),
            str(tmp_path / "nope"),
            "--out",
            str(out),
        ],
    )
    assert exit_code.exit_code == 1
    assert "Public comparison export failed" in exit_code.output
    assert not out.exists()


def test_cli_requires_two_arguments(tmp_path) -> None:
    exit_code = runner.invoke(
        cli.app, ["export-public-comparison", str(tmp_path), "--out", str(tmp_path)]
    )
    assert exit_code.exit_code != 0


# ---------------------------------------------------------------------------
# Renderer boundary
# ---------------------------------------------------------------------------


def test_report_renders_only_projected_facts(tmp_path, monkeypatch) -> None:
    dirs = _pair(
        tmp_path,
        monkeypatch,
        left_task=_COMPLETED_TASK,
        left_responses=_OK,
        right_task=_COMPLETED_TASK,
        right_responses=_FAILED,
    )
    projection = _projection_for(tmp_path, monkeypatch, dirs)
    report = render_public_transcript_comparison_markdown(projection)
    assert "- Completion asymmetry: the pair terminates" in report
    assert "- Eligible for like-for-like comparison: yes" in report
    assert "- Comparison basis (all fields must match)" in report
    assert "- Omitted field classes:" in report
    assert "scores" in report
    assert "the final answer text" not in report  # no response content in the report


# ---------------------------------------------------------------------------
# Single-run native transcript public derivative
# ---------------------------------------------------------------------------

_SINGLE_TOP_KEYS = {
    "schema_version",
    "generated_by",
    "created_at_utc",
    "source_class",
    "transcript_schema",
    "protocol",
    "producer",
    "limits",
    "run",
    "redaction",
    "claim_boundary",
    "human_review_required_before_publication",
}
_SINGLE_NESTED = {
    key: value
    for key, value in _NESTED.items()
    if key not in {"eligibility", "classification", "runs", "redaction"}
} | {
    "protocol": {"protocol_id", "protocol_version"},
    "producer": {"producer_id", "producer_version"},
    "limits": {
        "effective_max_model_turns",
        "max_attempts_per_turn",
        "max_feedback_items",
    },
    "run": _NESTED["runs"],
    "redaction": _NESTED["redaction"]
    | {"raw_transcript_content_included", "private_identifiers_included"},
}


def _walk_single_keys(node: Any, key: str | None, path: str) -> None:
    if isinstance(node, dict):
        allowed = (
            _SINGLE_TOP_KEYS if path == "$" else _SINGLE_NESTED.get(key or "", set())
        )
        assert set(node) <= allowed, f"unexpected keys at {path}: {sorted(node)}"
        for child_key, child in node.items():
            _walk_single_keys(child, child_key, f"{path}.{child_key}")
        return
    if isinstance(node, list):
        for index, item in enumerate(node):
            _walk_single_keys(item, key, f"{path}[{index}]")


def _single(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, **kwargs: Any) -> Path:
    kwargs.setdefault("task_kwargs", _COMPLETED_TASK)
    kwargs.setdefault("responses", _OK)
    kwargs.setdefault("conversation_id", "conversation-single")
    return _run_result(tmp_path, monkeypatch, "single", **kwargs)


def _single_projection_for(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    directory: Path,
) -> dict[str, Any]:
    result, transcript = load_public_transcript_result(directory)
    return build_public_transcript(result, transcript)


def test_single_projection_is_closed_world(tmp_path, monkeypatch) -> None:
    directory = _single(
        tmp_path,
        monkeypatch,
        task_kwargs={"feedback": True, "max_turns": 2},
        responses=[("first", "", 0), ("corrected", "", 0)],
    )
    projection = _single_projection_for(tmp_path, monkeypatch, directory)
    _walk_single_keys(projection, None, "$")
    validate_public_transcript_projection(projection)
    assert projection["schema_version"] == PUBLIC_TRANSCRIPT_SCHEMA_VERSION
    assert projection["generated_by"] == "llmgauge"
    assert projection["source_class"] == "native_multi_turn_response"
    assert projection["transcript_schema"] == "llmgauge.transcript.v0"
    assert projection["protocol"] == {
        "protocol_id": "llmgauge.sequential_supplied_feedback",
        "protocol_version": "0.1.0",
    }
    assert projection["producer"]["producer_id"] == "llmgauge"
    assert re.fullmatch(r"\d+\.\d+\.\d+", projection["producer"]["producer_version"])
    assert projection["limits"] == {
        "effective_max_model_turns": 2,
        "max_attempts_per_turn": 1,
        "max_feedback_items": 1,
    }
    assert projection["run"]["slot"] == "run"
    assert projection["run"]["model_label"] == "test-model"
    assert projection["redaction"]["raw_transcript_content_included"] is False
    assert projection["redaction"]["private_identifiers_included"] is False
    assert (
        projection["redaction"]["omitted_field_classes"].count(
            "result_provenance_and_run_fingerprint"
        )
        == 1
    )
    assert (
        "producer_version_and_result_provenance"
        not in (projection["redaction"]["omitted_field_classes"])
    )
    assert projection["human_review_required_before_publication"] is True


def test_single_run_partial_completion_projection(tmp_path, monkeypatch) -> None:
    directory = _single(tmp_path, monkeypatch, responses=_FAILED)
    projection = _single_projection_for(tmp_path, monkeypatch, directory)
    run = projection["run"]
    assert run["completion"]["completion_state"] == "partial"
    assert run["attempt_states"][0]["attempt_state"] == "failed"
    assert run["attempt_states"][0]["exit_status"] == 1
    validate_public_transcript_projection(projection)


def test_single_run_carries_no_identity_values(tmp_path, monkeypatch) -> None:
    directory = _single(tmp_path, monkeypatch)
    projection = _single_projection_for(tmp_path, monkeypatch, directory)
    encoded = json.dumps(projection)
    strings = set(re.findall(r'"([^"]*)"', encoded))
    transcript = load_transcript(directory)
    for value in (
        transcript.conversation_id,
        transcript.task_id,
        transcript.initial_state_id,
        transcript.suite_id,
    ):
        assert value not in strings
    assert "conversation-single" not in encoded
    assert directory.name not in encoded
    assert TASK_ID not in encoded
    assert not _FULL_HASH_RE.search(encoded)
    for event in projection["run"]["event_order"]:
        assert isinstance(event["sequence"], int)


def test_single_and_comparison_share_projection(tmp_path, monkeypatch) -> None:
    dirs = _pair(
        tmp_path,
        monkeypatch,
        left_task={"feedback": True, "max_turns": 2},
        left_responses=[("first", "", 0), ("corrected", "", 0)],
        right_task={"feedback": True, "max_turns": 2},
        right_responses=[("first", "", 0), ("corrected", "", 0)],
    )
    comparison = _projection_for(tmp_path, monkeypatch, dirs)
    single = _single_projection_for(tmp_path, monkeypatch, dirs[0])
    left = dict(comparison["runs"][0])
    run = dict(single["run"])
    left.pop("slot")
    run.pop("slot")
    # same private fact, same public interpretation
    assert run == left


def test_single_model_label_sanitization(tmp_path, monkeypatch) -> None:
    directory = _single(tmp_path, monkeypatch, model_id=CANARY_URL)
    projection = _single_projection_for(tmp_path, monkeypatch, directory)
    assert projection["run"]["model_label"] == "REDACTED_SECRET"
    assert "credential_bearing_url" in projection["redaction"]["categories"]
    assert {
        "slot": "run",
        "reason": "sanitized_model_label",
    } in projection["redaction"]["model_label_substitutions"]
    assert CANARY_URL not in json.dumps(projection)
    validate_public_transcript_projection(projection)


def test_single_model_label_falls_back_to_model(tmp_path, monkeypatch) -> None:
    directory = _single(tmp_path, monkeypatch, model_id=CANARY_SLASH)
    projection = _single_projection_for(tmp_path, monkeypatch, directory)
    assert projection["run"]["model_label"] == "Model"
    assert {
        "slot": "run",
        "reason": "fallback_positional_label",
    } in projection["redaction"]["model_label_substitutions"]
    validate_public_transcript_projection(projection)


def test_single_validator_rejects_unknown_keys(tmp_path, monkeypatch) -> None:
    directory = _single(tmp_path, monkeypatch)
    projection = _single_projection_for(tmp_path, monkeypatch, directory)
    projection["conversation_id"] = "leak"
    with pytest.raises(
        TranscriptPublicExportError,
        match=r"closed-world violation at \$: unexpected keys",
    ):
        validate_public_transcript_projection(projection)


def test_single_validator_rejects_raw_content_strings(tmp_path, monkeypatch) -> None:
    directory = _single(tmp_path, monkeypatch)
    projection = _single_projection_for(tmp_path, monkeypatch, directory)
    projection["run"]["review_hooks"]["correction"] = "the model said: fix it"
    with pytest.raises(
        TranscriptPublicExportError, match="is not an allowed public value"
    ):
        validate_public_transcript_projection(projection)


def test_single_validator_rejects_non_numeric_producer_version(
    tmp_path, monkeypatch
) -> None:
    directory = _single(tmp_path, monkeypatch)
    projection = _single_projection_for(tmp_path, monkeypatch, directory)
    projection["producer"]["producer_version"] = "0.75.0-custom+build9"
    with pytest.raises(TranscriptPublicExportError, match="producer_version"):
        validate_public_transcript_projection(projection)


def test_single_validator_rejects_raw_hash_labels(tmp_path, monkeypatch) -> None:
    directory = _single(tmp_path, monkeypatch)
    projection = _single_projection_for(tmp_path, monkeypatch, directory)
    projection["run"]["model_label"] = "b" * 64
    with pytest.raises(TranscriptPublicExportError, match="model_label"):
        validate_public_transcript_projection(projection)


def test_single_canary_export_leaks_nothing(tmp_path, monkeypatch) -> None:
    directory = _single(
        tmp_path,
        monkeypatch,
        task_kwargs={"feedback": True, "max_turns": 2},
        responses=[(CANARY_STDOUT, CANARY_STDERR, 0), (CANARY_STDOUT, "", 0)],
        conversation_id=CANARY_CONV,
        model_id=CANARY_URL,
        feedback_content=CANARY_FEEDBACK,
    )
    out = tmp_path / "public"
    projection = export_public_transcript(directory, out)

    canaries = (
        CANARY_URL,
        CANARY_HOME,
        CANARY_HASH,
        CANARY_CONV,
        CANARY_FEEDBACK,
        CANARY_STDOUT,
        CANARY_STDERR,
        "hunter2",
        "sk-canary-feedback-9e7d",
        "sk-canary-out-9e7d",
        "privateuser",
        "secret.txt",
        "host.example.invalid",
        TASK_ID,
        directory.name,
    )
    files = sorted(path for path in out.rglob("*") if path.is_file())
    assert sorted(path.name for path in files) == sorted(
        [PUBLIC_TRANSCRIPT_FILENAME, PUBLIC_TRANSCRIPT_REPORT_FILENAME]
    )
    for path in files:
        text = path.read_text(encoding="utf-8")
        for canary in canaries:
            assert canary not in text, f"canary {canary!r} found in {path.name}"
        assert not _FULL_HASH_RE.search(text), f"full hash found in {path.name}"
        assert "://" not in text
        assert not re.search(r"(?<![A-Za-z0-9_:/#])/(?!/)[A-Za-z0-9._-]", text)
    assert projection["redaction"]["categories"] == ["credential_bearing_url"]
    assert projection["run"]["model_label"] == "REDACTED_SECRET"
    # the source result is untouched
    assert (directory / "llmgauge-result.json").is_file()


def test_single_export_writes_exactly_two_files_and_valid_json(
    tmp_path, monkeypatch
) -> None:
    directory = _single(tmp_path, monkeypatch)
    out = tmp_path / "public"
    projection = export_public_transcript(directory, out)
    files = sorted(path.name for path in out.iterdir())
    assert files == sorted(
        [PUBLIC_TRANSCRIPT_FILENAME, PUBLIC_TRANSCRIPT_REPORT_FILENAME]
    )
    written = json.loads((out / PUBLIC_TRANSCRIPT_FILENAME).read_text(encoding="utf-8"))
    assert written == json.loads(json.dumps(projection))
    validate_public_transcript_projection(written)
    report = (out / PUBLIC_TRANSCRIPT_REPORT_FILENAME).read_text(encoding="utf-8")
    assert "Human review required before publication" in report
    assert (
        "No session aggregate, score, winner, or quality verdict is computed." in report
    )
    assert "## Run — test-model" in report
    assert "| Sequence | Kind | Role | Execution status | Relationship |" in report
    assert "implies no universal rank" in report
    assert "the final answer text" not in report


def test_single_export_accepts_precreated_empty_destination(
    tmp_path, monkeypatch
) -> None:
    directory = _single(tmp_path, monkeypatch)
    out = tmp_path / "public"
    out.mkdir()
    export_public_transcript(directory, out)
    assert (out / PUBLIC_TRANSCRIPT_FILENAME).is_file()


def test_single_export_failure_removes_staging(tmp_path, monkeypatch) -> None:
    directory = _single(tmp_path, monkeypatch)
    out = tmp_path / "public"

    def explode(projection: dict[str, Any]) -> str:
        raise RuntimeError("renderer failed")

    monkeypatch.setattr(tpe, "render_public_transcript_markdown", explode)
    with pytest.raises(RuntimeError, match="renderer failed"):
        export_public_transcript(directory, out)
    assert not out.exists()
    assert not list(tmp_path.glob(".llmgauge-public-export-*"))


def test_single_missing_directory_fails_closed(tmp_path) -> None:
    out = tmp_path / "public"
    with pytest.raises(TranscriptPublicExportError, match="Missing result directory"):
        export_public_transcript(tmp_path / "nope", out)
    assert not out.exists()


def test_single_non_transcript_result_fails_closed(tmp_path) -> None:
    flat = _write_run(tmp_path)
    with pytest.raises(
        TranscriptPublicExportError, match="requires a transcript-bearing result"
    ):
        export_public_transcript(flat, tmp_path / "public")


def test_single_mutated_transcript_fails_closed(tmp_path, monkeypatch) -> None:
    directory = _single(tmp_path, monkeypatch)
    tampered = _copy_result(tmp_path, directory, "tampered")
    transcript_path = tampered / "transcript" / "transcript.json"
    data = json.loads(transcript_path.read_text(encoding="utf-8"))
    data["completion_state"] = "abandoned"
    transcript_path.write_text(json.dumps(data), encoding="utf-8")
    out = tmp_path / "public"
    with pytest.raises(TranscriptPublicExportError, match="validation failed"):
        export_public_transcript(tampered, out)
    assert not out.exists()


def test_single_imported_evidence_fails_closed(tmp_path, monkeypatch) -> None:
    directory = _single(tmp_path, monkeypatch)
    imported = _copy_result(tmp_path, directory, "imported")
    _rewrite_result_json(
        imported,
        lambda data: data.__setitem__(
            "agent_harness_evidence",
            {
                "schema_version": "llmgauge.agent_harness_evidence.v0",
                "contract_version": "0.1.0",
                "evidence_class": "external_agent_environment",
                "evidence_id": "sha256:" + "a" * 64,
                "path": "agent-harness/evidence.json",
                "sha256": "b" * 64,
            },
        ),
    )
    out = tmp_path / "public"
    with pytest.raises(TranscriptPublicExportError):
        export_public_transcript(imported, out)
    assert not out.exists()


def test_single_destination_equals_source_fails_closed(tmp_path, monkeypatch) -> None:
    directory = _single(tmp_path, monkeypatch)
    with pytest.raises(TranscriptPublicExportError, match="must differ"):
        export_public_transcript(directory, directory)


def test_single_destination_inside_source_fails_closed(tmp_path, monkeypatch) -> None:
    directory = _single(tmp_path, monkeypatch)
    with pytest.raises(TranscriptPublicExportError, match="inside"):
        export_public_transcript(directory, directory / "public")


def test_single_nonempty_destination_fails_closed(tmp_path, monkeypatch) -> None:
    directory = _single(tmp_path, monkeypatch)
    out = tmp_path / "public"
    out.mkdir()
    (out / "existing.txt").write_text("keep", encoding="utf-8")
    with pytest.raises(TranscriptPublicExportError, match="Refusing to overwrite"):
        export_public_transcript(directory, out)
    assert (out / "existing.txt").read_text(encoding="utf-8") == "keep"


def test_single_file_destination_fails_closed(tmp_path, monkeypatch) -> None:
    directory = _single(tmp_path, monkeypatch)
    out = tmp_path / "public"
    out.write_text("not a directory", encoding="utf-8")
    with pytest.raises(TranscriptPublicExportError, match="not a directory"):
        export_public_transcript(directory, out)


def test_single_cli_success(tmp_path, monkeypatch) -> None:
    directory = _single(tmp_path, monkeypatch)
    out = tmp_path / "public"
    exit_code = runner.invoke(
        cli.app,
        ["export-public-transcript", str(directory), "--out", str(out)],
    )
    assert exit_code.exit_code == 0, exit_code.output
    assert "Wrote public transcript derivative" in exit_code.output
    assert "Review the public export before publication" in exit_code.output
    assert (out / PUBLIC_TRANSCRIPT_FILENAME).is_file()
    assert (out / PUBLIC_TRANSCRIPT_REPORT_FILENAME).is_file()


def test_single_cli_failure_writes_nothing(tmp_path) -> None:
    out = tmp_path / "public"
    exit_code = runner.invoke(
        cli.app,
        ["export-public-transcript", str(tmp_path / "nope"), "--out", str(out)],
    )
    assert exit_code.exit_code == 1
    assert "Public transcript export failed" in exit_code.output
    assert not out.exists()


def test_single_report_renders_only_projected_facts(tmp_path, monkeypatch) -> None:
    directory = _single(
        tmp_path,
        monkeypatch,
        task_kwargs={"feedback": False, "max_turns": 1, "attempts": 2},
        responses=[
            ("partial response body", "runtime exploded", 1),
            ("corrected", "", 0),
        ],
    )
    projection = _single_projection_for(tmp_path, monkeypatch, directory)
    report = render_public_transcript_markdown(projection)
    assert "## Run — test-model" in report
    assert "- Completion: `completed`" in report
    assert "### Review hooks (as recorded; not answer-quality validation)" in report
    assert "- Omitted field classes:" in report
    assert "result_provenance_and_run_fingerprint" in report
    assert "partial response body" not in report
    assert "runtime exploded" not in report
    assert "conversation-single" not in report
