from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path


def slugify_run_name(value: str) -> str:
    stripped = value.strip().lower()
    if not stripped:
        raise ValueError("run name must not be empty")

    slug = re.sub(r"[^a-z0-9]+", "-", stripped)
    slug = slug.strip("-")

    if not slug:
        raise ValueError("run name must contain at least one alphanumeric character")

    return slug


def timestamp_for_output(now: datetime | None = None) -> str:
    resolved = now if now is not None else datetime.now(UTC)

    if resolved.tzinfo is None:
        resolved = resolved.replace(tzinfo=UTC)

    resolved = resolved.astimezone(UTC)
    return resolved.strftime("%Y-%m-%d_%H-%M-%S")


def build_auto_output_dir(
    *,
    runs_root: Path,
    run_name: str,
    now: datetime | None = None,
) -> Path:
    slug = slugify_run_name(run_name)
    timestamp = timestamp_for_output(now)
    base_name = f"{timestamp}-{slug}"

    runs_root.mkdir(parents=True, exist_ok=True)

    for sequence in range(1, 1000):
        candidate = runs_root / f"{base_name}-{sequence:03d}"
        if not candidate.exists():
            return candidate

    raise RuntimeError(f"could not find available output directory for {base_name!r}")
