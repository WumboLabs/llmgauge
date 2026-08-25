"""Distribution metadata and content guards for public packaging.

These tests prove the built wheel and sdist carry PyPI-grade metadata,
license text, packaged suite resources, and no local/private leakage.
Exact Generic Core inventory equivalence is owned by
``tests/test_generic_core_content_package.py``.
"""

import os
import subprocess
import tarfile
import zipfile
from pathlib import Path


import pytest

REPOSITORY_ROOT = Path(__file__).parents[1]
LICENSE_PATH = REPOSITORY_ROOT / "LICENSE"

EXPECTED_VERSION = "0.73.0"
EXPECTED_URLS = {
    "Homepage": "https://github.com/WumboLabs/llmgauge",
    "Repository": "https://github.com/WumboLabs/llmgauge",
    "Issues": "https://github.com/WumboLabs/llmgauge/issues",
    "Changelog": "https://github.com/WumboLabs/llmgauge/blob/main/CHANGELOG.md",
}

FORBIDDEN_NAME_MARKERS = ("tmp/", "results/", ".gguf")
# Actual private values, not the product's own redaction-pattern literals.
FORBIDDEN_TEXT_MARKERS = (
    os.fspath(REPOSITORY_ROOT),
    os.fspath(Path.home()),
)
MAX_TEXT_MEMBER_BYTES = 1_000_000


@pytest.fixture(scope="module")
def built_distributions(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    dist_dir = tmp_path_factory.mktemp("distribution-metadata-dist")
    subprocess.run(
        ["uv", "build", "--out-dir", str(dist_dir)],
        cwd=REPOSITORY_ROOT,
        check=True,
        timeout=300,
    )
    return next(dist_dir.glob("*.whl")), next(dist_dir.glob("*.tar.gz"))


def _core_metadata(headers: list[str]) -> dict[str, list[str]]:
    values: dict[str, list[str]] = {}
    for header in headers:
        key, _, raw_value = header.partition(": ")
        values.setdefault(key, []).append(raw_value)
    return values


def _wheel_metadata_headers(wheel: Path) -> list[str]:
    with zipfile.ZipFile(wheel) as archive:
        name = next(
            entry
            for entry in archive.namelist()
            if entry.endswith(".dist-info/METADATA")
        )
        return archive.read(name).decode("utf-8").splitlines()


def _sdist_pkg_info_headers(sdist: Path) -> list[str]:
    with tarfile.open(sdist, "r:gz") as archive:
        member = next(
            entry for entry in archive.getmembers() if entry.name.endswith("PKG-INFO")
        )
        extracted = archive.extractfile(member)
        assert extracted is not None
        return extracted.read().decode("utf-8").splitlines()


def test_built_artifacts_use_the_current_release_version(
    built_distributions: tuple[Path, Path],
) -> None:
    wheel, sdist = built_distributions

    assert wheel.name == f"llmgauge-{EXPECTED_VERSION}-py3-none-any.whl"
    assert sdist.name == f"llmgauge-{EXPECTED_VERSION}.tar.gz"


def test_wheel_metadata_is_pypi_grade(built_distributions: tuple[Path, Path]) -> None:
    wheel, _ = built_distributions
    metadata = _core_metadata(_wheel_metadata_headers(wheel))

    assert metadata["Version"] == [EXPECTED_VERSION]
    assert metadata["License-Expression"] == ["MIT"]
    assert metadata["License-File"] == ["LICENSE"]
    project_urls = dict(
        part.split(", ", 1)
        for part in metadata["Project-URL"]  # type: ignore[union-attr]
    )
    assert project_urls == EXPECTED_URLS


def test_sdist_pkg_info_matches_wheel_metadata(
    built_distributions: tuple[Path, Path],
) -> None:
    wheel, sdist = built_distributions
    wheel_metadata = _core_metadata(_wheel_metadata_headers(wheel))
    pkg_info = _core_metadata(_sdist_pkg_info_headers(sdist))

    for key in ("Version", "License-Expression", "License-File", "Project-URL"):
        assert pkg_info[key] == wheel_metadata[key]


def test_license_text_ships_byte_identical_in_both_artifacts(
    built_distributions: tuple[Path, Path],
) -> None:
    wheel, sdist = built_distributions
    license_bytes = LICENSE_PATH.read_bytes()

    with zipfile.ZipFile(wheel) as archive:
        wheel_license = archive.read(
            f"llmgauge-{EXPECTED_VERSION}.dist-info/licenses/LICENSE"
        )

    with tarfile.open(sdist, "r:gz") as archive:
        member = archive.extractfile(f"llmgauge-{EXPECTED_VERSION}/LICENSE")
        assert member is not None
        sdist_license = member.read()

    assert wheel_license == license_bytes
    assert sdist_license == license_bytes


def test_wheel_carries_package_modules_and_generic_core_resources(
    built_distributions: tuple[Path, Path],
) -> None:
    wheel, _ = built_distributions

    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()

    for module in (
        "llmgauge/__init__.py",
        "llmgauge/cli.py",
        "llmgauge/core/suite_paths.py",
    ):
        assert module in names
    core_prefix = "llmgauge/builtin_suites/generic-core-v1/"
    bundled = [
        name.removeprefix(core_prefix) for name in names if name.startswith(core_prefix)
    ]
    assert "suite.yaml" in bundled
    assert sum(name.startswith("prompts/") for name in bundled) >= 13
    assert sum(name.startswith("fixtures/") for name in bundled) >= 4


def test_artifacts_contain_no_local_or_private_content(
    built_distributions: tuple[Path, Path],
) -> None:
    wheel, sdist = built_distributions

    wheel_members: dict[str, bytes] = {}
    with zipfile.ZipFile(wheel) as archive:
        for info in archive.infolist():
            if not info.is_dir():
                wheel_members[info.filename] = archive.read(info)

    sdist_members: dict[str, bytes] = {}
    with tarfile.open(sdist, "r:gz") as archive:
        for member in archive.getmembers():
            if member.isfile() and member.size <= MAX_TEXT_MEMBER_BYTES:
                extracted = archive.extractfile(member)
                assert extracted is not None
                sdist_members[member.name] = extracted.read()

    for members in (wheel_members, sdist_members):
        for name, payload in members.items():
            lowered_name = name.lower()
            for marker in FORBIDDEN_NAME_MARKERS:
                assert marker not in lowered_name, name
            try:
                text = payload.decode("utf-8")
            except UnicodeDecodeError:
                continue
            for marker in FORBIDDEN_TEXT_MARKERS:
                assert marker not in text, name
