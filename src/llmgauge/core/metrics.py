from __future__ import annotations

import math
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

_PERF_PREFIXES = ("llama_perf_context_print:", "llama_print_timings:")
_PLACEMENT_PREFIXES = ("llm_load_tensors:",)

_LOAD_TIME_RE = re.compile(
    r"^\s*(?:llama_perf_context_print|llama_print_timings):\s*"
    r"load time\s*=\s*(?P<ms>[0-9.]+)\s*ms\s*$",
    re.IGNORECASE,
)
_PROMPT_EVAL_DIAG_RE = re.compile(
    r"^\s*(?:llama_perf_context_print|llama_print_timings):\s*"
    r"prompt eval time\s*=\s*(?P<ms>[0-9.]+)\s*ms\s*/\s*(?P<tokens>\d+)\s+tokens"
    r"\s*\((?P<tps>[0-9.]+)\s+tokens per second\)\s*$",
    re.IGNORECASE,
)
_EVAL_DIAG_RE = re.compile(
    r"^\s*(?:llama_perf_context_print|llama_print_timings):\s*"
    r"eval time\s*=\s*(?P<ms>[0-9.]+)\s*ms\s*/\s*(?P<tokens>\d+)\s+runs"
    r"\s*\((?P<tps>[0-9.]+)\s+tokens per second\)\s*$",
    re.IGNORECASE,
)
_TOTAL_TIME_RE = re.compile(
    r"^\s*(?:llama_perf_context_print|llama_print_timings):\s*"
    r"total time\s*=\s*(?P<ms>[0-9.]+)\s*ms\s*/\s*(?P<tokens>\d+)\s+tokens\s*$",
    re.IGNORECASE,
)
_OFFLOAD_RE = re.compile(
    r"^\s*llm_load_tensors:\s*offloaded\s+(?P<off>\d+)\s*/\s*(?P<total>\d+)\s+"
    r"layers to GPU\s*$",
    re.IGNORECASE,
)

_PLACEMENT_STATES = frozenset(
    {
        "full_accelerator",
        "hybrid_accelerator_cpu",
        "cpu_only",
        "unknown",
        "unavailable",
    }
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


def _finite_non_negative(value: float) -> bool:
    return math.isfinite(value) and value >= 0


def _ms_to_seconds(raw: str) -> float | None:
    try:
        milliseconds = float(raw)
    except ValueError:
        return None
    if not _finite_non_negative(milliseconds):
        return None
    return milliseconds / 1000.0


def _int_count(raw: str) -> int | None:
    try:
        value = int(raw)
    except ValueError:
        return None
    if value < 0:
        return None
    return value


def _tps(raw: str) -> float | None:
    try:
        value = float(raw)
    except ValueError:
        return None
    if not math.isfinite(value) or value < 0:
        return None
    return value


def _consistent(values: list[Any]) -> Any | None:
    if not values:
        return None
    first = values[0]
    if any(item != first for item in values[1:]):
        return None
    return first


def parse_llama_cpp_diagnostics(text: str) -> dict[str, Any]:
    """Parse llama.cpp-owned diagnostic lines only.

    Unprefixed model text is ignored. Conflicting duplicate values leave the
    field absent rather than picking one. Layer N/N is preserved as counts but
    does not prove ``full_accelerator``.
    """
    load_times: list[float] = []
    prompt_times: list[float] = []
    prompt_tokens: list[int] = []
    prompt_tps: list[float] = []
    eval_times: list[float] = []
    eval_tokens: list[int] = []
    eval_tps: list[float] = []
    total_times: list[float] = []
    offloads: list[tuple[int, int]] = []
    timing_source: str | None = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        lower = line.lower()
        if any(lower.startswith(prefix) for prefix in _PERF_PREFIXES):
            prefix = (
                "llama_perf_context_print"
                if lower.startswith("llama_perf_context_print:")
                else "llama_print_timings"
            )
            load_match = _LOAD_TIME_RE.match(line)
            if load_match:
                seconds = _ms_to_seconds(load_match.group("ms"))
                if seconds is not None:
                    load_times.append(seconds)
                    timing_source = prefix
                continue
            prompt_match = _PROMPT_EVAL_DIAG_RE.match(line)
            if prompt_match:
                seconds = _ms_to_seconds(prompt_match.group("ms"))
                tokens = _int_count(prompt_match.group("tokens"))
                tps = _tps(prompt_match.group("tps"))
                if seconds is not None and tokens is not None and tps is not None:
                    prompt_times.append(seconds)
                    prompt_tokens.append(tokens)
                    prompt_tps.append(tps)
                    timing_source = prefix
                continue
            eval_match = _EVAL_DIAG_RE.match(line)
            if eval_match:
                seconds = _ms_to_seconds(eval_match.group("ms"))
                tokens = _int_count(eval_match.group("tokens"))
                tps = _tps(eval_match.group("tps"))
                if seconds is not None and tokens is not None and tps is not None:
                    eval_times.append(seconds)
                    eval_tokens.append(tokens)
                    eval_tps.append(tps)
                    timing_source = prefix
                continue
            total_match = _TOTAL_TIME_RE.match(line)
            if total_match:
                seconds = _ms_to_seconds(total_match.group("ms"))
                if seconds is not None:
                    total_times.append(seconds)
                    timing_source = prefix
                continue
        if any(lower.startswith(prefix) for prefix in _PLACEMENT_PREFIXES):
            offload_match = _OFFLOAD_RE.match(line)
            if offload_match:
                offloaded = _int_count(offload_match.group("off"))
                total = _int_count(offload_match.group("total"))
                if offloaded is not None and total is not None:
                    offloads.append((offloaded, total))

    load_time = _consistent(load_times)
    prompt_eval_time = _consistent(prompt_times)
    prompt_eval_token_count = _consistent(prompt_tokens)
    prompt_eval_tps = _consistent(prompt_tps)
    eval_time = _consistent(eval_times)
    eval_token_count = _consistent(eval_tokens)
    generation_tps = _consistent(eval_tps)
    total_time = _consistent(total_times)
    offload = _consistent(offloads)

    observed, offloaded_layers, total_layers, placement_source = (
        classify_llama_cpp_placement(offload)
    )
    has_timing = any(
        value is not None
        for value in (
            load_time,
            prompt_eval_time,
            prompt_eval_token_count,
            prompt_eval_tps,
            eval_time,
            eval_token_count,
            generation_tps,
            total_time,
        )
    )
    return {
        "llama_cpp_timing": {
            "load_time_seconds": load_time,
            "prompt_eval_time_seconds": prompt_eval_time,
            "prompt_eval_token_count": prompt_eval_token_count,
            "prompt_eval_tps": prompt_eval_tps,
            "eval_time_seconds": eval_time,
            "eval_token_count": eval_token_count,
            "generation_tps": generation_tps,
            "total_time_seconds": total_time,
            "source": timing_source if has_timing else None,
        },
        "llama_cpp_placement": {
            "offloaded_layers": offloaded_layers,
            "total_layers": total_layers,
            "observed": observed,
            "source": placement_source,
        },
    }


def classify_llama_cpp_placement(
    offload: tuple[int, int] | None,
) -> tuple[str, int | None, int | None, str | None]:
    if offload is None:
        return "unavailable", None, None, None
    offloaded, total = offload
    if total <= 0 or offloaded > total:
        return "unknown", offloaded, total, "llm_load_tensors"
    if offloaded == 0:
        return "cpu_only", offloaded, total, "llm_load_tensors"
    if offloaded < total:
        return "hybrid_accelerator_cpu", offloaded, total, "llm_load_tensors"
    # N/N transformer-layer counts do not prove embeddings/output/other
    # execution is accelerator-resident.
    return "unknown", offloaded, total, "llm_load_tensors"


def placement_states() -> frozenset[str]:
    return _PLACEMENT_STATES
