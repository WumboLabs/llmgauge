from __future__ import annotations

from pathlib import Path

import typer

from llmgauge.cli_common import console, fail_cli_validation
from llmgauge.core.agent_session_review import (
    AgentSessionReviewError,
    apply_review,
    load_review,
    write_report,
    write_template,
)


def agent_session_review(
    result_dir: Path = typer.Argument(
        ..., help="Imported Agent Harness result directory"
    ),
    init: bool = typer.Option(
        False, "--init", help="Create an editable review template"
    ),
    review: Path | None = typer.Option(None, "--review", help="Candidate review JSON"),
    check: bool = typer.Option(
        False, "--check", help="Validate candidate review without writing"
    ),
    apply: bool = typer.Option(
        False, "--apply", help="Validate and publish candidate review"
    ),
    report: bool = typer.Option(
        False, "--report", help="Generate the Agent Harness review report"
    ),
    force: bool = typer.Option(
        False, "--force", help="Replace an existing template or canonical review"
    ),
) -> None:
    """Initialize, validate, apply, or report Agent Harness review metadata."""
    modes = sum((init, check, apply, report))
    if modes != 1:
        fail_cli_validation("use exactly one of --init, --check, --apply, or --report")
    if check and review is None:
        fail_cli_validation("--check requires --review PATH")
    if apply and review is None:
        fail_cli_validation("--apply requires --review PATH")
    if review is not None and not (check or apply):
        fail_cli_validation("--review requires --check or --apply")
    if force and not (init or apply):
        fail_cli_validation("--force can only be used with --init or --apply")
    try:
        if init:
            path = write_template(result_dir, force=force)
            console.print(f"Created Agent Harness review template: {path}")
        elif check:
            candidate = load_review(review)
            from llmgauge.core.agent_session_review import validate_review

            validate_review(candidate, result_dir)
            console.print(f"Agent Harness review validation passed: {review}")
        elif apply:
            path = apply_review(result_dir, load_review(review), force=force)
            console.print(f"Applied Agent Harness review: {path}")
        else:
            path = write_report(result_dir)
            console.print(f"Generated Agent Harness review report: {path}")
    except (AgentSessionReviewError, FileNotFoundError, ValueError) as exc:
        fail_cli_validation(str(exc))
