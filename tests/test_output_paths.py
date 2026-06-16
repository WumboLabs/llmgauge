from datetime import UTC, datetime
from pathlib import Path

import pytest

from llmgauge.core.output_paths import (
    build_auto_output_dir,
    slugify_run_name,
    timestamp_for_output,
)


def test_slugify_run_name() -> None:
    assert (
        slugify_run_name("Gemma 4 QAT / Agent Backend") == "gemma-4-qat-agent-backend"
    )


def test_slugify_run_name_rejects_empty() -> None:
    with pytest.raises(ValueError, match="empty"):
        slugify_run_name("   ")


def test_slugify_run_name_rejects_non_alphanumeric() -> None:
    with pytest.raises(ValueError, match="alphanumeric"):
        slugify_run_name("///")


def test_timestamp_for_output_uses_utc_format() -> None:
    now = datetime(2026, 6, 16, 5, 30, 45, tzinfo=UTC)
    assert timestamp_for_output(now) == "2026-06-16_05-30-45"


def test_build_auto_output_dir_returns_first_sequence(tmp_path: Path) -> None:
    now = datetime(2026, 6, 16, 5, 30, 45, tzinfo=UTC)

    output_dir = build_auto_output_dir(
        runs_root=tmp_path,
        run_name="Agent Backend Smoke",
        now=now,
    )

    assert output_dir == tmp_path / "2026-06-16_05-30-45-agent-backend-smoke-001"


def test_build_auto_output_dir_increments_sequence(tmp_path: Path) -> None:
    now = datetime(2026, 6, 16, 5, 30, 45, tzinfo=UTC)

    first = tmp_path / "2026-06-16_05-30-45-agent-backend-smoke-001"
    first.mkdir(parents=True)

    output_dir = build_auto_output_dir(
        runs_root=tmp_path,
        run_name="Agent Backend Smoke",
        now=now,
    )

    assert output_dir == tmp_path / "2026-06-16_05-30-45-agent-backend-smoke-002"
