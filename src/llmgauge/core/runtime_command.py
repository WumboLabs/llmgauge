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

ReasoningMode = Literal["off", "on", "auto", "default", "unknown"]
ModelSource = Literal["model_profile", "direct_model_path"]

REASONING_MODES: frozenset[str] = frozenset(
    {"off", "on", "auto", "default", "unknown"}
)


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


def redact_command_argv(command_argv: list[str], model_path: Path) -> list[str]:
    model_text = str(model_path)
    return [arg if arg != model_text else "REDACTED_MODEL_PATH" for arg in command_argv]


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
        "batch": config.batch_size,
        "ubatch": config.ubatch_size,
        "gpu_layers": config.gpu_layers,
        "flash_attn": config.flash_attn,
        "runtime_label": resolved.get("runtime_label"),
        "reasoning_mode": config.reasoning_mode,
        "prompt_placeholder": PROMPT_PLACEHOLDER,
        "prompt_source_note": (
            "Per-prompt text is stored under raw/*.prompt.md; substitute the placeholder "
            "when reproducing a prompt-level invocation."
        ),
        "created_at": created_at,
    }


def format_command_preview(command_argv: list[str]) -> str:
    return shlex.join(command_argv)