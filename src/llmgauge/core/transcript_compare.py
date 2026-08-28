"""Bounded structural transcript comparison.

Implements the accepted
``docs/TRANSCRIPT_COMPARISON_REVIEW_CONTRACT.md`` V1 slice: eligibility
classification, side-by-side structural facts, preserved role/ordering
semantics, and manual-review hook presentation for transcript-bearing
results. No session aggregate, no ranking, no winner claim.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from llmgauge.core.multi_turn import (
    ArtifactReference,
    FeedbackEvent,
    ModelAttemptEvent,
    StateEvent,
    TaskEvent,
    TerminalEvent,
    Transcript,
    load_transcript,
)

TRANSCRIPT_COMPARISON_CLASSIFIER = "llmgauge.transcript_compare.v0"


def _result_label(result: dict[str, Any]) -> str:
    model_id = result.get("model", {}).get("model_id", "unknown-model")
    run_id = result.get("run", {}).get("run_id", "unknown-run")
    return f"{model_id} ({run_id})"


_IDENTITY_FIELDS = (
    "protocol_id",
    "protocol_version",
    "task_id",
    "task_version",
    "initial_state_id",
    "initial_state_sha256",
    "suite_id",
    "suite_version",
    "effective_max_model_turns",
    "max_attempts_per_turn",
    "max_feedback_items",
)

_REVIEW_HOOKS = (
    "scoreability",
    "per_turn",
    "feedback_use",
    "correction",
    "recovery",
    "consistency",
    "final_response",
)


class TranscriptComparisonError(ValueError):
    """Raised when transcript comparison cannot proceed under the contract."""


def load_transcript_for_compare(result: dict[str, Any]) -> Transcript:
    """Load the transcript referenced by a result dictionary."""
    reference = result.get("transcript")
    if not isinstance(reference, dict):
        raise TranscriptComparisonError(
            "Result is marked transcript-bearing but has no transcript reference"
        )
    result_dir_value = result.get("_result_dir")
    if not result_dir_value:
        raise TranscriptComparisonError(
            "Transcript comparison requires the loaded result directory"
        )
    return load_transcript(Path(str(result_dir_value)), str(reference.get("path", "")))


def transcript_identity(transcript: Transcript) -> dict[str, Any]:
    """Return the closed eligibility identity defined by the contract."""
    return {
        "protocol_id": transcript.protocol_id,
        "protocol_version": transcript.protocol_version,
        "task_id": transcript.task_id,
        "task_version": transcript.task_version,
        "initial_state_id": transcript.initial_state_id,
        "initial_state_sha256": transcript.initial_state_sha256,
        "suite_id": transcript.suite_id,
        "suite_version": transcript.suite_version,
        "effective_max_model_turns": transcript.effective_model_turn_limit,
        "max_attempts_per_turn": transcript.declared_limits.max_attempts_per_turn,
        "max_feedback_items": transcript.declared_limits.max_feedback_items,
    }


def _artifact_fields(transcript: Transcript) -> list[ArtifactReference]:
    artifacts: list[ArtifactReference] = []
    for planned in transcript.feedback_plan:
        artifacts.append(planned.raw_content)
    for event in transcript.events:
        if isinstance(event, TaskEvent):
            artifacts.append(event.raw_input)
        elif isinstance(event, ModelAttemptEvent):
            artifacts.extend([event.raw_input, event.raw_output, event.runtime_stderr])
            if event.cleaned_output is not None:
                artifacts.append(event.cleaned_output)
        elif isinstance(event, StateEvent):
            artifacts.append(event.visible_messages)
    return artifacts


def structural_facts(transcript: Transcript) -> dict[str, Any]:
    """Return only represented structural facts, never normalized."""
    attempts = [
        event for event in transcript.events if isinstance(event, ModelAttemptEvent)
    ]
    feedback_events = [
        event for event in transcript.events if isinstance(event, FeedbackEvent)
    ]
    state_events = [
        event for event in transcript.events if isinstance(event, StateEvent)
    ]
    artifacts = _artifact_fields(transcript)
    return {
        "completion_state": transcript.completion_state,
        "completion_actor": transcript.completion_actor,
        "terminal_reason": transcript.terminal_reason,
        "selected_branch_id": transcript.selected_branch_id,
        "final_response_event_id": transcript.final_response_event_id,
        "logical_model_turns": len({event.turn_id for event in attempts}),
        "model_attempts": len(attempts),
        "retries": sum(event.relationship == "retry" for event in attempts),
        "recoveries": sum(event.relationship == "recovery" for event in attempts),
        "attempt_outcomes": [
            f"{event.attempt_id}:{event.attempt_state}:exit={event.exit_status}"
            for event in attempts
        ],
        "declared_feedback_items": len(transcript.feedback_plan),
        "supplied_feedback_items": len(feedback_events),
        "consumed_feedback_items": sum(
            planned.lifecycle_state == "consumed"
            for planned in transcript.feedback_plan
        ),
        "supplied_unconsumed_feedback_items": sum(
            planned.lifecycle_state == "supplied_unconsumed"
            for planned in transcript.feedback_plan
        ),
        "unreached_feedback_items": sum(
            planned.lifecycle_state == "unreached"
            for planned in transcript.feedback_plan
        ),
        "feedback_dispositions": [
            f"{planned.feedback_id}:{planned.lifecycle_state}:"
            f"{planned.disposition_reason}"
            for planned in transcript.feedback_plan
        ],
        "state_transitions": len(state_events),
        "truncated_artifacts": sum(artifact.truncated for artifact in artifacts),
        "partial_artifacts": sum(
            artifact.capture_state == "partial" for artifact in artifacts
        ),
        "failed_artifacts": sum(
            artifact.capture_state == "failed" for artifact in artifacts
        ),
        "redacted_artifacts": sum(artifact.redacted for artifact in artifacts),
    }


def review_hooks(transcript: Transcript) -> dict[str, str]:
    """Return the closed review hooks exactly as recorded."""
    review = transcript.review.model_dump()
    return {hook: str(review[hook]) for hook in _REVIEW_HOOKS}


def classify_pair(
    identities: list[dict[str, Any]],
    facts: list[dict[str, Any]],
) -> dict[str, Any]:
    """Classify the compared set per the contract's three-way outcome."""
    mismatched = sorted(
        field
        for field in _IDENTITY_FIELDS
        if len({str(identity[field]) for identity in identities}) > 1
    )
    if mismatched:
        return {
            "eligible": False,
            "classification": "structurally incomparable",
            "mismatched_identity_fields": mismatched,
            "differing_facts": [],
            "completion_asymmetry": None,
        }
    differing = sorted(
        field for field in facts[0] if len({str(fact[field]) for fact in facts}) > 1
    )
    asymmetry = None
    if (
        len({fact["completion_state"] for fact in facts}) > 1
        or len({fact["terminal_reason"] for fact in facts}) > 1
    ):
        asymmetry = "; ".join(
            f"{fact['completion_state']}/{fact['terminal_reason']}" for fact in facts
        )
        return {
            "eligible": True,
            "classification": "structurally incomparable",
            "mismatched_identity_fields": [],
            "differing_facts": differing,
            "completion_asymmetry": asymmetry,
        }
    if not differing:
        classification = "identical structure"
    else:
        classification = "structurally comparable"
    return {
        "eligible": True,
        "classification": classification,
        "mismatched_identity_fields": [],
        "differing_facts": differing,
        "completion_asymmetry": None,
    }


def _fmt(value: Any) -> str:
    return "None" if value is None else str(value)


def _identity_lines(labels: list[str], identities: list[dict[str, Any]]) -> list[str]:
    lines = [
        "| Identity field | " + " | ".join(labels) + " |",
        "|---|" + "---|" * len(labels),
    ]
    for field in _IDENTITY_FIELDS:
        values = [_fmt(identity[field]) for identity in identities]
        marker = " (match)" if len(set(values)) == 1 else " (MISMATCH)"
        lines.append(f"| `{field}`{marker} | " + " | ".join(values) + " |")
    return lines


def _facts_lines(label: str, facts: dict[str, Any]) -> list[str]:
    lines = [f"### {label}", ""]
    for key, value in facts.items():
        if isinstance(value, list):
            rendered = ", ".join(str(item) for item in value) if value else "None"
        else:
            rendered = _fmt(value)
        lines.append(f"- {key}: `{rendered}`")
    lines.append("")
    return lines


def _event_order_lines(transcript: Transcript) -> list[str]:
    lines = [
        "Canonical ordered events (task first, terminal last; roles preserved "
        "as `user`/`assistant`/`evaluator`/`protocol`; missing turns are never "
        "synthesized):",
        "",
    ]
    for event in transcript.events:
        if isinstance(event, TaskEvent):
            detail = f"role `user`; initial state `{event.initial_state_id}`"
        elif isinstance(event, ModelAttemptEvent):
            links = []
            if event.relationship == "retry" and event.retry_of_event_id:
                links.append(f"retry of `{event.retry_of_event_id}`")
            if event.recovery_of_feedback_ids:
                links.append(
                    "recovery for feedback "
                    + ", ".join(f"`{fid}`" for fid in event.recovery_of_feedback_ids)
                )
            if event.consumed_feedback_ids:
                links.append(
                    "consumed "
                    + ", ".join(f"`{fid}`" for fid in event.consumed_feedback_ids)
                )
            link_text = f"; {'; '.join(links)}" if links else ""
            detail = (
                f"role `assistant`; turn `{event.turn_id}`; attempt "
                f"`{event.attempt_id}`; relationship `{event.relationship}`; "
                f"state `{event.attempt_state}`; exit status "
                f"`{event.exit_status}`{link_text}"
            )
        elif isinstance(event, FeedbackEvent):
            detail = (
                f"role `evaluator`; `{event.feedback_id}` inert supply "
                "occurrence (not executed work)"
            )
        elif isinstance(event, StateEvent):
            detail = (
                f"role `protocol`; state `{event.state_id}` from "
                f"`{_fmt(event.previous_state_id)}`"
            )
        elif isinstance(event, TerminalEvent):
            detail = (
                f"role `protocol`; `{event.completion_state}` / "
                f"`{event.terminal_reason}`; final "
                f"`{_fmt(event.final_response_event_id)}`"
            )
        else:
            detail = "unsupported event"
        lines.append(f"{event.sequence}. `{event.kind}` `{event.event_id}` — {detail}")
    lines.append("")
    return lines


def _review_lines(labels: list[str], hooks: list[dict[str, str]]) -> list[str]:
    lines = [
        "| Review hook | " + " | ".join(labels) + " |",
        "|---|" + "---|" * len(labels),
    ]
    for hook in _REVIEW_HOOKS:
        lines.append(
            f"| `{hook}` | " + " | ".join(f"`{item[hook]}`" for item in hooks) + " |"
        )
    return lines


def build_transcript_compare_report(results: list[dict[str, Any]]) -> str:
    """Build the bounded human-readable transcript comparison report."""
    if len(results) < 2:
        raise TranscriptComparisonError(
            "Transcript comparison requires at least two transcript-bearing results"
        )
    labels = [_result_label(result) for result in results]
    transcripts = [load_transcript_for_compare(result) for result in results]
    identities = [transcript_identity(transcript) for transcript in transcripts]
    facts = [structural_facts(transcript) for transcript in transcripts]
    hooks = [review_hooks(transcript) for transcript in transcripts]
    verdict = classify_pair(identities, facts)

    lines = [
        "# LLMGauge Transcript Comparison",
        "",
        f"- Classifier: `{TRANSCRIPT_COMPARISON_CLASSIFIER}`",
        "- Comparison is disclosure plus eligibility classification. It does "
        "not rank runs, declare winners, or imply quality equivalence.",
        "- No transcript/session aggregate score exists in V1.",
        "",
        "## Comparison eligibility",
        "",
    ]
    lines.extend(_identity_lines(labels, identities))
    lines.append("")
    if verdict["eligible"]:
        lines.append(
            "- Eligibility: **eligible for bounded structural comparison** "
            "(all identity fields match exactly)."
        )
    else:
        mismatched = ", ".join(
            f"`{field}`" for field in verdict["mismatched_identity_fields"]
        )
        lines.append(
            f"- Eligibility: **not comparable** — identity mismatch on {mismatched}. "
            "The transcripts are listed side by side below as independent "
            "evidence, labeled as such."
        )
    lines.append("")

    lines.extend(["## Structural classification", ""])
    lines.append(f"- Classification: **{verdict['classification']}**")
    if verdict["completion_asymmetry"]:
        lines.append(
            f"- Completion asymmetry: {verdict['completion_asymmetry']} — a "
            "partial, failed, or abandoned transcript is never presented as "
            "though completion occurred on every run."
        )
    if verdict["differing_facts"]:
        differing = ", ".join(f"`{field}`" for field in verdict["differing_facts"])
        lines.append(f"- Disclosed structural differences: {differing}.")
    lines.append("")

    lines.extend(["## Side-by-side structural facts", ""])
    for label, fact in zip(labels, facts):
        lines.extend(_facts_lines(label, fact))

    lines.extend(["## Turn and event ordering", ""])
    for label, transcript in zip(labels, transcripts):
        lines.append(f"### {label}")
        lines.append("")
        lines.extend(_event_order_lines(transcript))

    lines.extend(
        [
            "## Manual review evidence",
            "",
            "Review hooks are shown exactly as recorded. Reviewed, unreviewed, "
            "incomplete, and unscoreable states remain visibly distinct; no "
            "verdict is invented or implied.",
            "",
        ]
    )
    lines.extend(_review_lines(labels, hooks))
    lines.append("")

    lines.extend(
        [
            "## Claim boundaries",
            "",
            "- Structural transcript comparison proves only represented "
            "structural facts; it does not prove semantic quality, safety, "
            "correctness, or publication readiness.",
            "- Completion is not correctness; supplied inert feedback is not "
            "executed work; requested settings remain distinct from observed "
            "evidence.",
            "- Differing model IDs are expected in model comparisons and do "
            "not block eligibility; they are disclosed above.",
            "- This comparison supports claims about the tested configuration "
            "only; it implies no universal rank or daily-driver reliability.",
            "- Transcript-bearing results remain fail-closed at public "
            "export; this report is private review evidence.",
            "",
        ]
    )
    return "\n".join(lines)
