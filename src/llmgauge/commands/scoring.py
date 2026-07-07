from __future__ import annotations

from pathlib import Path
from typing import Any

import typer
from rich.table import Table

from llmgauge.cli_common import console, fail_cli_validation
from llmgauge.core.artifacts import write_json, write_text
from llmgauge.core.baseline import check_result_against_baselines
from llmgauge.core.compare import build_compare_report, load_compare_result
from llmgauge.core.export_index import build_export_index, write_export_index
from llmgauge.core.reports import build_markdown_report
from llmgauge.core.scoring import (
    apply_scores,
    build_auto_score_draft,
    build_score_template,
    describe_score_artifact_mismatch,
    load_result,
    load_scores,
    validate_scores,
    write_auto_score_draft,
    write_result,
    write_score_template,
)
from llmgauge.core.suite_paths import resolve_suite_path


def metadata_only_score_prompt_count(scores_data: dict[str, Any]) -> int:
    dimensions = scores_data.get("dimensions")
    scores = scores_data.get("scores")

    if not isinstance(dimensions, list) or not isinstance(scores, dict):
        return 0

    count = 0
    for score_entry in scores.values():
        if not isinstance(score_entry, dict):
            continue

        numeric_values = [
            score_entry.get(dimension)
            for dimension in dimensions
            if isinstance(score_entry.get(dimension), int | float)
        ]
        if not numeric_values:
            count += 1

    return count


def print_metadata_only_score_warning(count: int) -> None:
    if count == 0:
        return

    noun = "entry has" if count == 1 else "entries have"
    console.print(
        "[yellow]Warning[/yellow]: "
        f"{count} prompt score {noun} review metadata but no numeric dimension "
        "values. The result will report review_metadata_only until numeric "
        "dimensions are filled."
    )



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
    check: bool = typer.Option(
        False,
        "--check",
        help="Validate a scores.yaml file without modifying result artifacts",
    ),
    auto_draft: bool = typer.Option(
        False,
        "--auto-draft",
        help="Create an auto-scores.yaml draft using deterministic local rules",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Overwrite an existing auto-scores.yaml when used with --auto-draft",
    ),
) -> None:
    """Initialize or apply manual scores for a completed run."""
    if check and init:
        fail_cli_validation("--check cannot be used with --init")

    if auto_draft and init:
        fail_cli_validation("--auto-draft cannot be used with --init")

    if auto_draft and scores is not None:
        fail_cli_validation("--auto-draft cannot be used with --scores")

    if auto_draft and check:
        fail_cli_validation("--auto-draft cannot be used with --check")

    if force and not auto_draft:
        fail_cli_validation("--force can only be used with --auto-draft")

    if check and scores is None:
        fail_cli_validation("--check requires --scores PATH")

    mismatch = describe_score_artifact_mismatch(result_dir)
    if mismatch:
        raise typer.BadParameter(mismatch)

    result = load_result(result_dir)

    if auto_draft:
        if isinstance(result.get("run"), dict):
            result["run"]["result_dir"] = str(result_dir)
        draft = build_auto_score_draft(result)
        try:
            scores_path = write_auto_score_draft(result_dir, draft, overwrite=force)
        except ValueError as exc:
            fail_cli_validation(str(exc))

        action = "Overwrote" if force else "Created"
        console.print(f"[bold green]{action} auto score draft[/bold green]: {scores_path}")
        console.print("Draft scores are review-required before applying.")
        console.print(
            "Validate next: "
            f"llmgauge score {result_dir} --scores {scores_path} --check"
        )
        return

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

    metadata_only_count = metadata_only_score_prompt_count(scores_data)

    if check:
        console.print(f"[bold green]Score validation passed[/bold green]: {scores}")
        print_metadata_only_score_warning(metadata_only_count)
        return

    print_metadata_only_score_warning(metadata_only_count)
    updated = apply_scores(result, scores_data)
    write_result(result_dir, updated)
    write_text(result_dir / "report.md", build_markdown_report(updated))

    console.print(f"[bold green]Applied scores[/bold green]: {scores}")
    console.print(f"Updated: {result_dir / 'llmgauge-result.json'}")
    console.print(f"Updated: {result_dir / 'report.md'}")



def export_index_command(
    artifact_paths: list[Path] = typer.Argument(
        ...,
        help="LLMGauge run, ladder, or batch directories to index",
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
