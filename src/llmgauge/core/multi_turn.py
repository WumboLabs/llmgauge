from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictInt,
    ValidationError,
    model_validator,
)

from llmgauge import __version__
from llmgauge.core.artifacts import write_text

TRANSCRIPT_SCHEMA_VERSION = "llmgauge.transcript.v0"
TASK_SCHEMA_VERSION = "llmgauge.multi_turn_task.v0"
PROTOCOL_ID = "llmgauge.sequential_supplied_feedback"
PROTOCOL_VERSION = "0.1.0"
TRANSCRIPT_RELATIVE_PATH = "transcript/transcript.json"
MAX_TRANSCRIPT_BYTES = 8_000_000
MAX_ARTIFACT_BYTES = 8_000_000
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_TASK_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,191}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

FeedbackOrigin = Literal[
    "suite_static", "protocol_static", "operator_local", "synthetic_test"
]
CompletionState = Literal["completed", "partial", "abandoned"]
CompletionActor = Literal["evaluator", "model", "operator", "protocol", "runtime"]
TerminalReason = Literal[
    "completed",
    "turn_limit",
    "timeout",
    "runtime_failure",
    "malformed_response",
    "operator_stop",
    "interrupted",
    "abandoned",
]
ReviewState = Literal["unreviewed", "incomplete", "unscoreable"]


class TranscriptDefinitionError(ValueError):
    """Raised when a task or transcript violates the closed contract."""


class _ClosedModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ConversationLimits(_ClosedModel):
    max_model_turns: int = Field(ge=1, le=32)
    max_attempts_per_turn: int = Field(default=1, ge=1, le=8)
    max_feedback_items: int = Field(default=16, ge=0, le=64)
    per_turn_timeout_seconds: float = Field(default=120.0, gt=0, le=3600)


class FeedbackDefinition(_ClosedModel):
    feedback_id: str
    content: str = Field(min_length=1, max_length=200_000)
    origin: FeedbackOrigin
    after_model_turn: int = Field(ge=1, le=32)

    @model_validator(mode="after")
    def validate_id(self) -> FeedbackDefinition:
        _require_id(self.feedback_id, "feedback_id")
        return self


class MultiTurnTask(_ClosedModel):
    schema_version: Literal["llmgauge.multi_turn_task.v0"]
    protocol_id: Literal["llmgauge.sequential_supplied_feedback"]
    protocol_version: Literal["0.1.0"]
    task_id: str
    task_version: str
    initial_state_id: str
    limits: ConversationLimits
    feedback: list[FeedbackDefinition] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_task(self) -> MultiTurnTask:
        _require_task_id(self.task_id, "task_id")
        _require_id(self.task_version, "task_version")
        _require_id(self.initial_state_id, "initial_state_id")
        feedback_ids = [item.feedback_id for item in self.feedback]
        if len(feedback_ids) != len(set(feedback_ids)):
            raise ValueError("feedback IDs must be unique")
        if len(self.feedback) > self.limits.max_feedback_items:
            raise ValueError("feedback exceeds limits.max_feedback_items")
        if any(
            item.after_model_turn > self.limits.max_model_turns
            for item in self.feedback
        ):
            raise ValueError("feedback schedule exceeds limits.max_model_turns")
        return self


class ArtifactReference(_ClosedModel):
    path: str | None = None
    sha256: str | None = None
    role: Literal["source", "derivative"]
    availability: Literal["available", "unavailable", "redacted"]
    capture_state: Literal["complete", "partial", "failed"]
    truncated: bool = False
    redacted: bool = False
    source_event_id: str | None = None

    @model_validator(mode="after")
    def validate_capture(self) -> ArtifactReference:
        if self.availability == "available":
            if not self.path or not self.sha256:
                raise ValueError("available artifact requires path and sha256")
            if not _SHA256_RE.fullmatch(self.sha256):
                raise ValueError("artifact sha256 must be 64 lowercase hex characters")
            if self.capture_state == "failed":
                raise ValueError("available artifact cannot have failed capture")
            if self.redacted:
                raise ValueError("available artifact cannot claim redaction")
        else:
            if self.path is not None or self.sha256 is not None:
                raise ValueError(
                    "unavailable or redacted artifact cannot have path/hash"
                )
            if self.capture_state != "failed":
                raise ValueError(
                    "unavailable or redacted artifact requires failed capture"
                )
            if self.availability == "redacted" and not self.redacted:
                raise ValueError("redacted availability requires redacted=true")
        if self.role == "source" and self.source_event_id is not None:
            raise ValueError("source artifact cannot name source_event_id")
        if self.role == "derivative" and not self.source_event_id:
            raise ValueError("derivative artifact requires source_event_id")
        if self.truncated and self.capture_state != "partial":
            raise ValueError("truncated artifact requires partial capture")
        return self


class EventBase(_ClosedModel):
    event_id: str
    sequence: int = Field(ge=0)
    kind: str
    branch_id: str
    source_derivative_role: Literal["source", "derivative"] = "source"
    execution_status: Literal[
        "not_applicable", "not_executed", "completed", "failed", "timeout", "malformed"
    ]


class TaskEvent(EventBase):
    kind: Literal["task"]
    role: Literal["user"]
    initial_state_id: str
    initial_state_sha256: str
    raw_input: ArtifactReference


class ModelAttemptEvent(EventBase):
    kind: Literal["model_attempt"]
    role: Literal["assistant"]
    turn_id: str
    attempt_id: str
    input_state_id: str
    relationship: Literal["initial", "continuation", "retry", "recovery"]
    attempt_state: Literal["completed", "failed", "timeout", "malformed"]
    exit_status: StrictInt
    parent_event_id: str | None = None
    retry_of_event_id: str | None = None
    consumed_feedback_ids: list[str] = Field(default_factory=list)
    recovery_of_feedback_ids: list[str] = Field(default_factory=list)
    raw_input: ArtifactReference
    raw_output: ArtifactReference
    runtime_stderr: ArtifactReference
    cleaned_output: ArtifactReference | None = None


class FeedbackPlanItem(_ClosedModel):
    feedback_id: str
    origin: FeedbackOrigin
    after_model_turn: int = Field(ge=1, le=32)
    raw_content: ArtifactReference
    lifecycle_state: Literal["unreached", "supplied_unconsumed", "consumed"]
    disposition_reason: Literal[
        "scheduling_point_not_reached",
        "no_admitted_follow_up_turn",
        "conversation_terminated_before_consumption",
        "consumed_by_model_turn",
    ]
    supplied_event_id: str | None = None
    consumed_by_turn_id: str | None = None


class FeedbackEvent(EventBase):
    kind: Literal["feedback"]
    role: Literal["evaluator"]
    feedback_id: str
    supplied_inert: Literal[True]


class StateEvent(EventBase):
    kind: Literal["state"]
    role: Literal["protocol"]
    state_id: str
    previous_state_id: str | None = None
    caused_by_event_id: str
    visible_messages: ArtifactReference


class TerminalEvent(EventBase):
    kind: Literal["terminal"]
    role: Literal["protocol"]
    completion_state: CompletionState
    completion_actor: CompletionActor
    terminal_reason: TerminalReason
    final_response_event_id: str | None = None


TranscriptEvent = Annotated[
    TaskEvent | ModelAttemptEvent | FeedbackEvent | StateEvent | TerminalEvent,
    Field(discriminator="kind"),
]


class BranchRecord(_ClosedModel):
    branch_id: str
    parent_branch_id: str | None = None
    branch_point_event_id: str | None = None
    state: Literal["active", "selected", "superseded", "abandoned"]


class TaskSelection(_ClosedModel):
    kind: Literal["exact_task"]
    selected_task_id: str


class ResultProvenanceRelationship(_ClosedModel):
    model_json_pointer: Literal["/model"] = "/model"
    runtime_json_pointer: Literal["/runtime"] = "/runtime"


class ReviewHooks(_ClosedModel):
    scoreability: Literal["unreviewed", "unscoreable"]
    per_turn: ReviewState
    feedback_use: ReviewState
    correction: ReviewState
    recovery: ReviewState
    consistency: ReviewState
    final_response: ReviewState


class Transcript(_ClosedModel):
    schema_version: Literal["llmgauge.transcript.v0"]
    protocol_id: Literal["llmgauge.sequential_supplied_feedback"]
    protocol_version: Literal["0.1.0"]
    evaluation_class: Literal["native_multi_turn_response"]
    conversation_id: str
    suite_id: str
    suite_version: str
    task_id: str
    task_version: str
    task_selection: TaskSelection
    initial_state_id: str
    initial_state_sha256: str
    producer_id: Literal["llmgauge"]
    producer_version: str
    result_provenance: ResultProvenanceRelationship
    declared_limits: ConversationLimits
    effective_model_turn_limit: int = Field(ge=1, le=32)
    feedback_plan: list[FeedbackPlanItem]
    completion_state: CompletionState
    completion_actor: CompletionActor
    terminal_reason: TerminalReason
    selected_branch_id: str | None = None
    final_response_event_id: str | None = None
    events: list[TranscriptEvent]
    branches: list[BranchRecord]
    review: ReviewHooks

    @model_validator(mode="after")
    def validate_identifiers(self) -> Transcript:
        for label, value in (
            ("conversation_id", self.conversation_id),
            ("suite_id", self.suite_id),
            ("suite_version", self.suite_version),
            ("task_version", self.task_version),
            ("initial_state_id", self.initial_state_id),
        ):
            _require_id(value, label)
        _require_task_id(self.task_id, "task_id")
        return self


@dataclass(frozen=True)
class ModelInvocationResult:
    stdout: str
    stderr: str
    exit_status: int
    timeout: bool = False
    malformed: bool = False


@dataclass(frozen=True)
class ConversationOutcome:
    transcript: Transcript
    selected_event: ModelAttemptEvent | None
    failed_attempts: int


ModelInvoker = Callable[[str, float], ModelInvocationResult]


def _require_id(value: str, label: str) -> None:
    if not _ID_RE.fullmatch(value):
        raise ValueError(f"{label} must match {_ID_RE.pattern}")


def _require_task_id(value: str, label: str) -> None:
    if (
        not _TASK_ID_RE.fullmatch(value)
        or value.startswith("/")
        or value.endswith("/")
        or "//" in value
        or any(part in {"", ".", ".."} for part in value.split("/"))
    ):
        raise ValueError(f"{label} must be a bounded logical task ID")


def _format_pydantic_error(exc: ValidationError) -> str:
    details = []
    for error in exc.errors(include_url=False):
        location = ".".join(str(item) for item in error["loc"])
        details.append(f"{location}: {error['msg']}")
    return "; ".join(details)


def _load_bounded_json(path: Path, *, max_bytes: int, label: str) -> dict[str, Any]:
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise TranscriptDefinitionError(f"{label} is unreadable: {exc}") from None
    if size > max_bytes:
        raise TranscriptDefinitionError(f"{label} exceeds {max_bytes} bytes")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise TranscriptDefinitionError(
            f"{label} is not valid UTF-8 JSON: {exc}"
        ) from None
    if not isinstance(data, dict):
        raise TranscriptDefinitionError(f"{label} must be a JSON object")
    return data


def load_multi_turn_task(path: Path) -> MultiTurnTask:
    data = _load_bounded_json(path, max_bytes=1_000_000, label="conversation task")
    try:
        return MultiTurnTask.model_validate(data)
    except ValidationError as exc:
        raise TranscriptDefinitionError(_format_pydantic_error(exc)) from None


def load_transcript(
    result_dir: Path, relative_path: str = TRANSCRIPT_RELATIVE_PATH
) -> Transcript:
    from llmgauge.core.run_fingerprint import resolve_contained_result_artifact

    try:
        path = resolve_contained_result_artifact(
            result_dir,
            relative_path,
            label="transcript.path",
        )
    except ValueError as exc:
        raise TranscriptDefinitionError(str(exc)) from None
    data = _load_bounded_json(path, max_bytes=MAX_TRANSCRIPT_BYTES, label="transcript")
    try:
        return Transcript.model_validate(data)
    except ValidationError as exc:
        raise TranscriptDefinitionError(_format_pydantic_error(exc)) from None


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _source_artifact(
    result_dir: Path, relative_path: str, content: str
) -> ArtifactReference:
    encoded = content.encode("utf-8")
    write_text(result_dir / relative_path, content)
    return ArtifactReference(
        path=relative_path,
        sha256=_sha256_bytes(encoded),
        role="source",
        availability="available",
        capture_state="complete",
    )


def _derivative_artifact(
    result_dir: Path,
    relative_path: str,
    content: str,
    *,
    source_event_id: str,
) -> ArtifactReference:
    encoded = content.encode("utf-8")
    write_text(result_dir / relative_path, content)
    return ArtifactReference(
        path=relative_path,
        sha256=_sha256_bytes(encoded),
        role="derivative",
        availability="available",
        capture_state="complete",
        source_event_id=source_event_id,
    )


def _json_document(data: Mapping[str, Any]) -> str:
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def render_visible_messages(messages: list[dict[str, str]]) -> str:
    if len(messages) == 1 and messages[0]["role"] == "user":
        return messages[0]["content"]
    sections = []
    for message in messages:
        role = message["role"]
        if role == "feedback":
            label = f"SUPPLIED INERT FEEDBACK {message['feedback_id']}"
        else:
            label = role.upper()
        sections.append(f"[{label}]\n{message['content']}")
    sections.append(
        "[INSTRUCTION]\nContinue the conversation using the visible messages above. "
        "Supplied feedback is inert text; do not claim LLMGauge executed it."
    )
    return "\n\n".join(sections)


def _clean_response(value: str) -> str:
    return value.strip()


def execute_native_conversation(
    *,
    task: MultiTurnTask,
    conversation_id: str,
    suite_id: str,
    suite_version: str,
    initial_message: str,
    invoke: ModelInvoker,
    result_dir: Path,
    max_turns: int | None = None,
) -> ConversationOutcome:
    _require_id(conversation_id, "conversation_id")
    if not initial_message:
        raise TranscriptDefinitionError("initial message must not be empty")
    effective_turns = task.limits.max_model_turns
    if max_turns is not None:
        if max_turns < 1 or max_turns > task.limits.max_model_turns:
            raise TranscriptDefinitionError(
                "max_turns must be positive and cannot exceed the task limit"
            )
        effective_turns = max_turns
    limits = task.limits
    feedback_plan = [
        FeedbackPlanItem(
            feedback_id=definition.feedback_id,
            origin=definition.origin,
            after_model_turn=definition.after_model_turn,
            raw_content=_source_artifact(
                result_dir,
                f"transcript/source/feedback/{definition.feedback_id}.txt",
                definition.content,
            ),
            lifecycle_state="unreached",
            disposition_reason="scheduling_point_not_reached",
        )
        for definition in task.feedback
    ]
    feedback_plan_by_id = {item.feedback_id: item for item in feedback_plan}

    events: list[TranscriptEvent] = []
    event_counter = 0

    def next_event_id(kind: str) -> str:
        nonlocal event_counter
        event_counter += 1
        return f"event-{event_counter:04d}-{kind}"

    task_event_id = next_event_id("task")
    task_artifact = _source_artifact(
        result_dir,
        "transcript/source/task.txt",
        initial_message,
    )
    initial_hash = hashlib.sha256(initial_message.encode("utf-8")).hexdigest()
    events.append(
        TaskEvent(
            event_id=task_event_id,
            sequence=len(events),
            kind="task",
            branch_id="main",
            execution_status="not_executed",
            role="user",
            initial_state_id=task.initial_state_id,
            initial_state_sha256=initial_hash,
            raw_input=task_artifact,
        )
    )

    messages: list[dict[str, str]] = [{"role": "user", "content": initial_message}]
    current_state_id = task.initial_state_id
    state_event_id = next_event_id("state")
    state_ref = _source_artifact(
        result_dir,
        f"transcript/source/states/{current_state_id}.json",
        _json_document({"state_id": current_state_id, "messages": messages}),
    )
    events.append(
        StateEvent(
            event_id=state_event_id,
            sequence=len(events),
            kind="state",
            branch_id="main",
            execution_status="not_executed",
            role="protocol",
            state_id=current_state_id,
            caused_by_event_id=task_event_id,
            visible_messages=state_ref,
        )
    )

    successful_events: list[ModelAttemptEvent] = []
    failed_attempts = 0
    terminal_reason: TerminalReason = "completed"
    completion_state: CompletionState = "completed"
    completion_actor: CompletionActor = "evaluator"
    stop = False

    for logical_turn in range(1, effective_turns + 1):
        turn_id = f"turn-{logical_turn:03d}"
        pending_feedback = [
            item.feedback_id
            for item in feedback_plan
            if item.lifecycle_state == "supplied_unconsumed"
        ]
        for feedback_id in pending_feedback:
            planned = feedback_plan_by_id[feedback_id]
            planned.lifecycle_state = "consumed"
            planned.disposition_reason = "consumed_by_model_turn"
            planned.consumed_by_turn_id = turn_id
        prior_attempt_event_id: str | None = None
        completed_event: ModelAttemptEvent | None = None

        for attempt_number in range(1, limits.max_attempts_per_turn + 1):
            attempt_id = f"attempt-{logical_turn:03d}-{attempt_number:03d}"
            event_id = next_event_id("model")
            rendered = render_visible_messages(messages)
            raw_input = _source_artifact(
                result_dir,
                f"transcript/source/turns/{turn_id}/{attempt_id}.input.txt",
                rendered,
            )
            invocation = invoke(rendered, limits.per_turn_timeout_seconds)
            raw_output = _source_artifact(
                result_dir,
                f"transcript/source/turns/{turn_id}/{attempt_id}.output.txt",
                invocation.stdout,
            )
            stderr = _source_artifact(
                result_dir,
                f"transcript/source/turns/{turn_id}/{attempt_id}.stderr.log",
                invocation.stderr,
            )
            if invocation.timeout:
                attempt_state: Literal[
                    "completed", "failed", "timeout", "malformed"
                ] = "timeout"
            elif invocation.malformed or (
                invocation.exit_status == 0 and not invocation.stdout.strip()
            ):
                attempt_state = "malformed"
            elif invocation.exit_status != 0:
                attempt_state = "failed"
            else:
                attempt_state = "completed"
            relationship: Literal["initial", "continuation", "retry", "recovery"]
            if attempt_number > 1:
                relationship = "retry"
            elif pending_feedback:
                relationship = "recovery"
            elif logical_turn == 1:
                relationship = "initial"
            else:
                relationship = "continuation"
            cleaned = _derivative_artifact(
                result_dir,
                f"transcript/derived/turns/{turn_id}/{attempt_id}.cleaned.txt",
                _clean_response(invocation.stdout),
                source_event_id=event_id,
            )
            model_event = ModelAttemptEvent(
                event_id=event_id,
                sequence=len(events),
                kind="model_attempt",
                branch_id="main",
                execution_status=attempt_state,
                role="assistant",
                turn_id=turn_id,
                attempt_id=attempt_id,
                input_state_id=current_state_id,
                relationship=relationship,
                attempt_state=attempt_state,
                exit_status=invocation.exit_status,
                parent_event_id=successful_events[-1].event_id
                if successful_events
                else task_event_id,
                retry_of_event_id=prior_attempt_event_id,
                consumed_feedback_ids=pending_feedback,
                recovery_of_feedback_ids=pending_feedback
                if relationship == "recovery"
                else [],
                raw_input=raw_input,
                raw_output=raw_output,
                runtime_stderr=stderr,
                cleaned_output=cleaned,
            )
            events.append(model_event)
            if attempt_state == "completed":
                completed_event = model_event
                successful_events.append(model_event)
                messages.append({"role": "assistant", "content": invocation.stdout})
                previous_state_id = current_state_id
                current_state_id = f"state-{logical_turn:03d}-response"
                new_state_event_id = next_event_id("state")
                visible_ref = _source_artifact(
                    result_dir,
                    f"transcript/source/states/{current_state_id}.json",
                    _json_document(
                        {"state_id": current_state_id, "messages": messages}
                    ),
                )
                events.append(
                    StateEvent(
                        event_id=new_state_event_id,
                        sequence=len(events),
                        kind="state",
                        branch_id="main",
                        execution_status="not_executed",
                        role="protocol",
                        state_id=current_state_id,
                        previous_state_id=previous_state_id,
                        caused_by_event_id=event_id,
                        visible_messages=visible_ref,
                    )
                )
                break
            failed_attempts += 1
            prior_attempt_event_id = event_id
            if attempt_number == limits.max_attempts_per_turn:
                completion_state = "partial"
                completion_actor = "runtime"
                terminal_reason = (
                    "timeout"
                    if attempt_state == "timeout"
                    else "malformed_response"
                    if attempt_state == "malformed"
                    else "runtime_failure"
                )
                stop = True

        if stop or completed_event is None:
            break

        scheduled = [
            definition
            for definition in task.feedback
            if definition.after_model_turn == logical_turn
        ]
        for definition in scheduled:
            planned = feedback_plan_by_id[definition.feedback_id]
            feedback_event_id = next_event_id("feedback")
            feedback_event = FeedbackEvent(
                event_id=feedback_event_id,
                sequence=len(events),
                kind="feedback",
                branch_id="main",
                execution_status="not_executed",
                role="evaluator",
                feedback_id=definition.feedback_id,
                supplied_inert=True,
            )
            events.append(feedback_event)
            planned.lifecycle_state = "supplied_unconsumed"
            planned.disposition_reason = (
                "no_admitted_follow_up_turn"
                if logical_turn == effective_turns
                else "conversation_terminated_before_consumption"
            )
            planned.supplied_event_id = feedback_event_id
            messages.append(
                {
                    "role": "feedback",
                    "feedback_id": definition.feedback_id,
                    "content": definition.content,
                }
            )
            previous_state_id = current_state_id
            current_state_id = (
                f"state-{logical_turn:03d}-feedback-{definition.feedback_id}"
            )
            feedback_state_event_id = next_event_id("state")
            visible_ref = _source_artifact(
                result_dir,
                f"transcript/source/states/{current_state_id}.json",
                _json_document({"state_id": current_state_id, "messages": messages}),
            )
            events.append(
                StateEvent(
                    event_id=feedback_state_event_id,
                    sequence=len(events),
                    kind="state",
                    branch_id="main",
                    execution_status="not_executed",
                    role="protocol",
                    state_id=current_state_id,
                    previous_state_id=previous_state_id,
                    caused_by_event_id=feedback_event_id,
                    visible_messages=visible_ref,
                )
            )

        remaining_scheduled = any(
            feedback.after_model_turn > logical_turn for feedback in task.feedback
        )
        unconsumed = any(
            item.lifecycle_state == "supplied_unconsumed" for item in feedback_plan
        )
        if logical_turn == effective_turns and (remaining_scheduled or unconsumed):
            completion_state = "partial"
            completion_actor = "protocol"
            terminal_reason = "turn_limit"
        elif not remaining_scheduled and not unconsumed:
            break

    selected_event = successful_events[-1] if completion_state == "completed" else None
    terminal_event_id = next_event_id("terminal")
    events.append(
        TerminalEvent(
            event_id=terminal_event_id,
            sequence=len(events),
            kind="terminal",
            branch_id="main",
            execution_status="not_applicable",
            role="protocol",
            completion_state=completion_state,
            completion_actor=completion_actor,
            terminal_reason=terminal_reason,
            final_response_event_id=selected_event.event_id if selected_event else None,
        )
    )

    review_state: ReviewState = (
        "unreviewed" if completion_state == "completed" else "incomplete"
    )
    transcript = Transcript(
        schema_version=TRANSCRIPT_SCHEMA_VERSION,
        protocol_id=PROTOCOL_ID,
        protocol_version=PROTOCOL_VERSION,
        evaluation_class="native_multi_turn_response",
        conversation_id=conversation_id,
        suite_id=suite_id,
        suite_version=suite_version,
        task_id=task.task_id,
        task_version=task.task_version,
        task_selection=TaskSelection(kind="exact_task", selected_task_id=task.task_id),
        initial_state_id=task.initial_state_id,
        initial_state_sha256=initial_hash,
        producer_id="llmgauge",
        producer_version=__version__,
        result_provenance=ResultProvenanceRelationship(),
        declared_limits=limits,
        effective_model_turn_limit=effective_turns,
        feedback_plan=feedback_plan,
        completion_state=completion_state,
        completion_actor=completion_actor,
        terminal_reason=terminal_reason,
        selected_branch_id="main" if completion_state == "completed" else None,
        final_response_event_id=selected_event.event_id if selected_event else None,
        events=events,
        branches=[
            BranchRecord(
                branch_id="main",
                state="selected" if completion_state == "completed" else "abandoned",
            )
        ],
        review=ReviewHooks(
            scoreability="unreviewed"
            if completion_state == "completed"
            else "unscoreable",
            per_turn=review_state,
            feedback_use=review_state,
            correction=review_state,
            recovery=review_state,
            consistency=review_state,
            final_response=review_state,
        ),
    )
    errors = validate_transcript_structure(transcript)
    if errors:
        raise TranscriptDefinitionError("; ".join(errors))
    write_transcript(result_dir, transcript)
    return ConversationOutcome(
        transcript=transcript,
        selected_event=selected_event,
        failed_attempts=failed_attempts,
    )


def write_transcript(result_dir: Path, transcript: Transcript) -> Path:
    path = result_dir / TRANSCRIPT_RELATIVE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    content = (
        json.dumps(
            transcript.model_dump(mode="json"),
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        )
        + "\n"
    )
    temporary = path.with_suffix(".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)
    return path


def build_result_transcript_reference(
    result_dir: Path, transcript: Transcript
) -> dict[str, str]:
    path = result_dir / TRANSCRIPT_RELATIVE_PATH
    sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
    return {
        "path": TRANSCRIPT_RELATIVE_PATH,
        "schema_version": transcript.schema_version,
        "protocol_id": transcript.protocol_id,
        "protocol_version": transcript.protocol_version,
        "conversation_id": transcript.conversation_id,
        "sha256": sha256,
    }


def validate_transcript_artifacts(
    result_dir: Path, transcript: Transcript
) -> list[str]:
    from llmgauge.core.run_fingerprint import resolve_contained_result_artifact

    errors: list[str] = []
    seen_paths: dict[str, str] = {}

    def validate_reference(label: str, reference: ArtifactReference) -> None:
        if reference.path is None:
            return
        owner = seen_paths.get(reference.path)
        if owner is not None:
            errors.append(f"{label}.path duplicates authority owned by {owner}")
            return
        seen_paths[reference.path] = label
        try:
            path = resolve_contained_result_artifact(
                result_dir,
                reference.path,
                label=f"{label}.path",
            )
            size = path.stat().st_size
            if size > MAX_ARTIFACT_BYTES:
                errors.append(f"{label}.path exceeds {MAX_ARTIFACT_BYTES} bytes")
                return
            observed = hashlib.sha256(path.read_bytes()).hexdigest()
            if observed != reference.sha256:
                errors.append(f"{label}.sha256 does not match artifact")
        except (OSError, ValueError) as exc:
            errors.append(str(exc))

    for index, planned in enumerate(transcript.feedback_plan):
        validate_reference(f"feedback_plan[{index}].raw_content", planned.raw_content)
    for event in transcript.events:
        references: list[tuple[str, ArtifactReference]] = []
        if isinstance(event, TaskEvent):
            references.append(("raw_input", event.raw_input))
        elif isinstance(event, ModelAttemptEvent):
            references.extend(
                [
                    ("raw_input", event.raw_input),
                    ("raw_output", event.raw_output),
                    ("runtime_stderr", event.runtime_stderr),
                ]
            )
            if event.cleaned_output is not None:
                references.append(("cleaned_output", event.cleaned_output))
        elif isinstance(event, StateEvent):
            references.append(("visible_messages", event.visible_messages))
        for field_name, reference in references:
            validate_reference(
                f"events[{event.sequence}].{field_name}",
                reference,
            )
    return errors


def validate_transcript_structure(transcript: Transcript) -> list[str]:
    errors: list[str] = []
    events = transcript.events
    if not events:
        return ["transcript.events must not be empty"]
    if [event.sequence for event in events] != list(range(len(events))):
        errors.append(
            "event sequence must be contiguous and match canonical array order"
        )
    event_ids = [event.event_id for event in events]
    if len(event_ids) != len(set(event_ids)):
        errors.append("event IDs must be unique")
    for event in events:
        try:
            _require_id(event.event_id, "event_id")
            _require_id(event.branch_id, "branch_id")
        except ValueError as exc:
            errors.append(str(exc))
        if event.source_derivative_role != "source":
            errors.append(f"{event.event_id} must remain authoritative source evidence")
    task_events = [event for event in events if isinstance(event, TaskEvent)]
    model_events = [event for event in events if isinstance(event, ModelAttemptEvent)]
    feedback_events = [event for event in events if isinstance(event, FeedbackEvent)]
    state_events = [event for event in events if isinstance(event, StateEvent)]
    terminal_events = [event for event in events if isinstance(event, TerminalEvent)]
    if len(task_events) != 1 or not isinstance(events[0], TaskEvent):
        errors.append("exactly one task event must be first")
    if not model_events:
        errors.append("at least one model_attempt event is required")
    if len(terminal_events) != 1 or not isinstance(events[-1], TerminalEvent):
        errors.append("exactly one terminal event must be last")

    if (
        transcript.effective_model_turn_limit
        > transcript.declared_limits.max_model_turns
    ):
        errors.append("effective model-turn limit exceeds declared limit")
    if len(transcript.feedback_plan) > transcript.declared_limits.max_feedback_items:
        errors.append("feedback plan exceeds declared limit")
    planned_feedback_by_id: dict[str, FeedbackPlanItem] = {}
    for planned in transcript.feedback_plan:
        try:
            _require_id(planned.feedback_id, "feedback_id")
        except ValueError as exc:
            errors.append(str(exc))
        if planned.feedback_id in planned_feedback_by_id:
            errors.append(f"duplicate planned feedback ID {planned.feedback_id}")
        planned_feedback_by_id[planned.feedback_id] = planned
        if planned.after_model_turn > transcript.declared_limits.max_model_turns:
            errors.append(
                f"feedback {planned.feedback_id} schedule exceeds declared limit"
            )
        if (
            planned.raw_content.role != "source"
            or planned.raw_content.availability != "available"
            or planned.raw_content.capture_state != "complete"
            or planned.raw_content.truncated
            or planned.raw_content.redacted
        ):
            errors.append(
                f"feedback {planned.feedback_id} content must remain exact authoritative source"
            )

        if planned.lifecycle_state == "unreached":
            if (
                planned.disposition_reason != "scheduling_point_not_reached"
                or planned.supplied_event_id is not None
                or planned.consumed_by_turn_id is not None
            ):
                errors.append(
                    f"feedback {planned.feedback_id} has contradictory unreached state"
                )
        elif planned.lifecycle_state == "supplied_unconsumed":
            if (
                planned.disposition_reason
                not in {
                    "no_admitted_follow_up_turn",
                    "conversation_terminated_before_consumption",
                }
                or planned.supplied_event_id is None
                or planned.consumed_by_turn_id is not None
            ):
                errors.append(
                    f"feedback {planned.feedback_id} has contradictory supplied-unconsumed state"
                )
        elif (
            planned.disposition_reason != "consumed_by_model_turn"
            or planned.supplied_event_id is None
            or planned.consumed_by_turn_id is None
        ):
            errors.append(
                f"feedback {planned.feedback_id} has contradictory consumed state"
            )
        if (
            planned.after_model_turn > transcript.effective_model_turn_limit
            and planned.lifecycle_state != "unreached"
        ):
            errors.append(
                f"feedback {planned.feedback_id} beyond effective limit cannot be supplied"
            )

    event_positions = {event.event_id: event.sequence for event in events}
    branch_ids = [branch.branch_id for branch in transcript.branches]
    if len(branch_ids) != len(set(branch_ids)):
        errors.append("branch IDs must be unique")
    branch_map = {branch.branch_id: branch for branch in transcript.branches}
    if "main" not in branch_map:
        errors.append("main branch is required")
    for event in events:
        if event.branch_id not in branch_map:
            errors.append(
                f"{event.event_id} references unknown branch {event.branch_id}"
            )
    for branch in transcript.branches:
        try:
            _require_id(branch.branch_id, "branch_id")
        except ValueError as exc:
            errors.append(str(exc))
        if (
            branch.parent_branch_id is not None
            and branch.parent_branch_id not in branch_map
        ):
            errors.append(f"branch {branch.branch_id} has unknown parent")
        if branch.branch_point_event_id is not None:
            position = event_positions.get(branch.branch_point_event_id)
            first_position = min(
                (
                    event.sequence
                    for event in events
                    if event.branch_id == branch.branch_id
                ),
                default=len(events),
            )
            if position is None or position >= first_position:
                errors.append(f"branch {branch.branch_id} has invalid branch point")
        visited: set[str] = set()
        cursor: BranchRecord | None = branch
        while cursor is not None and cursor.parent_branch_id is not None:
            if cursor.branch_id in visited:
                errors.append(f"branch cycle includes {cursor.branch_id}")
                break
            visited.add(cursor.branch_id)
            cursor = branch_map.get(cursor.parent_branch_id)

    state_positions: dict[str, int] = {}
    for state in state_events:
        if state.state_id in state_positions:
            errors.append(f"duplicate state ID {state.state_id}")
        state_positions[state.state_id] = state.sequence
        cause_position = event_positions.get(state.caused_by_event_id)
        if cause_position is None or cause_position >= state.sequence:
            errors.append(
                f"state {state.state_id} has invalid forward or unknown cause"
            )
        if state.previous_state_id is not None:
            previous_position = state_positions.get(state.previous_state_id)
            if previous_position is None or previous_position >= state.sequence:
                errors.append(f"state {state.state_id} has invalid previous state")
    if transcript.initial_state_id not in state_positions:
        errors.append("initial_state_id has no state event")
    elif task_events and task_events[0].initial_state_id != transcript.initial_state_id:
        errors.append("task initial_state_id does not match transcript")
    if (
        task_events
        and task_events[0].initial_state_sha256 != transcript.initial_state_sha256
    ):
        errors.append("task initial_state_sha256 does not match transcript")
    if state_events:
        initial_state = state_events[0]
        if (
            initial_state.state_id != transcript.initial_state_id
            or initial_state.previous_state_id is not None
            or not task_events
            or initial_state.caused_by_event_id != task_events[0].event_id
        ):
            errors.append("first state event must establish the declared initial state")

    turn_attempts: dict[str, list[ModelAttemptEvent]] = {}
    model_by_id = {event.event_id: event for event in model_events}
    attempt_ids: set[str] = set()
    feedback_by_id: dict[str, FeedbackEvent] = {}
    for feedback in feedback_events:
        if feedback.feedback_id in feedback_by_id:
            errors.append(f"duplicate supplied feedback ID {feedback.feedback_id}")
        feedback_by_id[feedback.feedback_id] = feedback
        planned = planned_feedback_by_id.get(feedback.feedback_id)
        if planned is None:
            errors.append(
                f"supplied feedback {feedback.feedback_id} has no declaration"
            )
        elif planned.lifecycle_state == "unreached":
            errors.append(
                f"unreached feedback {feedback.feedback_id} has a supply event"
            )
        elif planned.supplied_event_id != feedback.event_id:
            errors.append(
                f"feedback {feedback.feedback_id} supply event does not match plan"
            )
        if (
            feedback.supplied_inert is not True
            or feedback.execution_status != "not_executed"
        ):
            errors.append(
                f"feedback {feedback.feedback_id} must remain inert and unexecuted"
            )
        completed_before_supply = {
            model.turn_id
            for model in model_events
            if model.attempt_state == "completed" and model.sequence < feedback.sequence
        }
        if (
            planned is not None
            and len(completed_before_supply) != planned.after_model_turn
        ):
            errors.append(
                f"feedback {feedback.feedback_id} supply event conflicts with schedule"
            )
        supplied_states = [
            state
            for state in state_events
            if state.caused_by_event_id == feedback.event_id
        ]
        if len(supplied_states) != 1:
            errors.append(
                f"feedback {feedback.feedback_id} requires one supplied visible state"
            )
    for planned in transcript.feedback_plan:
        supplied = feedback_by_id.get(planned.feedback_id)
        if planned.lifecycle_state == "unreached":
            if supplied is not None:
                errors.append(
                    f"unreached feedback {planned.feedback_id} cannot be supplied"
                )
        elif supplied is None:
            errors.append(
                f"feedback {planned.feedback_id} claims supply without a supply event"
            )
    previous_model: ModelAttemptEvent | None = None
    for model in model_events:
        existing_turn_attempts = turn_attempts.setdefault(model.turn_id, [])
        if model.attempt_id in attempt_ids:
            errors.append(f"duplicate attempt ID {model.attempt_id}")
        attempt_ids.add(model.attempt_id)
        try:
            _require_id(model.turn_id, "turn_id")
            _require_id(model.attempt_id, "attempt_id")
        except ValueError as exc:
            errors.append(str(exc))
        if model.execution_status != model.attempt_state:
            errors.append(
                f"{model.event_id} execution status conflicts with attempt state"
            )
        input_position = state_positions.get(model.input_state_id)
        if input_position is None or input_position >= model.sequence:
            errors.append(f"{model.event_id} references unknown or forward input state")
        if model.parent_event_id is not None:
            parent_position = event_positions.get(model.parent_event_id)
            if parent_position is None or parent_position >= model.sequence:
                errors.append(f"{model.event_id} has invalid parent reference")
        if model.relationship == "retry":
            retry = model_by_id.get(model.retry_of_event_id or "")
            if retry is None or retry.sequence >= model.sequence:
                errors.append(f"{model.event_id} has invalid retry reference")
            else:
                if not existing_turn_attempts or retry.turn_id != model.turn_id:
                    errors.append(
                        f"{model.event_id} retry does not share its logical turn"
                    )
                if previous_model is None or retry.event_id != previous_model.event_id:
                    errors.append(
                        f"{model.event_id} retry must target the previous attempt"
                    )
                if retry.attempt_state == "completed":
                    errors.append(f"{model.event_id} retry targets a completed attempt")
                if retry.input_state_id != model.input_state_id:
                    errors.append(f"{model.event_id} retry changed input state")
                if retry.raw_input.sha256 != model.raw_input.sha256:
                    errors.append(f"{model.event_id} retry changed rendered input")
                if retry.consumed_feedback_ids != model.consumed_feedback_ids:
                    errors.append(f"{model.event_id} retry changed consumed feedback")
                if (
                    retry.parent_event_id != model.parent_event_id
                    or retry.branch_id != model.branch_id
                ):
                    errors.append(
                        f"{model.event_id} retry changed logical turn ancestry"
                    )
        else:
            if existing_turn_attempts:
                errors.append(
                    f"{model.event_id} reuses turn ID across unrelated logical turns"
                )
            if model.retry_of_event_id is not None:
                errors.append(
                    f"{model.event_id} has retry reference without retry relationship"
                )
        if model.relationship == "recovery":
            if (
                not model.recovery_of_feedback_ids
                or model.recovery_of_feedback_ids != model.consumed_feedback_ids
            ):
                errors.append(
                    f"{model.event_id} recovery feedback must match consumed feedback"
                )
        elif model.recovery_of_feedback_ids:
            errors.append(
                f"{model.event_id} has recovery feedback without recovery relationship"
            )
        if model.relationship in {"initial", "continuation"} and (
            model.consumed_feedback_ids
        ):
            errors.append(
                f"{model.event_id} consumes feedback without recovery relationship"
            )
        if len(model.consumed_feedback_ids) != len(set(model.consumed_feedback_ids)):
            errors.append(f"{model.event_id} repeats consumed feedback")
        for feedback_id in model.consumed_feedback_ids:
            planned = planned_feedback_by_id.get(feedback_id)
            feedback = feedback_by_id.get(feedback_id)
            if (
                planned is None
                or feedback is None
                or feedback.sequence >= model.sequence
            ):
                errors.append(
                    f"{model.event_id} consumes unknown, unsupplied, or future feedback {feedback_id}"
                )
            elif (
                planned.lifecycle_state != "consumed"
                or planned.consumed_by_turn_id != model.turn_id
            ):
                errors.append(f"feedback {feedback_id} lacks reciprocal consuming turn")
        for feedback_id in model.recovery_of_feedback_ids:
            if feedback_id not in model.consumed_feedback_ids:
                errors.append(f"{model.event_id} recovery feedback was not consumed")
        existing_turn_attempts.append(model)
        previous_model = model

    retry_cycle_reported = False
    for model in model_events:
        seen_retry_events: set[str] = set()
        current = model
        while current.retry_of_event_id is not None:
            if current.event_id in seen_retry_events:
                if not retry_cycle_reported:
                    errors.append("retry cycle detected")
                    retry_cycle_reported = True
                break
            seen_retry_events.add(current.event_id)
            target = model_by_id.get(current.retry_of_event_id)
            if target is None:
                break
            current = target

    for planned in transcript.feedback_plan:
        consumers = turn_attempts.get(planned.consumed_by_turn_id or "", [])
        if planned.lifecycle_state == "consumed":
            supplied = feedback_by_id.get(planned.feedback_id)
            if (
                supplied is None
                or not consumers
                or consumers[0].sequence <= supplied.sequence
            ):
                errors.append(
                    f"feedback {planned.feedback_id} has invalid consuming turn"
                )
            elif any(
                planned.feedback_id not in attempt.consumed_feedback_ids
                for attempt in consumers
            ):
                errors.append(
                    f"feedback {planned.feedback_id} missing from consuming turn"
                )
        elif consumers:
            errors.append(
                f"unconsumed feedback {planned.feedback_id} names a consuming turn"
            )
        supplied = feedback_by_id.get(planned.feedback_id)
        if (
            planned.lifecycle_state == "supplied_unconsumed"
            and supplied is not None
            and any(model.sequence > supplied.sequence for model in model_events)
        ):
            errors.append(
                f"supplied-unconsumed feedback {planned.feedback_id} has a later model turn"
            )
        if planned.lifecycle_state == "unreached" and planned.after_model_turn <= len(
            {
                model.turn_id
                for model in model_events
                if model.attempt_state == "completed"
            }
        ):
            errors.append(
                f"feedback {planned.feedback_id} was reached but marked unreached"
            )
        if (
            planned.lifecycle_state == "supplied_unconsumed"
            and planned.disposition_reason == "no_admitted_follow_up_turn"
            and planned.after_model_turn != transcript.effective_model_turn_limit
        ):
            errors.append(
                f"feedback {planned.feedback_id} has invalid no-follow-up reason"
            )
        if planned.lifecycle_state == "consumed":
            supplied = feedback_by_id.get(planned.feedback_id)
            next_model = (
                next(
                    (
                        model
                        for model in model_events
                        if supplied is not None and model.sequence > supplied.sequence
                    ),
                    None,
                )
                if supplied is not None
                else None
            )
            if next_model is None or next_model.turn_id != planned.consumed_by_turn_id:
                errors.append(
                    f"feedback {planned.feedback_id} was not consumed by the next logical turn"
                )

    if len(turn_attempts) > transcript.declared_limits.max_model_turns:
        errors.append("model turns exceed declared limit")
    if len(turn_attempts) > transcript.effective_model_turn_limit:
        errors.append("model turns exceed effective limit")
    if any(
        len(attempts) > transcript.declared_limits.max_attempts_per_turn
        for attempts in turn_attempts.values()
    ):
        errors.append("attempts exceed declared per-turn limit")

    terminal = terminal_events[0] if len(terminal_events) == 1 else None
    valid_completion = (
        transcript.completion_state == "completed"
        and transcript.terminal_reason == "completed"
        and transcript.final_response_event_id is not None
        and transcript.selected_branch_id is not None
    )
    if transcript.completion_state == "completed" and not valid_completion:
        errors.append(
            "completed transcript requires completed reason, final response, and branch"
        )
    if (
        transcript.completion_state != "completed"
        and transcript.terminal_reason == "completed"
    ):
        errors.append("partial or abandoned transcript cannot use completed reason")
    if (
        transcript.completion_state == "abandoned"
        and transcript.terminal_reason != "abandoned"
    ):
        errors.append("abandoned transcript requires abandoned reason")
    allowed_terminal_actors: dict[TerminalReason, set[CompletionActor]] = {
        "completed": {"evaluator", "model"},
        "turn_limit": {"protocol"},
        "timeout": {"runtime"},
        "runtime_failure": {"runtime"},
        "malformed_response": {"runtime"},
        "operator_stop": {"operator"},
        "interrupted": {"operator", "protocol", "runtime"},
        "abandoned": {"operator", "protocol"},
    }
    if (
        transcript.completion_actor
        not in allowed_terminal_actors[transcript.terminal_reason]
    ):
        errors.append("completion actor is inconsistent with terminal reason")
    if transcript.completion_state == "completed":
        if transcript.review.scoreability != "unreviewed" or any(
            getattr(transcript.review, field) != "unreviewed"
            for field in (
                "per_turn",
                "feedback_use",
                "correction",
                "recovery",
                "consistency",
                "final_response",
            )
        ):
            errors.append("completed transcript review hooks must remain unreviewed")
    elif transcript.review.scoreability != "unscoreable":
        errors.append("partial or abandoned transcript must be unscoreable")
    final_event = model_by_id.get(transcript.final_response_event_id or "")
    if transcript.final_response_event_id is not None:
        if final_event is None or final_event.attempt_state != "completed":
            errors.append(
                "final_response_event_id must select a completed model attempt"
            )
    if terminal is not None and (
        terminal.completion_state != transcript.completion_state
        or terminal.completion_actor != transcript.completion_actor
        or terminal.terminal_reason != transcript.terminal_reason
        or terminal.final_response_event_id != transcript.final_response_event_id
    ):
        errors.append("terminal event does not match transcript terminal fields")
    if transcript.selected_branch_id is not None:
        selected = branch_map.get(transcript.selected_branch_id)
        if selected is None or selected.state != "selected":
            errors.append("selected_branch_id must reference selected branch")
    selected_branches = [
        branch for branch in transcript.branches if branch.state == "selected"
    ]
    if transcript.completion_state == "completed" and len(selected_branches) != 1:
        errors.append("completed transcript requires exactly one selected branch")
    if (
        final_event is not None
        and transcript.selected_branch_id is not None
        and final_event.branch_id != transcript.selected_branch_id
    ):
        errors.append("final response must belong to the selected branch")
    if transcript.task_selection.selected_task_id != transcript.task_id:
        errors.append("task selection does not match task_id")

    for event in events:
        references: list[ArtifactReference] = []
        source_references: list[ArtifactReference] = []
        derivative_references: list[ArtifactReference] = []
        if isinstance(event, TaskEvent):
            references = [event.raw_input]
            source_references = [event.raw_input]
        elif isinstance(event, ModelAttemptEvent):
            references = [event.raw_input, event.raw_output, event.runtime_stderr]
            source_references = [
                event.raw_input,
                event.raw_output,
                event.runtime_stderr,
            ]
            if event.cleaned_output is not None:
                references.append(event.cleaned_output)
                derivative_references.append(event.cleaned_output)
        elif isinstance(event, StateEvent):
            references = [event.visible_messages]
            source_references = [event.visible_messages]
        if any(reference.role != "source" for reference in source_references):
            errors.append(f"{event.event_id} required evidence must remain source")
        if transcript.completion_state == "completed" and any(
            reference.availability != "available" for reference in source_references
        ):
            errors.append(f"{event.event_id} completed evidence must remain available")
        if any(reference.role != "derivative" for reference in derivative_references):
            errors.append(f"{event.event_id} cleaned evidence must remain derivative")
        for reference in references:
            if reference.role == "derivative":
                source_position = event_positions.get(reference.source_event_id or "")
                if source_position is None or source_position > event.sequence:
                    errors.append(
                        f"{event.event_id} derivative has invalid source event"
                    )
    return errors


def validate_result_transcript(
    result_dir: Path, result: Mapping[str, Any]
) -> list[str]:
    reference = result.get("transcript")
    if reference is None:
        return []
    if not isinstance(reference, Mapping):
        return ["transcript must be an object"]
    required = {
        "path",
        "schema_version",
        "protocol_id",
        "protocol_version",
        "conversation_id",
        "sha256",
    }
    if set(reference) != required:
        return [
            "transcript reference must contain exactly: " + ", ".join(sorted(required))
        ]
    try:
        transcript = load_transcript(result_dir, str(reference.get("path", "")))
    except TranscriptDefinitionError as exc:
        return [f"transcript: {exc}"]
    errors = validate_transcript_structure(transcript)
    errors.extend(validate_transcript_artifacts(result_dir, transcript))
    for field in (
        "schema_version",
        "protocol_id",
        "protocol_version",
        "conversation_id",
    ):
        if reference.get(field) != getattr(transcript, field):
            errors.append(f"transcript.{field} does not match contained transcript")
    try:
        transcript_path = result_dir / str(reference["path"])
        observed = hashlib.sha256(transcript_path.read_bytes()).hexdigest()
        if reference.get("sha256") != observed:
            errors.append("transcript.sha256 does not match contained transcript")
    except OSError as exc:
        errors.append(f"transcript artifact is unreadable: {exc}")
    results = result.get("results")
    if (
        not isinstance(results, list)
        or len(results) != 1
        or not isinstance(results[0], Mapping)
    ):
        errors.append(
            "native transcript result requires exactly one prompt compatibility result"
        )
    else:
        prompt_result = results[0]
        if prompt_result.get("prompt_id") != transcript.task_id:
            errors.append("prompt result does not match transcript task_id")
        selected = transcript.final_response_event_id
        if prompt_result.get("transcript_event_id") != selected:
            errors.append(
                "prompt result transcript_event_id does not match final response"
            )
        model_attempts = [
            event for event in transcript.events if isinstance(event, ModelAttemptEvent)
        ]
        if selected is None:
            compatibility_attempt = model_attempts[-1] if model_attempts else None
        else:
            compatibility_attempt = next(
                (event for event in model_attempts if event.event_id == selected),
                None,
            )
        if (
            compatibility_attempt is not None
            and prompt_result.get("exit_status") != compatibility_attempt.exit_status
        ):
            errors.append(
                "prompt result exit_status does not match compatibility attempt"
            )
        if prompt_result.get("score") is not None:
            errors.append("native transcript prompt score must remain null")
    suite = result.get("suite")
    if isinstance(suite, Mapping):
        if (
            suite.get("suite_id") != transcript.suite_id
            or str(suite.get("suite_version")) != transcript.suite_version
        ):
            errors.append("result suite identity does not match transcript")
    return errors


def immutable_transcript_payload(transcript: Transcript) -> dict[str, Any]:
    immutable_events: list[dict[str, Any]] = []
    for event in transcript.events:
        item: dict[str, Any] = {
            "event_id": event.event_id,
            "sequence": event.sequence,
            "kind": event.kind,
            "branch_id": event.branch_id,
            "execution_status": event.execution_status,
        }
        if isinstance(event, TaskEvent):
            item.update(
                initial_state_id=event.initial_state_id,
                initial_state_sha256=event.initial_state_sha256,
                raw_input_sha256=event.raw_input.sha256,
            )
        elif isinstance(event, ModelAttemptEvent):
            item.update(
                turn_id=event.turn_id,
                attempt_id=event.attempt_id,
                input_state_id=event.input_state_id,
                relationship=event.relationship,
                attempt_state=event.attempt_state,
                exit_status=event.exit_status,
                parent_event_id=event.parent_event_id,
                retry_of_event_id=event.retry_of_event_id,
                consumed_feedback_ids=event.consumed_feedback_ids,
                recovery_of_feedback_ids=event.recovery_of_feedback_ids,
                raw_input_sha256=event.raw_input.sha256,
                raw_output_sha256=event.raw_output.sha256,
                runtime_stderr_sha256=event.runtime_stderr.sha256,
            )
        elif isinstance(event, FeedbackEvent):
            item.update(
                feedback_id=event.feedback_id,
                supplied_inert=event.supplied_inert,
            )
        elif isinstance(event, StateEvent):
            item.update(
                state_id=event.state_id,
                previous_state_id=event.previous_state_id,
                caused_by_event_id=event.caused_by_event_id,
                visible_messages_sha256=event.visible_messages.sha256,
            )
        elif isinstance(event, TerminalEvent):
            item.update(
                completion_state=event.completion_state,
                completion_actor=event.completion_actor,
                terminal_reason=event.terminal_reason,
                final_response_event_id=event.final_response_event_id,
            )
        immutable_events.append(item)
    return {
        "schema_version": transcript.schema_version,
        "protocol_id": transcript.protocol_id,
        "protocol_version": transcript.protocol_version,
        "evaluation_class": transcript.evaluation_class,
        "conversation_id": transcript.conversation_id,
        "suite_id": transcript.suite_id,
        "suite_version": transcript.suite_version,
        "task_id": transcript.task_id,
        "task_version": transcript.task_version,
        "task_selection": transcript.task_selection.model_dump(mode="json"),
        "initial_state_id": transcript.initial_state_id,
        "initial_state_sha256": transcript.initial_state_sha256,
        "producer_id": transcript.producer_id,
        "producer_version": transcript.producer_version,
        "result_provenance": transcript.result_provenance.model_dump(mode="json"),
        "declared_limits": transcript.declared_limits.model_dump(mode="json"),
        "effective_model_turn_limit": transcript.effective_model_turn_limit,
        "feedback_plan": [
            {
                "feedback_id": planned.feedback_id,
                "origin": planned.origin,
                "after_model_turn": planned.after_model_turn,
                "raw_content_sha256": planned.raw_content.sha256,
                "lifecycle_state": planned.lifecycle_state,
                "disposition_reason": planned.disposition_reason,
                "supplied_event_id": planned.supplied_event_id,
                "consumed_by_turn_id": planned.consumed_by_turn_id,
            }
            for planned in transcript.feedback_plan
        ],
        "completion_state": transcript.completion_state,
        "completion_actor": transcript.completion_actor,
        "terminal_reason": transcript.terminal_reason,
        "selected_branch_id": transcript.selected_branch_id,
        "final_response_event_id": transcript.final_response_event_id,
        "branches": [branch.model_dump(mode="json") for branch in transcript.branches],
        "events": immutable_events,
    }
