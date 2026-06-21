from __future__ import annotations

import re


_METRICS_LINE_RE = re.compile(r"^\[\s*Prompt:\s+.*\|\s*Generation:\s+.*\]\s*$")


def _strip_trailing_runtime_lines(lines: list[str]) -> list[str]:
    stripped = list(lines)

    while stripped and stripped[-1].strip() in {"", "Exiting..."}:
        stripped.pop()

    for index, line in enumerate(stripped):
        if _METRICS_LINE_RE.match(line.strip()):
            return stripped[:index]

    return stripped


def _strip_leading_llama_echo(lines: list[str]) -> list[str]:
    system_index = None
    for index, line in enumerate(lines):
        if line.strip() == "> SYSTEM:":
            system_index = index
            break

    if system_index is None:
        return lines

    for index in range(system_index, len(lines)):
        if "(truncated)" in lines[index]:
            return lines[index + 1 :]

    return lines[system_index:]


def _trim_blank_edges(lines: list[str]) -> list[str]:
    stripped = list(lines)

    while stripped and stripped[0].strip() == "":
        stripped.pop(0)

    while stripped and stripped[-1].strip() == "":
        stripped.pop()

    return stripped


def clean_llama_output(raw_output: str) -> str:
    """Return a review-oriented cleaned view of llama.cpp stdout.

    This function is intentionally conservative. It does not rewrite model answer
    content. It only removes obvious llama.cpp terminal wrapper text when the
    captured output matches the interactive/simple-io format used by LLMGauge.

    Raw output remains the audit source of truth.
    """

    lines = raw_output.splitlines()
    lines = _strip_leading_llama_echo(lines)
    lines = _strip_trailing_runtime_lines(lines)
    lines = _trim_blank_edges(lines)

    if not lines:
        return ""

    return "\n".join(lines) + "\n"
