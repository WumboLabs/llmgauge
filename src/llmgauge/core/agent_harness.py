from __future__ import annotations

import ctypes
import errno
import hashlib
import json
import os
import re
import shutil
import stat
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any, Literal
from urllib.parse import parse_qsl, urlsplit

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from llmgauge import __version__
from llmgauge.core.artifacts import write_json

EVIDENCE_SCHEMA_VERSION = "llmgauge.agent_harness_evidence.v0"
CONTRACT_VERSION = "0.1.0"
EVIDENCE_CLASS = "external_agent_environment"
SOURCE_TYPE = "wumbolabs_omp_session"
SOURCE_FORMAT = "wumbolabs.omp.session_jsonl"
SOURCE_FORMAT_VERSION = 3
SOURCE_PRODUCER = "wumbolabs.omp"
IMPORTER_ID = "llmgauge.agent_harness_importer"
EVIDENCE_RELATIVE_PATH = "agent-harness/evidence.json"
SESSION_RELATIVE_PATH = "agent-harness/source/session.jsonl"
OBJECTS_RELATIVE_DIR = "agent-harness/source/objects/sha256"

MAX_SESSION_BYTES = 64 * 1024 * 1024
MAX_JSONL_LINE_BYTES = 8 * 1024 * 1024
MAX_EVENT_COUNT = 100_000
MAX_REFERENCED_OBJECTS = 256
MAX_OBJECT_BYTES = 64 * 1024 * 1024
MAX_TOTAL_SOURCE_BYTES = 256 * 1024 * 1024
MAX_EVIDENCE_JSON_BYTES = 16 * 1024 * 1024
MAX_JSON_NESTING = 64
MAX_ARTIFACT_DIRECTORY_ENTRIES = 4096
_COPY_CHUNK_BYTES = 1024 * 1024
_TITLE_SLOT_BYTES = 256
_PERSISTENCE_TRUNCATION_MARKER = "[Session persistence truncated large content]"

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_DIGEST_ID_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_BLOB_REF_RE = re.compile(r"^blob:sha256:([0-9a-f]{64})$")
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,191}$")
_ARTIFACT_ID_RE = re.compile(r"^[0-9]+$")

Availability = Literal[
    "available", "absent", "unknown", "unavailable", "redacted", "unsupported"
]
SourceCompleteness = Literal["complete", "partial"]
SourceSessionOutcome = Literal[
    "completed",
    "failed",
    "partial",
    "interrupted",
    "timed_out",
    "denied",
    "operator_stopped",
    "abandoned",
    "unknown",
]
LifecycleState = Literal[
    "requested",
    "started",
    "completed",
    "failed",
    "timed_out",
    "denied",
    "interrupted",
    "cancelled",
    "unavailable",
    "unknown",
]


class AgentHarnessImportError(ValueError):
    """Bounded failure from source admission or atomic import."""

    def __init__(
        self,
        outcome: Literal["unsupported_source", "malformed_source", "failed"],
        message: str,
    ) -> None:
        super().__init__(message)
        self.outcome = outcome


class _ClosedModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class SourceFact(_ClosedModel):
    availability: Availability
    value: str | int | bool | None = None
    source_entry_id: str | None = None

    @model_validator(mode="after")
    def validate_availability(self) -> SourceFact:
        if self.source_entry_id is not None:
            _require_id(self.source_entry_id, "source fact entry ID")
        if self.availability == "available":
            if self.value is None or not self.source_entry_id:
                raise ValueError("available fact requires value and source_entry_id")
        elif self.value is not None:
            raise ValueError("non-available fact cannot carry a value")
        return self


class ProducerIdentity(_ClosedModel):
    producer_id: Literal["wumbolabs.omp"]
    version: SourceFact


class ImporterIdentity(_ClosedModel):
    importer_id: Literal["llmgauge.agent_harness_importer"]
    version: str = Field(min_length=1, max_length=64)


class SourceIdentity(_ClosedModel):
    source_type: Literal["wumbolabs_omp_session"]
    source_format: Literal["wumbolabs.omp.session_jsonl"]
    source_format_version: Literal[3]
    producer: ProducerIdentity
    session_id: str
    started_at: SourceFact
    ended_at: SourceFact
    workspace_path: SourceFact
    selected_leaf: SourceFact

    @model_validator(mode="after")
    def validate_identity(self) -> SourceIdentity:
        _require_id(self.session_id, "source session ID")
        return self


class SourceMember(_ClosedModel):
    member_id: str
    role: Literal["session_log", "source_object"]
    path: str
    sha256: str
    byte_size: int = Field(ge=0, le=MAX_TOTAL_SOURCE_BYTES)
    availability: Literal["available"]
    source_relationship: Literal["canonical_session", "referenced_object"]
    observed_source_path: str | None = Field(default=None, max_length=4096)

    @model_validator(mode="after")
    def validate_member(self) -> SourceMember:
        _require_id(self.member_id, "source member ID")
        _require_sha256(self.sha256, "source member sha256")
        _require_contained_path(self.path, "source member path")
        if self.role == "session_log" and self.byte_size > MAX_SESSION_BYTES:
            raise ValueError("session_log exceeds the session byte limit")
        if self.role == "source_object" and self.byte_size > MAX_OBJECT_BYTES:
            raise ValueError("source_object exceeds the object byte limit")
        if self.role == "session_log":
            if self.member_id != "session":
                raise ValueError("session_log member_id must be session")
            if self.path != SESSION_RELATIVE_PATH:
                raise ValueError("session_log must use the fixed session path")
            if self.source_relationship != "canonical_session":
                raise ValueError("session_log must be the canonical session")
        else:
            if self.member_id != f"object:{self.sha256}":
                raise ValueError("source_object member_id must match its digest")
            expected = f"{OBJECTS_RELATIVE_DIR}/{self.sha256}"
            if self.path != expected:
                raise ValueError("source_object path must be content addressed")
            if self.source_relationship != "referenced_object":
                raise ValueError("source_object must be referenced evidence")
        return self


class SourceReference(_ClosedModel):
    reference_id: str
    kind: Literal["blob", "artifact"]
    source_entry_id: str
    source_pointer: str = Field(min_length=1, max_length=4096)
    source_object_id: str = Field(min_length=1, max_length=192)
    declared_sha256: str | None = None
    member_id: str
    availability: Literal["available"]
    source_relationship: Literal["blob_reference", "artifact_reference"]

    @model_validator(mode="after")
    def validate_reference(self) -> SourceReference:
        _require_id(self.reference_id, "source reference ID")
        _require_id(self.source_entry_id, "source entry ID")
        _require_id(self.member_id, "source member ID")
        if not self.source_pointer.startswith("/"):
            raise ValueError("source pointer must be an absolute JSON pointer")
        if self.declared_sha256 is not None:
            _require_sha256(self.declared_sha256, "declared source sha256")
        if self.kind == "blob" and self.declared_sha256 is None:
            raise ValueError("blob reference requires declared_sha256")
        if self.kind == "blob":
            if self.source_object_id != self.declared_sha256:
                raise ValueError("blob source identity must match its declared digest")
        elif not _ARTIFACT_ID_RE.fullmatch(self.source_object_id):
            raise ValueError("artifact source object ID is malformed")
        if self.source_relationship != f"{self.kind}_reference":
            raise ValueError("source relationship does not match reference kind")
        expected_reference_id = "ref:" + _sha256_bytes(
            _canonical_json_bytes(
                {
                    "kind": self.kind,
                    "source_entry_id": self.source_entry_id,
                    "source_pointer": self.source_pointer,
                    "source_object_id": self.source_object_id,
                    "declared_sha256": self.declared_sha256,
                }
            )
        )
        if self.reference_id != expected_reference_id:
            raise ValueError("source reference ID does not match its source facts")
        return self


class TrajectoryEvent(_ClosedModel):
    event_id: str
    sequence: int = Field(ge=0, le=MAX_EVENT_COUNT)
    subsequence: int = Field(ge=0, le=10_000)
    kind: Literal[
        "task_input",
        "user_input",
        "model_message",
        "harness_message",
        "tool_request",
        "command_request",
        "execution_start",
        "tool_output",
        "harness_event",
        "source_terminal",
    ]
    source_entry_id: str
    source_entry_type: str
    source_entry_sha256: str
    parent_id: str | None = None
    role: str | None = None
    visibility: Literal[
        "user_visible",
        "model_visible",
        "user_and_model_visible",
        "harness_internal",
        "redacted",
        "unknown",
    ]
    content_sha256: str | None = None
    tool_call_id: str | None = None
    tool_name: str | None = None

    @model_validator(mode="after")
    def validate_event(self) -> TrajectoryEvent:
        _require_id(self.event_id, "trajectory event ID")
        _require_id(self.source_entry_id, "source entry ID")
        _require_sha256(self.source_entry_sha256, "source entry sha256")
        if self.content_sha256 is not None:
            _require_sha256(self.content_sha256, "event content sha256")
        if self.tool_call_id is not None:
            _require_id(self.tool_call_id, "tool call ID")
        return self


class ToolLifecycle(_ClosedModel):
    lifecycle_id: str
    tool_call_id: str
    tool_name: str
    lifecycle_state: LifecycleState
    source_entry_ids: list[str] = Field(min_length=1, max_length=MAX_EVENT_COUNT)
    request_event_id: str
    started_event_id: str | None = None
    terminal_event_id: str | None = None
    arguments: dict[str, Any]
    arguments_sha256: str
    output_availability: Availability
    output_complete: bool
    output_sha256: str | None = None
    full_output_member_id: str | None = None
    exit_status: int | None = None
    signal: str | None = None
    timed_out: bool = False
    denied: bool = False
    interrupted: bool = False
    cancelled: bool = False
    is_error: bool | None = None

    @model_validator(mode="after")
    def validate_lifecycle(self) -> ToolLifecycle:
        _require_id(self.lifecycle_id, "tool lifecycle ID")
        _require_id(self.tool_call_id, "tool call ID")
        _require_id(self.request_event_id, "tool request event ID")
        for source_entry_id in self.source_entry_ids:
            _require_id(source_entry_id, "tool lifecycle source entry ID")
        _require_unique(self.source_entry_ids, "tool lifecycle source entry IDs")
        if self.started_event_id is not None:
            _require_id(self.started_event_id, "tool started event ID")
        if self.terminal_event_id is not None:
            _require_id(self.terminal_event_id, "tool terminal event ID")
        if self.full_output_member_id is not None:
            _require_id(self.full_output_member_id, "full output member ID")
        _require_sha256(self.arguments_sha256, "tool arguments sha256")
        if self.arguments_sha256 != _sha256_bytes(
            _canonical_json_bytes(self.arguments)
        ):
            raise ValueError("arguments_sha256 must match canonical arguments")
        if self.output_sha256 is not None:
            _require_sha256(self.output_sha256, "tool output sha256")
        if self.lifecycle_state in {"requested", "started"}:
            if self.terminal_event_id is not None:
                raise ValueError("non-terminal lifecycle cannot have terminal_event_id")
        elif self.terminal_event_id is None:
            raise ValueError("terminal lifecycle requires terminal_event_id")
        if self.lifecycle_state == "requested" and self.started_event_id is not None:
            raise ValueError("requested lifecycle cannot have started_event_id")
        if self.lifecycle_state == "started" and self.started_event_id is None:
            raise ValueError("started lifecycle requires started_event_id")
        if self.lifecycle_state == "denied" and self.started_event_id is not None:
            raise ValueError("denied lifecycle cannot have started_event_id")
        if self.timed_out != (self.lifecycle_state == "timed_out"):
            raise ValueError("timed_out flag must match lifecycle_state")
        if self.denied != (self.lifecycle_state == "denied"):
            raise ValueError("denied flag must match lifecycle_state")
        if self.cancelled != (self.lifecycle_state == "cancelled"):
            raise ValueError("cancelled flag must match lifecycle_state")
        if self.interrupted != (self.lifecycle_state == "interrupted"):
            raise ValueError("interrupted flag must match lifecycle_state")
        if self.output_complete and self.output_availability != "available":
            raise ValueError("complete output must be available")
        if self.output_availability != "available" and (
            self.output_sha256 is not None or self.full_output_member_id is not None
        ):
            raise ValueError("unavailable output cannot carry output evidence")
        if self.full_output_member_id is not None and self.output_sha256 is None:
            raise ValueError("full output member requires output_sha256")
        if self.lifecycle_state == "completed" and (
            self.is_error is True
            or self.signal is not None
            or (self.exit_status is not None and self.exit_status != 0)
        ):
            raise ValueError("completed lifecycle has contradictory terminal facts")
        return self


class ModelObservation(_ClosedModel):
    observation_id: str
    source_entry_id: str
    provider: SourceFact
    model: SourceFact
    role: SourceFact
    resolved_model_is_fallback: SourceFact | None = Field(
        default=None, exclude_if=lambda value: value is None
    )

    @model_validator(mode="after")
    def validate_observation(self) -> ModelObservation:
        _require_id(self.observation_id, "model observation ID")
        _require_id(self.source_entry_id, "source entry ID")
        return self


class RepositoryObservation(_ClosedModel):
    observation_id: str
    source_entry_ids: list[str] = Field(min_length=1, max_length=MAX_EVENT_COUNT)
    observed_path: SourceFact
    remote: SourceFact
    branch: SourceFact
    initial_head: SourceFact
    final_head: SourceFact
    dirty: SourceFact
    staged: SourceFact
    unstaged: SourceFact
    untracked: SourceFact
    source_diff_member_id: SourceFact
    patch_member_id: SourceFact
    snapshot_identity: SourceFact
    manifest_identity: SourceFact

    @model_validator(mode="after")
    def validate_observation(self) -> RepositoryObservation:
        _require_id(self.observation_id, "repository observation ID")
        for source_entry_id in self.source_entry_ids:
            _require_id(source_entry_id, "source entry ID")
        _require_unique(self.source_entry_ids, "repository source entry IDs")
        return self


class SourceTerminal(_ClosedModel):
    outcome: SourceSessionOutcome
    availability: Availability
    source_entry_id: str | None = None
    kind: str | None = None
    reason: str | None = None

    @model_validator(mode="after")
    def validate_terminal(self) -> SourceTerminal:
        if self.availability == "available":
            if not self.source_entry_id or self.kind is None or self.reason is None:
                raise ValueError("available terminal requires source evidence")
            _require_id(self.source_entry_id, "terminal source entry ID")
            expected_outcome: SourceSessionOutcome
            if self.kind == "fatal":
                expected_outcome = "failed"
            elif self.kind in {"signal", "process_exit"}:
                expected_outcome = "interrupted"
            elif self.kind == "normal":
                expected_outcome = "unknown"
            else:
                raise ValueError("available terminal kind is unsupported")
            if self.outcome != expected_outcome:
                raise ValueError("terminal outcome disagrees with its kind")
        elif any(
            item is not None for item in (self.source_entry_id, self.kind, self.reason)
        ):
            raise ValueError("unavailable terminal cannot carry source evidence")
        if self.availability != "available" and self.outcome != "unknown":
            raise ValueError("unavailable terminal outcome must be unknown")
        return self


class AgentHarnessEvidence(_ClosedModel):
    schema_version: Literal["llmgauge.agent_harness_evidence.v0"]
    contract_version: Literal["0.1.0"]
    evidence_class: Literal["external_agent_environment"]
    evidence_id: str
    imported_session_id: str
    source_package_sha256: str
    source: SourceIdentity
    importer: ImporterIdentity
    source_completeness: SourceCompleteness
    source_session_outcome: SourceSessionOutcome
    import_outcome: Literal["completed"]
    validation_outcome: Literal["passed"]
    scoreability: Literal["not_assessed"]
    publication_readiness: Literal["not_assessed"]
    task_identity: SourceFact
    source_inventory: list[SourceMember] = Field(
        min_length=1, max_length=MAX_REFERENCED_OBJECTS + 1
    )
    source_references: list[SourceReference] = Field(max_length=MAX_REFERENCED_OBJECTS)
    trajectory: list[TrajectoryEvent] = Field(max_length=MAX_EVENT_COUNT)
    tool_lifecycles: list[ToolLifecycle] = Field(max_length=MAX_EVENT_COUNT)
    model_observations: list[ModelObservation] = Field(max_length=MAX_EVENT_COUNT)
    repository_observations: list[RepositoryObservation] = Field(
        max_length=MAX_EVENT_COUNT
    )
    terminal: SourceTerminal

    @model_validator(mode="after")
    def validate_evidence(self) -> AgentHarnessEvidence:
        _require_digest_id(self.evidence_id, "evidence_id")
        _require_digest_id(self.imported_session_id, "imported_session_id")
        _require_sha256(self.source_package_sha256, "source_package_sha256")
        member_ids = [item.member_id for item in self.source_inventory]
        member_paths = [item.path for item in self.source_inventory]
        _require_unique(member_ids, "source member IDs")
        _require_unique(member_paths, "source member paths")
        if sum(item.role == "session_log" for item in self.source_inventory) != 1:
            raise ValueError("source inventory requires exactly one session_log")
        if (
            sum(item.byte_size for item in self.source_inventory)
            > MAX_TOTAL_SOURCE_BYTES
        ):
            raise ValueError("source inventory exceeds the total source byte limit")
        member_by_id = {item.member_id: item for item in self.source_inventory}
        referenced_member_ids: set[str] = set()
        for source_reference in self.source_references:
            member = member_by_id.get(source_reference.member_id)
            if member is None or member.role != "source_object":
                raise ValueError("source reference must name a source_object member")
            referenced_member_ids.add(source_reference.member_id)
        source_object_ids = {
            item.member_id
            for item in self.source_inventory
            if item.role == "source_object"
        }
        if source_object_ids != referenced_member_ids:
            raise ValueError("every source_object member must have a source reference")
        _require_unique(
            [item.reference_id for item in self.source_references],
            "source reference IDs",
        )
        _require_unique(
            [item.event_id for item in self.trajectory], "trajectory event IDs"
        )
        if [(item.sequence, item.subsequence) for item in self.trajectory] != sorted(
            (item.sequence, item.subsequence) for item in self.trajectory
        ):
            raise ValueError("trajectory must use physical source order")
        event_by_id = {item.event_id: item for item in self.trajectory}
        source_entry_ids = {item.source_entry_id for item in self.trajectory}
        for source_reference in self.source_references:
            if source_reference.source_entry_id not in source_entry_ids:
                raise ValueError("source reference entry lacks trajectory evidence")
        for lifecycle in self.tool_lifecycles:
            request_event = event_by_id.get(lifecycle.request_event_id)
            if request_event is None or request_event.kind not in {
                "tool_request",
                "command_request",
            }:
                raise ValueError("tool lifecycle request event is invalid")
            if lifecycle.started_event_id is not None:
                started_event = event_by_id.get(lifecycle.started_event_id)
                if started_event is None or started_event.kind != "execution_start":
                    raise ValueError("tool lifecycle started event is invalid")
            if lifecycle.terminal_event_id is not None:
                terminal_event = event_by_id.get(lifecycle.terminal_event_id)
                if terminal_event is None or terminal_event.kind not in {
                    "tool_output",
                    "source_terminal",
                }:
                    raise ValueError("tool lifecycle terminal event is invalid")
            if not set(lifecycle.source_entry_ids) <= source_entry_ids:
                raise ValueError("tool lifecycle source entries are invalid")
        for observation in self.model_observations:
            if observation.source_entry_id not in source_entry_ids:
                raise ValueError("model observation entry lacks trajectory evidence")
        for observation in self.repository_observations:
            if not set(observation.source_entry_ids) <= source_entry_ids:
                raise ValueError("repository observation entries are invalid")
        if (
            self.terminal.source_entry_id is not None
            and self.terminal.source_entry_id not in source_entry_ids
        ):
            raise ValueError("terminal entry lacks trajectory evidence")
        _require_unique(
            [item.lifecycle_id for item in self.tool_lifecycles],
            "tool lifecycle IDs",
        )
        _require_unique(
            [item.tool_call_id for item in self.tool_lifecycles], "tool call IDs"
        )
        _require_unique(
            [item.observation_id for item in self.model_observations],
            "model observation IDs",
        )
        _require_unique(
            [item.observation_id for item in self.repository_observations],
            "repository observation IDs",
        )
        if self.source_session_outcome != self.terminal.outcome:
            raise ValueError("source_session_outcome must match terminal outcome")
        return self


class AgentHarnessEvidenceReference(_ClosedModel):
    schema_version: Literal["llmgauge.agent_harness_evidence.v0"]
    contract_version: Literal["0.1.0"]
    evidence_class: Literal["external_agent_environment"]
    evidence_id: str
    path: Literal["agent-harness/evidence.json"]
    sha256: str

    @model_validator(mode="after")
    def validate_reference(self) -> AgentHarnessEvidenceReference:
        _require_digest_id(self.evidence_id, "agent_harness_evidence.evidence_id")
        _require_sha256(self.sha256, "agent_harness_evidence.sha256")
        return self


@dataclass(frozen=True)
class ParsedRecord:
    data: dict[str, Any]
    source_entry_sha256: str
    physical_line: int
    sequence: int


@dataclass(frozen=True)
class ParsedSession:
    header: dict[str, Any]
    header_sha256: str
    entries: tuple[ParsedRecord, ...]
    byte_size: int


@dataclass(frozen=True)
class DiscoveredReference:
    kind: Literal["blob", "artifact"]
    source_entry_id: str
    source_pointer: str
    source_object_id: str
    declared_sha256: str | None

    @property
    def reference_id(self) -> str:
        projection = {
            "kind": self.kind,
            "source_entry_id": self.source_entry_id,
            "source_pointer": self.source_pointer,
            "source_object_id": self.source_object_id,
            "declared_sha256": self.declared_sha256,
        }
        return "ref:" + _sha256_bytes(_canonical_json_bytes(projection))


@dataclass(frozen=True)
class ResolvedObject:
    reference: DiscoveredReference
    source_path: Path
    sha256: str
    byte_size: int


@dataclass(frozen=True)
class ImportOperationResult:
    outcome: Literal["completed", "already_imported", "dry_run"]
    evidence_id: str
    source_package_sha256: str
    destination: Path


_HEADER_FIELDS = frozenset(
    {
        "type",
        "version",
        "id",
        "timestamp",
        "cwd",
        "title",
        "titleSource",
        "additionalDirectories",
        "previousSessionFiles",
        "parentSession",
        "providerPromptCacheKey",
    }
)
_ENTRY_FIELDS: dict[str, frozenset[str]] = {
    "message": frozenset({"message"}),
    "thinking_level_change": frozenset({"thinkingLevel", "configured"}),
    "model_change": frozenset({"model", "role", "resolvedModelIsFallback"}),
    "service_tier_change": frozenset({"serviceTier"}),
    "compaction": frozenset(
        {
            "summary",
            "shortSummary",
            "firstKeptEntryId",
            "tokensBefore",
            "details",
            "preserveData",
            "fromExtension",
        }
    ),
    "branch_summary": frozenset({"fromId", "summary", "details", "fromExtension"}),
    "reset_boundary": frozenset(),
    "custom": frozenset({"customType", "data"}),
    "custom_message": frozenset(
        {"customType", "content", "display", "details", "attribution"}
    ),
    "label": frozenset({"targetId", "label"}),
    "title_change": frozenset({"title", "source", "previousTitle", "trigger"}),
    "ttsr_injection": frozenset({"injectedRules"}),
    "credential_pin": frozenset({"provider", "accountHash", "scopeHash"}),
    "session_init": frozenset(
        {
            "systemPrompt",
            "task",
            "tools",
            "outputSchema",
            "outputSchemaMode",
            "restrictToolNames",
            "spawns",
            "readSummarize",
        }
    ),
    "mode_change": frozenset({"mode", "data"}),
}
_ENTRY_BASE_FIELDS = frozenset({"type", "id", "parentId", "timestamp"})
_PRIVATE_KEYS = frozenset(
    {
        "apikey",
        "password",
        "passwd",
        "accesstoken",
        "refreshtoken",
        "authorization",
        "proxyauthorization",
        "cookie",
        "setcookie",
        "credential",
        "credentials",
        "clientsecret",
        "secret",
        "token",
        "bearertoken",
        "providerpromptcachekey",
        "providerpayload",
        "rawproviderpayload",
        "providerinternal",
        "thinkingsignature",
        "thoughtsignature",
        "textsignature",
        "privatekey",
    }
)
_PRIVATE_KEY_SUFFIXES = (
    "accesstoken",
    "apikey",
    "clientsecret",
    "credential",
    "credentials",
    "password",
    "privatekey",
    "secret",
    "token",
)
_ENVIRONMENT_KEYS = frozenset({"env", "environment", "environmentvariables"})
_PRIVATE_BLOCK_TYPES = frozenset(
    {"thinking", "reasoning", "private_reasoning", "redacted_thinking"}
)
_URL_SECRET_QUERY_KEYS = frozenset(
    {"api_key", "apikey", "token", "access_token", "password", "secret"}
)
_ALLOWED_MESSAGE_ROLES = frozenset(
    {"user", "assistant", "toolResult", "system", "custom"}
)


def _require_sha256(value: str, label: str) -> None:
    if not _SHA256_RE.fullmatch(value):
        raise ValueError(f"{label} must be 64 lowercase hex characters")


def _require_digest_id(value: str, label: str) -> None:
    if not _DIGEST_ID_RE.fullmatch(value):
        raise ValueError(f"{label} must be sha256:<64 lowercase hex>")


def _require_id(value: str, label: str) -> None:
    if not isinstance(value, str) or not _ID_RE.fullmatch(value):
        raise ValueError(f"{label} is invalid")


def _require_unique(values: list[str], label: str) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"{label} must be unique")


def _require_contained_path(value: str, label: str) -> None:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ValueError(f"{label} must be a non-empty relative POSIX path")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"{label} must remain contained")


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _json_object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result


def _validate_json_nesting(value: Any) -> None:
    stack: list[tuple[Any, int]] = [(value, 0)]
    while stack:
        item, depth = stack.pop()
        if depth > MAX_JSON_NESTING:
            raise AgentHarnessImportError(
                "malformed_source", "source JSON nesting exceeds limit"
            )
        if isinstance(item, Mapping):
            stack.extend((child, depth + 1) for child in item.values())
        elif isinstance(item, list):
            stack.extend((child, depth + 1) for child in item)


def _parse_json_object(raw: bytes) -> dict[str, Any]:
    try:
        text = raw.decode("utf-8")
        value = json.loads(
            text,
            object_pairs_hook=_json_object_pairs,
            parse_constant=lambda _value: (_ for _ in ()).throw(
                ValueError("non-finite JSON number")
            ),
        )
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        ValueError,
        RecursionError,
        OverflowError,
    ) as exc:
        raise AgentHarnessImportError(
            "malformed_source", "source contains malformed JSONL"
        ) from exc
    if not isinstance(value, dict):
        raise AgentHarnessImportError(
            "malformed_source", "each source JSONL record must be an object"
        )
    _validate_json_nesting(value)
    return value


def _regular_file_stat(path: Path, *, label: str) -> os.stat_result:
    try:
        value = path.lstat()
    except OSError as exc:
        raise AgentHarnessImportError("failed", f"{label} is unavailable") from exc
    if stat.S_ISLNK(value.st_mode) or not stat.S_ISREG(value.st_mode):
        raise AgentHarnessImportError("failed", f"{label} must be a regular file")
    return value


def _stat_identity(value: os.stat_result) -> tuple[int, int, int, int]:
    return (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns)


def _open_regular_file(
    path: Path, *, label: str
) -> tuple[int, os.stat_result, os.stat_result]:
    before = _regular_file_stat(path, label=label)
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise AgentHarnessImportError("failed", f"{label} is unreadable") from exc
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode) or _stat_identity(before) != _stat_identity(
            opened
        ):
            raise AgentHarnessImportError(
                "failed", f"{label} changed before it was opened"
            )
    except Exception:
        os.close(descriptor)
        raise
    return descriptor, before, opened


def _verify_open_file(
    path: Path,
    descriptor: int,
    *,
    before: os.stat_result,
    opened: os.stat_result,
    label: str,
) -> None:
    try:
        descriptor_after = os.fstat(descriptor)
    except OSError as exc:
        raise AgentHarnessImportError("failed", f"{label} became unreadable") from exc
    path_after = _regular_file_stat(path, label=label)
    identity = _stat_identity(before)
    if (
        _stat_identity(opened) != identity
        or _stat_identity(descriptor_after) != identity
        or _stat_identity(path_after) != identity
    ):
        raise AgentHarnessImportError("failed", f"{label} changed while reading")


def _read_bounded_regular_file(
    path: Path, *, limit: int, label: str
) -> tuple[bytes, str]:
    descriptor, before, opened = _open_regular_file(path, label=label)
    if before.st_size > limit:
        os.close(descriptor)
        raise AgentHarnessImportError("failed", f"{label} exceeds byte limit")
    payload = bytearray()
    digest = hashlib.sha256()
    try:
        with os.fdopen(descriptor, "rb") as handle:
            while chunk := handle.read(_COPY_CHUNK_BYTES):
                if len(payload) + len(chunk) > limit:
                    raise AgentHarnessImportError(
                        "failed", f"{label} exceeds byte limit"
                    )
                payload.extend(chunk)
                digest.update(chunk)
            if len(payload) != before.st_size:
                raise AgentHarnessImportError(
                    "failed", f"{label} changed while reading"
                )
            _verify_open_file(
                path,
                handle.fileno(),
                before=before,
                opened=opened,
                label=label,
            )
    except AgentHarnessImportError:
        raise
    except OSError as exc:
        raise AgentHarnessImportError("failed", f"{label} is unreadable") from exc
    return bytes(payload), digest.hexdigest()


def _scan_private_material(
    value: Any, *, key: str | None = None, depth: int = 0
) -> None:
    if depth > MAX_JSON_NESTING:
        raise AgentHarnessImportError(
            "malformed_source", "source JSON nesting exceeds limit"
        )
    normalized_key = re.sub(r"[^a-z0-9]", "", key.lower()) if key else None
    if normalized_key and (
        normalized_key in _PRIVATE_KEYS
        or normalized_key.endswith(_PRIVATE_KEY_SUFFIXES)
    ):
        raise AgentHarnessImportError(
            "failed", "source contains structurally prohibited private material"
        )
    if (
        normalized_key
        and (
            normalized_key in _ENVIRONMENT_KEYS
            or normalized_key.endswith(("environment", "environmentvariables"))
        )
        and isinstance(value, Mapping)
        and value
    ):
        raise AgentHarnessImportError(
            "failed", "source contains a prohibited broad environment capture"
        )
    if isinstance(value, Mapping):
        block_type = value.get("type")
        if isinstance(block_type, str) and block_type in _PRIVATE_BLOCK_TYPES:
            raise AgentHarnessImportError(
                "failed", "source contains prohibited private reasoning material"
            )
        for child_key, child_value in value.items():
            _scan_private_material(child_value, key=str(child_key), depth=depth + 1)
        return
    if isinstance(value, list):
        for child in value:
            _scan_private_material(child, depth=depth + 1)
        return
    if not isinstance(value, str):
        return
    if "-----BEGIN " in value and "PRIVATE KEY-----" in value:
        raise AgentHarnessImportError(
            "failed", "source contains prohibited private-key material"
        )
    if "://" not in value:
        return
    try:
        parsed = urlsplit(value)
    except ValueError:
        return
    if parsed.username is not None or parsed.password is not None:
        raise AgentHarnessImportError(
            "failed", "source contains a credential-bearing URL"
        )
    if any(
        re.sub(r"[^a-z0-9]", "", query_key.lower())
        in {re.sub(r"[^a-z0-9]", "", item) for item in _URL_SECRET_QUERY_KEYS}
        for query_key, _ in parse_qsl(parsed.query)
    ):
        raise AgentHarnessImportError(
            "failed", "source contains a credential-bearing URL"
        )


def _validate_header(header: dict[str, Any]) -> None:
    if header.get("type") != "session":
        raise AgentHarnessImportError(
            "unsupported_source", "source is not an OMP session JSONL v3 file"
        )
    version = header.get("version")
    if not isinstance(version, int) or isinstance(version, bool):
        raise AgentHarnessImportError(
            "unsupported_source", "source format version is missing or malformed"
        )
    if version != SOURCE_FORMAT_VERSION:
        raise AgentHarnessImportError(
            "unsupported_source", "source format version is unsupported"
        )
    session_id = header.get("id")
    if not isinstance(session_id, str) or not session_id:
        raise AgentHarnessImportError(
            "malformed_source", "source session ID is missing or malformed"
        )
    _require_id_or_import_error(session_id, "source session ID")
    for required in ("timestamp", "cwd"):
        if not isinstance(header.get(required), str):
            raise AgentHarnessImportError(
                "malformed_source", "source session header is incomplete"
            )
    unknown = set(header) - _HEADER_FIELDS
    if unknown:
        raise AgentHarnessImportError(
            "unsupported_source", "source header contains unsupported semantics"
        )
    if "providerPromptCacheKey" in header:
        raise AgentHarnessImportError(
            "failed", "source contains structurally prohibited private material"
        )
    _scan_private_material(header)


def _validate_entry(record: dict[str, Any], prior_ids: set[str]) -> None:
    entry_type = record.get("type")
    if not isinstance(entry_type, str) or entry_type not in _ENTRY_FIELDS:
        raise AgentHarnessImportError(
            "unsupported_source", "source contains an unsupported required entry"
        )
    if entry_type == "credential_pin":
        raise AgentHarnessImportError(
            "failed", "source contains structurally prohibited credential metadata"
        )
    unknown = set(record) - _ENTRY_BASE_FIELDS - _ENTRY_FIELDS[entry_type]
    if unknown:
        raise AgentHarnessImportError(
            "unsupported_source", "source entry contains unsupported semantics"
        )
    entry_id = record.get("id")
    if not isinstance(entry_id, str) or not entry_id:
        raise AgentHarnessImportError(
            "malformed_source", "source entry ID is missing or malformed"
        )
    _require_id_or_import_error(entry_id, "source entry ID")
    if entry_id in prior_ids:
        raise AgentHarnessImportError(
            "malformed_source", "source entry IDs must be unique"
        )
    parent_id = record.get("parentId")
    if parent_id is not None and (
        not isinstance(parent_id, str) or parent_id not in prior_ids
    ):
        raise AgentHarnessImportError(
            "malformed_source", "source entry parent must be an earlier entry"
        )
    if not isinstance(record.get("timestamp"), str):
        raise AgentHarnessImportError(
            "malformed_source", "source entry timestamp is missing or malformed"
        )
    if (
        entry_type == "model_change"
        and "resolvedModelIsFallback" in record
        and not isinstance(record["resolvedModelIsFallback"], bool)
    ):
        raise AgentHarnessImportError(
            "malformed_source", "source model fallback flag is malformed"
        )
    if entry_type == "message":
        message = record.get("message")
        if not isinstance(message, dict):
            raise AgentHarnessImportError(
                "malformed_source", "source message entry is malformed"
            )
        role = message.get("role")
        if role not in _ALLOWED_MESSAGE_ROLES or "content" not in message:
            raise AgentHarnessImportError(
                "unsupported_source", "source message semantics are unsupported"
            )
    if entry_type == "custom":
        custom_type = record.get("customType")
        if not isinstance(custom_type, str) or not isinstance(record.get("data"), dict):
            raise AgentHarnessImportError(
                "malformed_source", "source custom entry is malformed"
            )
        if custom_type == "tool_execution_start":
            data = record["data"]
            if not all(
                isinstance(data.get(key), str)
                for key in ("toolCallId", "toolName", "startedAt")
            ):
                raise AgentHarnessImportError(
                    "malformed_source", "tool start entry is malformed"
                )
            _require_id_or_import_error(data["toolCallId"], "source tool call ID")
        if custom_type == "session_exit":
            data = record["data"]
            if data.get("kind") not in {"normal", "signal", "fatal", "process_exit"}:
                raise AgentHarnessImportError(
                    "malformed_source", "session exit entry is malformed"
                )
            if not isinstance(data.get("reason"), str) or not isinstance(
                data.get("recordedAt"), str
            ):
                raise AgentHarnessImportError(
                    "malformed_source", "session exit entry is malformed"
                )
            pending = data.get("pendingToolCalls")
            if pending is not None:
                if not isinstance(pending, list) or len(pending) > MAX_EVENT_COUNT:
                    raise AgentHarnessImportError(
                        "malformed_source", "session pending tool calls are malformed"
                    )
                allowed_pending_fields = {
                    "toolCallId",
                    "toolName",
                    "args",
                    "intent",
                    "assistantTimestamp",
                    "startedAt",
                }
                for item in pending:
                    if (
                        not isinstance(item, dict)
                        or set(item) - allowed_pending_fields
                        or not isinstance(item.get("toolName"), str)
                    ):
                        raise AgentHarnessImportError(
                            "malformed_source",
                            "session pending tool calls are malformed",
                        )
                    call_id = item.get("toolCallId")
                    if call_id is not None:
                        if not isinstance(call_id, str):
                            raise AgentHarnessImportError(
                                "malformed_source",
                                "session pending tool calls are malformed",
                            )
                        _require_id_or_import_error(
                            call_id, "pending source tool call ID"
                        )
                    if "intent" in item and not isinstance(item["intent"], str):
                        raise AgentHarnessImportError(
                            "malformed_source",
                            "session pending tool calls are malformed",
                        )
                    if "startedAt" in item and not isinstance(item["startedAt"], str):
                        raise AgentHarnessImportError(
                            "malformed_source",
                            "session pending tool calls are malformed",
                        )
                    if "assistantTimestamp" in item and not isinstance(
                        item["assistantTimestamp"], int | float
                    ):
                        raise AgentHarnessImportError(
                            "malformed_source",
                            "session pending tool calls are malformed",
                        )
    _scan_private_material(record)


def parse_omp_v3_session(path: Path) -> ParsedSession:
    """Strictly parse one bounded OMP v3 JSONL source without migration or repair."""

    descriptor, before, opened = _open_regular_file(path, label="source session")
    if before.st_size > MAX_SESSION_BYTES:
        os.close(descriptor)
        raise AgentHarnessImportError("failed", "source session exceeds byte limit")

    logical: list[tuple[dict[str, Any], bytes, int]] = []
    total = 0
    try:
        with os.fdopen(descriptor, "rb") as handle:
            physical_line = 0
            while True:
                raw = handle.readline(MAX_JSONL_LINE_BYTES + 1)
                if not raw:
                    break
                physical_line += 1
                total += len(raw)
                if len(raw) > MAX_JSONL_LINE_BYTES:
                    raise AgentHarnessImportError(
                        "failed", "source JSONL line exceeds byte limit"
                    )
                if total > MAX_SESSION_BYTES:
                    raise AgentHarnessImportError(
                        "failed", "source session exceeds byte limit"
                    )
                if not raw.strip():
                    raise AgentHarnessImportError(
                        "malformed_source", "source contains an empty JSONL record"
                    )
                logical.append((_parse_json_object(raw), raw, physical_line))
            if total != before.st_size:
                raise AgentHarnessImportError(
                    "failed", "source session changed while reading"
                )
            _verify_open_file(
                path,
                handle.fileno(),
                before=before,
                opened=opened,
                label="source session",
            )
    except AgentHarnessImportError:
        raise
    except OSError as exc:
        raise AgentHarnessImportError("failed", "source session is unreadable") from exc
    if not logical:
        raise AgentHarnessImportError(
            "unsupported_source", "source is not an OMP session JSONL v3 file"
        )

    if logical[0][0].get("type") == "title":
        if len(logical[0][1]) != _TITLE_SLOT_BYTES:
            raise AgentHarnessImportError(
                "malformed_source", "OMP physical title slot has invalid width"
            )
        _scan_private_material(logical[0][0])
        logical = logical[1:]
    if not logical:
        raise AgentHarnessImportError(
            "unsupported_source", "source session header is missing"
        )

    header, header_raw, _ = logical[0]
    _validate_header(header)
    _scan_private_material(header)
    entries_raw = logical[1:]
    if len(entries_raw) > MAX_EVENT_COUNT:
        raise AgentHarnessImportError("failed", "source event count exceeds limit")

    entries: list[ParsedRecord] = []
    prior_ids: set[str] = set()
    for sequence, (record, raw, physical_line) in enumerate(entries_raw):
        _validate_entry(record, prior_ids)
        prior_ids.add(record["id"])
        entries.append(
            ParsedRecord(
                data=record,
                source_entry_sha256=_sha256_bytes(raw),
                physical_line=physical_line,
                sequence=sequence,
            )
        )

    return ParsedSession(
        header=header,
        header_sha256=_sha256_bytes(header_raw),
        entries=tuple(entries),
        byte_size=total,
    )


def _walk_blob_references(
    value: Any,
    *,
    source_entry_id: str,
    pointer: str = "",
    parent_key: str | None = None,
) -> list[DiscoveredReference]:
    references: list[DiscoveredReference] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            escaped = str(key).replace("~", "~0").replace("/", "~1")
            references.extend(
                _walk_blob_references(
                    child,
                    source_entry_id=source_entry_id,
                    pointer=f"{pointer}/{escaped}",
                    parent_key=str(key),
                )
            )
        return references
    if isinstance(value, list):
        for index, child in enumerate(value):
            references.extend(
                _walk_blob_references(
                    child,
                    source_entry_id=source_entry_id,
                    pointer=f"{pointer}/{index}",
                    parent_key=parent_key,
                )
            )
        return references
    if isinstance(value, str) and parent_key in {"data", "image_url"}:
        match = _BLOB_REF_RE.fullmatch(value)
        if match:
            digest = match.group(1)
            references.append(
                DiscoveredReference(
                    kind="blob",
                    source_entry_id=source_entry_id,
                    source_pointer=pointer,
                    source_object_id=digest,
                    declared_sha256=digest,
                )
            )
        elif value.startswith("blob:"):
            raise AgentHarnessImportError(
                "malformed_source", "source blob reference is malformed"
            )
    return references


def _artifact_references_from_message(
    message: Mapping[str, Any],
) -> list[tuple[str, str]]:
    if message.get("role") != "toolResult":
        return []
    details = message.get("details")
    if not isinstance(details, Mapping):
        return []
    candidates: list[tuple[str, Any]] = []
    if "artifactId" in details:
        candidates.append(("/message/details/artifactId", details.get("artifactId")))
    meta = details.get("meta")
    if isinstance(meta, Mapping):
        truncation = meta.get("truncation")
        if isinstance(truncation, Mapping) and "artifactId" in truncation:
            candidates.append(
                (
                    "/message/details/meta/truncation/artifactId",
                    truncation.get("artifactId"),
                )
            )
    truncation = details.get("truncation")
    if isinstance(truncation, Mapping) and "artifactId" in truncation:
        candidates.append(
            (
                "/message/details/truncation/artifactId",
                truncation.get("artifactId"),
            )
        )
    normalized: list[tuple[str, str]] = []
    for pointer, value in candidates:
        if isinstance(value, int) and not isinstance(value, bool):
            value = str(value)
        if not isinstance(value, str) or not _ARTIFACT_ID_RE.fullmatch(value):
            raise AgentHarnessImportError(
                "malformed_source", "source artifact reference is malformed"
            )
        normalized.append((pointer, value))
    return normalized


def discover_source_references(parsed: ParsedSession) -> list[DiscoveredReference]:
    references: list[DiscoveredReference] = []
    for record in parsed.entries:
        entry_id = record.data["id"]
        references.extend(_walk_blob_references(record.data, source_entry_id=entry_id))
        if record.data["type"] == "message":
            message = record.data["message"]
            for source_pointer, artifact_id in _artifact_references_from_message(
                message
            ):
                references.append(
                    DiscoveredReference(
                        kind="artifact",
                        source_entry_id=entry_id,
                        source_pointer=source_pointer,
                        source_object_id=artifact_id,
                        declared_sha256=None,
                    )
                )
    if len(references) > MAX_REFERENCED_OBJECTS:
        raise AgentHarnessImportError(
            "failed", "referenced source object count exceeds limit"
        )
    ids = [item.reference_id for item in references]
    if len(ids) != len(set(ids)):
        raise AgentHarnessImportError(
            "malformed_source", "source contains duplicate object references"
        )
    return sorted(references, key=lambda item: item.reference_id)


def _hash_regular_file(path: Path, *, limit: int, label: str) -> tuple[str, int]:
    descriptor, before, opened = _open_regular_file(path, label=label)
    if before.st_size > limit:
        os.close(descriptor)
        raise AgentHarnessImportError("failed", f"{label} exceeds byte limit")
    digest = hashlib.sha256()
    total = 0
    try:
        with os.fdopen(descriptor, "rb") as handle:
            for chunk in iter(lambda: handle.read(_COPY_CHUNK_BYTES), b""):
                total += len(chunk)
                if total > limit:
                    raise AgentHarnessImportError(
                        "failed", f"{label} exceeds byte limit"
                    )
                digest.update(chunk)
            if total != before.st_size:
                raise AgentHarnessImportError(
                    "failed", f"{label} changed while reading"
                )
            _verify_open_file(
                path,
                handle.fileno(),
                before=before,
                opened=opened,
                label=label,
            )
    except AgentHarnessImportError:
        raise
    except OSError as exc:
        raise AgentHarnessImportError("failed", f"{label} is unreadable") from exc
    return digest.hexdigest(), total


def _resolve_blob_path(blob_dir: Path | None, digest: str) -> Path:
    if blob_dir is None:
        raise AgentHarnessImportError(
            "failed", "source references blobs but no blob directory was supplied"
        )
    if blob_dir.is_symlink() or not blob_dir.is_dir():
        raise AgentHarnessImportError("failed", "blob directory is unsafe")
    path = blob_dir / digest
    if path.parent != blob_dir:
        raise AgentHarnessImportError("failed", "blob reference escapes source root")
    return path


def _resolve_artifact_path(source: Path, artifact_id: str) -> Path:
    root = source.with_suffix("")
    try:
        before = root.lstat()
    except OSError as exc:
        raise AgentHarnessImportError(
            "failed", "source references an unavailable artifact directory"
        ) from exc
    if stat.S_ISLNK(before.st_mode) or not stat.S_ISDIR(before.st_mode):
        raise AgentHarnessImportError(
            "failed", "source references an unavailable artifact directory"
        )
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(root, flags)
        opened = os.fstat(descriptor)
        if _stat_identity(before) != _stat_identity(opened):
            raise AgentHarnessImportError(
                "failed", "source artifact directory changed while scanning"
            )
        matches: list[str] = []
        with os.scandir(descriptor) as entries:
            for count, entry in enumerate(entries, start=1):
                if count > MAX_ARTIFACT_DIRECTORY_ENTRIES:
                    raise AgentHarnessImportError(
                        "failed", "source artifact directory exceeds entry limit"
                    )
                if entry.name.startswith(f"{artifact_id}.") and entry.name.endswith(
                    ".log"
                ):
                    matches.append(entry.name)
        after_descriptor = os.fstat(descriptor)
    except AgentHarnessImportError:
        raise
    except OSError as exc:
        raise AgentHarnessImportError(
            "failed", "source artifact directory is unreadable"
        ) from exc
    finally:
        if "descriptor" in locals():
            os.close(descriptor)
    try:
        after = root.lstat()
    except OSError as exc:
        raise AgentHarnessImportError(
            "failed", "source artifact directory changed while scanning"
        ) from exc
    if _stat_identity(before) != _stat_identity(after_descriptor) or _stat_identity(
        before
    ) != _stat_identity(after):
        raise AgentHarnessImportError(
            "failed", "source artifact directory changed while scanning"
        )
    if len(matches) != 1:
        raise AgentHarnessImportError(
            "failed", "source artifact reference is missing or conflicting"
        )
    return root / matches[0]


def resolve_source_objects(
    source: Path,
    references: list[DiscoveredReference],
    *,
    blob_dir: Path | None,
    session_size: int,
) -> list[ResolvedObject]:
    resolved: list[ResolvedObject] = []
    total = session_size
    counted_digests: set[str] = set()
    for reference in references:
        path = (
            _resolve_blob_path(blob_dir, reference.source_object_id)
            if reference.kind == "blob"
            else _resolve_artifact_path(source, reference.source_object_id)
        )
        digest, byte_size = _hash_regular_file(
            path, limit=MAX_OBJECT_BYTES, label="referenced source object"
        )
        if (
            reference.declared_sha256 is not None
            and digest != reference.declared_sha256
        ):
            raise AgentHarnessImportError(
                "failed", "source object digest does not match its declared identity"
            )
        if digest not in counted_digests:
            total += byte_size
            counted_digests.add(digest)
        if total > MAX_TOTAL_SOURCE_BYTES:
            raise AgentHarnessImportError(
                "failed", "total imported source bytes exceed limit"
            )
        resolved.append(
            ResolvedObject(
                reference=reference,
                source_path=path,
                sha256=digest,
                byte_size=byte_size,
            )
        )
    return resolved


def _copy_exact_file(
    source: Path,
    destination: Path,
    *,
    expected_sha256: str,
    expected_size: int,
    limit: int,
    label: str,
) -> None:
    descriptor, before, opened = _open_regular_file(source, label=label)
    if before.st_size != expected_size or before.st_size > limit:
        os.close(descriptor)
        raise AgentHarnessImportError("failed", f"{label} changed before copy")
    destination.parent.mkdir(parents=True, exist_ok=True)
    output_flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_BINARY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        output_descriptor = os.open(destination, output_flags, 0o600)
    except OSError as exc:
        os.close(descriptor)
        raise AgentHarnessImportError("failed", f"{label} could not be copied") from exc
    digest = hashlib.sha256()
    total = 0
    try:
        with (
            os.fdopen(descriptor, "rb") as input_handle,
            os.fdopen(output_descriptor, "wb") as output_handle,
        ):
            for chunk in iter(lambda: input_handle.read(_COPY_CHUNK_BYTES), b""):
                total += len(chunk)
                if total > limit:
                    raise AgentHarnessImportError(
                        "failed", f"{label} exceeds byte limit"
                    )
                digest.update(chunk)
                output_handle.write(chunk)
            _verify_open_file(
                source,
                input_handle.fileno(),
                before=before,
                opened=opened,
                label=label,
            )
    except AgentHarnessImportError:
        raise
    except OSError as exc:
        raise AgentHarnessImportError("failed", f"{label} could not be copied") from exc
    if total != expected_size or digest.hexdigest() != expected_sha256:
        raise AgentHarnessImportError("failed", f"{label} copy failed integrity check")
    copied_digest, copied_size = _hash_regular_file(
        destination, limit=limit, label="copied source member"
    )
    if copied_size != expected_size or copied_digest != expected_sha256:
        raise AgentHarnessImportError(
            "failed", f"{label} destination verification failed"
        )


def _fact(
    value: str | int | bool | None,
    *,
    source_entry_id: str | None,
    missing: Availability = "unknown",
) -> SourceFact:
    if value is None:
        return SourceFact(
            availability=missing, value=None, source_entry_id=source_entry_id
        )
    return SourceFact(
        availability="available", value=value, source_entry_id=source_entry_id
    )


def _entry_event(
    record: ParsedRecord,
    *,
    event_id: str,
    subsequence: int,
    kind: str,
    visibility: str,
    role: str | None = None,
    content: Any = None,
    tool_call_id: str | None = None,
    tool_name: str | None = None,
) -> TrajectoryEvent:
    return TrajectoryEvent(
        event_id=event_id,
        sequence=record.sequence,
        subsequence=subsequence,
        kind=kind,
        source_entry_id=record.data["id"],
        source_entry_type=record.data["type"],
        source_entry_sha256=record.source_entry_sha256,
        parent_id=record.data.get("parentId"),
        role=role,
        visibility=visibility,
        content_sha256=(
            _sha256_bytes(_canonical_json_bytes(content))
            if content is not None
            else None
        ),
        tool_call_id=tool_call_id,
        tool_name=tool_name,
    )


def _tool_calls(message: Mapping[str, Any]) -> list[dict[str, Any]]:
    content = message.get("content")
    if not isinstance(content, list):
        return []
    calls: list[dict[str, Any]] = []
    for block in content:
        if not isinstance(block, Mapping) or block.get("type") != "toolCall":
            continue
        call_id = block.get("id")
        name = block.get("name")
        arguments = block.get("arguments", block.get("args"))
        if (
            not isinstance(call_id, str)
            or not isinstance(name, str)
            or not isinstance(arguments, dict)
        ):
            raise AgentHarnessImportError(
                "malformed_source", "source tool request is malformed"
            )
        _require_id_or_import_error(call_id, "source tool call ID")
        calls.append({"id": call_id, "name": name, "arguments": arguments})
    return calls


def _require_id_or_import_error(value: str, label: str) -> None:
    try:
        _require_id(value, label)
    except ValueError as exc:
        raise AgentHarnessImportError(
            "malformed_source", f"{label} is malformed"
        ) from exc


def _terminal_exit_record(parsed: ParsedSession) -> ParsedRecord | None:
    if not parsed.entries:
        return None
    record = parsed.entries[-1]
    if (
        record.data["type"] == "custom"
        and record.data.get("customType") == "session_exit"
    ):
        return record
    return None


def normalize_trajectory(parsed: ParsedSession) -> list[TrajectoryEvent]:
    events: list[TrajectoryEvent] = []
    terminal_record = _terminal_exit_record(parsed)
    terminal_entry_id = (
        terminal_record.data["id"] if terminal_record is not None else None
    )
    for record in parsed.entries:
        data = record.data
        entry_id = data["id"]
        entry_type = data["type"]
        base_id = f"event:{entry_id}"
        if entry_type == "message":
            message = data["message"]
            role = message["role"]
            if role == "user":
                kind = "user_input"
                visibility = "user_and_model_visible"
            elif role == "assistant":
                kind = "model_message"
                visibility = "user_and_model_visible"
            elif role == "toolResult":
                kind = "tool_output"
                visibility = "model_visible"
            elif role == "system":
                kind = "model_message"
                visibility = "model_visible"
            else:
                kind = "harness_message"
                visibility = "harness_internal"
            events.append(
                _entry_event(
                    record,
                    event_id=base_id,
                    subsequence=0,
                    kind=kind,
                    visibility=visibility,
                    role=role,
                    content=message.get("content"),
                    tool_call_id=(
                        message.get("toolCallId")
                        if isinstance(message.get("toolCallId"), str)
                        else None
                    ),
                    tool_name=(
                        message.get("toolName")
                        if isinstance(message.get("toolName"), str)
                        else None
                    ),
                )
            )
            for offset, call in enumerate(_tool_calls(message), start=1):
                request_kind = (
                    "command_request" if call["name"] == "bash" else "tool_request"
                )
                events.append(
                    _entry_event(
                        record,
                        event_id=f"{base_id}:request:{call['id']}",
                        subsequence=offset,
                        kind=request_kind,
                        visibility="harness_internal",
                        role="assistant",
                        content=call["arguments"],
                        tool_call_id=call["id"],
                        tool_name=call["name"],
                    )
                )
            continue
        if entry_type == "session_init":
            subsequence = 0
            if isinstance(data.get("task"), str):
                events.append(
                    _entry_event(
                        record,
                        event_id=f"{base_id}:task",
                        subsequence=subsequence,
                        kind="task_input",
                        visibility="model_visible",
                        role="task",
                        content=data["task"],
                    )
                )
                subsequence += 1
            if isinstance(data.get("systemPrompt"), str):
                events.append(
                    _entry_event(
                        record,
                        event_id=f"{base_id}:system",
                        subsequence=subsequence,
                        kind="model_message",
                        visibility="model_visible",
                        role="system",
                        content=data["systemPrompt"],
                    )
                )
                subsequence += 1
            if "tools" in data:
                events.append(
                    _entry_event(
                        record,
                        event_id=f"{base_id}:tools",
                        subsequence=subsequence,
                        kind="harness_message",
                        visibility="model_visible",
                        role="tools",
                        content=data["tools"],
                    )
                )
                subsequence += 1
            if subsequence == 0:
                events.append(
                    _entry_event(
                        record,
                        event_id=base_id,
                        subsequence=0,
                        kind="harness_event",
                        visibility="harness_internal",
                        content=data,
                    )
                )
            continue
        if entry_type == "custom" and data.get("customType") == "tool_execution_start":
            start = data["data"]
            events.append(
                _entry_event(
                    record,
                    event_id=base_id,
                    subsequence=0,
                    kind="execution_start",
                    visibility="harness_internal",
                    content=start.get("args", {}),
                    tool_call_id=start["toolCallId"],
                    tool_name=start["toolName"],
                )
            )
            continue
        if entry_type == "custom" and data.get("customType") == "session_exit":
            events.append(
                _entry_event(
                    record,
                    event_id=base_id,
                    subsequence=0,
                    kind=(
                        "source_terminal"
                        if entry_id == terminal_entry_id
                        else "harness_event"
                    ),
                    visibility="harness_internal",
                    content=data["data"],
                )
            )
            continue
        if entry_type == "custom_message":
            visibility = (
                "user_and_model_visible"
                if data.get("display") is True
                else "model_visible"
            )
            events.append(
                _entry_event(
                    record,
                    event_id=base_id,
                    subsequence=0,
                    kind="harness_message",
                    visibility=visibility,
                    role=(
                        data.get("attribution")
                        if isinstance(data.get("attribution"), str)
                        else None
                    ),
                    content=data.get("content"),
                )
            )
            continue
        if entry_type in {"branch_summary", "compaction", "ttsr_injection"}:
            events.append(
                _entry_event(
                    record,
                    event_id=base_id,
                    subsequence=0,
                    kind="harness_message",
                    visibility="model_visible",
                    role=entry_type,
                    content=data,
                )
            )
            continue
        events.append(
            _entry_event(
                record,
                event_id=base_id,
                subsequence=0,
                kind="harness_event",
                visibility="harness_internal",
                content=data,
            )
        )
    if len(events) > MAX_EVENT_COUNT:
        raise AgentHarnessImportError(
            "failed", "normalized trajectory event count exceeds limit"
        )
    return events


def _truncation_details(
    message: Mapping[str, Any],
) -> tuple[Mapping[str, Any], str] | None:
    details = message.get("details")
    if not isinstance(details, Mapping):
        return None
    direct = details.get("truncation")
    if isinstance(direct, Mapping):
        return direct, "/message/details/truncation"
    meta = details.get("meta")
    if isinstance(meta, Mapping) and isinstance(meta.get("truncation"), Mapping):
        return meta["truncation"], "/message/details/meta/truncation"
    return None


def _tool_result_map(
    parsed: ParsedSession,
) -> dict[str, tuple[ParsedRecord, dict[str, Any]]]:
    results: dict[str, tuple[ParsedRecord, dict[str, Any]]] = {}
    for record in parsed.entries:
        if record.data["type"] != "message":
            continue
        message = record.data["message"]
        if message.get("role") != "toolResult":
            continue
        call_id = message.get("toolCallId")
        if not isinstance(call_id, str):
            raise AgentHarnessImportError(
                "malformed_source", "source tool result lacks a tool call ID"
            )
        if call_id in results:
            raise AgentHarnessImportError(
                "malformed_source", "source has duplicate terminal tool results"
            )
        results[call_id] = (record, message)
    return results


def _pending_tool_map(
    parsed: ParsedSession,
) -> dict[str, tuple[ParsedRecord, dict[str, Any]]]:
    terminal = _terminal_exit_record(parsed)
    if terminal is None:
        return {}
    pending = terminal.data["data"].get("pendingToolCalls")
    if not isinstance(pending, list):
        return {}
    mapped: dict[str, tuple[ParsedRecord, dict[str, Any]]] = {}
    for item in pending:
        call_id = item.get("toolCallId")
        if call_id is None:
            continue
        if call_id in mapped:
            raise AgentHarnessImportError(
                "malformed_source", "source has duplicate pending tool calls"
            )
        mapped[call_id] = (terminal, item)
    return mapped


def normalize_tool_lifecycles(
    parsed: ParsedSession, source_references: list[SourceReference]
) -> list[ToolLifecycle]:
    requests: dict[str, tuple[ParsedRecord, dict[str, Any]]] = {}
    starts: dict[str, tuple[ParsedRecord, dict[str, Any]]] = {}
    for record in parsed.entries:
        if record.data["type"] == "message":
            for call in _tool_calls(record.data["message"]):
                if call["id"] in requests:
                    raise AgentHarnessImportError(
                        "malformed_source", "source tool call IDs must be unique"
                    )
                requests[call["id"]] = (record, call)
        elif (
            record.data["type"] == "custom"
            and record.data.get("customType") == "tool_execution_start"
        ):
            start = record.data["data"]
            call_id = start["toolCallId"]
            if call_id in starts:
                raise AgentHarnessImportError(
                    "malformed_source", "source has duplicate tool start records"
                )
            starts[call_id] = (record, start)
    results = _tool_result_map(parsed)
    pending = _pending_tool_map(parsed)
    if (
        set(starts) - set(requests)
        or set(results) - set(requests)
        or set(pending) - set(requests)
    ):
        raise AgentHarnessImportError(
            "malformed_source", "tool lifecycle references an unknown request"
        )
    if set(results) & set(pending):
        raise AgentHarnessImportError(
            "malformed_source", "tool lifecycle is both terminal and pending"
        )

    artifact_members = {
        (item.source_entry_id, item.source_pointer): item.member_id
        for item in source_references
        if item.kind == "artifact"
    }
    lifecycles: list[ToolLifecycle] = []
    for call_id, (request_record, call) in sorted(
        requests.items(), key=lambda item: item[1][0].sequence
    ):
        start_item = starts.get(call_id)
        result_item = results.get(call_id)
        pending_item = pending.get(call_id)
        if start_item is not None:
            if start_item[0].sequence <= request_record.sequence:
                raise AgentHarnessImportError(
                    "malformed_source", "tool start precedes its request"
                )
            if start_item[1]["toolName"] != call["name"]:
                raise AgentHarnessImportError(
                    "malformed_source", "tool start name disagrees with its request"
                )
        if result_item is not None:
            if result_item[0].sequence <= request_record.sequence or (
                start_item is not None
                and result_item[0].sequence <= start_item[0].sequence
            ):
                raise AgentHarnessImportError(
                    "malformed_source", "tool result precedes its lifecycle"
                )
            result_tool_name = result_item[1].get("toolName")
            if result_tool_name is not None and result_tool_name != call["name"]:
                raise AgentHarnessImportError(
                    "malformed_source", "tool result name disagrees with its request"
                )
        if pending_item is not None:
            if pending_item[0].sequence <= request_record.sequence or (
                start_item is not None
                and pending_item[0].sequence <= start_item[0].sequence
            ):
                raise AgentHarnessImportError(
                    "malformed_source", "pending tool state precedes its lifecycle"
                )
            if pending_item[1]["toolName"] != call["name"]:
                raise AgentHarnessImportError(
                    "malformed_source", "pending tool name disagrees with its request"
                )

        started_event_id = (
            f"event:{start_item[0].data['id']}" if start_item is not None else None
        )
        terminal_item = result_item or pending_item
        terminal_event_id = (
            f"event:{terminal_item[0].data['id']}"
            if terminal_item is not None
            else None
        )
        output_availability: Availability = "absent"
        output_complete = False
        output_sha256 = None
        full_output_member_id = None
        exit_status = None
        signal = None
        timed_out = False
        denied = False
        interrupted = pending_item is not None
        cancelled = False
        is_error = None
        if result_item is not None:
            result_record, message = result_item
            details = message.get("details")
            details = details if isinstance(details, Mapping) else {}
            is_error = (
                message.get("isError")
                if isinstance(message.get("isError"), bool)
                else None
            )
            timed_out = details.get("timedOut") is True
            denied = (
                details.get("denied") is True or details.get("approval") == "denied"
            )
            interrupted = details.get("interrupted") is True
            cancelled = details.get("cancelled") is True
            exit_value = details.get("exitCode")
            if isinstance(exit_value, int) and not isinstance(exit_value, bool):
                exit_status = exit_value
            if isinstance(details.get("signal"), str):
                signal = details["signal"]
                interrupted = True
            if sum((timed_out, denied, interrupted, cancelled)) > 1:
                raise AgentHarnessImportError(
                    "malformed_source", "tool result has conflicting terminal states"
                )
            if denied and start_item is not None:
                raise AgentHarnessImportError(
                    "malformed_source", "denied tool action cannot have started"
                )
            content = message.get("content")
            output_availability = "available"
            output_sha256 = _sha256_bytes(_canonical_json_bytes(content))
            truncation = _truncation_details(message)
            if truncation is not None:
                full_output_member_id = artifact_members.get(
                    (result_record.data["id"], f"{truncation[1]}/artifactId")
                )
            output_complete = not _contains_persistence_loss(content) and (
                truncation is None or full_output_member_id is not None
            )
            if denied:
                lifecycle_state: LifecycleState = "denied"
            elif timed_out:
                lifecycle_state = "timed_out"
            elif cancelled:
                lifecycle_state = "cancelled"
            elif interrupted:
                lifecycle_state = "interrupted"
            elif is_error is True or (exit_status is not None and exit_status != 0):
                lifecycle_state = "failed"
            else:
                lifecycle_state = "completed"
        elif pending_item is not None:
            lifecycle_state = "interrupted"
        elif start_item is not None:
            lifecycle_state = "started"
        else:
            lifecycle_state = "requested"

        source_items = [request_record]
        if start_item is not None:
            source_items.append(start_item[0])
        if terminal_item is not None:
            source_items.append(terminal_item[0])
        source_entry_ids = [
            item.data["id"]
            for item in sorted(source_items, key=lambda item: item.sequence)
        ]
        lifecycles.append(
            ToolLifecycle(
                lifecycle_id=f"lifecycle:{call_id}",
                tool_call_id=call_id,
                tool_name=call["name"],
                lifecycle_state=lifecycle_state,
                source_entry_ids=source_entry_ids,
                request_event_id=f"event:{request_record.data['id']}:request:{call_id}",
                started_event_id=started_event_id,
                terminal_event_id=terminal_event_id,
                arguments=call["arguments"],
                arguments_sha256=_sha256_bytes(
                    _canonical_json_bytes(call["arguments"])
                ),
                output_availability=output_availability,
                output_complete=output_complete,
                output_sha256=output_sha256,
                full_output_member_id=full_output_member_id,
                exit_status=exit_status,
                signal=signal,
                timed_out=timed_out,
                denied=denied,
                interrupted=interrupted,
                cancelled=cancelled,
                is_error=is_error,
            )
        )
    return lifecycles


def normalize_model_observations(parsed: ParsedSession) -> list[ModelObservation]:
    observations: list[ModelObservation] = []
    for record in parsed.entries:
        data = record.data
        if data["type"] == "model_change":
            observations.append(
                ModelObservation(
                    observation_id=f"model:{data['id']}",
                    source_entry_id=data["id"],
                    provider=_fact(None, source_entry_id=data["id"], missing="absent"),
                    model=_fact(data.get("model"), source_entry_id=data["id"]),
                    role=_fact(data.get("role", "default"), source_entry_id=data["id"]),
                    resolved_model_is_fallback=(
                        _fact(
                            data["resolvedModelIsFallback"],
                            source_entry_id=data["id"],
                        )
                        if "resolvedModelIsFallback" in data
                        else None
                    ),
                )
            )
        elif data["type"] == "message" and data["message"].get("role") == "assistant":
            message = data["message"]
            provider = message.get("provider")
            model = message.get("model")
            if provider is None and model is None:
                continue
            observations.append(
                ModelObservation(
                    observation_id=f"model:{data['id']}",
                    source_entry_id=data["id"],
                    provider=_fact(
                        provider if isinstance(provider, str) else None,
                        source_entry_id=data["id"],
                        missing="absent",
                    ),
                    model=_fact(
                        model if isinstance(model, str) else None,
                        source_entry_id=data["id"],
                        missing="absent",
                    ),
                    role=_fact("default", source_entry_id=data["id"]),
                )
            )
    return observations


def normalize_task_identity(parsed: ParsedSession) -> SourceFact:
    tasks = [
        (record.data["id"], record.data.get("task"))
        for record in parsed.entries
        if record.data["type"] == "session_init"
        and isinstance(record.data.get("task"), str)
    ]
    if not tasks:
        return _fact(None, source_entry_id=None, missing="unknown")
    values = {value for _, value in tasks}
    if len(values) != 1:
        raise AgentHarnessImportError(
            "malformed_source", "source contains conflicting task identities"
        )
    entry_id, task = tasks[-1]
    return _fact(task, source_entry_id=entry_id)


def normalize_terminal(parsed: ParsedSession) -> SourceTerminal:
    record = _terminal_exit_record(parsed)
    if record is None:
        return SourceTerminal(outcome="unknown", availability="absent")
    data = record.data["data"]
    kind = data["kind"]
    if kind == "fatal":
        outcome: SourceSessionOutcome = "failed"
    elif kind in {"signal", "process_exit"}:
        outcome = "interrupted"
    else:
        outcome = "unknown"
    return SourceTerminal(
        outcome=outcome,
        availability="available",
        source_entry_id=record.data["id"],
        kind=kind,
        reason=data["reason"],
    )


def _contains_persistence_loss(value: Any) -> bool:
    stack = [value]
    while stack:
        item = stack.pop()
        if item == _PERSISTENCE_TRUNCATION_MARKER:
            return True
        if isinstance(item, Mapping):
            stack.extend(item.values())
        elif isinstance(item, list):
            stack.extend(item)
    return False


def normalize_completeness(
    parsed: ParsedSession, references: list[SourceReference]
) -> SourceCompleteness:
    artifact_pointers = {
        (item.source_entry_id, item.source_pointer)
        for item in references
        if item.kind == "artifact"
    }
    terminal = _terminal_exit_record(parsed)
    if terminal is not None:
        pending = terminal.data["data"].get("pendingToolCalls")
        if isinstance(pending, list) and any(
            item.get("toolCallId") is None for item in pending
        ):
            return "partial"
    for record in parsed.entries:
        if _contains_persistence_loss(record.data):
            return "partial"
        if record.data["type"] != "message":
            continue
        message = record.data["message"]
        truncation = _truncation_details(message)
        if (
            truncation is not None
            and (
                record.data["id"],
                f"{truncation[1]}/artifactId",
            )
            not in artifact_pointers
        ):
            return "partial"
    return "complete"


def _source_package_projection(inventory: list[SourceMember]) -> list[dict[str, Any]]:
    return sorted(
        [
            {
                "path": item.path,
                "role": item.role,
                "byte_size": item.byte_size,
                "sha256": item.sha256,
            }
            for item in inventory
        ],
        key=lambda item: item["path"],
    )


def source_package_sha256(inventory: list[SourceMember]) -> str:
    return _sha256_bytes(_canonical_json_bytes(_source_package_projection(inventory)))


def _member_projection(item: SourceMember) -> dict[str, Any]:
    return item.model_dump(mode="json", exclude={"observed_source_path"})


def immutable_mapping_projection(evidence: AgentHarnessEvidence) -> dict[str, Any]:
    return {
        "source": evidence.source.model_dump(mode="json"),
        "source_completeness": evidence.source_completeness,
        "source_session_outcome": evidence.source_session_outcome,
        "task_identity": evidence.task_identity.model_dump(mode="json"),
        "source_inventory": [
            _member_projection(item)
            for item in sorted(evidence.source_inventory, key=lambda item: item.path)
        ],
        "source_references": [
            item.model_dump(mode="json")
            for item in sorted(
                evidence.source_references, key=lambda item: item.reference_id
            )
        ],
        "trajectory": [item.model_dump(mode="json") for item in evidence.trajectory],
        "tool_lifecycles": [
            item.model_dump(mode="json") for item in evidence.tool_lifecycles
        ],
        "model_observations": [
            item.model_dump(mode="json") for item in evidence.model_observations
        ],
        "repository_observations": [
            item.model_dump(mode="json") for item in evidence.repository_observations
        ],
        "terminal": evidence.terminal.model_dump(mode="json"),
    }


def imported_session_identity(evidence: AgentHarnessEvidence) -> str:
    projection = {
        "source_type": evidence.source.source_type,
        "source_format": evidence.source.source_format,
        "source_format_version": evidence.source.source_format_version,
        "producer": evidence.source.producer.model_dump(mode="json"),
        "source_session_id": evidence.source.session_id,
        "source_package_sha256": evidence.source_package_sha256,
    }
    return "sha256:" + _sha256_bytes(_canonical_json_bytes(projection))


def evidence_identity(evidence: AgentHarnessEvidence) -> str:
    projection = {
        "imported_session_id": evidence.imported_session_id,
        "schema_version": evidence.schema_version,
        "contract_version": evidence.contract_version,
        "evidence_class": evidence.evidence_class,
        "importer": evidence.importer.model_dump(mode="json"),
        "immutable_mapping": immutable_mapping_projection(evidence),
    }
    return "sha256:" + _sha256_bytes(_canonical_json_bytes(projection))


def immutable_agent_harness_payload(evidence: AgentHarnessEvidence) -> dict[str, Any]:
    return {
        "schema_version": evidence.schema_version,
        "contract_version": evidence.contract_version,
        "evidence_class": evidence.evidence_class,
        "evidence_id": evidence.evidence_id,
        "imported_session_id": evidence.imported_session_id,
        "source_package_sha256": evidence.source_package_sha256,
        "importer": evidence.importer.model_dump(mode="json"),
        "immutable_mapping": immutable_mapping_projection(evidence),
    }


def _build_inventory(
    source: Path,
    session_sha256: str,
    session_size: int,
    resolved: list[ResolvedObject],
) -> list[SourceMember]:
    inventory = [
        SourceMember(
            member_id="session",
            role="session_log",
            path=SESSION_RELATIVE_PATH,
            sha256=session_sha256,
            byte_size=session_size,
            availability="available",
            source_relationship="canonical_session",
            observed_source_path=str(source),
        )
    ]
    by_digest: dict[str, int] = {}
    for item in resolved:
        previous_size = by_digest.get(item.sha256)
        if previous_size is not None and previous_size != item.byte_size:
            raise AgentHarnessImportError(
                "failed", "conflicting source objects share one digest identity"
            )
        by_digest[item.sha256] = item.byte_size
    for digest, byte_size in sorted(by_digest.items()):
        inventory.append(
            SourceMember(
                member_id=f"object:{digest}",
                role="source_object",
                path=f"{OBJECTS_RELATIVE_DIR}/{digest}",
                sha256=digest,
                byte_size=byte_size,
                availability="available",
                source_relationship="referenced_object",
            )
        )
    return inventory


def _build_source_references(
    resolved: list[ResolvedObject],
) -> list[SourceReference]:
    return [
        SourceReference(
            reference_id=item.reference.reference_id,
            kind=item.reference.kind,
            source_entry_id=item.reference.source_entry_id,
            source_pointer=item.reference.source_pointer,
            source_object_id=item.reference.source_object_id,
            declared_sha256=item.reference.declared_sha256,
            member_id=f"object:{item.sha256}",
            availability="available",
            source_relationship=f"{item.reference.kind}_reference",
        )
        for item in sorted(resolved, key=lambda item: item.reference.reference_id)
    ]


def build_agent_harness_evidence(
    source: Path,
    parsed: ParsedSession,
    session_sha256: str,
    resolved: list[ResolvedObject],
) -> AgentHarnessEvidence:
    inventory = _build_inventory(source, session_sha256, parsed.byte_size, resolved)
    references = _build_source_references(resolved)
    terminal = normalize_terminal(parsed)
    terminal_record = _terminal_exit_record(parsed)
    ended_at = (
        _fact(
            terminal_record.data["data"]["recordedAt"],
            source_entry_id=terminal_record.data["id"],
        )
        if terminal_record is not None
        else _fact(None, source_entry_id=None, missing="absent")
    )
    source_identity = SourceIdentity(
        source_type=SOURCE_TYPE,
        source_format=SOURCE_FORMAT,
        source_format_version=SOURCE_FORMAT_VERSION,
        producer=ProducerIdentity(
            producer_id=SOURCE_PRODUCER,
            version=_fact(None, source_entry_id=None, missing="unknown"),
        ),
        session_id=parsed.header["id"],
        started_at=_fact(parsed.header["timestamp"], source_entry_id="session"),
        ended_at=ended_at,
        workspace_path=_fact(parsed.header["cwd"], source_entry_id="session"),
        selected_leaf=_fact(None, source_entry_id=None, missing="unknown"),
    )
    draft = AgentHarnessEvidence(
        schema_version=EVIDENCE_SCHEMA_VERSION,
        contract_version=CONTRACT_VERSION,
        evidence_class=EVIDENCE_CLASS,
        evidence_id="sha256:" + "0" * 64,
        imported_session_id="sha256:" + "0" * 64,
        source_package_sha256=source_package_sha256(inventory),
        source=source_identity,
        importer=ImporterIdentity(importer_id=IMPORTER_ID, version=__version__),
        source_completeness=normalize_completeness(parsed, references),
        source_session_outcome=terminal.outcome,
        import_outcome="completed",
        validation_outcome="passed",
        scoreability="not_assessed",
        publication_readiness="not_assessed",
        task_identity=normalize_task_identity(parsed),
        source_inventory=inventory,
        source_references=references,
        trajectory=normalize_trajectory(parsed),
        tool_lifecycles=normalize_tool_lifecycles(parsed, references),
        model_observations=normalize_model_observations(parsed),
        repository_observations=[],
        terminal=terminal,
    )
    draft.imported_session_id = imported_session_identity(draft)
    draft.evidence_id = evidence_identity(draft)
    return AgentHarnessEvidence.model_validate(draft.model_dump(mode="json"))


def _source_and_destination_overlap(
    source: Path,
    destination: Path,
    *,
    blob_dir: Path | None,
) -> bool:
    source_resolved = source.resolve(strict=False)
    destination_resolved = destination.resolve(strict=False)
    roots = [source.with_suffix("").resolve(strict=False)]
    if blob_dir is not None:
        roots.append(blob_dir.resolve(strict=False))
    for root in roots:
        try:
            destination_resolved.relative_to(root)
            return True
        except ValueError:
            pass
    try:
        source_resolved.relative_to(destination_resolved)
        return True
    except ValueError:
        return False


def _build_result(
    destination: Path,
    evidence: AgentHarnessEvidence,
    evidence_sha256: str,
) -> dict[str, Any]:
    result = {
        "schema_version": "llmgauge.result.v0",
        "llmgauge_version": __version__,
        "run": {
            "operation": "agent_harness_import",
            "run_id": f"agent-harness-{evidence.evidence_id.removeprefix('sha256:')[:16]}",
            "timestamp_utc": datetime.now(UTC).replace(microsecond=0).isoformat(),
            "result_dir": str(destination),
            "status": "completed",
        },
        "model": {"model_path": "redacted"},
        "runtime": {},
        "suite": {},
        "summary": {"completed": 0, "failed": 0},
        "results": [],
        "agent_harness_evidence": AgentHarnessEvidenceReference(
            schema_version=EVIDENCE_SCHEMA_VERSION,
            contract_version=CONTRACT_VERSION,
            evidence_class=EVIDENCE_CLASS,
            evidence_id=evidence.evidence_id,
            path=EVIDENCE_RELATIVE_PATH,
            sha256=evidence_sha256,
        ).model_dump(mode="json"),
    }
    return result


def _existing_import_result(
    destination: Path,
    expected: AgentHarnessEvidence,
) -> ImportOperationResult | None:
    if not destination.exists():
        return None
    if destination.is_symlink() or not destination.is_dir():
        raise AgentHarnessImportError("failed", "destination already exists")
    try:
        from llmgauge.core.result_validation import validate_result_dir

        errors = validate_result_dir(destination)
        result = json.loads(
            (destination / "llmgauge-result.json").read_text(encoding="utf-8")
        )
        reference = result.get("agent_harness_evidence")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise AgentHarnessImportError(
            "failed", "destination contains conflicting or invalid evidence"
        ) from exc
    if errors or not isinstance(reference, Mapping):
        raise AgentHarnessImportError(
            "failed", "destination contains conflicting or invalid evidence"
        )
    if reference.get("evidence_id") != expected.evidence_id:
        raise AgentHarnessImportError("failed", "destination evidence conflicts")
    evidence = load_agent_harness_evidence(destination, reference)
    if evidence.source_package_sha256 != expected.source_package_sha256:
        raise AgentHarnessImportError("failed", "destination evidence conflicts")
    return ImportOperationResult(
        outcome="already_imported",
        evidence_id=evidence.evidence_id,
        source_package_sha256=evidence.source_package_sha256,
        destination=destination,
    )


def _create_lock(destination: Path) -> tuple[int, Path]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    lock_path = destination.parent / f".{destination.name}.agent-harness-import.lock"
    try:
        descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise AgentHarnessImportError(
            "failed", "another import is in progress"
        ) from exc
    except OSError as exc:
        raise AgentHarnessImportError(
            "failed", "import lock could not be created"
        ) from exc
    return descriptor, lock_path


def _rename_directory_no_replace(source: Path, destination: Path) -> None:
    if os.name == "nt":
        try:
            os.rename(source, destination)
        except FileExistsError as exc:
            raise AgentHarnessImportError(
                "failed", "destination appeared during import"
            ) from exc
        except OSError as exc:
            raise AgentHarnessImportError(
                "failed", "completed import could not be published atomically"
            ) from exc
        return
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        renameat2 = libc.renameat2
    except (AttributeError, OSError) as exc:
        raise AgentHarnessImportError(
            "failed", "atomic no-replace directory publish is unavailable"
        ) from exc
    renameat2.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    ]
    renameat2.restype = ctypes.c_int
    at_fdcwd = -100
    rename_noreplace = 1
    if (
        renameat2(
            at_fdcwd,
            os.fsencode(source),
            at_fdcwd,
            os.fsencode(destination),
            rename_noreplace,
        )
        == 0
    ):
        return
    error_number = ctypes.get_errno()
    if error_number in {errno.EEXIST, errno.ENOTEMPTY}:
        raise AgentHarnessImportError("failed", "destination appeared during import")
    raise AgentHarnessImportError(
        "failed",
        "completed import could not be published atomically",
    )


def import_agent_harness_session(
    source: Path,
    destination: Path,
    *,
    blob_dir: Path | None = None,
    dry_run: bool = False,
) -> ImportOperationResult:
    """Import one exact OMP v3 source as contained, read-only evidence."""

    source = source.expanduser()
    destination = destination.expanduser()
    blob_dir = blob_dir.expanduser() if blob_dir is not None else None
    if _source_and_destination_overlap(source, destination, blob_dir=blob_dir):
        raise AgentHarnessImportError(
            "failed", "source and destination overlap is unsafe"
        )
    parsed = parse_omp_v3_session(source)
    session_sha256, session_size = _hash_regular_file(
        source, limit=MAX_SESSION_BYTES, label="source session"
    )
    if session_size != parsed.byte_size:
        raise AgentHarnessImportError("failed", "source session changed during import")
    references = discover_source_references(parsed)
    resolved = resolve_source_objects(
        source,
        references,
        blob_dir=blob_dir,
        session_size=session_size,
    )
    try:
        evidence = build_agent_harness_evidence(
            source, parsed, session_sha256, resolved
        )
    except AgentHarnessImportError:
        raise
    except (ValidationError, ValueError, TypeError, RecursionError) as exc:
        raise AgentHarnessImportError(
            "malformed_source", "source evidence cannot be represented safely"
        ) from exc
    existing = _existing_import_result(destination, evidence)
    if existing is not None:
        return existing
    if dry_run:
        return ImportOperationResult(
            outcome="dry_run",
            evidence_id=evidence.evidence_id,
            source_package_sha256=evidence.source_package_sha256,
            destination=destination,
        )

    descriptor, lock_path = _create_lock(destination)
    staging: Path | None = None
    try:
        staging = Path(
            tempfile.mkdtemp(
                prefix=f".{destination.name}.agent-harness-import-",
                dir=destination.parent,
            )
        )
        if destination.exists():
            raise AgentHarnessImportError("failed", "destination already exists")
        _copy_exact_file(
            source,
            staging / SESSION_RELATIVE_PATH,
            expected_sha256=session_sha256,
            expected_size=session_size,
            limit=MAX_SESSION_BYTES,
            label="source session",
        )
        copied: set[str] = set()
        for item in resolved:
            if item.sha256 in copied:
                continue
            _copy_exact_file(
                item.source_path,
                staging / OBJECTS_RELATIVE_DIR / item.sha256,
                expected_sha256=item.sha256,
                expected_size=item.byte_size,
                limit=MAX_OBJECT_BYTES,
                label="referenced source object",
            )
            copied.add(item.sha256)

        evidence_data = evidence.model_dump(mode="json")
        encoded_evidence = (
            json.dumps(
                evidence_data, indent=2, sort_keys=True, ensure_ascii=False
            ).encode("utf-8")
            + b"\n"
        )
        if len(encoded_evidence) > MAX_EVIDENCE_JSON_BYTES:
            raise AgentHarnessImportError("failed", "normalized evidence exceeds limit")
        evidence_path = staging / EVIDENCE_RELATIVE_PATH
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        evidence_path.write_bytes(encoded_evidence)
        evidence_sha256 = _sha256_bytes(encoded_evidence)

        result = _build_result(destination, evidence, evidence_sha256)
        from llmgauge.core.run_fingerprint import attach_run_fingerprint

        if attach_run_fingerprint(staging, result) is None:
            raise AgentHarnessImportError(
                "failed", "imported evidence fingerprint could not be created"
            )
        write_json(staging / "llmgauge-result.json", result)

        from llmgauge.core.result_validation import validate_result_dir

        errors = validate_result_dir(staging)
        if errors:
            raise AgentHarnessImportError(
                "failed", "staged imported evidence failed structural validation"
            )
        if destination.exists():
            raise AgentHarnessImportError(
                "failed", "destination appeared during import"
            )
        _rename_directory_no_replace(staging, destination)
    except Exception:
        if staging is not None:
            shutil.rmtree(staging, ignore_errors=True)
        raise
    finally:
        os.close(descriptor)
        try:
            lock_path.unlink()
        except OSError:
            pass
    return ImportOperationResult(
        outcome="completed",
        evidence_id=evidence.evidence_id,
        source_package_sha256=evidence.source_package_sha256,
        destination=destination,
    )


def _bounded_validation_error(exc: ValidationError) -> list[str]:
    errors: list[str] = []
    for item in exc.errors(include_input=False, include_context=False)[:20]:
        location = ".".join(str(part) for part in item.get("loc", ())) or "root"
        errors.append(
            f"agent_harness_evidence.{location}: {item.get('msg', 'invalid value')}"
        )
    if len(exc.errors()) > 20:
        errors.append("agent_harness_evidence has additional validation errors")
    return errors


def load_agent_harness_evidence(
    result_dir: Path, reference: Mapping[str, Any]
) -> AgentHarnessEvidence:
    try:
        parsed_reference = AgentHarnessEvidenceReference.model_validate(reference)
    except ValidationError as exc:
        raise ValueError("agent_harness_evidence reference is invalid") from exc
    from llmgauge.core.run_fingerprint import (
        FingerprintUnavailable,
        resolve_contained_result_artifact,
    )

    try:
        path = resolve_contained_result_artifact(
            result_dir,
            parsed_reference.path,
            label="agent_harness_evidence.path",
            require_file=True,
        )
    except FingerprintUnavailable as exc:
        raise ValueError(str(exc)) from None
    try:
        raw, evidence_sha256 = _read_bounded_regular_file(
            path,
            limit=MAX_EVIDENCE_JSON_BYTES,
            label="agent_harness_evidence",
        )
        data = _parse_json_object(raw)
        evidence = AgentHarnessEvidence.model_validate(data)
    except AgentHarnessImportError as exc:
        raise ValueError("agent_harness_evidence is unreadable or invalid") from exc
    except ValidationError as exc:
        raise ValueError("; ".join(_bounded_validation_error(exc))) from exc
    if evidence_sha256 != parsed_reference.sha256:
        raise ValueError("agent_harness_evidence file hash does not match reference")
    if evidence.evidence_id != parsed_reference.evidence_id:
        raise ValueError("agent_harness_evidence identity does not match reference")
    return evidence


def _validate_member_files(
    result_dir: Path, evidence: AgentHarnessEvidence
) -> tuple[list[str], dict[str, Path]]:
    from llmgauge.core.run_fingerprint import (
        FingerprintUnavailable,
        resolve_contained_result_artifact,
    )

    errors: list[str] = []
    paths: dict[str, Path] = {}
    for member in evidence.source_inventory:
        try:
            path = resolve_contained_result_artifact(
                result_dir,
                member.path,
                label=f"source member {member.member_id}",
                require_file=True,
            )
            digest, byte_size = _hash_regular_file(
                path,
                limit=(
                    MAX_SESSION_BYTES
                    if member.role == "session_log"
                    else MAX_OBJECT_BYTES
                ),
                label="contained source member",
            )
        except (FingerprintUnavailable, AgentHarnessImportError) as exc:
            errors.append(str(exc))
            continue
        paths[member.member_id] = path
        if digest != member.sha256:
            errors.append(f"source member {member.member_id} hash mismatch")
        if byte_size != member.byte_size:
            errors.append(f"source member {member.member_id} byte size mismatch")
    return errors, paths


def _expected_reference_projection(parsed: ParsedSession) -> list[dict[str, Any]]:
    return [
        {
            "reference_id": item.reference_id,
            "kind": item.kind,
            "source_entry_id": item.source_entry_id,
            "source_pointer": item.source_pointer,
            "source_object_id": item.source_object_id,
            "declared_sha256": item.declared_sha256,
        }
        for item in discover_source_references(parsed)
    ]


def _represented_reference_projection(
    references: list[SourceReference],
) -> list[dict[str, Any]]:
    return [
        {
            "reference_id": item.reference_id,
            "kind": item.kind,
            "source_entry_id": item.source_entry_id,
            "source_pointer": item.source_pointer,
            "source_object_id": item.source_object_id,
            "declared_sha256": item.declared_sha256,
        }
        for item in sorted(references, key=lambda item: item.reference_id)
    ]


def validate_agent_harness_result(
    result_dir: Path, result: Mapping[str, Any]
) -> list[str]:
    reference = result.get("agent_harness_evidence")
    if reference is None:
        return []
    errors: list[str] = []
    if not isinstance(reference, Mapping):
        return ["agent_harness_evidence must be an object"]
    try:
        parsed_reference = AgentHarnessEvidenceReference.model_validate(reference)
    except ValidationError as exc:
        return _bounded_validation_error(exc)
    try:
        evidence = load_agent_harness_evidence(result_dir, reference)
    except ValueError as exc:
        return [str(exc)]

    if result.get("schema_version") != "llmgauge.result.v0":
        errors.append("imported result schema_version must be llmgauge.result.v0")
    if result.get("llmgauge_version") != evidence.importer.version:
        errors.append(
            "imported result llmgauge_version must match the importer version"
        )
    if not isinstance(result.get("run_fingerprint"), Mapping):
        errors.append("imported Agent Harness evidence requires a run_fingerprint")
    if result.get("transcript") is not None:
        errors.append(
            "imported Agent Harness evidence cannot include a native transcript"
        )
    if result.get("external_benchmark_evidence") is not None:
        errors.append(
            "imported Agent Harness evidence cannot include external benchmark evidence"
        )
    results = result.get("results")
    if results != []:
        errors.append("imported Agent Harness evidence requires empty native results")
    if result.get("runtime") != {} or result.get("suite") != {}:
        errors.append(
            "imported Agent Harness evidence requires empty runtime and suite"
        )
    if result.get("model") != {"model_path": "redacted"}:
        errors.append(
            "imported Agent Harness evidence requires the redacted model sentinel"
        )
    if result.get("summary") != {"completed": 0, "failed": 0}:
        errors.append("imported Agent Harness evidence requires a zero native summary")
    run = result.get("run")
    if not isinstance(run, Mapping):
        errors.append("imported Agent Harness evidence requires run metadata")
    else:
        if run.get("operation") != "agent_harness_import":
            errors.append("imported result run.operation must be agent_harness_import")
        if run.get("status") != "completed":
            errors.append("imported result run.status must be completed")

    member_errors, member_paths = _validate_member_files(result_dir, evidence)
    errors.extend(member_errors)
    expected_package = source_package_sha256(evidence.source_inventory)
    if evidence.source_package_sha256 != expected_package:
        errors.append("source_package_sha256 does not match canonical inventory")
    if evidence.imported_session_id != imported_session_identity(evidence):
        errors.append("imported_session_id does not match canonical source identity")
    if evidence.evidence_id != evidence_identity(evidence):
        errors.append("evidence_id does not match canonical normalized evidence")

    member_by_id = {item.member_id: item for item in evidence.source_inventory}
    for source_reference in evidence.source_references:
        member = member_by_id.get(source_reference.member_id)
        if member is None or member.role != "source_object":
            errors.append(
                f"source reference {source_reference.reference_id} has no source object"
            )
            continue
        if (
            source_reference.declared_sha256 is not None
            and source_reference.declared_sha256 != member.sha256
        ):
            errors.append(
                f"source reference {source_reference.reference_id} digest disagrees"
            )

    session_member = next(
        (item for item in evidence.source_inventory if item.role == "session_log"), None
    )
    if session_member is None:
        return errors
    session_path = member_paths.get(session_member.member_id)
    if session_path is None:
        return errors
    try:
        parsed = parse_omp_v3_session(session_path)
        expected_references = _expected_reference_projection(parsed)
        represented_references = _represented_reference_projection(
            evidence.source_references
        )
        if expected_references != represented_references:
            errors.append("source reference mapping disagrees with canonical session")
        if evidence.source.session_id != parsed.header["id"]:
            errors.append("source session ID disagrees with canonical session")
        if evidence.source.started_at != _fact(
            parsed.header["timestamp"], source_entry_id="session"
        ):
            errors.append("source start time disagrees with canonical session")
        if evidence.source.workspace_path != _fact(
            parsed.header["cwd"], source_entry_id="session"
        ):
            errors.append("source workspace metadata disagrees with canonical session")
        terminal_record = _terminal_exit_record(parsed)
        expected_ended_at = (
            _fact(
                terminal_record.data["data"]["recordedAt"],
                source_entry_id=terminal_record.data["id"],
            )
            if terminal_record is not None
            else _fact(None, source_entry_id=None, missing="absent")
        )
        if evidence.source.ended_at != expected_ended_at:
            errors.append("source end time disagrees with canonical session")
        if evidence.trajectory != normalize_trajectory(parsed):
            errors.append("normalized trajectory disagrees with canonical session")
        if evidence.tool_lifecycles != normalize_tool_lifecycles(
            parsed, evidence.source_references
        ):
            errors.append("tool lifecycle mapping disagrees with canonical session")
        if evidence.model_observations != normalize_model_observations(parsed):
            errors.append("model observations disagree with canonical session")
        if evidence.task_identity != normalize_task_identity(parsed):
            errors.append("task identity disagrees with canonical session")
        expected_terminal = normalize_terminal(parsed)
        if evidence.terminal != expected_terminal:
            errors.append("source terminal mapping disagrees with canonical session")
        if evidence.source_session_outcome != expected_terminal.outcome:
            errors.append("source outcome disagrees with canonical session")
        if evidence.source_completeness != normalize_completeness(
            parsed, evidence.source_references
        ):
            errors.append("source completeness disagrees with canonical session")
        if evidence.repository_observations:
            errors.append(
                "generic OMP v3 does not provide repository observation authority"
            )
    except (
        AgentHarnessImportError,
        ValidationError,
        ValueError,
        RecursionError,
    ) as exc:
        errors.append(f"canonical session validation failed: {exc}")

    if parsed_reference.schema_version != evidence.schema_version:
        errors.append("result reference schema version disagrees with evidence")
    if parsed_reference.contract_version != evidence.contract_version:
        errors.append("result reference contract version disagrees with evidence")
    if parsed_reference.evidence_class != evidence.evidence_class:
        errors.append("result reference evidence class disagrees with evidence")
    return errors


def require_native_result(result: Mapping[str, Any], *, consumer: str) -> None:
    if result.get("agent_harness_evidence") is not None:
        raise ValueError(
            f"{consumer} does not support imported Agent Harness evidence; "
            "Agent Harness scoring and reporting are not implemented"
        )
    if result.get("external_benchmark_evidence") is not None:
        raise ValueError(
            f"{consumer} does not support imported external benchmark evidence; "
            "use `llmgauge benchmark report` for imported external-benchmark evidence"
        )
