from __future__ import annotations

from pathlib import Path

import typer

from llmgauge.cli_common import console
from llmgauge.core.public_export import export_public_run
from llmgauge.core.transcript_public_export import (
    export_public_transcript,
    export_public_transcript_comparison,
)


def export_public_command(
    run_dir: Path = typer.Argument(..., help="Completed LLMGauge run directory"),
    out: Path = typer.Option(..., "--out", help="New public export directory"),
) -> None:
    """Create a sanitized public derivative of one completed run."""

    try:
        manifest = export_public_run(run_dir, out)
    except (OSError, ValueError) as exc:
        console.print(f"[bold red]Public export failed[/bold red]: {exc}")
        raise typer.Exit(code=1) from exc

    console.print(f"[bold green]Wrote public export[/bold green]: {out}")
    console.print(f"Transformed files: {len(manifest['files_transformed'])}")
    console.print(f"Omitted files: {len(manifest['files_omitted'])}")
    console.print(
        "Review the public export before publication; sanitization is not answer-quality validation."
    )


def export_public_comparison_command(
    run_a: Path = typer.Argument(..., help="First transcript-bearing run directory"),
    run_b: Path = typer.Argument(..., help="Second transcript-bearing run directory"),
    out: Path = typer.Option(..., "--out", help="New public export directory"),
) -> None:
    """Create a sanitized public derivative of a transcript comparison."""

    try:
        projection = export_public_transcript_comparison([run_a, run_b], out)
    except (OSError, ValueError) as exc:
        console.print(f"[bold red]Public comparison export failed[/bold red]: {exc}")
        raise typer.Exit(code=1) from exc

    console.print(f"[bold green]Wrote public transcript comparison[/bold green]: {out}")
    console.print(f"Classification: {projection['classification']['classification']}")
    console.print(
        "Review the public export before publication; sanitization is not answer-quality validation."
    )


def export_public_transcript_command(
    run_dir: Path = typer.Argument(
        ..., help="Transcript-bearing run directory to project"
    ),
    out: Path = typer.Option(..., "--out", help="New public export directory"),
) -> None:
    """Create a content-default-deny public derivative of one native transcript run."""

    try:
        projection = export_public_transcript(run_dir, out)
    except (OSError, ValueError) as exc:
        console.print(f"[bold red]Public transcript export failed[/bold red]: {exc}")
        raise typer.Exit(code=1) from exc

    console.print(f"[bold green]Wrote public transcript derivative[/bold green]: {out}")
    console.print(f"Projected run: {projection['run']['model_label']}")
    console.print(
        "Review the public export before publication; sanitization is not answer-quality validation."
    )
