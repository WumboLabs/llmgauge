from __future__ import annotations

from importlib.resources import files
from pathlib import Path

DEFAULT_REPO_SUITES_DIR = Path("suites")


def builtin_suites_dir() -> Path:
    """Return the installed built-in suites directory."""
    resource = files("llmgauge.builtin_suites")
    return Path(str(resource))


def resolve_suites_dir(suites_dir: Path | None = None) -> Path:
    """Resolve the default suites directory.

    Resolution order:
    1. explicit suites_dir argument
    2. ./suites from the current working directory
    3. packaged built-in suites
    """
    if suites_dir is not None:
        return suites_dir

    if DEFAULT_REPO_SUITES_DIR.exists():
        return DEFAULT_REPO_SUITES_DIR

    return builtin_suites_dir()


def resolve_suite_path(suite: Path) -> Path:
    """Resolve a suite path or built-in suite name.

    Explicit existing paths are used as-is. A single path component such as
    "core-v1" may resolve to a built-in suite under the default suites dir.
    """
    if suite.exists():
        return suite

    if len(suite.parts) == 1:
        candidate = resolve_suites_dir() / suite.name
        if candidate.exists():
            return candidate

    return suite
