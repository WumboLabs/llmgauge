from __future__ import annotations

from pathlib import Path

import typer
from rich.table import Table

from llmgauge.cli_common import (
    DEFAULT_LOCAL_MODEL_PROFILES,
    console,
    default_existing_path,
    user_model_profiles_path,
)
from llmgauge.core.config import load_model_profiles


def list_model_profiles(
    model_profiles: Path | None = typer.Option(
        None,
        "--model-profiles",
        help="Model profiles YAML to list; defaults to discovered config",
    ),
) -> None:
    """List configured model profiles and model path status."""
    model_profiles_path = model_profiles or default_existing_path(
        DEFAULT_LOCAL_MODEL_PROFILES,
        user_model_profiles_path(),
    )
    if model_profiles_path is None:
        raise typer.BadParameter(
            "Provide --model-profiles or run llmgauge init first"
        )

    if not model_profiles_path.exists():
        raise typer.BadParameter(
            f"Model profiles file does not exist: {model_profiles_path}"
        )

    try:
        profiles = load_model_profiles(model_profiles_path)
    except Exception as exc:
        raise typer.BadParameter(str(exc)) from exc

    console.print(f"Model profiles file: {model_profiles_path}")

    table = Table(title="Model Profiles")
    table.add_column("Profile", no_wrap=True)
    table.add_column("Label")
    table.add_column("Family")
    table.add_column("Role")
    table.add_column("Quant")
    table.add_column("Path Status", no_wrap=True)

    if not profiles:
        console.print("[yellow]No model profiles found[/yellow]")
        return

    for name, profile in sorted(profiles.items()):
        if not isinstance(profile, dict):
            table.add_row(name, "", "", "", "", "invalid-profile")
            continue

        raw_path = profile.get("path")
        if isinstance(raw_path, str) and raw_path:
            model_path = Path(raw_path)
            path_status = "ok" if model_path.exists() else "missing-file"
        else:
            path_status = "missing-path"

        table.add_row(
            name,
            str(profile.get("label", "")),
            str(profile.get("family", "")),
            str(profile.get("role", "")),
            str(profile.get("quant", "")),
            path_status,
        )

    console.print(table)