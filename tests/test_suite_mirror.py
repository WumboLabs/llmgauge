from hashlib import sha256
from pathlib import Path

import pytest


ROOT_SUITE_DIR = Path("suites")
BUILTIN_SUITE_DIR = Path("src/llmgauge/builtin_suites")

INTENTIONALLY_SOURCE_ONLY_SUITES = frozenset({"wumbolabs-practical-use-v1"})
EXPECTED_HISTORICAL_SUITE_SHA256 = {
    Path(
        "wumbolabs-practical-use-v1/suite.yaml"
    ): "39dbce3bb36aea166a8f59a1a284fd42c2145ab0c2ef932fbac0caba665115bf",
    Path(
        "wumbolabs-practical-use-v1/prompts/coding/python-log-parser.md"
    ): "d82474e433e3acff1982da69c1006a1c8f667b3e2cba56292422cac4670e1593",
    Path(
        "wumbolabs-practical-use-v1/prompts/docker/compose-review.md"
    ): "5300f46a122c965d161c861ee056d87773d91d1af028bc2596dee08250144b2f",
    Path(
        "wumbolabs-practical-use-v1/prompts/honesty/unknown-package.md"
    ): "2f21fabe26dadbe2af242b6e2dcc0b7ade86298de113f48db155442cce6eec7f",
    Path(
        "wumbolabs-practical-use-v1/prompts/linux/arch-nvidia-update-advice.md"
    ): "8f513449383094bf5df8a32080f7347a672fc90add4494e304e37d151e1d1e82",
    Path(
        "wumbolabs-practical-use-v1/prompts/local-llm/consumer-gpu-advice.md"
    ): "c22240d6aa3e99c0f6f3626247e425052f1b0b7fb7bd647827b8e958e62ff4e6",
    Path(
        "wumbolabs-practical-use-v1/prompts/summarization/technical-run-summary.md"
    ): "73286e2fa553f5671131a86b04fcc2bd34b6aada2808f9e3f33168bf7da0c0e5",
}


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


def _packaged_source_files(root: Path) -> dict[Path, Path]:
    return {
        relative: path
        for relative, path in _mirrored_files(root).items()
        if relative.parts[0] not in INTENTIONALLY_SOURCE_ONLY_SUITES
    }


def _assert_suite_mirrors_match(source_root: Path, builtin_root: Path) -> None:
    source_files = _packaged_source_files(source_root)
    builtin_files = _mirrored_files(builtin_root)

    assert sorted(source_files) == sorted(builtin_files)

    for relative_path, source_path in source_files.items():
        builtin_path = builtin_files[relative_path]
        assert source_path.read_bytes() == builtin_path.read_bytes(), (
            f"Suite mirror drift in {relative_path}"
        )


def test_source_checkout_suites_match_packaged_builtin_suites() -> None:
    _assert_suite_mirrors_match(ROOT_SUITE_DIR, BUILTIN_SUITE_DIR)


def test_historical_practical_suite_is_intentionally_source_only_and_immutable() -> (
    None
):
    source_files = _mirrored_files(ROOT_SUITE_DIR)
    packaged_source_files = _packaged_source_files(ROOT_SUITE_DIR)
    builtin_files = _mirrored_files(BUILTIN_SUITE_DIR)
    historical_files = {
        relative: path
        for relative, path in source_files.items()
        if relative.parts[0] == "wumbolabs-practical-use-v1"
    }

    assert set(historical_files) == set(EXPECTED_HISTORICAL_SUITE_SHA256)
    assert historical_files.keys().isdisjoint(packaged_source_files)
    assert historical_files.keys().isdisjoint(builtin_files)

    for relative_path, expected_digest in EXPECTED_HISTORICAL_SUITE_SHA256.items():
        assert sha256(historical_files[relative_path].read_bytes()).hexdigest() == (
            expected_digest
        )


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
