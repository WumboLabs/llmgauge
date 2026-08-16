from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer

from llmgauge.core import localmaxxing as core

app = typer.Typer(
    help="Dedicated offline LocalMaxxing benchmark integration.", no_args_is_help=True
)


def _artifact(path: Path) -> dict:
    return core.load_artifact(path)


@app.command()
def validate(artifact: Annotated[Path, typer.Argument(exists=True)]) -> None:
    """Validate an immutable benchmark artifact without network access."""
    valid, errors, ineligible = core.validate_artifact(_artifact(artifact))
    if not valid:
        typer.echo("invalid: " + "; ".join(errors), err=True)
        raise typer.Exit(1)
    typer.echo("locally_valid")
    typer.echo(
        "localmaxxing_eligible"
        if not ineligible
        else "localmaxxing_ineligible: " + "; ".join(ineligible)
    )


@app.command()
def export(
    artifact: Annotated[Path, typer.Argument(exists=True)], output: Path | None = None
) -> None:
    """Export an eligible artifact as the LocalMaxxing payload offline."""
    payload = core.export_payload(_artifact(artifact))
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if output:
        output.write_text(rendered, encoding="utf-8")
    else:
        typer.echo(rendered, nl=False)


@app.command("dry-run")
def dry_run(artifact: Annotated[Path, typer.Argument(exists=True)]) -> None:
    """Perform an explicit authenticated non-writing API validation."""
    response = core.checked_online_request(_artifact(artifact))
    typer.echo(json.dumps(response, indent=2, sort_keys=True))


@app.command()
def submit(
    artifact: Annotated[Path, typer.Argument(exists=True)],
    confirm_public: Annotated[
        bool,
        typer.Option(
            "--confirm-public", help="Confirm public LocalMaxxing publication."
        ),
    ] = False,
) -> None:
    """Publicly submit only after explicit confirmation and dry-run validation."""
    if not confirm_public:
        typer.echo("public confirmation required: pass --confirm-public", err=True)
        raise typer.Exit(2)
    receipt_path = (
        artifact if artifact.is_dir() else artifact.parent
    ) / "localmaxxing-submission-receipt.json"
    if receipt_path.exists():
        raise typer.BadParameter("successful submission receipt already exists")
    value = _artifact(artifact)
    core.checked_online_request(value)  # mandatory non-writing validation first
    response = core.checked_online_request(value, submit=True)
    receipt = {
        "artifact_fingerprint": value["fingerprint"],
        "submitted_at": datetime.now(UTC).isoformat(),
        "endpoint": core.SUBMIT_PATH,
        "server_id": response.get("id"),
        "response_status": "success",
    }
    receipt_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    typer.echo(str(receipt_path))


@app.command()
def run(
    output: Annotated[
        Path, typer.Option(help="New artifact directory; it must not exist.")
    ],
    profile: Annotated[str, typer.Option(help="Configured LLMGauge model profile.")],
    hf_id: Annotated[str | None, typer.Option()],
    gpu_name: Annotated[str, typer.Option()],
    vram_gb: Annotated[float, typer.Option()],
    quantization: Annotated[str | None, typer.Option()] = None,
    revision: Annotated[str | None, typer.Option()] = None,
    model_profiles: Annotated[Path | None, typer.Option("--model-profiles")] = None,
    llama_bench: Annotated[Path, typer.Option()] = Path("llama-bench"),
) -> None:
    """Run llama-bench with one warmup plus five measured repetitions offline."""
    from llmgauge.cli_common import default_model_profiles_path
    from llmgauge.core.config import load_model_profiles, resolve_model_profile

    profiles_path = default_model_profiles_path(model_profiles)
    if profiles_path is None:
        raise typer.BadParameter("no model profiles file found")
    selected = resolve_model_profile(load_model_profiles(profiles_path), profile)
    model_path = selected.get("path")
    if not isinstance(model_path, str) or not Path(model_path).is_file():
        raise typer.BadParameter("profile must resolve to an existing model path")
    quantization = quantization or selected.get("quant")
    command = [
        str(llama_bench),
        "-m",
        model_path,
        "-p",
        "512",
        "-n",
        "128",
        "-b",
        "2048",
        "-ub",
        "512",
        "-ngl",
        "-1",
        "-o",
        "json",
        "-r",
        "1",
    ]
    command_provenance = command.copy()
    command_provenance[0] = llama_bench.name
    command_provenance[2] = Path(model_path).name

    sampler = core.NvidiaTelemetrySampler()
    sampler.start()
    try:
        warmup = core.run_llama_bench(command)  # excluded from aggregation
        engine_version = core.llama_bench_version(warmup)
        outputs = [core.run_llama_bench(command) for _ in range(5)]
        measurements = [core.parse_llama_bench_json(value)[0] for value in outputs]
        combined_command = [*command[:3], "-pg", "512,128", *command[7:]]
        combined_warmup = core.run_llama_bench(combined_command)
        combined_outputs = [core.run_llama_bench(combined_command) for _ in range(5)]
        combined_measurements = [
            core.parse_llama_bench_combined_json(value) for value in combined_outputs
        ]
    finally:
        telemetry = sampler.stop()
    runtime = core.llama_bench_runtime_metadata(warmup)
    ttft = None
    ttft_evidence = None
    llama_server = llama_bench.with_name("llama-server")
    if llama_server.is_file():
        ttft, ttft_evidence = core.measure_ttft(
            [
                str(llama_server),
                "-m",
                model_path,
                "-c",
                "1024",
                "-n",
                "128",
                "-b",
                "2048",
                "-ub",
                "512",
                "-ngl",
                "all",
                "-ctk",
                "f16",
                "-ctv",
                "f16",
            ]
        )
    hardware = {
        "hwClass": "DISCRETE_GPU",
        "gpuName": gpu_name,
        "gpuCount": core.probe_nvidia_gpu_count() or 1,
        "vramGb": vram_gb,
        **core.probe_host_hardware(),
    }
    artifact = core.make_artifact(
        hf_id=hf_id,
        quantization=quantization if isinstance(quantization, str) else None,
        model_path=Path(model_path).name,
        engine_version=engine_version,
        backend="cuda",
        hardware=hardware,
        command=" ".join(command_provenance),
        measurements=measurements,
        profile=profile,
        revision=revision,
        executable=llama_bench.name,
        runtime=runtime,
        combined_measurements=combined_measurements,
        ttft=ttft,
        telemetry=telemetry,
    )
    evidence = {
        "executable": str(llama_bench),
        "command": command,
        "combined_command": combined_command,
        "profile": profile,
        "model_path": model_path,
        "engine_version": engine_version,
        "backend": "cuda",
        "runtime": runtime,
        "warmup_stdout": warmup,
        "measured_stdout": outputs,
        "combined_warmup_stdout": combined_warmup,
        "combined_measured_stdout": combined_outputs,
        "exit_status": 0,
    }
    typer.echo(str(core.save_artifact(artifact, output, evidence, ttft_evidence)))
