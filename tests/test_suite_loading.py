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


def test_historical_source_only_suite_loads_without_rewrite() -> None:
    suite = load_suite(Path("suites/wumbolabs-practical-use-v1"))

    assert suite["suite_id"] == "wumbolabs-practical-use-v1"
    assert suite["suite_version"] == "0.1.0"


def test_historical_source_only_validation_is_unchanged() -> None:
    errors = validate_suite(Path("suites/wumbolabs-practical-use-v1"))

    assert errors == ["Missing required field: title"]
