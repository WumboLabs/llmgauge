from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import typer
from rich.table import Table

from llmgauge import __version__
from llmgauge.cli_common import (
    DEFAULT_LOCAL_CONFIG,
    DEFAULT_LOCAL_MODEL_PROFILES,
    MODEL_PROFILES_FILE_OPTIONS,
    console,
    default_existing_path,
    is_placeholder_path,
    llmgauge_user_config_dir,
    read_packaged_template,
    user_config_path,
    user_model_profiles_path,
)
from llmgauge.core.config import (
    coalesce,
    get_config_value,
    load_llmgauge_config,
    load_model_profiles,
    resolve_model_profile,
)
from llmgauge.core.suite_paths import resolve_suites_dir


@dataclass
class SetupReadiness:
    config_found: bool = False
    profiles_loaded: bool = False
    llama_cli_ready: bool = False
    setup_skipped: bool = False
    setup_warnings: bool = False


def _config_missing_note() -> str:
    return "Skipped; no config file found. Run llmgauge init or provide --config"


def _profiles_missing_note() -> str:
    return (
        "Skipped; no profiles file found. Run llmgauge init, add a profile with "
        "llmgauge model add, or pass --model-profile-file "
        "(--model-profiles also accepted)"
    )


def _model_profile_without_profiles_note() -> str:
    return (
        "Cannot check profile; profiles file was not loaded. Run llmgauge init or "
        "pass --model-profile-file (or --model-profiles), then retry --model-profile"
    )


def _collect_first_run_next_steps(readiness: SetupReadiness) -> list[str]:
    steps: list[str] = []
    if readiness.setup_skipped or not readiness.config_found:
        steps.append("Run llmgauge init to create user config files")
    elif not readiness.llama_cli_ready:
        steps.append("Edit config.yaml and set runtime.llama_cli")
    if readiness.setup_skipped or not readiness.profiles_loaded:
        steps.append(
            "Add a model profile with llmgauge model add or edit model-profiles.yaml"
        )
    steps.extend(
        [
            "Run llmgauge model list to verify profile paths",
            "Run llmgauge smoke for a quick readiness check",
            "Preview a run with llmgauge run --dry-run",
        ]
    )
    return steps


def _print_first_run_next_steps(readiness: SetupReadiness) -> None:
    if not (readiness.setup_skipped or readiness.setup_warnings):
        return

    console.print("Next steps:")
    for index, step in enumerate(_collect_first_run_next_steps(readiness), start=1):
        console.print(f"  {index}. {step}")


def show_version(value: bool) -> None:
    if value:
        console.print(f"llmgauge {__version__}")
        raise typer.Exit()






def version_command() -> None:
    """Show the LLMGauge version."""
    console.print(f"llmgauge {__version__}")



def doctor(
    config: Path | None = typer.Option(
        None,
        "--config",
        help="Optional LLMGauge config YAML to check",
    ),
    model_profiles: Path | None = typer.Option(
        None,
        *MODEL_PROFILES_FILE_OPTIONS,
        help="Optional model profiles YAML to check",
    ),
    model_profile: str | None = typer.Option(
        None,
        "--model-profile",
        help="Optional model profile name to resolve and check",
    ),
    llama_cli: Path | None = typer.Option(
        None,
        "--llama-cli",
        help="Optional llama-cli path override to check",
    ),
) -> None:
    """Check the local LLMGauge environment."""
    table = Table(title="LLMGauge Doctor")
    table.add_column("Check")
    table.add_column("Status")
    table.add_column("Notes")

    has_failure = False
    readiness = SetupReadiness()

    def add_row(check: str, status: str, notes: str) -> None:
        nonlocal has_failure
        if status == "fail":
            has_failure = True
        table.add_row(check, status, notes)

    add_row("Python package", "ok", "LLMGauge import works")
    add_row("Runner", "ok", "llama.cpp runner module installed")

    try:
        suites_dir = resolve_suites_dir()
        suite_count = len(list(suites_dir.glob("*/suite.yaml")))
        if suite_count:
            add_row(
                "Built-in suites",
                "ok",
                f"{suite_count} suite(s) available at {suites_dir}",
            )
        else:
            add_row("Built-in suites", "fail", f"No suite.yaml files under {suites_dir}")
    except Exception as exc:
        add_row("Built-in suites", "fail", str(exc))

    config_data: dict[str, Any] = {}
    config_path = config or default_existing_path(DEFAULT_LOCAL_CONFIG, user_config_path())
    if config_path is None:
        readiness.setup_skipped = True
        add_row("Config", "skip", _config_missing_note())
    else:
        try:
            config_data = load_llmgauge_config(config_path)
            readiness.config_found = True
            if config is None:
                add_row("Config", "ok", f"Auto-detected {config_path}")
            else:
                add_row("Config", "ok", f"Loaded {config_path}")
        except Exception as exc:
            add_row("Config", "fail", str(exc))

    resolved_llama_cli = coalesce(
        llama_cli,
        get_config_value(config_data, "runtime.llama_cli"),
    )
    if resolved_llama_cli is None:
        readiness.setup_warnings = True
        add_row(
            "llama-cli",
            "warn",
            "Provide --llama-cli or runtime.llama_cli in --config before running models",
        )
    else:
        resolved_llama_cli = Path(resolved_llama_cli)
        if not resolved_llama_cli.exists():
            if is_placeholder_path(resolved_llama_cli):
                readiness.setup_warnings = True
                add_row(
                    "llama-cli",
                    "warn",
                    f"Placeholder path; edit config.yaml before running models: {resolved_llama_cli}",
                )
            else:
                add_row("llama-cli", "fail", f"Path does not exist: {resolved_llama_cli}")
        elif not resolved_llama_cli.is_file():
            add_row("llama-cli", "fail", f"Path is not a file: {resolved_llama_cli}")
        elif not os.access(resolved_llama_cli, os.X_OK):
            add_row("llama-cli", "fail", f"Path is not executable: {resolved_llama_cli}")
        else:
            readiness.llama_cli_ready = True
            add_row("llama-cli", "ok", str(resolved_llama_cli))

    profiles: dict[str, Any] = {}
    model_profiles_path = model_profiles or default_existing_path(
        DEFAULT_LOCAL_MODEL_PROFILES,
        user_model_profiles_path(),
    )
    if model_profiles_path is None:
        readiness.setup_skipped = True
        add_row("Model profiles", "skip", _profiles_missing_note())
    else:
        try:
            profiles = load_model_profiles(model_profiles_path)
            readiness.profiles_loaded = True
            if model_profiles is None:
                add_row(
                    "Model profiles",
                    "ok",
                    f"Auto-detected {len(profiles)} profile(s) from {model_profiles_path}",
                )
            else:
                add_row(
                    "Model profiles",
                    "ok",
                    f"Loaded {len(profiles)} profile(s) from {model_profiles_path}",
                )
        except Exception as exc:
            add_row("Model profiles", "fail", str(exc))

    if model_profile is not None:
        if not profiles:
            add_row(
                "Selected model profile",
                "fail",
                _model_profile_without_profiles_note(),
            )
        else:
            try:
                profile = resolve_model_profile(profiles, model_profile)
                add_row("Selected model profile", "ok", model_profile)

                model_path = profile.get("path")
                if not isinstance(model_path, str) or not model_path:
                    add_row("Model file", "fail", f"Profile has no path: {model_profile}")
                else:
                    resolved_model_path = Path(model_path)
                    if resolved_model_path.exists():
                        add_row("Model file", "ok", str(resolved_model_path))
                    else:
                        add_row(
                            "Model file",
                            "fail",
                            f"Path does not exist: {resolved_model_path}",
                        )
            except Exception as exc:
                add_row("Selected model profile", "fail", str(exc))

    nvidia_smi = shutil.which("nvidia-smi")
    if nvidia_smi:
        add_row("nvidia-smi", "ok", nvidia_smi)
    else:
        add_row(
            "nvidia-smi",
            "warn",
            "Optional; VRAM capture will be unavailable without it",
        )

    console.print(table)
    _print_first_run_next_steps(readiness)

    if has_failure:
        raise typer.Exit(code=1)


def copy_config_templates(
    *,
    config_target: Path,
    model_profiles_target: Path,
    force: bool,
) -> tuple[list[tuple[Path, str, str]], bool]:
    targets = [
        ("llmgauge.example.yaml", config_target),
        ("model-profiles.example.yaml", model_profiles_target),
    ]

    rows: list[tuple[Path, str, str]] = []
    has_failure = False

    for template_name, target in targets:
        if target.exists() and not force:
            rows.append((target, "skipped", "already exists; use --force"))
            continue

        try:
            template_text = read_packaged_template(template_name)
        except FileNotFoundError:
            rows.append((target, "fail", f"Packaged template missing: {template_name}"))
            has_failure = True
            continue

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(template_text, encoding="utf-8")
        rows.append((target, "created", f"from packaged template {template_name}"))

    return rows, has_failure


def print_config_init_table(title: str, rows: list[tuple[Path, str, str]]) -> None:
    table = Table(title=title)
    table.add_column("File")
    table.add_column("Status")
    table.add_column("Notes")

    for target, status, notes in rows:
        table.add_row(str(target), status, notes)

    console.print(table)



def init(
    force: bool = typer.Option(
        False,
        "--force",
        help="Overwrite existing user config files",
    ),
) -> None:
    """Create user config files under the LLMGauge config directory."""
    rows, has_failure = copy_config_templates(
        config_target=user_config_path(),
        model_profiles_target=user_model_profiles_path(),
        force=force,
    )

    print_config_init_table("Initialize User Config", rows)

    if has_failure:
        raise typer.Exit(code=1)

    console.print(f"Config directory: {llmgauge_user_config_dir()}")
    console.print("Next steps:")
    console.print("  1. Edit config.yaml and set runtime.llama_cli")
    console.print(
        "  2. Add a model profile with llmgauge model add or edit model-profiles.yaml"
    )
    console.print("  3. Run llmgauge doctor")
    console.print("  4. Run llmgauge model list")
    console.print("  5. Run llmgauge smoke")
    console.print("  6. Preview a run with llmgauge run --dry-run")



def init_config(
    force: bool = typer.Option(
        False,
        "--force",
        help="Overwrite existing local config files",
    ),
) -> None:
    """Create ignored project-local config files from example templates."""
    rows, has_failure = copy_config_templates(
        config_target=DEFAULT_LOCAL_CONFIG,
        model_profiles_target=DEFAULT_LOCAL_MODEL_PROFILES,
        force=force,
    )

    print_config_init_table("Initialize Local Config", rows)

    if has_failure:
        raise typer.Exit(code=1)



def smoke(
    config: Path | None = typer.Option(
        None,
        "--config",
        help="Optional LLMGauge config YAML to check",
    ),
    model_profiles: Path | None = typer.Option(
        None,
        *MODEL_PROFILES_FILE_OPTIONS,
        help="Optional model profiles YAML to check",
    ),
    model_profile: str | None = typer.Option(
        None,
        "--model-profile",
        help="Optional model profile name to verify",
    ),
    llama_cli: Path | None = typer.Option(
        None,
        "--llama-cli",
        help="Optional llama-cli path override",
    ),
) -> None:
    """Run safe setup checks without launching a model."""
    table = Table(title="LLMGauge Smoke Check")
    table.add_column("Check")
    table.add_column("Status")
    table.add_column("Notes")

    has_failure = False
    readiness = SetupReadiness()

    def add_row(check: str, status: str, notes: str) -> None:
        nonlocal has_failure
        if status == "fail":
            has_failure = True
        table.add_row(check, status, notes)

    add_row("Python package", "ok", f"LLMGauge {__version__} import works")
    add_row("Runner", "ok", "llama.cpp runner module installed")

    try:
        suites_dir = resolve_suites_dir()
        suite_count = len(list(suites_dir.glob("*/suite.yaml")))
        if suite_count:
            add_row(
                "Built-in suites",
                "ok",
                f"{suite_count} suite(s) available at {suites_dir}",
            )
        else:
            add_row("Built-in suites", "fail", f"No suite.yaml files under {suites_dir}")
    except Exception as exc:
        add_row("Built-in suites", "fail", str(exc))

    config_data: dict[str, Any] = {}
    config_path = config or default_existing_path(
        DEFAULT_LOCAL_CONFIG,
        user_config_path(),
    )
    if config_path is None:
        readiness.setup_skipped = True
        add_row("Config", "skip", _config_missing_note())
    else:
        try:
            config_data = load_llmgauge_config(config_path)
            readiness.config_found = True
            if config is None:
                add_row("Config", "ok", f"Auto-detected {config_path}")
            else:
                add_row("Config", "ok", f"Loaded {config_path}")
        except Exception as exc:
            add_row("Config", "fail", str(exc))

    resolved_llama_cli = coalesce(
        llama_cli,
        get_config_value(config_data, "runtime.llama_cli"),
    )
    if resolved_llama_cli is None:
        readiness.setup_warnings = True
        add_row(
            "llama-cli",
            "warn",
            "Provide --llama-cli or runtime.llama_cli before running models",
        )
    else:
        resolved_llama_cli = Path(resolved_llama_cli)
        if not resolved_llama_cli.exists():
            if is_placeholder_path(resolved_llama_cli):
                readiness.setup_warnings = True
                add_row(
                    "llama-cli",
                    "warn",
                    f"Placeholder path; edit config.yaml before running models: {resolved_llama_cli}",
                )
            else:
                add_row("llama-cli", "fail", f"Path does not exist: {resolved_llama_cli}")
        elif not resolved_llama_cli.is_file():
            add_row("llama-cli", "fail", f"Path is not a file: {resolved_llama_cli}")
        elif not os.access(resolved_llama_cli, os.X_OK):
            add_row("llama-cli", "fail", f"Path is not executable: {resolved_llama_cli}")
        else:
            readiness.llama_cli_ready = True
            add_row("llama-cli", "ok", str(resolved_llama_cli))

    profiles: dict[str, Any] = {}
    model_profiles_path = model_profiles or default_existing_path(
        DEFAULT_LOCAL_MODEL_PROFILES,
        user_model_profiles_path(),
    )
    if model_profiles_path is None:
        readiness.setup_skipped = True
        add_row("Model profiles", "skip", _profiles_missing_note())
    else:
        try:
            profiles = load_model_profiles(model_profiles_path)
            readiness.profiles_loaded = True
            if model_profiles is None:
                add_row(
                    "Model profiles",
                    "ok",
                    f"Auto-detected {len(profiles)} profile(s) from {model_profiles_path}",
                )
            else:
                add_row(
                    "Model profiles",
                    "ok",
                    f"Loaded {len(profiles)} profile(s) from {model_profiles_path}",
                )
        except Exception as exc:
            add_row("Model profiles", "fail", str(exc))

    if model_profile is not None:
        if not profiles:
            add_row(
                "Selected model profile",
                "fail",
                _model_profile_without_profiles_note(),
            )
        else:
            try:
                profile = resolve_model_profile(profiles, model_profile)
                add_row("Selected model profile", "ok", model_profile)
                model_path = profile.get("path")
                if model_path is None:
                    add_row("Model file", "fail", f"Profile has no path: {model_profile}")
                else:
                    resolved_model_path = Path(model_path)
                    if resolved_model_path.exists() and resolved_model_path.is_file():
                        add_row("Model file", "ok", str(resolved_model_path))
                    elif resolved_model_path.exists():
                        add_row(
                            "Model file",
                            "fail",
                            f"Path is not a file: {resolved_model_path}",
                        )
                    else:
                        if is_placeholder_path(resolved_model_path):
                            readiness.setup_warnings = True
                            add_row(
                                "Model file",
                                "warn",
                                f"Placeholder path; edit model-profiles.yaml before running models: {resolved_model_path}",
                            )
                        else:
                            add_row(
                                "Model file",
                                "fail",
                                f"Path does not exist: {resolved_model_path}",
                            )
            except Exception as exc:
                add_row("Selected model profile", "fail", str(exc))

    nvidia_smi = shutil.which("nvidia-smi")
    if nvidia_smi:
        add_row("nvidia-smi", "ok", nvidia_smi)
    else:
        add_row("nvidia-smi", "warn", "not found; VRAM capture may be unavailable")

    console.print(table)

    if has_failure:
        console.print("[bold red]Smoke check failed[/bold red]")
        _print_first_run_next_steps(readiness)
        raise typer.Exit(code=1)

    if readiness.setup_skipped or readiness.setup_warnings:
        console.print("[bold yellow]Smoke check passed with warnings[/bold yellow]")
        _print_first_run_next_steps(readiness)
    else:
        console.print("[bold green]Smoke check passed[/bold green]")
        console.print(
            "Safe next step: run llmgauge run --dry-run before launching a model."
        )
