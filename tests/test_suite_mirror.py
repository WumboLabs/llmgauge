from pathlib import Path

import pytest


ROOT_SUITE_DIR = Path("suites")
BUILTIN_SUITE_DIR = Path("src/llmgauge/builtin_suites")


def _mirrored_files(root: Path) -> dict[Path, Path]:
    files: dict[Path, Path] = {}

    for path in root.rglob("*"):
        if not path.is_file():
            continue

        relative = path.relative_to(root)

        if relative.parts[0] == "__pycache__":
            continue
        if "__pycache__" in relative.parts:
            continue
        if path.suffix == ".pyc":
            continue
        if path.name == "__init__.py":
            continue

        # Top-level source-checkout suites may include local baseline files that
        # are intentionally not packaged with built-in prompt suites.
        if "baselines" in relative.parts:
            continue

        files[relative] = path

    return files


def _assert_suite_mirrors_match(source_root: Path, builtin_root: Path) -> None:
    source_files = _mirrored_files(source_root)
    builtin_files = _mirrored_files(builtin_root)

    assert sorted(source_files) == sorted(builtin_files)

    for relative_path, source_path in source_files.items():
        builtin_path = builtin_files[relative_path]
        assert source_path.read_bytes() == builtin_path.read_bytes(), (
            f"Suite mirror drift in {relative_path}"
        )


def test_source_checkout_suites_match_packaged_builtin_suites() -> None:
    _assert_suite_mirrors_match(ROOT_SUITE_DIR, BUILTIN_SUITE_DIR)


def test_unexpected_source_only_ordinary_suite_fails_mirror_check(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "suites"
    builtin_root = tmp_path / "builtin_suites"
    ordinary_suite = source_root / "ordinary-v1"
    ordinary_suite.mkdir(parents=True)
    builtin_root.mkdir()
    (ordinary_suite / "suite.yaml").write_text(
        "suite_id: ordinary-v1\n", encoding="utf-8"
    )

    with pytest.raises(AssertionError):
        _assert_suite_mirrors_match(source_root, builtin_root)
