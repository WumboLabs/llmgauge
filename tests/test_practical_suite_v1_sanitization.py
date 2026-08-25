"""Synthetic regression for the historical practical suite and public-export
sanitization.

This test deliberately avoids any real model-run evidence. Suite-level
integrity (SHA immutability, source-only mirror policy) is owned by
``tests/test_suite_mirror.py``; this module only checks loadability and the
public-export sanitizer contract with synthetic content.
"""

from pathlib import Path

import llmgauge.core.public_export as public_export
from llmgauge.commands.run_helpers import build_combined_prompt, load_system_prompt
from llmgauge.core.suite import load_suite

SUITE_DIR = Path("suites/wumbolabs-practical-use-v1")

EXPECTED_PROMPT_IDS = [
    "linux/arch-nvidia-update-advice",
    "coding/python-log-parser",
    "docker/compose-review",
    "honesty/unknown-package",
    "summarization/technical-run-summary",
    "local-llm/consumer-gpu-advice",
]


def test_historical_practical_suite_loads_with_expected_inventory() -> None:
    suite = load_suite(SUITE_DIR)

    assert suite["suite_id"] == "wumbolabs-practical-use-v1"
    assert suite["suite_version"] == "0.1.0"
    assert [prompt["id"] for prompt in suite["prompts"]] == EXPECTED_PROMPT_IDS


def test_sanitize_text_rewrites_injected_absolute_path() -> None:
    rendered = build_combined_prompt(
        load_system_prompt(),
        "Review this compose file at /srv/operator-stack/docker-compose.yml.",
    )

    categories: set[str] = set()
    sanitized = public_export._sanitize_text(rendered, categories)

    assert rendered != sanitized
    assert "/srv/operator-stack" not in sanitized
    assert "REDACTED_ABSOLUTE_PATH" in sanitized


def test_sanitize_text_on_historical_suite_prompts_is_benign_or_absolute_path_only() -> (
    None
):
    """Historical source prompts are already clean except for ordinary
    absolute paths, which public export must rewrite."""
    for prompt in load_suite(SUITE_DIR)["prompts"]:
        source_text = (SUITE_DIR / prompt["file"]).read_text(encoding="utf-8")
        rendered = build_combined_prompt(load_system_prompt(), source_text.strip())

        categories: set[str] = set()
        sanitized = public_export._sanitize_text(rendered, categories)

        assert categories <= {"absolute_path"}
        assert rendered != sanitized or categories == set()
        if rendered != sanitized:
            assert "REDACTED_ABSOLUTE_PATH" in sanitized
