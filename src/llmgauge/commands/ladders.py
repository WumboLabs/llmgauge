from __future__ import annotations

from pathlib import Path
from typing import Any

import typer

from llmgauge.cli_common import MODEL_PROFILES_FILE_OPTIONS, console
from llmgauge.commands import run_helpers
from llmgauge.core.artifacts import prepare_result_dir, write_json
from llmgauge.core.fit_ladder import (
    build_fit_attempt_plan,
    build_fit_attempt_record,
    build_fit_ladder_summary,
    write_fit_ladder_report,
)
from llmgauge.core.ladder import (
    build_ladder_summary,
    parse_ctx_ladder,
    write_ladder_report,
    write_ladder_summary,
)
from llmgauge.core.suite import load_suite
from llmgauge.core.suite_paths import resolve_suite_path



def fit_ladder(
    suite: Path = typer.Option(..., "--suite", help="Suite directory"),
    only: str | None = typer.Option(
        None,
        "--only",
        help="Exact prompt ID to run, for example honesty/unknown-package",
    ),
    include: str = typer.Option(
        "all",
        "--include",
        help="Prompt category to run, or 'all'. Ignored when --only is set.",
    ),
    model_id: str | None = typer.Option(None, "--model-id", help="Model identifier"),
    model_profile: str | None = typer.Option(
        None, "--model-profile", help="Model profile name"
    ),
    config_path: Path | None = typer.Option(
        None, "--config", help="LLMGauge config YAML"
    ),
    model_profiles_path: Path | None = typer.Option(
        None,
        *MODEL_PROFILES_FILE_OPTIONS,
        help="Model profiles YAML",
    ),
    model_path: Path | None = typer.Option(
        None, "--model-path", help="GGUF model path"
    ),
    llama_cli: Path | None = typer.Option(None, "--llama-cli", help="llama-cli path"),
    ctx: int | None = typer.Option(None, "--ctx", help="Requested context size"),
    fallback_contexts: str | None = typer.Option(
        None,
        "--fallback-contexts",
        help="Comma-separated fallback context sizes. Default: 8192,16384,32768",
    ),
    allow_extreme_context: bool = typer.Option(
        False,
        "--allow-extreme-context",
        help="Allow fallback context values above 65536 up to 262144",
    ),
    max_tokens: int | None = typer.Option(
        None, "--max-tokens", help="Max generated tokens"
    ),
    temp: float | None = typer.Option(None, "--temp", help="Temperature"),
    top_p: float | None = typer.Option(None, "--top-p", help="Top-p"),
    batch: int | None = typer.Option(None, "--batch", help="Batch size"),
    ubatch: int | None = typer.Option(None, "--ubatch", help="Micro-batch size"),
    gpu_layers: int | None = typer.Option(None, "--gpu-layers", help="GPU layers"),
    flash_attn: str | None = typer.Option(
        None,
        "--flash-attn",
        help="Flash attention mode: auto, on, or off",
    ),
    runtime_label: str | None = typer.Option(
        None,
        "--runtime-label",
        help="Runtime methodology label, such as stock-reference or daily-tuned",
    ),
    reasoning_mode: str | None = typer.Option(
        None,
        "--reasoning-mode",
        help="Reasoning mode: off, on, auto, default, or unknown",
    ),
    out: Path | None = typer.Option(None, "--out", help="Output fit-ladder directory"),
    auto_name: bool = typer.Option(
        False,
        "--auto-name",
        help="Automatically create a timestamped output directory",
    ),
    runs_root: Path = typer.Option(
        Path("results"),
        "--runs-root",
        help="Root directory for auto-named fit-ladder runs",
    ),
    run_name: str | None = typer.Option(
        None,
        "--run-name",
        help="Name slug for auto-named fit-ladder directories",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Resolve and print the fit-ladder plan without launching llama.cpp",
    ),
) -> None:
    """Run explicit context fallback attempts until one fits or all fail."""
    resolved_suite = resolve_suite_path(suite)
    loaded_suite = load_suite(resolved_suite)

    base_resolved = run_helpers.resolve_run_options(
        model_id=model_id,
        model_profile=model_profile,
        config_path=config_path,
        model_profiles_path=model_profiles_path,
        model_path=model_path,
        llama_cli=llama_cli,
        ctx=ctx,
        max_tokens=max_tokens,
        temp=temp,
        top_p=top_p,
        batch=batch,
        ubatch=ubatch,
        gpu_layers=gpu_layers,
        flash_attn=flash_attn,
        runtime_label=runtime_label,
        reasoning_mode=reasoning_mode,
    )
    run_helpers.reject_unsupported_vllm_command(
        base_resolved,
        command="fit-ladder",
    )

    try:
        fallback_values = parse_ctx_ladder(
            fallback_contexts,
            allow_extreme_context=allow_extreme_context,
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    attempts = build_fit_attempt_plan(
        requested_ctx=base_resolved["ctx"],
        fallback_contexts=fallback_values,
        batch_size=base_resolved["batch"],
        ubatch_size=base_resolved["ubatch"],
        gpu_layers=base_resolved["gpu_layers"],
    )
    default_run_name = f"fit-{base_resolved['model_id']}-{suite.name}"

    if dry_run:
        run_helpers.print_fit_ladder_preflight(
            suite=resolved_suite,
            loaded_suite=loaded_suite,
            only=only,
            include=include,
            resolved=base_resolved,
            attempts=attempts,
            out=out,
            auto_name=auto_name,
            runs_root=runs_root,
            run_name=run_name,
            default_run_name=default_run_name,
        )
        return

    resolved_out = run_helpers.resolve_cli_output_dir(
        out=out,
        auto_name=auto_name,
        runs_root=runs_root,
        run_name=run_name,
        default_run_name=default_run_name,
    )
    resolved_out.mkdir(parents=True, exist_ok=True)

    console.print(
        f"Running fit ladder [bold]{resolved_out.name}[/bold] with "
        f"[bold]{len(attempts)}[/bold] planned attempt(s)"
    )

    attempt_records: list[dict[str, Any]] = []

    for index, attempt in enumerate(attempts):
        attempt_id = str(attempt["attempt_id"])
        ctx_size = int(attempt["ctx_size"])
        attempt_dir = resolved_out / f"{attempt_id}-ctx-{ctx_size}"

        console.print(
            f"[{index + 1}/{len(attempts)}] Fit attempt "
            f"[bold]{attempt_id}[/bold] at ctx [bold]{ctx_size}[/bold]"
        )

        attempt_resolved = dict(base_resolved)
        attempt_resolved["ctx"] = ctx_size
        attempt_resolved["batch"] = int(attempt["batch_size"])
        attempt_resolved["ubatch"] = int(attempt["ubatch_size"])
        attempt_resolved["gpu_layers"] = int(attempt["gpu_layers"])

        try:
            result = run_helpers.execute_run(
                suite=suite,
                only=only,
                include=include,
                resolved=attempt_resolved,
                out=attempt_dir,
                fail_on_failed_prompts=False,
            )
            record = run_helpers.build_fit_attempt_record_from_result(
                attempt=attempt,
                result=result,
                result_dir=attempt_dir,
            )
        except Exception as exc:
            record = build_fit_attempt_record(
                attempt_id=attempt_id,
                ctx_size=ctx_size,
                batch_size=int(attempt["batch_size"]),
                ubatch_size=int(attempt["ubatch_size"]),
                gpu_layers=int(attempt["gpu_layers"]),
                exit_status=1,
                stderr=str(exc),
                result_dir=str(attempt_dir),
            )
            console.print(f"[bold red]Fit attempt failed[/bold red]: {exc}")

        attempt_records.append(record)

        if record["status"] == "completed":
            console.print(
                f"[bold green]Fit ladder selected ctx={ctx_size}[/bold green]"
            )
            break

        has_next_attempt = index + 1 < len(attempts)
        if record["retryable"] and has_next_attempt:
            next_ctx = attempts[index + 1]["ctx_size"]
            console.print(
                f"[bold yellow]{record['failure_class']} detected at ctx={ctx_size}; "
                f"retrying at ctx={next_ctx}[/bold yellow]"
            )
            continue

        if not record["retryable"]:
            console.print(
                f"[bold red]Non-retryable fit failure at ctx={ctx_size}[/bold red]: "
                f"{record['failure_reason']}"
            )
        break

    summary = build_fit_ladder_summary(
        fit_ladder_id=resolved_out.name,
        requested_settings={
            "suite_id": loaded_suite["suite_id"],
            "include": include,
            "only": only,
            "model_id": base_resolved["model_id"],
            "model_profile": base_resolved["model_profile"],
            "ctx_size": base_resolved["ctx"],
            "batch_size": base_resolved["batch"],
            "ubatch_size": base_resolved["ubatch"],
            "gpu_layers": base_resolved["gpu_layers"],
            "max_tokens": base_resolved["max_tokens"],
            "temperature": base_resolved["temp"],
            "top_p": base_resolved["top_p"],
        },
        retry_policy={
            "fallback_order": ["context"],
            "fallback_contexts": fallback_values,
            "stop_on_first_completed": True,
            "gpu_layer_fallback": "explicit-only",
        },
        attempts=attempt_records,
    )
    write_json(resolved_out / "fit-ladder-summary.json", summary)
    report_path = write_fit_ladder_report(resolved_out, summary)

    if summary["final_status"] == "failed":
        console.print(f"[bold red]Fit ladder failed[/bold red]: {resolved_out}")
        console.print(f"Fit ladder report: {report_path}")
        raise typer.Exit(code=1)

    console.print(f"[bold green]Fit ladder completed[/bold green]: {resolved_out}")
    console.print(f"Fit ladder report: {report_path}")



def run_ladder(
    suite: Path = typer.Option(..., "--suite", help="Suite directory"),
    only: str | None = typer.Option(
        None,
        "--only",
        help="Exact prompt ID to run, for example honesty/unknown-package",
    ),
    include: str = typer.Option(
        "all",
        "--include",
        help="Prompt category to run, or 'all'. Ignored when --only is set.",
    ),
    model_id: str | None = typer.Option(None, "--model-id", help="Model identifier"),
    model_profile: str | None = typer.Option(
        None, "--model-profile", help="Model profile name"
    ),
    config_path: Path | None = typer.Option(
        None, "--config", help="LLMGauge config YAML"
    ),
    model_profiles_path: Path | None = typer.Option(
        None,
        *MODEL_PROFILES_FILE_OPTIONS,
        help="Model profiles YAML",
    ),
    model_path: Path | None = typer.Option(
        None, "--model-path", help="GGUF model path"
    ),
    llama_cli: Path | None = typer.Option(None, "--llama-cli", help="llama-cli path"),
    ctx_ladder: str | None = typer.Option(
        None,
        "--ctx-ladder",
        help="Comma-separated context sizes. Default: 8192,16384,32768",
    ),
    allow_extreme_context: bool = typer.Option(
        False,
        "--allow-extreme-context",
        help="Allow explicit context ladder values above 65536 up to 262144",
    ),
    max_tokens: int | None = typer.Option(
        None, "--max-tokens", help="Max generated tokens"
    ),
    temp: float | None = typer.Option(None, "--temp", help="Temperature"),
    top_p: float | None = typer.Option(None, "--top-p", help="Top-p"),
    batch: int | None = typer.Option(None, "--batch", help="Batch size"),
    ubatch: int | None = typer.Option(None, "--ubatch", help="Micro-batch size"),
    gpu_layers: int | None = typer.Option(None, "--gpu-layers", help="GPU layers"),
    flash_attn: str | None = typer.Option(
        None,
        "--flash-attn",
        help="Flash attention mode: auto, on, or off",
    ),
    runtime_label: str | None = typer.Option(
        None,
        "--runtime-label",
        help="Runtime methodology label, such as stock-reference or daily-tuned",
    ),
    reasoning_mode: str | None = typer.Option(
        None,
        "--reasoning-mode",
        help="Reasoning mode: off, on, auto, default, or unknown",
    ),
    out: Path | None = typer.Option(None, "--out", help="Output ladder directory"),
    auto_name: bool = typer.Option(
        False,
        "--auto-name",
        help="Automatically create a timestamped output directory",
    ),
    runs_root: Path = typer.Option(
        Path("results"),
        "--runs-root",
        help="Root directory for auto-named ladder runs",
    ),
    run_name: str | None = typer.Option(
        None,
        "--run-name",
        help="Name slug for auto-named ladder directories",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Resolve and print the ladder run plan without launching llama.cpp",
    ),
) -> None:
    """Run the same selected prompts across multiple context sizes."""
    try:
        contexts = parse_ctx_ladder(
            ctx_ladder,
            allow_extreme_context=allow_extreme_context,
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    child_runs: list[dict[str, Any]] = []
    resolved_suite = resolve_suite_path(suite)
    loaded_suite = load_suite(resolved_suite)
    default_run_name = f"ladder-{model_id or model_profile or loaded_suite['suite_id']}"

    if dry_run:
        resolved = run_helpers.resolve_run_options(
            model_id=model_id,
            model_profile=model_profile,
            config_path=config_path,
            model_profiles_path=model_profiles_path,
            model_path=model_path,
            llama_cli=llama_cli,
            ctx=contexts[0],
            max_tokens=max_tokens,
            temp=temp,
            top_p=top_p,
            batch=batch,
            ubatch=ubatch,
            gpu_layers=gpu_layers,
            flash_attn=flash_attn,
            runtime_label=runtime_label,
            reasoning_mode=reasoning_mode,
        )
        run_helpers.reject_unsupported_vllm_command(
            resolved,
            command="run-ladder",
        )
        run_helpers.print_ladder_preflight(
            suite=resolved_suite,
            loaded_suite=loaded_suite,
            only=only,
            include=include,
            resolved=resolved,
            contexts=contexts,
            allow_extreme_context=allow_extreme_context,
            out=out,
            auto_name=auto_name,
            runs_root=runs_root,
            run_name=run_name,
            default_run_name=default_run_name,
        )
        return

    resolved_out = run_helpers.resolve_cli_output_dir(
        out=out,
        auto_name=auto_name,
        runs_root=runs_root,
        run_name=run_name,
        default_run_name=default_run_name,
    )

    prepare_result_dir(resolved_out)

    console.print(
        f"Running context ladder [bold]{resolved_out.name}[/bold] across "
        f"[bold]{len(contexts)}[/bold] context size(s): "
        f"{', '.join(str(ctx) for ctx in contexts)}"
    )

    for ctx_size in contexts:
        child_dir = resolved_out / f"ctx-{ctx_size}"
        try:
            resolved = run_helpers.resolve_run_options(
                model_id=model_id,
                model_profile=model_profile,
                config_path=config_path,
                model_profiles_path=model_profiles_path,
                model_path=model_path,
                llama_cli=llama_cli,
                ctx=ctx_size,
                max_tokens=max_tokens,
                temp=temp,
                top_p=top_p,
                batch=batch,
                ubatch=ubatch,
                gpu_layers=gpu_layers,
                flash_attn=flash_attn,
                runtime_label=runtime_label,
                reasoning_mode=reasoning_mode,
            )
            run_helpers.reject_unsupported_vllm_command(
                resolved,
                command="run-ladder",
            )

            result = run_helpers.execute_run(
                suite=suite,
                only=only,
                include=include,
                resolved=resolved,
                out=child_dir,
                fail_on_failed_prompts=False,
            )

            child_runs.append(
                {
                    "ctx_size": ctx_size,
                    "status": result["run"]["status"],
                    "result_dir": str(child_dir),
                    "completed": result["summary"]["completed"],
                    "failed": result["summary"]["failed"],
                    "error": None
                    if result["run"]["status"] == "completed"
                    else "one or more prompts failed",
                }
            )
        except Exception as exc:
            child_runs.append(
                {
                    "ctx_size": ctx_size,
                    "status": "failed",
                    "result_dir": str(child_dir),
                    "completed": None,
                    "failed": None,
                    "error": str(exc),
                }
            )
            console.print(f"[bold red]Context {ctx_size} failed[/bold red]: {exc}")

    summary = build_ladder_summary(
        ladder_id=resolved_out.name,
        suite_id=loaded_suite["suite_id"],
        include=include,
        only=only,
        model_id=str(model_id or model_profile or "unknown-model"),
        contexts=contexts,
        child_runs=child_runs,
        allow_extreme_context=allow_extreme_context,
    )
    write_ladder_summary(resolved_out, summary)
    write_ladder_report(resolved_out, summary)

    if summary["summary"]["failed"]:
        console.print(
            f"[bold red]Context ladder completed with failures[/bold red]: {resolved_out}"
        )
        raise typer.Exit(code=1)

    console.print(f"[bold green]Context ladder completed[/bold green]: {resolved_out}")
