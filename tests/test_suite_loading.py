from pathlib import Path

from llmgauge.core.suite import load_suite, validate_suite


def test_core_v1_suite_loads() -> None:
    suite = load_suite(Path("suites/core-v1"))
    assert suite["suite_id"] == "core-v1"
    assert len(suite["prompts"]) == 8


def test_core_v1_suite_validates() -> None:
    errors = validate_suite(Path("suites/core-v1"))
    assert errors == []


def test_context_v1_suite_loads() -> None:
    suite = load_suite(Path("suites/context-v1"))
    assert suite["suite_id"] == "context-v1"


def test_agent_backend_v1_suite_loads() -> None:
    suite = load_suite(Path("suites/agent-backend-v1"))
    assert suite["suite_id"] == "agent-backend-v1"


def test_wumbolabs_practical_v1_suite_loads() -> None:
    suite = load_suite(Path("suites/wumbolabs-practical-v1"))
    assert suite["suite_id"] == "wumbolabs-practical-v1"
    assert suite["evaluation_tier"] == 2
    assert len(suite["prompts"]) == 10


def test_wumbolabs_practical_v1_suite_validates() -> None:
    errors = validate_suite(Path("suites/wumbolabs-practical-v1"))
    assert errors == []


def test_validate_suite_reports_missing_title(tmp_path: Path) -> None:
    """A legacy manifest without a top-level title loads unchanged while
    validate_suite reports the missing field."""
    suite_dir = tmp_path / "suite"
    (suite_dir / "prompts").mkdir(parents=True)
    (suite_dir / "prompts" / "example.md").write_text(
        "Example synthetic prompt.\n", encoding="utf-8"
    )
    (suite_dir / "suite.yaml").write_text(
        "schema_version: llmgauge.suite.v0\n"
        "suite_id: synthetic-title-v1\n"
        "suite_version: 0.1.0\n"
        "prompts:\n"
        "  - id: example/task\n"
        "    title: Example Task\n"
        "    category: example\n"
        "    file: prompts/example.md\n",
        encoding="utf-8",
    )

    assert load_suite(suite_dir)["suite_id"] == "synthetic-title-v1"
    assert validate_suite(suite_dir) == ["Missing required field: title"]
