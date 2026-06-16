from __future__ import annotations

import re
from typing import Any


PROMPT_EVAL_RE = re.compile(
    r"prompt eval time\s*=\s*.*?/\s*(?P<tokens>\d+)\s+tokens\s*"
    r"\((?P<tps>[0-9.]+)\s+tokens per second\)",
    re.IGNORECASE,
)

EVAL_RE = re.compile(
    r"eval time\s*=\s*.*?/\s*(?P<tokens>\d+)\s+runs\s*"
    r"\((?P<tps>[0-9.]+)\s+tokens per second\)",
    re.IGNORECASE,
)

COMPACT_SUMMARY_RE = re.compile(
    r"\[\s*Prompt:\s*(?P<prompt_tps>[0-9.]+)\s*t/s\s*\|\s*"
    r"Generation:\s*(?P<generation_tps>[0-9.]+)\s*t/s\s*\]",
    re.IGNORECASE,
)


def parse_llama_metrics(text: str) -> dict[str, Any]:
    prompt_eval_tokens = None
    prompt_eval_tps = None
    generation_tokens = None
    generation_tps = None

    prompt_match = PROMPT_EVAL_RE.search(text)
    if prompt_match:
        prompt_eval_tokens = int(prompt_match.group("tokens"))
        prompt_eval_tps = float(prompt_match.group("tps"))

    eval_match = EVAL_RE.search(text)
    if eval_match:
        generation_tokens = int(eval_match.group("tokens"))
        generation_tps = float(eval_match.group("tps"))

    compact_match = COMPACT_SUMMARY_RE.search(text)
    if compact_match:
        if prompt_eval_tps is None:
            prompt_eval_tps = float(compact_match.group("prompt_tps"))
        if generation_tps is None:
            generation_tps = float(compact_match.group("generation_tps"))

    return {
        "prompt_eval_tokens": prompt_eval_tokens,
        "prompt_eval_tps": prompt_eval_tps,
        "generation_tokens": generation_tokens,
        "generation_tps": generation_tps,
        "peak_vram_mib": None,
        "vram_headroom_mib": None,
    }
