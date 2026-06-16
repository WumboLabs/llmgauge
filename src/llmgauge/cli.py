from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from llmgauge.core.artifacts import prepare_result_dir, write_json, write_text
from llmgauge.core.metrics import parse_llama_metrics
from llmgauge.core.reports import build_markdown_report
from llmgauge.core.suite import load_suite, validate_suite
from llmgauge.runners.llama_cpp import LlamaCppRunConfig, run_llama_cpp

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
    table.add_row("Runner", "available", "llama.cpp runner module installed")
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


def _find_prompt(suite: dict, prompt_id: str) -> dict:
    for prompt in suite.get("prompts", []):
        if prompt.get("id") == prompt_id:
            return prompt
    raise typer.BadParameter(f"Prompt ID not found in suite: {prompt_id}")


def _load_system_prompt() -> str:
    path = Path("suites/core-v1/prompts/system-conservative-ops.txt")
    if path.exists():
        return path.read_text(encoding="utf-8").strip()

    return (
        "You are a conservative local systems assistant. "
        "Prefer safe, reversible, verified steps. "
        "Say when unsure. Do not invent commands, packages, flags, or docs."
    )


@app.command()
def run(
    suite: Path = typer.Option(..., "--suite", help="Suite directory"),
    only: str = typer.Option(..., "--only", help="Prompt ID to run"),
    model_id: str = typer.Option(..., "--model-id", help="Model identifier"),
    model_path: Path = typer.Option(..., "--model-path", help="GGUF model path"),
    llama_cli: Path = typer.Option(..., "--llama-cli", help="llama-cli path"),
    ctx: int = typer.Option(8192, "--ctx", help="Context size"),
    max_tokens: int = typer.Option(800, "--max-tokens", help="Max generated tokens"),
    temp: float = typer.Option(0.2, "--temp", help="Temperature"),
    top_p: float = typer.Option(0.95, "--top-p", help="Top-p"),
    batch: int = typer.Option(256, "--batch", help="Batch size"),
    ubatch: int = typer.Option(64, "--ubatch", help="Micro-batch size"),
    gpu_layers: int = typer.Option(999, "--gpu-layers", help="GPU layers"),
    out: Path = typer.Option(..., "--out", help="Output result directory"),
) -> None:
    """Run one prompt through llama.cpp."""
    if not model_path.exists():
        raise typer.BadParameter(f"Model path does not exist: {model_path}")

    if not llama_cli.exists():
        raise typer.BadParameter(f"llama-cli path does not exist: {llama_cli}")

    loaded_suite = load_suite(suite)
    prompt_meta = _find_prompt(loaded_suite, only)
    prompt_path = suite / prompt_meta["file"]
    prompt_text = prompt_path.read_text(encoding="utf-8").strip()

    system_prompt = _load_system_prompt()
    combined_prompt = "\n\n".join(
        [
            "SYSTEM:",
            system_prompt,
            "USER:",
            prompt_text,
        ]
    )

    prepare_result_dir(out)

    raw_prompt_path = out / "raw" / f"{only}.prompt.md"
    raw_output_path = out / "raw" / f"{only}.output.txt"
    stderr_log_path = out / "logs" / f"{only}.stderr.log"

    write_text(raw_prompt_path, combined_prompt)

    config = LlamaCppRunConfig(
        llama_cli=llama_cli,
        model_path=model_path,
        ctx_size=ctx,
        max_tokens=max_tokens,
        temperature=temp,
        top_p=top_p,
        batch_size=batch,
        ubatch_size=ubatch,
        gpu_layers=gpu_layers,
    )

    console.print(
        f"Running prompt [bold]{only}[/bold] with model [bold]{model_id}[/bold]"
    )
    run_result = run_llama_cpp(config, combined_prompt)

    write_text(raw_output_path, run_result.stdout)
    write_text(stderr_log_path, run_result.stderr)

    metrics = parse_llama_metrics(run_result.stdout + "\n" + run_result.stderr)

    timestamp = datetime.now(UTC).replace(microsecond=0).isoformat()
    run_id = out.name

    result = {
        "schema_version": "llmgauge.result.v0",
        "llmgauge_version": "0.1.0",
        "run": {
            "run_id": run_id,
            "timestamp_utc": timestamp,
            "status": "completed" if run_result.exit_status == 0 else "failed",
            "result_dir": str(out),
        },
        "model": {
            "model_id": model_id,
            "model_path": "redacted",
            "model_path_policy": "redacted",
        },
        "runtime": {
            "backend": "llama.cpp",
            "llama_cli": str(llama_cli),
            "ctx_size": ctx,
            "max_tokens": max_tokens,
            "temperature": temp,
            "top_p": top_p,
            "batch_size": batch,
            "ubatch_size": ubatch,
            "gpu_layers": gpu_layers,
            "command": [
                arg if arg != str(model_path) else "REDACTED_MODEL_PATH"
                for arg in run_result.command
            ],
        },
        "suite": {
            "suite_id": loaded_suite["suite_id"],
            "suite_version": str(loaded_suite["suite_version"]),
            "suite_path": str(suite),
            "prompt_count": 1,
        },
        "results": [
            {
                "prompt_id": only,
                "title": prompt_meta.get("title", only),
                "category": prompt_meta.get("category"),
                "status": "completed" if run_result.exit_status == 0 else "failed",
                "raw_prompt_path": str(raw_prompt_path.relative_to(out)),
                "raw_output_path": str(raw_output_path.relative_to(out)),
                "stderr_log_path": str(stderr_log_path.relative_to(out)),
                "metrics": metrics,
                "score": None,
                "failure_labels": [],
                "notes": "",
                "exit_status": run_result.exit_status,
                "error": None
                if run_result.exit_status == 0
                else "llama-cli exited nonzero",
            }
        ],
        "summary": {
            "completed": 1 if run_result.exit_status == 0 else 0,
            "failed": 0 if run_result.exit_status == 0 else 1,
            "manual_score_total": None,
            "manual_score_max": None,
            "failure_labels": {},
        },
    }

    write_json(out / "llmgauge-result.json", result)
    write_text(out / "report.md", build_markdown_report(result))

    if run_result.exit_status != 0:
        console.print("[bold red]Run failed[/bold red]")
        console.print(f"See log: {stderr_log_path}")
        raise typer.Exit(code=run_result.exit_status)

    console.print(f"[bold green]Run completed[/bold green]: {out}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
