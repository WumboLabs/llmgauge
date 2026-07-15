from __future__ import annotations

from pathlib import Path
from typing import Any

import typer

from llmgauge.cli_common import MODEL_PROFILES_FILE_OPTIONS, console
from llmgauge.commands import run_helpers
from llmgauge.core.artifacts import prepare_result_dir
from llmgauge.core.batch import (
    build_batch_summary,
    load_batch_manifest,
    write_batch_report,
    write_batch_summary,
)
from llmgauge.core.output_paths import slugify_run_name
from llmgauge.core.suite import load_suite
from llmgauge.core.suite_paths import resolve_suite_path



def run_batch(
    manifest: Path = typer.Option(..., "--manifest", help="Batch manifest YAML"),
    config_path: Path = typer.Option(..., "--config", help="LLMGauge config YAML"),
    model_profiles_path: Path = typer.Option(
        ...,
        *MODEL_PROFILES_FILE_OPTIONS,
        help="Model profiles YAML",
    ),
    out: Path = typer.Option(..., "--out", help="Output batch directory"),
) -> None:
    """Run selected prompts sequentially across manifest-listed model profiles."""
    try:
        manifest_data = load_batch_manifest(manifest)
    except (OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc

    suite_path = Path(manifest_data["suite"])
    resolved_suite = resolve_suite_path(suite_path)
    loaded_suite = load_suite(resolved_suite)

    prepare_result_dir(out)

    model_profiles = manifest_data["models"]
    console.print(
        f"Running model batch [bold]{manifest_data['batch_id']}[/bold] across "
        f"[bold]{len(model_profiles)}[/bold] model profile(s)"
    )

    child_runs: list[dict[str, Any]] = []

    for index, model_profile_name in enumerate(model_profiles, start=1):
        child_dir = out / f"model-{index:02d}-{slugify_run_name(model_profile_name)}"

        try:
            resolved = run_helpers.resolve_run_options(
                model_id=None,
                model_profile=model_profile_name,
                config_path=config_path,
                model_profiles_path=model_profiles_path,
                model_path=None,
                llama_cli=None,
                ctx=None,
                max_tokens=manifest_data["max_tokens"],
                temp=None,
                top_p=None,
                batch=None,
                ubatch=None,
                gpu_layers=None,
                flash_attn=None,
                runtime_label=None,
            )
            run_helpers.reject_unsupported_vllm_command(
                resolved,
                command="run-batch",
            )

            result = run_helpers.execute_run(
                suite=suite_path,
                only=manifest_data["only"],
                include=manifest_data["include"],
                resolved=resolved,
                out=child_dir,
                fail_on_failed_prompts=False,
            )

            child_runs.append(
                {
                    "model_profile": model_profile_name,
                    "model_id": result["model"]["model_id"],
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
                    "model_profile": model_profile_name,
                    "model_id": None,
                    "status": "failed",
                    "result_dir": str(child_dir),
                    "completed": None,
                    "failed": None,
                    "error": str(exc),
                }
            )
            console.print(
                f"[bold red]Model profile {model_profile_name} failed[/bold red]: {exc}"
            )

    summary = build_batch_summary(
        batch_id=manifest_data["batch_id"],
        suite_id=loaded_suite["suite_id"],
        suite_path=str(resolved_suite),
        include=manifest_data["include"],
        only=manifest_data["only"],
        max_tokens=manifest_data["max_tokens"],
        models=model_profiles,
        child_runs=child_runs,
        manifest_path=str(manifest),
    )
    write_batch_summary(out, summary)
    write_batch_report(out, summary)

    if summary["summary"]["failed"]:
        console.print(
            f"[bold red]Model batch completed with failures[/bold red]: {out}"
        )
        raise typer.Exit(code=1)

    console.print(f"[bold green]Model batch completed[/bold green]: {out}")
