from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
import os
import shutil
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from llmgauge import __version__
from llmgauge.core.artifacts import prepare_result_dir, write_json, write_text
from llmgauge.core.baseline import check_result_against_baselines
from llmgauge.core.batch_validation import validate_batch_dir
from llmgauge.core.batch import (
    build_batch_summary,
    load_batch_manifest,
    write_batch_report,
    write_batch_summary,
)
from llmgauge.core.compare import build_compare_report, load_compare_result
from llmgauge.core.contextgen import (
    build_context_prompt,
    write_context_prompt_artifacts,
)
from llmgauge.core.export_index import build_export_index, write_export_index
from llmgauge.core.config import (
    coalesce,
    get_config_value,
    load_llmgauge_config,
    load_model_profiles,
    resolve_model_profile,
)
from llmgauge.core.ladder import (
    build_ladder_summary,
    parse_ctx_ladder,
    write_ladder_report,
    write_ladder_summary,
)
from llmgauge.core.fit_ladder_validation import validate_fit_ladder_dir
from llmgauge.core.ladder_validation import validate_ladder_dir
from llmgauge.core.fit_ladder import (
    build_fit_attempt_plan,
    build_fit_attempt_record,
    build_fit_ladder_summary,
    write_fit_ladder_report,
)
from llmgauge.core.metrics import parse_llama_metrics
from llmgauge.core.output_cleaning import clean_llama_output
from llmgauge.core.output_paths import build_auto_output_dir, slugify_run_name
from llmgauge.core.reports import build_markdown_report
from llmgauge.core.result_validation import validate_result_dir
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
from llmgauge.core.suite import load_suite, validate_suite
from llmgauge.core.suite_paths import resolve_suite_path, resolve_suites_dir
from llmgauge.runners.llama_cpp import LlamaCppRunConfig, run_llama_cpp

def _fail_cli_validation(message: str) -> None:
    typer.echo(message, err=True)
    raise typer.Exit(2)


app = typer.Typer(
    name="llmgauge",
    help="Practical local LLM evaluation on real hardware.",
    no_args_is_help=True,
)

console = Console()

DEFAULT_LOCAL_CONFIG = Path("examples/configs/llmgauge.local.yaml")
DEFAULT_LOCAL_MODEL_PROFILES = Path("examples/configs/model-profiles.local.yaml")
USER_CONFIG_FILENAME = "config.yaml"
USER_MODEL_PROFILES_FILENAME = "model-profiles.yaml"
EXAMPLE_CONFIG = Path("examples/configs/llmgauge.example.yaml")
EXAMPLE_MODEL_PROFILES = Path("examples/configs/model-profiles.example.yaml")


def _show_version(value: bool) -> None:
    if value:
        console.print(f"llmgauge {__version__}")
        raise typer.Exit()


@app.callback()
def cli_options(
    version: bool = typer.Option(
        False,
        "--version",
        help="Show the LLMGauge version and exit.",
        callback=_show_version,
        is_eager=True,
    ),
) -> None:
    """Practical local LLM evaluation on real hardware."""


@app.command("version")
def version_command() -> None:
    """Show the LLMGauge version."""
    console.print(f"llmgauge {__version__}")


def _llmgauge_user_config_dir() -> Path:
    xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config_home:
        return Path(xdg_config_home) / "llmgauge"
    return Path.home() / ".config" / "llmgauge"


def _user_config_path() -> Path:
    return _llmgauge_user_config_dir() / USER_CONFIG_FILENAME


def _user_model_profiles_path() -> Path:
    return _llmgauge_user_config_dir() / USER_MODEL_PROFILES_FILENAME


def _default_existing_path(*paths: Path) -> Path | None:
    for candidate in paths:
        if candidate.exists():
            return candidate
    return None


@app.command()
def doctor(
    config: Path | None = typer.Option(
        None,
        "--config",
        help="Optional LLMGauge config YAML to check",
    ),
    model_profiles: Path | None = typer.Option(
        None,
        "--model-profiles",
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
    config_path = config or _default_existing_path(DEFAULT_LOCAL_CONFIG, _user_config_path())
    if config_path is None:
        add_row("Config", "warn", "No --config provided; run checks are limited")
    else:
        try:
            config_data = load_llmgauge_config(config_path)
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
        add_row(
            "llama-cli",
            "warn",
            "Provide --llama-cli or runtime.llama_cli in --config before running models",
        )
    else:
        resolved_llama_cli = Path(resolved_llama_cli)
        if not resolved_llama_cli.exists():
            add_row("llama-cli", "fail", f"Path does not exist: {resolved_llama_cli}")
        elif not resolved_llama_cli.is_file():
            add_row("llama-cli", "fail", f"Path is not a file: {resolved_llama_cli}")
        elif not os.access(resolved_llama_cli, os.X_OK):
            add_row("llama-cli", "fail", f"Path is not executable: {resolved_llama_cli}")
        else:
            add_row("llama-cli", "ok", str(resolved_llama_cli))

    profiles: dict[str, Any] = {}
    model_profiles_path = model_profiles or _default_existing_path(
        DEFAULT_LOCAL_MODEL_PROFILES,
        _user_model_profiles_path(),
    )
    if model_profiles_path is None:
        add_row(
            "Model profiles",
            "warn",
            "No --model-profiles provided; profile checks are skipped",
        )
    else:
        try:
            profiles = load_model_profiles(model_profiles_path)
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
                "Use --model-profiles with --model-profile",
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

    if has_failure:
        raise typer.Exit(code=1)


@app.command("list-suites")
def list_suites(suites_dir: Path | None = typer.Argument(None)) -> None:
    """List available prompt suites."""
    resolved_suites_dir = resolve_suites_dir(suites_dir)
    if not resolved_suites_dir.exists():
        raise typer.BadParameter(
            f"Suites directory does not exist: {resolved_suites_dir}"
        )

    table = Table(title="Available Suites")
    table.add_column("Suite ID")
    table.add_column("Version")
    table.add_column("Title")
    table.add_column("Prompts")

    for suite_file in sorted(resolved_suites_dir.glob("*/suite.yaml")):
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
    resolved_suite_dir = resolve_suite_path(suite_dir)
    errors = validate_suite(resolved_suite_dir)

    if errors:
        console.print("[bold red]Suite validation failed[/bold red]")
        for error in errors:
            console.print(f"- {error}")
        raise typer.Exit(code=1)

    suite = load_suite(resolved_suite_dir)
    console.print(
        f"[bold green]OK[/bold green] {suite['suite_id']} "
        f"({len(suite.get('prompts', []))} prompts)"
    )


def _copy_config_templates(
    *,
    config_target: Path,
    model_profiles_target: Path,
    force: bool,
) -> tuple[list[tuple[Path, str, str]], bool]:
    targets = [
        (EXAMPLE_CONFIG, config_target),
        (EXAMPLE_MODEL_PROFILES, model_profiles_target),
    ]

    rows: list[tuple[Path, str, str]] = []
    has_failure = False

    for source, target in targets:
        if not source.exists():
            rows.append((target, "fail", f"Example template missing: {source}"))
            has_failure = True
            continue

        if target.exists() and not force:
            rows.append((target, "skipped", "already exists; use --force"))
            continue

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        rows.append((target, "created", f"from {source}"))

    return rows, has_failure


def _print_config_init_table(title: str, rows: list[tuple[Path, str, str]]) -> None:
    table = Table(title=title)
    table.add_column("File")
    table.add_column("Status")
    table.add_column("Notes")

    for target, status, notes in rows:
        table.add_row(str(target), status, notes)

    console.print(table)


@app.command("init")
def init(
    force: bool = typer.Option(
        False,
        "--force",
        help="Overwrite existing user config files",
    ),
) -> None:
    """Create user config files under the LLMGauge config directory."""
    rows, has_failure = _copy_config_templates(
        config_target=_user_config_path(),
        model_profiles_target=_user_model_profiles_path(),
        force=force,
    )

    _print_config_init_table("Initialize User Config", rows)

    if has_failure:
        raise typer.Exit(code=1)

    console.print(f"Config directory: {_llmgauge_user_config_dir()}")
    console.print("Next steps:")
    console.print("  1. Edit config.yaml and model-profiles.yaml")
    console.print("  2. Run llmgauge doctor")
    console.print("  3. Run llmgauge list-model-profiles")


@app.command("init-config")
def init_config(
    force: bool = typer.Option(
        False,
        "--force",
        help="Overwrite existing local config files",
    ),
) -> None:
    """Create ignored project-local config files from example templates."""
    rows, has_failure = _copy_config_templates(
        config_target=DEFAULT_LOCAL_CONFIG,
        model_profiles_target=DEFAULT_LOCAL_MODEL_PROFILES,
        force=force,
    )

    _print_config_init_table("Initialize Local Config", rows)

    if has_failure:
        raise typer.Exit(code=1)


@app.command("list-model-profiles")
def list_model_profiles(
    model_profiles: Path | None = typer.Option(
        None,
        "--model-profiles",
        help="Model profiles YAML to list; defaults to examples/configs/model-profiles.local.yaml when present",
    ),
) -> None:
    """List configured model profiles and model path status."""
    model_profiles_path = model_profiles or _default_existing_path(
        DEFAULT_LOCAL_MODEL_PROFILES,
        _user_model_profiles_path(),
    )
    if model_profiles_path is None:
        raise typer.BadParameter(
            "Provide --model-profiles or run llmgauge init-config first"
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
    path = resolve_suite_path(Path("core-v1")) / "prompts/system-conservative-ops.txt"
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


def _optional_nonnegative_int(value: Any, *, field_name: str) -> int | None:
    if value is None:
        return None

    resolved = int(value)
    if resolved < 0:
        raise typer.BadParameter(f"{field_name} must be non-negative")

    return resolved


def _vram_headroom_mib(vram_summary: dict[str, Any] | None) -> int | None:
    if not isinstance(vram_summary, dict) or not vram_summary.get("available"):
        return None

    peak_used_mib = vram_summary.get("peak_used_mib")
    peak_total_mib = vram_summary.get("peak_total_mib")

    if not isinstance(peak_used_mib, int) or not isinstance(peak_total_mib, int):
        return None

    return peak_total_mib - peak_used_mib


def _build_vram_guardrails(
    vram_summary: dict[str, Any] | None,
    *,
    min_headroom_warn_mib: int | None,
) -> dict[str, Any] | None:
    if min_headroom_warn_mib is None:
        return None

    observed_headroom_mib = _vram_headroom_mib(vram_summary)
    if observed_headroom_mib is None:
        return None

    warnings = []
    status = "ok"

    if observed_headroom_mib < min_headroom_warn_mib:
        status = "warning"
        warnings.append("vram_headroom_below_warning_threshold")

    return {
        "schema_version": "llmgauge.vram.guardrails.v0",
        "status": status,
        "min_headroom_warn_mib": min_headroom_warn_mib,
        "observed_headroom_mib": observed_headroom_mib,
        "warnings": warnings,
    }


def _metadata_only_score_prompt_count(scores_data: dict[str, Any]) -> int:
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


def _print_metadata_only_score_warning(count: int) -> None:
    if count == 0:
        return

    noun = "entry has" if count == 1 else "entries have"
    console.print(
        "[yellow]Warning[/yellow]: "
        f"{count} prompt score {noun} review metadata but no numeric dimension "
        "values. The result will report review_metadata_only until numeric "
        "dimensions are filled."
    )


def _resolve_cli_output_dir(
    *,
    out: Path | None,
    auto_name: bool,
    runs_root: Path,
    run_name: str | None,
    default_run_name: str,
) -> Path:
    if out is not None and auto_name:
        raise typer.BadParameter("Use either --out or --auto-name, not both")

    if out is not None:
        return out

    if not auto_name:
        _fail_cli_validation("Use --out PATH or --auto-name")

    return build_auto_output_dir(
        runs_root=runs_root,
        run_name=run_name or default_run_name,
    )


def _resolve_run_options(
    *,
    model_id: str | None,
    model_profile: str | None,
    config_path: Path | None,
    model_profiles_path: Path | None,
    model_path: Path | None,
    llama_cli: Path | None,
    ctx: int | None,
    max_tokens: int | None,
    temp: float | None,
    top_p: float | None,
    batch: int | None,
    ubatch: int | None,
    gpu_layers: int | None,
    flash_attn: str | None = None,
    runtime_label: str | None = None,
) -> dict[str, Any]:
    resolved_config_path = config_path or _default_existing_path(DEFAULT_LOCAL_CONFIG, _user_config_path())
    resolved_model_profiles_path = model_profiles_path or _default_existing_path(
        DEFAULT_LOCAL_MODEL_PROFILES,
        _user_model_profiles_path(),
    )

    config_data = load_llmgauge_config(resolved_config_path)
    profiles = load_model_profiles(resolved_model_profiles_path)
    profile = resolve_model_profile(profiles, model_profile)

    resolved_model_id = coalesce(model_id, model_profile, profile.get("label"))
    if resolved_model_id is None:
        raise typer.BadParameter("Provide --model-id or --model-profile")

    resolved_model_path = coalesce(model_path, profile.get("path"))
    if resolved_model_path is None:
        if (
            model_id is not None
            and model_profile is None
            and isinstance(profiles.get(model_id), dict)
        ):
            raise typer.BadParameter(
                f"Model profile {model_id!r} was provided with --model-id. "
                f"Use --model-profile {model_id} to load its configured path."
            )
        raise typer.BadParameter(
            "Provide --model-path or use --model-profile with a path"
        )
    resolved_model_path = Path(resolved_model_path)

    resolved_llama_cli = coalesce(
        llama_cli,
        get_config_value(config_data, "runtime.llama_cli"),
    )
    if resolved_llama_cli is None:
        raise typer.BadParameter(
            "Provide --llama-cli or set runtime.llama_cli in --config"
        )
    resolved_llama_cli = Path(resolved_llama_cli)

    resolved_ctx = int(
        coalesce(
            ctx,
            profile.get("ctx_size"),
            get_config_value(config_data, "defaults.ctx_size"),
            8192,
        )
    )
    resolved_max_tokens = int(
        coalesce(
            max_tokens,
            profile.get("max_tokens"),
            get_config_value(config_data, "defaults.max_tokens"),
            800,
        )
    )
    resolved_temp = float(
        coalesce(
            temp,
            profile.get("temperature"),
            get_config_value(config_data, "defaults.temperature"),
            0.2,
        )
    )
    resolved_top_p = float(
        coalesce(
            top_p,
            profile.get("top_p"),
            get_config_value(config_data, "defaults.top_p"),
            0.95,
        )
    )
    resolved_batch = int(
        coalesce(
            batch,
            profile.get("batch_size"),
            get_config_value(config_data, "defaults.batch_size"),
            256,
        )
    )
    resolved_ubatch = int(
        coalesce(
            ubatch,
            profile.get("ubatch_size"),
            get_config_value(config_data, "defaults.ubatch_size"),
            64,
        )
    )
    resolved_gpu_layers = int(
        coalesce(
            gpu_layers,
            profile.get("gpu_layers"),
            get_config_value(config_data, "defaults.gpu_layers"),
            999,
        )
    )
    raw_flash_attn = coalesce(
        flash_attn,
        profile.get("flash_attn"),
        get_config_value(config_data, "defaults.flash_attn"),
        "auto",
    )
    if isinstance(raw_flash_attn, bool):
        resolved_flash_attn = "on" if raw_flash_attn else "off"
    else:
        resolved_flash_attn = str(raw_flash_attn).lower()

    if resolved_flash_attn not in {"auto", "on", "off"}:
        raise typer.BadParameter("flash_attn must be one of: auto, on, off")

    raw_runtime_label = coalesce(
        runtime_label,
        profile.get("runtime_label"),
        get_config_value(config_data, "defaults.runtime_label"),
    )
    resolved_runtime_label = (
        str(raw_runtime_label).strip() if raw_runtime_label is not None else None
    )
    if resolved_runtime_label == "":
        resolved_runtime_label = None

    resolved_vram_min_headroom_warn_mib = _optional_nonnegative_int(
        get_config_value(config_data, "vram.min_headroom_warn_mib"),
        field_name="vram.min_headroom_warn_mib",
    )

    if not resolved_model_path.exists():
        raise typer.BadParameter(f"Model path does not exist: {resolved_model_path}")

    if not resolved_llama_cli.exists():
        raise typer.BadParameter(f"llama-cli path does not exist: {resolved_llama_cli}")

    return {
        "model_id": str(resolved_model_id),
        "model_profile": model_profile,
        "profile": profile,
        "config_path": resolved_config_path,
        "model_profiles_path": resolved_model_profiles_path,
        "model_path": resolved_model_path,
        "llama_cli": resolved_llama_cli,
        "ctx": resolved_ctx,
        "max_tokens": resolved_max_tokens,
        "temp": resolved_temp,
        "top_p": resolved_top_p,
        "batch": resolved_batch,
        "ubatch": resolved_ubatch,
        "gpu_layers": resolved_gpu_layers,
        "flash_attn": resolved_flash_attn,
        "runtime_label": resolved_runtime_label,
        "vram_min_headroom_warn_mib": resolved_vram_min_headroom_warn_mib,
    }


def _print_run_preflight(
    *,
    suite: Path,
    only: str | None,
    include: str,
    resolved: dict[str, Any],
    out: Path | None,
    auto_name: bool,
    runs_root: Path,
    run_name: str | None,
) -> None:
    resolved_suite = resolve_suite_path(suite)
    loaded_suite = load_suite(resolved_suite)
    selected_prompts = _select_prompts(loaded_suite, only, include)

    if out is not None:
        output_plan = str(out)
    elif auto_name:
        default_run_name = f"{resolved['model_id']}-{suite.name}"
        output_plan = (
            f"auto-name under {runs_root} "
            f"with run name {run_name or default_run_name}"
        )
    else:
        output_plan = (
            "not required for --dry-run; real runs require --out or --auto-name"
        )

    selection = f"only={only}" if only else f"include={include}"

    table = Table(title="LLMGauge Run Dry Run")
    table.add_column("Field", no_wrap=True)
    table.add_column("Value")

    table.add_row("Suite", str(loaded_suite.get("suite_id", suite)))
    table.add_row("Suite path", str(resolved_suite))
    table.add_row("Selection", selection)
    table.add_row("Prompt count", str(len(selected_prompts)))
    table.add_row("Model ID", str(resolved["model_id"]))
    table.add_row("Model profile", str(resolved["model_profile"]))
    table.add_row("Config", str(resolved["config_path"]))
    table.add_row("Model profiles", str(resolved["model_profiles_path"]))
    table.add_row("Model path", str(resolved["model_path"]))
    table.add_row("llama-cli", str(resolved["llama_cli"]))
    table.add_row("Context", str(resolved["ctx"]))
    table.add_row("Max tokens", str(resolved["max_tokens"]))
    table.add_row("Temperature", str(resolved["temp"]))
    table.add_row("Top-p", str(resolved["top_p"]))
    table.add_row("Batch", str(resolved["batch"]))
    table.add_row("UBatch", str(resolved["ubatch"]))
    table.add_row("GPU layers", str(resolved["gpu_layers"]))
    table.add_row("Flash attention", str(resolved["flash_attn"]))
    table.add_row("Runtime label", str(resolved["runtime_label"] or "unknown"))
    table.add_row("Output plan", output_plan)

    console.print(table)

    prompt_table = Table(title="Selected Prompts")
    prompt_table.add_column("Prompt", no_wrap=True)
    prompt_table.add_column("Category", no_wrap=True)
    prompt_table.add_column("Title")

    for prompt in selected_prompts:
        prompt_table.add_row(
            str(prompt.get("id", "")),
            str(prompt.get("category", "")),
            str(prompt.get("title", prompt.get("id", ""))),
        )

    console.print(prompt_table)
    console.print(
        "[bold green]Dry run complete[/bold green]: llama.cpp was not "
        "launched and no result directory was created."
    )


def _execute_run(
    *,
    suite: Path,
    only: str | None,
    include: str,
    resolved: dict[str, Any],
    out: Path,
    fail_on_failed_prompts: bool,
) -> dict[str, Any]:
    resolved_suite = resolve_suite_path(suite)
    suite = resolved_suite
    loaded_suite = load_suite(suite)
    selected_prompts = _select_prompts(loaded_suite, only, include)
    system_prompt = _load_system_prompt()

    prepare_result_dir(out)

    config = LlamaCppRunConfig(
        llama_cli=resolved["llama_cli"],
        model_path=resolved["model_path"],
        ctx_size=resolved["ctx"],
        max_tokens=resolved["max_tokens"],
        temperature=resolved["temp"],
        top_p=resolved["top_p"],
        batch_size=resolved["batch"],
        ubatch_size=resolved["ubatch"],
        gpu_layers=resolved["gpu_layers"],
        flash_attn=resolved["flash_attn"],
    )

    timestamp = datetime.now(UTC).replace(microsecond=0).isoformat()
    run_id = out.name
    prompt_results: list[dict] = []
    redacted_command: list[str] | None = None

    console.print(
        f"Running [bold]{len(selected_prompts)}[/bold] prompt(s) "
        f"with model [bold]{resolved['model_id']}[/bold] "
        f"at ctx [bold]{resolved['ctx']}[/bold]"
    )

    for index, prompt_meta in enumerate(selected_prompts, start=1):
        prompt_id = prompt_meta["id"]
        prompt_path = suite / prompt_meta["file"]
        prompt_text = prompt_path.read_text(encoding="utf-8").strip()
        combined_prompt = _build_combined_prompt(system_prompt, prompt_text)

        raw_prompt_path = out / "raw" / f"{prompt_id}.prompt.md"
        raw_output_path = out / "raw" / f"{prompt_id}.output.txt"
        cleaned_output_path = out / "cleaned" / f"{prompt_id}.output.txt"
        stderr_log_path = out / "logs" / f"{prompt_id}.stderr.log"

        write_text(raw_prompt_path, combined_prompt)

        console.print(f"[{index}/{len(selected_prompts)}] Running {prompt_id}")
        run_result = run_llama_cpp(config, combined_prompt)

        if redacted_command is None:
            redacted_command = _redacted_command(
                run_result.command,
                resolved["model_path"],
            )

        write_text(raw_output_path, run_result.stdout)
        write_text(cleaned_output_path, clean_llama_output(run_result.stdout))
        write_text(stderr_log_path, run_result.stderr)

        vram_samples = getattr(run_result, "vram_samples", [])
        vram_summary = getattr(run_result, "vram_summary", None)

        vram_samples_path = None
        if vram_samples:
            vram_samples_path = (
                out / "vram" / f"{prompt_id.replace('/', '__')}.samples.json"
            )
            write_json(
                vram_samples_path,
                {
                    "schema_version": "llmgauge.vram.samples.v0",
                    "prompt_id": prompt_id,
                    "samples": vram_samples,
                },
            )

        metrics = parse_llama_metrics(run_result.stdout + "\n" + run_result.stderr)
        status = "completed" if run_result.exit_status == 0 else "failed"
        vram_guardrails = _build_vram_guardrails(
            vram_summary,
            min_headroom_warn_mib=resolved["vram_min_headroom_warn_mib"],
        )

        prompt_results.append(
            {
                "prompt_id": prompt_id,
                "title": prompt_meta.get("title", prompt_id),
                "category": prompt_meta.get("category"),
                "status": status,
                "raw_prompt_path": str(raw_prompt_path.relative_to(out)),
                "raw_output_path": str(raw_output_path.relative_to(out)),
                "cleaned_output_path": str(cleaned_output_path.relative_to(out)),
                "stderr_log_path": str(stderr_log_path.relative_to(out)),
                "metrics": metrics,
                "vram": vram_summary,
                "vram_samples_path": str(vram_samples_path.relative_to(out))
                if vram_samples_path is not None
                else None,
                "vram_guardrails": vram_guardrails,
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
    profile = resolved["profile"]

    result = {
        "schema_version": "llmgauge.result.v0",
        "llmgauge_version": __version__,
        "run": {
            "run_id": run_id,
            "timestamp_utc": timestamp,
            "status": run_status,
            "result_dir": str(out),
        },
        "model": {
            "model_id": resolved["model_id"],
            "model_profile": resolved["model_profile"],
            "label": profile.get("label"),
            "family": profile.get("family"),
            "role": profile.get("role"),
            "quant": profile.get("quant"),
            "model_path": "redacted",
            "model_path_policy": "redacted",
        },
        "runtime": {
            "backend": "llama.cpp",
            "llama_cli": str(resolved["llama_cli"]),
            "ctx_size": resolved["ctx"],
            "max_tokens": resolved["max_tokens"],
            "temperature": resolved["temp"],
            "top_p": resolved["top_p"],
            "batch_size": resolved["batch"],
            "ubatch_size": resolved["ubatch"],
            "gpu_layers": resolved["gpu_layers"],
            "flash_attn": resolved["flash_attn"],
            "runtime_label": resolved["runtime_label"],
            "vram_min_headroom_warn_mib": resolved["vram_min_headroom_warn_mib"],
            "command": redacted_command or [],
            "config_path": str(resolved["config_path"])
            if resolved["config_path"]
            else None,
            "model_profiles_path": str(resolved["model_profiles_path"])
            if resolved["model_profiles_path"]
            else None,
        },
        "suite": {
            "suite_id": loaded_suite["suite_id"],
            "suite_version": str(loaded_suite["suite_version"]),
            "suite_path": str(resolved_suite),
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
        if fail_on_failed_prompts:
            raise typer.Exit(code=1)
    else:
        console.print(f"[bold green]Run completed[/bold green]: {out}")

    return result


@app.command()
def contextgen(
    target_tokens: int = typer.Option(
        ...,
        "--target-tokens",
        help="Approximate target token count using a simple character heuristic",
    ),
    needle: str = typer.Option(..., "--needle", help="Needle fact to embed"),
    question: str = typer.Option(..., "--question", help="Final question/task"),
    placement: float = typer.Option(
        0.5,
        "--placement",
        help="Needle placement ratio from 0.0 to 1.0",
    ),
    out_prompt: Path = typer.Option(
        ...,
        "--out-prompt",
        help="Generated prompt Markdown path",
    ),
    out_metadata: Path = typer.Option(
        ...,
        "--out-metadata",
        help="Generated metadata JSON path",
    ),
) -> None:
    """Generate a synthetic long-context prompt."""
    try:
        generated = build_context_prompt(
            target_tokens=target_tokens,
            needle=needle,
            question=question,
            placement=placement,
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    write_context_prompt_artifacts(
        out_prompt=out_prompt,
        out_metadata=out_metadata,
        generated=generated,
    )

    console.print(f"[bold green]Generated prompt[/bold green]: {out_prompt}")
    console.print(f"[bold green]Generated metadata[/bold green]: {out_metadata}")
    console.print(f"Estimated tokens: {generated['estimated_tokens']}")


@app.command()
def run(
    suite: Path = typer.Option(..., "--suite", help="Suite directory"),
    only: str | None = typer.Option(
        None,
        "--only",
        help="Exact prompt ID to run, for example honesty/unknown-package",
    ),
    include: str = typer.Option(
        "all",
        "--include",
        help="Prompt category to run, or 'all'. Ignored when --only is set.",
    ),
    model_id: str | None = typer.Option(None, "--model-id", help="Model identifier"),
    model_profile: str | None = typer.Option(
        None, "--model-profile", help="Model profile name"
    ),
    config_path: Path | None = typer.Option(
        None, "--config", help="LLMGauge config YAML"
    ),
    model_profiles_path: Path | None = typer.Option(
        None,
        "--model-profiles",
        help="Model profiles YAML",
    ),
    model_path: Path | None = typer.Option(
        None, "--model-path", help="GGUF model path"
    ),
    llama_cli: Path | None = typer.Option(None, "--llama-cli", help="llama-cli path"),
    ctx: int | None = typer.Option(None, "--ctx", help="Context size"),
    max_tokens: int | None = typer.Option(
        None, "--max-tokens", help="Max generated tokens"
    ),
    temp: float | None = typer.Option(None, "--temp", help="Temperature"),
    top_p: float | None = typer.Option(None, "--top-p", help="Top-p"),
    batch: int | None = typer.Option(None, "--batch", help="Batch size"),
    ubatch: int | None = typer.Option(None, "--ubatch", help="Micro-batch size"),
    gpu_layers: int | None = typer.Option(None, "--gpu-layers", help="GPU layers"),
    flash_attn: str | None = typer.Option(
        None,
        "--flash-attn",
        help="Flash attention mode: auto, on, or off",
    ),
    runtime_label: str | None = typer.Option(
        None,
        "--runtime-label",
        help="Runtime methodology label, such as stock-reference or daily-tuned",
    ),
    out: Path | None = typer.Option(None, "--out", help="Output result directory"),
    auto_name: bool = typer.Option(
        False,
        "--auto-name",
        help="Automatically create a timestamped output directory",
    ),
    runs_root: Path = typer.Option(
        Path("results"),
        "--runs-root",
        help="Root directory for auto-named runs",
    ),
    run_name: str | None = typer.Option(
        None,
        "--run-name",
        help="Name slug for auto-named run directories",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Resolve and print the run plan without launching llama.cpp",
    ),
) -> None:
    """Run one or more prompts through llama.cpp."""
    resolved = _resolve_run_options(
        model_id=model_id,
        model_profile=model_profile,
        config_path=config_path,
        model_profiles_path=model_profiles_path,
        model_path=model_path,
        llama_cli=llama_cli,
        ctx=ctx,
        max_tokens=max_tokens,
        temp=temp,
        top_p=top_p,
        batch=batch,
        ubatch=ubatch,
        gpu_layers=gpu_layers,
        flash_attn=flash_attn,
        runtime_label=runtime_label,
    )

    if dry_run:
        _print_run_preflight(
            suite=suite,
            only=only,
            include=include,
            resolved=resolved,
            out=out,
            auto_name=auto_name,
            runs_root=runs_root,
            run_name=run_name,
        )
        return

    resolved_out = _resolve_cli_output_dir(
        out=out,
        auto_name=auto_name,
        runs_root=runs_root,
        run_name=run_name,
        default_run_name=f"{resolved['model_id']}-{suite.name}",
    )

    _execute_run(
        suite=suite,
        only=only,
        include=include,
        resolved=resolved,
        out=resolved_out,
        fail_on_failed_prompts=True,
    )


def _print_ladder_preflight(
    *,
    suite: Path,
    loaded_suite: dict[str, Any],
    only: str | None,
    include: str,
    resolved: dict[str, Any],
    contexts: list[int],
    allow_extreme_context: bool,
    out: Path | None,
    auto_name: bool,
    runs_root: Path,
    run_name: str | None,
    default_run_name: str,
) -> None:
    selected_prompts = _select_prompts(loaded_suite, only, include)

    if out is not None:
        output_plan = str(out)

        def child_output_plan(ctx: int) -> str:
            return str(out / f"ctx-{ctx}")

    elif auto_name:
        ladder_name = run_name or default_run_name
        output_plan = f"auto-name under {runs_root} with ladder name {ladder_name}"

        def child_output_plan(ctx: int) -> str:
            return f"<auto ladder dir>/ctx-{ctx}"

    else:
        output_plan = (
            "not required for --dry-run; real ladder runs require --out or --auto-name"
        )

        def child_output_plan(ctx: int) -> str:
            return "not required for --dry-run"

    selection = f"only={only}" if only else f"include={include}"

    table = Table(title="LLMGauge Run Ladder Dry Run")
    table.add_column("Field", no_wrap=True)
    table.add_column("Value")

    table.add_row("Suite", str(loaded_suite.get("suite_id", suite)))
    table.add_row("Suite path", str(suite))
    table.add_row("Selection", selection)
    table.add_row("Prompt count", str(len(selected_prompts)))
    table.add_row("Model ID", str(resolved["model_id"]))
    table.add_row("Model profile", str(resolved["model_profile"]))
    table.add_row("Config", str(resolved["config_path"]))
    table.add_row("Model profiles", str(resolved["model_profiles_path"]))
    table.add_row("Model path", str(resolved["model_path"]))
    table.add_row("llama-cli", str(resolved["llama_cli"]))
    table.add_row("Context ladder", ", ".join(str(ctx) for ctx in contexts))
    table.add_row("Max tokens", str(resolved["max_tokens"]))
    table.add_row("Temperature", str(resolved["temp"]))
    table.add_row("Top-p", str(resolved["top_p"]))
    table.add_row("Batch", str(resolved["batch"]))
    table.add_row("UBatch", str(resolved["ubatch"]))
    table.add_row("GPU layers", str(resolved["gpu_layers"]))
    table.add_row("Flash attention", str(resolved["flash_attn"]))
    table.add_row("Runtime label", str(resolved["runtime_label"] or "unknown"))
    table.add_row("Extreme context opt-in", str(allow_extreme_context))
    table.add_row("Output plan", output_plan)

    console.print(table)

    context_table = Table(title="Planned Context Runs")
    context_table.add_column("Context", no_wrap=True)
    context_table.add_column("Child output plan")

    for ctx in contexts:
        context_table.add_row(str(ctx), child_output_plan(ctx))

    console.print(context_table)

    prompt_table = Table(title="Selected Prompts")
    prompt_table.add_column("Prompt", no_wrap=True)
    prompt_table.add_column("Category", no_wrap=True)
    prompt_table.add_column("Title")

    for prompt in selected_prompts:
        prompt_table.add_row(
            str(prompt.get("id", "")),
            str(prompt.get("category", "")),
            str(prompt.get("title", prompt.get("id", ""))),
        )

    console.print(prompt_table)
    console.print(
        "[bold green]Ladder dry run complete[/bold green]: llama.cpp was not "
        "launched and no ladder or result directories were created."
    )


def _read_attempt_artifact(result_dir: Path, relative_path: Any) -> str:
    if not isinstance(relative_path, str) or not relative_path:
        return ""

    path = result_dir / relative_path
    if not path.exists():
        return ""

    return path.read_text(encoding="utf-8", errors="replace")


def _build_fit_attempt_record_from_result(
    *,
    attempt: dict[str, Any],
    result: dict[str, Any],
    result_dir: Path,
) -> dict[str, Any]:
    prompt_results = result.get("results", [])
    if not isinstance(prompt_results, list):
        prompt_results = []

    failed_prompt = next(
        (
            prompt
            for prompt in prompt_results
            if isinstance(prompt, dict) and prompt.get("status") == "failed"
        ),
        None,
    )

    first_prompt = next(
        (prompt for prompt in prompt_results if isinstance(prompt, dict)),
        None,
    )
    source_prompt = failed_prompt or first_prompt or {}

    run = result.get("run", {})
    run_status = run.get("status") if isinstance(run, dict) else None

    if failed_prompt is None and run_status == "completed":
        exit_status = 0
    else:
        raw_exit_status = source_prompt.get("exit_status")
        exit_status = raw_exit_status if isinstance(raw_exit_status, int) else 1

    stdout = _read_attempt_artifact(result_dir, source_prompt.get("raw_output_path"))
    stderr = _read_attempt_artifact(result_dir, source_prompt.get("stderr_log_path"))

    if not stderr and source_prompt.get("error"):
        stderr = str(source_prompt["error"])

    vram_summary = source_prompt.get("vram")
    if not isinstance(vram_summary, dict):
        vram_summary = None

    return build_fit_attempt_record(
        attempt_id=str(attempt["attempt_id"]),
        ctx_size=int(attempt["ctx_size"]),
        batch_size=int(attempt["batch_size"]),
        ubatch_size=int(attempt["ubatch_size"]),
        gpu_layers=int(attempt["gpu_layers"]),
        exit_status=exit_status,
        stdout=stdout,
        stderr=stderr,
        result_dir=str(result_dir),
        vram_summary=vram_summary,
    )


def _print_fit_ladder_preflight(
    *,
    suite: Path,
    loaded_suite: dict[str, Any],
    only: str | None,
    include: str,
    resolved: dict[str, Any],
    attempts: list[dict[str, Any]],
    out: Path | None,
    auto_name: bool,
    runs_root: Path,
    run_name: str | None,
    default_run_name: str,
) -> None:
    selected_prompts = _select_prompts(loaded_suite, only, include)

    if out is not None:
        output_plan = str(out)
    elif auto_name:
        output_plan = (
            f"auto-name under {runs_root} with fit-ladder name "
            f"{run_name or default_run_name}"
        )
    else:
        output_plan = (
            "not required for --dry-run; real fit-ladder runs require --out or --auto-name"
        )

    selection = f"only={only}" if only else f"include={include}"

    table = Table(title="LLMGauge Fit Ladder Dry Run")
    table.add_column("Field", no_wrap=True)
    table.add_column("Value")

    table.add_row("Suite", str(loaded_suite.get("suite_id", suite)))
    table.add_row("Suite path", str(suite))
    table.add_row("Selection", selection)
    table.add_row("Prompt count", str(len(selected_prompts)))
    table.add_row("Model ID", str(resolved["model_id"]))
    table.add_row("Model profile", str(resolved["model_profile"]))
    table.add_row("Config", str(resolved["config_path"]))
    table.add_row("Model profiles", str(resolved["model_profiles_path"]))
    table.add_row("Model path", str(resolved["model_path"]))
    table.add_row("llama-cli", str(resolved["llama_cli"]))
    table.add_row("Max tokens", str(resolved["max_tokens"]))
    table.add_row("Temperature", str(resolved["temp"]))
    table.add_row("Top-p", str(resolved["top_p"]))
    table.add_row("GPU layers", str(resolved["gpu_layers"]))
    table.add_row("Flash attention", str(resolved["flash_attn"]))
    table.add_row("Runtime label", str(resolved["runtime_label"] or "unknown"))
    table.add_row("Output plan", output_plan)

    console.print(table)

    attempt_table = Table(title="Planned Fit Attempts")
    attempt_table.add_column("Attempt", no_wrap=True)
    attempt_table.add_column("Context", no_wrap=True)
    attempt_table.add_column("Batch", no_wrap=True)
    attempt_table.add_column("UBatch", no_wrap=True)
    attempt_table.add_column("Fallback axes")

    for attempt in attempts:
        attempt_table.add_row(
            str(attempt["attempt_id"]),
            str(attempt["ctx_size"]),
            str(attempt["batch_size"]),
            str(attempt["ubatch_size"]),
            ", ".join(attempt["fallback_axes"]) or "none",
        )

    console.print(attempt_table)
    console.print(
        "[bold green]Fit ladder dry run complete[/bold green]: llama.cpp was not "
        "launched and no fit-ladder directories were created."
    )


@app.command("fit-ladder")
def fit_ladder(
    suite: Path = typer.Option(..., "--suite", help="Suite directory"),
    only: str | None = typer.Option(
        None,
        "--only",
        help="Exact prompt ID to run, for example honesty/unknown-package",
    ),
    include: str = typer.Option(
        "all",
        "--include",
        help="Prompt category to run, or 'all'. Ignored when --only is set.",
    ),
    model_id: str | None = typer.Option(None, "--model-id", help="Model identifier"),
    model_profile: str | None = typer.Option(
        None, "--model-profile", help="Model profile name"
    ),
    config_path: Path | None = typer.Option(
        None, "--config", help="LLMGauge config YAML"
    ),
    model_profiles_path: Path | None = typer.Option(
        None,
        "--model-profiles",
        help="Model profiles YAML",
    ),
    model_path: Path | None = typer.Option(
        None, "--model-path", help="GGUF model path"
    ),
    llama_cli: Path | None = typer.Option(None, "--llama-cli", help="llama-cli path"),
    ctx: int | None = typer.Option(None, "--ctx", help="Requested context size"),
    fallback_contexts: str | None = typer.Option(
        None,
        "--fallback-contexts",
        help="Comma-separated fallback context sizes. Default: 8192,16384,32768",
    ),
    allow_extreme_context: bool = typer.Option(
        False,
        "--allow-extreme-context",
        help="Allow fallback context values above 65536 up to 262144",
    ),
    max_tokens: int | None = typer.Option(
        None, "--max-tokens", help="Max generated tokens"
    ),
    temp: float | None = typer.Option(None, "--temp", help="Temperature"),
    top_p: float | None = typer.Option(None, "--top-p", help="Top-p"),
    batch: int | None = typer.Option(None, "--batch", help="Batch size"),
    ubatch: int | None = typer.Option(None, "--ubatch", help="Micro-batch size"),
    gpu_layers: int | None = typer.Option(None, "--gpu-layers", help="GPU layers"),
    flash_attn: str | None = typer.Option(
        None,
        "--flash-attn",
        help="Flash attention mode: auto, on, or off",
    ),
    runtime_label: str | None = typer.Option(
        None,
        "--runtime-label",
        help="Runtime methodology label, such as stock-reference or daily-tuned",
    ),
    out: Path | None = typer.Option(None, "--out", help="Output fit-ladder directory"),
    auto_name: bool = typer.Option(
        False,
        "--auto-name",
        help="Automatically create a timestamped output directory",
    ),
    runs_root: Path = typer.Option(
        Path("results"),
        "--runs-root",
        help="Root directory for auto-named fit-ladder runs",
    ),
    run_name: str | None = typer.Option(
        None,
        "--run-name",
        help="Name slug for auto-named fit-ladder directories",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Resolve and print the fit-ladder plan without launching llama.cpp",
    ),
) -> None:
    """Run explicit context fallback attempts until one fits or all fail."""
    resolved_suite = resolve_suite_path(suite)
    loaded_suite = load_suite(resolved_suite)

    base_resolved = _resolve_run_options(
        model_id=model_id,
        model_profile=model_profile,
        config_path=config_path,
        model_profiles_path=model_profiles_path,
        model_path=model_path,
        llama_cli=llama_cli,
        ctx=ctx,
        max_tokens=max_tokens,
        temp=temp,
        top_p=top_p,
        batch=batch,
        ubatch=ubatch,
        gpu_layers=gpu_layers,
        flash_attn=flash_attn,
        runtime_label=runtime_label,
    )

    try:
        fallback_values = parse_ctx_ladder(
            fallback_contexts,
            allow_extreme_context=allow_extreme_context,
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    attempts = build_fit_attempt_plan(
        requested_ctx=base_resolved["ctx"],
        fallback_contexts=fallback_values,
        batch_size=base_resolved["batch"],
        ubatch_size=base_resolved["ubatch"],
        gpu_layers=base_resolved["gpu_layers"],
    )
    default_run_name = f"fit-{base_resolved['model_id']}-{suite.name}"

    if dry_run:
        _print_fit_ladder_preflight(
            suite=resolved_suite,
            loaded_suite=loaded_suite,
            only=only,
            include=include,
            resolved=base_resolved,
            attempts=attempts,
            out=out,
            auto_name=auto_name,
            runs_root=runs_root,
            run_name=run_name,
            default_run_name=default_run_name,
        )
        return

    resolved_out = _resolve_cli_output_dir(
        out=out,
        auto_name=auto_name,
        runs_root=runs_root,
        run_name=run_name,
        default_run_name=default_run_name,
    )
    resolved_out.mkdir(parents=True, exist_ok=True)

    console.print(
        f"Running fit ladder [bold]{resolved_out.name}[/bold] with "
        f"[bold]{len(attempts)}[/bold] planned attempt(s)"
    )

    attempt_records: list[dict[str, Any]] = []

    for index, attempt in enumerate(attempts):
        attempt_id = str(attempt["attempt_id"])
        ctx_size = int(attempt["ctx_size"])
        attempt_dir = resolved_out / f"{attempt_id}-ctx-{ctx_size}"

        console.print(
            f"[{index + 1}/{len(attempts)}] Fit attempt "
            f"[bold]{attempt_id}[/bold] at ctx [bold]{ctx_size}[/bold]"
        )

        attempt_resolved = dict(base_resolved)
        attempt_resolved["ctx"] = ctx_size
        attempt_resolved["batch"] = int(attempt["batch_size"])
        attempt_resolved["ubatch"] = int(attempt["ubatch_size"])
        attempt_resolved["gpu_layers"] = int(attempt["gpu_layers"])

        try:
            result = _execute_run(
                suite=suite,
                only=only,
                include=include,
                resolved=attempt_resolved,
                out=attempt_dir,
                fail_on_failed_prompts=False,
            )
            record = _build_fit_attempt_record_from_result(
                attempt=attempt,
                result=result,
                result_dir=attempt_dir,
            )
        except Exception as exc:
            record = build_fit_attempt_record(
                attempt_id=attempt_id,
                ctx_size=ctx_size,
                batch_size=int(attempt["batch_size"]),
                ubatch_size=int(attempt["ubatch_size"]),
                gpu_layers=int(attempt["gpu_layers"]),
                exit_status=1,
                stderr=str(exc),
                result_dir=str(attempt_dir),
            )
            console.print(f"[bold red]Fit attempt failed[/bold red]: {exc}")

        attempt_records.append(record)

        if record["status"] == "completed":
            console.print(
                f"[bold green]Fit ladder selected ctx={ctx_size}[/bold green]"
            )
            break

        has_next_attempt = index + 1 < len(attempts)
        if record["retryable"] and has_next_attempt:
            next_ctx = attempts[index + 1]["ctx_size"]
            console.print(
                f"[bold yellow]{record['failure_class']} detected at ctx={ctx_size}; "
                f"retrying at ctx={next_ctx}[/bold yellow]"
            )
            continue

        if not record["retryable"]:
            console.print(
                f"[bold red]Non-retryable fit failure at ctx={ctx_size}[/bold red]: "
                f"{record['failure_reason']}"
            )
        break

    summary = build_fit_ladder_summary(
        fit_ladder_id=resolved_out.name,
        requested_settings={
            "suite_id": loaded_suite["suite_id"],
            "include": include,
            "only": only,
            "model_id": base_resolved["model_id"],
            "model_profile": base_resolved["model_profile"],
            "ctx_size": base_resolved["ctx"],
            "batch_size": base_resolved["batch"],
            "ubatch_size": base_resolved["ubatch"],
            "gpu_layers": base_resolved["gpu_layers"],
            "max_tokens": base_resolved["max_tokens"],
            "temperature": base_resolved["temp"],
            "top_p": base_resolved["top_p"],
        },
        retry_policy={
            "fallback_order": ["context"],
            "fallback_contexts": fallback_values,
            "stop_on_first_completed": True,
            "gpu_layer_fallback": "explicit-only",
        },
        attempts=attempt_records,
    )
    write_json(resolved_out / "fit-ladder-summary.json", summary)
    report_path = write_fit_ladder_report(resolved_out, summary)

    if summary["final_status"] == "failed":
        console.print(f"[bold red]Fit ladder failed[/bold red]: {resolved_out}")
        console.print(f"Fit ladder report: {report_path}")
        raise typer.Exit(code=1)

    console.print(f"[bold green]Fit ladder completed[/bold green]: {resolved_out}")
    console.print(f"Fit ladder report: {report_path}")

@app.command("run-ladder")
def run_ladder(
    suite: Path = typer.Option(..., "--suite", help="Suite directory"),
    only: str | None = typer.Option(
        None,
        "--only",
        help="Exact prompt ID to run, for example honesty/unknown-package",
    ),
    include: str = typer.Option(
        "all",
        "--include",
        help="Prompt category to run, or 'all'. Ignored when --only is set.",
    ),
    model_id: str | None = typer.Option(None, "--model-id", help="Model identifier"),
    model_profile: str | None = typer.Option(
        None, "--model-profile", help="Model profile name"
    ),
    config_path: Path | None = typer.Option(
        None, "--config", help="LLMGauge config YAML"
    ),
    model_profiles_path: Path | None = typer.Option(
        None,
        "--model-profiles",
        help="Model profiles YAML",
    ),
    model_path: Path | None = typer.Option(
        None, "--model-path", help="GGUF model path"
    ),
    llama_cli: Path | None = typer.Option(None, "--llama-cli", help="llama-cli path"),
    ctx_ladder: str | None = typer.Option(
        None,
        "--ctx-ladder",
        help="Comma-separated context sizes. Default: 8192,16384,32768",
    ),
    allow_extreme_context: bool = typer.Option(
        False,
        "--allow-extreme-context",
        help="Allow explicit context ladder values above 65536 up to 262144",
    ),
    max_tokens: int | None = typer.Option(
        None, "--max-tokens", help="Max generated tokens"
    ),
    temp: float | None = typer.Option(None, "--temp", help="Temperature"),
    top_p: float | None = typer.Option(None, "--top-p", help="Top-p"),
    batch: int | None = typer.Option(None, "--batch", help="Batch size"),
    ubatch: int | None = typer.Option(None, "--ubatch", help="Micro-batch size"),
    gpu_layers: int | None = typer.Option(None, "--gpu-layers", help="GPU layers"),
    flash_attn: str | None = typer.Option(
        None,
        "--flash-attn",
        help="Flash attention mode: auto, on, or off",
    ),
    runtime_label: str | None = typer.Option(
        None,
        "--runtime-label",
        help="Runtime methodology label, such as stock-reference or daily-tuned",
    ),
    out: Path | None = typer.Option(None, "--out", help="Output ladder directory"),
    auto_name: bool = typer.Option(
        False,
        "--auto-name",
        help="Automatically create a timestamped output directory",
    ),
    runs_root: Path = typer.Option(
        Path("results"),
        "--runs-root",
        help="Root directory for auto-named ladder runs",
    ),
    run_name: str | None = typer.Option(
        None,
        "--run-name",
        help="Name slug for auto-named ladder directories",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Resolve and print the ladder run plan without launching llama.cpp",
    ),
) -> None:
    """Run the same selected prompts across multiple context sizes."""
    try:
        contexts = parse_ctx_ladder(
            ctx_ladder,
            allow_extreme_context=allow_extreme_context,
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    child_runs: list[dict[str, Any]] = []
    resolved_suite = resolve_suite_path(suite)
    loaded_suite = load_suite(resolved_suite)
    default_run_name = f"ladder-{model_id or model_profile or loaded_suite['suite_id']}"

    if dry_run:
        resolved = _resolve_run_options(
            model_id=model_id,
            model_profile=model_profile,
            config_path=config_path,
            model_profiles_path=model_profiles_path,
            model_path=model_path,
            llama_cli=llama_cli,
            ctx=contexts[0],
            max_tokens=max_tokens,
            temp=temp,
            top_p=top_p,
            batch=batch,
            ubatch=ubatch,
            gpu_layers=gpu_layers,
            flash_attn=flash_attn,
            runtime_label=runtime_label,
        )
        _print_ladder_preflight(
            suite=resolved_suite,
            loaded_suite=loaded_suite,
            only=only,
            include=include,
            resolved=resolved,
            contexts=contexts,
            allow_extreme_context=allow_extreme_context,
            out=out,
            auto_name=auto_name,
            runs_root=runs_root,
            run_name=run_name,
            default_run_name=default_run_name,
        )
        return

    resolved_out = _resolve_cli_output_dir(
        out=out,
        auto_name=auto_name,
        runs_root=runs_root,
        run_name=run_name,
        default_run_name=default_run_name,
    )

    prepare_result_dir(resolved_out)

    console.print(
        f"Running context ladder [bold]{resolved_out.name}[/bold] across "
        f"[bold]{len(contexts)}[/bold] context size(s): "
        f"{', '.join(str(ctx) for ctx in contexts)}"
    )

    for ctx_size in contexts:
        child_dir = resolved_out / f"ctx-{ctx_size}"
        try:
            resolved = _resolve_run_options(
                model_id=model_id,
                model_profile=model_profile,
                config_path=config_path,
                model_profiles_path=model_profiles_path,
                model_path=model_path,
                llama_cli=llama_cli,
                ctx=ctx_size,
                max_tokens=max_tokens,
                temp=temp,
                top_p=top_p,
                batch=batch,
                ubatch=ubatch,
                gpu_layers=gpu_layers,
                flash_attn=flash_attn,
            )

            result = _execute_run(
                suite=suite,
                only=only,
                include=include,
                resolved=resolved,
                out=child_dir,
                fail_on_failed_prompts=False,
            )

            child_runs.append(
                {
                    "ctx_size": ctx_size,
                    "status": result["run"]["status"],
                    "result_dir": str(child_dir),
                    "completed": result["summary"]["completed"],
                    "failed": result["summary"]["failed"],
                    "error": None
                    if result["run"]["status"] == "completed"
                    else "one or more prompts failed",
                }
            )
        except Exception as exc:
            child_runs.append(
                {
                    "ctx_size": ctx_size,
                    "status": "failed",
                    "result_dir": str(child_dir),
                    "completed": None,
                    "failed": None,
                    "error": str(exc),
                }
            )
            console.print(f"[bold red]Context {ctx_size} failed[/bold red]: {exc}")

    summary = build_ladder_summary(
        ladder_id=resolved_out.name,
        suite_id=loaded_suite["suite_id"],
        include=include,
        only=only,
        model_id=str(model_id or model_profile or "unknown-model"),
        contexts=contexts,
        child_runs=child_runs,
        allow_extreme_context=allow_extreme_context,
    )
    write_ladder_summary(resolved_out, summary)
    write_ladder_report(resolved_out, summary)

    if summary["summary"]["failed"]:
        console.print(
            f"[bold red]Context ladder completed with failures[/bold red]: {resolved_out}"
        )
        raise typer.Exit(code=1)

    console.print(f"[bold green]Context ladder completed[/bold green]: {resolved_out}")


@app.command("run-batch")
def run_batch(
    manifest: Path = typer.Option(..., "--manifest", help="Batch manifest YAML"),
    config_path: Path = typer.Option(..., "--config", help="LLMGauge config YAML"),
    model_profiles_path: Path = typer.Option(
        ...,
        "--model-profiles",
        help="Model profiles YAML",
    ),
    out: Path = typer.Option(..., "--out", help="Output batch directory"),
) -> None:
    """Run selected prompts sequentially across manifest-listed model profiles."""
    try:
        manifest_data = load_batch_manifest(manifest)
    except (OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc

    suite_path = Path(manifest_data["suite"])
    resolved_suite = resolve_suite_path(suite_path)
    loaded_suite = load_suite(resolved_suite)

    prepare_result_dir(out)

    model_profiles = manifest_data["models"]
    console.print(
        f"Running model batch [bold]{manifest_data['batch_id']}[/bold] across "
        f"[bold]{len(model_profiles)}[/bold] model profile(s)"
    )

    child_runs: list[dict[str, Any]] = []

    for index, model_profile_name in enumerate(model_profiles, start=1):
        child_dir = out / f"model-{index:02d}-{slugify_run_name(model_profile_name)}"

        try:
            resolved = _resolve_run_options(
                model_id=None,
                model_profile=model_profile_name,
                config_path=config_path,
                model_profiles_path=model_profiles_path,
                model_path=None,
                llama_cli=None,
                ctx=None,
                max_tokens=manifest_data["max_tokens"],
                temp=None,
                top_p=None,
                batch=None,
                ubatch=None,
                gpu_layers=None,
                flash_attn=None,
                runtime_label=None,
            )

            result = _execute_run(
                suite=suite_path,
                only=manifest_data["only"],
                include=manifest_data["include"],
                resolved=resolved,
                out=child_dir,
                fail_on_failed_prompts=False,
            )

            child_runs.append(
                {
                    "model_profile": model_profile_name,
                    "model_id": result["model"]["model_id"],
                    "status": result["run"]["status"],
                    "result_dir": str(child_dir),
                    "completed": result["summary"]["completed"],
                    "failed": result["summary"]["failed"],
                    "error": None
                    if result["run"]["status"] == "completed"
                    else "one or more prompts failed",
                }
            )
        except Exception as exc:
            child_runs.append(
                {
                    "model_profile": model_profile_name,
                    "model_id": None,
                    "status": "failed",
                    "result_dir": str(child_dir),
                    "completed": None,
                    "failed": None,
                    "error": str(exc),
                }
            )
            console.print(
                f"[bold red]Model profile {model_profile_name} failed[/bold red]: {exc}"
            )

    summary = build_batch_summary(
        batch_id=manifest_data["batch_id"],
        suite_id=loaded_suite["suite_id"],
        suite_path=str(resolved_suite),
        include=manifest_data["include"],
        only=manifest_data["only"],
        max_tokens=manifest_data["max_tokens"],
        models=model_profiles,
        child_runs=child_runs,
        manifest_path=str(manifest),
    )
    write_batch_summary(out, summary)
    write_batch_report(out, summary)

    if summary["summary"]["failed"]:
        console.print(
            f"[bold red]Model batch completed with failures[/bold red]: {out}"
        )
        raise typer.Exit(code=1)

    console.print(f"[bold green]Model batch completed[/bold green]: {out}")


@app.command("validate-batch")
def validate_batch(
    batch_dir: Path = typer.Argument(..., help="LLMGauge model batch directory"),
) -> None:
    """Validate a LLMGauge model batch directory."""
    try:
        errors = validate_batch_dir(batch_dir)
    except Exception as exc:
        console.print(f"[bold red]Batch validation failed[/bold red]: {exc}")
        raise typer.Exit(code=1) from exc

    if errors:
        console.print("[bold red]Batch validation failed[/bold red]")
        for error in errors:
            console.print(f"- {error}")
        raise typer.Exit(code=1)

    console.print(f"[bold green]OK[/bold green] {batch_dir}")


@app.command("validate-fit-ladder")
def validate_fit_ladder(
    fit_ladder_dir: Path = typer.Argument(..., help="Fit Ladder artifact directory"),
) -> None:
    """Validate a Fit Ladder artifact directory."""
    errors = validate_fit_ladder_dir(fit_ladder_dir)

    if errors:
        console.print("[bold red]Invalid fit-ladder artifact[/bold red]")
        for error in errors:
            console.print(f"- {error}")
        raise typer.Exit(code=1)

    console.print("[bold green]Fit Ladder artifact is valid[/bold green]")


@app.command("validate-ladder")
def validate_ladder(
    ladder_dir: Path = typer.Argument(..., help="LLMGauge ladder result directory"),
) -> None:
    """Validate a LLMGauge context ladder directory."""
    try:
        errors = validate_ladder_dir(ladder_dir)
    except Exception as exc:
        console.print(f"[bold red]Ladder validation failed[/bold red]: {exc}")
        raise typer.Exit(code=1) from exc

    if errors:
        console.print("[bold red]Ladder validation failed[/bold red]")
        for error in errors:
            console.print(f"- {error}")
        raise typer.Exit(code=1)

    console.print(f"[bold green]OK[/bold green] {ladder_dir}")


@app.command("validate-result")
def validate_result(
    result_dir: Path = typer.Argument(..., help="LLMGauge result directory"),
) -> None:
    """Validate a LLMGauge result directory."""
    try:
        errors = validate_result_dir(result_dir)
    except Exception as exc:
        console.print(f"[bold red]Result validation failed[/bold red]: {exc}")
        raise typer.Exit(code=1) from exc

    if errors:
        console.print("[bold red]Result validation failed[/bold red]")
        for error in errors:
            console.print(f"- {error}")
        raise typer.Exit(code=1)

    console.print(f"[bold green]OK[/bold green] {result_dir}")


@app.command()
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
        _fail_cli_validation("--check cannot be used with --init")

    if auto_draft and init:
        _fail_cli_validation("--auto-draft cannot be used with --init")

    if auto_draft and scores is not None:
        _fail_cli_validation("--auto-draft cannot be used with --scores")

    if auto_draft and check:
        _fail_cli_validation("--auto-draft cannot be used with --check")

    if force and not auto_draft:
        _fail_cli_validation("--force can only be used with --auto-draft")

    if check and scores is None:
        _fail_cli_validation("--check requires --scores PATH")

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
            _fail_cli_validation(str(exc))

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

    metadata_only_count = _metadata_only_score_prompt_count(scores_data)

    if check:
        console.print(f"[bold green]Score validation passed[/bold green]: {scores}")
        _print_metadata_only_score_warning(metadata_only_count)
        return

    _print_metadata_only_score_warning(metadata_only_count)
    updated = apply_scores(result, scores_data)
    write_result(result_dir, updated)
    write_text(result_dir / "report.md", build_markdown_report(updated))

    console.print(f"[bold green]Applied scores[/bold green]: {scores}")
    console.print(f"Updated: {result_dir / 'llmgauge-result.json'}")
    console.print(f"Updated: {result_dir / 'report.md'}")


@app.command("export-index")
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


@app.command("baseline-check")
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


@app.command()
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


def main() -> None:
    app()


if __name__ == "__main__":
    main()
