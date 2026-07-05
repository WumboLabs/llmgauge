from pathlib import Path


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


def test_source_checkout_suites_match_packaged_builtin_suites() -> None:
    source_files = _mirrored_files(ROOT_SUITE_DIR)
    builtin_files = _mirrored_files(BUILTIN_SUITE_DIR)

    assert sorted(source_files) == sorted(builtin_files)

    for relative_path, source_path in source_files.items():
        builtin_path = builtin_files[relative_path]
        assert source_path.read_text(encoding="utf-8") == builtin_path.read_text(
            encoding="utf-8"
        ), f"Suite mirror drift in {relative_path}"
