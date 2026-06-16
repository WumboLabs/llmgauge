import json
from pathlib import Path

import pytest

from llmgauge.core.contextgen import (
    build_context_prompt,
    estimate_tokens,
    write_context_prompt_artifacts,
)


def test_estimate_tokens() -> None:
    assert estimate_tokens("") == 0
    assert estimate_tokens("abcd") == 1
    assert estimate_tokens("abcde") == 2


def test_build_context_prompt_contains_needle_and_question() -> None:
    generated = build_context_prompt(
        target_tokens=512,
        needle="The secret project codename is Wumbo Finch.",
        question="What is the secret project codename?",
        placement=0.5,
    )

    assert generated["schema_version"] == "llmgauge.context_prompt.v0"
    assert generated["target_tokens"] == 512
    assert generated["estimated_tokens"] >= 512
    assert "The secret project codename is Wumbo Finch." in generated["prompt"]
    assert "What is the secret project codename?" in generated["prompt"]
    assert "[IMPORTANT NEEDLE FACT]" in generated["prompt"]


def test_build_context_prompt_placement_changes_needle_position() -> None:
    early = build_context_prompt(
        target_tokens=512,
        needle="Needle early.",
        question="Find the needle.",
        placement=0.1,
    )
    late = build_context_prompt(
        target_tokens=512,
        needle="Needle late.",
        question="Find the needle.",
        placement=0.9,
    )

    early_position = early["prompt"].find("[IMPORTANT NEEDLE FACT]")
    late_position = late["prompt"].find("[IMPORTANT NEEDLE FACT]")

    assert early_position < late_position


def test_build_context_prompt_rejects_bad_placement() -> None:
    with pytest.raises(ValueError, match="placement"):
        build_context_prompt(
            target_tokens=512,
            needle="Needle.",
            question="Question?",
            placement=1.5,
        )


def test_build_context_prompt_rejects_empty_needle() -> None:
    with pytest.raises(ValueError, match="needle"):
        build_context_prompt(
            target_tokens=512,
            needle="",
            question="Question?",
        )


def test_write_context_prompt_artifacts(tmp_path: Path) -> None:
    generated = build_context_prompt(
        target_tokens=256,
        needle="The answer is local.",
        question="What is the answer?",
    )

    prompt_path = tmp_path / "prompt.md"
    metadata_path = tmp_path / "metadata.json"

    write_context_prompt_artifacts(
        out_prompt=prompt_path,
        out_metadata=metadata_path,
        generated=generated,
    )

    assert prompt_path.exists()
    assert metadata_path.exists()

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata["schema_version"] == "llmgauge.context_prompt.v0"
    assert "prompt" not in metadata
