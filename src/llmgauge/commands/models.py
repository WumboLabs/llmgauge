from __future__ import annotations

from pathlib import Path

import typer
from rich.table import Table

from llmgauge.cli_common import (
    MODEL_PROFILES_FILE_OPTIONS,
    console,
    default_model_profiles_path,
)
from llmgauge.core.model_profiles_store import (
    add_model_profile,
    load_model_profiles_document,
    remove_model_profile,
    update_model_profile,
)
from llmgauge.core.schemas import (
    MODEL_SOURCE_KINDS,
    effective_source_kind,
    resolve_profile_source_status,
)

model_app = typer.Typer(
    name="model",
    help="Manage configured local model profiles.",
    no_args_is_help=True,
)


def _resolve_profiles_path(model_profiles: Path | None) -> Path:
    resolved = default_model_profiles_path(model_profiles)
    if resolved is None:
        raise typer.BadParameter(
            "No model profiles file found. Pass --model-profile-file "
            "(or --model-profiles) or run 'llmgauge init' first."
        )
    return resolved


def _normalize_source_kind_option(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized not in MODEL_SOURCE_KINDS:
        raise typer.BadParameter(
            "source_kind must be one of: " + ", ".join(MODEL_SOURCE_KINDS)
        )
    return normalized


def _validate_source_path(source_kind: str | None, path: Path) -> None:
    """Apply the filesystem source-shape rule for a CLI-supplied path.

    ``source_kind`` here is the effective kind (explicit or legacy). Legacy
    no-discriminator profiles keep the contractual GGUF file rule; a path is
    never reinterpreted as a checkpoint directory because it happens to exist
    as one.
    """
    if source_kind == "checkpoint_directory":
        if not path.exists():
            raise typer.BadParameter(f"Checkpoint directory does not exist: {path}")
        if not path.is_dir():
            raise typer.BadParameter(f"Checkpoint path is not a directory: {path}")
        return

    if not path.exists():
        raise typer.BadParameter(f"Model path does not exist: {path}")
    if not path.is_file():
        raise typer.BadParameter(f"Model path is not a file: {path}")


def render_model_profiles_table(model_profiles_path: Path) -> None:
    document = load_model_profiles_document(model_profiles_path)
    console.print(f"Model profiles file: {model_profiles_path}")

    table = Table(title="Model Profiles")
    table.add_column("Profile", no_wrap=True)
    table.add_column("Label", no_wrap=True)
    table.add_column("Family")
    table.add_column("Role")
    table.add_column("Quant")
    table.add_column("Source Kind", no_wrap=True)
    table.add_column("Source Status", no_wrap=True)

    if not document.models:
        console.print("[yellow]No model profiles found[/yellow]")
        return

    for name, profile in sorted(document.models.items()):
        data = profile.model_dump(exclude_none=True)
        table.add_row(
            name,
            str(profile.label or ""),
            str(profile.family or ""),
            str(profile.role or ""),
            str(profile.quant or ""),
            effective_source_kind(data),
            resolve_profile_source_status(data),
        )

    console.print(table)


def list_model_profiles(
    model_profiles: Path | None = typer.Option(
        None,
        *MODEL_PROFILES_FILE_OPTIONS,
        help="Model profiles YAML to list; defaults to discovered config",
    ),
) -> None:
    """List configured model profiles and model source status."""
    model_profiles_path = _resolve_profiles_path(model_profiles)
    if not model_profiles_path.exists():
        raise typer.BadParameter(
            f"Model profiles file does not exist: {model_profiles_path}"
        )

    try:
        render_model_profiles_table(model_profiles_path)
    except (OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc


@model_app.command("list")
def model_list(
    model_profiles: Path | None = typer.Option(
        None,
        *MODEL_PROFILES_FILE_OPTIONS,
        help="Model profiles YAML to list; defaults to discovered config",
    ),
) -> None:
    """List configured model profiles."""
    list_model_profiles(model_profiles=model_profiles)


@model_app.command("add")
def model_add(
    profile_name: str = typer.Argument(..., help="Model profile name"),
    path: Path | None = typer.Option(
        None,
        "--path",
        help="Local model path (GGUF file or checkpoint directory)",
    ),
    source_kind: str | None = typer.Option(
        None,
        "--source-kind",
        help=(
            "Model source kind: gguf_file, checkpoint_directory, or "
            "served_model_reference; omit for a legacy GGUF file profile"
        ),
    ),
    served_model: str | None = typer.Option(
        None,
        "--served-model",
        help="Served-model identifier for served_model_reference profiles",
    ),
    label: str | None = typer.Option(None, "--label", help="Display label"),
    family: str | None = typer.Option(None, "--family", help="Model family"),
    role: str | None = typer.Option(None, "--role", help="Evaluation role label"),
    quant: str | None = typer.Option(None, "--quant", help="Quantization label"),
    ctx_size: int | None = typer.Option(
        None, "--ctx-size", help="Default context size"
    ),
    max_tokens: int | None = typer.Option(
        None, "--max-tokens", help="Default max tokens"
    ),
    temperature: float | None = typer.Option(
        None, "--temp", help="Default temperature"
    ),
    notes: str | None = typer.Option(None, "--notes", help="Optional notes"),
    model_profiles: Path | None = typer.Option(
        None,
        *MODEL_PROFILES_FILE_OPTIONS,
        help="Model profiles YAML to update; defaults to discovered config",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Overwrite an existing profile with the same name",
    ),
) -> None:
    """Add or replace a model profile."""
    model_profiles_path = _resolve_profiles_path(model_profiles)
    normalized_source_kind = _normalize_source_kind_option(source_kind)

    if normalized_source_kind is None:
        # Legacy shape: --path is a required GGUF file; no discriminator is
        # stored, so existing profiles and commands behave exactly as before.
        if path is None:
            raise typer.BadParameter(
                "Missing option '--path' (or pass --source-kind for a "
                "checkpoint directory or served-model reference)"
            )
        _validate_source_path("gguf_file", path)
    elif normalized_source_kind == "served_model_reference":
        if path is not None:
            raise typer.BadParameter(
                "--source-kind served_model_reference does not accept --path "
                "in this contract; identify the model with --served-model only"
            )
        if served_model is None or not served_model.strip():
            raise typer.BadParameter(
                "--source-kind served_model_reference requires --served-model"
            )
    else:
        if path is None:
            raise typer.BadParameter(
                f"--source-kind {normalized_source_kind} requires --path"
            )
        _validate_source_path(normalized_source_kind, path)

    try:
        _, created = add_model_profile(
            model_profiles_path,
            profile_name=profile_name,
            model_path=path,
            label=label,
            family=family,
            role=role,
            quant=quant,
            ctx_size=ctx_size,
            max_tokens=max_tokens,
            temperature=temperature,
            notes=notes,
            overwrite=force,
            source_kind=normalized_source_kind,
            served_model=served_model,
        )
    except (OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc

    action = "Added" if created else "Updated"
    console.print(
        f"[bold green]{action} model profile[/bold green]: "
        f"{profile_name} -> {model_profiles_path}"
    )


@model_app.command("remove")
def model_remove(
    profile_name: str = typer.Argument(..., help="Model profile name"),
    model_profiles: Path | None = typer.Option(
        None,
        *MODEL_PROFILES_FILE_OPTIONS,
        help="Model profiles YAML to update; defaults to discovered config",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        help="Confirm removal without an interactive prompt",
    ),
) -> None:
    """Remove a model profile."""
    if not yes:
        raise typer.BadParameter("Pass --yes to confirm model profile removal")

    model_profiles_path = _resolve_profiles_path(model_profiles)

    try:
        remove_model_profile(model_profiles_path, profile_name=profile_name)
    except FileNotFoundError as exc:
        raise typer.BadParameter(str(exc)) from exc
    except KeyError as exc:
        raise typer.BadParameter(str(exc)) from exc
    except (OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc

    console.print(
        f"[bold green]Removed model profile[/bold green]: "
        f"{profile_name} from {model_profiles_path}"
    )


@model_app.command("update")
def model_update(
    profile_name: str = typer.Argument(..., help="Model profile name"),
    path: Path | None = typer.Option(
        None,
        "--path",
        help="Local model path (GGUF file or checkpoint directory)",
    ),
    source_kind: str | None = typer.Option(
        None,
        "--source-kind",
        help=(
            "Model source kind: gguf_file, checkpoint_directory, or "
            "served_model_reference"
        ),
    ),
    served_model: str | None = typer.Option(
        None,
        "--served-model",
        help="Served-model identifier for served_model_reference profiles",
    ),
    label: str | None = typer.Option(None, "--label", help="Display label"),
    family: str | None = typer.Option(None, "--family", help="Model family"),
    role: str | None = typer.Option(None, "--role", help="Evaluation role label"),
    quant: str | None = typer.Option(None, "--quant", help="Quantization label"),
    ctx_size: int | None = typer.Option(
        None, "--ctx-size", help="Default context size"
    ),
    max_tokens: int | None = typer.Option(
        None, "--max-tokens", help="Default max tokens"
    ),
    temperature: float | None = typer.Option(
        None, "--temp", help="Default temperature"
    ),
    notes: str | None = typer.Option(None, "--notes", help="Optional notes"),
    model_profiles: Path | None = typer.Option(
        None,
        *MODEL_PROFILES_FILE_OPTIONS,
        help="Model profiles YAML to update; defaults to discovered config",
    ),
) -> None:
    """Update fields on an existing model profile."""
    model_profiles_path = _resolve_profiles_path(model_profiles)
    normalized_source_kind = _normalize_source_kind_option(source_kind)

    if all(
        value is None
        for value in (
            path,
            normalized_source_kind,
            served_model,
            label,
            family,
            role,
            quant,
            ctx_size,
            max_tokens,
            temperature,
            notes,
        )
    ):
        raise typer.BadParameter("Provide at least one field to update")

    # Filesystem validation follows the effective source kind after the
    # update. Incompatible representation switches (for example keeping a
    # local path while moving to served_model_reference) fail closed in the
    # store's schema validation; remove/re-add or --force replacement remains
    # the supported conversion path.
    if path is not None:
        effective_kind = normalized_source_kind
        if effective_kind is None:
            try:
                document = load_model_profiles_document(model_profiles_path)
            except (OSError, ValueError) as exc:
                raise typer.BadParameter(str(exc)) from exc
            existing = document.models.get(profile_name)
            if existing is not None:
                effective_kind = effective_source_kind(
                    existing.model_dump(exclude_none=True)
                )
        _validate_source_path(effective_kind, path)

    try:
        update_model_profile(
            model_profiles_path,
            profile_name=profile_name,
            model_path=path,
            label=label,
            family=family,
            role=role,
            quant=quant,
            ctx_size=ctx_size,
            max_tokens=max_tokens,
            temperature=temperature,
            notes=notes,
            source_kind=normalized_source_kind,
            served_model=served_model,
        )
    except FileNotFoundError as exc:
        raise typer.BadParameter(str(exc)) from exc
    except KeyError as exc:
        raise typer.BadParameter(str(exc)) from exc
    except (OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc

    console.print(
        f"[bold green]Updated model profile[/bold green]: "
        f"{profile_name} in {model_profiles_path}"
    )
