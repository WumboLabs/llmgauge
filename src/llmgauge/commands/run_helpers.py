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
from llmgauge.core.metrics import parse_llama_metrics
from llmgauge.core.output_cleaning import clean_llama_output
from llmgauge.core.output_paths import build_auto_output_dir
from llmgauge.core.reports import build_markdown_report
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

    resolved_model_id = coalesce(model_id, model_profile, profile.get("label"))
    if resolved_model_id is None:
        raise typer.BadParameter("Provide --model-id or --model-profile")

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

    if not resolved_model_path.exists():
        raise typer.BadParameter(f"Model path does not exist: {resolved_model_path}")

    if not resolved_llama_cli.exists():
        raise typer.BadParameter(f"llama-cli path does not exist: {resolved_llama_cli}")

    return {
        "model_id": str(resolved_model_id),
        "model_profile": model_profile,
        "profile": profile,
        "config_path": resolved_config_path,
        "model_profiles_path": resolved_model_profiles_path,
        "model_path": resolved_model_path,
        "llama_cli": resolved_llama_cli,
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
    table.add_row("Model ID", str(resolved["model_id"]))
    table.add_row("Model source", str(resolved["model_source"]))
    table.add_row("Model profile", str(resolved["model_profile"]))
    table.add_row("Config", str(resolved["config_path"]))
    table.add_row("Model profiles", str(resolved["model_profiles_path"]))
    table.add_row("Model path", str(resolved["model_path"]))
    table.add_row("llama-cli", str(resolved["llama_cli"]))
    table.add_row("Context", str(resolved["ctx"]))
    table.add_row("Max tokens", str(resolved["max_tokens"]))
    table.add_row("Temperature", str(resolved["temp"]))
    table.add_row("Top-p", str(resolved["top_p"]))
    table.add_row("Batch", str(resolved["batch"]))
    table.add_row("UBatch", str(resolved["ubatch"]))
    table.add_row("GPU layers", str(resolved["gpu_layers"]))
    table.add_row("Flash attention", str(resolved["flash_attn"]))
    table.add_row("Runtime label", str(resolved["runtime_label"] or "unknown"))
    table.add_row("Reasoning mode", str(resolved["reasoning_mode"]))
    table.add_row("Output plan", output_plan)

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
            f"<result-dir>/{RUNTIME_COMMAND_FILENAME} for real runs with --out or --auto-name"
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
    console.print(
        "[bold green]Dry run complete[/bold green]: llama.cpp was not "
        "launched and no result directory was created."
    )


def execute_run(
    *,
    suite: Path,
    only: str | None,
    include: str,
    resolved: dict[str, Any],
    out: Path,
    fail_on_failed_prompts: bool,
) -> dict[str, Any]:
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

    write_json(out / "llmgauge-result.json", result)
    write_text(out / "report.md", build_markdown_report(result))

    if failed_count:
        console.print(f"[bold red]Run completed with failures[/bold red]: {out}")
        if fail_on_failed_prompts:
            raise typer.Exit(code=1)
    else:
        console.print(f"[bold green]Run completed[/bold green]: {out}")

    return result



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


