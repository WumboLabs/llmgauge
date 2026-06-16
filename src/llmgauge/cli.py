from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from llmgauge.core.suite import load_suite, validate_suite

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
    table.add_row("Runner", "not checked", "Runner validation will be added in v0.02")
    table.add_row("Suites", "manual", "Run: llmgauge validate-suite suites/core-v1")

    console.print(table)


@app.command("list-suites")
def list_suites(suites_dir: Path = typer.Argument(Path("suites"))) -> None:
    """List available prompt suites."""
    if not suites_dir.exists():
        raise typer.BadParameter(f"Suites directory does not exist: {suites_dir}")

    table = Table(title="Available Suites")
    table.add_column("Suite ID")
    table.add_column("Version")
    table.add_column("Title")
    table.add_column("Prompts")

    for suite_file in sorted(suites_dir.glob("*/suite.yaml")):
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
    errors = validate_suite(suite_dir)

    if errors:
        console.print("[bold red]Suite validation failed[/bold red]")
        for error in errors:
            console.print(f"- {error}")
        raise typer.Exit(code=1)

    suite = load_suite(suite_dir)
    console.print(
        f"[bold green]OK[/bold green] {suite['suite_id']} "
        f"({len(suite.get('prompts', []))} prompts)"
    )


@app.command()
def run(
    suite: Path = typer.Option(..., "--suite", help="Suite directory"),
    only: Optional[str] = typer.Option(None, "--only", help="Prompt ID to run"),
) -> None:
    """Run an evaluation suite. Placeholder until runner v0.02."""
    loaded = load_suite(suite)
    console.print(f"Loaded suite: [bold]{loaded['suite_id']}[/bold]")

    if only:
        console.print(f"Requested prompt: {only}")

    console.print("[yellow]Runner implementation comes next in v0.02.[/yellow]")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
