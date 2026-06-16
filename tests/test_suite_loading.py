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
