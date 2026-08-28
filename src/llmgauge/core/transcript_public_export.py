"""Content-default-deny public derivative of transcript comparisons.

Implements the accepted
``docs/TRANSCRIPT_COMPARISON_PUBLIC_EXPORT_CONTRACT.md`` V1 slice: an
allowlist projection of exactly two transcript-bearing results into a closed
``llmgauge.public_transcript_comparison.v0`` directory containing only
``transcript-comparison.json`` and ``report.md``. No transcript content,
private identifiers, or full hashes are admitted; single-run public export
remains fail-closed for transcript-bearing results.
"""

from __future__ import annotations

import re
import shutil
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from llmgauge.core.agent_harness import require_native_result
from llmgauge.core.artifacts import write_json
from llmgauge.core.multi_turn import (
    ModelAttemptEvent,
    StateEvent,
    TaskEvent,
    Transcript,
    validate_transcript_artifacts,
    validate_transcript_structure,
)
from llmgauge.core.public_export import (
    _ABSOLUTE_PATH_RE,
    _check_output_destination,
    _create_staging_dir,
    _finalize_staged_export,
    _FULL_HASH_SEGMENT_RE,
    _sanitize_text,
    _utc_timestamp,
)
from llmgauge.core.result_validation import load_result_json, validate_result_dir
from llmgauge.core.transcript_compare import (
    _IDENTITY_FIELDS,
    _REVIEW_HOOKS,
    classify_pair,
    load_transcript_for_compare,
    review_hooks,
    structural_facts,
    transcript_identity,
)

PUBLIC_TRANSCRIPT_COMPARISON_SCHEMA_VERSION = "llmgauge.public_transcript_comparison.v0"
PUBLIC_TRANSCRIPT_COMPARISON_FILENAME = "transcript-comparison.json"
PUBLIC_TRANSCRIPT_COMPARISON_REPORT_FILENAME = "report.md"
SOURCE_RESULT_SCHEMA_VERSION = "llmgauge.result.v0"
SOURCE_TRANSCRIPT_SCHEMA_VERSION = "llmgauge.transcript.v0"

_SLOT_LABELS = ("run-a", "run-b")
_FALLBACK_LABELS = ("Model A", "Model B")
_LABEL_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\+00:00|Z)$")
_SAFE_VALUE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 .,_\-]*$")

_REDACTION_POLICY = "content-default-deny-allowlist-projection"
_OMITTED_FIELD_CLASSES = (
    "conversation_id",
    "run_id",
    "event_attempt_turn_state_feedback_and_branch_ids",
    "selected_branch_id_and_final_response_event_id",
    "suite_and_task_identity_values",
    "initial_state_identity_and_sha256",
    "artifact_paths_and_full_sha256_values",
    "rendered_inputs_raw_outputs_stderr_and_visible_message_content",
    "feedback_content",
    "prompts",
    "runtime_and_generation_settings",
    "hardware_and_vram_metadata",
    "scores",
    "producer_version_and_result_provenance",
)
_CLAIM_BOUNDARY = (
    "This derivative supports claims about the tested configuration only; it "
    "implies no universal rank, no untested safety or performance, and no "
    "daily-driver reliability. Completion is not correctness; supplied inert "
    "feedback is not executed work. Structural comparison is not "
    "answer-quality validation, and sanitization is not proof that private "
    "data is absent. No session aggregate, winner, or quality verdict "
    "exists. Human review is required before publication."
)

_TOP_LEVEL_KEYS = {
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
_ELIGIBILITY_KEYS = {
    "eligible",
    "classification",
    "mismatched_identity_fields",
    "comparison_basis",
}
_CLASSIFICATION_KEYS = {
    "classification",
    "differing_facts",
    "completion_asymmetry",
}
_RUN_KEYS = {
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
}
_COMPLETION_KEYS = {"completion_state", "completion_actor", "terminal_reason"}
_TURNS_KEYS = {"logical_model_turns", "model_attempts", "retries", "recoveries"}
_ATTEMPT_KEYS = {"sequence", "relationship", "attempt_state", "exit_status"}
_FEEDBACK_KEYS = {
    "declared",
    "supplied",
    "consumed",
    "supplied_unconsumed",
    "unreached",
    "plan",
}
_FEEDBACK_PLAN_KEYS = {
    "ordinal",
    "after_model_turn",
    "lifecycle_state",
    "disposition_reason",
}
_STATES_KEYS = {"state_transitions", "links"}
_STATE_LINK_KEYS = {"sequence", "previous_sequence", "caused_by_sequence"}
_EVENT_KEYS = {"sequence", "kind", "role", "execution_status", "relationship"}
_CAPTURE_KEYS = {
    "truncated_artifacts",
    "partial_artifacts",
    "failed_artifacts",
    "redacted_artifacts",
}
_SUBSTITUTION_KEYS = {"slot", "reason"}
_REDACTION_KEYS = {
    "policy",
    "categories",
    "model_label_substitutions",
    "omitted_field_classes",
}
_NESTED_KEY_SETS: dict[str, set[str]] = {
    "eligibility": _ELIGIBILITY_KEYS,
    "classification": _CLASSIFICATION_KEYS,
    "runs": _RUN_KEYS,
    "completion": _COMPLETION_KEYS,
    "turns": _TURNS_KEYS,
    "attempt_states": _ATTEMPT_KEYS,
    "feedback": _FEEDBACK_KEYS,
    "plan": _FEEDBACK_PLAN_KEYS,
    "states": _STATES_KEYS,
    "links": _STATE_LINK_KEYS,
    "event_order": _EVENT_KEYS,
    "capture_health": _CAPTURE_KEYS,
    "review_hooks": set(_REVIEW_HOOKS),
    "model_label_substitutions": _SUBSTITUTION_KEYS,
    "redaction": _REDACTION_KEYS,
}

_FACT_NAMES = {
    "completion_state",
    "completion_actor",
    "terminal_reason",
    "selected_branch_id",
    "final_response_event_id",
    "logical_model_turns",
    "model_attempts",
    "retries",
    "recoveries",
    "attempt_outcomes",
    "declared_feedback_items",
    "supplied_feedback_items",
    "consumed_feedback_items",
    "supplied_unconsumed_feedback_items",
    "unreached_feedback_items",
    "feedback_dispositions",
    "state_transitions",
    "truncated_artifacts",
    "partial_artifacts",
    "failed_artifacts",
    "redacted_artifacts",
}
_VOCABULARY = {
    "identical structure",
    "structurally comparable",
    "structurally incomparable",
    # CompletionState / CompletionActor / TerminalReason
    "completed",
    "partial",
    "abandoned",
    "evaluator",
    "model",
    "operator",
    "protocol",
    "runtime",
    "turn_limit",
    "timeout",
    "runtime_failure",
    "malformed_response",
    "operator_stop",
    "interrupted",
    # Event roles and execution statuses
    "user",
    "assistant",
    "not_applicable",
    "not_executed",
    "failed",
    "malformed",
    # Attempt relationships and states
    "initial",
    "continuation",
    "retry",
    "recovery",
    # Feedback lifecycle and dispositions
    "unreached",
    "supplied_unconsumed",
    "consumed",
    "scheduling_point_not_reached",
    "no_admitted_follow_up_turn",
    "conversation_terminated_before_consumption",
    "consumed_by_model_turn",
    # Review hooks
    "unreviewed",
    "incomplete",
    "unscoreable",
    # Substitution reasons
    "fallback_positional_label",
    "sanitized_model_label",
    # Sanitizer categories
    "credential_bearing_url",
    "secret_like_value",
    "secret_like_metadata",
    "absolute_path",
    "home_directory_path",
    "local_hostname",
    "local_username",
    "full_local_sha256",
    "filename_full_sha256",
    "prompt_duplication",
}
_CLOSED_LITERALS = {
    PUBLIC_TRANSCRIPT_COMPARISON_SCHEMA_VERSION,
    SOURCE_RESULT_SCHEMA_VERSION,
    SOURCE_TRANSCRIPT_SCHEMA_VERSION,
    "llmgauge",
    "llmgauge.sequential_supplied_feedback",
    "0.1.0",
    "run-a",
    "run-b",
    "Model A",
    "Model B",
    "REDACTED_SECRET",
    "REDACTED_HOSTNAME",
    "REDACTED_USERNAME",
    "REDACTED_HOME_PATH",
    "REDACTED_ABSOLUTE_PATH",
    "REDACTED_FULL_HASH",
    _REDACTION_POLICY,
    _CLAIM_BOUNDARY,
}


class TranscriptPublicExportError(ValueError):
    """Raised when a public transcript comparison cannot be produced."""


def _allowed_public_string(value: str, path: str) -> bool:
    if path.endswith(".model_label"):
        if value in _FALLBACK_LABELS:
            return True
        # Already passed through the shared sanitizer and constrained to the
        # transcript ID character class at projection time; reject raw full
        # hashes as defense-in-depth even though they match the ID class.
        return bool(_LABEL_ID_RE.fullmatch(value)) and not _FULL_HASH_SEGMENT_RE.search(
            value
        )
    if path == "$.created_at_utc":
        return bool(_TIMESTAMP_RE.fullmatch(value))
    if value in _CLOSED_LITERALS:
        return True
    if value in _IDENTITY_FIELDS or value in _REVIEW_HOOKS:
        return True
    if value in _OMITTED_FIELD_CLASSES or value in _FACT_NAMES:
        return True
    if value in _VOCABULARY:
        return True
    return bool(_SAFE_VALUE_RE.fullmatch(value)) and not (
        _ABSOLUTE_PATH_RE.search(value) or _FULL_HASH_SEGMENT_RE.search(value)
    )


def _model_label(
    slot: int,
    result: dict[str, Any],
    categories: set[str],
    substitutions: list[dict[str, str]],
) -> str:
    model = result.get("model")
    raw = str(model.get("model_id") or "") if isinstance(model, dict) else ""
    label = _sanitize_text(raw, categories)
    label, hash_count = _FULL_HASH_SEGMENT_RE.subn("REDACTED_FULL_HASH", label)
    if hash_count:
        categories.add("full_local_sha256")
    if not label or not _LABEL_ID_RE.fullmatch(label):
        substitutions.append(
            {"slot": _SLOT_LABELS[slot], "reason": "fallback_positional_label"}
        )
        return _FALLBACK_LABELS[slot]
    if label != raw:
        substitutions.append(
            {"slot": _SLOT_LABELS[slot], "reason": "sanitized_model_label"}
        )
    return label


def _project_run(
    slot: int,
    result: dict[str, Any],
    transcript: Transcript,
    facts: dict[str, Any],
    categories: set[str],
    substitutions: list[dict[str, str]],
) -> dict[str, Any]:
    attempts = [
        event for event in transcript.events if isinstance(event, ModelAttemptEvent)
    ]
    state_events = [
        event for event in transcript.events if isinstance(event, StateEvent)
    ]
    sequence_by_event_id = {
        event.event_id: event.sequence for event in transcript.events
    }
    sequence_by_state_id = {event.state_id: event.sequence for event in state_events}
    initial_state_sequence = next(
        (
            event.sequence
            for event in transcript.events
            if isinstance(event, TaskEvent)
            and event.initial_state_id == transcript.initial_state_id
        ),
        None,
    )
    return {
        "slot": _SLOT_LABELS[slot],
        "model_label": _model_label(slot, result, categories, substitutions),
        "completion": {
            "completion_state": transcript.completion_state,
            "completion_actor": transcript.completion_actor,
            "terminal_reason": transcript.terminal_reason,
        },
        "turns": {
            "logical_model_turns": facts["logical_model_turns"],
            "model_attempts": facts["model_attempts"],
            "retries": facts["retries"],
            "recoveries": facts["recoveries"],
        },
        "attempt_states": [
            {
                "sequence": event.sequence,
                "relationship": event.relationship,
                "attempt_state": event.attempt_state,
                "exit_status": event.exit_status,
            }
            for event in attempts
        ],
        "feedback": {
            "declared": facts["declared_feedback_items"],
            "supplied": facts["supplied_feedback_items"],
            "consumed": facts["consumed_feedback_items"],
            "supplied_unconsumed": facts["supplied_unconsumed_feedback_items"],
            "unreached": facts["unreached_feedback_items"],
            "plan": [
                {
                    "ordinal": index,
                    "after_model_turn": planned.after_model_turn,
                    "lifecycle_state": planned.lifecycle_state,
                    "disposition_reason": planned.disposition_reason,
                }
                for index, planned in enumerate(transcript.feedback_plan, start=1)
            ],
        },
        "states": {
            "state_transitions": facts["state_transitions"],
            "links": [
                {
                    "sequence": event.sequence,
                    "previous_sequence": (
                        sequence_by_state_id.get(event.previous_state_id)
                        if event.previous_state_id is not None
                        else initial_state_sequence
                    ),
                    "caused_by_sequence": sequence_by_event_id.get(
                        event.caused_by_event_id
                    ),
                }
                for event in state_events
            ],
        },
        "event_order": [
            {
                "sequence": event.sequence,
                "kind": event.kind,
                "role": event.role,
                "execution_status": event.execution_status,
                **(
                    {"relationship": event.relationship}
                    if isinstance(event, ModelAttemptEvent)
                    else {}
                ),
            }
            for event in transcript.events
        ],
        "capture_health": {
            "truncated_artifacts": facts["truncated_artifacts"],
            "partial_artifacts": facts["partial_artifacts"],
            "failed_artifacts": facts["failed_artifacts"],
            "redacted_artifacts": facts["redacted_artifacts"],
        },
        "review_hooks": review_hooks(transcript),
    }


def build_public_transcript_comparison(
    results: Sequence[dict[str, Any]],
    transcripts: Sequence[Transcript],
) -> dict[str, Any]:
    """Project two validated transcripts into the closed public derivative."""
    if len(results) != 2 or len(transcripts) != 2:
        raise TranscriptPublicExportError(
            "Public transcript comparison admits exactly two results"
        )
    categories: set[str] = set()
    substitutions: list[dict[str, str]] = []
    identities = [transcript_identity(transcript) for transcript in transcripts]
    facts = [structural_facts(transcript) for transcript in transcripts]
    verdict = classify_pair(identities, facts)
    return {
        "schema_version": PUBLIC_TRANSCRIPT_COMPARISON_SCHEMA_VERSION,
        "generated_by": "llmgauge",
        "created_at_utc": _utc_timestamp(),
        "source_artifact_types": [
            SOURCE_RESULT_SCHEMA_VERSION,
            SOURCE_RESULT_SCHEMA_VERSION,
        ],
        "transcript_schema_versions": [
            SOURCE_TRANSCRIPT_SCHEMA_VERSION,
            SOURCE_TRANSCRIPT_SCHEMA_VERSION,
        ],
        "eligibility": {
            "eligible": verdict["eligible"],
            "classification": verdict["classification"],
            "mismatched_identity_fields": verdict["mismatched_identity_fields"],
            "comparison_basis": list(_IDENTITY_FIELDS),
        },
        "classification": {
            "classification": verdict["classification"],
            "differing_facts": verdict["differing_facts"],
            "completion_asymmetry": verdict["completion_asymmetry"] is not None,
        },
        "runs": [
            _project_run(slot, result, transcript, fact, categories, substitutions)
            for slot, (result, transcript, fact) in enumerate(
                zip(results, transcripts, facts)
            )
        ],
        "redaction": {
            "policy": _REDACTION_POLICY,
            "categories": sorted(categories),
            "model_label_substitutions": substitutions,
            "omitted_field_classes": list(_OMITTED_FIELD_CLASSES),
        },
        "claim_boundary": _CLAIM_BOUNDARY,
        "human_review_required_before_publication": True,
    }


def _validate_node(node: Any, allowed: set[str], path: str) -> None:
    if isinstance(node, dict):
        unexpected = sorted(set(node) - allowed)
        if unexpected:
            raise TranscriptPublicExportError(
                f"Public projection closed-world violation at {path}: "
                f"unexpected keys {unexpected}"
            )
        for key, child in node.items():
            _validate_node(child, _NESTED_KEY_SETS.get(key, set()), f"{path}.{key}")
        return
    if isinstance(node, list):
        for index, item in enumerate(node):
            _validate_node(item, allowed, f"{path}[{index}]")
        return
    if isinstance(node, str):
        if not _allowed_public_string(node, path):
            raise TranscriptPublicExportError(
                f"Public projection closed-world violation at {path}: "
                f"string {node!r} is not an allowed public value"
            )
        return
    if isinstance(node, bool) or isinstance(node, int) or node is None:
        return
    raise TranscriptPublicExportError(
        f"Public projection closed-world violation at {path}: "
        f"unsupported value type {type(node).__name__}"
    )


def validate_public_projection(projection: dict[str, Any]) -> None:
    """Fail closed unless the projection matches the closed public schema."""
    _validate_node(projection, _TOP_LEVEL_KEYS, "$")


def load_public_transcript_pair(
    result_dirs: Sequence[Path],
) -> tuple[list[dict[str, Any]], list[Transcript]]:
    """Admit exactly two validated transcript-bearing native results."""
    if len(result_dirs) != 2:
        raise TranscriptPublicExportError(
            "Public transcript comparison admits exactly two result directories in V1"
        )
    results: list[dict[str, Any]] = []
    transcripts: list[Transcript] = []
    for result_dir in result_dirs:
        result_dir = Path(result_dir)
        if not result_dir.is_dir():
            raise TranscriptPublicExportError(f"Missing result directory: {result_dir}")
        validation_errors = validate_result_dir(result_dir)
        if validation_errors:
            raise TranscriptPublicExportError(
                "Source result validation failed: " + "; ".join(validation_errors[:5])
            )
        result = load_result_json(result_dir)
        try:
            require_native_result(result, consumer="Public transcript export")
        except ValueError as exc:
            raise TranscriptPublicExportError(str(exc)) from exc
        if not isinstance(result.get("transcript"), dict):
            raise TranscriptPublicExportError(
                "Transcript comparison requires transcript-bearing results"
            )
        result["_result_dir"] = str(result_dir)
        transcript = load_transcript_for_compare(result)
        structure_errors = validate_transcript_structure(transcript)
        if structure_errors:
            raise TranscriptPublicExportError(
                f"Transcript structure validation failed for {result_dir}: "
                + "; ".join(structure_errors[:5])
            )
        artifact_errors = validate_transcript_artifacts(result_dir, transcript)
        if artifact_errors:
            raise TranscriptPublicExportError(
                f"Transcript evidence validation failed for {result_dir}: "
                + "; ".join(artifact_errors[:5])
            )
        results.append(result)
        transcripts.append(transcript)
    return results, transcripts


def render_public_transcript_comparison_markdown(
    projection: dict[str, Any],
) -> str:
    """Render the public report from the projected JSON only."""
    eligibility = projection["eligibility"]
    classification = projection["classification"]
    lines: list[str] = [
        "# Public Transcript Comparison",
        "",
        "> **Human review required before publication.** Sanitization is not",
        "> answer-quality validation and is not proof that private data is",
        "> absent. This derivative discloses bounded structural facts only.",
        "",
        f"- Schema: `{projection['schema_version']}`",
        f"- Generated by: {projection['generated_by']}",
        f"- Source artifacts: {', '.join(projection['source_artifact_types'])}",
        f"- Transcript schemas: {', '.join(projection['transcript_schema_versions'])}",
        "",
        "## Eligibility",
        "",
        f"- Eligible for like-for-like comparison: "
        f"{'yes' if eligibility['eligible'] else 'no'}",
        f"- Classification: {eligibility['classification']}",
    ]
    if eligibility["mismatched_identity_fields"]:
        lines.append(
            "- Mismatched identity fields: "
            + ", ".join(
                f"`{field}`" for field in eligibility["mismatched_identity_fields"]
            )
        )
    lines += [
        "- Comparison basis (all fields must match): "
        + ", ".join(f"`{field}`" for field in eligibility["comparison_basis"]),
        "",
        "## Structural classification",
        "",
        f"- Classification: {classification['classification']}",
    ]
    if classification["differing_facts"]:
        lines.append(
            "- Differing structural facts: "
            + ", ".join(f"`{field}`" for field in classification["differing_facts"])
        )
    else:
        lines.append("- Differing structural facts: none")
    lines.append(
        "- Completion asymmetry: "
        + (
            "the pair terminates in different completion states or terminal "
            "reasons; this is disclosed without ranking either side."
            if classification["completion_asymmetry"]
            else "none."
        )
    )
    for run in projection["runs"]:
        lines += [
            "",
            f"## Run {run['slot']} — {run['model_label']}",
            "",
            f"- Completion: `{run['completion']['completion_state']}` / "
            f"actor `{run['completion']['completion_actor']}` / "
            f"reason `{run['completion']['terminal_reason']}`",
            f"- Logical model turns: {run['turns']['logical_model_turns']}",
            f"- Model attempts: {run['turns']['model_attempts']} "
            f"(retries {run['turns']['retries']}, "
            f"recoveries {run['turns']['recoveries']})",
            f"- Feedback: declared {run['feedback']['declared']}, "
            f"supplied {run['feedback']['supplied']}, "
            f"consumed {run['feedback']['consumed']}, "
            f"supplied unconsumed {run['feedback']['supplied_unconsumed']}, "
            f"unreached {run['feedback']['unreached']}",
            f"- State transitions: {run['states']['state_transitions']}",
            f"- Capture health: truncated {run['capture_health']['truncated_artifacts']}, "
            f"partial {run['capture_health']['partial_artifacts']}, "
            f"failed {run['capture_health']['failed_artifacts']}, "
            f"redacted {run['capture_health']['redacted_artifacts']}",
            "",
            "### Event order",
            "",
            "| Sequence | Kind | Role | Execution status | Relationship |",
            "| --- | --- | --- | --- | --- |",
        ]
        for event in run["event_order"]:
            lines.append(
                f"| {event['sequence']} | {event['kind']} | {event['role']} | "
                f"{event['execution_status']} | {event.get('relationship', '')} |"
            )
        lines += [
            "",
            "### Review hooks (as recorded; not answer-quality validation)",
            "",
        ]
        for hook in _REVIEW_HOOKS:
            lines.append(f"- {hook}: `{run['review_hooks'][hook]}`")
    redaction = projection["redaction"]
    lines += [
        "",
        "## Redaction summary",
        "",
        f"- Policy: `{redaction['policy']}`",
        "- Sanitizer categories touched: "
        + (", ".join(f"`{c}`" for c in redaction["categories"]) or "none"),
    ]
    for record in redaction["model_label_substitutions"]:
        lines.append(f"- Model label for `{record['slot']}`: {record['reason']}")
    lines += [
        "- Omitted field classes: "
        + ", ".join(f"`{name}`" for name in redaction["omitted_field_classes"]),
        "",
        "## Claim boundaries",
        "",
        projection["claim_boundary"],
        "",
        "No session aggregate, winner, or quality verdict is computed.",
        "Completion is not correctness; supplied inert feedback is not executed",
        "work. Structural comparison is not answer-quality validation.",
        "",
    ]
    return "\n".join(lines)


def export_public_transcript_comparison(
    result_dirs: Sequence[Path],
    output_dir: Path,
) -> dict[str, Any]:
    """Write the closed public derivative for exactly two transcript results."""
    dirs = [Path(directory).expanduser() for directory in result_dirs]
    results, transcripts = load_public_transcript_pair(dirs)
    projection = build_public_transcript_comparison(results, transcripts)
    validate_public_projection(projection)

    resolved_output = output_dir.expanduser().resolve()
    existing_empty_destination = False
    for source_dir in dirs:
        try:
            empty = _check_output_destination(source_dir.resolve(), resolved_output)
        except ValueError as exc:
            raise TranscriptPublicExportError(str(exc)) from exc
        existing_empty_destination = existing_empty_destination or empty

    staging_dir = _create_staging_dir(resolved_output)
    try:
        write_json(
            staging_dir / PUBLIC_TRANSCRIPT_COMPARISON_FILENAME,
            projection,
        )
        (staging_dir / PUBLIC_TRANSCRIPT_COMPARISON_REPORT_FILENAME).write_text(
            render_public_transcript_comparison_markdown(projection),
            encoding="utf-8",
        )
        _finalize_staged_export(
            staging_dir,
            resolved_output,
            existing_empty_destination=existing_empty_destination,
        )
    except Exception:
        shutil.rmtree(staging_dir, ignore_errors=True)
        raise
    return projection
