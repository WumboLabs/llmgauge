from pathlib import Path

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
