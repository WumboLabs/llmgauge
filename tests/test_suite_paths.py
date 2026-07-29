from pathlib import Path
import shutil

import pytest

from llmgauge.core import suite_paths
from llmgauge.core.suite import SuiteDefinitionError, load_normalized_suite, load_suite
from llmgauge.core.suite_paths import (
    builtin_suites_dir,
    resolve_suite_path,
    resolve_suites_dir,
)


def test_builtin_suites_dir_contains_core_suite() -> None:
    suites_dir = builtin_suites_dir()

    assert suites_dir.exists()
    assert (suites_dir / "core-v1" / "suite.yaml").exists()
    assert (suites_dir / "agent-backend-v1" / "suite.yaml").exists()
    assert (suites_dir / "wumbolabs-practical-v1" / "suite.yaml").exists()


def test_resolve_suites_dir_falls_back_to_builtins_outside_repo(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    suites_dir = resolve_suites_dir()

    assert suites_dir.exists()
    assert (suites_dir / "core-v1" / "suite.yaml").exists()


def test_resolve_suite_path_accepts_builtin_suite_name_outside_repo(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    suite_dir = resolve_suite_path(Path("core-v1"))

    assert suite_dir.exists()
    assert suite_dir.name == "core-v1"
    assert (suite_dir / "suite.yaml").exists()


def test_missing_packaged_resource_fails_without_checkout_fallback(
    tmp_path: Path,
    monkeypatch,
) -> None:
    packaged_root = tmp_path / "builtin_suites"
    packaged_suite = packaged_root / "core-v1"
    shutil.copytree(Path("src/llmgauge/builtin_suites/core-v1"), packaged_suite)
    manifest = load_suite(packaged_suite)
    missing_resource = packaged_suite / manifest["prompts"][0]["file"]
    missing_resource.unlink()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(suite_paths, "builtin_suites_dir", lambda: packaged_root)

    resolved = suite_paths.resolve_suite_path(Path("core-v1"))

    assert resolved == packaged_suite
    with pytest.raises(SuiteDefinitionError, match="missing-resource") as exc_info:
        load_normalized_suite(resolved)
    assert str(missing_resource) not in str(exc_info.value)
