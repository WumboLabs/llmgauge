from __future__ import annotations

from pathlib import Path

import typer
from rich.table import Table

from llmgauge.cli_common import console
from llmgauge.core.suite import load_suite, validate_suite
from llmgauge.core.suite_paths import resolve_suite_path, resolve_suites_dir, suite_aliases_for



def list_suites(suites_dir: Path | None = typer.Argument(None)) -> None:
    """List available suites."""
    resolved_suites_dir = resolve_suites_dir(suites_dir)
    table = Table(title="Available Suites", expand=True)
    table.add_column("Suite ID", no_wrap=True)
    table.add_column("Aliases", no_wrap=True)
    table.add_column("Version", no_wrap=True)
    table.add_column("Prompts", no_wrap=True)
    table.add_column("Path", no_wrap=True)

    for suite_file in sorted(resolved_suites_dir.glob("*/suite.yaml")):
        suite = load_suite(suite_file.parent)
        suite_id = str(suite.get("suite_id", suite_file.parent.name))
        aliases = ", ".join(suite_aliases_for(suite_id)) or "—"
        table.add_row(
            suite_id,
            aliases,
            str(suite.get("suite_version", "")),
            str(len(suite.get("prompts", []))),
            str(suite_file.parent),
        )

    console.print(table)



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
