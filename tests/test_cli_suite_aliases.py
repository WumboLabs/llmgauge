from pathlib import Path

from typer.testing import CliRunner

from llmgauge.cli import app
from llmgauge.core.suite import load_suite
from llmgauge.core.suite_paths import (
    canonical_suite_name,
    resolve_suite_path,
    suite_aliases_for,
)

runner = CliRunner()


def test_canonical_suite_name_accepts_friendly_aliases() -> None:
    assert canonical_suite_name("core") == "core-v1"
    assert canonical_suite_name("context") == "context-v1"
    assert canonical_suite_name("agent") == "agent-backend-v1"
    assert canonical_suite_name("practical") == "wumbolabs-practical-v1"
    assert canonical_suite_name("custom-suite") == "custom-suite"


def test_suite_aliases_for_returns_known_aliases() -> None:
    assert "core" in suite_aliases_for("core-v1")
    assert "agent" in suite_aliases_for("agent-backend-v1")
    assert "practical" in suite_aliases_for("wumbolabs-practical-v1")


def test_resolve_suite_path_accepts_builtin_alias_outside_repo(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    suite_dir = resolve_suite_path(Path("practical"))

    assert suite_dir.exists()
    assert suite_dir.name == "wumbolabs-practical-v1"
    assert (suite_dir / "suite.yaml").exists()


def test_load_suite_alias_preserves_canonical_suite_id(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    suite = load_suite(resolve_suite_path(Path("practical")))

    assert suite["suite_id"] == "wumbolabs-practical-v1"


def test_validate_suite_accepts_alias() -> None:
    result = runner.invoke(app, ["validate-suite", "practical"])

    assert result.exit_code == 0


def test_list_suites_shows_aliases() -> None:
    result = runner.invoke(app, ["list-suites"])

    assert result.exit_code == 0
    assert "Aliases" in result.output
    assert "core" in result.output
    assert "practical" in result.output
