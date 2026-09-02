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

# llama.cpp stderr lines may carry a `M.MM.mmm.uuu L ` timestamp/level prefix
# (default-on at verbosity >= 1 in the qualified build 10449). Diagnostic
# grammars tolerate exactly that prefix and nothing looser.
_LOG_PREFIX = r"(?:\d+(?:\.\d+){3}\s+[IWED]\s+)?"

SLOT_TIMING_SOURCE = "slot_print_timing"
CURRENT_PLACEMENT_SOURCE = "load_tensors"
HISTORICAL_PLACEMENT_SOURCE = "llm_load_tensors"

# Request-final slot block fields (server_slot::print_timings). The
# prompt/eval/total lines must share one `task N` identity; progress lines
# from print_timings_pp/print_timings_tg carry different field text and are
# rejected by these grammars.
_SLOT_PROMPT_RE = re.compile(
    r"^\s*" + _LOG_PREFIX + r"slot\s+print_timing:\s*"
    r"id\s+(?P<slot>\d+)\s*\|\s*task\s+(?P<task>\d+)\s*\|\s*"
    r"prompt eval time\s*=\s*(?P<ms>[0-9.]+)\s*ms\s*/\s*(?P<tokens>\d+)\s+tokens"
    r"\s*\(\s*(?P<mspt>[0-9.]+)\s+ms per token,\s*(?P<tps>[0-9.]+)\s+"
    r"tokens per second\)\s*$",
    re.IGNORECASE,
)
_SLOT_EVAL_RE = re.compile(
    r"^\s*" + _LOG_PREFIX + r"slot\s+print_timing:\s*"
    r"id\s+(?P<slot>\d+)\s*\|\s*task\s+(?P<task>\d+)\s*\|\s*"
    r"eval time\s*=\s*(?P<ms>[0-9.]+)\s*ms\s*/\s*(?P<tokens>\d+)\s+tokens"
    r"\s*\(\s*(?P<mspt>[0-9.]+)\s+ms per token,\s*(?P<tps>[0-9.]+)\s+"
    r"tokens per second\)\s*$",
    re.IGNORECASE,
)
_SLOT_TOTAL_RE = re.compile(
    r"^\s*" + _LOG_PREFIX + r"slot\s+print_timing:\s*"
    r"id\s+(?P<slot>\d+)\s*\|\s*task\s+(?P<task>\d+)\s*\|\s*"
    r"total time\s*=\s*(?P<ms>[0-9.]+)\s*ms\s*/\s*(?P<tokens>\d+)\s+tokens\s*$",
    re.IGNORECASE,
)
_SLOT_GRAPHS_RE = re.compile(
    r"^\s*" + _LOG_PREFIX + r"slot\s+print_timing:\s*"
    r"id\s+(?P<slot>\d+)\s*\|\s*task\s+(?P<task>\d+)\s*\|\s*"
    r"graphs reused\s*=\s*(?P<n>\d+)\s*$",
    re.IGNORECASE,
)
_OFFLOAD_RE = re.compile(
    r"^\s*llm_load_tensors:\s*offloaded\s+(?P<off>\d+)\s*/\s*(?P<total>\d+)\s+"
    r"layers to GPU\s*$",
    re.IGNORECASE,
)
# Current renamed prefix (qualified build 10449): same producer, emitted at
# verbosity >= 4 with a timestamp/level prefix. Admitted only under exact
# runtime qualification, and only from stderr.
_OFFLOAD_CURRENT_RE = re.compile(
    r"^\s*" + _LOG_PREFIX + r"load_tensors:\s*offloaded\s+"
    r"(?P<off>\d+)\s*/\s*(?P<total>\d+)\s+layers to GPU\s*$",
    re.IGNORECASE,
)

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


def parse_llama_cpp_diagnostics(
    text: str,
    *,
    stderr: str | None = None,
    placement_admitted: bool = False,
    slot_timing_admitted: bool = False,
) -> dict[str, Any]:
    """Parse llama.cpp-owned diagnostic lines only.

    Unprefixed model text is ignored. Conflicting duplicate values leave the
    field absent rather than picking one. Layer N/N is preserved as counts but
    does not prove ``full_accelerator``.

    Historical ``llm_load_tensors:`` / ``llama_perf`` behavior is unchanged.
    The current ``load_tensors:`` placement prefix is admitted only when
    ``placement_admitted`` proves a lineage-qualified runtime, and the
    request-final ``slot print_timing:`` block only when
    ``slot_timing_admitted`` proves a timing-qualified lineage identity; the
    two flags are independent (placement-only identities exist). Both are
    parsed from ``stderr`` only (never stdout) so model output cannot forge
    current-prefix evidence. When ``stderr`` is omitted, ``text`` is used for
    the current scan as well.
    """
    load_times: list[float] = []
    prompt_times: list[float] = []
    prompt_tokens: list[int] = []
    prompt_tps: list[float] = []
    eval_times: list[float] = []
    eval_tokens: list[int] = []
    eval_tps: list[float] = []
    total_times: list[float] = []
    offloads: list[tuple[int, int, str]] = []
    offload_lines: list[str] = []
    timing_lines: list[str] = []
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
                    timing_lines.append(line)
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
                    timing_lines.append(line)
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
                    timing_lines.append(line)
                continue
            total_match = _TOTAL_TIME_RE.match(line)
            if total_match:
                seconds = _ms_to_seconds(total_match.group("ms"))
                if seconds is not None:
                    total_times.append(seconds)
                    timing_source = prefix
                    timing_lines.append(line)
                continue
        offload_match = _OFFLOAD_RE.match(line)
        if offload_match:
            offloaded = _int_count(offload_match.group("off"))
            total = _int_count(offload_match.group("total"))
            if offloaded is not None and total is not None:
                offloads.append((offloaded, total, HISTORICAL_PLACEMENT_SOURCE))
                offload_lines.append(line)

    if placement_admitted:
        current_text = text if stderr is None else stderr
        for raw_line in current_text.splitlines():
            line = raw_line.strip()
            offload_match = _OFFLOAD_CURRENT_RE.match(line)
            if offload_match:
                offloaded = _int_count(offload_match.group("off"))
                total = _int_count(offload_match.group("total"))
                if offloaded is not None and total is not None:
                    offloads.append((offloaded, total, CURRENT_PLACEMENT_SOURCE))
                    offload_lines.append(line)

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
        classify_llama_cpp_placement(
            (offload[0], offload[1]) if offload is not None else None,
            offload[2] if offload is not None else None,
        )
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
    parsed: dict[str, Any] = {
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
            "raw_lines": timing_lines,
        },
        "llama_cpp_placement": {
            "offloaded_layers": offloaded_layers,
            "total_layers": total_layers,
            "observed": observed,
            "source": placement_source,
            "raw_lines": offload_lines,
        },
    }
    if slot_timing_admitted:
        parsed["slot_print_timing"] = parse_slot_print_timing(
            text if stderr is None else stderr
        )
    return parsed


def parse_slot_print_timing(text: str) -> dict[str, Any]:
    """Parse the request-final ``slot print_timing:`` block only.

    A complete block is one (slot, task) group carrying all four final field
    lines (prompt eval / eval / total / graphs reused) with consistent values.
    Progress lines from ``print_timings_pp`` / ``print_timings_tg`` share the
    truncated prefix but a different field grammar and are never candidates.
    Zero candidates is unavailable; more than one candidate is ambiguous and
    also unavailable (no last-match-wins policy). Rejected fields
    (``load_time_seconds``, ``total_time_seconds``, ``graphs_reused``) stay
    null; the raw displayed line values are preserved for source-aware
    validator recomputation.
    """
    groups: dict[tuple[str, str], dict[str, dict[str, Any]]] = {}
    block_lines: dict[tuple[str, str], dict[str, str]] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        for name, pattern in (
            ("prompt_eval", _SLOT_PROMPT_RE),
            ("eval", _SLOT_EVAL_RE),
            ("total", _SLOT_TOTAL_RE),
            ("graphs", _SLOT_GRAPHS_RE),
        ):
            match = pattern.match(line)
            if match is None:
                continue
            key = (match.group("slot"), match.group("task"))
            group = groups.setdefault(key, {})
            if name in group and group[name] != match.groupdict():
                group[name] = {"_conflict": True}
            else:
                group.setdefault(name, match.groupdict())
                block_lines.setdefault(key, {})[name] = line
            break

    candidates: list[tuple[str, str, dict[str, dict[str, Any]]]] = []
    conflicted = False
    for key, group in groups.items():
        if any(item.get("_conflict") for item in group.values()):
            conflicted = True
            continue
        if all(name in group for name in ("prompt_eval", "eval", "total", "graphs")):
            candidates.append((key[0], key[1], group))

    unavailable: dict[str, Any] = {
        "source": SLOT_TIMING_SOURCE,
        "availability": "unavailable",
        "prompt_eval_time_seconds": None,
        "prompt_eval_token_count": None,
        "prompt_eval_tps": None,
        "eval_time_seconds": None,
        "eval_token_count": None,
        "generation_tps": None,
        "load_time_seconds": None,
        "total_time_seconds": None,
        "graphs_reused": None,
        "raw": None,
    }
    if conflicted or len(candidates) > 1:
        unavailable["reason"] = "ambiguous_final_blocks"
        return unavailable
    if not candidates:
        return unavailable

    slot, task, group = candidates[0]
    prompt = group["prompt_eval"]
    gen = group["eval"]
    total = group["total"]
    graphs = group["graphs"]
    prompt_ms = _ms_to_seconds(prompt["ms"])
    prompt_tokens = _int_count(prompt["tokens"])
    prompt_tps_value = _tps(prompt["tps"])
    eval_ms = _ms_to_seconds(gen["ms"])
    eval_tokens = _int_count(gen["tokens"])
    eval_tps_value = _tps(gen["tps"])
    if None in (
        prompt_ms,
        prompt_tokens,
        prompt_tps_value,
        eval_ms,
        eval_tokens,
        eval_tps_value,
    ):
        unavailable["reason"] = "malformed_final_block"
        return unavailable
    return {
        "source": SLOT_TIMING_SOURCE,
        "availability": "available",
        "prompt_eval_time_seconds": prompt_ms,
        "prompt_eval_token_count": prompt_tokens,
        "prompt_eval_tps": prompt_tps_value,
        "eval_time_seconds": eval_ms,
        # n_gen as displayed by the source; the rate denominator below is
        # n_gen - 1 decode steps. The count is never falsified to n_gen - 1.
        "eval_token_count": eval_tokens,
        "generation_tps": eval_tps_value,
        # Rejected for this source: boundary/ownership semantics differ.
        "load_time_seconds": None,
        "total_time_seconds": None,
        "graphs_reused": None,
        "raw": {
            "slot": _int_count(slot),
            "task": _int_count(task),
            "prompt_eval_ms": _tps(prompt["ms"]),
            "prompt_eval_tokens": prompt_tokens,
            "prompt_eval_tps": prompt_tps_value,
            "eval_ms": _tps(gen["ms"]),
            "eval_tokens": eval_tokens,
            "eval_tps": eval_tps_value,
            "total_ms": _tps(total["ms"]),
            "total_tokens": _int_count(total["tokens"]),
            "graphs_reused": _int_count(graphs["n"]),
            "generation_rate_denominator": "eval_tokens_minus_one",
            "lines": [
                block_lines[(slot, task)][name]
                for name in ("prompt_eval", "eval", "total", "graphs")
            ],
        },
    }


_RETAIN_LEVEL_RE = re.compile(r"^\s*(?:\d+(?:\.\d+){3}\s+)?[WE]\s", re.IGNORECASE)
_RETAIN_VERBOSITY_RE = re.compile(
    r"^\s*(?:\d+(?:\.\d+){3}\s+[IWED]\s+)?(?:cmn\s+)?(?:common_param:\s*)?"
    r"common_params_print_info:\s*verbosity\s*=\s*\d+\b.*$",
    re.IGNORECASE,
)
_PERF_LINE_RE = re.compile(
    r"^\s*(?:\d+(?:\.\d+){3}\s+[IWED]\s+)?(?:llama_perf_context_print"
    r"|llama_print_timings):",
    re.IGNORECASE,
)


def retain_native_diagnostics_stderr(stderr: str) -> str:
    """Selectively retain stderr for a successful verbosity-raised run.

    Verbosity 4 emits substantial unrelated stderr (buffer sizes, absolute
    model paths, implementation detail). Only these lines are retained as
    ordinary success evidence:

    - warning/error-level lines (failure diagnostics stay diagnosable);
    - the effective-verbosity confirmation line;
    - lines matching the admitted diagnostic grammars (offload placement,
      request-final slot timing block, historical llama_perf footer).

    Everything else (verbosity-only info/trace noise) is not persisted.
    """
    kept: list[str] = []
    for raw_line in stderr.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if _RETAIN_LEVEL_RE.match(raw_line):
            kept.append(line)
            continue
        if _RETAIN_VERBOSITY_RE.match(line) or _PERF_LINE_RE.match(line):
            kept.append(line)
            continue
        if _OFFLOAD_RE.match(line) or _OFFLOAD_CURRENT_RE.match(line):
            kept.append(line)
            continue
        for pattern in (
            _SLOT_PROMPT_RE,
            _SLOT_EVAL_RE,
            _SLOT_TOTAL_RE,
            _SLOT_GRAPHS_RE,
        ):
            if pattern.match(line):
                kept.append(line)
                break
    return "\n".join(kept) + "\n" if kept else ""


def classify_llama_cpp_placement(
    offload: tuple[int, int] | None,
    placement_prefix: str | None = None,
) -> tuple[str, int | None, int | None, str | None]:
    source = placement_prefix or HISTORICAL_PLACEMENT_SOURCE
    if offload is None:
        return "unavailable", None, None, None
    offloaded, total = offload
    if total <= 0 or offloaded > total:
        return "unknown", offloaded, total, source
    if offloaded == 0:
        return "cpu_only", offloaded, total, source
    if offloaded < total:
        return "hybrid_accelerator_cpu", offloaded, total, source
    # N/N transformer-layer counts do not prove embeddings/output/other
    # execution is accelerator-resident.
    return "unknown", offloaded, total, source


def placement_states() -> frozenset[str]:
    return _PLACEMENT_STATES
