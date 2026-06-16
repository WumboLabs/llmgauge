from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any


DEFAULT_CHARS_PER_TOKEN = 4

DEFAULT_FILLER_BLOCK = """This is synthetic filler text for a long-context evaluation. It is intentionally mundane, repetitive, and low-salience. The goal is to create context pressure without adding hidden factual claims or model-specific knowledge requirements. The model should preserve the important needle fact and answer the final task using only information present in this generated prompt."""


def estimate_tokens(text: str, chars_per_token: int = DEFAULT_CHARS_PER_TOKEN) -> int:
    if chars_per_token <= 0:
        raise ValueError("chars_per_token must be positive")

    if not text:
        return 0

    return math.ceil(len(text) / chars_per_token)


def _validate_generation_inputs(
    *,
    target_tokens: int,
    placement: float,
    chars_per_token: int,
) -> None:
    if target_tokens <= 0:
        raise ValueError("target_tokens must be positive")

    if placement < 0 or placement > 1:
        raise ValueError("placement must be between 0 and 1")

    if chars_per_token <= 0:
        raise ValueError("chars_per_token must be positive")


def _repeat_filler_to_tokens(
    *,
    target_tokens: int,
    filler: str,
    chars_per_token: int,
) -> str:
    if target_tokens <= 0:
        return ""

    if not filler.strip():
        raise ValueError("filler must not be empty")

    chunks: list[str] = []
    current_tokens = 0
    counter = 1

    while current_tokens < target_tokens:
        block = f"[filler-block-{counter}]\n{filler.strip()}\n"
        chunks.append(block)
        current_tokens = estimate_tokens("\n".join(chunks), chars_per_token)
        counter += 1

    return "\n".join(chunks).strip()


def build_context_prompt(
    *,
    target_tokens: int,
    needle: str,
    question: str,
    placement: float = 0.5,
    filler: str = DEFAULT_FILLER_BLOCK,
    chars_per_token: int = DEFAULT_CHARS_PER_TOKEN,
) -> dict[str, Any]:
    _validate_generation_inputs(
        target_tokens=target_tokens,
        placement=placement,
        chars_per_token=chars_per_token,
    )

    if not needle.strip():
        raise ValueError("needle must not be empty")

    if not question.strip():
        raise ValueError("question must not be empty")

    header = """# Synthetic Long-Context Evaluation Prompt

You are being tested on long-context retention. Most of the context below is low-salience filler. One important needle fact appears somewhere in the context. Use only the information in this prompt to answer the final task.

## Context
"""

    needle_block = f"""[IMPORTANT NEEDLE FACT]
{needle.strip()}
[/IMPORTANT NEEDLE FACT]
"""

    final_task = f"""## Final Task

{question.strip()}

Requirements:
- Answer using only the generated context.
- Do not invent facts not present in the prompt.
- If the needle fact is not available, say so.
"""

    fixed_text = header + "\n" + needle_block + "\n" + final_task
    fixed_tokens = estimate_tokens(fixed_text, chars_per_token)
    filler_budget = max(target_tokens - fixed_tokens, 0)

    pre_tokens = int(filler_budget * placement)
    post_tokens = max(filler_budget - pre_tokens, 0)

    pre_filler = _repeat_filler_to_tokens(
        target_tokens=pre_tokens,
        filler=filler,
        chars_per_token=chars_per_token,
    )
    post_filler = _repeat_filler_to_tokens(
        target_tokens=post_tokens,
        filler=filler,
        chars_per_token=chars_per_token,
    )

    parts = [
        header.strip(),
    ]

    if pre_filler:
        parts.append(pre_filler)

    parts.append(needle_block.strip())

    if post_filler:
        parts.append(post_filler)

    parts.append(final_task.strip())

    prompt = "\n\n".join(parts).strip() + "\n"
    estimated_tokens = estimate_tokens(prompt, chars_per_token)

    return {
        "schema_version": "llmgauge.context_prompt.v0",
        "target_tokens": target_tokens,
        "estimated_tokens": estimated_tokens,
        "chars_per_token": chars_per_token,
        "placement": placement,
        "needle": needle.strip(),
        "question": question.strip(),
        "filler_block_tokens_estimate": estimate_tokens(filler, chars_per_token),
        "prompt": prompt,
    }


def write_context_prompt_artifacts(
    *,
    out_prompt: Path,
    out_metadata: Path,
    generated: dict[str, Any],
) -> None:
    out_prompt.parent.mkdir(parents=True, exist_ok=True)
    out_metadata.parent.mkdir(parents=True, exist_ok=True)

    out_prompt.write_text(generated["prompt"], encoding="utf-8")

    metadata = {key: value for key, value in generated.items() if key != "prompt"}
    out_metadata.write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
