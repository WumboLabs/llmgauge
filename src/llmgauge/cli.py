from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from llmgauge.core.artifacts import prepare_result_dir, write_json, write_text
from llmgauge.core.baseline import check_result_against_baselines
from llmgauge.core.compare import build_compare_report, load_compare_result
from llmgauge.core.contextgen import (
    build_context_prompt,
    write_context_prompt_artifacts,
)
from llmgauge.core.export_index import build_export_index, write_export_index
from llmgauge.core.config import (
    coalesce,
    get_config_value,
    load_llmgauge_config,
    load_model_profiles,
    resolve_model_profile,
)
from llmgauge.core.ladder import (
    build_ladder_summary,
    parse_ctx_ladder,
    write_ladder_report,
    write_ladder_summary,
)
from llmgauge.core.ladder_validation import validate_ladder_dir
from llmgauge.core.metrics import parse_llama_metrics
from llmgauge.core.output_paths import build_auto_output_dir
from llmgauge.core.reports import build_markdown_report
from llmgauge.core.result_validation import validate_result_dir
from llmgauge.core.scoring import (
    apply_scores,
    build_score_template,
    load_result,
    load_scores,
    validate_scores,
    write_result,
    write_score_template,
)
from llmgauge.core.suite import load_suite, validate_suite
from llmgauge.core.suite_paths import resolve_suite_path, resolve_suites_dir
from llmgauge.runners.llama_cpp import LlamaCppRunConfig, run_llama_cpp

app = typer.Typer(
    name="llmgauge",
    help="Practical local LLM evaluation on real hardware.",
    no_args_is_help=True,
)

console = Console()


@app.command()
def doctor() -> None:
    """Check the local LLMGauge environment."""
    table = Table(title="LLMGauge Doctor")
    table.add_column("Check")
    table.add_column("Status")
    table.add_column("Notes")

    table.add_row("Python package", "ok", "LLMGauge import works")
    table.add_row("Runner", "available", "llama.cpp runner module installed")
    table.add_row("Suites", "available", "Run: llmgauge list-suites")

    console.print(table)


@app.command("list-suites")
def list_suites(suites_dir: Path | None = typer.Argument(None)) -> None:
    """List available prompt suites."""
    resolved_suites_dir = resolve_suites_dir(suites_dir)
    if not resolved_suites_dir.exists():
        raise typer.BadParameter(
            f"Suites directory does not exist: {resolved_suites_dir}"
        )

    table = Table(title="Available Suites")
    table.add_column("Suite ID")
    table.add_column("Version")
    table.add_column("Title")
    table.add_column("Prompts")

    for suite_file in sorted(resolved_suites_dir.glob("*/suite.yaml")):
        suite = load_suite(suite_file.parent)
        table.add_row(
            suite["suite_id"],
            str(suite["suite_version"]),
            suite.get("title", ""),
            str(len(suite.get("prompts", []))),
        )

    console.print(table)


@app.command("validate-suite")
def validate_suite_command(suite_dir: Path = typer.Argument(...)) -> None:
    """Validate a prompt suite."""
    resolved_suite_dir = resolve_suite_path(suite_dir)
    errors = validate_suite(resolved_suite_dir)

    if errors:
        console.print("[bold red]Suite validation failed[/bold red]")
        for error in errors:
            console.print(f"- {error}")
        raise typer.Exit(code=1)

    suite = load_suite(resolved_suite_dir)
    console.print(
        f"[bold green]OK[/bold green] {suite['suite_id']} "
        f"({len(suite.get('prompts', []))} prompts)"
    )


def _find_prompt(suite: dict, prompt_id: str) -> dict:
    for prompt in suite.get("prompts", []):
        if prompt.get("id") == prompt_id:
            return prompt
    raise typer.BadParameter(f"Prompt ID not found in suite: {prompt_id}")


def _select_prompts(suite: dict, only: str | None, include: str) -> list[dict]:
    prompts = suite.get("prompts", [])

    if only:
        return [_find_prompt(suite, only)]

    if include == "all":
        return list(prompts)

    selected = [prompt for prompt in prompts if prompt.get("category") == include]
    if not selected:
        raise typer.BadParameter(f"No prompts found for include/category: {include}")

    return selected


def _load_system_prompt() -> str:
    path = resolve_suite_path(Path("core-v1")) / "prompts/system-conservative-ops.txt"
    if path.exists():
        return path.read_text(encoding="utf-8").strip()

    return (
        "You are a conservative local systems assistant. "
        "Prefer safe, reversible, verified steps. "
        "Say when unsure. Do not invent commands, packages, flags, or docs."
    )


def _build_combined_prompt(system_prompt: str, prompt_text: str) -> str:
    return "\n\n".join(
        [
            "SYSTEM:",
            system_prompt,
            "USER:",
            prompt_text,
        ]
    )


def _redacted_command(command: list[str], model_path: Path) -> list[str]:
    return [arg if arg != str(model_path) else "REDACTED_MODEL_PATH" for arg in command]


def _resolve_cli_output_dir(
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
        raise typer.BadParameter("Use --out PATH or --auto-name")

    return build_auto_output_dir(
        runs_root=runs_root,
        run_name=run_name or default_run_name,
    )


def _resolve_run_options(
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
) -> dict[str, Any]:
    config_data = load_llmgauge_config(config_path)
    profiles = load_model_profiles(model_profiles_path)
    profile = resolve_model_profile(profiles, model_profile)

    resolved_model_id = coalesce(model_id, model_profile, profile.get("label"))
    if resolved_model_id is None:
        raise typer.BadParameter("Provide --model-id or --model-profile")

    resolved_model_path = coalesce(model_path, profile.get("path"))
    if resolved_model_path is None:
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

    if not resolved_model_path.exists():
        raise typer.BadParameter(f"Model path does not exist: {resolved_model_path}")

    if not resolved_llama_cli.exists():
        raise typer.BadParameter(f"llama-cli path does not exist: {resolved_llama_cli}")

    return {
        "model_id": str(resolved_model_id),
        "model_profile": model_profile,
        "profile": profile,
        "config_path": config_path,
        "model_profiles_path": model_profiles_path,
        "model_path": resolved_model_path,
        "llama_cli": resolved_llama_cli,
        "ctx": resolved_ctx,
        "max_tokens": resolved_max_tokens,
        "temp": resolved_temp,
        "top_p": resolved_top_p,
        "batch": resolved_batch,
        "ubatch": resolved_ubatch,
        "gpu_layers": resolved_gpu_layers,
    }


def _execute_run(
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
    selected_prompts = _select_prompts(loaded_suite, only, include)
    system_prompt = _load_system_prompt()

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
    )

    timestamp = datetime.now(UTC).replace(microsecond=0).isoformat()
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
        combined_prompt = _build_combined_prompt(system_prompt, prompt_text)

        raw_prompt_path = out / "raw" / f"{prompt_id}.prompt.md"
        raw_output_path = out / "raw" / f"{prompt_id}.output.txt"
        stderr_log_path = out / "logs" / f"{prompt_id}.stderr.log"

        write_text(raw_prompt_path, combined_prompt)

        console.print(f"[{index}/{len(selected_prompts)}] Running {prompt_id}")
        run_result = run_llama_cpp(config, combined_prompt)

        if redacted_command is None:
            redacted_command = _redacted_command(
                run_result.command,
                resolved["model_path"],
            )

        write_text(raw_output_path, run_result.stdout)
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

        prompt_results.append(
            {
                "prompt_id": prompt_id,
                "title": prompt_meta.get("title", prompt_id),
                "category": prompt_meta.get("category"),
                "status": status,
                "raw_prompt_path": str(raw_prompt_path.relative_to(out)),
                "raw_output_path": str(raw_output_path.relative_to(out)),
                "stderr_log_path": str(stderr_log_path.relative_to(out)),
                "metrics": metrics,
                "vram": vram_summary,
                "vram_samples_path": str(vram_samples_path.relative_to(out))
                if vram_samples_path is not None
                else None,
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
        "llmgauge_version": "0.1.0",
        "run": {
            "run_id": run_id,
            "timestamp_utc": timestamp,
            "status": run_status,
            "result_dir": str(out),
        },
        "model": {
            "model_id": resolved["model_id"],
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


@app.command()
def contextgen(
    target_tokens: int = typer.Option(
        ...,
        "--target-tokens",
        help="Approximate target token count using a simple character heuristic",
    ),
    needle: str = typer.Option(..., "--needle", help="Needle fact to embed"),
    question: str = typer.Option(..., "--question", help="Final question/task"),
    placement: float = typer.Option(
        0.5,
        "--placement",
        help="Needle placement ratio from 0.0 to 1.0",
    ),
    out_prompt: Path = typer.Option(
        ...,
        "--out-prompt",
        help="Generated prompt Markdown path",
    ),
    out_metadata: Path = typer.Option(
        ...,
        "--out-metadata",
        help="Generated metadata JSON path",
    ),
) -> None:
    """Generate a synthetic long-context prompt."""
    try:
        generated = build_context_prompt(
            target_tokens=target_tokens,
            needle=needle,
            question=question,
            placement=placement,
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    write_context_prompt_artifacts(
        out_prompt=out_prompt,
        out_metadata=out_metadata,
        generated=generated,
    )

    console.print(f"[bold green]Generated prompt[/bold green]: {out_prompt}")
    console.print(f"[bold green]Generated metadata[/bold green]: {out_metadata}")
    console.print(f"Estimated tokens: {generated['estimated_tokens']}")


@app.command()
def run(
    suite: Path = typer.Option(..., "--suite", help="Suite directory"),
    only: str | None = typer.Option(None, "--only", help="Prompt ID to run"),
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
        "--model-profiles",
        help="Model profiles YAML",
    ),
    model_path: Path | None = typer.Option(
        None, "--model-path", help="GGUF model path"
    ),
    llama_cli: Path | None = typer.Option(None, "--llama-cli", help="llama-cli path"),
    ctx: int | None = typer.Option(None, "--ctx", help="Context size"),
    max_tokens: int | None = typer.Option(
        None, "--max-tokens", help="Max generated tokens"
    ),
    temp: float | None = typer.Option(None, "--temp", help="Temperature"),
    top_p: float | None = typer.Option(None, "--top-p", help="Top-p"),
    batch: int | None = typer.Option(None, "--batch", help="Batch size"),
    ubatch: int | None = typer.Option(None, "--ubatch", help="Micro-batch size"),
    gpu_layers: int | None = typer.Option(None, "--gpu-layers", help="GPU layers"),
    out: Path | None = typer.Option(None, "--out", help="Output result directory"),
    auto_name: bool = typer.Option(
        False,
        "--auto-name",
        help="Automatically create a timestamped output directory",
    ),
    runs_root: Path = typer.Option(
        Path("results"),
        "--runs-root",
        help="Root directory for auto-named runs",
    ),
    run_name: str | None = typer.Option(
        None,
        "--run-name",
        help="Name slug for auto-named run directories",
    ),
) -> None:
    """Run one or more prompts through llama.cpp."""
    resolved = _resolve_run_options(
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
    )

    resolved_out = _resolve_cli_output_dir(
        out=out,
        auto_name=auto_name,
        runs_root=runs_root,
        run_name=run_name,
        default_run_name=f"{resolved['model_id']}-{suite.name}",
    )

    _execute_run(
        suite=suite,
        only=only,
        include=include,
        resolved=resolved,
        out=resolved_out,
        fail_on_failed_prompts=True,
    )


@app.command("run-ladder")
def run_ladder(
    suite: Path = typer.Option(..., "--suite", help="Suite directory"),
    only: str | None = typer.Option(None, "--only", help="Prompt ID to run"),
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
        "--model-profiles",
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
    resolved_out = _resolve_cli_output_dir(
        out=out,
        auto_name=auto_name,
        runs_root=runs_root,
        run_name=run_name,
        default_run_name=f"ladder-{model_id or model_profile or loaded_suite['suite_id']}",
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
            resolved = _resolve_run_options(
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
            )

            result = _execute_run(
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


@app.command("validate-ladder")
def validate_ladder(
    ladder_dir: Path = typer.Argument(..., help="LLMGauge ladder result directory"),
) -> None:
    """Validate a LLMGauge context ladder directory."""
    try:
        errors = validate_ladder_dir(ladder_dir)
    except Exception as exc:
        console.print(f"[bold red]Ladder validation failed[/bold red]: {exc}")
        raise typer.Exit(code=1) from exc

    if errors:
        console.print("[bold red]Ladder validation failed[/bold red]")
        for error in errors:
            console.print(f"- {error}")
        raise typer.Exit(code=1)

    console.print(f"[bold green]OK[/bold green] {ladder_dir}")


@app.command("validate-result")
def validate_result(
    result_dir: Path = typer.Argument(..., help="LLMGauge result directory"),
) -> None:
    """Validate a LLMGauge result directory."""
    try:
        errors = validate_result_dir(result_dir)
    except Exception as exc:
        console.print(f"[bold red]Result validation failed[/bold red]: {exc}")
        raise typer.Exit(code=1) from exc

    if errors:
        console.print("[bold red]Result validation failed[/bold red]")
        for error in errors:
            console.print(f"- {error}")
        raise typer.Exit(code=1)

    console.print(f"[bold green]OK[/bold green] {result_dir}")


@app.command()
def score(
    result_dir: Path = typer.Argument(..., help="LLMGauge result directory"),
    init: bool = typer.Option(
        False,
        "--init",
        help="Create a scores.yaml template in the result directory",
    ),
    scores: Path | None = typer.Option(
        None,
        "--scores",
        help="Apply a scores.yaml file to the result",
    ),
) -> None:
    """Initialize or apply manual scores for a completed run."""
    result = load_result(result_dir)

    if init:
        template = build_score_template(result)
        scores_path = write_score_template(result_dir, template)
        console.print(f"[bold green]Created score template[/bold green]: {scores_path}")
        return

    if scores is None:
        raise typer.BadParameter("Use --init or provide --scores PATH")

    scores_data = load_scores(scores)
    errors = validate_scores(result, scores_data)
    if errors:
        console.print("[bold red]Score validation failed[/bold red]")
        for error in errors:
            console.print(f"- {error}")
        raise typer.Exit(code=1)

    updated = apply_scores(result, scores_data)
    write_result(result_dir, updated)
    write_text(result_dir / "report.md", build_markdown_report(updated))

    console.print(f"[bold green]Applied scores[/bold green]: {scores}")
    console.print(f"Updated: {result_dir / 'llmgauge-result.json'}")
    console.print(f"Updated: {result_dir / 'report.md'}")


@app.command("export-index")
def export_index_command(
    artifact_paths: list[Path] = typer.Argument(
        ...,
        help="LLMGauge run or ladder directories to index",
    ),
    out: Path = typer.Option(..., "--out", help="Output index JSON path"),
    validate: bool = typer.Option(
        False,
        "--validate",
        help="Validate indexed artifacts and include validation status",
    ),
) -> None:
    """Create a machine-readable index of LLMGauge result artifacts."""
    try:
        index = build_export_index(artifact_paths, validate=validate)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    write_export_index(out, index)

    console.print(f"[bold green]Wrote export index[/bold green]: {out}")
    console.print(f"Indexed artifacts: {index['item_count']}")


@app.command("baseline-check")
def baseline_check_command(
    result_dir: Path = typer.Argument(...),
    suite_dir: Path = typer.Option(
        ...,
        "--suite",
        help="Prompt suite directory or built-in suite ID",
    ),
    out: Path | None = typer.Option(
        None,
        "--out",
        help="Optional JSON baseline-check report path",
    ),
    fail_on_mixed: bool = typer.Option(
        False,
        "--fail-on-mixed",
        help="Exit non-zero when any baseline check is mixed",
    ),
) -> None:
    """Check a completed run against suite baseline files."""
    resolved_suite_dir = resolve_suite_path(suite_dir)
    result = load_result(result_dir)

    report = check_result_against_baselines(
        result_dir=result_dir,
        suite_dir=resolved_suite_dir,
        result=result,
    )

    table = Table(title="LLMGauge Baseline Check")
    table.add_column("Prompt")
    table.add_column("Status")
    table.add_column("Missing")
    table.add_column("Forbidden")
    table.add_column("Hard Failures")

    for check in report["checks"]:
        table.add_row(
            str(check.get("prompt_id", "")),
            str(check.get("status", "")),
            str(len(check.get("missing_required", []))),
            str(len(check.get("forbidden_present", []))),
            str(len(check.get("hard_failures", []))),
        )

    console.print(table)
    console.print(f"Status counts: {report['status_counts']}")

    if out is not None:
        write_json(out, report)
        console.print(f"Wrote baseline-check report: {out}")

    failing_statuses = {"fail", "invalid_baseline", "wrong_prompt"}
    if fail_on_mixed:
        failing_statuses.add("mixed")

    if any(check.get("status") in failing_statuses for check in report["checks"]):
        raise typer.Exit(code=1)


@app.command()
def compare(
    result_dirs: list[Path] = typer.Argument(..., help="Result directories to compare"),
    out: Path = typer.Option(..., "--out", help="Markdown comparison report path"),
) -> None:
    """Compare two or more LLMGauge result directories."""
    if len(result_dirs) < 2:
        raise typer.BadParameter("Compare requires at least two result directories")

    results = []
    for result_dir in result_dirs:
        results.append(load_compare_result(result_dir))

    report = build_compare_report(results)
    write_text(out, report)

    console.print(f"[bold green]Wrote comparison report[/bold green]: {out}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
