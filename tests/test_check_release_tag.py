"""Focused tests for the release tag/version guard."""

from __future__ import annotations

import subprocess
import tomllib
from pathlib import Path

import pytest

from scripts.check_release_tag import (
    expected_version_for_tag,
    validate_release_tag,
    verify_tag_commit_identity,
)

REPOSITORY_ROOT = Path(__file__).parents[1]
PYPROJECT = REPOSITORY_ROOT / "pyproject.toml"


def current_pyproject_version() -> str:
    with PYPROJECT.open("rb") as handle:
        return tomllib.load(handle)["project"]["version"]


@pytest.mark.parametrize(
    ("tag", "expected"),
    [
        ("v0.74", "0.74.0"),
        ("v0.74.1", "0.74.1"),
        ("v0.74.0rc1", "0.74.0rc1"),
        ("v1.2", "1.2.0"),
        ("v10.20.30", "10.20.30"),
    ],
)
def test_tag_to_version_mapping(tag: str, expected: str) -> None:
    assert expected_version_for_tag(tag) == expected


@pytest.mark.parametrize(
    "tag",
    [
        "",
        "v",
        "0.73",
        "release-v0.73",
        "vgarbage",
        "v01.2",
        "v0.73.0.1",
        "v0.73-dev",
        "V0.73",
        "v0.73 ",
        "v-0.73",
    ],
)
def test_malformed_tags_map_to_nothing(tag: str) -> None:
    assert expected_version_for_tag(tag) is None


@pytest.mark.parametrize("tag", ["v0.74", "v0.74.0"])
def test_current_release_tags_pass_against_pyproject(tag: str) -> None:
    assert current_pyproject_version() == "0.74.0"
    ok, message = validate_release_tag(tag, PYPROJECT)
    assert ok
    assert tag in message


@pytest.mark.parametrize(
    "tag", ["0.74", "release-v0.74", "vgarbage", "v0.73", "v0.73.1", "v0.75"]
)
def test_rejected_tags_fail_closed_against_pyproject(tag: str) -> None:
    ok, message = validate_release_tag(tag, PYPROJECT)
    assert not ok
    assert message


def test_validator_cli_passes_for_current_tag() -> None:
    result = subprocess.run(
        ["python3", "scripts/check_release_tag.py", "v0.74"],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0


def test_validator_cli_fails_for_version_mismatch() -> None:
    result = subprocess.run(
        ["python3", "scripts/check_release_tag.py", "v0.75"],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1


def _init_temp_repository(work_path: Path) -> Path:
    repo = work_path / "repo"
    repo.mkdir()

    def git(*args: str) -> None:
        subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)

    git("init", "-q")
    git("config", "user.email", "test@example.invalid")
    git("config", "user.name", "Test")
    (repo / "pyproject.toml").write_text(
        '[project]\nname = "llmgauge"\nversion = "0.74.0"\n', encoding="utf-8"
    )
    git("add", "pyproject.toml")
    git("commit", "-q", "-m", "init")
    return repo


def test_check_commit_accepts_annotated_tag_at_checked_out_commit(
    tmp_path: Path,
) -> None:
    repo = _init_temp_repository(tmp_path)
    subprocess.run(
        ["git", "tag", "-a", "v0.74", "-m", "release v0.74"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    ok, message = validate_release_tag(
        "v0.74", repo / "pyproject.toml", repository=repo, check_commit=True
    )
    assert ok
    assert "annotated" in message


def test_check_commit_rejects_lightweight_tag(tmp_path: Path) -> None:
    repo = _init_temp_repository(tmp_path)
    subprocess.run(["git", "tag", "v0.74"], cwd=repo, check=True, capture_output=True)
    ok, message = validate_release_tag(
        "v0.74", repo / "pyproject.toml", repository=repo, check_commit=True
    )
    assert not ok
    assert "annotated" in message


def test_check_commit_rejects_tag_on_other_commit(tmp_path: Path) -> None:
    repo = _init_temp_repository(tmp_path)

    def git(*args: str) -> None:
        subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)

    git("tag", "-a", "v0.74", "-m", "release v0.74")
    (repo / "pyproject.toml").write_text(
        '[project]\nname = "llmgauge"\nversion = "0.74.0"\n# moved\n',
        encoding="utf-8",
    )
    git("add", "pyproject.toml")
    git("commit", "-q", "-m", "second")
    ok, message = verify_tag_commit_identity("v0.74", repo)
    assert not ok
    assert "checked-out commit" in message


def test_check_commit_rejects_missing_tag(tmp_path: Path) -> None:
    repo = _init_temp_repository(tmp_path)
    ok, message = verify_tag_commit_identity("v9.99", repo)
    assert not ok
    assert message
