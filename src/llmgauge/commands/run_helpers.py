from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import typer
from rich.table import Table

from llmgauge import __version__
from llmgauge.cli_common import (
    DEFAULT_LOCAL_CONFIG,
    DEFAULT_LOCAL_MODEL_PROFILES,
    console,
    default_existing_path,
    fail_cli_validation,
    user_config_path,
    user_model_profiles_path,
)
from llmgauge.core.artifacts import prepare_result_dir, write_json, write_text
from llmgauge.core.area4_evidence import (
    build_area4_evidence,
    build_native_execution_evidence,
)
from llmgauge.core.config import (
    coalesce,
    get_config_value,
    load_llmgauge_config,
    load_model_profiles,
    resolve_model_profile,
)
from llmgauge.core.coding_core_evidence import (
    build_portable_selection,
    build_prompt_evidence,
)
from llmgauge.core.fit_ladder import build_fit_attempt_record
from llmgauge.core.identity import (
    collect_backend_provenance,
    collect_model_provenance,
    discover_llama_runtime_identity,
)
from llmgauge.core.metrics import parse_llama_metrics
from llmgauge.core.multi_turn import (
    ModelAttemptEvent,
    ModelInvocationResult,
    TranscriptDefinitionError,
    build_result_transcript_reference,
    execute_native_conversation,
    load_multi_turn_task,
)
from llmgauge.core.output_cleaning import clean_llama_output
from llmgauge.core.output_paths import build_auto_output_dir
from llmgauge.core.reports import build_markdown_report
from llmgauge.core.run_fingerprint import attach_run_fingerprint
from llmgauge.core.runtime_command import (
    RUNTIME_COMMAND_FILENAME,
    build_runtime_command_document,
    format_command_preview,
    redact_command_argv,
    resolve_model_source,
    resolve_reasoning_mode,
)
from llmgauge.core.suite import (
    NormalizedSuite,
    SuiteDefinitionError,
    load_normalized_suite,
    load_suite,
)
from llmgauge.core.suite_paths import resolve_suite_path
from llmgauge.runners.llama_cpp import LlamaCppRunConfig, run_llama_cpp
from llmgauge.runners.vllm_external import (
    DEFAULT_CONNECT_TIMEOUT,
    DEFAULT_MAX_RESPONSE_BYTES,
    DEFAULT_REQUEST_TIMEOUT,
    VLLM_RUNTIME_EVIDENCE_FILENAME,
    VllmExternalConfig,
    VllmRequestResult,
    build_runtime_evidence_document,
    build_vllm_metrics,
    check_readiness_and_model,
    format_failure_log,
    run_chat_completion,
)
from llmgauge.runners.vllm_http import VllmTransportError, validate_vllm_endpoint


def find_prompt(suite: dict, prompt_id: str) -> dict:
    for prompt in suite.get("prompts", []):
        if prompt.get("id") == prompt_id:
            return prompt
    raise typer.BadParameter(f"Prompt ID not found in suite: {prompt_id}")


def select_prompts(suite: dict, only: str | None, include: str) -> list[dict]:
    prompts = suite.get("prompts", [])

    if only:
        return [find_prompt(suite, only)]

    if include == "all":
        return list(prompts)

    selected = [prompt for prompt in prompts if prompt.get("category") == include]
    if not selected:
        raise typer.BadParameter(f"No prompts found for include/category: {include}")

    return selected


def load_run_suite(
    suite: Path,
    *,
    only: str | None,
    include: str,
    profile: str | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], NormalizedSuite]:
    if profile is not None and (only is not None or include != "all"):
        raise typer.BadParameter(
            "--profile is mutually exclusive with --only and category-based --include"
        )

    loaded_suite = load_suite(suite)
    try:
        if only is None and include == "all":
            normalized = load_normalized_suite(suite, profile=profile)
            prompts_by_id = {
                prompt["id"]: prompt for prompt in loaded_suite.get("prompts", [])
            }
            selected_prompts = [
                prompts_by_id[prompt_id] for prompt_id in normalized.selected_prompt_ids
            ]
        else:
            selected_prompts = select_prompts(loaded_suite, only, include)
            selected_ids = tuple(prompt["id"] for prompt in selected_prompts)
            normalized = load_normalized_suite(suite, prompt_ids=selected_ids)
    except SuiteDefinitionError as exc:
        raise typer.BadParameter(str(exc)) from exc

    return loaded_suite, selected_prompts, normalized


def build_result_suite_metadata(
    *,
    loaded_suite: dict[str, Any],
    resolved_suite: Path,
    normalized_suite: NormalizedSuite,
    prompt_count: int,
    include: str,
    only: str | None,
) -> dict[str, Any]:
    result = {
        "suite_id": loaded_suite["suite_id"],
        "suite_version": str(loaded_suite["suite_version"]),
        "suite_path": str(resolved_suite),
        "prompt_count": prompt_count,
        "include": include,
        "only": only,
    }
    selection = build_portable_selection(normalized_suite)
    if selection is not None:
        result["selection"] = selection
    return result


def load_system_prompt() -> str:
    path = resolve_suite_path(Path("core-v1")) / "prompts/system-conservative-ops.txt"
    if path.exists():
        return path.read_text(encoding="utf-8").strip()

    return (
        "You are a conservative local systems assistant. "
        "Prefer safe, reversible, verified steps. "
        "Say when unsure. Do not invent commands, packages, flags, or docs."
    )


def build_combined_prompt(system_prompt: str, prompt_text: str) -> str:
    return "\n\n".join(
        [
            "SYSTEM:",
            system_prompt,
            "USER:",
            prompt_text,
        ]
    )


def build_redacted_command(command: list[str], model_path: Path) -> list[str]:
    return redact_command_argv(command, model_path)


def optional_nonnegative_int(value: Any, *, field_name: str) -> int | None:
    if value is None:
        return None

    resolved = int(value)
    if resolved < 0:
        raise typer.BadParameter(f"{field_name} must be non-negative")

    return resolved


LLAMA_CACHE_TYPES = frozenset(
    {"f32", "f16", "bf16", "q8_0", "q4_0", "q4_1", "iq4_nl", "q5_0", "q5_1"}
)
LLAMA_REASONING_EFFORTS = frozenset(
    {"default", "minimal", "low", "medium", "high", "xhigh", "max"}
)
LLAMA_FIT_MODES = frozenset({"on", "off"})
LLAMA_SPEC_TYPES = frozenset(
    {
        "none",
        "draft-simple",
        "draft-eagle3",
        "draft-mtp",
        "draft-dflash",
        "draft-dspark",
        "ngram-simple",
        "ngram-map-k",
        "ngram-map-k4v",
        "ngram-mod",
        "ngram-cache",
    }
)


def optional_fit_mode(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return "on" if value else "off"
    if not isinstance(value, str):
        raise typer.BadParameter("fit must be one of: off, on")
    resolved = value.strip().lower()
    if resolved not in LLAMA_FIT_MODES:
        raise typer.BadParameter("fit must be one of: off, on")
    return resolved


def optional_bool(value: Any, *, field_name: str) -> bool | None:
    if value is None:
        return None
    if not isinstance(value, bool):
        raise typer.BadParameter(f"{field_name} must be true or false")
    return value


def optional_spec_type(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise typer.BadParameter(
            f"spec_type must use: {', '.join(sorted(LLAMA_SPEC_TYPES))}"
        )
    tokens = [token.strip().lower() for token in value.split(",")]
    if not tokens or any(not token for token in tokens):
        raise typer.BadParameter(
            f"spec_type must use: {', '.join(sorted(LLAMA_SPEC_TYPES))}"
        )
    invalid = sorted(set(tokens) - LLAMA_SPEC_TYPES)
    if invalid:
        raise typer.BadParameter(
            "spec_type contains unsupported value(s): "
            f"{', '.join(invalid)}; supported values: "
            f"{', '.join(sorted(LLAMA_SPEC_TYPES))}"
        )
    if len(tokens) != len(set(tokens)):
        raise typer.BadParameter("spec_type must not contain duplicate values")
    if "none" in tokens and len(tokens) != 1:
        raise typer.BadParameter("spec_type=none cannot be combined with other values")
    return ",".join(tokens)


def optional_int(
    value: Any,
    *,
    field_name: str,
    minimum: int | None = None,
) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise typer.BadParameter(f"{field_name} must be an integer")
    try:
        resolved = int(value)
    except (TypeError, ValueError) as exc:
        raise typer.BadParameter(f"{field_name} must be an integer") from exc
    if minimum is not None and resolved < minimum:
        raise typer.BadParameter(f"{field_name} must be at least {minimum}")
    return resolved


def optional_llama_cache_type(value: Any, *, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise typer.BadParameter(
            f"{field_name} must be one of: {', '.join(sorted(LLAMA_CACHE_TYPES))}"
        )
    resolved = value.strip().lower()
    if resolved not in LLAMA_CACHE_TYPES:
        raise typer.BadParameter(
            f"{field_name} must be one of: {', '.join(sorted(LLAMA_CACHE_TYPES))}"
        )
    return resolved


def optional_reasoning_effort(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise typer.BadParameter(
            "reasoning_effort must be one of: "
            f"{', '.join(sorted(LLAMA_REASONING_EFFORTS))}"
        )
    resolved = value.strip().lower()
    if resolved not in LLAMA_REASONING_EFFORTS:
        raise typer.BadParameter(
            "reasoning_effort must be one of: "
            f"{', '.join(sorted(LLAMA_REASONING_EFFORTS))}"
        )
    return resolved


def vram_headroom_mib(vram_summary: dict[str, Any] | None) -> int | None:
    if not isinstance(vram_summary, dict) or not vram_summary.get("available"):
        return None

    peak_used_mib = vram_summary.get("peak_used_mib")
    peak_total_mib = vram_summary.get("peak_total_mib")

    if not isinstance(peak_used_mib, int) or not isinstance(peak_total_mib, int):
        return None

    return peak_total_mib - peak_used_mib


def build_vram_guardrails(
    vram_summary: dict[str, Any] | None,
    *,
    min_headroom_warn_mib: int | None,
) -> dict[str, Any] | None:
    if min_headroom_warn_mib is None:
        return None

    observed_headroom_mib = vram_headroom_mib(vram_summary)
    if observed_headroom_mib is None:
        return None

    warnings = []
    status = "ok"

    if observed_headroom_mib < min_headroom_warn_mib:
        status = "warning"
        warnings.append("vram_headroom_below_warning_threshold")

    return {
        "schema_version": "llmgauge.vram.guardrails.v0",
        "status": status,
        "min_headroom_warn_mib": min_headroom_warn_mib,
        "observed_headroom_mib": observed_headroom_mib,
        "warnings": warnings,
    }


def resolve_cli_output_dir(
    *,
    out: Path | None,
    auto_name: bool,
    runs_root: Path,
    run_name: str | None,
    default_run_name: str,
) -> Path:
    if out is not None and auto_name:
        raise typer.BadParameter("Use either --out or --auto-name, not both")

    if out is not None:
        return out

    if not auto_name:
        fail_cli_validation("Use --out PATH or --auto-name")

    return build_auto_output_dir(
        runs_root=runs_root,
        run_name=run_name or default_run_name,
    )


def _normalize_backend(value: Any) -> str:
    if value is None:
        return "llama.cpp"
    normalized = str(value).strip().lower()
    if normalized in {"llama.cpp", "llamacpp", "llama"}:
        return "llama.cpp"
    if normalized == "vllm":
        return "vllm"
    raise typer.BadParameter("backend must be one of: llama.cpp, vllm")


def reject_unsupported_vllm_command(
    resolved: dict[str, Any],
    *,
    command: str,
) -> None:
    """Fail closed: backend=vllm is supported only by the normal run command."""
    if (resolved.get("backend") or "llama.cpp") != "vllm":
        return
    raise typer.BadParameter(
        f"{command} does not support backend=vllm in this slice. "
        "Use `llmgauge run` with --backend vllm (or a vLLM profile) for the "
        "externally managed server adapter. Batch, ladder, and fit-ladder "
        "vLLM execution is not implemented."
    )


def _optional_positive_float(value: Any, *, field_name: str) -> float | None:
    if value is None:
        return None
    resolved = float(value)
    if resolved <= 0:
        raise typer.BadParameter(f"{field_name} must be positive")
    return resolved


def _optional_positive_int(value: Any, *, field_name: str) -> int | None:
    if value is None:
        return None
    resolved = int(value)
    if resolved <= 0:
        raise typer.BadParameter(f"{field_name} must be positive")
    return resolved


def resolve_run_options(
    *,
    model_id: str | None,
    model_profile: str | None,
    config_path: Path | None,
    model_profiles_path: Path | None,
    model_path: Path | None,
    llama_cli: Path | None,
    ctx: int | None,
    max_tokens: int | None,
    temp: float | None,
    top_p: float | None,
    top_k: int | None = None,
    seed: int | None = None,
    batch: int | None = None,
    ubatch: int | None = None,
    gpu_layers: int | None = None,
    flash_attn: str | None = None,
    cache_type_k: str | None = None,
    cache_type_v: str | None = None,
    runtime_label: str | None = None,
    reasoning_mode: str | None = None,
    reasoning_effort: str | None = None,
    reasoning_budget: int | None = None,
    fit: str | None = None,
    reasoning_preserve: bool | None = None,
    spec_type: str | None = None,
    backend: str | None = None,
    vllm_endpoint: str | None = None,
    served_model: str | None = None,
    connect_timeout: float | None = None,
    request_timeout: float | None = None,
    max_response_bytes: int | None = None,
) -> dict[str, Any]:
    resolved_config_path = config_path or default_existing_path(
        DEFAULT_LOCAL_CONFIG,
        user_config_path(),
    )
    resolved_model_profiles_path = model_profiles_path or default_existing_path(
        DEFAULT_LOCAL_MODEL_PROFILES,
        user_model_profiles_path(),
    )

    config_data = load_llmgauge_config(resolved_config_path)
    profiles = load_model_profiles(resolved_model_profiles_path)
    profile = resolve_model_profile(profiles, model_profile)

    resolved_backend = _normalize_backend(
        coalesce(
            backend,
            profile.get("backend"),
            get_config_value(config_data, "runtime.backend"),
            "llama.cpp",
        )
    )

    resolved_model_id = coalesce(model_id, model_profile, profile.get("label"))
    if resolved_model_id is None:
        raise typer.BadParameter("Provide --model-id or --model-profile")

    resolved_ctx = int(
        coalesce(
            ctx,
            profile.get("ctx_size"),
            get_config_value(config_data, "defaults.ctx_size"),
            8192,
        )
    )
    resolved_max_tokens = int(
        coalesce(
            max_tokens,
            profile.get("max_tokens"),
            get_config_value(config_data, "defaults.max_tokens"),
            800,
        )
    )
    resolved_temp = float(
        coalesce(
            temp,
            profile.get("temperature"),
            get_config_value(config_data, "defaults.temperature"),
            0.2,
        )
    )
    resolved_top_p = float(
        coalesce(
            top_p,
            profile.get("top_p"),
            get_config_value(config_data, "defaults.top_p"),
            0.95,
        )
    )
    resolved_top_k = optional_int(
        coalesce(
            top_k,
            profile.get("top_k"),
            get_config_value(config_data, "defaults.top_k"),
        ),
        field_name="top_k",
        minimum=0,
    )
    resolved_seed = optional_int(
        coalesce(
            seed,
            profile.get("seed"),
            get_config_value(config_data, "defaults.seed"),
        ),
        field_name="seed",
    )
    resolved_batch = int(
        coalesce(
            batch,
            profile.get("batch_size"),
            get_config_value(config_data, "defaults.batch_size"),
            256,
        )
    )
    resolved_ubatch = int(
        coalesce(
            ubatch,
            profile.get("ubatch_size"),
            get_config_value(config_data, "defaults.ubatch_size"),
            64,
        )
    )
    resolved_gpu_layers = int(
        coalesce(
            gpu_layers,
            profile.get("gpu_layers"),
            get_config_value(config_data, "defaults.gpu_layers"),
            999,
        )
    )
    raw_flash_attn = coalesce(
        flash_attn,
        profile.get("flash_attn"),
        get_config_value(config_data, "defaults.flash_attn"),
        "auto",
    )
    if isinstance(raw_flash_attn, bool):
        resolved_flash_attn = "on" if raw_flash_attn else "off"
    else:
        resolved_flash_attn = str(raw_flash_attn).lower()

    if resolved_flash_attn not in {"auto", "on", "off"}:
        raise typer.BadParameter("flash_attn must be one of: auto, on, off")

    raw_runtime_label = coalesce(
        runtime_label,
        profile.get("runtime_label"),
        get_config_value(config_data, "defaults.runtime_label"),
    )
    resolved_runtime_label = (
        str(raw_runtime_label).strip() if raw_runtime_label is not None else None
    )
    if resolved_runtime_label == "":
        resolved_runtime_label = None
    resolved_cache_type_k = optional_llama_cache_type(
        coalesce(
            cache_type_k,
            profile.get("cache_type_k"),
            get_config_value(config_data, "defaults.cache_type_k"),
        ),
        field_name="cache_type_k",
    )
    resolved_cache_type_v = optional_llama_cache_type(
        coalesce(
            cache_type_v,
            profile.get("cache_type_v"),
            get_config_value(config_data, "defaults.cache_type_v"),
        ),
        field_name="cache_type_v",
    )
    if (
        resolved_backend == "llama.cpp"
        and resolved_cache_type_v not in {None, "f16"}
        and resolved_flash_attn != "on"
    ):
        raise typer.BadParameter(
            "cache_type_v quantization requires --flash-attn on for llama.cpp"
        )

    resolved_reasoning_effort = optional_reasoning_effort(
        coalesce(
            reasoning_effort,
            profile.get("reasoning_effort"),
            get_config_value(config_data, "defaults.reasoning_effort"),
        )
    )
    resolved_reasoning_budget = optional_int(
        coalesce(
            reasoning_budget,
            profile.get("reasoning_budget"),
            get_config_value(config_data, "defaults.reasoning_budget"),
        ),
        field_name="reasoning_budget",
        minimum=-1,
    )
    resolved_fit = optional_fit_mode(
        coalesce(
            fit,
            profile.get("fit"),
            get_config_value(config_data, "defaults.fit"),
        )
    )
    resolved_reasoning_preserve = optional_bool(
        coalesce(
            reasoning_preserve,
            profile.get("reasoning_preserve"),
            get_config_value(config_data, "defaults.reasoning_preserve"),
        ),
        field_name="reasoning_preserve",
    )
    resolved_spec_type = optional_spec_type(
        coalesce(
            spec_type,
            profile.get("spec_type"),
            get_config_value(config_data, "defaults.spec_type"),
        )
    )

    resolved_reasoning_mode = resolve_reasoning_mode(
        cli_value=reasoning_mode,
        profile=profile,
        config_data=config_data,
    )
    resolved_model_source = resolve_model_source(model_profile=model_profile)

    resolved_vram_min_headroom_warn_mib = optional_nonnegative_int(
        get_config_value(config_data, "vram.min_headroom_warn_mib"),
        field_name="vram.min_headroom_warn_mib",
    )

    if resolved_backend != "llama.cpp" and any(
        value is not None
        for value in (resolved_fit, resolved_reasoning_preserve, resolved_spec_type)
    ):
        raise typer.BadParameter(
            "fit, reasoning_preserve, and spec_type are supported only by "
            "backend=llama.cpp"
        )

    if resolved_backend == "vllm" and any(
        value is not None
        for value in (
            resolved_top_k,
            resolved_seed,
            resolved_cache_type_k,
            resolved_cache_type_v,
            resolved_reasoning_effort,
            resolved_reasoning_budget,
        )
    ):
        raise typer.BadParameter(
            "top_k, seed, cache_type_k, cache_type_v, reasoning_effort, and "
            "reasoning_budget are currently supported only by backend=llama.cpp"
        )

    if resolved_backend == "vllm":
        resolved_endpoint = coalesce(
            vllm_endpoint,
            profile.get("vllm_endpoint"),
            get_config_value(config_data, "runtime.vllm_endpoint"),
        )
        if resolved_endpoint is None or not str(resolved_endpoint).strip():
            raise typer.BadParameter(
                "Provide --vllm-endpoint or set runtime.vllm_endpoint / "
                "profile vllm_endpoint for backend=vllm"
            )
        resolved_endpoint = str(resolved_endpoint).strip()
        try:
            validate_vllm_endpoint(resolved_endpoint)
        except VllmTransportError as exc:
            raise typer.BadParameter(f"Invalid vLLM endpoint ({exc.detail})") from exc

        resolved_served_model = coalesce(
            served_model,
            profile.get("served_model"),
            get_config_value(config_data, "runtime.served_model"),
            profile.get("label"),
            model_id,
            model_profile,
        )
        if resolved_served_model is None or not str(resolved_served_model).strip():
            raise typer.BadParameter(
                "Provide --served-model or set profile served_model for backend=vllm"
            )
        resolved_served_model = str(resolved_served_model).strip()

        resolved_connect_timeout = float(
            coalesce(
                _optional_positive_float(connect_timeout, field_name="connect_timeout"),
                _optional_positive_float(
                    profile.get("connect_timeout"), field_name="connect_timeout"
                ),
                _optional_positive_float(
                    get_config_value(config_data, "runtime.connect_timeout"),
                    field_name="runtime.connect_timeout",
                ),
                DEFAULT_CONNECT_TIMEOUT,
            )
        )
        resolved_request_timeout = float(
            coalesce(
                _optional_positive_float(request_timeout, field_name="request_timeout"),
                _optional_positive_float(
                    profile.get("request_timeout"), field_name="request_timeout"
                ),
                _optional_positive_float(
                    get_config_value(config_data, "runtime.request_timeout"),
                    field_name="runtime.request_timeout",
                ),
                DEFAULT_REQUEST_TIMEOUT,
            )
        )
        resolved_max_response_bytes = int(
            coalesce(
                _optional_positive_int(
                    max_response_bytes, field_name="max_response_bytes"
                ),
                _optional_positive_int(
                    profile.get("max_response_bytes"),
                    field_name="max_response_bytes",
                ),
                _optional_positive_int(
                    get_config_value(config_data, "runtime.max_response_bytes"),
                    field_name="runtime.max_response_bytes",
                ),
                DEFAULT_MAX_RESPONSE_BYTES,
            )
        )

        # Directory/GGUF provenance is deferred for vLLM. Reject local paths so
        # collect_model_provenance is never applied to a served checkpoint.
        profile_path = profile.get("path")
        if model_path is not None or (
            isinstance(profile_path, str) and profile_path.strip()
        ):
            raise typer.BadParameter(
                "backend=vllm does not accept --model-path or profile path in "
                "this slice; directory-model and GGUF provenance for served "
                "checkpoints is deferred. Identify the model with "
                "--served-model / profile served_model only."
            )

        return {
            "backend": "vllm",
            "model_id": str(resolved_model_id),
            "model_profile": model_profile,
            "profile": profile,
            "config_path": resolved_config_path,
            "model_profiles_path": resolved_model_profiles_path,
            "model_path": None,
            "llama_cli": None,
            "vllm_endpoint": resolved_endpoint,
            "served_model": resolved_served_model,
            "connect_timeout": resolved_connect_timeout,
            "request_timeout": resolved_request_timeout,
            "max_response_bytes": resolved_max_response_bytes,
            "ctx": resolved_ctx,
            "max_tokens": resolved_max_tokens,
            "temp": resolved_temp,
            "top_p": resolved_top_p,
            "batch": resolved_batch,
            "ubatch": resolved_ubatch,
            "gpu_layers": resolved_gpu_layers,
            "flash_attn": resolved_flash_attn,
            "runtime_label": resolved_runtime_label,
            "reasoning_mode": resolved_reasoning_mode,
            "model_source": resolved_model_source,
            "vram_min_headroom_warn_mib": resolved_vram_min_headroom_warn_mib,
        }

    resolved_model_path = coalesce(model_path, profile.get("path"))
    if resolved_model_path is None:
        if (
            model_id is not None
            and model_profile is None
            and isinstance(profiles.get(model_id), dict)
        ):
            raise typer.BadParameter(
                f"Model profile {model_id!r} was provided with --model-id. "
                f"Use --model-profile {model_id} to load its configured path."
            )
        raise typer.BadParameter(
            "Provide --model-path or use --model-profile with a path"
        )
    resolved_model_path = Path(resolved_model_path)

    resolved_llama_cli = coalesce(
        llama_cli,
        get_config_value(config_data, "runtime.llama_cli"),
    )
    if resolved_llama_cli is None:
        raise typer.BadParameter(
            "Provide --llama-cli or set runtime.llama_cli in --config"
        )
    resolved_llama_cli = Path(resolved_llama_cli)

    if not resolved_model_path.exists():
        raise typer.BadParameter(f"Model path does not exist: {resolved_model_path}")

    if not resolved_llama_cli.exists():
        raise typer.BadParameter(f"llama-cli path does not exist: {resolved_llama_cli}")

    return {
        "backend": "llama.cpp",
        "model_id": str(resolved_model_id),
        "model_profile": model_profile,
        "profile": profile,
        "config_path": resolved_config_path,
        "model_profiles_path": resolved_model_profiles_path,
        "model_path": resolved_model_path,
        "llama_cli": resolved_llama_cli,
        "vllm_endpoint": None,
        "served_model": None,
        "connect_timeout": None,
        "request_timeout": None,
        "max_response_bytes": None,
        "ctx": resolved_ctx,
        "max_tokens": resolved_max_tokens,
        "temp": resolved_temp,
        "top_p": resolved_top_p,
        "top_k": resolved_top_k,
        "seed": resolved_seed,
        "batch": resolved_batch,
        "ubatch": resolved_ubatch,
        "gpu_layers": resolved_gpu_layers,
        "flash_attn": resolved_flash_attn,
        "cache_type_k": resolved_cache_type_k,
        "cache_type_v": resolved_cache_type_v,
        "runtime_label": resolved_runtime_label,
        "reasoning_mode": resolved_reasoning_mode,
        "reasoning_effort": resolved_reasoning_effort,
        "reasoning_budget": resolved_reasoning_budget,
        "fit": resolved_fit,
        "reasoning_preserve": resolved_reasoning_preserve,
        "spec_type": resolved_spec_type,
        "model_source": resolved_model_source,
        "vram_min_headroom_warn_mib": resolved_vram_min_headroom_warn_mib,
    }


def print_run_preflight(
    *,
    suite: Path,
    only: str | None,
    include: str,
    profile: str | None = None,
    resolved: dict[str, Any],
    out: Path | None,
    auto_name: bool,
    runs_root: Path,
    run_name: str | None,
    conversation_task: Path | None = None,
    conversation_id: str | None = None,
    max_turns: int | None = None,
) -> None:
    if conversation_task is not None:
        print_multi_turn_preflight(
            suite=suite,
            only=only,
            include=include,
            profile=profile,
            resolved=resolved,
            out=out,
            auto_name=auto_name,
            runs_root=runs_root,
            run_name=run_name,
            conversation_task=conversation_task,
            conversation_id=conversation_id,
            max_turns=max_turns,
        )
        return
    resolved_suite = resolve_suite_path(suite)
    loaded_suite, selected_prompts, normalized_suite = load_run_suite(
        resolved_suite,
        only=only,
        include=include,
        profile=profile,
    )

    if out is not None:
        output_plan = str(out)
    elif auto_name:
        default_run_name = f"{resolved['model_id']}-{suite.name}"
        output_plan = (
            f"auto-name under {runs_root} with run name {run_name or default_run_name}"
        )
    else:
        output_plan = (
            "not required for --dry-run; real runs require --out or --auto-name"
        )

    selection = (
        f"profile={normalized_suite.selected_profile}"
        if profile is not None
        else (f"only={only}" if only else f"include={include}")
    )

    table = Table(title="LLMGauge Run Dry Run")
    table.add_column("Field", no_wrap=True)
    table.add_column("Value")

    table.add_row("Suite", str(loaded_suite.get("suite_id", suite)))
    table.add_row("Suite path", str(resolved_suite))
    table.add_row("Selection", selection)
    table.add_row("Prompt count", str(len(selected_prompts)))
    backend = resolved.get("backend") or "llama.cpp"
    table.add_row("Backend", str(backend))
    table.add_row("Model ID", str(resolved["model_id"]))
    table.add_row("Model source", str(resolved["model_source"]))
    table.add_row("Model profile", str(resolved["model_profile"]))
    table.add_row("Config", str(resolved["config_path"]))
    table.add_row("Model profiles", str(resolved["model_profiles_path"]))
    if backend == "vllm":
        try:
            endpoint = validate_vllm_endpoint(str(resolved["vllm_endpoint"]))
            identity = endpoint.identity
            identity_text = (
                f"scheme={identity.get('scheme')}, "
                f"loopback_class={identity.get('loopback_class')}, "
                f"port={identity.get('port')}"
            )
        except VllmTransportError as exc:
            identity_text = f"invalid ({exc.detail})"
        table.add_row("Endpoint identity", identity_text)
        table.add_row("Served model", str(resolved["served_model"]))
        table.add_row("Connect timeout s", str(resolved["connect_timeout"]))
        table.add_row("Request timeout s", str(resolved["request_timeout"]))
        table.add_row("Max response bytes", str(resolved["max_response_bytes"]))
        table.add_row(
            "Model path",
            "not used (served-model identity only; local provenance deferred)",
        )
    else:
        table.add_row("Model path", str(resolved["model_path"]))
        table.add_row("llama-cli", str(resolved["llama_cli"]))
    table.add_row("Context", str(resolved["ctx"]))
    table.add_row("Max tokens", str(resolved["max_tokens"]))
    table.add_row("Temperature", str(resolved["temp"]))
    table.add_row("Top-p", str(resolved["top_p"]))
    if backend != "vllm":
        table.add_row("Top-k", str(resolved.get("top_k")))
        table.add_row("Seed", str(resolved.get("seed")))
        table.add_row("Batch", str(resolved["batch"]))
        table.add_row("UBatch", str(resolved["ubatch"]))
        table.add_row("GPU layers", str(resolved["gpu_layers"]))
        table.add_row("KV cache K type", str(resolved.get("cache_type_k")))
        table.add_row("KV cache V type", str(resolved.get("cache_type_v")))
        table.add_row("KV offload", "requested on")
        table.add_row("Flash attention", str(resolved["flash_attn"]))
    table.add_row("Runtime label", str(resolved["runtime_label"] or "unknown"))
    table.add_row("Reasoning mode", str(resolved["reasoning_mode"]))
    table.add_row("Output plan", output_plan)

    if backend == "vllm":
        table.add_row(
            "Request shape",
            "non-streaming OpenAI-compatible chat.completions (external server)",
        )
        if out is not None:
            evidence_path = str(out / VLLM_RUNTIME_EVIDENCE_FILENAME)
        elif auto_name:
            default_run_name = f"{resolved['model_id']}-{suite.name}"
            evidence_path = (
                f"{runs_root}/<auto-named-run>/{VLLM_RUNTIME_EVIDENCE_FILENAME} "
                f"(run name {run_name or default_run_name})"
            )
        else:
            evidence_path = (
                f"<result-dir>/{VLLM_RUNTIME_EVIDENCE_FILENAME} for real runs "
                "with --out or --auto-name"
            )
        table.add_row("Runtime evidence artifact", evidence_path)
        table.add_row("Runtime command artifact", "not used for vLLM")
    else:
        preview_config = LlamaCppRunConfig(
            llama_cli=resolved["llama_cli"],
            model_path=resolved["model_path"],
            ctx_size=resolved["ctx"],
            max_tokens=resolved["max_tokens"],
            temperature=resolved["temp"],
            top_p=resolved["top_p"],
            top_k=resolved.get("top_k"),
            seed=resolved.get("seed"),
            batch_size=resolved["batch"],
            ubatch_size=resolved["ubatch"],
            gpu_layers=resolved["gpu_layers"],
            flash_attn=resolved["flash_attn"],
            cache_type_k=resolved.get("cache_type_k"),
            cache_type_v=resolved.get("cache_type_v"),
            reasoning_mode=resolved["reasoning_mode"],
            reasoning_effort=resolved.get("reasoning_effort"),
            reasoning_budget=resolved.get("reasoning_budget"),
            fit=resolved.get("fit"),
            reasoning_preserve=resolved.get("reasoning_preserve"),
            spec_type=resolved.get("spec_type"),
        )
        preview_document = build_runtime_command_document(
            config=preview_config,
            resolved=resolved,
            suite_id=str(loaded_suite.get("suite_id", suite)),
            suite_version=str(loaded_suite.get("suite_version", "unknown")),
        )
        table.add_row(
            "Command preview",
            format_command_preview(preview_document["command_argv"]),
        )
        if out is not None:
            runtime_command_path = str(out / RUNTIME_COMMAND_FILENAME)
        elif auto_name:
            default_run_name = f"{resolved['model_id']}-{suite.name}"
            runtime_command_path = (
                f"{runs_root}/<auto-named-run>/{RUNTIME_COMMAND_FILENAME} "
                f"(run name {run_name or default_run_name})"
            )
        else:
            runtime_command_path = (
                f"<result-dir>/{RUNTIME_COMMAND_FILENAME} for real runs "
                "with --out or --auto-name"
            )
        table.add_row("Runtime command artifact", runtime_command_path)

    console.print(table)

    prompt_table = Table(title="Selected Prompts")
    prompt_table.add_column("Prompt", no_wrap=True)
    prompt_table.add_column("Category", no_wrap=True)
    prompt_table.add_column("Title")

    for prompt in selected_prompts:
        prompt_table.add_row(
            str(prompt.get("id", "")),
            str(prompt.get("category", "")),
            str(prompt.get("title", prompt.get("id", ""))),
        )

    console.print(prompt_table)
    if backend == "vllm":
        console.print(
            "[bold green]Dry run complete[/bold green]: no HTTP request was "
            "sent and no result directory was created. Server lifecycle remains "
            "operator-owned."
        )
    else:
        console.print(
            "[bold green]Dry run complete[/bold green]: llama.cpp was not "
            "launched and no result directory was created."
        )


def _load_multi_turn_selection(
    *,
    suite: Path,
    only: str | None,
    include: str,
    profile: str | None,
    conversation_task: Path,
    conversation_id: str | None,
) -> tuple[
    Path,
    dict[str, Any],
    dict[str, Any],
    NormalizedSuite,
    Any,
    str,
]:
    if conversation_id is None:
        raise typer.BadParameter(
            "--conversation-id is required with --conversation-task"
        )
    if only is None:
        raise typer.BadParameter("--only is required with --conversation-task")
    if profile is not None or include != "all":
        raise typer.BadParameter(
            "--conversation-task requires exact --only selection; "
            "--profile and category --include are not supported"
        )
    try:
        task = load_multi_turn_task(conversation_task)
    except TranscriptDefinitionError as exc:
        raise typer.BadParameter(str(exc)) from None
    if task.task_id != only:
        raise typer.BadParameter(
            "conversation task task_id must match the exact --only selection"
        )
    resolved_suite = resolve_suite_path(suite)
    loaded_suite, selected_prompts, normalized_suite = load_run_suite(
        resolved_suite,
        only=only,
        include="all",
        profile=None,
    )
    if loaded_suite.get("suite_id") == "coding-core-v1":
        raise typer.BadParameter(
            "native multi-turn evaluation does not alter the static Coding Core inventory"
        )
    prompt_meta = selected_prompts[0]
    prompt_text = (
        (resolved_suite / prompt_meta["file"]).read_text(encoding="utf-8").strip()
    )
    initial_message = build_combined_prompt(load_system_prompt(), prompt_text)
    return (
        resolved_suite,
        loaded_suite,
        prompt_meta,
        normalized_suite,
        task,
        initial_message,
    )


def print_multi_turn_preflight(
    *,
    suite: Path,
    only: str | None,
    include: str,
    profile: str | None,
    resolved: dict[str, Any],
    out: Path | None,
    auto_name: bool,
    runs_root: Path,
    run_name: str | None,
    conversation_task: Path,
    conversation_id: str | None,
    max_turns: int | None,
) -> None:
    (
        resolved_suite,
        loaded_suite,
        prompt_meta,
        _normalized_suite,
        task,
        initial_message,
    ) = _load_multi_turn_selection(
        suite=suite,
        only=only,
        include=include,
        profile=profile,
        conversation_task=conversation_task,
        conversation_id=conversation_id,
    )
    effective_turns = task.limits.max_model_turns
    if max_turns is not None:
        if max_turns < 1 or max_turns > effective_turns:
            raise typer.BadParameter(
                "--max-turns must be positive and cannot exceed the task limit"
            )
        effective_turns = max_turns
    planned_requests = (
        min(
            effective_turns,
            max(feedback.after_model_turn for feedback in task.feedback) + 1,
        )
        if task.feedback
        else 1
    )
    if out is not None:
        output_plan = str(out)
    elif auto_name:
        default_name = f"{resolved['model_id']}-{suite.name}"
        output_plan = (
            f"auto-name under {runs_root} with run name {run_name or default_name}"
        )
    else:
        output_plan = (
            "not required for --dry-run; real runs require --out or --auto-name"
        )

    backend = str(resolved.get("backend") or "llama.cpp")
    table = Table(title="LLMGauge Native Multi-turn Dry Run")
    table.add_column("Field", no_wrap=True)
    table.add_column("Value")
    table.add_row("Transcript schema", "llmgauge.transcript.v0")
    table.add_row("Protocol", f"{task.protocol_id} {task.protocol_version}")
    table.add_row("Conversation ID", str(conversation_id))
    table.add_row(
        "Task",
        f"{loaded_suite['suite_id']} {loaded_suite['suite_version']} / {task.task_id} {task.task_version}",
    )
    table.add_row("Suite path", str(resolved_suite))
    table.add_row("Selection", f"exact --only={only}")
    table.add_row("Declared model-turn limit", str(task.limits.max_model_turns))
    table.add_row("Effective model-turn limit", str(effective_turns))
    table.add_row("Planned model requests", str(planned_requests))
    table.add_row("Attempts per turn limit", str(task.limits.max_attempts_per_turn))
    table.add_row("Per-turn timeout s", str(task.limits.per_turn_timeout_seconds))
    table.add_row("Declared feedback items", str(len(task.feedback)))
    table.add_row("Backend", backend)
    table.add_row("Model ID", str(resolved["model_id"]))
    table.add_row("Model profile", str(resolved["model_profile"]))
    table.add_row("Context", str(resolved["ctx"]))
    table.add_row("Max tokens", str(resolved["max_tokens"]))
    table.add_row("Temperature", str(resolved["temp"]))
    table.add_row("Top-p", str(resolved["top_p"]))
    table.add_row("Output plan", output_plan)
    table.add_row(
        "Execution boundary",
        "sequential, non-streaming, supplied inert feedback; no generated content execution",
    )
    console.print(table)

    plan = Table(title="Runtime-conditional deterministic protocol plan")
    plan.add_column("Order", no_wrap=True)
    plan.add_column("Kind", no_wrap=True)
    plan.add_column("Condition / association")
    plan.add_row("1", "initial user/task", initial_message)
    order = 2
    for turn in range(1, planned_requests + 1):
        if turn == 1:
            request_condition = "planned initial request"
        elif any(feedback.after_model_turn == turn - 1 for feedback in task.feedback):
            request_condition = (
                "conditional on prior request completing and scheduled feedback "
                "being supplied"
            )
        else:
            request_condition = (
                "conditional on prior request completing to reach a future "
                "feedback schedule"
            )
        plan.add_row(
            str(order),
            f"model request {turn}",
            request_condition,
        )
        order += 1
        for feedback in task.feedback:
            if feedback.after_model_turn == turn and turn <= effective_turns:
                supply_result = (
                    "supplied but unconsumable: no admitted follow-up request"
                    if turn == effective_turns
                    else f"consumed by conditional model request {turn + 1}"
                )
                plan.add_row(
                    str(order),
                    f"conditional feedback supply {feedback.feedback_id}",
                    f"if request {turn} completes; {supply_result}",
                )
                order += 1
    console.print(plan)

    feedback_plan = Table(title="Complete declared feedback plan")
    feedback_plan.add_column("ID", no_wrap=True)
    feedback_plan.add_column("Origin", no_wrap=True)
    feedback_plan.add_column("Schedule", no_wrap=True)
    feedback_plan.add_column("Reachability")
    feedback_plan.add_column("Exact content")
    for feedback in task.feedback:
        if feedback.after_model_turn > effective_turns:
            reachability = "declared but unreachable under effective turn limit"
        elif feedback.after_model_turn == effective_turns:
            reachability = (
                "conditional supply if scheduling request completes; "
                "then supplied but unconsumable"
            )
        else:
            reachability = (
                "conditional supply if scheduling request completes; "
                f"then consumption by request {feedback.after_model_turn + 1}"
            )
        feedback_plan.add_row(
            feedback.feedback_id,
            feedback.origin,
            f"after model turn {feedback.after_model_turn}",
            reachability,
            feedback.content,
        )
    console.print(feedback_plan)
    console.print(
        "[bold green]Dry run complete[/bold green]: no runtime was launched or "
        "contacted, no generated content was executed, and no result directory "
        "was created."
    )


def execute_multi_turn_run(
    *,
    suite: Path,
    only: str | None,
    include: str,
    profile: str | None,
    resolved: dict[str, Any],
    out: Path,
    fail_on_failed_prompts: bool,
    conversation_task: Path,
    conversation_id: str | None,
    max_turns: int | None,
) -> dict[str, Any]:
    (
        resolved_suite,
        loaded_suite,
        prompt_meta,
        normalized_suite,
        task,
        initial_message,
    ) = _load_multi_turn_selection(
        suite=suite,
        only=only,
        include=include,
        profile=profile,
        conversation_task=conversation_task,
        conversation_id=conversation_id,
    )
    prepare_result_dir(out)
    timestamp = datetime.now(UTC).replace(microsecond=0).isoformat()
    backend = str(resolved.get("backend") or "llama.cpp")
    runtime_command_path: Path | None = None
    runtime_evidence_path: Path | None = None
    invocation_results: list[Any] = []
    endpoint_identity: dict[str, Any] = {}
    readiness: Any = None

    if backend == "vllm":
        vllm_config = VllmExternalConfig(
            endpoint_url=str(resolved["vllm_endpoint"]),
            served_model=str(resolved["served_model"]),
            max_tokens=int(resolved["max_tokens"]),
            temperature=float(resolved["temp"]),
            top_p=float(resolved["top_p"]),
            connect_timeout=float(resolved["connect_timeout"]),
            request_timeout=float(resolved["request_timeout"]),
            max_response_bytes=int(resolved["max_response_bytes"]),
            ctx_size=int(resolved["ctx"]),
        )
        readiness = check_readiness_and_model(vllm_config)
        endpoint_identity = readiness.endpoint_identity or {}

        def invoke(prompt: str, timeout_seconds: float) -> ModelInvocationResult:
            if not readiness.success:
                return ModelInvocationResult(
                    stdout="",
                    stderr=format_failure_log(readiness),
                    exit_status=1,
                    timeout=readiness.failure_class == "request_timeout",
                )
            bounded_config = VllmExternalConfig(
                endpoint_url=vllm_config.endpoint_url,
                served_model=vllm_config.served_model,
                max_tokens=vllm_config.max_tokens,
                temperature=vllm_config.temperature,
                top_p=vllm_config.top_p,
                connect_timeout=min(vllm_config.connect_timeout, timeout_seconds),
                request_timeout=min(vllm_config.request_timeout, timeout_seconds),
                max_response_bytes=vllm_config.max_response_bytes,
                ctx_size=vllm_config.ctx_size,
            )
            request_result = run_chat_completion(
                bounded_config,
                prompt=prompt,
                system_prompt=None,
            )
            invocation_results.append(request_result)
            return ModelInvocationResult(
                stdout=request_result.generated_text,
                stderr=(
                    "vllm request completed\n"
                    if request_result.success and not request_result.incomplete_usage
                    else format_failure_log(request_result)
                ),
                exit_status=0 if request_result.success else 1,
                timeout=request_result.failure_class == "request_timeout",
                malformed=request_result.failure_class == "malformed_response",
            )

    else:
        llama_config = LlamaCppRunConfig(
            llama_cli=resolved["llama_cli"],
            model_path=resolved["model_path"],
            ctx_size=resolved["ctx"],
            max_tokens=resolved["max_tokens"],
            temperature=resolved["temp"],
            top_p=resolved["top_p"],
            top_k=resolved.get("top_k"),
            seed=resolved.get("seed"),
            batch_size=resolved["batch"],
            ubatch_size=resolved["ubatch"],
            gpu_layers=resolved["gpu_layers"],
            flash_attn=resolved["flash_attn"],
            cache_type_k=resolved.get("cache_type_k"),
            cache_type_v=resolved.get("cache_type_v"),
            reasoning_mode=resolved["reasoning_mode"],
            reasoning_effort=resolved.get("reasoning_effort"),
            reasoning_budget=resolved.get("reasoning_budget"),
            fit=resolved.get("fit"),
            reasoning_preserve=resolved.get("reasoning_preserve"),
            spec_type=resolved.get("spec_type"),
        )
        runtime_command_document = build_runtime_command_document(
            config=llama_config,
            resolved=resolved,
            suite_id=loaded_suite["suite_id"],
            suite_version=str(loaded_suite["suite_version"]),
            timestamp_utc=timestamp,
        )
        runtime_command_path = out / RUNTIME_COMMAND_FILENAME
        write_json(runtime_command_path, runtime_command_document)

        def invoke(prompt: str, timeout_seconds: float) -> ModelInvocationResult:
            run_result = run_llama_cpp(
                llama_config,
                prompt,
                timeout_seconds=timeout_seconds,
            )
            invocation_results.append(run_result)
            return ModelInvocationResult(
                stdout=run_result.stdout,
                stderr=run_result.stderr,
                exit_status=run_result.exit_status,
                timeout=run_result.timed_out,
            )

    outcome = execute_native_conversation(
        task=task,
        conversation_id=str(conversation_id),
        suite_id=str(loaded_suite["suite_id"]),
        suite_version=str(loaded_suite["suite_version"]),
        initial_message=initial_message,
        invoke=invoke,
        result_dir=out,
        max_turns=max_turns,
    )
    model_events = [
        event
        for event in outcome.transcript.events
        if isinstance(event, ModelAttemptEvent)
    ]
    compatibility_event = outcome.selected_event or model_events[-1]
    completed = outcome.transcript.completion_state == "completed"
    selected_runtime_result = invocation_results[-1] if invocation_results else None

    if backend == "vllm":
        observed_fingerprints = [
            result.system_fingerprint
            for result in invocation_results
            if isinstance(result, VllmRequestResult) and result.system_fingerprint
        ]
        runtime_evidence = build_runtime_evidence_document(
            config=vllm_config,
            readiness=readiness,
            endpoint_identity=endpoint_identity,
            observed_system_fingerprints=observed_fingerprints,
        )
        runtime_evidence_path = out / VLLM_RUNTIME_EVIDENCE_FILENAME
        write_json(runtime_evidence_path, runtime_evidence)
        for index, request_result in enumerate(invocation_results, start=1):
            if isinstance(request_result, VllmRequestResult):
                write_json(
                    out / "request" / f"multi-turn-{index:03d}.json",
                    request_result.request_evidence
                    or {
                        "schema_version": "llmgauge.vllm_request_evidence.v0",
                        "lifecycle_ownership": "external_operator",
                        "failure_class": request_result.failure_class,
                        "failure_detail": request_result.failure_detail,
                        "endpoint_identity": request_result.endpoint_identity,
                    },
                )
        model_provenance = {
            "source_type": resolved["model_source"],
            "filename": None,
            "file_size_bytes": None,
            "sha256": None,
            "public_fingerprint": None,
            "status": "unavailable",
            "warning": (
                "Directory-model and GGUF provenance are unavailable for backend=vllm; "
                "identity is the requested/observed served-model name only"
            ),
            "served_model": resolved["served_model"],
            "provenance_kind": "served_model_only",
        }
        backend_provenance = {
            "backend_name": "vllm",
            "lifecycle_ownership": "external_operator",
            "endpoint_identity": endpoint_identity,
            "requested_served_model": resolved["served_model"],
            "observed_served_model": readiness.observed_model,
            "status": "available" if readiness.success else "unavailable",
            "warning": None
            if readiness.success
            else (readiness.failure_detail or readiness.failure_class),
        }
        runtime: dict[str, Any] = {
            "backend": "vllm",
            "lifecycle_ownership": "external_operator",
            "endpoint_identity": endpoint_identity,
            "requested_served_model": resolved["served_model"],
            "observed_served_model": readiness.observed_model,
            "connect_timeout_seconds": resolved["connect_timeout"],
            "request_timeout_seconds": resolved["request_timeout"],
            "max_response_bytes": resolved["max_response_bytes"],
            "ctx_size": resolved["ctx"],
            "max_tokens": resolved["max_tokens"],
            "temperature": resolved["temp"],
            "top_p": resolved["top_p"],
            "runtime_label": resolved["runtime_label"],
            "reasoning_mode": resolved["reasoning_mode"],
            "runtime_command_captured": False,
            "runtime_command_path": None,
            "vllm_runtime_evidence_captured": True,
            "vllm_runtime_evidence_path": str(runtime_evidence_path.relative_to(out)),
            "vram_min_headroom_warn_mib": resolved["vram_min_headroom_warn_mib"],
            "command": [],
            "config_path": str(resolved["config_path"])
            if resolved["config_path"]
            else None,
            "model_profiles_path": str(resolved["model_profiles_path"])
            if resolved["model_profiles_path"]
            else None,
            "backend_provenance": backend_provenance,
            "proxy_bypass_policy": runtime_evidence.get("proxy_bypass_policy"),
            "streaming": False,
            "authentication": "none",
        }
        metrics = (
            build_vllm_metrics(selected_runtime_result)
            if isinstance(selected_runtime_result, VllmRequestResult)
            else build_vllm_metrics(VllmRequestResult(success=False))
        )
        vram_summary = None
        command: list[str] = []
    else:
        model_provenance = collect_model_provenance(
            resolved["model_path"],
            source_type=resolved["model_source"],
        )
        backend_provenance = collect_backend_provenance(resolved["llama_cli"])
        backend_provenance.update(
            discover_llama_runtime_identity(resolved["llama_cli"])
        )
        command = (
            build_redacted_command(
                selected_runtime_result.command,
                resolved["model_path"],
            )
            if selected_runtime_result is not None
            else []
        )
        runtime = {
            "backend": "llama.cpp",
            "llama_cli": str(resolved["llama_cli"]),
            "ctx_size": resolved["ctx"],
            "max_tokens": resolved["max_tokens"],
            "temperature": resolved["temp"],
            "top_p": resolved["top_p"],
            "top_k": resolved.get("top_k"),
            "top_k_state": (
                "explicit" if resolved.get("top_k") is not None else "runtime_default"
            ),
            "seed": resolved.get("seed"),
            "seed_state": (
                "explicit" if resolved.get("seed") is not None else "runtime_default"
            ),
            "batch_size": resolved["batch"],
            "parallel_sequences": 1,
            "ubatch_size": resolved["ubatch"],
            "gpu_layers": resolved["gpu_layers"],
            "kv_offload": "requested_on",
            "cache_type_k": resolved.get("cache_type_k"),
            "cache_type_k_state": (
                "explicit"
                if resolved.get("cache_type_k") is not None
                else "runtime_default"
            ),
            "cache_type_v": resolved.get("cache_type_v"),
            "cache_type_v_state": (
                "explicit"
                if resolved.get("cache_type_v") is not None
                else "runtime_default"
            ),
            "flash_attn": resolved["flash_attn"],
            "runtime_label": resolved["runtime_label"],
            "reasoning_mode": resolved["reasoning_mode"],
            "reasoning_effort": resolved.get("reasoning_effort"),
            "reasoning_effort_state": (
                "explicit"
                if resolved.get("reasoning_effort") is not None
                else "runtime_default"
            ),
            "reasoning_budget": resolved.get("reasoning_budget"),
            "reasoning_budget_state": (
                "explicit"
                if resolved.get("reasoning_budget") is not None
                else "runtime_default"
            ),
            "fit": resolved.get("fit"),
            "fit_state": (
                "explicit" if resolved.get("fit") is not None else "runtime_default"
            ),
            "reasoning_preserve": resolved.get("reasoning_preserve"),
            "reasoning_preserve_state": (
                "explicit"
                if resolved.get("reasoning_preserve") is not None
                else "runtime_default"
            ),
            "spec_type": resolved.get("spec_type"),
            "spec_type_state": (
                "explicit"
                if resolved.get("spec_type") is not None
                else "runtime_default"
            ),
            "runtime_command_captured": True,
            "runtime_command_path": str(runtime_command_path.relative_to(out)),
            "vram_min_headroom_warn_mib": resolved["vram_min_headroom_warn_mib"],
            "command": command,
            "config_path": str(resolved["config_path"])
            if resolved["config_path"]
            else None,
            "model_profiles_path": str(resolved["model_profiles_path"])
            if resolved["model_profiles_path"]
            else None,
            "backend_provenance": backend_provenance,
        }
        raw_output = (
            (out / compatibility_event.raw_output.path).read_text(encoding="utf-8")
            if compatibility_event.raw_output.path
            else ""
        )
        runtime_stderr = (
            (out / compatibility_event.runtime_stderr.path).read_text(encoding="utf-8")
            if compatibility_event.runtime_stderr.path
            else ""
        )
        metrics = parse_llama_metrics(raw_output + "\n" + runtime_stderr)
        vram_summary = getattr(selected_runtime_result, "vram_summary", None)

    profile_data = resolved["profile"]
    prompt_entry: dict[str, Any] = {
        "prompt_id": task.task_id,
        "title": prompt_meta.get("title", task.task_id),
        "category": prompt_meta.get("category"),
        "status": "completed" if completed else "failed",
        "raw_prompt_path": compatibility_event.raw_input.path,
        "raw_output_path": compatibility_event.raw_output.path,
        "cleaned_output_path": (
            compatibility_event.cleaned_output.path
            if compatibility_event.cleaned_output is not None
            else compatibility_event.raw_output.path
        ),
        "stderr_log_path": compatibility_event.runtime_stderr.path,
        "metrics": metrics,
        "vram": vram_summary,
        "vram_samples_path": None,
        "vram_guardrails": build_vram_guardrails(
            vram_summary,
            min_headroom_warn_mib=resolved["vram_min_headroom_warn_mib"],
        ),
        "score": None,
        "failure_labels": [],
        "notes": "",
        "exit_status": compatibility_event.exit_status,
        "error": None if completed else outcome.transcript.terminal_reason,
        "transcript_event_id": (
            outcome.transcript.final_response_event_id if completed else None
        ),
    }
    result: dict[str, Any] = {
        "schema_version": "llmgauge.result.v0",
        "llmgauge_version": __version__,
        "run": {
            "run_id": out.name,
            "timestamp_utc": timestamp,
            "status": "completed" if completed else "failed",
            "result_dir": str(out),
        },
        "model": {
            "model_id": resolved["model_id"],
            "model_source": resolved["model_source"],
            "model_profile": resolved["model_profile"],
            "label": profile_data.get("label"),
            "family": profile_data.get("family"),
            "role": profile_data.get("role"),
            "quant": profile_data.get("quant"),
            "model_path": "redacted",
            "model_path_policy": "redacted",
            "provenance": model_provenance,
        },
        "runtime": runtime,
        "suite": build_result_suite_metadata(
            loaded_suite=loaded_suite,
            resolved_suite=resolved_suite,
            normalized_suite=normalized_suite,
            prompt_count=1,
            include="all",
            only=only,
        ),
        "results": [prompt_entry],
        "summary": {
            "completed": 1 if completed else 0,
            "failed": 0 if completed else 1,
            "manual_score_total": None,
            "manual_score_max": None,
            "failure_labels": {},
        },
    }
    result["transcript"] = build_result_transcript_reference(out, outcome.transcript)
    return _finalize_run_result(
        out=out,
        result=result,
        failed_count=0 if completed else 1,
        fail_on_failed_prompts=fail_on_failed_prompts,
    )


def _finalize_run_result(
    *,
    out: Path,
    result: dict[str, Any],
    failed_count: int,
    fail_on_failed_prompts: bool,
) -> dict[str, Any]:
    attach_run_fingerprint(out, result)
    write_json(out / "llmgauge-result.json", result)
    report_kwargs = {"result_dir": out} if result.get("transcript") is not None else {}
    write_text(out / "report.md", build_markdown_report(result, **report_kwargs))
    if failed_count:
        console.print(f"[bold red]Run completed with failures[/bold red]: {out}")
        if fail_on_failed_prompts:
            raise typer.Exit(code=1)
    else:
        console.print(f"[bold green]Run completed[/bold green]: {out}")

    return result


def execute_run(
    *,
    suite: Path,
    only: str | None,
    include: str,
    profile: str | None = None,
    resolved: dict[str, Any],
    out: Path,
    fail_on_failed_prompts: bool,
    conversation_task: Path | None = None,
    conversation_id: str | None = None,
    max_turns: int | None = None,
) -> dict[str, Any]:
    if conversation_task is not None:
        return execute_multi_turn_run(
            suite=suite,
            only=only,
            include=include,
            profile=profile,
            resolved=resolved,
            out=out,
            fail_on_failed_prompts=fail_on_failed_prompts,
            conversation_task=conversation_task,
            conversation_id=conversation_id,
            max_turns=max_turns,
        )
    if (resolved.get("backend") or "llama.cpp") == "vllm":
        return execute_vllm_run(
            suite=suite,
            only=only,
            include=include,
            profile=profile,
            resolved=resolved,
            out=out,
            fail_on_failed_prompts=fail_on_failed_prompts,
        )

    resolved_suite = resolve_suite_path(suite)
    suite = resolved_suite
    loaded_suite, selected_prompts, normalized_suite = load_run_suite(
        suite,
        only=only,
        include=include,
        profile=profile,
    )
    normalized_prompts = {
        prompt.id: prompt for prompt in normalized_suite.selected_prompts
    }
    system_prompt = load_system_prompt()

    prepare_result_dir(out)

    config = LlamaCppRunConfig(
        llama_cli=resolved["llama_cli"],
        model_path=resolved["model_path"],
        ctx_size=resolved["ctx"],
        max_tokens=resolved["max_tokens"],
        temperature=resolved["temp"],
        top_p=resolved["top_p"],
        top_k=resolved.get("top_k"),
        seed=resolved.get("seed"),
        batch_size=resolved["batch"],
        ubatch_size=resolved["ubatch"],
        gpu_layers=resolved["gpu_layers"],
        flash_attn=resolved["flash_attn"],
        cache_type_k=resolved.get("cache_type_k"),
        cache_type_v=resolved.get("cache_type_v"),
        reasoning_mode=resolved["reasoning_mode"],
        reasoning_effort=resolved.get("reasoning_effort"),
        reasoning_budget=resolved.get("reasoning_budget"),
        fit=resolved.get("fit"),
        reasoning_preserve=resolved.get("reasoning_preserve"),
        spec_type=resolved.get("spec_type"),
    )

    timestamp = datetime.now(UTC).replace(microsecond=0).isoformat()
    runtime_command_document = build_runtime_command_document(
        config=config,
        resolved=resolved,
        suite_id=loaded_suite["suite_id"],
        suite_version=str(loaded_suite["suite_version"]),
        timestamp_utc=timestamp,
    )
    runtime_command_path = out / RUNTIME_COMMAND_FILENAME
    write_json(runtime_command_path, runtime_command_document)
    backend_provenance = collect_backend_provenance(resolved["llama_cli"])
    if backend_provenance["status"] == "unavailable":
        console.print(f"[yellow]{backend_provenance['warning']}[/yellow]")
    backend_provenance.update(discover_llama_runtime_identity(resolved["llama_cli"]))
    if backend_provenance.get("discovery_warning"):
        console.print(f"[yellow]{backend_provenance['discovery_warning']}[/yellow]")
    run_id = out.name
    prompt_results: list[dict] = []
    redacted_command: list[str] | None = None
    prompt_command_entries: list[dict[str, Any]] = []

    console.print(
        f"Running [bold]{len(selected_prompts)}[/bold] prompt(s) "
        f"with model [bold]{resolved['model_id']}[/bold] "
        f"at ctx [bold]{resolved['ctx']}[/bold]"
    )

    for index, prompt_meta in enumerate(selected_prompts, start=1):
        prompt_id = prompt_meta["id"]
        prompt_path = suite / prompt_meta["file"]
        prompt_text = prompt_path.read_text(encoding="utf-8").strip()
        combined_prompt = build_combined_prompt(system_prompt, prompt_text)

        raw_prompt_path = out / "raw" / f"{prompt_id}.prompt.md"
        raw_output_path = out / "raw" / f"{prompt_id}.output.txt"
        cleaned_output_path = out / "cleaned" / f"{prompt_id}.output.txt"
        stderr_log_path = out / "logs" / f"{prompt_id}.stderr.log"

        write_text(raw_prompt_path, combined_prompt)

        console.print(f"[{index}/{len(selected_prompts)}] Running {prompt_id}")
        run_result = run_llama_cpp(config, combined_prompt)

        if redacted_command is None:
            redacted_command = build_redacted_command(
                run_result.command,
                resolved["model_path"],
            )
        raw_prompt_relative_path = str(raw_prompt_path.relative_to(out))
        prompt_transport = getattr(run_result, "prompt_transport", None)
        if not isinstance(prompt_transport, dict):
            prompt_transport = {"mode": "unknown"}
        prompt_transport = {
            **prompt_transport,
            "raw_prompt_path": raw_prompt_relative_path,
        }
        prompt_command_entries.append(
            {
                "prompt_id": prompt_id,
                "command_argv": build_redacted_command(
                    run_result.command,
                    resolved["model_path"],
                ),
                "prompt_transport": prompt_transport,
            }
        )

        write_text(raw_output_path, run_result.stdout)
        write_text(cleaned_output_path, clean_llama_output(run_result.stdout))
        write_text(stderr_log_path, run_result.stderr)
        native_execution_evidence = build_native_execution_evidence(
            prompt_id=prompt_id,
            elapsed_seconds=getattr(run_result, "elapsed_seconds", None),
            stdout=run_result.stdout,
            stderr=run_result.stderr,
            exit_status=run_result.exit_status,
            timed_out=getattr(run_result, "timed_out", False),
            launch_error=getattr(run_result, "launch_error", None),
        )
        native_execution_path = (
            out / "native" / f"{prompt_id.replace('/', '__')}.execution.json"
        )
        write_json(native_execution_path, native_execution_evidence)

        vram_samples = getattr(run_result, "vram_samples", [])
        vram_summary = getattr(run_result, "vram_summary", None)

        vram_samples_path = None
        if vram_samples:
            vram_samples_path = (
                out / "vram" / f"{prompt_id.replace('/', '__')}.samples.json"
            )
            write_json(
                vram_samples_path,
                {
                    "schema_version": "llmgauge.vram.samples.v0",
                    "prompt_id": prompt_id,
                    "samples": vram_samples,
                },
            )

        metrics = parse_llama_metrics(run_result.stdout + "\n" + run_result.stderr)
        status = "completed" if run_result.exit_status == 0 else "failed"
        vram_guardrails = build_vram_guardrails(
            vram_summary,
            min_headroom_warn_mib=resolved["vram_min_headroom_warn_mib"],
        )

        prompt_entry = {
            "prompt_id": prompt_id,
            "title": prompt_meta.get("title", prompt_id),
            "category": prompt_meta.get("category"),
            "status": status,
            "raw_prompt_path": raw_prompt_relative_path,
            "raw_output_path": str(raw_output_path.relative_to(out)),
            "cleaned_output_path": str(cleaned_output_path.relative_to(out)),
            "stderr_log_path": str(stderr_log_path.relative_to(out)),
            "metrics": metrics,
            "vram": vram_summary,
            "vram_samples_path": str(vram_samples_path.relative_to(out))
            if vram_samples_path is not None
            else None,
            "native_execution_evidence_path": str(
                native_execution_path.relative_to(out)
            ),
            "_area4_native_execution_evidence": native_execution_evidence,
            "prompt_transport": prompt_transport,
            "vram_guardrails": vram_guardrails,
            "score": None,
            "failure_labels": [],
            "notes": "",
            "exit_status": run_result.exit_status,
            "error": None
            if run_result.exit_status == 0
            else "llama-cli exited nonzero",
        }
        coding_evidence = build_prompt_evidence(
            normalized_suite,
            normalized_prompts[prompt_id],
            run_result.stdout,
            generation_failed=status == "failed",
        )
        if coding_evidence is not None:
            prompt_entry["coding_core"] = coding_evidence
        prompt_results.append(prompt_entry)

    runtime_command_document["prompt_commands"] = prompt_command_entries
    if len(prompt_command_entries) == 1:
        runtime_command_document["command_argv"] = prompt_command_entries[0][
            "command_argv"
        ]
        runtime_command_document["command_argv_scope"] = "single_prompt_invocation"
    else:
        runtime_command_document["command_argv_scope"] = (
            "template; inspect prompt_commands for exact per-prompt transport"
        )
    write_json(runtime_command_path, runtime_command_document)

    completed_count = sum(1 for item in prompt_results if item["status"] == "completed")
    failed_count = sum(1 for item in prompt_results if item["status"] == "failed")
    run_status = "completed" if failed_count == 0 else "failed"
    profile = resolved["profile"]
    model_provenance = collect_model_provenance(
        resolved["model_path"],
        source_type=resolved["model_source"],
    )
    if model_provenance["status"] == "unavailable":
        console.print(f"[yellow]{model_provenance['warning']}[/yellow]")

    result = {
        "schema_version": "llmgauge.result.v0",
        "llmgauge_version": __version__,
        "run": {
            "run_id": run_id,
            "timestamp_utc": timestamp,
            "status": run_status,
            "result_dir": str(out),
        },
        "model": {
            "model_id": resolved["model_id"],
            "model_source": resolved["model_source"],
            "model_profile": resolved["model_profile"],
            "label": profile.get("label"),
            "family": profile.get("family"),
            "role": profile.get("role"),
            "quant": profile.get("quant"),
            "model_path": "redacted",
            "model_path_policy": "redacted",
            "provenance": model_provenance,
        },
        "runtime": {
            "backend": "llama.cpp",
            "llama_cli": str(resolved["llama_cli"]),
            "ctx_size": resolved["ctx"],
            "max_tokens": resolved["max_tokens"],
            "temperature": resolved["temp"],
            "top_p": resolved["top_p"],
            "top_k": resolved.get("top_k"),
            "top_k_state": (
                "explicit" if resolved.get("top_k") is not None else "runtime_default"
            ),
            "seed": resolved.get("seed"),
            "seed_state": (
                "explicit" if resolved.get("seed") is not None else "runtime_default"
            ),
            "batch_size": resolved["batch"],
            "parallel_sequences": 1,
            "ubatch_size": resolved["ubatch"],
            "gpu_layers": resolved["gpu_layers"],
            "kv_offload": "requested_on",
            "cache_type_k": resolved.get("cache_type_k"),
            "cache_type_k_state": (
                "explicit"
                if resolved.get("cache_type_k") is not None
                else "runtime_default"
            ),
            "cache_type_v": resolved.get("cache_type_v"),
            "cache_type_v_state": (
                "explicit"
                if resolved.get("cache_type_v") is not None
                else "runtime_default"
            ),
            "flash_attn": resolved["flash_attn"],
            "runtime_label": resolved["runtime_label"],
            "reasoning_mode": resolved["reasoning_mode"],
            "reasoning_effort": resolved.get("reasoning_effort"),
            "reasoning_effort_state": (
                "explicit"
                if resolved.get("reasoning_effort") is not None
                else "runtime_default"
            ),
            "reasoning_budget": resolved.get("reasoning_budget"),
            "reasoning_budget_state": (
                "explicit"
                if resolved.get("reasoning_budget") is not None
                else "runtime_default"
            ),
            "fit": resolved.get("fit"),
            "fit_state": (
                "explicit" if resolved.get("fit") is not None else "runtime_default"
            ),
            "reasoning_preserve": resolved.get("reasoning_preserve"),
            "reasoning_preserve_state": (
                "explicit"
                if resolved.get("reasoning_preserve") is not None
                else "runtime_default"
            ),
            "spec_type": resolved.get("spec_type"),
            "spec_type_state": (
                "explicit"
                if resolved.get("spec_type") is not None
                else "runtime_default"
            ),
            "runtime_command_captured": True,
            "runtime_command_path": str(runtime_command_path.relative_to(out)),
            "vram_min_headroom_warn_mib": resolved["vram_min_headroom_warn_mib"],
            "command": redacted_command or [],
            "config_path": str(resolved["config_path"])
            if resolved["config_path"]
            else None,
            "model_profiles_path": str(resolved["model_profiles_path"])
            if resolved["model_profiles_path"]
            else None,
            "backend_provenance": backend_provenance,
        },
        "suite": build_result_suite_metadata(
            loaded_suite=loaded_suite,
            resolved_suite=resolved_suite,
            normalized_suite=normalized_suite,
            prompt_count=len(prompt_results),
            include=include,
            only=only,
        ),
        "results": prompt_results,
        "summary": {
            "completed": completed_count,
            "failed": failed_count,
            "manual_score_total": None,
            "manual_score_max": None,
            "failure_labels": {},
        },
    }
    runtime_neutral_metrics, failure_taxonomy = build_area4_evidence(
        prompt_results=prompt_results,
        suite=result["suite"],
        runtime=result["runtime"],
    )
    for prompt_entry in prompt_results:
        prompt_entry.pop("_area4_native_execution_evidence")
    result["runtime_neutral_metrics"] = runtime_neutral_metrics
    result["failure_taxonomy"] = failure_taxonomy

    return _finalize_run_result(
        out=out,
        result=result,
        failed_count=failed_count,
        fail_on_failed_prompts=fail_on_failed_prompts,
    )


def execute_vllm_run(
    *,
    suite: Path,
    only: str | None,
    include: str,
    profile: str | None = None,
    resolved: dict[str, Any],
    out: Path,
    fail_on_failed_prompts: bool,
) -> dict[str, Any]:
    """Execute prompts against an operator-managed local vLLM server."""
    resolved_suite = resolve_suite_path(suite)
    suite = resolved_suite
    loaded_suite, selected_prompts, normalized_suite = load_run_suite(
        suite,
        only=only,
        include=include,
        profile=profile,
    )
    normalized_prompts = {
        prompt.id: prompt for prompt in normalized_suite.selected_prompts
    }
    system_prompt = load_system_prompt()

    prepare_result_dir(out)
    (out / "request").mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(UTC).replace(microsecond=0).isoformat()
    run_id = out.name
    vllm_config = VllmExternalConfig(
        endpoint_url=str(resolved["vllm_endpoint"]),
        served_model=str(resolved["served_model"]),
        max_tokens=int(resolved["max_tokens"]),
        temperature=float(resolved["temp"]),
        top_p=float(resolved["top_p"]),
        connect_timeout=float(resolved["connect_timeout"]),
        request_timeout=float(resolved["request_timeout"]),
        max_response_bytes=int(resolved["max_response_bytes"]),
        ctx_size=int(resolved["ctx"]),
    )

    console.print(
        f"Running [bold]{len(selected_prompts)}[/bold] prompt(s) "
        f"via external vLLM model [bold]{resolved['served_model']}[/bold] "
        f"(backend=vllm, operator-managed server)"
    )

    readiness = check_readiness_and_model(vllm_config)
    endpoint_identity = readiness.endpoint_identity or {}
    observed_fingerprints: list[str] = []
    runtime_evidence = build_runtime_evidence_document(
        config=vllm_config,
        readiness=readiness,
        endpoint_identity=endpoint_identity,
        observed_system_fingerprints=observed_fingerprints,
    )
    runtime_evidence_path = out / VLLM_RUNTIME_EVIDENCE_FILENAME
    write_json(runtime_evidence_path, runtime_evidence)

    prompt_results: list[dict] = []

    if not readiness.success:
        # Fail all selected prompts deterministically without evaluation requests.
        for prompt_meta in selected_prompts:
            prompt_id = prompt_meta["id"]
            prompt_path = suite / prompt_meta["file"]
            prompt_text = prompt_path.read_text(encoding="utf-8").strip()
            combined_prompt = build_combined_prompt(system_prompt, prompt_text)

            raw_prompt_path = out / "raw" / f"{prompt_id}.prompt.md"
            raw_output_path = out / "raw" / f"{prompt_id}.output.txt"
            cleaned_output_path = out / "cleaned" / f"{prompt_id}.output.txt"
            stderr_log_path = out / "logs" / f"{prompt_id}.stderr.log"
            request_evidence_path = (
                out / "request" / f"{prompt_id.replace('/', '__')}.json"
            )

            write_text(raw_prompt_path, combined_prompt)
            write_text(raw_output_path, "")
            write_text(cleaned_output_path, "")
            write_text(stderr_log_path, format_failure_log(readiness))
            write_json(
                request_evidence_path,
                {
                    "schema_version": "llmgauge.vllm_request_evidence.v0",
                    "lifecycle_ownership": "external_operator",
                    "skipped": True,
                    "skip_reason": "readiness_or_model_check_failed",
                    "failure_class": readiness.failure_class,
                    "failure_detail": readiness.failure_detail,
                    "endpoint_identity": endpoint_identity,
                },
            )

            prompt_entry = {
                "prompt_id": prompt_id,
                "title": prompt_meta.get("title", prompt_id),
                "category": prompt_meta.get("category"),
                "status": "failed",
                "raw_prompt_path": str(raw_prompt_path.relative_to(out)),
                "raw_output_path": str(raw_output_path.relative_to(out)),
                "cleaned_output_path": str(cleaned_output_path.relative_to(out)),
                "stderr_log_path": str(stderr_log_path.relative_to(out)),
                "request_evidence_path": str(request_evidence_path.relative_to(out)),
                "metrics": build_vllm_metrics(VllmRequestResult(success=False)),
                "vram": None,
                "vram_samples_path": None,
                "vram_guardrails": None,
                "score": None,
                "failure_labels": [],
                "notes": "",
                "exit_status": 1,
                "error": readiness.failure_detail or readiness.failure_class,
                "failure_class": readiness.failure_class,
                "failure_detail": readiness.failure_detail,
                "finish_reason": None,
            }
            coding_evidence = build_prompt_evidence(
                normalized_suite,
                normalized_prompts[prompt_id],
                None,
                generation_failed=True,
            )
            if coding_evidence is not None:
                prompt_entry["coding_core"] = coding_evidence
            prompt_results.append(prompt_entry)
    else:
        for index, prompt_meta in enumerate(selected_prompts, start=1):
            prompt_id = prompt_meta["id"]
            prompt_path = suite / prompt_meta["file"]
            prompt_text = prompt_path.read_text(encoding="utf-8").strip()
            # Human-readable combined form for compatibility with existing raw
            # prompt artifacts. Chat request uses separate system/user roles and
            # is not claimed byte-identical to this combined text.
            combined_prompt = build_combined_prompt(system_prompt, prompt_text)

            raw_prompt_path = out / "raw" / f"{prompt_id}.prompt.md"
            raw_output_path = out / "raw" / f"{prompt_id}.output.txt"
            cleaned_output_path = out / "cleaned" / f"{prompt_id}.output.txt"
            stderr_log_path = out / "logs" / f"{prompt_id}.stderr.log"
            request_evidence_path = (
                out / "request" / f"{prompt_id.replace('/', '__')}.json"
            )

            write_text(raw_prompt_path, combined_prompt)

            console.print(
                f"[{index}/{len(selected_prompts)}] Requesting {prompt_id} "
                f"(non-streaming chat.completions)"
            )
            request_result = run_chat_completion(
                vllm_config,
                prompt=prompt_text,
                system_prompt=system_prompt,
            )

            write_text(raw_output_path, request_result.generated_text)
            write_text(
                cleaned_output_path,
                clean_llama_output(request_result.generated_text),
            )
            if request_result.success and not request_result.incomplete_usage:
                write_text(stderr_log_path, "vllm request completed\n")
            else:
                write_text(stderr_log_path, format_failure_log(request_result))

            write_json(
                request_evidence_path,
                request_result.request_evidence
                or {
                    "schema_version": "llmgauge.vllm_request_evidence.v0",
                    "lifecycle_ownership": "external_operator",
                    "failure_class": request_result.failure_class,
                    "failure_detail": request_result.failure_detail,
                    "endpoint_identity": request_result.endpoint_identity,
                },
            )

            if request_result.system_fingerprint:
                observed_fingerprints.append(request_result.system_fingerprint)

            # incomplete_usage_metadata: output may still be usable; mark completed
            # with explicit incomplete usage rather than inventing token counts.
            if request_result.success:
                status = "completed"
                exit_status = 0
                error = (
                    "incomplete_usage_metadata"
                    if request_result.incomplete_usage
                    else None
                )
            else:
                status = "failed"
                exit_status = 1
                error = request_result.failure_detail or request_result.failure_class

            prompt_entry: dict[str, Any] = {
                "prompt_id": prompt_id,
                "title": prompt_meta.get("title", prompt_id),
                "category": prompt_meta.get("category"),
                "status": status,
                "raw_prompt_path": str(raw_prompt_path.relative_to(out)),
                "raw_output_path": str(raw_output_path.relative_to(out)),
                "cleaned_output_path": str(cleaned_output_path.relative_to(out)),
                "stderr_log_path": str(stderr_log_path.relative_to(out)),
                "request_evidence_path": str(request_evidence_path.relative_to(out)),
                "metrics": build_vllm_metrics(request_result),
                "vram": None,
                "vram_samples_path": None,
                "vram_guardrails": None,
                "score": None,
                "failure_labels": [],
                "notes": "",
                "exit_status": exit_status,
                "error": error,
                "failure_class": request_result.failure_class,
                "failure_detail": request_result.failure_detail,
                "finish_reason": request_result.finish_reason,
                "observed_served_model": request_result.observed_model,
            }
            if request_result.system_fingerprint is not None:
                prompt_entry["system_fingerprint"] = request_result.system_fingerprint
            if request_result.system_fingerprint_status is not None:
                prompt_entry["system_fingerprint_status"] = (
                    request_result.system_fingerprint_status
                )
            coding_evidence = build_prompt_evidence(
                normalized_suite,
                normalized_prompts[prompt_id],
                request_result.generated_text,
                generation_failed=status == "failed",
            )
            if coding_evidence is not None:
                prompt_entry["coding_core"] = coding_evidence
            prompt_results.append(prompt_entry)

    # Rewrite runtime evidence with ordered-unique observed fingerprints.
    runtime_evidence = build_runtime_evidence_document(
        config=vllm_config,
        readiness=readiness,
        endpoint_identity=endpoint_identity,
        observed_system_fingerprints=observed_fingerprints,
    )
    write_json(runtime_evidence_path, runtime_evidence)

    completed_count = sum(1 for item in prompt_results if item["status"] == "completed")
    failed_count = sum(1 for item in prompt_results if item["status"] == "failed")
    run_status = "completed" if failed_count == 0 else "failed"
    profile = resolved["profile"]
    observed_vllm_version = runtime_evidence.get("vllm_version") or "unknown"
    observed_server_state = runtime_evidence.get("server_state") or "unknown"

    # Never feed a local path into GGUF provenance for vLLM; directory-model
    # provenance remains deferred and must not misrepresent the served model.
    model_provenance = {
        "source_type": resolved["model_source"],
        "filename": None,
        "file_size_bytes": None,
        "sha256": None,
        "public_fingerprint": None,
        "status": "unavailable",
        "warning": (
            "Directory-model and GGUF provenance are deferred for backend=vllm; "
            "identity is the requested/observed served-model name only"
        ),
        "served_model": resolved["served_model"],
        "provenance_kind": "served_model_only",
    }

    discovery_warning: str | None
    if readiness.success and observed_vllm_version != "unknown":
        discovery_warning = (
            "vLLM version observed from server /version; kernel, device, and "
            "launch-configuration metadata remain unknown for this slice"
        )
        discovery_status = "partial"
    elif readiness.success:
        discovery_warning = (
            "Server /version was unavailable or unparseable; kernel and device "
            "metadata remain unknown for this slice"
        )
        discovery_status = "partial"
    else:
        discovery_warning = readiness.failure_detail or readiness.failure_class
        discovery_status = "unavailable"

    backend_provenance = {
        "backend_name": "vllm",
        "lifecycle_ownership": "external_operator",
        "endpoint_identity": endpoint_identity,
        "requested_served_model": resolved["served_model"],
        "observed_served_model": readiness.observed_model,
        "vllm_version": observed_vllm_version,
        "vllm_version_source": runtime_evidence.get("vllm_version_source"),
        "server_state": observed_server_state,
        "observed_system_fingerprints": list(
            runtime_evidence.get("observed_system_fingerprints") or []
        ),
        "status": "available" if readiness.success else "unavailable",
        "warning": None
        if readiness.success
        else (readiness.failure_detail or readiness.failure_class),
        "discovery_status": discovery_status,
        "discovery_warning": discovery_warning,
    }

    result = {
        "schema_version": "llmgauge.result.v0",
        "llmgauge_version": __version__,
        "run": {
            "run_id": run_id,
            "timestamp_utc": timestamp,
            "status": run_status,
            "result_dir": str(out),
        },
        "model": {
            "model_id": resolved["model_id"],
            "model_source": resolved["model_source"],
            "model_profile": resolved["model_profile"],
            "label": profile.get("label"),
            "family": profile.get("family"),
            "role": profile.get("role"),
            "quant": profile.get("quant"),
            "model_path": "redacted",
            "model_path_policy": "redacted",
            "served_model": resolved["served_model"],
            "provenance": model_provenance,
        },
        "runtime": {
            "backend": "vllm",
            "lifecycle_ownership": "external_operator",
            "endpoint_identity": endpoint_identity,
            "requested_served_model": resolved["served_model"],
            "observed_served_model": readiness.observed_model,
            "connect_timeout_seconds": resolved["connect_timeout"],
            "request_timeout_seconds": resolved["request_timeout"],
            "max_response_bytes": resolved["max_response_bytes"],
            "ctx_size": resolved["ctx"],
            "max_tokens": resolved["max_tokens"],
            "temperature": resolved["temp"],
            "top_p": resolved["top_p"],
            "runtime_label": resolved["runtime_label"],
            "reasoning_mode": resolved["reasoning_mode"],
            "runtime_command_captured": False,
            "runtime_command_path": None,
            "vllm_runtime_evidence_captured": True,
            "vllm_runtime_evidence_path": str(runtime_evidence_path.relative_to(out)),
            "vllm_version": observed_vllm_version,
            "server_state": observed_server_state,
            "observed_system_fingerprints": list(
                runtime_evidence.get("observed_system_fingerprints") or []
            ),
            "vram_min_headroom_warn_mib": resolved["vram_min_headroom_warn_mib"],
            "command": [],
            "config_path": str(resolved["config_path"])
            if resolved["config_path"]
            else None,
            "model_profiles_path": str(resolved["model_profiles_path"])
            if resolved["model_profiles_path"]
            else None,
            "backend_provenance": backend_provenance,
            "proxy_bypass_policy": runtime_evidence.get("proxy_bypass_policy"),
            "streaming": False,
            "authentication": "none",
        },
        "suite": build_result_suite_metadata(
            loaded_suite=loaded_suite,
            resolved_suite=resolved_suite,
            normalized_suite=normalized_suite,
            prompt_count=len(prompt_results),
            include=include,
            only=only,
        ),
        "results": prompt_results,
        "summary": {
            "completed": completed_count,
            "failed": failed_count,
            "manual_score_total": None,
            "manual_score_max": None,
            "failure_labels": {},
        },
    }

    return _finalize_run_result(
        out=out,
        result=result,
        failed_count=failed_count,
        fail_on_failed_prompts=fail_on_failed_prompts,
    )


def print_ladder_preflight(
    *,
    suite: Path,
    loaded_suite: dict[str, Any],
    only: str | None,
    include: str,
    resolved: dict[str, Any],
    contexts: list[int],
    allow_extreme_context: bool,
    out: Path | None,
    auto_name: bool,
    runs_root: Path,
    run_name: str | None,
    default_run_name: str,
) -> None:
    selected_prompts = select_prompts(loaded_suite, only, include)

    if out is not None:
        output_plan = str(out)

        def child_output_plan(ctx: int) -> str:
            return str(out / f"ctx-{ctx}")

    elif auto_name:
        ladder_name = run_name or default_run_name
        output_plan = f"auto-name under {runs_root} with ladder name {ladder_name}"

        def child_output_plan(ctx: int) -> str:
            return f"<auto ladder dir>/ctx-{ctx}"

    else:
        output_plan = (
            "not required for --dry-run; real ladder runs require --out or --auto-name"
        )

        def child_output_plan(ctx: int) -> str:
            return "not required for --dry-run"

    selection = f"only={only}" if only else f"include={include}"

    table = Table(title="LLMGauge Run Ladder Dry Run")
    table.add_column("Field", no_wrap=True)
    table.add_column("Value")

    table.add_row("Suite", str(loaded_suite.get("suite_id", suite)))
    table.add_row("Suite path", str(suite))
    table.add_row("Selection", selection)
    table.add_row("Prompt count", str(len(selected_prompts)))
    table.add_row("Model ID", str(resolved["model_id"]))
    table.add_row("Model profile", str(resolved["model_profile"]))
    table.add_row("Config", str(resolved["config_path"]))
    table.add_row("Model profiles", str(resolved["model_profiles_path"]))
    table.add_row("Model path", str(resolved["model_path"]))
    table.add_row("llama-cli", str(resolved["llama_cli"]))
    table.add_row("Context ladder", ", ".join(str(ctx) for ctx in contexts))
    table.add_row("Max tokens", str(resolved["max_tokens"]))
    table.add_row("Temperature", str(resolved["temp"]))
    table.add_row("Top-p", str(resolved["top_p"]))
    table.add_row("Batch", str(resolved["batch"]))
    table.add_row("UBatch", str(resolved["ubatch"]))
    table.add_row("GPU layers", str(resolved["gpu_layers"]))
    table.add_row("Flash attention", str(resolved["flash_attn"]))
    table.add_row("Runtime label", str(resolved["runtime_label"] or "unknown"))
    table.add_row("Extreme context opt-in", str(allow_extreme_context))
    table.add_row("Output plan", output_plan)

    console.print(table)

    context_table = Table(title="Planned Context Runs")
    context_table.add_column("Context", no_wrap=True)
    context_table.add_column("Child output plan")

    for ctx in contexts:
        context_table.add_row(str(ctx), child_output_plan(ctx))

    console.print(context_table)

    prompt_table = Table(title="Selected Prompts")
    prompt_table.add_column("Prompt", no_wrap=True)
    prompt_table.add_column("Category", no_wrap=True)
    prompt_table.add_column("Title")

    for prompt in selected_prompts:
        prompt_table.add_row(
            str(prompt.get("id", "")),
            str(prompt.get("category", "")),
            str(prompt.get("title", prompt.get("id", ""))),
        )

    console.print(prompt_table)
    console.print(
        "[bold green]Ladder dry run complete[/bold green]: llama.cpp was not "
        "launched and no ladder or result directories were created."
    )


def read_attempt_artifact(result_dir: Path, relative_path: Any) -> str:
    if not isinstance(relative_path, str) or not relative_path:
        return ""

    path = result_dir / relative_path
    if not path.exists():
        return ""

    return path.read_text(encoding="utf-8", errors="replace")


def build_fit_attempt_record_from_result(
    *,
    attempt: dict[str, Any],
    result: dict[str, Any],
    result_dir: Path,
) -> dict[str, Any]:
    prompt_results = result.get("results", [])
    if not isinstance(prompt_results, list):
        prompt_results = []

    failed_prompt = next(
        (
            prompt
            for prompt in prompt_results
            if isinstance(prompt, dict) and prompt.get("status") == "failed"
        ),
        None,
    )

    first_prompt = next(
        (prompt for prompt in prompt_results if isinstance(prompt, dict)),
        None,
    )
    source_prompt = failed_prompt or first_prompt or {}

    run = result.get("run", {})
    run_status = run.get("status") if isinstance(run, dict) else None

    if failed_prompt is None and run_status == "completed":
        exit_status = 0
    else:
        raw_exit_status = source_prompt.get("exit_status")
        exit_status = raw_exit_status if isinstance(raw_exit_status, int) else 1

    stdout = read_attempt_artifact(result_dir, source_prompt.get("raw_output_path"))
    stderr = read_attempt_artifact(result_dir, source_prompt.get("stderr_log_path"))

    if not stderr and source_prompt.get("error"):
        stderr = str(source_prompt["error"])

    vram_summary = source_prompt.get("vram")
    if not isinstance(vram_summary, dict):
        vram_summary = None

    return build_fit_attempt_record(
        attempt_id=str(attempt["attempt_id"]),
        ctx_size=int(attempt["ctx_size"]),
        batch_size=int(attempt["batch_size"]),
        ubatch_size=int(attempt["ubatch_size"]),
        gpu_layers=int(attempt["gpu_layers"]),
        exit_status=exit_status,
        stdout=stdout,
        stderr=stderr,
        result_dir=str(result_dir),
        vram_summary=vram_summary,
    )


def print_fit_ladder_preflight(
    *,
    suite: Path,
    loaded_suite: dict[str, Any],
    only: str | None,
    include: str,
    resolved: dict[str, Any],
    attempts: list[dict[str, Any]],
    out: Path | None,
    auto_name: bool,
    runs_root: Path,
    run_name: str | None,
    default_run_name: str,
) -> None:
    selected_prompts = select_prompts(loaded_suite, only, include)

    if out is not None:
        output_plan = str(out)
    elif auto_name:
        output_plan = (
            f"auto-name under {runs_root} with fit-ladder name "
            f"{run_name or default_run_name}"
        )
    else:
        output_plan = "not required for --dry-run; real fit-ladder runs require --out or --auto-name"

    selection = f"only={only}" if only else f"include={include}"

    table = Table(title="LLMGauge Fit Ladder Dry Run")
    table.add_column("Field", no_wrap=True)
    table.add_column("Value")

    table.add_row("Suite", str(loaded_suite.get("suite_id", suite)))
    table.add_row("Suite path", str(suite))
    table.add_row("Selection", selection)
    table.add_row("Prompt count", str(len(selected_prompts)))
    table.add_row("Model ID", str(resolved["model_id"]))
    table.add_row("Model profile", str(resolved["model_profile"]))
    table.add_row("Config", str(resolved["config_path"]))
    table.add_row("Model profiles", str(resolved["model_profiles_path"]))
    table.add_row("Model path", str(resolved["model_path"]))
    table.add_row("llama-cli", str(resolved["llama_cli"]))
    table.add_row("Max tokens", str(resolved["max_tokens"]))
    table.add_row("Temperature", str(resolved["temp"]))
    table.add_row("Top-p", str(resolved["top_p"]))
    table.add_row("GPU layers", str(resolved["gpu_layers"]))
    table.add_row("Flash attention", str(resolved["flash_attn"]))
    table.add_row("Runtime label", str(resolved["runtime_label"] or "unknown"))
    table.add_row("Output plan", output_plan)

    console.print(table)

    attempt_table = Table(title="Planned Fit Attempts")
    attempt_table.add_column("Attempt", no_wrap=True)
    attempt_table.add_column("Context", no_wrap=True)
    attempt_table.add_column("Batch", no_wrap=True)
    attempt_table.add_column("UBatch", no_wrap=True)
    attempt_table.add_column("Fallback axes")

    for attempt in attempts:
        attempt_table.add_row(
            str(attempt["attempt_id"]),
            str(attempt["ctx_size"]),
            str(attempt["batch_size"]),
            str(attempt["ubatch_size"]),
            ", ".join(attempt["fallback_axes"]) or "none",
        )

    console.print(attempt_table)
    console.print(
        "[bold green]Fit ladder dry run complete[/bold green]: llama.cpp was not "
        "launched and no fit-ladder directories were created."
    )
