from __future__ import annotations

from pathlib import Path

import typer

from llmgauge.cli_common import console
from llmgauge.core.agent_harness import (
    AgentHarnessImportError,
    import_agent_harness_session,
)


def import_agent_harness_command(
    source: Path = typer.Argument(..., help="Local OMP v3 session JSONL file"),
    result_dir: Path = typer.Argument(..., help="New LLMGauge result directory"),
    blob_dir: Path | None = typer.Option(
        None,
        "--blob-dir",
        help="Explicit OMP blob directory when the session references blobs",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Validate and identify the source without writing result artifacts",
    ),
) -> None:
    """Import one OMP v3 session as contained read-only evidence."""

    try:
        outcome = import_agent_harness_session(
            source,
            result_dir,
            blob_dir=blob_dir,
            dry_run=dry_run,
        )
    except AgentHarnessImportError as exc:
        console.print(
            f"[bold red]Agent Harness import failed[/bold red] ({exc.outcome}): {exc}"
        )
        raise typer.Exit(code=1) from exc
    except OSError as exc:
        console.print(
            "[bold red]Agent Harness import failed[/bold red]: local I/O error"
        )
        raise typer.Exit(code=1) from exc

    if outcome.outcome == "already_imported":
        console.print(
            "[bold green]Already imported[/bold green]: evidence is unchanged"
        )
        return
    if outcome.outcome == "dry_run":
        console.print(
            "[bold green]Agent Harness source accepted[/bold green]: dry run wrote no artifacts"
        )
        return
    console.print(
        f"[bold green]Imported Agent Harness evidence[/bold green]: {result_dir}"
    )
    console.print(
        "Structural validation passed; this does not prove task success, quality, "
        "scoreability, or publication readiness."
    )
