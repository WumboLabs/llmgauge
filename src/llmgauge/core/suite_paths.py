from importlib.resources import files
from pathlib import Path


DEFAULT_REPO_SUITES_DIR = Path("suites")

BUILTIN_SUITE_ALIASES: dict[str, str] = {
    "agent": "agent-backend-v1",
    "agent-backend": "agent-backend-v1",
    "core": "core-v1",
    "context": "context-v1",
    "practical": "wumbolabs-practical-v1",
    "wumbolabs": "wumbolabs-practical-v1",
    "wumbolabs-practical": "wumbolabs-practical-v1",
}


def canonical_suite_name(name: str) -> str:
    """Return the canonical built-in suite name for a user-facing alias."""
    return BUILTIN_SUITE_ALIASES.get(name, name)


def suite_aliases_for(suite_id: str) -> tuple[str, ...]:
    """Return user-facing aliases that resolve to a canonical built-in suite."""
    return tuple(
        alias
        for alias, target in sorted(BUILTIN_SUITE_ALIASES.items())
        if target == suite_id
    )


def builtin_suites_dir() -> Path:
    """Return the installed built-in suites directory."""
    resource = files("llmgauge.builtin_suites")
    return Path(str(resource))


def resolve_suites_dir(suites_dir: Path | None = None) -> Path:
    """Resolve the suites root directory.

    Explicit paths are used as-is. When running from a source checkout, the
    repository-level suites directory is preferred. Installed packages fall back
    to packaged built-in suites.
    """
    if suites_dir is not None:
        return suites_dir

    if DEFAULT_REPO_SUITES_DIR.exists():
        return DEFAULT_REPO_SUITES_DIR

    return builtin_suites_dir()


def resolve_suite_path(suite: Path) -> Path:
    """Resolve a suite path, built-in suite ID, or built-in suite alias."""
    if suite.exists():
        return suite

    if suite.is_absolute() or len(suite.parts) > 1:
        return suite

    suite_name = canonical_suite_name(suite.name)
    candidate = resolve_suites_dir() / suite_name
    if candidate.exists():
        return candidate

    return suite
