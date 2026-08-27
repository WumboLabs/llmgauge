"""Focused tests for the release distribution-content guard."""

from __future__ import annotations

from pathlib import Path

from scripts.check_release_dist import validate_dist_dir

VERSION = "0.75.0"


def _write(dist: Path, name: str) -> None:
    (dist / name).write_bytes(b"x")


def test_exact_wheel_and_sdist_pass(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    _write(dist, f"llmgauge-{VERSION}-py3-none-any.whl")
    _write(dist, f"llmgauge-{VERSION}.tar.gz")

    ok, message = validate_dist_dir(dist, VERSION)

    assert ok
    assert message


def test_missing_sdist_fails(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    _write(dist, f"llmgauge-{VERSION}-py3-none-any.whl")

    ok, _ = validate_dist_dir(dist, VERSION)

    assert not ok


def test_extra_file_fails(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    _write(dist, f"llmgauge-{VERSION}-py3-none-any.whl")
    _write(dist, f"llmgauge-{VERSION}.tar.gz")
    _write(dist, "notes.txt")

    ok, _ = validate_dist_dir(dist, VERSION)

    assert not ok


def test_wrong_version_fails(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    _write(dist, "llmgauge-0.73.0-py3-none-any.whl")
    _write(dist, "llmgauge-0.73.0.tar.gz")

    ok, message = validate_dist_dir(dist, VERSION)

    assert not ok
    assert "0.73.0" in message


def test_missing_dist_dir_fails(tmp_path: Path) -> None:
    ok, message = validate_dist_dir(tmp_path / "absent", VERSION)

    assert not ok
    assert "does not exist" in message
