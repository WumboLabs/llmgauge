from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any

CANONICAL_JSON_VERSION = "llmgauge.canonical_json.v0"
PROMPT_IDENTITY_VERSION = "llmgauge.prompt_identity.v0"
SUITE_IDENTITY_VERSION = "llmgauge.suite_identity.v0"

_JSON_SCALAR_TYPES = (str, int, float, bool, type(None))


def _canonical_json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        normalized: dict[str, Any] = {}
        for key, child in value.items():
            if not isinstance(key, str):
                raise TypeError("canonical JSON mappings must use string keys")
            normalized[key] = _canonical_json_value(child)
        return normalized

    if isinstance(value, tuple):
        return [_canonical_json_value(child) for child in value]

    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [_canonical_json_value(child) for child in value]

    if isinstance(value, _JSON_SCALAR_TYPES):
        return value

    raise TypeError(f"unsupported canonical JSON value: {type(value).__name__}")


def canonical_json_bytes(value: Any) -> bytes:
    """Serialize evaluation identity payloads to deterministic JSON bytes."""

    normalized = _canonical_json_value(value)
    return json.dumps(
        normalized,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def prompt_definition_payload(
    *,
    prompt: Mapping[str, Any],
    prompt_text: str,
    system_text: str | None = None,
    output_contract: Any = None,
    scoring_rubric: Any = None,
    evaluation_metadata: Mapping[str, Any] | None = None,
    template_instructions: Any = None,
) -> dict[str, Any]:
    """Build the evaluation-relevant prompt identity payload."""

    return {
        "schema_version": PROMPT_IDENTITY_VERSION,
        "prompt": dict(prompt),
        "prompt_text": prompt_text,
        "system_text": system_text or "",
        "output_contract": output_contract,
        "scoring_rubric": scoring_rubric,
        "evaluation_metadata": dict(evaluation_metadata or {}),
        "template_instructions": template_instructions,
    }


def prompt_definition_identity(
    *,
    prompt: Mapping[str, Any],
    prompt_text: str,
    system_text: str | None = None,
    output_contract: Any = None,
    scoring_rubric: Any = None,
    evaluation_metadata: Mapping[str, Any] | None = None,
    template_instructions: Any = None,
) -> str:
    return canonical_sha256(
        prompt_definition_payload(
            prompt=prompt,
            prompt_text=prompt_text,
            system_text=system_text,
            output_contract=output_contract,
            scoring_rubric=scoring_rubric,
            evaluation_metadata=evaluation_metadata,
            template_instructions=template_instructions,
        )
    )


def suite_definition_payload(
    *,
    suite: Mapping[str, Any],
    prompt_identities: Mapping[str, str],
) -> dict[str, Any]:
    """Build the evaluation-relevant suite identity payload."""

    return {
        "schema_version": SUITE_IDENTITY_VERSION,
        "suite": dict(suite),
        "prompt_identities": dict(prompt_identities),
    }


def suite_definition_identity(
    *,
    suite: Mapping[str, Any],
    prompt_identities: Mapping[str, str],
) -> str:
    return canonical_sha256(
        suite_definition_payload(suite=suite, prompt_identities=prompt_identities)
    )
