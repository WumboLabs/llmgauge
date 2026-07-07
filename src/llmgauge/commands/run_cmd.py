from __future__ import annotations

from pathlib import Path

import typer

from llmgauge.cli_common import console
from llmgauge.commands import run_helpers
from llmgauge.core.contextgen import build_context_prompt, write_context_prompt_artifacts



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



def run(
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
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Resolve and print the run plan without launching llama.cpp",
    ),
) -> None:
    """Run one or more prompts through llama.cpp."""
    resolved = run_helpers.resolve_run_options(
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
    )

    if dry_run:
        run_helpers.print_run_preflight(
            suite=suite,
            only=only,
            include=include,
            resolved=resolved,
            out=out,
            auto_name=auto_name,
            runs_root=runs_root,
            run_name=run_name,
        )
        return

    resolved_out = run_helpers.resolve_cli_output_dir(
        out=out,
        auto_name=auto_name,
        runs_root=runs_root,
        run_name=run_name,
        default_run_name=f"{resolved['model_id']}-{suite.name}",
    )

    run_helpers.execute_run(
        suite=suite,
        only=only,
        include=include,
        resolved=resolved,
        out=resolved_out,
        fail_on_failed_prompts=True,
    )
