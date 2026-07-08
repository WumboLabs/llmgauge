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
from llmgauge.core.guided_setup import (
    current_config_llama_cli,
    discover_llama_cli_candidates,
    discover_model_directory_candidates,
    sanitize_profile_name,
    scan_gguf_files,
    storage_path_string,
    update_config_llama_cli,
    validate_llama_cli_for_setup,
    validate_model_path_for_setup,
)
from llmgauge.core.model_profiles_store import add_model_profile
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
        steps.append("Run llmgauge setup or llmgauge init to create user config files")
    elif not readiness.llama_cli_ready:
        steps.append("Run llmgauge setup or edit config.yaml and set runtime.llama_cli")
    if readiness.setup_skipped or not readiness.profiles_loaded:
        steps.append(
            "Run llmgauge setup or add a model profile with llmgauge model add"
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
    console.print("  1. Run llmgauge setup for guided path selection")
    console.print("  2. Or edit config.yaml and set runtime.llama_cli manually")
    console.print(
        "  3. Add a model profile with llmgauge setup or llmgauge model add"
    )
    console.print("  4. Run llmgauge doctor")
    console.print("  5. Run llmgauge model list")
    console.print("  6. Run llmgauge smoke")
    console.print("  7. Preview a run with llmgauge run --dry-run")



def _print_setup_scan_results(
    *,
    config_path: Path,
    profiles_path: Path,
) -> None:
    console.print("[bold]LLMGauge setup scan[/bold]")
    console.print("Read-only scan. No files were written.")

    if config_path.exists():
        console.print(f"Config: {config_path}")
        current = current_config_llama_cli(config_path)
        console.print(f"  runtime.llama_cli: {current or 'not set'}")
    else:
        console.print(f"Config: missing ({config_path})")

    if profiles_path.exists():
        try:
            profiles = load_model_profiles(profiles_path)
            console.print(f"Model profiles: {profiles_path} ({len(profiles)} profile(s))")
        except Exception as exc:
            console.print(f"Model profiles: {profiles_path} (load error: {exc})")
    else:
        console.print(f"Model profiles: missing ({profiles_path})")

    llama_candidates = discover_llama_cli_candidates()
    console.print("Detected llama-cli candidates:")
    if llama_candidates:
        for candidate in llama_candidates:
            suffix = " (executable)" if os.access(candidate, os.X_OK) else ""
            console.print(f"  - {candidate}{suffix}")
    else:
        console.print("  - None")

    model_dirs = discover_model_directory_candidates()
    console.print("Detected model directories:")
    if model_dirs:
        for directory in model_dirs:
            gguf_files, total = scan_gguf_files(directory)
            if total:
                console.print(f"  - {directory} ({total} .gguf file(s))")
                for gguf_path in gguf_files:
                    console.print(f"      {gguf_path}")
                if total > len(gguf_files):
                    remaining = total - len(gguf_files)
                    console.print(f"      ... and {remaining} more")
            else:
                console.print(f"  - {directory} (no .gguf files found)")
    else:
        console.print("  - None")


def _ensure_user_config_files(*, force: bool) -> tuple[Path, Path]:
    config_path = user_config_path()
    profiles_path = user_model_profiles_path()

    if not config_path.exists() or not profiles_path.exists():
        rows, has_failure = copy_config_templates(
            config_target=config_path,
            model_profiles_target=profiles_path,
            force=force,
        )
        if has_failure:
            raise typer.Exit(code=1)
        for target, status, notes in rows:
            if status == "created":
                console.print(f"Created {target}")

    return config_path, profiles_path


def _print_post_setup_next_steps(profile_name: str | None) -> None:
    console.print("No model was launched during setup.")
    console.print("Clean-clone setup validates paths and CLI readiness, not model quality.")
    console.print("Next steps:")
    console.print("  1. llmgauge doctor")
    console.print("  2. llmgauge smoke")
    if profile_name:
        console.print(
            "  3. llmgauge run --suite practical "
            "--only honesty-uncertainty/fake-package-currentness "
            f"--model-profile {profile_name} --ctx 8192 --max-tokens 800 "
            "--temp 0.2 --dry-run"
        )
    else:
        console.print(
            "  3. llmgauge run ... --dry-run after adding a model profile"
        )


def _resolve_non_interactive_model_path(
    *,
    model_path: Path | None,
    models_dir: Path | None,
) -> Path | None:
    if model_path is not None:
        validate_model_path_for_setup(model_path)
        return model_path.expanduser().resolve()

    if models_dir is None:
        return None

    directory = models_dir.expanduser().resolve()
    if not directory.exists() or not directory.is_dir():
        raise typer.BadParameter(f"Models directory does not exist: {directory}")

    gguf_files, total = scan_gguf_files(directory)
    if total == 0:
        raise typer.BadParameter(f"No GGUF files found under {directory}")
    if total > 1:
        raise typer.BadParameter(
            f"Found {total} GGUF files under {directory}; "
            "use --model-path to select one explicitly"
        )

    return gguf_files[0]


def _write_setup_profile(
    profiles_path: Path,
    *,
    profile_name: str,
    model_file: Path,
    force: bool,
) -> None:
    try:
        add_model_profile(
            profiles_path,
            profile_name=profile_name,
            model_path=model_file,
            label=profile_name.replace("_", " ").title(),
            overwrite=force,
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    console.print(
        f"[bold green]Updated model profile[/bold green]: {profile_name} -> {storage_path_string(model_file)}"
    )


def _write_setup_llama_cli(
    config_path: Path,
    llama_cli: Path,
    *,
    force: bool,
) -> None:
    template_text = read_packaged_template("llmgauge.example.yaml")
    try:
        update_config_llama_cli(
            config_path,
            llama_cli,
            force=force,
            template_text=template_text,
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    console.print(
        f"[bold green]Updated config[/bold green]: runtime.llama_cli -> {storage_path_string(llama_cli)}"
    )


def guided_setup(
    scan: bool = typer.Option(
        False,
        "--scan",
        help="Read-only scan for llama-cli and GGUF candidates; does not write files",
    ),
    llama_cli: Path | None = typer.Option(
        None,
        "--llama-cli",
        help="llama-cli executable path to write into config.yaml",
    ),
    models_dir: Path | None = typer.Option(
        None,
        "--models-dir",
        help="Directory to scan for .gguf files in non-interactive mode",
    ),
    model_path: Path | None = typer.Option(
        None,
        "--model-path",
        help="GGUF model file path for a model profile",
    ),
    profile_name: str | None = typer.Option(
        None,
        "--profile-name",
        help="Model profile name to create or update",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Replace existing llama-cli path or model profile",
    ),
    non_interactive: bool = typer.Option(
        False,
        "--non-interactive",
        help="Use flags only; do not prompt",
    ),
) -> None:
    """Guide first-run config and model profile setup without launching a model."""
    config_path = user_config_path()
    profiles_path = user_model_profiles_path()

    if scan:
        _print_setup_scan_results(
            config_path=config_path,
            profiles_path=profiles_path,
        )
        return

    if non_interactive:
        config_path, profiles_path = _ensure_user_config_files(force=force)

        resolved_profile_name = profile_name
        resolved_model = _resolve_non_interactive_model_path(
            model_path=model_path,
            models_dir=models_dir,
        )

        if llama_cli is None:
            current = current_config_llama_cli(config_path)
            if current is None or is_placeholder_path(Path(current)):
                raise typer.BadParameter(
                    "--llama-cli is required in --non-interactive mode when "
                    "config.yaml does not have a real llama-cli path"
                )
        else:
            _write_setup_llama_cli(config_path, llama_cli, force=force)

        if resolved_model is not None:
            if not resolved_profile_name:
                resolved_profile_name = sanitize_profile_name(resolved_model.name)
            _write_setup_profile(
                profiles_path,
                profile_name=resolved_profile_name,
                model_file=resolved_model,
                force=force,
            )

        _print_post_setup_next_steps(resolved_profile_name)
        return

    import sys

    if not sys.stdin.isatty():
        raise typer.BadParameter(
            "Interactive setup requires a TTY. Use --non-interactive with explicit flags, "
            "or run llmgauge setup --scan"
        )

    console.print(
        "LLMGauge guided setup helps configure llama-cli and a model profile. "
        "No model will be launched."
    )
    config_path, profiles_path = _ensure_user_config_files(force=False)

    selected_llama_cli: Path | None = None
    if llama_cli is not None:
        validate_llama_cli_for_setup(llama_cli)
        selected_llama_cli = llama_cli.expanduser().resolve()
    else:
        candidates = discover_llama_cli_candidates()
        executable_candidates = [path for path in candidates if os.access(path, os.X_OK)]
        display_candidates = executable_candidates or candidates

        console.print("Detected llama-cli candidates:")
        if display_candidates:
            for index, candidate in enumerate(display_candidates, start=1):
                console.print(f"  {index}. {candidate}")
        else:
            console.print("  None")

        choice = typer.prompt(
            "Select llama-cli candidate number, enter a custom path, or press Enter to skip",
            default="",
            show_default=False,
        ).strip()

        if choice:
            if choice.isdigit():
                option_index = int(choice)
                if option_index < 1 or option_index > len(display_candidates):
                    raise typer.BadParameter(f"Invalid llama-cli selection: {choice}")
                selected_llama_cli = display_candidates[option_index - 1]
            else:
                selected_llama_cli = Path(choice).expanduser().resolve()
            validate_llama_cli_for_setup(selected_llama_cli)

    if selected_llama_cli is not None:
        current = current_config_llama_cli(config_path)
        replace = True
        if (
            current
            and not is_placeholder_path(Path(current))
            and storage_path_string(Path(current)) != storage_path_string(selected_llama_cli)
            and not force
        ):
            replace = typer.confirm(
                f"Replace existing runtime.llama_cli ({current})?",
                default=False,
            )
        if replace or force:
            _write_setup_llama_cli(config_path, selected_llama_cli, force=True)

    selected_model: Path | None = None
    if model_path is not None:
        validate_model_path_for_setup(model_path)
        selected_model = model_path.expanduser().resolve()
    else:
        model_dirs = discover_model_directory_candidates()
        if models_dir is not None:
            model_dirs = [models_dir.expanduser().resolve(), *model_dirs]

        console.print("Detected model directories:")
        if model_dirs:
            for index, directory in enumerate(model_dirs, start=1):
                _, total = scan_gguf_files(directory)
                label = f"{total} .gguf file(s)" if total else "no .gguf files"
                console.print(f"  {index}. {directory} ({label})")
        else:
            console.print("  None")

        dir_choice = typer.prompt(
            "Select model directory number, enter a custom directory, or press Enter to skip",
            default="",
            show_default=False,
        ).strip()

        selected_directory: Path | None = None
        if dir_choice:
            if dir_choice.isdigit():
                option_index = int(dir_choice)
                if option_index < 1 or option_index > len(model_dirs):
                    raise typer.BadParameter(f"Invalid model directory selection: {dir_choice}")
                selected_directory = model_dirs[option_index - 1]
            else:
                selected_directory = Path(dir_choice).expanduser().resolve()

        if selected_directory is not None:
            if not selected_directory.exists():
                create_dir = typer.confirm(
                    f"Directory does not exist ({selected_directory}). Create it?",
                    default=False,
                )
                if create_dir:
                    selected_directory.mkdir(parents=True, exist_ok=True)
                    console.print(f"Created directory: {selected_directory}")
                else:
                    selected_directory = None

        if selected_directory is not None and selected_directory.is_dir():
            gguf_files, total = scan_gguf_files(selected_directory)
            if total == 0:
                console.print(f"No GGUF files found under {selected_directory}")
            else:
                console.print("Detected GGUF files:")
                for index, gguf_file in enumerate(gguf_files, start=1):
                    console.print(f"  {index}. {gguf_file}")
                if total > len(gguf_files):
                    remaining = total - len(gguf_files)
                    console.print(f"  ... and {remaining} more")

                file_choice = typer.prompt(
                    "Select GGUF file number, enter a custom .gguf path, or press Enter to skip",
                    default="",
                    show_default=False,
                ).strip()

                if file_choice:
                    if file_choice.isdigit():
                        option_index = int(file_choice)
                        if option_index < 1 or option_index > len(gguf_files):
                            raise typer.BadParameter(
                                f"Invalid GGUF selection: {file_choice}"
                            )
                        selected_model = gguf_files[option_index - 1]
                    else:
                        selected_model = Path(file_choice).expanduser().resolve()
                    validate_model_path_for_setup(selected_model)

    resolved_profile_name = profile_name
    if selected_model is not None:
        suggested = sanitize_profile_name(selected_model.name)
        if not resolved_profile_name:
            resolved_profile_name = typer.prompt(
                f"Model profile name (suggested: {suggested})",
                default=suggested,
            ).strip()
            if not resolved_profile_name:
                resolved_profile_name = suggested

        profiles = load_model_profiles(profiles_path)
        overwrite = force
        if resolved_profile_name in profiles and not force:
            overwrite = typer.confirm(
                f"Model profile '{resolved_profile_name}' already exists. Replace it?",
                default=False,
            )
        _write_setup_profile(
            profiles_path,
            profile_name=resolved_profile_name,
            model_file=selected_model,
            force=overwrite,
        )

    _print_post_setup_next_steps(resolved_profile_name)


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
