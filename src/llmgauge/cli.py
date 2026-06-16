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


def _select_prompts(suite: dict, only: str | None, include: str) -> list[dict]:
    prompts = suite.get("prompts", [])

    if only:
        return [_find_prompt(suite, only)]

    if include == "all":
        return list(prompts)

    selected = [prompt for prompt in prompts if prompt.get("category") == include]
    if not selected:
        raise typer.BadParameter(f"No prompts found for include/category: {include}")

    return selected


def _load_system_prompt() -> str:
    path = Path("suites/core-v1/prompts/system-conservative-ops.txt")
    if path.exists():
        return path.read_text(encoding="utf-8").strip()

    return (
        "You are a conservative local systems assistant. "
        "Prefer safe, reversible, verified steps. "
        "Say when unsure. Do not invent commands, packages, flags, or docs."
    )


def _build_combined_prompt(system_prompt: str, prompt_text: str) -> str:
    return "\n\n".join(
        [
            "SYSTEM:",
            system_prompt,
            "USER:",
            prompt_text,
        ]
    )


def _redacted_command(command: list[str], model_path: Path) -> list[str]:
    return [arg if arg != str(model_path) else "REDACTED_MODEL_PATH" for arg in command]


@app.command()
def run(
    suite: Path = typer.Option(..., "--suite", help="Suite directory"),
    only: str | None = typer.Option(None, "--only", help="Prompt ID to run"),
    include: str = typer.Option(
        "all",
        "--include",
        help="Prompt category to run, or 'all'. Ignored when --only is set.",
    ),
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
    """Run one or more prompts through llama.cpp."""
    if not model_path.exists():
        raise typer.BadParameter(f"Model path does not exist: {model_path}")

    if not llama_cli.exists():
        raise typer.BadParameter(f"llama-cli path does not exist: {llama_cli}")

    loaded_suite = load_suite(suite)
    selected_prompts = _select_prompts(loaded_suite, only, include)
    system_prompt = _load_system_prompt()

    prepare_result_dir(out)

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

    timestamp = datetime.now(UTC).replace(microsecond=0).isoformat()
    run_id = out.name
    prompt_results: list[dict] = []
    redacted_command: list[str] | None = None

    console.print(
        f"Running [bold]{len(selected_prompts)}[/bold] prompt(s) "
        f"with model [bold]{model_id}[/bold]"
    )

    for index, prompt_meta in enumerate(selected_prompts, start=1):
        prompt_id = prompt_meta["id"]
        prompt_path = suite / prompt_meta["file"]
        prompt_text = prompt_path.read_text(encoding="utf-8").strip()
        combined_prompt = _build_combined_prompt(system_prompt, prompt_text)

        raw_prompt_path = out / "raw" / f"{prompt_id}.prompt.md"
        raw_output_path = out / "raw" / f"{prompt_id}.output.txt"
        stderr_log_path = out / "logs" / f"{prompt_id}.stderr.log"

        write_text(raw_prompt_path, combined_prompt)

        console.print(f"[{index}/{len(selected_prompts)}] Running {prompt_id}")
        run_result = run_llama_cpp(config, combined_prompt)

        if redacted_command is None:
            redacted_command = _redacted_command(run_result.command, model_path)

        write_text(raw_output_path, run_result.stdout)
        write_text(stderr_log_path, run_result.stderr)

        metrics = parse_llama_metrics(run_result.stdout + "\n" + run_result.stderr)
        status = "completed" if run_result.exit_status == 0 else "failed"

        prompt_results.append(
            {
                "prompt_id": prompt_id,
                "title": prompt_meta.get("title", prompt_id),
                "category": prompt_meta.get("category"),
                "status": status,
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
        )

    completed_count = sum(1 for item in prompt_results if item["status"] == "completed")
    failed_count = sum(1 for item in prompt_results if item["status"] == "failed")
    run_status = "completed" if failed_count == 0 else "failed"

    result = {
        "schema_version": "llmgauge.result.v0",
        "llmgauge_version": "0.1.0",
        "run": {
            "run_id": run_id,
            "timestamp_utc": timestamp,
            "status": run_status,
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
            "command": redacted_command or [],
        },
        "suite": {
            "suite_id": loaded_suite["suite_id"],
            "suite_version": str(loaded_suite["suite_version"]),
            "suite_path": str(suite),
            "prompt_count": len(prompt_results),
            "include": include,
            "only": only,
        },
        "results": prompt_results,
        "summary": {
            "completed": completed_count,
            "failed": failed_count,
            "manual_score_total": None,
            "manual_score_max": None,
            "failure_labels": {},
        },
    }

    write_json(out / "llmgauge-result.json", result)
    write_text(out / "report.md", build_markdown_report(result))

    if failed_count:
        console.print(f"[bold red]Run completed with failures[/bold red]: {out}")
        raise typer.Exit(code=1)

    console.print(f"[bold green]Run completed[/bold green]: {out}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
