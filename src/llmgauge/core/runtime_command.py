from __future__ import annotations

import shlex
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import typer

from llmgauge.core.config import coalesce, get_config_value
from llmgauge.runners.llama_cpp import LlamaCppRunConfig, build_llama_command

RUNTIME_COMMAND_FILENAME = "runtime-command.json"
RUNTIME_COMMAND_SCHEMA_VERSION = "llmgauge.runtime_command.v0"
PROMPT_PLACEHOLDER = "__PROMPT_FROM_RAW_ARTIFACT__"
PROMPT_FILE_THRESHOLD_BYTES = 64 * 1024
ReasoningMode = Literal["off", "on", "auto", "default", "unknown"]
ModelSource = Literal["model_profile", "direct_model_path"]
REASONING_MODE_FIELD = "reasoning_mode"
REASONING_MODE_REQUESTED_FIELD = "reasoning_mode_requested"


REASONING_MODES: frozenset[str] = frozenset({"off", "on", "auto", "default", "unknown"})


def resolve_model_source(*, model_profile: str | None) -> ModelSource:
    if model_profile is not None:
        return "model_profile"
    return "direct_model_path"


def normalize_reasoning_mode(value: Any) -> ReasoningMode:
    if value is None:
        return "off"

    normalized = str(value).strip().lower()
    if normalized not in REASONING_MODES:
        raise typer.BadParameter(
            f"reasoning_mode must be one of: {', '.join(sorted(REASONING_MODES))}"
        )
    return normalized  # type: ignore[return-value]


def resolve_reasoning_mode(
    *,
    cli_value: str | None,
    profile: dict[str, Any],
    config_data: dict[str, Any],
) -> ReasoningMode:
    raw = coalesce(
        cli_value,
        profile.get("reasoning_mode"),
        get_config_value(config_data, "defaults.reasoning_mode"),
        "off",
    )
    return normalize_reasoning_mode(raw)


def resolve_reasoning_mode_requested_from_metadata(
    runtime: dict[str, Any],
) -> ReasoningMode:
    raw = runtime.get(REASONING_MODE_REQUESTED_FIELD)
    if raw is None:
        raw = runtime.get(REASONING_MODE_FIELD)
    if raw is None:
        return "unknown"
    return normalize_reasoning_mode(raw)


def redact_command_argv(command_argv: list[str], model_path: Path) -> list[str]:
    redacted: list[str] = []
    redact_next = False
    for argument in command_argv:
        if redact_next:
            redacted.append(PROMPT_PLACEHOLDER)
            redact_next = False
            continue
        redacted.append(
            "REDACTED_MODEL_PATH" if argument == str(model_path) else argument
        )
        if argument in {"-p", "--prompt", "-f", "--file"}:
            redact_next = True
    return redacted


def build_runtime_command_document(
    *,
    config: LlamaCppRunConfig,
    resolved: dict[str, Any],
    suite_id: str,
    suite_version: str,
    timestamp_utc: str | None = None,
) -> dict[str, Any]:
    command_argv = build_llama_command(config, PROMPT_PLACEHOLDER)
    redacted_argv = redact_command_argv(command_argv, config.model_path)

    created_at = timestamp_utc or datetime.now(UTC).replace(microsecond=0).isoformat()

    return {
        "schema_version": RUNTIME_COMMAND_SCHEMA_VERSION,
        "command_argv": redacted_argv,
        "executable": str(config.llama_cli),
        "model_path": "redacted",
        "redacted_model_path": "REDACTED_MODEL_PATH",
        "model_source": resolved["model_source"],
        "model_id": resolved["model_id"],
        "model_profile": resolved["model_profile"],
        "suite_id": suite_id,
        "suite_version": suite_version,
        "ctx": config.ctx_size,
        "max_tokens": config.max_tokens,
        "temperature": config.temperature,
        "top_p": config.top_p,
        "top_k": config.top_k,
        "top_k_state": "explicit" if config.top_k is not None else "runtime_default",
        "seed": config.seed,
        "seed_state": "explicit" if config.seed is not None else "runtime_default",
        "batch": config.batch_size,
        "ubatch": config.ubatch_size,
        "parallel_sequences": 1,
        "gpu_layers": config.gpu_layers,
        "kv_offload": "requested_on",
        "cache_type_k": config.cache_type_k,
        "cache_type_k_state": (
            "explicit" if config.cache_type_k is not None else "runtime_default"
        ),
        "cache_type_v": config.cache_type_v,
        "cache_type_v_state": (
            "explicit" if config.cache_type_v is not None else "runtime_default"
        ),
        "flash_attn": config.flash_attn,
        "runtime_label": resolved.get("runtime_label"),
        "reasoning_mode": config.reasoning_mode,
        "reasoning_effort": config.reasoning_effort,
        "reasoning_effort_state": (
            "explicit" if config.reasoning_effort is not None else "runtime_default"
        ),
        "reasoning_budget": config.reasoning_budget,
        "reasoning_budget_state": (
            "explicit" if config.reasoning_budget is not None else "runtime_default"
        ),
        "fit": config.fit,
        "fit_state": "explicit" if config.fit is not None else "runtime_default",
        "reasoning_preserve": config.reasoning_preserve,
        "reasoning_preserve_state": (
            "explicit" if config.reasoning_preserve is not None else "runtime_default"
        ),
        "spec_type": config.spec_type,
        "spec_type_state": (
            "explicit" if config.spec_type is not None else "runtime_default"
        ),
        "prompt_transport": {
            "mode": "per_prompt",
            "argv_max_utf8_bytes": PROMPT_FILE_THRESHOLD_BYTES,
            "argv": {"flag": "--prompt", "source": "raw/*.prompt.md"},
            "file": {
                "flag": "--file",
                "source": "temporary local UTF-8 prompt file",
                "raw_evidence_source": "raw/*.prompt.md",
            },
        },
        "prompt_placeholder": PROMPT_PLACEHOLDER,
        "prompt_source_note": (
            "Per-prompt transport evidence is recorded after execution; raw prompt text "
            "is stored under raw/*.prompt.md."
        ),
        "created_at": created_at,
    }


def format_command_preview(command_argv: list[str]) -> str:
    return shlex.join(command_argv)
