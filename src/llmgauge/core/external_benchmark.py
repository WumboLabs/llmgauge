from __future__ import annotations

import ctypes
import errno
import hashlib
import json
import math
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

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from llmgauge import __version__
from llmgauge.core.artifacts import write_json

EVIDENCE_SCHEMA_VERSION = "llmgauge.external_benchmark_evidence.v0"
CONTRACT_VERSION = "0.1.0"
EVALUATION_CLASS = "external_text_benchmark"
SOURCE_TYPE = "lm_eval_harness_results"
SOURCE_FORMAT = "eleutherai.lm_eval.results_json"
IMPORTER_ID = "llmgauge.external_benchmark_importer"
EVIDENCE_RELATIVE_PATH = "external-benchmark/evidence.json"
SOURCE_RELATIVE_DIR = "external-benchmark/source"
OBJECTS_RELATIVE_DIR = "external-benchmark/source/objects/sha256"
REPORT_RELATIVE_PATH = "external-benchmark/report.md"
RESULT_OPERATION = "external_benchmark_import"

MAX_RESULTS_JSON_BYTES = 32 * 1024 * 1024
MAX_SOURCE_FILE_BYTES = 64 * 1024 * 1024
MAX_TOTAL_SOURCE_BYTES = 256 * 1024 * 1024
MAX_EVIDENCE_JSON_BYTES = 16 * 1024 * 1024
MAX_SOURCE_FILES = 256
MAX_DIRECTORY_ENTRIES = 4096
MAX_DIRECTORY_DEPTH = 4
MAX_TASKS = 512
MAX_GROUPS = 256
MAX_METRICS_PER_ITEM = 64
MAX_JSON_NESTING = 64
MAX_STRING_BYTES = 16 * 1024
MAX_ID_LENGTH = 192
_COPY_CHUNK_BYTES = 1024 * 1024

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_DIGEST_ID_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_TASK_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,191}$")
_HF_ID_RE = re.compile(r"^[^./][^/\s]{0,126}/[^/\s]{1,127}$")
_NON_METRIC_RESULT_KEYS = frozenset({"alias", "name", "sample_len"})

Availability = Literal[
    "available", "absent", "unknown", "unavailable", "redacted", "unsupported"
]
SourceMemberRole = Literal["results_json", "config", "log", "samples", "other_source"]
JsonScalar = str | int | float | bool
JsonValue = JsonScalar | list[Any] | dict[str, Any]


class ExternalBenchmarkImportError(ValueError):
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
    value: JsonValue | None = None

    @model_validator(mode="after")
    def validate_availability(self) -> SourceFact:
        if self.availability == "available":
            if self.value is None:
                raise ValueError("available fact requires a value")
            _require_bounded_json(self.value, "available fact")
        elif self.value is not None:
            raise ValueError("non-available fact cannot carry a value")
        return self


class ImporterIdentity(_ClosedModel):
    importer_id: Literal["llmgauge.external_benchmark_importer"]
    version: str = Field(min_length=1, max_length=64)
    imported_at: str = Field(min_length=1, max_length=64)


class SourceMember(_ClosedModel):
    member_id: str
    role: SourceMemberRole
    path: str
    sha256: str
    byte_count: int = Field(ge=0, le=MAX_TOTAL_SOURCE_BYTES)
    availability: Literal["available"]
    original_name: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def validate_member(self) -> SourceMember:
        _require_id(self.member_id, "source member ID")
        _require_sha256(self.sha256, "source member sha256")
        _require_contained_path(self.path, "source member path")
        if not self.path.startswith(f"{SOURCE_RELATIVE_DIR}/"):
            raise ValueError("source member path must stay under the source tree")
        if self.role == "results_json" and self.byte_count > MAX_RESULTS_JSON_BYTES:
            raise ValueError("results_json exceeds the results byte limit")
        if self.byte_count > MAX_SOURCE_FILE_BYTES:
            raise ValueError("source member exceeds the file byte limit")
        if self.original_name is not None and (
            "/" in self.original_name
            or "\\" in self.original_name
            or self.original_name in {".", ".."}
        ):
            raise ValueError("original_name must be a basename")
        return self


class NativeMetric(_ClosedModel):
    task_id: str
    metric_name: str = Field(min_length=1, max_length=MAX_ID_LENGTH)
    value: float
    stderr: SourceFact
    higher_is_better: SourceFact
    unit: SourceFact
    aggregation: SourceFact

    @model_validator(mode="after")
    def validate_metric(self) -> NativeMetric:
        _require_task_id(self.task_id, "metric task ID")
        if not math.isfinite(self.value):
            raise ValueError("metric value must be finite")
        if self.stderr.availability == "available":
            if not isinstance(self.stderr.value, int | float) or isinstance(
                self.stderr.value, bool
            ):
                raise ValueError("metric stderr must be numeric when available")
            if not math.isfinite(float(self.stderr.value)):
                raise ValueError("metric stderr must be finite")
        return self


class TaskEvidence(_ClosedModel):
    task_id: str
    n_shot: SourceFact
    n_samples: SourceFact
    dataset_path: SourceFact
    dataset_name: SourceFact
    dataset_config: SourceFact
    split: SourceFact
    revision: SourceFact
    output_type: SourceFact
    version: SourceFact
    fewshot_config: SourceFact
    generation_settings: SourceFact
    metrics: list[NativeMetric] = Field(min_length=1, max_length=MAX_METRICS_PER_ITEM)
    group_ids: list[str] = Field(default_factory=list, max_length=MAX_GROUPS)

    @model_validator(mode="after")
    def validate_task(self) -> TaskEvidence:
        _require_task_id(self.task_id, "task ID")
        for group_id in self.group_ids:
            _require_task_id(group_id, "group ID")
        _require_unique(self.group_ids, "task group IDs")
        metric_names = [item.metric_name for item in self.metrics]
        _require_unique(metric_names, "task metric names")
        if any(item.task_id != self.task_id for item in self.metrics):
            raise ValueError("task metrics must use the task ID")
        return self


class GroupAggregation(_ClosedModel):
    group_id: str
    subtask_ids: list[str] = Field(min_length=1, max_length=MAX_TASKS)
    metrics: list[NativeMetric] = Field(max_length=MAX_METRICS_PER_ITEM)

    @model_validator(mode="after")
    def validate_group(self) -> GroupAggregation:
        _require_task_id(self.group_id, "group ID")
        for task_id in self.subtask_ids:
            _require_task_id(task_id, "group subtask ID")
        _require_unique(self.subtask_ids, "group subtask IDs")
        metric_names = [item.metric_name for item in self.metrics]
        _require_unique(metric_names, "group metric names")
        if any(item.task_id != self.group_id for item in self.metrics):
            raise ValueError("group metrics must use the group ID")
        return self


class HarnessIdentity(_ClosedModel):
    family: Literal["lm_eval"]
    version: SourceFact
    git_hash: SourceFact
    transformers_version: SourceFact


class ModelIdentity(_ClosedModel):
    model_name: SourceFact
    model_source: SourceFact
    model_args: SourceFact
    hf_id: SourceFact


class RuntimeHardware(_ClosedModel):
    runtime: SourceFact
    device: SourceFact
    batch_size: SourceFact
    limit: SourceFact


class SeedRecord(_ClosedModel):
    random_seed: SourceFact
    numpy_random_seed: SourceFact
    torch_random_seed: SourceFact
    fewshot_random_seed: SourceFact


class ExternalBenchmarkEvidence(_ClosedModel):
    schema_version: Literal["llmgauge.external_benchmark_evidence.v0"]
    contract_version: Literal["0.1.0"]
    evaluation_class: Literal["external_text_benchmark"]
    source_type: Literal["lm_eval_harness_results"]
    source_format: Literal["eleutherai.lm_eval.results_json"]
    evidence_id: str
    source_package_sha256: str
    importer: ImporterIdentity
    harness: HarnessIdentity
    model: ModelIdentity
    runtime: RuntimeHardware
    seeds: SeedRecord
    tasks: list[TaskEvidence] = Field(min_length=1, max_length=MAX_TASKS)
    groups: list[GroupAggregation] = Field(default_factory=list, max_length=MAX_GROUPS)
    source_inventory: list[SourceMember] = Field(
        min_length=1, max_length=MAX_SOURCE_FILES
    )
    validation_outcome: Literal["passed"]
    scoreability: Literal["not_assessed"]
    publication_readiness: Literal["not_assessed"]

    @model_validator(mode="after")
    def validate_evidence(self) -> ExternalBenchmarkEvidence:
        _require_digest_id(self.evidence_id, "evidence_id")
        _require_sha256(self.source_package_sha256, "source_package_sha256")
        member_ids = [item.member_id for item in self.source_inventory]
        member_paths = [item.path for item in self.source_inventory]
        _require_unique(member_ids, "source member IDs")
        _require_unique(member_paths, "source member paths")
        if sum(item.role == "results_json" for item in self.source_inventory) != 1:
            raise ValueError("source inventory requires exactly one results_json")
        if (
            sum(item.byte_count for item in self.source_inventory)
            > MAX_TOTAL_SOURCE_BYTES
        ):
            raise ValueError("source inventory exceeds the total source byte limit")
        task_ids = [item.task_id for item in self.tasks]
        _require_unique(task_ids, "task IDs")
        group_ids = [item.group_id for item in self.groups]
        _require_unique(group_ids, "group IDs")
        overlap = set(task_ids) & set(group_ids)
        if overlap:
            raise ValueError("task and group identities must not collide")
        known_tasks = set(task_ids)
        known_groups = set(group_ids)
        for group in self.groups:
            missing = [
                item_id
                for item_id in group.subtask_ids
                if item_id not in known_tasks and item_id not in known_groups
            ]
            if missing:
                raise ValueError("group subtasks must name represented tasks or groups")
            if group.group_id in group.subtask_ids:
                raise ValueError("group cannot list itself as a subtask")
        _require_acyclic_groups(self.groups)
        return self


class ExternalBenchmarkEvidenceReference(_ClosedModel):
    schema_version: Literal["llmgauge.external_benchmark_evidence.v0"]
    contract_version: Literal["0.1.0"]
    evaluation_class: Literal["external_text_benchmark"]
    evidence_id: str
    path: Literal["external-benchmark/evidence.json"]
    sha256: str

    @model_validator(mode="after")
    def validate_reference(self) -> ExternalBenchmarkEvidenceReference:
        _require_digest_id(self.evidence_id, "external_benchmark_evidence.evidence_id")
        _require_sha256(self.sha256, "external_benchmark_evidence.sha256")
        return self


@dataclass(frozen=True)
class DiscoveredSourceFile:
    source_path: Path
    relative_posix: str
    role: SourceMemberRole
    original_name: str


@dataclass(frozen=True)
class CopiedSourceFile:
    discovered: DiscoveredSourceFile
    sha256: str
    byte_count: int
    contained_path: str


@dataclass(frozen=True)
class ParsedLmEval:
    results: dict[str, Any]
    groups: dict[str, Any]
    group_subtasks: dict[str, list[str]]
    configs: dict[str, Any]
    versions: dict[str, Any]
    n_shot: dict[str, Any]
    higher_is_better: dict[str, Any]
    n_samples: dict[str, Any]
    run_config: dict[str, Any]


@dataclass(frozen=True)
class ImportOperationResult:
    outcome: Literal["completed", "already_imported", "dry_run"]
    evidence_id: str
    source_package_sha256: str
    destination: Path


def _require_id(value: str, label: str) -> None:
    if not isinstance(value, str) or not _TASK_ID_RE.fullmatch(value):
        raise ValueError(f"{label} is malformed")


def _require_task_id(value: str, label: str) -> None:
    _require_id(value, label)


def _require_sha256(value: str, label: str) -> None:
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
        raise ValueError(f"{label} must be 64 lowercase hex characters")


def _require_digest_id(value: str, label: str) -> None:
    if not isinstance(value, str) or not _DIGEST_ID_RE.fullmatch(value):
        raise ValueError(f"{label} must be sha256:<64 lowercase hex>")


def _require_unique(values: list[str], label: str) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"{label} must be unique")


def _require_acyclic_groups(groups: list[GroupAggregation]) -> None:
    children = {item.group_id: list(item.subtask_ids) for item in groups}
    known_groups = set(children)
    visiting: set[str] = set()
    visited: set[str] = set()

    def walk(group_id: str) -> None:
        if group_id in visited:
            return
        if group_id in visiting:
            raise ValueError("group membership must be acyclic")
        visiting.add(group_id)
        for child_id in children.get(group_id, ()):
            if child_id in known_groups:
                walk(child_id)
        visiting.remove(group_id)
        visited.add(group_id)

    for group_id in children:
        walk(group_id)


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


def _require_bounded_json(value: Any, label: str, *, depth: int = 0) -> None:
    if depth > MAX_JSON_NESTING:
        raise ValueError(f"{label} exceeds JSON nesting limit")
    if value is None or isinstance(value, bool):
        return
    if isinstance(value, str):
        if len(value.encode("utf-8")) > MAX_STRING_BYTES:
            raise ValueError(f"{label} exceeds string byte limit")
        return
    if isinstance(value, int) and not isinstance(value, bool):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{label} must be finite")
        return
    if isinstance(value, list):
        if len(value) > MAX_TASKS:
            raise ValueError(f"{label} exceeds list limit")
        for index, item in enumerate(value):
            _require_bounded_json(item, f"{label}[{index}]", depth=depth + 1)
        return
    if isinstance(value, dict):
        if len(value) > MAX_TASKS:
            raise ValueError(f"{label} exceeds object size limit")
        for key, item in value.items():
            if not isinstance(key, str) or not key or len(key) > MAX_ID_LENGTH:
                raise ValueError(f"{label} has a malformed object key")
            _require_bounded_json(item, f"{label}.{key}", depth=depth + 1)
        return
    raise ValueError(f"{label} has an unsupported JSON type")


def _json_object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result


def _validate_json_nesting(value: Any, *, depth: int = 0) -> None:
    if depth > MAX_JSON_NESTING:
        raise ExternalBenchmarkImportError(
            "malformed_source", "source JSON nesting exceeds limit"
        )
    if isinstance(value, dict):
        for child in value.values():
            _validate_json_nesting(child, depth=depth + 1)
        return
    if isinstance(value, list):
        for child in value:
            _validate_json_nesting(child, depth=depth + 1)


def _parse_json_object(raw: bytes, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_json_object_pairs,
            parse_constant=lambda item: (_ for _ in ()).throw(
                ValueError(f"non-finite JSON number: {item}")
            ),
        )
    except ValueError as exc:
        message = str(exc)
        if "non-finite JSON number" in message:
            raise ExternalBenchmarkImportError(
                "malformed_source", f"{label} contains a malformed non-finite metric"
            ) from exc
        raise ExternalBenchmarkImportError(
            "malformed_source", f"{label} is not valid JSON"
        ) from exc
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        RecursionError,
        OverflowError,
    ) as exc:
        raise ExternalBenchmarkImportError(
            "malformed_source", f"{label} is not valid JSON"
        ) from exc
    if not isinstance(value, dict):
        raise ExternalBenchmarkImportError(
            "malformed_source", f"{label} must be a JSON object"
        )
    _validate_json_nesting(value)
    return value


def _regular_file_stat(path: Path, *, label: str) -> os.stat_result:
    try:
        value = path.lstat()
    except OSError as exc:
        raise ExternalBenchmarkImportError("failed", f"{label} is unavailable") from exc
    if stat.S_ISLNK(value.st_mode) or not stat.S_ISREG(value.st_mode):
        raise ExternalBenchmarkImportError("failed", f"{label} must be a regular file")
    return value


def _stat_identity(value: os.stat_result) -> tuple[int, int, int, int]:
    return (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns)


def _open_regular_file(path: Path, *, label: str) -> tuple[int, os.stat_result]:
    before = _regular_file_stat(path, label=label)
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise ExternalBenchmarkImportError("failed", f"{label} is unreadable") from exc
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode) or _stat_identity(before) != _stat_identity(
            opened
        ):
            raise ExternalBenchmarkImportError(
                "failed", f"{label} changed before it was opened"
            )
    except Exception:
        os.close(descriptor)
        raise
    return descriptor, before


def _hash_regular_file(path: Path, *, limit: int, label: str) -> tuple[str, int]:
    descriptor, before = _open_regular_file(path, label=label)
    if before.st_size > limit:
        os.close(descriptor)
        raise ExternalBenchmarkImportError("failed", f"{label} exceeds byte limit")
    digest = hashlib.sha256()
    remaining = before.st_size
    try:
        with os.fdopen(descriptor, "rb") as handle:
            while remaining:
                chunk = handle.read(min(_COPY_CHUNK_BYTES, remaining))
                if not chunk:
                    raise ExternalBenchmarkImportError(
                        "failed", f"{label} changed while reading"
                    )
                digest.update(chunk)
                remaining -= len(chunk)
            after = os.fstat(handle.fileno())
            path_after = _regular_file_stat(path, label=label)
            if _stat_identity(after) != _stat_identity(before) or _stat_identity(
                path_after
            ) != _stat_identity(before):
                raise ExternalBenchmarkImportError(
                    "failed", f"{label} changed while reading"
                )
    except ExternalBenchmarkImportError:
        raise
    except OSError as exc:
        raise ExternalBenchmarkImportError("failed", f"{label} is unreadable") from exc
    return digest.hexdigest(), before.st_size


def _read_bounded_regular_file(path: Path, *, limit: int, label: str) -> bytes:
    descriptor, before = _open_regular_file(path, label=label)
    if before.st_size > limit:
        os.close(descriptor)
        raise ExternalBenchmarkImportError("failed", f"{label} exceeds byte limit")
    try:
        with os.fdopen(descriptor, "rb") as handle:
            payload = handle.read(limit + 1)
            if len(payload) != before.st_size:
                raise ExternalBenchmarkImportError(
                    "failed", f"{label} changed while reading"
                )
            return payload
    except ExternalBenchmarkImportError:
        raise
    except OSError as exc:
        raise ExternalBenchmarkImportError("failed", f"{label} is unreadable") from exc


def _copy_exact_file(
    source: Path,
    destination: Path,
    *,
    expected_sha256: str,
    expected_size: int,
    limit: int,
    label: str,
) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    digest, byte_count = _hash_regular_file(source, limit=limit, label=label)
    if digest != expected_sha256 or byte_count != expected_size:
        raise ExternalBenchmarkImportError("failed", f"{label} changed during import")
    descriptor, before = _open_regular_file(source, label=label)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    try:
        out_fd = os.open(destination, flags, 0o600)
    except OSError as exc:
        os.close(descriptor)
        raise ExternalBenchmarkImportError(
            "failed", f"{label} could not be copied"
        ) from exc
    copied = 0
    hasher = hashlib.sha256()
    try:
        with os.fdopen(descriptor, "rb") as reader, os.fdopen(out_fd, "wb") as writer:
            while chunk := reader.read(_COPY_CHUNK_BYTES):
                copied += len(chunk)
                if copied > limit:
                    raise ExternalBenchmarkImportError(
                        "failed", f"{label} exceeds byte limit"
                    )
                writer.write(chunk)
                hasher.update(chunk)
    except ExternalBenchmarkImportError:
        destination.unlink(missing_ok=True)
        raise
    except OSError as exc:
        destination.unlink(missing_ok=True)
        raise ExternalBenchmarkImportError(
            "failed", f"{label} could not be copied"
        ) from exc
    if hasher.hexdigest() != expected_sha256 or copied != expected_size:
        destination.unlink(missing_ok=True)
        raise ExternalBenchmarkImportError("failed", f"{label} changed during import")
    if _stat_identity(_regular_file_stat(source, label=label)) != _stat_identity(
        before
    ):
        destination.unlink(missing_ok=True)
        raise ExternalBenchmarkImportError("failed", f"{label} changed during import")


def _safe_relative_posix(path: Path, root: Path) -> str:
    try:
        relative = path.resolve(strict=False).relative_to(root.resolve(strict=False))
    except ValueError as exc:
        raise ExternalBenchmarkImportError(
            "failed", "source path escapes the admitted source tree"
        ) from exc
    posix = relative.as_posix()
    _require_contained_path(posix, "source relative path")
    return posix


def _classify_source_role(relative_posix: str) -> SourceMemberRole:
    name = PurePosixPath(relative_posix).name.lower()
    if name == "results.json" or name.startswith("results_"):
        return "results_json"
    if "sample" in name:
        return "samples"
    if name.endswith(".log") or "log" in name:
        return "log"
    if "config" in name:
        return "config"
    return "other_source"


def _looks_like_llmgauge_result(data: Mapping[str, Any]) -> bool:
    schema = data.get("schema_version")
    return isinstance(schema, str) and schema.startswith("llmgauge.")


def _looks_like_shard_trace(data: Mapping[str, Any]) -> bool:
    if "question_id" in data or "shard_id" in data:
        return True
    results = data.get("results")
    if isinstance(results, list):
        return True
    return False


def _mapping_or_empty(value: Any, *, label: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ExternalBenchmarkImportError(
            "malformed_source", f"{label} must be an object when present"
        )
    return value


def parse_lm_eval_results(data: Mapping[str, Any]) -> ParsedLmEval:
    if _looks_like_llmgauge_result(data):
        raise ExternalBenchmarkImportError(
            "unsupported_source",
            "source is an LLMGauge artifact, not lm-eval harness results",
        )
    if _looks_like_shard_trace(data):
        raise ExternalBenchmarkImportError(
            "unsupported_source",
            "source is not lm_eval_harness_results",
        )
    results = data.get("results")
    if not isinstance(results, dict) or not results:
        raise ExternalBenchmarkImportError(
            "malformed_source", "source results object is missing or empty"
        )
    if len(results) > MAX_TASKS:
        raise ExternalBenchmarkImportError(
            "malformed_source", "source declares too many tasks"
        )
    for task_id, payload in results.items():
        if not isinstance(task_id, str) or not _TASK_ID_RE.fullmatch(task_id):
            raise ExternalBenchmarkImportError(
                "malformed_source", "source task identity is malformed"
            )
        if not isinstance(payload, dict) or not payload:
            raise ExternalBenchmarkImportError(
                "malformed_source", "source task result must be a non-empty object"
            )
    groups = _mapping_or_empty(data.get("groups"), label="groups")
    if len(groups) > MAX_GROUPS:
        raise ExternalBenchmarkImportError(
            "malformed_source", "source declares too many groups"
        )
    raw_subtasks = _mapping_or_empty(data.get("group_subtasks"), label="group_subtasks")
    group_subtasks: dict[str, list[str]] = {}
    for group_id, subtasks in raw_subtasks.items():
        if not isinstance(group_id, str) or not _TASK_ID_RE.fullmatch(group_id):
            raise ExternalBenchmarkImportError(
                "malformed_source", "source group identity is malformed"
            )
        if not isinstance(subtasks, list) or not subtasks:
            raise ExternalBenchmarkImportError(
                "malformed_source", "source group subtasks must be a non-empty list"
            )
        parsed_subtasks: list[str] = []
        for item in subtasks:
            if not isinstance(item, str) or not _TASK_ID_RE.fullmatch(item):
                raise ExternalBenchmarkImportError(
                    "malformed_source", "source group subtask identity is malformed"
                )
            parsed_subtasks.append(item)
        if len(parsed_subtasks) != len(set(parsed_subtasks)):
            raise ExternalBenchmarkImportError(
                "malformed_source", "source group subtasks must be unique"
            )
        group_subtasks[group_id] = parsed_subtasks
    return ParsedLmEval(
        results=dict(results),
        groups=groups,
        group_subtasks=group_subtasks,
        configs=_mapping_or_empty(data.get("configs"), label="configs"),
        versions=_mapping_or_empty(data.get("versions"), label="versions"),
        n_shot=_mapping_or_empty(
            data.get("n-shot", data.get("n_shot")), label="n-shot"
        ),
        higher_is_better=_mapping_or_empty(
            data.get("higher_is_better"), label="higher_is_better"
        ),
        n_samples=_mapping_or_empty(
            data.get("n-samples", data.get("n_samples")), label="n-samples"
        ),
        run_config=_mapping_or_empty(data.get("config"), label="config"),
    )


def _fact(value: Any, *, missing: Availability = "absent") -> SourceFact:
    if value is None:
        return SourceFact(availability=missing, value=None)
    return SourceFact(availability="available", value=value)


def _optional_mapping_fact(container: Mapping[str, Any], key: str) -> SourceFact:
    if key not in container:
        return _fact(None, missing="absent")
    return _fact(container.get(key))


def _numeric_metric_value(value: Any, *, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ExternalBenchmarkImportError(
            "malformed_source", f"{label} is not a numeric metric"
        )
    number = float(value)
    if not math.isfinite(number):
        raise ExternalBenchmarkImportError(
            "malformed_source", f"{label} is not a finite metric"
        )
    return number


def _stderr_key(metric_name: str) -> str:
    if "," in metric_name:
        name, filter_name = metric_name.split(",", 1)
        return f"{name}_stderr,{filter_name}"
    return f"{metric_name}_stderr"


def _metric_direction(
    parsed: ParsedLmEval, item_id: str, metric_name: str
) -> SourceFact:
    directions = parsed.higher_is_better.get(item_id)
    if not isinstance(directions, dict):
        return _fact(None, missing="absent")
    raw_name = metric_name.split(",", 1)[0]
    if raw_name not in directions and metric_name not in directions:
        return _fact(None, missing="absent")
    value = directions.get(raw_name, directions.get(metric_name))
    if not isinstance(value, bool):
        raise ExternalBenchmarkImportError(
            "malformed_source", "higher_is_better values must be booleans"
        )
    return _fact(value)


def _metric_aggregation(
    parsed: ParsedLmEval, item_id: str, metric_name: str
) -> SourceFact:
    config = parsed.configs.get(item_id)
    if not isinstance(config, dict):
        return _fact(None, missing="absent")
    metric_list = config.get("metric_list")
    if metric_list is None:
        return _fact(None, missing="absent")
    if not isinstance(metric_list, list):
        raise ExternalBenchmarkImportError(
            "malformed_source", "metric_list must be a list when present"
        )
    raw_name = metric_name.split(",", 1)[0]
    matches: list[Any] = []
    for item in metric_list:
        if not isinstance(item, dict):
            continue
        declared = item.get("metric")
        if declared in {raw_name, metric_name}:
            matches.append(item.get("aggregation"))
    if not matches:
        return _fact(None, missing="absent")
    if len(set(map(repr, matches))) != 1:
        raise ExternalBenchmarkImportError(
            "malformed_source", "metric aggregation identities conflict"
        )
    aggregation = matches[0]
    if aggregation is None:
        return _fact(None, missing="absent")
    if not isinstance(aggregation, str) or not aggregation:
        raise ExternalBenchmarkImportError(
            "malformed_source", "metric aggregation must be a string when present"
        )
    return _fact(aggregation)


def _extract_metrics(
    parsed: ParsedLmEval, item_id: str, payload: Mapping[str, Any]
) -> list[NativeMetric]:
    numeric: dict[str, float] = {}
    for key, value in payload.items():
        if key in _NON_METRIC_RESULT_KEYS:
            continue
        if not isinstance(key, str) or not key:
            raise ExternalBenchmarkImportError(
                "malformed_source", "metric name is malformed"
            )
        if isinstance(value, str):
            continue
        numeric[key] = _numeric_metric_value(value, label=f"{item_id}.{key}")
    metric_names = [name for name in numeric if not _is_stderr_name(name)]
    if not metric_names:
        raise ExternalBenchmarkImportError(
            "malformed_source", f"{item_id} has no native numeric metrics"
        )
    if len(metric_names) > MAX_METRICS_PER_ITEM:
        raise ExternalBenchmarkImportError(
            "malformed_source", f"{item_id} declares too many metrics"
        )
    metrics: list[NativeMetric] = []
    consumed_stderr: set[str] = set()
    for name in sorted(metric_names):
        stderr_name = _stderr_key(name)
        if stderr_name in numeric:
            stderr = _fact(numeric[stderr_name])
            consumed_stderr.add(stderr_name)
        else:
            stderr = _fact(None, missing="absent")
        metrics.append(
            NativeMetric(
                task_id=item_id,
                metric_name=name,
                value=numeric[name],
                stderr=stderr,
                higher_is_better=_metric_direction(parsed, item_id, name),
                unit=_fact(None, missing="absent"),
                aggregation=_metric_aggregation(parsed, item_id, name),
            )
        )
    leftover = [
        name
        for name in numeric
        if _is_stderr_name(name) and name not in consumed_stderr
    ]
    for name in sorted(leftover):
        metrics.append(
            NativeMetric(
                task_id=item_id,
                metric_name=name,
                value=numeric[name],
                stderr=_fact(None, missing="absent"),
                higher_is_better=_fact(None, missing="absent"),
                unit=_fact(None, missing="absent"),
                aggregation=_fact(None, missing="absent"),
            )
        )
    return metrics


def _is_stderr_name(name: str) -> bool:
    if name.endswith("_stderr"):
        return True
    head, _sep, _tail = name.partition(",")
    return head.endswith("_stderr")


def _n_samples_fact(parsed: ParsedLmEval, item_id: str) -> SourceFact:
    if item_id not in parsed.n_samples:
        return _fact(None, missing="absent")
    value = parsed.n_samples[item_id]
    if isinstance(value, dict):
        allowed = {"original", "effective"}
        if not set(value) <= allowed or not value:
            raise ExternalBenchmarkImportError(
                "malformed_source", "n-samples object has an unsupported shape"
            )
        for key, count in value.items():
            if not isinstance(count, int) or isinstance(count, bool) or count < 0:
                raise ExternalBenchmarkImportError(
                    "malformed_source",
                    f"n-samples.{key} must be a non-negative integer",
                )
        return _fact(value)
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return _fact(value)
    raise ExternalBenchmarkImportError(
        "malformed_source", "n-samples value is malformed"
    )


def _dataset_facts(config: Mapping[str, Any] | None) -> dict[str, SourceFact]:
    if config is None:
        missing = _fact(None, missing="absent")
        return {
            "dataset_path": missing,
            "dataset_name": missing,
            "dataset_config": missing,
            "split": missing,
            "revision": missing,
            "output_type": missing,
            "fewshot_config": missing,
            "generation_settings": missing,
        }
    split = None
    for key in ("test_split", "validation_split", "training_split"):
        if isinstance(config.get(key), str) and config.get(key):
            split = config[key]
            break
    dataset_kwargs = config.get("dataset_kwargs")
    revision = None
    if isinstance(dataset_kwargs, dict) and "revision" in dataset_kwargs:
        revision = dataset_kwargs.get("revision")
    fewshot = None
    if "num_fewshot" in config or "fewshot_split" in config:
        fewshot = {
            key: config[key]
            for key in ("num_fewshot", "fewshot_split")
            if key in config
        }
    generation = config.get("generation_kwargs")
    return {
        "dataset_path": _optional_mapping_fact(config, "dataset_path"),
        "dataset_name": _optional_mapping_fact(config, "dataset_name"),
        "dataset_config": _optional_mapping_fact(config, "dataset_config"),
        "split": _fact(split) if split is not None else _fact(None, missing="absent"),
        "revision": _fact(revision)
        if revision is not None
        else _fact(None, missing="absent"),
        "output_type": _optional_mapping_fact(config, "output_type"),
        "fewshot_config": _fact(fewshot)
        if fewshot is not None
        else _fact(None, missing="absent"),
        "generation_settings": _fact(generation)
        if generation is not None
        else _fact(None, missing="absent"),
    }


def _task_group_ids(parsed: ParsedLmEval, task_id: str) -> list[str]:
    group_ids = [
        group_id
        for group_id, subtasks in parsed.group_subtasks.items()
        if task_id in subtasks
    ]
    return sorted(group_ids)


def _select_task_ids(parsed: ParsedLmEval) -> list[str]:
    group_ids = set(parsed.group_subtasks)
    group_ids.update(parsed.groups)
    task_ids = [task_id for task_id in parsed.results if task_id not in group_ids]
    if not task_ids:
        raise ExternalBenchmarkImportError(
            "malformed_source", "source results contain no task-level metrics"
        )
    return sorted(task_ids)


def _build_tasks(parsed: ParsedLmEval) -> list[TaskEvidence]:
    tasks: list[TaskEvidence] = []
    for task_id in _select_task_ids(parsed):
        config = parsed.configs.get(task_id)
        if config is not None and not isinstance(config, dict):
            raise ExternalBenchmarkImportError(
                "malformed_source", "task config must be an object when present"
            )
        dataset = _dataset_facts(config if isinstance(config, dict) else None)
        n_shot_value = parsed.n_shot.get(task_id)
        if n_shot_value is None and isinstance(config, dict):
            n_shot_value = config.get("num_fewshot")
        version = parsed.versions.get(task_id)
        if version is None and isinstance(config, dict):
            metadata = config.get("metadata")
            if isinstance(metadata, dict):
                version = metadata.get("version")
        tasks.append(
            TaskEvidence(
                task_id=task_id,
                n_shot=_fact(n_shot_value)
                if n_shot_value is not None
                else _fact(None, missing="absent"),
                n_samples=_n_samples_fact(parsed, task_id),
                version=_fact(version)
                if version is not None
                else _fact(None, missing="absent"),
                metrics=_extract_metrics(parsed, task_id, parsed.results[task_id]),
                group_ids=_task_group_ids(parsed, task_id),
                **dataset,
            )
        )
    return tasks


def _build_groups(
    parsed: ParsedLmEval, tasks: list[TaskEvidence]
) -> list[GroupAggregation]:
    known_tasks = {item.task_id for item in tasks}
    groups: list[GroupAggregation] = []
    group_ids = sorted(set(parsed.groups) | set(parsed.group_subtasks))
    known_groups = set(group_ids)
    for group_id in group_ids:
        subtasks = parsed.group_subtasks.get(group_id)
        if subtasks is None:
            raise ExternalBenchmarkImportError(
                "malformed_source", "group is missing subtask membership"
            )
        missing = [
            item_id
            for item_id in subtasks
            if item_id not in known_tasks and item_id not in known_groups
        ]
        if missing:
            raise ExternalBenchmarkImportError(
                "malformed_source",
                "group subtasks are not represented as tasks or groups",
            )
        if group_id in subtasks:
            raise ExternalBenchmarkImportError(
                "malformed_source", "group cannot list itself as a subtask"
            )
        payload = parsed.groups.get(group_id)
        metrics: list[NativeMetric] = []
        if payload is not None:
            if not isinstance(payload, dict):
                raise ExternalBenchmarkImportError(
                    "malformed_source", "group result must be an object when present"
                )
            metrics = _extract_metrics(parsed, group_id, payload)
        groups.append(
            GroupAggregation(
                group_id=group_id,
                subtask_ids=list(subtasks),
                metrics=metrics,
            )
        )
    try:
        _require_acyclic_groups(groups)
    except ValueError as exc:
        raise ExternalBenchmarkImportError("malformed_source", str(exc)) from exc
    return groups


def _hf_id_fact(model_name: Any, model_source: Any) -> SourceFact:
    if not isinstance(model_name, str) or not model_name:
        return _fact(None, missing="absent")
    if any(sep in model_name for sep in ("\\", ":", " ")):
        return _fact(None, missing="absent")
    if model_name.startswith(("/", ".", "~")):
        return _fact(None, missing="absent")
    if not _HF_ID_RE.fullmatch(model_name):
        return _fact(None, missing="absent")
    if (
        isinstance(model_source, str)
        and model_source
        and model_source not in {"hf", "huggingface"}
    ):
        return _fact(None, missing="absent")
    return _fact(model_name)


def _build_model(parsed: ParsedLmEval, root: Mapping[str, Any]) -> ModelIdentity:
    model_name = root.get("model_name")
    if model_name is None:
        model_name = parsed.run_config.get("model_args")
    model_source = root.get("model_source", parsed.run_config.get("model"))
    model_args = parsed.run_config.get("model_args")
    return ModelIdentity(
        model_name=_fact(model_name)
        if model_name is not None
        else _fact(None, missing="absent"),
        model_source=_fact(model_source)
        if model_source is not None
        else _fact(None, missing="absent"),
        model_args=_fact(model_args)
        if model_args is not None
        else _fact(None, missing="absent"),
        hf_id=_hf_id_fact(root.get("model_name"), model_source),
    )


def _build_runtime(parsed: ParsedLmEval) -> RuntimeHardware:
    return RuntimeHardware(
        runtime=_optional_mapping_fact(parsed.run_config, "model"),
        device=_optional_mapping_fact(parsed.run_config, "device"),
        batch_size=_optional_mapping_fact(parsed.run_config, "batch_size"),
        limit=_optional_mapping_fact(parsed.run_config, "limit"),
    )


def _build_seeds(parsed: ParsedLmEval) -> SeedRecord:
    return SeedRecord(
        random_seed=_optional_mapping_fact(parsed.run_config, "random_seed"),
        numpy_random_seed=_optional_mapping_fact(
            parsed.run_config, "numpy_random_seed"
        ),
        torch_random_seed=_optional_mapping_fact(
            parsed.run_config, "torch_random_seed"
        ),
        fewshot_random_seed=_optional_mapping_fact(
            parsed.run_config, "fewshot_random_seed"
        ),
    )


def _build_harness(root: Mapping[str, Any]) -> HarnessIdentity:
    return HarnessIdentity(
        family="lm_eval",
        version=_fact(root["lm_eval_version"])
        if "lm_eval_version" in root
        else _fact(None, missing="absent"),
        git_hash=_fact(root["git_hash"])
        if "git_hash" in root
        else _fact(None, missing="absent"),
        transformers_version=_fact(root["transformers_version"])
        if "transformers_version" in root
        else _fact(None, missing="absent"),
    )


def source_package_projection(inventory: list[SourceMember]) -> list[dict[str, Any]]:
    return sorted(
        [
            {
                "byte_count": item.byte_count,
                "path": item.path,
                "role": item.role,
                "sha256": item.sha256,
            }
            for item in inventory
        ],
        key=lambda item: item["path"],
    )


def source_package_sha256(inventory: list[SourceMember]) -> str:
    return _sha256_bytes(_canonical_json_bytes(source_package_projection(inventory)))


def immutable_metric_projection(metric: NativeMetric) -> dict[str, Any]:
    return {
        "aggregation": metric.aggregation.model_dump(mode="json"),
        "higher_is_better": metric.higher_is_better.model_dump(mode="json"),
        "metric_name": metric.metric_name,
        "stderr": metric.stderr.model_dump(mode="json"),
        "task_id": metric.task_id,
        "unit": metric.unit.model_dump(mode="json"),
        "value": metric.value,
    }


def immutable_identity_projection(
    evidence: ExternalBenchmarkEvidence,
) -> dict[str, Any]:
    return {
        "evaluation_class": evidence.evaluation_class,
        "groups": [
            {
                "group_id": group.group_id,
                "metrics": [
                    immutable_metric_projection(item) for item in group.metrics
                ],
                "subtask_ids": list(group.subtask_ids),
            }
            for group in sorted(evidence.groups, key=lambda item: item.group_id)
        ],
        "harness": evidence.harness.model_dump(mode="json"),
        "model": evidence.model.model_dump(mode="json"),
        "runtime": evidence.runtime.model_dump(mode="json"),
        "seeds": evidence.seeds.model_dump(mode="json"),
        "source_format": evidence.source_format,
        "source_type": evidence.source_type,
        "tasks": [
            {
                "dataset_config": task.dataset_config.model_dump(mode="json"),
                "dataset_name": task.dataset_name.model_dump(mode="json"),
                "dataset_path": task.dataset_path.model_dump(mode="json"),
                "fewshot_config": task.fewshot_config.model_dump(mode="json"),
                "generation_settings": task.generation_settings.model_dump(mode="json"),
                "group_ids": list(task.group_ids),
                "metrics": [immutable_metric_projection(item) for item in task.metrics],
                "n_samples": task.n_samples.model_dump(mode="json"),
                "n_shot": task.n_shot.model_dump(mode="json"),
                "output_type": task.output_type.model_dump(mode="json"),
                "revision": task.revision.model_dump(mode="json"),
                "split": task.split.model_dump(mode="json"),
                "task_id": task.task_id,
                "version": task.version.model_dump(mode="json"),
            }
            for task in sorted(evidence.tasks, key=lambda item: item.task_id)
        ],
    }


def evidence_identity(evidence: ExternalBenchmarkEvidence) -> str:
    projection = {
        "contract_version": evidence.contract_version,
        "evaluation_class": evidence.evaluation_class,
        "immutable_identity": immutable_identity_projection(evidence),
        "importer_id": evidence.importer.importer_id,
        "schema_version": evidence.schema_version,
        "source_package_sha256": evidence.source_package_sha256,
        "source_type": evidence.source_type,
    }
    return "sha256:" + _sha256_bytes(_canonical_json_bytes(projection))


def immutable_external_benchmark_payload(
    evidence: ExternalBenchmarkEvidence,
) -> dict[str, Any]:
    return {
        "contract_version": evidence.contract_version,
        "evaluation_class": evidence.evaluation_class,
        "evidence_id": evidence.evidence_id,
        "immutable_identity": immutable_identity_projection(evidence),
        "importer_id": evidence.importer.importer_id,
        "importer_version": evidence.importer.version,
        "schema_version": evidence.schema_version,
        "source_members": source_package_projection(evidence.source_inventory),
        "source_package_sha256": evidence.source_package_sha256,
        "source_type": evidence.source_type,
    }


def _member_id_for(path: str) -> str:
    encoded = path.replace("/", ":")
    if len(encoded) <= MAX_ID_LENGTH and _TASK_ID_RE.fullmatch(encoded):
        return encoded
    return "src:" + _sha256_bytes(path.encode("utf-8"))


def _build_inventory(copied: list[CopiedSourceFile]) -> list[SourceMember]:
    inventory = []
    for item in sorted(copied, key=lambda value: value.contained_path):
        inventory.append(
            SourceMember(
                member_id=_member_id_for(item.contained_path),
                role=item.discovered.role,
                path=item.contained_path,
                sha256=item.sha256,
                byte_count=item.byte_count,
                availability="available",
                original_name=item.discovered.original_name,
            )
        )
    return inventory


def build_external_benchmark_evidence(
    root: Mapping[str, Any],
    copied: list[CopiedSourceFile],
    *,
    imported_at: str,
) -> ExternalBenchmarkEvidence:
    parsed = parse_lm_eval_results(root)
    tasks = _build_tasks(parsed)
    groups = _build_groups(parsed, tasks)
    inventory = _build_inventory(copied)
    draft = ExternalBenchmarkEvidence(
        schema_version=EVIDENCE_SCHEMA_VERSION,
        contract_version=CONTRACT_VERSION,
        evaluation_class=EVALUATION_CLASS,
        source_type=SOURCE_TYPE,
        source_format=SOURCE_FORMAT,
        evidence_id="sha256:" + "0" * 64,
        source_package_sha256=source_package_sha256(inventory),
        importer=ImporterIdentity(
            importer_id=IMPORTER_ID,
            version=__version__,
            imported_at=imported_at,
        ),
        harness=_build_harness(root),
        model=_build_model(parsed, root),
        runtime=_build_runtime(parsed),
        seeds=_build_seeds(parsed),
        tasks=tasks,
        groups=groups,
        source_inventory=inventory,
        validation_outcome="passed",
        scoreability="not_assessed",
        publication_readiness="not_assessed",
    )
    draft.evidence_id = evidence_identity(draft)
    return ExternalBenchmarkEvidence.model_validate(draft.model_dump(mode="json"))


def _discover_directory_files(root: Path) -> list[DiscoveredSourceFile]:
    files: list[DiscoveredSourceFile] = []
    seen = 0
    for current, dirnames, filenames in os.walk(root, followlinks=False):
        current_path = Path(current)
        relative_dir = (
            "" if current_path == root else _safe_relative_posix(current_path, root)
        )
        depth = 0 if relative_dir == "" else len(PurePosixPath(relative_dir).parts)
        if depth > MAX_DIRECTORY_DEPTH:
            raise ExternalBenchmarkImportError(
                "failed", "source directory nesting exceeds limit"
            )
        seen += len(dirnames) + len(filenames)
        if seen > MAX_DIRECTORY_ENTRIES:
            raise ExternalBenchmarkImportError(
                "failed", "source directory has too many entries"
            )
        for name in sorted(filenames):
            path = current_path / name
            try:
                info = path.lstat()
            except OSError as exc:
                raise ExternalBenchmarkImportError(
                    "failed", "source member is unavailable"
                ) from exc
            if stat.S_ISLNK(info.st_mode):
                raise ExternalBenchmarkImportError(
                    "failed", "source tree must not contain symlinks"
                )
            if not stat.S_ISREG(info.st_mode):
                continue
            relative = _safe_relative_posix(path, root)
            files.append(
                DiscoveredSourceFile(
                    source_path=path,
                    relative_posix=relative,
                    role=_classify_source_role(relative),
                    original_name=name,
                )
            )
    if not files:
        raise ExternalBenchmarkImportError(
            "unsupported_source", "source directory contains no regular files"
        )
    if len(files) > MAX_SOURCE_FILES:
        raise ExternalBenchmarkImportError(
            "failed", "source directory exceeds the admitted file count"
        )
    return files


def _choose_primary_results(
    files: list[DiscoveredSourceFile],
) -> DiscoveredSourceFile:
    candidates = [item for item in files if item.role == "results_json"]
    if not candidates:
        json_files = [
            item for item in files if item.original_name.lower().endswith(".json")
        ]
        if len(json_files) == 1:
            chosen = json_files[0]
            return DiscoveredSourceFile(
                source_path=chosen.source_path,
                relative_posix=chosen.relative_posix,
                role="results_json",
                original_name=chosen.original_name,
            )
        raise ExternalBenchmarkImportError(
            "unsupported_source", "source does not contain lm-eval results JSON"
        )
    if len(candidates) > 1:
        raise ExternalBenchmarkImportError(
            "malformed_source", "source contains conflicting results JSON identities"
        )
    return candidates[0]


def _discover_source(
    source: Path,
) -> tuple[list[DiscoveredSourceFile], DiscoveredSourceFile]:
    source = source.expanduser()
    try:
        info = source.lstat()
    except OSError as exc:
        raise ExternalBenchmarkImportError("failed", "source is unavailable") from exc
    if stat.S_ISLNK(info.st_mode):
        raise ExternalBenchmarkImportError("failed", "source must not be a symlink")
    if stat.S_ISREG(info.st_mode):
        name = source.name
        if not name:
            raise ExternalBenchmarkImportError(
                "failed", "source file name is malformed"
            )
        discovered = DiscoveredSourceFile(
            source_path=source,
            relative_posix=name,
            role="results_json",
            original_name=name,
        )
        return [discovered], discovered
    if not stat.S_ISDIR(info.st_mode):
        raise ExternalBenchmarkImportError(
            "unsupported_source", "source must be a results JSON file or directory"
        )
    files = _discover_directory_files(source)
    primary = _choose_primary_results(files)
    rewritten: list[DiscoveredSourceFile] = []
    for item in files:
        if item.source_path == primary.source_path:
            rewritten.append(
                DiscoveredSourceFile(
                    source_path=item.source_path,
                    relative_posix=item.relative_posix,
                    role="results_json",
                    original_name=item.original_name,
                )
            )
        else:
            rewritten.append(item)
    return rewritten, primary


def _contained_source_path(relative_posix: str) -> str:
    path = f"{SOURCE_RELATIVE_DIR}/{relative_posix}"
    _require_contained_path(path, "contained source path")
    if PurePosixPath(path).as_posix().startswith(f"{OBJECTS_RELATIVE_DIR}/"):
        raise ExternalBenchmarkImportError(
            "failed", "source path collides with the object store"
        )
    return path


def _hash_discovered(files: list[DiscoveredSourceFile]) -> list[CopiedSourceFile]:
    copied: list[CopiedSourceFile] = []
    total = 0
    for item in files:
        limit = (
            MAX_RESULTS_JSON_BYTES
            if item.role == "results_json"
            else MAX_SOURCE_FILE_BYTES
        )
        digest, byte_count = _hash_regular_file(
            item.source_path, limit=limit, label="source member"
        )
        total += byte_count
        if total > MAX_TOTAL_SOURCE_BYTES:
            raise ExternalBenchmarkImportError(
                "failed", "source package exceeds the total byte limit"
            )
        copied.append(
            CopiedSourceFile(
                discovered=item,
                sha256=digest,
                byte_count=byte_count,
                contained_path=_contained_source_path(item.relative_posix),
            )
        )
    paths = [item.contained_path for item in copied]
    if len(paths) != len(set(paths)):
        raise ExternalBenchmarkImportError(
            "malformed_source", "source members have conflicting contained paths"
        )
    return copied


def _load_primary_results(primary: CopiedSourceFile) -> dict[str, Any]:
    raw = _read_bounded_regular_file(
        primary.discovered.source_path,
        limit=MAX_RESULTS_JSON_BYTES,
        label="source results JSON",
    )
    if hashlib.sha256(raw).hexdigest() != primary.sha256:
        raise ExternalBenchmarkImportError(
            "failed", "source results JSON changed during import"
        )
    return _parse_json_object(raw, label="source results JSON")


def _source_and_destination_overlap(source: Path, destination: Path) -> bool:
    source_resolved = source.resolve(strict=False)
    destination_resolved = destination.resolve(strict=False)
    try:
        destination_resolved.relative_to(source_resolved)
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
    evidence: ExternalBenchmarkEvidence,
    evidence_sha256: str,
) -> dict[str, Any]:
    return {
        "schema_version": "llmgauge.result.v0",
        "llmgauge_version": __version__,
        "run": {
            "operation": RESULT_OPERATION,
            "run_id": (
                "external-benchmark-"
                + evidence.evidence_id.removeprefix("sha256:")[:16]
            ),
            "timestamp_utc": evidence.importer.imported_at,
            "result_dir": str(destination),
            "status": "completed",
        },
        "model": {"model_path": "redacted"},
        "runtime": {},
        "suite": {},
        "summary": {"completed": 0, "failed": 0},
        "results": [],
        "external_benchmark_evidence": ExternalBenchmarkEvidenceReference(
            schema_version=EVIDENCE_SCHEMA_VERSION,
            contract_version=CONTRACT_VERSION,
            evaluation_class=EVALUATION_CLASS,
            evidence_id=evidence.evidence_id,
            path=EVIDENCE_RELATIVE_PATH,
            sha256=evidence_sha256,
        ).model_dump(mode="json"),
    }


def _existing_import_result(
    destination: Path,
    expected: ExternalBenchmarkEvidence,
) -> ImportOperationResult | None:
    if not destination.exists():
        return None
    if destination.is_symlink() or not destination.is_dir():
        raise ExternalBenchmarkImportError("failed", "destination already exists")
    try:
        from llmgauge.core.result_validation import validate_result_dir

        errors = validate_result_dir(destination)
        result = json.loads(
            (destination / "llmgauge-result.json").read_text(encoding="utf-8")
        )
        reference = result.get("external_benchmark_evidence")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise ExternalBenchmarkImportError(
            "failed", "destination contains conflicting or invalid evidence"
        ) from exc
    if errors or not isinstance(reference, Mapping):
        raise ExternalBenchmarkImportError(
            "failed", "destination contains conflicting or invalid evidence"
        )
    if reference.get("evidence_id") != expected.evidence_id:
        raise ExternalBenchmarkImportError("failed", "destination evidence conflicts")
    evidence = load_external_benchmark_evidence(destination, reference)
    if evidence.source_package_sha256 != expected.source_package_sha256:
        raise ExternalBenchmarkImportError("failed", "destination evidence conflicts")
    return ImportOperationResult(
        outcome="already_imported",
        evidence_id=evidence.evidence_id,
        source_package_sha256=evidence.source_package_sha256,
        destination=destination,
    )


def _create_lock(destination: Path) -> tuple[int, Path]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    lock_path = (
        destination.parent / f".{destination.name}.external-benchmark-import.lock"
    )
    try:
        descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise ExternalBenchmarkImportError(
            "failed", "another import is in progress"
        ) from exc
    except OSError as exc:
        raise ExternalBenchmarkImportError(
            "failed", "import lock could not be created"
        ) from exc
    return descriptor, lock_path


def _rename_directory_no_replace(source: Path, destination: Path) -> None:
    if os.name == "nt":
        try:
            os.rename(source, destination)
        except FileExistsError as exc:
            raise ExternalBenchmarkImportError(
                "failed", "destination appeared during import"
            ) from exc
        except OSError as exc:
            raise ExternalBenchmarkImportError(
                "failed", "completed import could not be published atomically"
            ) from exc
        return
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        renameat2 = libc.renameat2
    except (AttributeError, OSError) as exc:
        raise ExternalBenchmarkImportError(
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
    if (
        renameat2(
            -100,
            os.fsencode(source),
            -100,
            os.fsencode(destination),
            1,
        )
        == 0
    ):
        return
    error_number = ctypes.get_errno()
    if error_number in {errno.EEXIST, errno.ENOTEMPTY}:
        raise ExternalBenchmarkImportError(
            "failed", "destination appeared during import"
        )
    raise ExternalBenchmarkImportError(
        "failed",
        "completed import could not be published atomically",
    )


def import_lm_eval_harness_results(
    source: Path,
    destination: Path,
    *,
    dry_run: bool = False,
) -> ImportOperationResult:
    """Import one lm-eval result package as contained, read-only evidence."""

    source = source.expanduser()
    destination = destination.expanduser()
    if _source_and_destination_overlap(source, destination):
        raise ExternalBenchmarkImportError(
            "failed", "source and destination overlap is unsafe"
        )
    discovered, _primary = _discover_source(source)
    copied = _hash_discovered(discovered)
    primary = next(item for item in copied if item.discovered.role == "results_json")
    root = _load_primary_results(primary)
    imported_at = datetime.now(UTC).replace(microsecond=0).isoformat()
    try:
        evidence = build_external_benchmark_evidence(
            root, copied, imported_at=imported_at
        )
    except ExternalBenchmarkImportError:
        raise
    except (ValidationError, ValueError, TypeError, RecursionError) as exc:
        raise ExternalBenchmarkImportError(
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
                prefix=f".{destination.name}.external-benchmark-import-",
                dir=destination.parent,
            )
        )
        if destination.exists():
            raise ExternalBenchmarkImportError("failed", "destination already exists")
        for item in copied:
            limit = (
                MAX_RESULTS_JSON_BYTES
                if item.discovered.role == "results_json"
                else MAX_SOURCE_FILE_BYTES
            )
            _copy_exact_file(
                item.discovered.source_path,
                staging / item.contained_path,
                expected_sha256=item.sha256,
                expected_size=item.byte_count,
                limit=limit,
                label="source member",
            )
        evidence_data = evidence.model_dump(mode="json")
        encoded_evidence = (
            json.dumps(
                evidence_data, indent=2, sort_keys=True, ensure_ascii=False
            ).encode("utf-8")
            + b"\n"
        )
        if len(encoded_evidence) > MAX_EVIDENCE_JSON_BYTES:
            raise ExternalBenchmarkImportError(
                "failed", "normalized evidence exceeds limit"
            )
        evidence_path = staging / EVIDENCE_RELATIVE_PATH
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        evidence_path.write_bytes(encoded_evidence)
        evidence_sha256 = _sha256_bytes(encoded_evidence)
        result = _build_result(destination, evidence, evidence_sha256)
        from llmgauge.core.run_fingerprint import attach_run_fingerprint

        if attach_run_fingerprint(staging, result) is None:
            raise ExternalBenchmarkImportError(
                "failed", "imported evidence fingerprint could not be created"
            )
        write_json(staging / "llmgauge-result.json", result)
        from llmgauge.core.result_validation import validate_result_dir

        errors = validate_result_dir(staging)
        if errors:
            raise ExternalBenchmarkImportError(
                "failed", "staged imported evidence failed structural validation"
            )
        if destination.exists():
            raise ExternalBenchmarkImportError(
                "failed", "destination appeared during import"
            )
        _rename_directory_no_replace(staging, destination)
        staging = None
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
            f"external_benchmark_evidence.{location}: {item.get('msg', 'invalid value')}"
        )
    if len(exc.errors()) > 20:
        errors.append("external_benchmark_evidence has additional validation errors")
    return errors


def load_external_benchmark_evidence(
    result_dir: Path, reference: Mapping[str, Any]
) -> ExternalBenchmarkEvidence:
    try:
        parsed_reference = ExternalBenchmarkEvidenceReference.model_validate(reference)
    except ValidationError as exc:
        raise ValueError("external_benchmark_evidence reference is invalid") from exc
    from llmgauge.core.run_fingerprint import (
        FingerprintUnavailable,
        resolve_contained_result_artifact,
    )

    try:
        evidence_path = resolve_contained_result_artifact(
            result_dir,
            parsed_reference.path,
            label="external_benchmark_evidence.path",
            require_file=True,
        )
    except FingerprintUnavailable as exc:
        raise ValueError(str(exc)) from exc
    raw = evidence_path.read_bytes()
    if len(raw) > MAX_EVIDENCE_JSON_BYTES:
        raise ValueError("external_benchmark_evidence exceeds byte limit")
    evidence_sha256 = _sha256_bytes(raw)
    if evidence_sha256 != parsed_reference.sha256:
        raise ValueError(
            "external_benchmark_evidence file hash does not match reference"
        )
    try:
        data = _parse_json_object(raw, label="external_benchmark_evidence")
        evidence = ExternalBenchmarkEvidence.model_validate(data)
    except (ExternalBenchmarkImportError, ValidationError) as exc:
        raise ValueError("external_benchmark_evidence is invalid") from exc
    if evidence.evidence_id != parsed_reference.evidence_id:
        raise ValueError(
            "external_benchmark_evidence identity does not match reference"
        )
    return evidence


def _validate_member_files(
    result_dir: Path, evidence: ExternalBenchmarkEvidence
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
            digest, byte_count = _hash_regular_file(
                path,
                limit=(
                    MAX_RESULTS_JSON_BYTES
                    if member.role == "results_json"
                    else MAX_SOURCE_FILE_BYTES
                ),
                label="contained source member",
            )
        except (FingerprintUnavailable, ExternalBenchmarkImportError) as exc:
            errors.append(str(exc))
            continue
        paths[member.member_id] = path
        if digest != member.sha256:
            errors.append(f"source member {member.member_id} hash mismatch")
        if byte_count != member.byte_count:
            errors.append(f"source member {member.member_id} byte count mismatch")
    return errors, paths


def _normalized_from_source(
    root: Mapping[str, Any], evidence: ExternalBenchmarkEvidence
) -> ExternalBenchmarkEvidence:
    copied = [
        CopiedSourceFile(
            discovered=DiscoveredSourceFile(
                source_path=Path("."),
                relative_posix=PurePosixPath(member.path)
                .relative_to(SOURCE_RELATIVE_DIR)
                .as_posix(),
                role=member.role,
                original_name=member.original_name or PurePosixPath(member.path).name,
            ),
            sha256=member.sha256,
            byte_count=member.byte_count,
            contained_path=member.path,
        )
        for member in evidence.source_inventory
    ]
    rebuilt = build_external_benchmark_evidence(
        root, copied, imported_at=evidence.importer.imported_at
    )
    return rebuilt.model_copy(
        update={
            "importer": evidence.importer,
            "evidence_id": evidence_identity(
                rebuilt.model_copy(update={"importer": evidence.importer})
            ),
        }
    )


def validate_external_benchmark_result(
    result_dir: Path, result: Mapping[str, Any]
) -> list[str]:
    reference = result.get("external_benchmark_evidence")
    if reference is None:
        return []
    if not isinstance(reference, Mapping):
        return ["external_benchmark_evidence must be an object"]
    try:
        parsed_reference = ExternalBenchmarkEvidenceReference.model_validate(reference)
    except ValidationError as exc:
        return _bounded_validation_error(exc)
    try:
        evidence = load_external_benchmark_evidence(result_dir, reference)
    except ValueError as exc:
        return [str(exc)]

    errors: list[str] = []
    if result.get("schema_version") != "llmgauge.result.v0":
        errors.append("imported result schema_version must be llmgauge.result.v0")
    if result.get("llmgauge_version") != evidence.importer.version:
        errors.append(
            "imported result llmgauge_version must match the importer version"
        )
    if not isinstance(result.get("run_fingerprint"), Mapping):
        errors.append("imported external benchmark evidence requires a run_fingerprint")
    if result.get("transcript") is not None:
        errors.append(
            "imported external benchmark evidence cannot include a native transcript"
        )
    if result.get("agent_harness_evidence") is not None:
        errors.append(
            "imported external benchmark evidence cannot include Agent Harness evidence"
        )
    if (
        result.get("runtime_neutral_metrics") is not None
        or result.get("failure_taxonomy") is not None
    ):
        errors.append(
            "imported external benchmark evidence cannot include Area 4 evidence"
        )
    if result.get("results") != []:
        errors.append(
            "imported external benchmark evidence requires empty native results"
        )
    if result.get("runtime") != {} or result.get("suite") != {}:
        errors.append(
            "imported external benchmark evidence requires empty runtime and suite"
        )
    if result.get("model") != {"model_path": "redacted"}:
        errors.append(
            "imported external benchmark evidence requires the redacted model sentinel"
        )
    if result.get("summary") != {"completed": 0, "failed": 0}:
        errors.append(
            "imported external benchmark evidence requires a zero native summary"
        )
    run = result.get("run")
    if not isinstance(run, Mapping):
        errors.append("imported external benchmark evidence requires run metadata")
    else:
        if run.get("operation") != RESULT_OPERATION:
            errors.append(
                "imported result run.operation must be external_benchmark_import"
            )
        if run.get("status") != "completed":
            errors.append("imported result run.status must be completed")

    member_errors, member_paths = _validate_member_files(result_dir, evidence)
    errors.extend(member_errors)
    expected_package = source_package_sha256(evidence.source_inventory)
    if evidence.source_package_sha256 != expected_package:
        errors.append("source_package_sha256 does not match canonical inventory")
    if evidence.evidence_id != evidence_identity(evidence):
        errors.append("evidence_id does not match canonical normalized evidence")

    results_member = next(
        (item for item in evidence.source_inventory if item.role == "results_json"),
        None,
    )
    if results_member is None:
        return errors
    results_path = member_paths.get(results_member.member_id)
    if results_path is None:
        return errors
    try:
        raw = _read_bounded_regular_file(
            results_path,
            limit=MAX_RESULTS_JSON_BYTES,
            label="contained results JSON",
        )
        root = _parse_json_object(raw, label="contained results JSON")
        expected = _normalized_from_source(root, evidence)
        expected_dump = expected.model_dump(
            mode="json", exclude={"importer", "evidence_id"}
        )
        actual_dump = evidence.model_dump(
            mode="json", exclude={"importer", "evidence_id"}
        )
        if expected_dump != actual_dump:
            errors.append(
                "normalized evidence disagrees with the contained source results"
            )
        if expected.importer.importer_id != evidence.importer.importer_id:
            errors.append("importer identity is not the admitted importer")
    except (
        ExternalBenchmarkImportError,
        ValidationError,
        ValueError,
        RecursionError,
    ) as exc:
        errors.append(f"contained source validation failed: {exc}")

    if parsed_reference.schema_version != evidence.schema_version:
        errors.append("result reference schema version disagrees with evidence")
    if parsed_reference.contract_version != evidence.contract_version:
        errors.append("result reference contract version disagrees with evidence")
    if parsed_reference.evaluation_class != evidence.evaluation_class:
        errors.append("result reference evaluation class disagrees with evidence")
    return errors
