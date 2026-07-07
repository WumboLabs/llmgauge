from __future__ import annotations

import typer

from llmgauge.commands import batch, ladders, models, run_cmd, run_helpers, scoring, setup, suites, validate_cmd

app = typer.Typer(
    name="llmgauge",
    help="Practical local LLM evaluation on real hardware.",
    no_args_is_help=True,
)


@app.callback()
def cli_options(
    version: bool = typer.Option(
        False,
        "--version",
        help="Show the LLMGauge version and exit.",
        callback=setup.show_version,
        is_eager=True,
    ),
) -> None:
    """Practical local LLM evaluation on real hardware."""


app.command("version")(setup.version_command)
app.command()(setup.doctor)
app.command("list-suites")(suites.list_suites)
app.command("validate-suite")(suites.validate_suite_command)
app.command("init")(setup.init)
app.command("init-config")(setup.init_config)
app.command()(setup.smoke)
app.command("list-model-profiles")(models.list_model_profiles)
app.add_typer(models.model_app)
app.command()(run_cmd.contextgen)
app.command()(run_cmd.run)
app.command("fit-ladder")(ladders.fit_ladder)
app.command("run-ladder")(ladders.run_ladder)
app.command("run-batch")(batch.run_batch)
app.command("validate-batch")(validate_cmd.validate_batch)
app.command("validate-fit-ladder")(validate_cmd.validate_fit_ladder)
app.command("validate-ladder")(validate_cmd.validate_ladder)
app.command("validate-result")(validate_cmd.validate_result)
app.command()(scoring.score)
app.command("export-index")(scoring.export_index_command)
app.command("baseline-check")(scoring.baseline_check_command)
app.command()(scoring.compare)

# Backward-compatible re-exports for tests and downstream imports.
_resolve_run_options = run_helpers.resolve_run_options
_execute_run = run_helpers.execute_run
run_batch = batch.run_batch


def main() -> None:
    app()


if __name__ == "__main__":
    main()