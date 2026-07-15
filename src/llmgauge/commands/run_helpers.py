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
from llmgauge.core.config import (
    coalesce,
    get_config_value,
    load_llmgauge_config,
    load_model_profiles,
    resolve_model_profile,
)
from llmgauge.core.fit_ladder import build_fit_attempt_record
from llmgauge.core.identity import (
    collect_backend_provenance,
    collect_model_provenance,
    discover_llama_runtime_identity,
)
from llmgauge.core.metrics import parse_llama_metrics
from llmgauge.core.output_cleaning import clean_llama_output
from llmgauge.core.output_paths import build_auto_output_dir
from llmgauge.core.reports import build_markdown_report
from llmgauge.core.run_fingerprint import attach_run_fingerprint
from llmgauge.core.runtime_command import (
    RUNTIME_COMMAND_FILENAME,
    build_runtime_command_document,
    format_command_preview,
    resolve_model_source,
    resolve_reasoning_mode,
)
from llmgauge.core.suite import load_suite
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
    return [arg if arg != str(model_path) else "REDACTED_MODEL_PATH" for arg in command]


def optional_nonnegative_int(value: Any, *, field_name: str) -> int | None:
    if value is None:
        return None

    resolved = int(value)
    if resolved < 0:
        raise typer.BadParameter(f"{field_name} must be non-negative")

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
    batch: int | None,
    ubatch: int | None,
    gpu_layers: int | None,
    flash_attn: str | None = None,
    runtime_label: str | None = None,
    reasoning_mode: str | None = None,
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
            raise typer.BadParameter(
                f"Invalid vLLM endpoint ({exc.detail})"
            ) from exc

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
                _optional_positive_float(
                    connect_timeout, field_name="connect_timeout"
                ),
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
                _optional_positive_float(
                    request_timeout, field_name="request_timeout"
                ),
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
        "batch": resolved_batch,
        "ubatch": resolved_ubatch,
        "gpu_layers": resolved_gpu_layers,
        "flash_attn": resolved_flash_attn,
        "runtime_label": resolved_runtime_label,
        "reasoning_mode": resolved_reasoning_mode,
        "model_source": resolved_model_source,
        "vram_min_headroom_warn_mib": resolved_vram_min_headroom_warn_mib,
    }


def print_run_preflight(
    *,
    suite: Path,
    only: str | None,
    include: str,
    resolved: dict[str, Any],
    out: Path | None,
    auto_name: bool,
    runs_root: Path,
    run_name: str | None,
) -> None:
    resolved_suite = resolve_suite_path(suite)
    loaded_suite = load_suite(resolved_suite)
    selected_prompts = select_prompts(loaded_suite, only, include)

    if out is not None:
        output_plan = str(out)
    elif auto_name:
        default_run_name = f"{resolved['model_id']}-{suite.name}"
        output_plan = (
            f"auto-name under {runs_root} "
            f"with run name {run_name or default_run_name}"
        )
    else:
        output_plan = (
            "not required for --dry-run; real runs require --out or --auto-name"
        )

    selection = f"only={only}" if only else f"include={include}"

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
        table.add_row("Batch", str(resolved["batch"]))
        table.add_row("UBatch", str(resolved["ubatch"]))
        table.add_row("GPU layers", str(resolved["gpu_layers"]))
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
            batch_size=resolved["batch"],
            ubatch_size=resolved["ubatch"],
            gpu_layers=resolved["gpu_layers"],
            flash_attn=resolved["flash_attn"],
            reasoning_mode=resolved["reasoning_mode"],
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


def _finalize_run_result(
    *,
    out: Path,
    result: dict[str, Any],
    failed_count: int,
    fail_on_failed_prompts: bool,
) -> dict[str, Any]:
    attach_run_fingerprint(out, result)
    write_json(out / "llmgauge-result.json", result)
    write_text(out / "report.md", build_markdown_report(result))

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
    resolved: dict[str, Any],
    out: Path,
    fail_on_failed_prompts: bool,
) -> dict[str, Any]:
    if (resolved.get("backend") or "llama.cpp") == "vllm":
        return execute_vllm_run(
            suite=suite,
            only=only,
            include=include,
            resolved=resolved,
            out=out,
            fail_on_failed_prompts=fail_on_failed_prompts,
        )

    resolved_suite = resolve_suite_path(suite)
    suite = resolved_suite
    loaded_suite = load_suite(suite)
    selected_prompts = select_prompts(loaded_suite, only, include)
    system_prompt = load_system_prompt()

    prepare_result_dir(out)

    config = LlamaCppRunConfig(
        llama_cli=resolved["llama_cli"],
        model_path=resolved["model_path"],
        ctx_size=resolved["ctx"],
        max_tokens=resolved["max_tokens"],
        temperature=resolved["temp"],
        top_p=resolved["top_p"],
        batch_size=resolved["batch"],
        ubatch_size=resolved["ubatch"],
        gpu_layers=resolved["gpu_layers"],
        flash_attn=resolved["flash_attn"],
        reasoning_mode=resolved["reasoning_mode"],
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
    backend_provenance.update(
        discover_llama_runtime_identity(resolved["llama_cli"])
    )
    if backend_provenance.get("discovery_warning"):
        console.print(f"[yellow]{backend_provenance['discovery_warning']}[/yellow]")
    run_id = out.name
    prompt_results: list[dict] = []
    redacted_command: list[str] | None = None

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

        write_text(raw_output_path, run_result.stdout)
        write_text(cleaned_output_path, clean_llama_output(run_result.stdout))
        write_text(stderr_log_path, run_result.stderr)

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

        prompt_results.append(
            {
                "prompt_id": prompt_id,
                "title": prompt_meta.get("title", prompt_id),
                "category": prompt_meta.get("category"),
                "status": status,
                "raw_prompt_path": str(raw_prompt_path.relative_to(out)),
                "raw_output_path": str(raw_output_path.relative_to(out)),
                "cleaned_output_path": str(cleaned_output_path.relative_to(out)),
                "stderr_log_path": str(stderr_log_path.relative_to(out)),
                "metrics": metrics,
                "vram": vram_summary,
                "vram_samples_path": str(vram_samples_path.relative_to(out))
                if vram_samples_path is not None
                else None,
                "vram_guardrails": vram_guardrails,
                "score": None,
                "failure_labels": [],
                "notes": "",
                "exit_status": run_result.exit_status,
                "error": None
                if run_result.exit_status == 0
                else "llama-cli exited nonzero",
            }
        )

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
            "batch_size": resolved["batch"],
            "ubatch_size": resolved["ubatch"],
            "gpu_layers": resolved["gpu_layers"],
            "flash_attn": resolved["flash_attn"],
            "runtime_label": resolved["runtime_label"],
            "reasoning_mode": resolved["reasoning_mode"],
            "runtime_command_captured": True,
            "runtime_command_path": str(
                runtime_command_path.relative_to(out)
            ),
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
        "suite": {
            "suite_id": loaded_suite["suite_id"],
            "suite_version": str(loaded_suite["suite_version"]),
            "suite_path": str(resolved_suite),
            "prompt_count": len(prompt_results),
            "include": include,
            "only": only,
        },
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


def execute_vllm_run(
    *,
    suite: Path,
    only: str | None,
    include: str,
    resolved: dict[str, Any],
    out: Path,
    fail_on_failed_prompts: bool,
) -> dict[str, Any]:
    """Execute prompts against an operator-managed local vLLM server."""
    resolved_suite = resolve_suite_path(suite)
    suite = resolved_suite
    loaded_suite = load_suite(suite)
    selected_prompts = select_prompts(loaded_suite, only, include)
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
    runtime_evidence = build_runtime_evidence_document(
        config=vllm_config,
        readiness=readiness,
        endpoint_identity=endpoint_identity,
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

            prompt_results.append(
                {
                    "prompt_id": prompt_id,
                    "title": prompt_meta.get("title", prompt_id),
                    "category": prompt_meta.get("category"),
                    "status": "failed",
                    "raw_prompt_path": str(raw_prompt_path.relative_to(out)),
                    "raw_output_path": str(raw_output_path.relative_to(out)),
                    "cleaned_output_path": str(cleaned_output_path.relative_to(out)),
                    "stderr_log_path": str(stderr_log_path.relative_to(out)),
                    "request_evidence_path": str(
                        request_evidence_path.relative_to(out)
                    ),
                    "metrics": build_vllm_metrics(
                        VllmRequestResult(success=False)
                    ),
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
            )
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

            prompt_results.append(
                {
                    "prompt_id": prompt_id,
                    "title": prompt_meta.get("title", prompt_id),
                    "category": prompt_meta.get("category"),
                    "status": status,
                    "raw_prompt_path": str(raw_prompt_path.relative_to(out)),
                    "raw_output_path": str(raw_output_path.relative_to(out)),
                    "cleaned_output_path": str(cleaned_output_path.relative_to(out)),
                    "stderr_log_path": str(stderr_log_path.relative_to(out)),
                    "request_evidence_path": str(
                        request_evidence_path.relative_to(out)
                    ),
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
            )

    completed_count = sum(1 for item in prompt_results if item["status"] == "completed")
    failed_count = sum(1 for item in prompt_results if item["status"] == "failed")
    run_status = "completed" if failed_count == 0 else "failed"
    profile = resolved["profile"]

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

    backend_provenance = {
        "backend_name": "vllm",
        "lifecycle_ownership": "external_operator",
        "endpoint_identity": endpoint_identity,
        "requested_served_model": resolved["served_model"],
        "observed_served_model": readiness.observed_model,
        "vllm_version": "unknown",
        "status": "available" if readiness.success else "unavailable",
        "warning": None
        if readiness.success
        else (readiness.failure_detail or readiness.failure_class),
        "discovery_status": "partial",
        "discovery_warning": (
            "Server version and kernel metadata are unknown for this slice"
        ),
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
            "vllm_runtime_evidence_path": str(
                runtime_evidence_path.relative_to(out)
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
        "suite": {
            "suite_id": loaded_suite["suite_id"],
            "suite_version": str(loaded_suite["suite_version"]),
            "suite_path": str(resolved_suite),
            "prompt_count": len(prompt_results),
            "include": include,
            "only": only,
        },
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
        output_plan = (
            "not required for --dry-run; real fit-ladder runs require --out or --auto-name"
        )

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
