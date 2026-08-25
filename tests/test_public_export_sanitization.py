"""Synthetic regression for the public-export sanitizer contract.

This test deliberately avoids any real model-run evidence. It checks that the
public-export sanitizer rewrites absolute paths while leaving otherwise clean
synthetic prompt text intact.
"""

import llmgauge.core.public_export as public_export
from llmgauge.commands.run_helpers import build_combined_prompt, load_system_prompt


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


def test_sanitize_text_on_clean_synthetic_prompts_is_benign_or_absolute_path_only() -> (
    None
):
    """Clean synthetic prompts stay unchanged except ordinary absolute paths,
    which public export must rewrite."""
    synthetic_prompts = [
        "Summarize this example run log in five bullet points.",
        "Explain how you would review this example compose file for service "
        "ordering problems.",
    ]
    for prompt_text in synthetic_prompts:
        rendered = build_combined_prompt(load_system_prompt(), prompt_text)

        categories: set[str] = set()
        sanitized = public_export._sanitize_text(rendered, categories)

        assert categories <= {"absolute_path"}
        assert rendered != sanitized or categories == set()
        if rendered != sanitized:
            assert "REDACTED_ABSOLUTE_PATH" in sanitized
