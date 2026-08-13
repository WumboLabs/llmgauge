from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SyntheticOmpSession:
    source: Path
    blob_dir: Path | None = None
    referenced_bytes: bytes | None = None


def _timestamp(index: int) -> str:
    return f"2026-08-12T00:00:{index:02d}.000Z"


def _entry(
    entry_type: str,
    entry_id: str,
    parent_id: str | None,
    index: int,
    **fields: Any,
) -> dict[str, Any]:
    return {
        "type": entry_type,
        "id": entry_id,
        "parentId": parent_id,
        "timestamp": _timestamp(index),
        **fields,
    }


def completed_records(
    *,
    result_details: dict[str, Any] | None = None,
    result_is_error: bool = False,
    exit_kind: str = "normal",
    exit_reason: str = "synthetic disposal",
    command: str = "printf synthetic",
) -> list[dict[str, Any]]:
    return [
        _entry(
            "session_init",
            "e001",
            None,
            1,
            task="Inspect the synthetic fixture without executing it.",
            tools=["bash"],
            outputSchemaMode="strict",
            restrictToolNames=True,
            spawns="*",
            readSummarize=False,
        ),
        _entry(
            "message",
            "e002",
            "e001",
            2,
            message={
                "role": "user",
                "content": [{"type": "text", "text": "Use inert synthetic evidence."}],
                "timestamp": 1,
            },
        ),
        _entry(
            "message",
            "e003",
            "e002",
            3,
            message={
                "role": "assistant",
                "provider": "synthetic-provider",
                "model": "synthetic-model",
                "content": [
                    {"type": "text", "text": "I will inspect the fixture."},
                    {
                        "type": "toolCall",
                        "id": "call-1",
                        "name": "bash",
                        "arguments": {"command": command},
                    },
                ],
                "timestamp": 2,
            },
        ),
        _entry(
            "custom",
            "e004",
            "e003",
            4,
            customType="tool_execution_start",
            data={
                "toolCallId": "call-1",
                "toolName": "bash",
                "startedAt": _timestamp(4),
                "args": {"command": command},
                "intent": "Inspecting synthetic fixture",
            },
        ),
        _entry(
            "message",
            "e005",
            "e004",
            5,
            message={
                "role": "toolResult",
                "toolCallId": "call-1",
                "toolName": "bash",
                "content": [{"type": "text", "text": "synthetic output"}],
                "isError": result_is_error,
                "details": result_details or {},
                "timestamp": 3,
            },
        ),
        _entry(
            "message",
            "e006",
            "e005",
            6,
            message={
                "role": "assistant",
                "provider": "synthetic-provider",
                "model": "synthetic-model",
                "content": [{"type": "text", "text": "Synthetic review finished."}],
                "timestamp": 4,
            },
        ),
        _entry(
            "custom",
            "e007",
            "e006",
            7,
            customType="session_exit",
            data={
                "reason": exit_reason,
                "kind": exit_kind,
                "recordedAt": _timestamp(7),
            },
        ),
    ]


def write_session(
    root: Path,
    records: list[dict[str, Any]],
    *,
    version: int | str | None = 3,
    header_updates: dict[str, Any] | None = None,
    physical_title: bool = False,
    source_name: str = "synthetic-session.jsonl",
) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    source = root / source_name
    header: dict[str, Any] = {
        "type": "session",
        "id": "synthetic-session-001",
        "timestamp": _timestamp(0),
        "cwd": "/synthetic/workspace",
    }
    if version is not None:
        header["version"] = version
    if header_updates:
        header.update(header_updates)
    payload = bytearray()
    if physical_title:
        title = json.dumps(
            {"type": "title", "title": "Synthetic"}, separators=(",", ":")
        ).encode("utf-8")
        payload.extend(title)
        payload.extend(b" " * (255 - len(title)))
        payload.extend(b"\n")
    for item in [header, *records]:
        payload.extend(
            json.dumps(item, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        )
        payload.extend(b"\n")
    source.write_bytes(payload)
    return source


def write_synthetic_omp_session(
    root: Path,
    scenario: str = "completed",
    *,
    physical_title: bool = False,
) -> SyntheticOmpSession:
    if scenario == "completed":
        records = completed_records()
    elif scenario == "failed":
        records = completed_records(
            result_details={"exitCode": 2},
            result_is_error=True,
            exit_kind="fatal",
            exit_reason="synthetic fatal exit",
        )
    elif scenario == "partial":
        records = completed_records()
        records[4]["message"]["content"] = [
            {
                "type": "text",
                "text": "[Session persistence truncated large content]",
            }
        ]
    elif scenario == "interrupted":
        complete = completed_records(
            exit_kind="signal",
            exit_reason="synthetic interruption",
        )
        exit_record = complete[-1]
        exit_record["parentId"] = "e004"
        exit_record["data"]["pendingToolCalls"] = [
            {
                "toolCallId": "call-1",
                "toolName": "bash",
                "args": {"command": "printf synthetic"},
                "startedAt": _timestamp(4),
            }
        ]
        records = [*complete[:4], exit_record]
    elif scenario == "command_lifecycle":
        records = completed_records(
            result_details={"exitCode": 7}, result_is_error=True
        )
    elif scenario == "denied":
        records = completed_records(
            result_details={"denied": True, "approval": "denied"},
            result_is_error=True,
        )
        records.pop(3)
        records[3]["parentId"] = "e003"
    elif scenario == "timeout":
        records = completed_records(
            result_details={"timedOut": True}, result_is_error=True
        )
    elif scenario == "clean_repository":
        records = completed_records(command="git status --porcelain")
    elif scenario == "dirty_repository":
        records = completed_records(command="git diff --no-ext-diff")
        records[4]["message"]["content"] = [
            {"type": "text", "text": "diff --git a/synthetic b/synthetic"}
        ]
    elif scenario == "unavailable_optional":
        records = completed_records()[:2]
    elif scenario == "referenced_object":
        records = completed_records(
            result_details={
                "meta": {
                    "truncation": {
                        "reason": "output spill",
                        "artifactId": "1",
                    }
                }
            }
        )
    else:
        raise ValueError(f"unknown synthetic scenario: {scenario}")

    source = write_session(root, records, physical_title=physical_title)
    if scenario != "referenced_object":
        return SyntheticOmpSession(source=source)

    referenced_bytes = b"complete synthetic command output\n"
    artifact_dir = source.with_suffix("")
    artifact_dir.mkdir()
    (artifact_dir / "1.bash.log").write_bytes(referenced_bytes)
    return SyntheticOmpSession(
        source=source,
        referenced_bytes=referenced_bytes,
    )


def add_blob_reference(
    root: Path, records: list[dict[str, Any]]
) -> SyntheticOmpSession:
    blob_bytes = b"synthetic-image-bytes"
    digest = hashlib.sha256(blob_bytes).hexdigest()
    records[1]["message"]["content"].append(
        {"type": "image", "data": f"blob:sha256:{digest}"}
    )
    source = write_session(root, records)
    blob_dir = root / "blobs"
    blob_dir.mkdir()
    (blob_dir / digest).write_bytes(blob_bytes)
    return SyntheticOmpSession(
        source=source,
        blob_dir=blob_dir,
        referenced_bytes=blob_bytes,
    )
