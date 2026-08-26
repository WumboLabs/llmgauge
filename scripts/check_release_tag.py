#!/usr/bin/env python3
"""Validate an LLMGauge release tag against the packaged version.

Accepted release-tag mapping (fail closed on anything else):

    vX.Y       <-> X.Y.0
    vX.Y.Z     <-> X.Y.Z
    vX.Y[.Z]S  <-> X.Y[.Z]S   where S is a prerelease suffix (aN, bN, rcN)

The preferred LLMGauge release tag for a `.0` release remains ``vX.Y``;
exact three-component equivalence (``vX.Y.Z``) is intentionally supported.

With ``--check-commit`` the script additionally verifies, using Git in the
repository working tree, that the tag exists, is an annotated tag, and that
its target commit is exactly the currently checked-out commit.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tomllib
from pathlib import Path

_NUM = r"(?:0|[1-9][0-9]*)"
_TAG_PATTERN = re.compile(rf"^v({_NUM})\.({_NUM})(?:\.({_NUM}))?((?:a|b|rc){_NUM})?$")


def expected_version_for_tag(tag: str) -> str | None:
    """Return the package version a release tag must match, else ``None``."""
    match = _TAG_PATTERN.fullmatch(tag)
    if match is None:
        return None
    major, minor, patch, prerelease = match.groups()
    return f"{major}.{minor}.{patch or '0'}{prerelease or ''}"


def read_pyproject_version(pyproject: Path) -> str:
    """Read the declared project version from ``pyproject.toml``."""
    with pyproject.open("rb") as handle:
        metadata = tomllib.load(handle)
    version = metadata["project"]["version"]
    if not isinstance(version, str) or not version:
        raise ValueError(f"missing [project] version in {pyproject}")
    return version


def _git_output(repository: Path, *args: str) -> str | None:
    result = subprocess.run(
        ["git", *args],
        cwd=repository,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def verify_tag_commit_identity(tag: str, repository: Path) -> tuple[bool, str]:
    """Verify the tag is annotated and resolves to the checked-out commit."""
    object_type = _git_output(repository, "cat-file", "-t", tag)
    if object_type != "tag":
        return (
            False,
            f"{tag!r} is not an annotated tag (found {object_type or 'nothing'})",
        )
    peeled = _git_output(repository, "rev-parse", f"{tag}^{{commit}}")
    head = _git_output(repository, "rev-parse", "HEAD")
    if peeled is None or head is None:
        return False, f"could not resolve {tag!r} or HEAD in the repository"
    if peeled != head:
        return False, (
            f"tag {tag!r} resolves to commit {peeled}, "
            f"but the checked-out commit is {head}"
        )
    return True, f"annotated tag {tag!r} resolves to the checked-out commit {head}"


def validate_release_tag(
    tag: str,
    pyproject: Path,
    repository: Path | None = None,
    *,
    check_commit: bool = False,
) -> tuple[bool, str]:
    """Validate a release tag against the packaged version.

    With ``check_commit``, also require an annotated tag resolving to the
    checked-out commit (used for production tag pushes).
    """
    expected = expected_version_for_tag(tag)
    if expected is None:
        return False, (
            f"malformed release tag {tag!r}: expected vX.Y, vX.Y.Z, or the same "
            "with a prerelease suffix (aN, bN, rcN)"
        )
    actual = read_pyproject_version(pyproject)
    if actual != expected:
        return False, (
            f"release tag {tag!r} requires package version {expected}, "
            f"but pyproject declares {actual}"
        )
    if check_commit:
        if repository is None:
            raise ValueError("check_commit requires a repository path")
        return verify_tag_commit_identity(tag, repository)
    return True, f"release tag {tag!r} matches package version {actual}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("tag", help="release tag to validate, e.g. v0.74")
    parser.add_argument(
        "--pyproject",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "pyproject.toml",
        help="path to pyproject.toml (default: repository root)",
    )
    parser.add_argument(
        "--check-commit",
        action="store_true",
        help="also require an annotated tag resolving to the checked-out commit",
    )
    args = parser.parse_args(argv)

    ok, message = validate_release_tag(
        args.tag,
        args.pyproject,
        repository=args.pyproject.parent,
        check_commit=args.check_commit,
    )
    print(message, file=sys.stderr if not ok else sys.stdout)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
