#!/usr/bin/env python3
"""Check that a build ``dist`` directory holds exactly the expected release artifacts.

The release workflow runs this after ``uv build`` and before uploading the
artifact, so a publish job can never receive an unexpected or incomplete set
of distributions.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def validate_dist_dir(dist_dir: Path, expected_version: str) -> tuple[bool, str]:
    """Return ``(ok, message)`` for the built distributions in ``dist_dir``."""
    if not dist_dir.is_dir():
        return False, f"dist directory does not exist: {dist_dir}"
    entries = sorted(entry.name for entry in dist_dir.iterdir())
    expected_wheel = f"llmgauge-{expected_version}-py3-none-any.whl"
    expected_sdist = f"llmgauge-{expected_version}.tar.gz"
    if set(entries) != {expected_sdist, expected_wheel}:
        return False, (
            f"expected exactly the {expected_version!r} wheel and sdist in "
            f"{dist_dir}, found {entries!r}"
        )
    return True, f"dist contains exactly the {expected_version} wheel and sdist"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--dist-dir",
        type=Path,
        default=Path("dist"),
        help="directory containing built distributions (default: dist)",
    )
    parser.add_argument("--expected-version", required=True, help="package version")
    args = parser.parse_args(argv)

    ok, message = validate_dist_dir(args.dist_dir, args.expected_version)
    print(message, file=sys.stderr if not ok else sys.stdout)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
