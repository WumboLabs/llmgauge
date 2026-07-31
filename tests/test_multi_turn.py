from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

import llmgauge.cli as cli
from llmgauge.commands import run_helpers
from llmgauge.core.multi_turn import (
    ArtifactReference,
    BranchRecord,
    FeedbackEvent,
    FeedbackPlanItem,
    ModelAttemptEvent,
    ModelInvocationResult,
    MultiTurnTask,
    StateEvent,
    TerminalEvent,
    Transcript,
    TranscriptDefinitionError,
    build_result_transcript_reference,
    execute_native_conversation,
    load_multi_turn_task,
    load_transcript,
    validate_result_transcript,
    validate_transcript_artifacts,
    validate_transcript_structure,
    write_transcript,
)
from llmgauge.core.result_validation import validate_result_dir
from llmgauge.core.run_fingerprint import run_fingerprint_value
from llmgauge.runners.vllm_external import (
    VllmReadinessResult,
    VllmRequestResult,
)

runner = CliRunner()
TASK_ID = "tool-honesty/fake-tool-resistance"


def _task_data(
    *,
    feedback: bool = True,
    max_turns: int = 2,
    attempts: int = 1,
    feedback_after_turn: int = 1,
) -> dict[str, Any]:
    return {
        "schema_version": "llmgauge.multi_turn_task.v0",
        "protocol_id": "llmgauge.sequential_supplied_feedback",
        "protocol_version": "0.1.0",
        "task_id": TASK_ID,
        "task_version": "0.1.0",
        "initial_state_id": "initial-state",
        "limits": {
            "max_model_turns": max_turns,
            "max_attempts_per_turn": attempts,
            "max_feedback_items": 1 if feedback else 0,
            "per_turn_timeout_seconds": 10,
        },
        "feedback": (
            [
                {
                    "feedback_id": "feedback-1",
                    "content": "The first response missed the stated constraint.",
                    "origin": "synthetic_test",
                    "after_model_turn": feedback_after_turn,
                }
            ]
            if feedback
            else []
        ),
    }


def _write_task(path: Path, **kwargs: Any) -> Path:
    path.write_text(json.dumps(_task_data(**kwargs)), encoding="utf-8")
    return path


def _invoke_from(values: list[ModelInvocationResult]):
    iterator: Iterator[ModelInvocationResult] = iter(values)
    prompts: list[str] = []

    def invoke(prompt: str, timeout: float) -> ModelInvocationResult:
        assert timeout == 10
        prompts.append(prompt)
        return next(iterator)

    return invoke, prompts


def _conversation(
    tmp_path: Path,
    *,
    feedback: bool = True,
    max_turns: int = 2,
    attempts: int = 1,
    feedback_after_turn: int = 1,
    responses: list[ModelInvocationResult] | None = None,
    max_turns_override: int | None = None,
):
    task = MultiTurnTask.model_validate(
        _task_data(
            feedback=feedback,
            max_turns=max_turns,
            attempts=attempts,
            feedback_after_turn=feedback_after_turn,
        )
    )
    if responses is None:
        responses = [
            ModelInvocationResult(stdout="first answer", stderr="", exit_status=0),
            ModelInvocationResult(stdout="corrected answer", stderr="", exit_status=0),
        ]
    invoke, prompts = _invoke_from(responses)
    outcome = execute_native_conversation(
        task=task,
        conversation_id="conversation-1",
        suite_id="agent-backend-v1",
        suite_version="0.1.0",
        initial_message="Initial exact task",
        invoke=invoke,
        result_dir=tmp_path,
        max_turns=max_turns_override,
    )
    return outcome, prompts


def _model_events(transcript: Transcript) -> list[ModelAttemptEvent]:
    return [
        event for event in transcript.events if isinstance(event, ModelAttemptEvent)
    ]


def _feedback_event(transcript: Transcript) -> FeedbackEvent:
    return next(
        event for event in transcript.events if isinstance(event, FeedbackEvent)
    )


def _feedback_plan_item(transcript: Transcript) -> FeedbackPlanItem:
    assert len(transcript.feedback_plan) == 1
    return transcript.feedback_plan[0]


def _terminal_event(transcript: Transcript) -> TerminalEvent:
    return next(
        event for event in transcript.events if isinstance(event, TerminalEvent)
    )


def _resolved(backend: str = "llama.cpp") -> dict[str, Any]:
    resolved: dict[str, Any] = {
        "model_id": "test-model",
        "model_profile": "test-profile",
        "profile": {
            "label": "Test Model",
            "family": "Test",
            "role": "test",
            "quant": "test",
        },
        "config_path": None,
        "model_profiles_path": None,
        "model_path": Path("/models/test.gguf"),
        "llama_cli": Path("/bin/llama-cli"),
        "ctx": 8192,
        "max_tokens": 64,
        "temp": 0.2,
        "top_p": 0.95,
        "batch": 256,
        "ubatch": 64,
        "gpu_layers": 999,
        "flash_attn": "auto",
        "runtime_label": None,
        "reasoning_mode": "off",
        "model_source": "model_profile",
        "vram_min_headroom_warn_mib": None,
        "backend": backend,
    }
    if backend == "vllm":
        resolved.update(
            vllm_endpoint="http://127.0.0.1:8000/v1",
            served_model="test-served-model",
            connect_timeout=5.0,
            request_timeout=20.0,
            max_response_bytes=100_000,
        )
    return resolved


def _patch_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        run_helpers,
        "collect_model_provenance",
        lambda *args, **kwargs: {
            "source_type": "model_profile",
            "filename": "test.gguf",
            "file_size_bytes": 5,
            "sha256": "a" * 64,
            "public_fingerprint": "sha256:aaaaaaaaaaaaaaaa",
            "status": "available",
        },
    )
    monkeypatch.setattr(
        run_helpers,
        "collect_backend_provenance",
        lambda *args, **kwargs: {
            "backend_name": "llama.cpp",
            "executable_filename": "llama-cli",
            "executable_file_size_bytes": 11,
            "executable_sha256": "b" * 64,
            "public_executable_fingerprint": "sha256:bbbbbbbbbbbbbbbb",
            "status": "available",
        },
    )
    monkeypatch.setattr(
        run_helpers,
        "discover_llama_runtime_identity",
        lambda *args, **kwargs: {
            "reported_version": "b1234",
            "commit": "abcdef1",
            "build_number": "1234",
            "build_type": None,
            "build_metadata": "gcc",
            "discovery_status": "available",
        },
    )


def test_valid_minimal_transcript(tmp_path: Path) -> None:
    outcome, prompts = _conversation(
        tmp_path,
        feedback=False,
        max_turns=1,
        responses=[ModelInvocationResult(stdout="answer", stderr="", exit_status=0)],
    )

    assert outcome.transcript.completion_state == "completed"
    assert prompts == ["Initial exact task"]
    assert _model_events(outcome.transcript)[0].exit_status == 0
    assert validate_transcript_structure(outcome.transcript) == []
    assert validate_transcript_artifacts(tmp_path, outcome.transcript) == []
    assert load_transcript(tmp_path) == outcome.transcript


def test_completed_two_turn_transcript_preserves_exact_feedback_order(
    tmp_path: Path,
) -> None:
    outcome, prompts = _conversation(tmp_path)
    events = outcome.transcript.events
    attempts = _model_events(outcome.transcript)

    assert [event.kind for event in events] == [
        "task",
        "state",
        "model_attempt",
        "state",
        "feedback",
        "state",
        "model_attempt",
        "state",
        "terminal",
    ]
    assert prompts[0] == "Initial exact task"
    assert "first answer" in prompts[1]
    assert "SUPPLIED INERT FEEDBACK feedback-1" in prompts[1]
    planned = _feedback_plan_item(outcome.transcript)
    assert planned.lifecycle_state == "consumed"
    assert planned.consumed_by_turn_id == attempts[1].turn_id
    assert attempts[1].relationship == "recovery"
    assert attempts[1].recovery_of_feedback_ids == ["feedback-1"]
    assert outcome.transcript.final_response_event_id == attempts[1].event_id


def test_retry_and_failed_first_attempt_are_retained(tmp_path: Path) -> None:
    outcome, prompts = _conversation(
        tmp_path,
        attempts=2,
        responses=[
            ModelInvocationResult(stdout="partial", stderr="failed", exit_status=1),
            ModelInvocationResult(stdout="first answer", stderr="", exit_status=0),
            ModelInvocationResult(stdout="corrected", stderr="", exit_status=0),
        ],
    )
    attempts = _model_events(outcome.transcript)

    assert [event.attempt_state for event in attempts] == [
        "failed",
        "completed",
        "completed",
    ]
    assert [event.exit_status for event in attempts] == [1, 0, 0]
    assert attempts[1].relationship == "retry"
    assert attempts[1].retry_of_event_id == attempts[0].event_id
    assert attempts[0].turn_id == attempts[1].turn_id
    assert attempts[0].attempt_id != attempts[1].attempt_id
    assert attempts[0].input_state_id == attempts[1].input_state_id
    assert attempts[0].consumed_feedback_ids == attempts[1].consumed_feedback_ids
    assert attempts[0].raw_input.path != attempts[1].raw_input.path
    assert attempts[0].raw_output.path != attempts[1].raw_output.path
    assert attempts[0].raw_output.path is not None
    assert prompts[0] == prompts[1]
    assert outcome.failed_attempts == 1


def test_recovery_retry_shares_logical_turn_and_preserves_attempts(
    tmp_path: Path,
) -> None:
    outcome, prompts = _conversation(
        tmp_path,
        attempts=2,
        responses=[
            ModelInvocationResult(stdout="first answer", stderr="", exit_status=0),
            ModelInvocationResult(
                stdout="failed recovery bytes",
                stderr="recovery failed",
                exit_status=7,
            ),
            ModelInvocationResult(
                stdout="corrected answer",
                stderr="retry diagnostic",
                exit_status=0,
            ),
        ],
    )
    attempts = _model_events(outcome.transcript)
    failed_recovery, successful_retry = attempts[1:]

    assert [event.attempt_state for event in attempts] == [
        "completed",
        "failed",
        "completed",
    ]
    assert [event.exit_status for event in attempts] == [0, 7, 0]
    assert failed_recovery.relationship == "recovery"
    assert successful_retry.relationship == "retry"
    assert successful_retry.retry_of_event_id == failed_recovery.event_id
    assert failed_recovery.turn_id == successful_retry.turn_id
    assert failed_recovery.attempt_id != successful_retry.attempt_id
    planned = _feedback_plan_item(outcome.transcript)
    assert planned.lifecycle_state == "consumed"
    assert planned.consumed_by_turn_id == failed_recovery.turn_id
    assert failed_recovery.consumed_feedback_ids == ["feedback-1"]
    assert successful_retry.consumed_feedback_ids == ["feedback-1"]
    assert failed_recovery.input_state_id == successful_retry.input_state_id
    assert len({event.attempt_id for event in attempts}) == len(attempts)
    assert len({event.raw_input.path for event in attempts}) == len(attempts)
    assert len({event.raw_output.path for event in attempts}) == len(attempts)
    assert len({event.runtime_stderr.path for event in attempts}) == len(attempts)
    assert all(
        (tmp_path / event.raw_input.path).is_file()
        and (tmp_path / event.raw_output.path).is_file()
        and (tmp_path / event.runtime_stderr.path).is_file()
        for event in attempts
    )
    assert prompts[1] == prompts[2]
    assert (tmp_path / failed_recovery.raw_output.path).read_text(
        encoding="utf-8"
    ) == "failed recovery bytes"
    assert (tmp_path / failed_recovery.runtime_stderr.path).read_text(
        encoding="utf-8"
    ) == "recovery failed"
    assert (tmp_path / successful_retry.raw_output.path).read_text(
        encoding="utf-8"
    ) == "corrected answer"
    assert (tmp_path / successful_retry.runtime_stderr.path).read_text(
        encoding="utf-8"
    ) == "retry diagnostic"
    assert validate_transcript_structure(outcome.transcript) == []


def test_fully_failed_recovery_is_partial_and_feedback_is_consumed(
    tmp_path: Path,
) -> None:
    outcome, prompts = _conversation(
        tmp_path,
        attempts=2,
        responses=[
            ModelInvocationResult(stdout="first answer", stderr="", exit_status=0),
            ModelInvocationResult(
                stdout="first failed recovery",
                stderr="first recovery error",
                exit_status=7,
            ),
            ModelInvocationResult(
                stdout="second failed recovery",
                stderr="second recovery error",
                exit_status=-9,
            ),
        ],
    )
    attempts = _model_events(outcome.transcript)
    failed_recovery, failed_retry = attempts[1:]

    assert outcome.transcript.completion_state == "partial"
    assert outcome.transcript.terminal_reason == "runtime_failure"
    assert outcome.transcript.final_response_event_id is None
    assert failed_recovery.attempt_state == failed_retry.attempt_state == "failed"
    assert [event.exit_status for event in attempts] == [0, 7, -9]
    assert failed_recovery.turn_id == failed_retry.turn_id
    assert failed_recovery.attempt_id != failed_retry.attempt_id
    planned = _feedback_plan_item(outcome.transcript)
    assert planned.lifecycle_state == "consumed"
    assert planned.consumed_by_turn_id == failed_recovery.turn_id
    assert failed_recovery.consumed_feedback_ids == ["feedback-1"]
    assert failed_retry.consumed_feedback_ids == ["feedback-1"]
    assert failed_recovery.input_state_id == failed_retry.input_state_id
    assert prompts[1] == prompts[2]
    assert (tmp_path / failed_recovery.runtime_stderr.path).read_text(
        encoding="utf-8"
    ) == "first recovery error"
    assert (tmp_path / failed_retry.runtime_stderr.path).read_text(
        encoding="utf-8"
    ) == "second recovery error"
    assert (tmp_path / failed_recovery.raw_output.path).read_text(
        encoding="utf-8"
    ) == "first failed recovery"
    assert (tmp_path / failed_retry.raw_output.path).read_text(
        encoding="utf-8"
    ) == "second failed recovery"
    assert validate_transcript_structure(outcome.transcript) == []


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        ("unrelated_turn_reuse", "reuses turn ID across unrelated logical turns"),
        ("retry_new_turn", "retry does not share its logical turn"),
        ("retry_input_state", "retry changed input state"),
        ("retry_rendered_input", "retry changed rendered input"),
        ("retry_feedback", "retry changed consumed feedback"),
        ("retry_parent", "retry changed logical turn ancestry"),
        ("retry_completed_turn", "retry targets a completed attempt"),
        ("duplicate_attempt", "duplicate attempt ID"),
        ("retry_cycle", "retry cycle detected"),
    ],
)
def test_retry_semantic_failures_fail_closed(
    tmp_path: Path, mutation: str, expected: str
) -> None:
    outcome, _ = _conversation(
        tmp_path,
        attempts=2,
        responses=[
            ModelInvocationResult(stdout="first answer", stderr="", exit_status=0),
            ModelInvocationResult(
                stdout="failed recovery",
                stderr="recovery failed",
                exit_status=1,
            ),
            ModelInvocationResult(stdout="corrected", stderr="", exit_status=0),
        ],
    )
    transcript = outcome.transcript.model_copy(deep=True)
    initial, recovery, retry = _model_events(transcript)

    if mutation == "unrelated_turn_reuse":
        recovery.turn_id = initial.turn_id
    elif mutation == "retry_new_turn":
        retry.turn_id = "unrelated-turn"
    elif mutation == "retry_input_state":
        retry.input_state_id = initial.input_state_id
    elif mutation == "retry_rendered_input":
        retry.raw_input.sha256 = "c" * 64
    elif mutation == "retry_feedback":
        retry.consumed_feedback_ids = []
    elif mutation == "retry_parent":
        retry.parent_event_id = initial.parent_event_id
    elif mutation == "retry_completed_turn":
        retry.retry_of_event_id = initial.event_id
    elif mutation == "duplicate_attempt":
        retry.attempt_id = recovery.attempt_id
    elif mutation == "retry_cycle":
        recovery.relationship = "retry"
        recovery.recovery_of_feedback_ids = []
        recovery.retry_of_event_id = retry.event_id

    assert expected in "; ".join(validate_transcript_structure(transcript))


def test_malformed_response_is_terminal_and_preserved(tmp_path: Path) -> None:
    outcome, _ = _conversation(
        tmp_path,
        feedback=False,
        max_turns=1,
        responses=[ModelInvocationResult(stdout="", stderr="", exit_status=0)],
    )

    attempt = _model_events(outcome.transcript)[0]
    assert attempt.attempt_state == "malformed"
    assert attempt.exit_status == 0
    assert outcome.transcript.completion_state == "partial"
    assert outcome.transcript.terminal_reason == "malformed_response"
    assert attempt.raw_output.path is not None


def test_timeout_preserves_partial_transcript(tmp_path: Path) -> None:
    outcome, _ = _conversation(
        tmp_path,
        feedback=False,
        max_turns=1,
        responses=[
            ModelInvocationResult(
                stdout="partial bytes",
                stderr="timeout",
                exit_status=-9,
                timeout=True,
            )
        ],
    )

    attempt = _model_events(outcome.transcript)[0]
    assert outcome.transcript.completion_state == "partial"
    assert outcome.transcript.terminal_reason == "timeout"
    assert outcome.transcript.final_response_event_id is None
    assert attempt.attempt_state == "timeout"
    assert attempt.exit_status == -9
    assert validate_transcript_structure(outcome.transcript) == []


def test_feedback_beyond_effective_limit_remains_declared_and_unreached(
    tmp_path: Path,
) -> None:
    outcome, prompts = _conversation(
        tmp_path,
        max_turns=3,
        feedback_after_turn=2,
        max_turns_override=1,
        responses=[ModelInvocationResult(stdout="first", stderr="", exit_status=0)],
    )

    planned = _feedback_plan_item(outcome.transcript)
    assert prompts == ["Initial exact task"]
    assert outcome.transcript.declared_limits.max_model_turns == 3
    assert outcome.transcript.effective_model_turn_limit == 1
    assert outcome.transcript.completion_state == "partial"
    assert outcome.transcript.terminal_reason == "turn_limit"
    assert planned.feedback_id == "feedback-1"
    assert planned.origin == "synthetic_test"
    assert planned.after_model_turn == 2
    assert planned.lifecycle_state == "unreached"
    assert planned.disposition_reason == "scheduling_point_not_reached"
    assert planned.supplied_event_id is None
    assert planned.consumed_by_turn_id is None
    assert not any(
        isinstance(event, FeedbackEvent) for event in outcome.transcript.events
    )
    assert (tmp_path / str(planned.raw_content.path)).read_text(
        encoding="utf-8"
    ) == "The first response missed the stated constraint."
    assert validate_transcript_structure(outcome.transcript) == []
    assert validate_transcript_artifacts(tmp_path, outcome.transcript) == []


@pytest.mark.parametrize(
    ("response", "terminal_reason", "attempt_state"),
    [
        (
            ModelInvocationResult(stdout="partial", stderr="failed", exit_status=7),
            "runtime_failure",
            "failed",
        ),
        (
            ModelInvocationResult(
                stdout="partial",
                stderr="timeout",
                exit_status=-9,
                timeout=True,
            ),
            "timeout",
            "timeout",
        ),
        (
            ModelInvocationResult(stdout="", stderr="", exit_status=0),
            "malformed_response",
            "malformed",
        ),
    ],
)
def test_future_feedback_remains_unreached_after_early_terminal_attempt(
    tmp_path: Path,
    response: ModelInvocationResult,
    terminal_reason: str,
    attempt_state: str,
) -> None:
    outcome, _ = _conversation(
        tmp_path,
        max_turns=3,
        feedback_after_turn=2,
        responses=[response],
    )

    planned = _feedback_plan_item(outcome.transcript)
    assert outcome.transcript.terminal_reason == terminal_reason
    assert _model_events(outcome.transcript)[0].attempt_state == attempt_state
    assert planned.lifecycle_state == "unreached"
    assert planned.disposition_reason == "scheduling_point_not_reached"
    assert planned.supplied_event_id is None
    assert planned.consumed_by_turn_id is None
    assert not any(
        isinstance(event, FeedbackEvent) for event in outcome.transcript.events
    )
    assert validate_transcript_structure(outcome.transcript) == []


def test_turn_limit_keeps_supplied_feedback_unconsumed(tmp_path: Path) -> None:
    outcome, _ = _conversation(
        tmp_path,
        max_turns_override=1,
        responses=[ModelInvocationResult(stdout="first", stderr="", exit_status=0)],
    )

    planned = _feedback_plan_item(outcome.transcript)
    assert outcome.transcript.completion_state == "partial"
    assert outcome.transcript.terminal_reason == "turn_limit"
    assert planned.lifecycle_state == "supplied_unconsumed"
    assert planned.disposition_reason == "no_admitted_follow_up_turn"
    assert planned.supplied_event_id == _feedback_event(outcome.transcript).event_id
    assert planned.consumed_by_turn_id is None


def test_valid_abandoned_transcript(tmp_path: Path) -> None:
    outcome, _ = _conversation(
        tmp_path,
        max_turns=3,
        feedback_after_turn=2,
        responses=[ModelInvocationResult(stdout="x", stderr="failed", exit_status=1)],
    )
    transcript = outcome.transcript.model_copy(deep=True)
    transcript.completion_state = "abandoned"
    transcript.completion_actor = "operator"
    transcript.terminal_reason = "abandoned"
    terminal = _terminal_event(transcript)
    terminal.completion_state = "abandoned"
    terminal.completion_actor = "operator"
    terminal.terminal_reason = "abandoned"

    planned = _feedback_plan_item(transcript)
    assert planned.lifecycle_state == "unreached"
    assert planned.disposition_reason == "scheduling_point_not_reached"
    assert planned.supplied_event_id is None
    assert planned.consumed_by_turn_id is None
    assert validate_transcript_structure(transcript) == []


def test_future_feedback_remains_unreached_for_operator_stop(tmp_path: Path) -> None:
    outcome, _ = _conversation(
        tmp_path,
        max_turns=3,
        feedback_after_turn=2,
        responses=[
            ModelInvocationResult(stdout="partial", stderr="stopped", exit_status=1)
        ],
    )
    transcript = outcome.transcript.model_copy(deep=True)
    transcript.completion_actor = "operator"
    transcript.terminal_reason = "operator_stop"
    terminal = _terminal_event(transcript)
    terminal.completion_actor = "operator"
    terminal.terminal_reason = "operator_stop"

    planned = _feedback_plan_item(transcript)
    assert planned.lifecycle_state == "unreached"
    assert planned.disposition_reason == "scheduling_point_not_reached"
    assert planned.supplied_event_id is None
    assert planned.consumed_by_turn_id is None
    assert validate_transcript_structure(transcript) == []


def test_task_loader_rejects_unsupported_versions(tmp_path: Path) -> None:
    path = tmp_path / "task.json"
    data = _task_data()
    data["schema_version"] = "llmgauge.multi_turn_task.v99"
    path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(TranscriptDefinitionError, match="schema_version"):
        load_multi_turn_task(path)


def test_transcript_loader_rejects_unsupported_version(tmp_path: Path) -> None:
    _conversation(tmp_path)
    path = tmp_path / "transcript" / "transcript.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["schema_version"] = "llmgauge.transcript.v99"
    path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(TranscriptDefinitionError, match="schema_version"):
        load_transcript(tmp_path)


def test_absent_transcript_preserves_single_turn_validation_path(
    tmp_path: Path,
) -> None:
    assert validate_result_transcript(tmp_path, {}) == []


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        ("duplicate_event", "event IDs must be unique"),
        ("order", "event sequence must be contiguous"),
        ("missing_terminal", "terminal event must be last"),
        ("unknown_parent", "invalid parent reference"),
        ("retry_cycle", "invalid retry reference"),
        ("forward_parent", "invalid parent reference"),
        ("unknown_feedback_consumer", "invalid consuming turn"),
        ("silent_feedback", "names a consuming turn"),
        ("invalid_final", "final_response_event_id"),
        ("terminal_mismatch", "terminal event does not match"),
        ("state_transition", "invalid previous state"),
        ("source_derivative", "required evidence must remain source"),
        ("limit", "model turns exceed declared limit"),
        ("review_hooks", "review hooks must remain unreviewed"),
    ],
)
def test_structural_failures_fail_closed(
    tmp_path: Path, mutation: str, expected: str
) -> None:
    outcome, _ = _conversation(tmp_path)
    transcript = outcome.transcript.model_copy(deep=True)
    attempts = _model_events(transcript)
    terminal = _terminal_event(transcript)

    if mutation == "duplicate_event":
        transcript.events[1].event_id = transcript.events[0].event_id
    elif mutation == "order":
        transcript.events[1].sequence = 9
    elif mutation == "missing_terminal":
        transcript.events.pop()
    elif mutation == "unknown_parent":
        attempts[0].parent_event_id = "unknown-event"
    elif mutation == "retry_cycle":
        attempts[1].relationship = "retry"
        attempts[1].recovery_of_feedback_ids = []
        attempts[1].retry_of_event_id = attempts[1].event_id
    elif mutation == "forward_parent":
        attempts[0].parent_event_id = attempts[1].event_id
    elif mutation == "unknown_feedback_consumer":
        transcript.feedback_plan[0].consumed_by_turn_id = "unknown-turn"
    elif mutation == "silent_feedback":
        transcript.feedback_plan[0].lifecycle_state = "supplied_unconsumed"
    elif mutation == "invalid_final":
        transcript.final_response_event_id = transcript.events[0].event_id
        terminal.final_response_event_id = transcript.events[0].event_id
    elif mutation == "terminal_mismatch":
        terminal.terminal_reason = "turn_limit"
    elif mutation == "state_transition":
        states = [event for event in transcript.events if isinstance(event, StateEvent)]
        states[1].previous_state_id = "unknown-state"
    elif mutation == "source_derivative":
        attempts[0].raw_output.role = "derivative"
        attempts[0].raw_output.source_event_id = attempts[0].event_id
    elif mutation == "limit":
        transcript.declared_limits.max_model_turns = 1
    elif mutation == "review_hooks":
        transcript.review.scoreability = "unscoreable"

    assert expected in "; ".join(validate_transcript_structure(transcript))


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        ("unreached_with_supply", "unreached feedback feedback-1 has a supply event"),
        ("supplied_without_event", "supply event does not match plan"),
        ("unconsumed_with_consumer", "contradictory supplied-unconsumed state"),
        ("schedule_conflict", "supply event conflicts with schedule"),
        (
            "unconsumed_with_later_model",
            "supplied-unconsumed feedback feedback-1 has a later model turn",
        ),
        (
            "feedback_content_unavailable",
            "content must remain exact authoritative source",
        ),
    ],
)
def test_feedback_plan_contradictions_fail_closed(
    tmp_path: Path, mutation: str, expected: str
) -> None:
    outcome, _ = _conversation(tmp_path)
    transcript = outcome.transcript.model_copy(deep=True)
    planned = _feedback_plan_item(transcript)

    if mutation == "unreached_with_supply":
        planned.lifecycle_state = "unreached"
        planned.disposition_reason = "scheduling_point_not_reached"
        planned.supplied_event_id = None
        planned.consumed_by_turn_id = None
    elif mutation == "supplied_without_event":
        planned.supplied_event_id = "unknown-feedback-event"
    elif mutation == "unconsumed_with_consumer":
        planned.lifecycle_state = "supplied_unconsumed"
        planned.disposition_reason = "no_admitted_follow_up_turn"
    elif mutation == "unconsumed_with_later_model":
        planned.lifecycle_state = "supplied_unconsumed"
        planned.disposition_reason = "conversation_terminated_before_consumption"
        planned.consumed_by_turn_id = None
    elif mutation == "feedback_content_unavailable":
        planned.raw_content = ArtifactReference(
            role="source",
            availability="unavailable",
            capture_state="failed",
        )
    elif mutation == "schedule_conflict":
        planned.after_model_turn = 2

    assert expected in "; ".join(validate_transcript_structure(transcript))


def test_valid_selected_branch_and_branch_point(tmp_path: Path) -> None:
    outcome, _ = _conversation(tmp_path)
    transcript = outcome.transcript.model_copy(deep=True)
    feedback = _feedback_event(transcript)
    attempts = _model_events(transcript)
    selected_attempt = attempts[-1]
    selected_attempt.branch_id = "branch-corrected"
    selected_state = next(
        event
        for event in transcript.events
        if isinstance(event, StateEvent)
        and event.caused_by_event_id == selected_attempt.event_id
    )
    selected_state.branch_id = "branch-corrected"
    terminal = _terminal_event(transcript)
    terminal.branch_id = "branch-corrected"
    transcript.branches[0].state = "superseded"
    transcript.branches.append(
        BranchRecord(
            branch_id="branch-corrected",
            parent_branch_id="main",
            branch_point_event_id=feedback.event_id,
            state="selected",
        )
    )
    transcript.selected_branch_id = "branch-corrected"

    assert validate_transcript_structure(transcript) == []


def test_branch_cycle_fails_closed(tmp_path: Path) -> None:
    outcome, _ = _conversation(tmp_path)
    transcript = outcome.transcript.model_copy(deep=True)
    transcript.branches.extend(
        [
            BranchRecord(
                branch_id="branch-a",
                parent_branch_id="branch-b",
                branch_point_event_id=transcript.events[0].event_id,
                state="superseded",
            ),
            BranchRecord(
                branch_id="branch-b",
                parent_branch_id="branch-a",
                branch_point_event_id=transcript.events[0].event_id,
                state="abandoned",
            ),
        ]
    )

    assert "branch cycle" in "; ".join(validate_transcript_structure(transcript))


def test_artifact_path_traversal_missing_and_unsafe_symlink(tmp_path: Path) -> None:
    outcome, _ = _conversation(tmp_path)

    traversal = outcome.transcript.model_copy(deep=True)
    _model_events(traversal)[0].raw_output.path = "../outside.txt"
    assert "path must be relative" in "; ".join(
        validate_transcript_artifacts(tmp_path, traversal)
    )

    missing = outcome.transcript.model_copy(deep=True)
    _model_events(missing)[0].raw_output.path = "transcript/source/missing.txt"
    assert "missing artifact" in "; ".join(
        validate_transcript_artifacts(tmp_path, missing)
    )

    outside = tmp_path.parent / "outside-transcript.txt"
    outside.write_text("outside", encoding="utf-8")
    link = tmp_path / "transcript" / "source" / "unsafe-link.txt"
    link.symlink_to(outside)
    symlinked = outcome.transcript.model_copy(deep=True)
    event = _model_events(symlinked)[0]
    event.raw_output.path = "transcript/source/unsafe-link.txt"
    event.raw_output.sha256 = hashlib.sha256(b"outside").hexdigest()
    assert "escapes result directory" in "; ".join(
        validate_transcript_artifacts(tmp_path, symlinked)
    )


def test_duplicate_artifact_authority_fails_closed(tmp_path: Path) -> None:
    outcome, _ = _conversation(tmp_path)
    transcript = outcome.transcript.model_copy(deep=True)
    attempts = _model_events(transcript)
    attempts[1].raw_output.path = attempts[0].raw_output.path
    attempts[1].raw_output.sha256 = attempts[0].raw_output.sha256

    assert "duplicates authority" in "; ".join(
        validate_transcript_artifacts(tmp_path, transcript)
    )


def test_model_attempt_exit_status_rejects_non_integer_representation(
    tmp_path: Path,
) -> None:
    outcome, _ = _conversation(
        tmp_path,
        feedback=False,
        max_turns=1,
        responses=[ModelInvocationResult(stdout="answer", stderr="", exit_status=0)],
    )
    represented = outcome.transcript.model_dump(mode="json")
    model_event = next(
        event for event in represented["events"] if event["kind"] == "model_attempt"
    )
    model_event["exit_status"] = "0"

    with pytest.raises(ValidationError, match="exit_status"):
        Transcript.model_validate(represented)


def test_malformed_redaction_and_availability_fail_model_validation() -> None:
    with pytest.raises(ValidationError, match="available artifact requires"):
        ArtifactReference.model_validate(
            {
                "role": "source",
                "availability": "available",
                "capture_state": "complete",
                "truncated": False,
                "redacted": False,
            }
        )
    with pytest.raises(ValidationError, match="redacted availability"):
        ArtifactReference.model_validate(
            {
                "role": "source",
                "availability": "redacted",
                "capture_state": "failed",
                "truncated": False,
                "redacted": False,
            }
        )


def test_partial_transcript_accepts_explicit_redacted_source_state(
    tmp_path: Path,
) -> None:
    outcome, _ = _conversation(
        tmp_path,
        feedback=False,
        max_turns=1,
        responses=[
            ModelInvocationResult(
                stdout="",
                stderr="capture unavailable",
                exit_status=1,
            )
        ],
    )
    transcript = outcome.transcript.model_copy(deep=True)
    attempt = _model_events(transcript)[0]
    attempt.raw_output = ArtifactReference(
        role="source",
        availability="redacted",
        capture_state="failed",
        redacted=True,
    )
    attempt.cleaned_output = None

    assert validate_transcript_structure(transcript) == []
    assert validate_transcript_artifacts(tmp_path, transcript) == []


def test_llama_end_to_end_persists_validates_reports_and_fingerprints(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    task_path = _write_task(tmp_path / "task.json", attempts=2)
    prompts: list[str] = []
    responses = iter(
        [
            ("first response", "", 0),
            ("failed recovery bytes", "recovery failed", 1),
            (
                "corrected response\nprompt eval time = 1 / 3 tokens (12.5 tokens per second)",
                "eval time = 1 / 4 runs (6.25 tokens per second)",
                0,
            ),
        ]
    )

    def fake_run(config, prompt, *, timeout_seconds):
        prompts.append(prompt)
        stdout, stderr, exit_status = next(responses)
        return SimpleNamespace(
            command=[str(config.llama_cli), "--model", str(config.model_path)],
            stdout=stdout,
            stderr=stderr,
            exit_status=exit_status,
            timed_out=False,
            vram_samples=[],
            vram_summary=None,
        )

    monkeypatch.setattr(run_helpers, "run_llama_cpp", fake_run)
    _patch_identity(monkeypatch)
    result_dir = tmp_path / "result"
    result = run_helpers.execute_run(
        suite=Path("agent-backend-v1"),
        only=TASK_ID,
        include="all",
        resolved=_resolved(),
        out=result_dir,
        fail_on_failed_prompts=True,
        conversation_task=task_path,
        conversation_id="conversation-e2e",
    )

    assert len(prompts) == 3
    assert "feedback-1" in prompts[1]
    assert prompts[1] == prompts[2]
    assert result["transcript"]["path"] == "transcript/transcript.json"
    assert result["results"][0]["transcript_event_id"] is not None
    assert validate_result_dir(result_dir) == []
    transcript = load_transcript(result_dir)
    assert transcript.completion_state == "completed"
    attempts = _model_events(transcript)
    assert attempts[1].turn_id == attempts[2].turn_id
    assert attempts[1].attempt_id != attempts[2].attempt_id
    assert [event.exit_status for event in attempts] == [0, 1, 0]
    assert result["results"][0]["exit_status"] == 0
    assert result["results"][0]["metrics"]["prompt_eval_tokens"] == 3
    assert result["results"][0]["metrics"]["prompt_eval_tps"] == 12.5
    assert result["results"][0]["metrics"]["generation_tokens"] == 4
    assert result["results"][0]["metrics"]["generation_tps"] == 6.25
    report = (result_dir / "report.md").read_text(encoding="utf-8")
    assert "## Native Multi-turn Transcript" in report
    assert "- Logical model turns: 2" in report
    assert "- Model attempts: 3" in report
    assert "- Retries: 1" in report
    assert "state `completed`; exit status `0`" in report
    assert "Supplied feedback text does not prove" in report
    assert "Native transcript evidence is not Agent Harness evidence" in report
    assert "- Declared feedback items: 1" in report
    assert "- Supplied feedback items: 1" in report
    assert "- Consumed feedback items: 1" in report
    assert "- Unreached feedback items: 0" in report
    assert "- Supplied but unconsumed feedback items: 0" in report
    assert "state `consumed`; reason `consumed_by_model_turn`" in report

    original_fingerprint = result["run_fingerprint"]["value"]
    (result_dir / "report.md").write_text("mutable report", encoding="utf-8")
    assert run_fingerprint_value(result_dir, result) == original_fingerprint

    transcript.review.final_response = "unscoreable"
    write_transcript(result_dir, transcript)
    result["transcript"] = build_result_transcript_reference(result_dir, transcript)
    assert run_fingerprint_value(result_dir, result) == original_fingerprint
    selected_attempt = _model_events(transcript)[-1]
    selected_attempt.exit_status = 7
    write_transcript(result_dir, transcript)
    result["transcript"] = build_result_transcript_reference(result_dir, transcript)
    assert run_fingerprint_value(result_dir, result) != original_fingerprint
    selected_attempt.exit_status = 0

    feedback = transcript.feedback_plan[0]
    original_origin = feedback.origin
    feedback.origin = "operator_local"
    write_transcript(result_dir, transcript)
    result["transcript"] = build_result_transcript_reference(result_dir, transcript)
    assert run_fingerprint_value(result_dir, result) != original_fingerprint
    feedback.origin = original_origin

    original_schedule = feedback.after_model_turn
    feedback.after_model_turn = 2
    write_transcript(result_dir, transcript)
    result["transcript"] = build_result_transcript_reference(result_dir, transcript)
    assert run_fingerprint_value(result_dir, result) != original_fingerprint
    feedback.after_model_turn = original_schedule

    feedback_path = result_dir / str(feedback.raw_content.path)
    feedback_path.write_text("changed immutable feedback", encoding="utf-8")
    feedback.raw_content.sha256 = hashlib.sha256(
        b"changed immutable feedback"
    ).hexdigest()
    write_transcript(result_dir, transcript)
    result["transcript"] = build_result_transcript_reference(result_dir, transcript)
    assert run_fingerprint_value(result_dir, result) != original_fingerprint


def test_failed_synthetic_result_is_preserved_and_valid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    task_path = _write_task(tmp_path / "failed-task.json", feedback=False, max_turns=1)

    def fake_run(config, prompt, *, timeout_seconds):
        return SimpleNamespace(
            command=[str(config.llama_cli)],
            stdout="partial response",
            stderr="[ Prompt: 11.0 t/s | Generation: 4.5 t/s ]",
            exit_status=7,
            timed_out=False,
            vram_samples=[],
            vram_summary=None,
        )

    monkeypatch.setattr(run_helpers, "run_llama_cpp", fake_run)
    _patch_identity(monkeypatch)
    result_dir = tmp_path / "failed-result"
    result = run_helpers.execute_run(
        suite=Path("agent-backend-v1"),
        only=TASK_ID,
        include="all",
        resolved=_resolved(),
        out=result_dir,
        fail_on_failed_prompts=False,
        conversation_task=task_path,
        conversation_id="conversation-failed",
    )

    assert result["run"]["status"] == "failed"
    assert load_transcript(result_dir).completion_state == "partial"
    attempt = _model_events(load_transcript(result_dir))[0]
    assert attempt.attempt_state == "failed"
    assert attempt.exit_status == 7
    assert result["results"][0]["exit_status"] == 7
    assert result["results"][0]["metrics"]["prompt_eval_tps"] == 11.0
    assert result["results"][0]["metrics"]["generation_tps"] == 4.5
    assert "partial response" == (
        result_dir / result["results"][0]["raw_output_path"]
    ).read_text(encoding="utf-8")
    assert validate_result_dir(result_dir) == []
    result["results"][0]["exit_status"] = 1
    (result_dir / "llmgauge-result.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    assert "prompt result exit_status does not match compatibility attempt" in (
        validate_result_dir(result_dir)
    )


def test_reports_distinguish_unreached_and_supplied_unconsumed_feedback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_run(config, prompt, *, timeout_seconds):
        return SimpleNamespace(
            command=[str(config.llama_cli)],
            stdout="first response",
            stderr="",
            exit_status=0,
            timed_out=False,
            vram_samples=[],
            vram_summary=None,
        )

    monkeypatch.setattr(run_helpers, "run_llama_cpp", fake_run)
    _patch_identity(monkeypatch)

    unreached_task = _write_task(
        tmp_path / "unreached-task.json",
        max_turns=3,
        feedback_after_turn=2,
    )
    unreached_dir = tmp_path / "unreached-result"
    run_helpers.execute_run(
        suite=Path("agent-backend-v1"),
        only=TASK_ID,
        include="all",
        resolved=_resolved(),
        out=unreached_dir,
        fail_on_failed_prompts=False,
        conversation_task=unreached_task,
        conversation_id="conversation-unreached",
        max_turns=1,
    )
    unreached_report = (unreached_dir / "report.md").read_text(encoding="utf-8")
    assert "- Declared feedback items: 1" in unreached_report
    assert "- Supplied feedback items: 0" in unreached_report
    assert "- Consumed feedback items: 0" in unreached_report
    assert "- Unreached feedback items: 1" in unreached_report
    assert "- Supplied but unconsumed feedback items: 0" in unreached_report
    assert (
        "state `unreached`; reason `scheduling_point_not_reached`" in unreached_report
    )
    assert validate_result_dir(unreached_dir) == []

    unconsumed_task = _write_task(tmp_path / "unconsumed-task.json")
    unconsumed_dir = tmp_path / "unconsumed-result"
    run_helpers.execute_run(
        suite=Path("agent-backend-v1"),
        only=TASK_ID,
        include="all",
        resolved=_resolved(),
        out=unconsumed_dir,
        fail_on_failed_prompts=False,
        conversation_task=unconsumed_task,
        conversation_id="conversation-unconsumed",
        max_turns=1,
    )
    unconsumed_report = (unconsumed_dir / "report.md").read_text(encoding="utf-8")
    assert "- Declared feedback items: 1" in unconsumed_report
    assert "- Supplied feedback items: 1" in unconsumed_report
    assert "- Consumed feedback items: 0" in unconsumed_report
    assert "- Unreached feedback items: 0" in unconsumed_report
    assert "- Supplied but unconsumed feedback items: 1" in unconsumed_report
    assert (
        "state `supplied_unconsumed`; reason `no_admitted_follow_up_turn`"
        in unconsumed_report
    )
    assert validate_result_dir(unconsumed_dir) == []


def test_vllm_path_receives_equivalent_order_without_lifecycle_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    task_path = _write_task(tmp_path / "vllm-task.json")
    prompts: list[str] = []
    responses = iter(["first response", "corrected response"])
    readiness = VllmReadinessResult(
        success=True,
        endpoint_identity={"scheme": "http", "loopback_class": "ipv4", "port": 8000},
        served_models=["test-served-model"],
        observed_model="test-served-model",
        vllm_version="0.test",
        server_state="ready",
    )

    monkeypatch.setattr(
        run_helpers, "check_readiness_and_model", lambda config: readiness
    )

    def fake_chat(config, *, prompt, system_prompt=None):
        assert system_prompt is None
        prompts.append(prompt)
        text = next(responses)
        return VllmRequestResult(
            success=True,
            generated_text=text,
            finish_reason="stop",
            observed_model="test-served-model",
            endpoint_identity=readiness.endpoint_identity,
            request_evidence={
                "schema_version": "llmgauge.vllm_request_evidence.v0",
                "lifecycle_ownership": "external_operator",
            },
        )

    monkeypatch.setattr(run_helpers, "run_chat_completion", fake_chat)
    result_dir = tmp_path / "vllm-result"
    result = run_helpers.execute_run(
        suite=Path("agent-backend-v1"),
        only=TASK_ID,
        include="all",
        resolved=_resolved("vllm"),
        out=result_dir,
        fail_on_failed_prompts=True,
        conversation_task=task_path,
        conversation_id="conversation-vllm",
    )

    assert len(prompts) == 2
    assert "feedback-1" in prompts[1]
    assert result["runtime"]["lifecycle_ownership"] == "external_operator"
    assert result["runtime"]["runtime_command_captured"] is False
    assert validate_result_dir(result_dir) == []
    assert [
        event.exit_status for event in _model_events(load_transcript(result_dir))
    ] == [
        0,
        0,
    ]


def test_multi_turn_dry_run_discloses_exact_deterministic_protocol_plan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        run_helpers, "resolve_run_options", lambda **kwargs: _resolved()
    )
    monkeypatch.setattr(
        run_helpers,
        "run_llama_cpp",
        lambda *args, **kwargs: pytest.fail("dry-run launched llama.cpp"),
    )
    monkeypatch.setattr(
        run_helpers,
        "check_readiness_and_model",
        lambda *args, **kwargs: pytest.fail("dry-run contacted vLLM"),
    )

    def invoke(task_path: Path, conversation_id: str, *extra: str):
        return runner.invoke(
            cli.app,
            [
                "run",
                "--suite",
                "agent-backend-v1",
                "--only",
                TASK_ID,
                "--conversation-task",
                str(task_path),
                "--conversation-id",
                conversation_id,
                "--model-id",
                "test-model",
                "--dry-run",
                *extra,
            ],
            env={"COLUMNS": "200"},
        )

    no_feedback = _write_task(
        tmp_path / "dry-no-feedback.json", feedback=False, max_turns=3
    )
    no_feedback_result = invoke(no_feedback, "conversation-dry-no-feedback")
    assert no_feedback_result.exit_code == 0, no_feedback_result.output
    assert (
        "Runtime-conditional deterministic protocol plan" in no_feedback_result.output
    )
    assert "model request 1" in no_feedback_result.output
    assert "model request 2" not in no_feedback_result.output
    assert "Planned model requests" in no_feedback_result.output

    future_feedback = _write_task(
        tmp_path / "dry-future-feedback.json",
        max_turns=3,
        feedback_after_turn=2,
    )
    unreachable_result = invoke(
        future_feedback,
        "conversation-dry-unreachable",
        "--max-turns",
        "1",
    )
    assert unreachable_result.exit_code == 0, unreachable_result.output
    assert "feedback-1" in unreachable_result.output
    assert "after model turn 2" in unreachable_result.output
    assert "model request 2" not in unreachable_result.output
    assert (
        "declared but unreachable under effective turn limit"
        in unreachable_result.output
    )
    admitted_result = invoke(future_feedback, "conversation-dry-admitted")
    assert admitted_result.exit_code == 0, admitted_result.output
    request_1 = admitted_result.output.index("model request 1")
    request_2 = admitted_result.output.index("model request 2")
    supply = admitted_result.output.index("conditional feedback supply feedback-1")
    request_3 = admitted_result.output.index("model request 3")
    assert request_1 < request_2 < supply < request_3
    assert "consumed by conditional model request 3" in admitted_result.output
    assert (
        "conditional on prior request completing to reach a future feedback schedule"
        in admitted_result.output
    )
    assert (
        "conditional on prior request completing and scheduled feedback being supplied"
        in admitted_result.output
    )
    assert "no runtime was launched or contacted" in admitted_result.output
    assert not (tmp_path / "result").exists()


def test_conflicting_or_incomplete_conversation_selectors_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    task_path = _write_task(tmp_path / "bad-selector-task.json")
    monkeypatch.setattr(
        run_helpers, "resolve_run_options", lambda **kwargs: _resolved()
    )

    missing_id = runner.invoke(
        cli.app,
        [
            "run",
            "--suite",
            "agent-backend-v1",
            "--only",
            TASK_ID,
            "--conversation-task",
            str(task_path),
            "--model-id",
            "test-model",
            "--dry-run",
        ],
    )
    assert missing_id.exit_code != 0
    missing_id_output = re.sub(
        r"\x1b\[[0-?]*[ -/]*[@-~]",
        "",
        missing_id.output,
    )
    missing_id_output = " ".join(missing_id_output.split())
    assert "--conversation-id is required" in missing_id_output
    assert "--conversation-task" in missing_id_output

    conflicting = runner.invoke(
        cli.app,
        [
            "run",
            "--suite",
            "agent-backend-v1",
            "--only",
            TASK_ID,
            "--profile",
            "smoke",
            "--conversation-task",
            str(task_path),
            "--conversation-id",
            "conversation-bad",
            "--model-id",
            "test-model",
            "--dry-run",
        ],
    )
    assert conflicting.exit_code != 0
    assert "requires exact --only selection" in conflicting.output
