from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

from llmgauge.core.config import load_yaml_file
from llmgauge.core.schemas import validate_llmgauge_config_document

GGUF_SCAN_LIMIT = 50

_RELATIVE_LLAMA_CLI_CANDIDATES = (
    Path("llama-cli"),
    Path("bin/llama-cli"),
    Path("llama.cpp/build/bin/llama-cli"),
    Path("llama.cpp/build-cuda/bin/llama-cli"),
    Path("llama.cpp/build-cuda-sm120/bin/llama-cli"),
)

_HOME_LLAMA_CLI_SUFFIXES = (
    Path("llama.cpp/build/bin/llama-cli"),
    Path("llama.cpp/build-cuda/bin/llama-cli"),
    Path("llama.cpp/build-cuda-sm120/bin/llama-cli"),
    Path("Projects/local-llm/llama.cpp/build/bin/llama-cli"),
    Path("Projects/local-llm/llama.cpp/build-cuda/bin/llama-cli"),
    Path("Projects/local-llm/llama.cpp/build-cuda-sm120/bin/llama-cli"),
)

_HOME_MODEL_DIRECTORY_SUFFIXES = (
    Path("Models"),
    Path("models"),
    Path("AI/models"),
    Path("Projects/local-llm/models"),
    Path("Projects/local-llm/llama.cpp-models"),
)


def is_placeholder_path(path: Path) -> bool:
    return str(path).startswith("/path/to/")


def sanitize_profile_name(source: str) -> str:
    base = Path(source).name
    if base.lower().endswith(".gguf"):
        base = base[: -len(".gguf")]

    normalized = base.lower()
    normalized = re.sub(r"[^a-z0-9_]+", "_", normalized)
    normalized = re.sub(r"_+", "_", normalized).strip("_")

    if not normalized:
        normalized = "model"

    return normalized[:48]


def is_executable_file(path: Path) -> bool:
    return path.is_file() and os.access(path, os.X_OK)


def storage_path_string(path: Path) -> str:
    return str(path.expanduser().resolve())


def _dedupe_sorted_paths(paths: list[Path]) -> list[Path]:
    seen: set[str] = set()
    unique: list[Path] = []

    for path in paths:
        try:
            resolved = path.expanduser().resolve()
        except OSError:
            continue

        key = str(resolved)
        if key in seen:
            continue

        seen.add(key)
        unique.append(resolved)

    return sorted(unique, key=str)


def discover_llama_cli_candidates(*, cwd: Path | None = None) -> list[Path]:
    candidates: list[Path] = []

    which = shutil.which("llama-cli")
    if which:
        candidates.append(Path(which))

    base = cwd or Path.cwd()
    for relative in _RELATIVE_LLAMA_CLI_CANDIDATES:
        candidates.append((base / relative).resolve())

    home = Path.home()
    for suffix in _HOME_LLAMA_CLI_SUFFIXES:
        candidates.append((home / suffix).resolve())

    existing = [path for path in _dedupe_sorted_paths(candidates) if path.exists()]
    return existing


def discover_model_directory_candidates(*, cwd: Path | None = None) -> list[Path]:
    candidates: list[Path] = []
    base = cwd or Path.cwd()
    home = Path.home()

    candidates.append((base / "models").resolve())
    for suffix in _HOME_MODEL_DIRECTORY_SUFFIXES:
        candidates.append((home / suffix).resolve())

    existing = [
        path
        for path in _dedupe_sorted_paths(candidates)
        if path.exists() and path.is_dir()
    ]
    return existing


def scan_gguf_files(
    directory: Path,
    *,
    limit: int = GGUF_SCAN_LIMIT,
) -> tuple[list[Path], int]:
    if not directory.exists() or not directory.is_dir():
        return [], 0

    discovered = sorted(
        (
            path.resolve()
            for path in directory.rglob("*.gguf")
            if path.is_file()
        ),
        key=str,
    )

    total = len(discovered)
    return discovered[:limit], total


def validate_llama_cli_for_setup(path: Path) -> None:
    resolved = path.expanduser().resolve()
    if not resolved.exists():
        raise ValueError(f"llama-cli path does not exist: {resolved}")
    if not resolved.is_file():
        raise ValueError(f"llama-cli path is not a file: {resolved}")
    if not os.access(resolved, os.X_OK):
        raise ValueError(f"llama-cli path is not executable: {resolved}")


def validate_model_path_for_setup(path: Path) -> None:
    resolved = path.expanduser().resolve()
    if not resolved.exists():
        raise ValueError(f"Model path does not exist: {resolved}")
    if not resolved.is_file():
        raise ValueError(f"Model path is not a file: {resolved}")
    if resolved.suffix.lower() != ".gguf":
        raise ValueError(f"Model path must be a .gguf file: {resolved}")


def current_config_llama_cli(config_path: Path) -> str | None:
    if not config_path.exists():
        return None

    data = load_yaml_file(config_path)
    runtime = data.get("runtime")
    if not isinstance(runtime, dict):
        return None

    value = runtime.get("llama_cli")
    return str(value) if isinstance(value, str) and value else None


def can_replace_config_llama_cli(
    config_path: Path,
    *,
    force: bool,
) -> tuple[bool, str | None]:
    current = current_config_llama_cli(config_path)
    if current is None:
        return True, None

    current_path = Path(current)
    if is_placeholder_path(current_path):
        return True, current

    if force:
        return True, current

    return False, current


def update_config_llama_cli(
    config_path: Path,
    llama_cli: Path,
    *,
    force: bool = False,
    template_text: str | None = None,
) -> bool:
    validate_llama_cli_for_setup(llama_cli)

    allowed, current = can_replace_config_llama_cli(config_path, force=force)
    if not allowed:
        raise ValueError(
            f"Config already sets runtime.llama_cli to {current!r}; "
            "use --force to replace it"
        )

    if config_path.exists():
        data = load_yaml_file(config_path)
    elif template_text is not None:
        import yaml

        data = yaml.safe_load(template_text) or {}
    else:
        data = {"schema_version": "llmgauge.config.v0"}

    runtime = data.get("runtime")
    if not isinstance(runtime, dict):
        runtime = {}
        data["runtime"] = runtime

    runtime["llama_cli"] = storage_path_string(llama_cli)
    validate_llmgauge_config_document(data)

    import yaml

    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return current != runtime["llama_cli"]
