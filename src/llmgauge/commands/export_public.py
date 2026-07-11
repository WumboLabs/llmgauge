from __future__ import annotations

from pathlib import Path

import typer

from llmgauge.cli_common import console
from llmgauge.core.public_export import export_public_run


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
