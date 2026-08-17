from __future__ import annotations

import json
from pathlib import Path

import typer

from llmgauge.cli_common import console
from llmgauge.core.external_benchmark import (
    ExternalBenchmarkImportError,
    import_lm_eval_harness_results,
)
from llmgauge.core.external_benchmark_report import (
    ExternalBenchmarkReportError,
    write_external_benchmark_report,
)
from llmgauge.core.result_validation import load_result_json, validate_result_dir


app = typer.Typer(
    help="Read-only external benchmark import, validation, and reporting.",
    no_args_is_help=True,
)


@app.command("import")
def import_command(
    source: Path = typer.Argument(
        ..., help="lm-eval results JSON file or result directory"
    ),
    result_dir: Path = typer.Argument(..., help="New LLMGauge result directory"),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Validate and identify the source without writing result artifacts",
    ),
) -> None:
    """Import one lm-eval result package as contained read-only evidence."""

    try:
        outcome = import_lm_eval_harness_results(
            source,
            result_dir,
            dry_run=dry_run,
        )
    except ExternalBenchmarkImportError as exc:
        console.print(
            f"[bold red]External benchmark import failed[/bold red] ({exc.outcome}): {exc}"
        )
        raise typer.Exit(code=1) from exc
    except OSError as exc:
        console.print(
            "[bold red]External benchmark import failed[/bold red]: local I/O error"
        )
        raise typer.Exit(code=1) from exc

    if outcome.outcome == "already_imported":
        console.print(
            "[bold green]Already imported[/bold green]: evidence is unchanged"
        )
        return
    if outcome.outcome == "dry_run":
        console.print(
            "[bold green]External benchmark source accepted[/bold green]: "
            "dry run wrote no artifacts"
        )
        return
    console.print(
        f"[bold green]Imported external benchmark evidence[/bold green]: {result_dir}"
    )
    console.print(
        "Structural validation passed; this does not prove official acceptance, "
        "answer quality, or publication readiness."
    )


@app.command("validate")
def validate_command(
    result_dir: Path = typer.Argument(
        ..., help="Imported external-benchmark result directory"
    ),
) -> None:
    """Validate contained external-benchmark evidence without network access."""

    try:
        data = load_result_json(result_dir)
        if data.get("external_benchmark_evidence") is None:
            raise ExternalBenchmarkImportError(
                "failed", "result is not imported external benchmark evidence"
            )
        errors = validate_result_dir(result_dir)
    except ExternalBenchmarkImportError as exc:
        console.print(
            f"[bold red]External benchmark validation failed[/bold red]: {exc}"
        )
        raise typer.Exit(code=1) from exc
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        console.print(
            "[bold red]External benchmark validation failed[/bold red]: "
            "result could not be read"
        )
        raise typer.Exit(code=1) from exc

    if errors:
        console.print("[bold red]External benchmark validation failed[/bold red]")
        for error in errors:
            console.print(f"- {error}")
        raise typer.Exit(code=1)

    console.print(f"[bold green]OK[/bold green] {result_dir}")
    console.print(
        "Structural validation passed; this does not prove official acceptance, "
        "answer quality, or publication readiness."
    )


@app.command("report")
def report_command(
    result_dir: Path = typer.Argument(
        ..., help="Imported external-benchmark result directory"
    ),
) -> None:
    """Write a read-only report from imported external-benchmark evidence."""

    try:
        path, qualification = write_external_benchmark_report(result_dir)
    except ExternalBenchmarkReportError as exc:
        console.print(f"[bold red]External benchmark report failed[/bold red]: {exc}")
        raise typer.Exit(code=1) from exc
    except (OSError, ValueError) as exc:
        console.print(
            "[bold red]External benchmark report failed[/bold red]: "
            "result could not be reported"
        )
        raise typer.Exit(code=1) from exc

    console.print(f"[bold green]Wrote external benchmark report[/bold green]: {path}")
    console.print(
        f"Bundle 1 status: {qualification.overall_status}. "
        "This is not a quality score, ranking, or publication decision."
    )
