from __future__ import annotations

import os
from importlib import resources
from pathlib import Path

import typer
from rich.console import Console


DEFAULT_LOCAL_CONFIG = Path("examples/configs/llmgauge.local.yaml")
DEFAULT_LOCAL_MODEL_PROFILES = Path("examples/configs/model-profiles.local.yaml")
USER_CONFIG_FILENAME = "config.yaml"
USER_MODEL_PROFILES_FILENAME = "model-profiles.yaml"
EXAMPLE_CONFIG = Path("examples/configs/llmgauge.example.yaml")
EXAMPLE_MODEL_PROFILES = Path("examples/configs/model-profiles.example.yaml")


class _LazyConsole:
    """Defer Console creation so tests can set NO_COLOR before first print."""

    def __init__(self) -> None:
        self._console: Console | None = None

    def _get(self) -> Console:
        if self._console is None:
            no_color = bool(os.environ.get("NO_COLOR")) or os.environ.get("TERM") == "dumb"
            self._console = Console(no_color=no_color, force_terminal=not no_color)
        return self._console

    def print(self, *args, **kwargs) -> None:
        self._get().print(*args, **kwargs)


console = _LazyConsole()


def fail_cli_validation(message: str) -> None:
    typer.echo(message, err=True)
    raise typer.Exit(2)


def llmgauge_user_config_dir() -> Path:
    xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config_home:
        return Path(xdg_config_home) / "llmgauge"
    return Path.home() / ".config" / "llmgauge"


def user_config_path() -> Path:
    return llmgauge_user_config_dir() / USER_CONFIG_FILENAME


def user_model_profiles_path() -> Path:
    return llmgauge_user_config_dir() / USER_MODEL_PROFILES_FILENAME


def default_existing_path(*paths: Path) -> Path | None:
    for candidate in paths:
        if candidate.exists():
            return candidate
    return None


def default_model_profiles_path(explicit: Path | None = None) -> Path | None:
    if explicit is not None:
        return explicit
    return default_existing_path(DEFAULT_LOCAL_MODEL_PROFILES, user_model_profiles_path())


def is_placeholder_path(path: Path) -> bool:
    return str(path).startswith("/path/to/")


def read_packaged_template(template_name: str) -> str:
    return (
        resources.files("llmgauge")
        .joinpath("templates")
        .joinpath("configs")
        .joinpath(template_name)
        .read_text(encoding="utf-8")
    )