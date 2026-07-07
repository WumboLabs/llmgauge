from __future__ import annotations

from pathlib import Path

import typer

from llmgauge.cli_common import console
from llmgauge.core.batch_validation import validate_batch_dir
from llmgauge.core.fit_ladder_validation import validate_fit_ladder_dir
from llmgauge.core.ladder_validation import validate_ladder_dir
from llmgauge.core.result_validation import validate_result_dir



def validate_batch(
    batch_dir: Path = typer.Argument(..., help="LLMGauge model batch directory"),
) -> None:
    """Validate a LLMGauge model batch directory."""
    try:
        errors = validate_batch_dir(batch_dir)
    except Exception as exc:
        console.print(f"[bold red]Batch validation failed[/bold red]: {exc}")
        raise typer.Exit(code=1) from exc

    if errors:
        console.print("[bold red]Batch validation failed[/bold red]")
        for error in errors:
            console.print(f"- {error}")
        raise typer.Exit(code=1)

    console.print(f"[bold green]OK[/bold green] {batch_dir}")



def validate_fit_ladder(
    fit_ladder_dir: Path = typer.Argument(..., help="Fit Ladder artifact directory"),
) -> None:
    """Validate a Fit Ladder artifact directory."""
    errors = validate_fit_ladder_dir(fit_ladder_dir)

    if errors:
        console.print("[bold red]Invalid fit-ladder artifact[/bold red]")
        for error in errors:
            console.print(f"- {error}")
        raise typer.Exit(code=1)

    console.print("[bold green]Fit Ladder artifact is valid[/bold green]")



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
