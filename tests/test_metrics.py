import pytest

from llmgauge.core.metrics import parse_llama_cpp_diagnostics, parse_llama_metrics


def test_parse_llama_metrics_full() -> None:
    text = """
llama_perf_context_print:        load time =     123.45 ms
llama_perf_context_print: prompt eval time =     456.78 ms /   100 tokens (218.92 tokens per second)
llama_perf_context_print:        eval time =     789.01 ms /    50 runs   (63.37 tokens per second)
"""

    metrics = parse_llama_metrics(text)

    assert metrics["prompt_eval_tokens"] == 100
    assert metrics["prompt_eval_tps"] == 218.92
    assert metrics["generation_tokens"] == 50
    assert metrics["generation_tps"] == 63.37


def test_parse_llama_metrics_compact_summary() -> None:
    text = "[ Prompt: 1568.9 t/s | Generation: 73.0 t/s ]"

    metrics = parse_llama_metrics(text)

    assert metrics["prompt_eval_tokens"] is None
    assert metrics["prompt_eval_tps"] == 1568.9
    assert metrics["generation_tokens"] is None
    assert metrics["generation_tps"] == 73.0


def test_parse_llama_metrics_missing() -> None:
    metrics = parse_llama_metrics("no metrics here")

    assert metrics["prompt_eval_tokens"] is None
    assert metrics["prompt_eval_tps"] is None
    assert metrics["generation_tokens"] is None
    assert metrics["generation_tps"] is None


_FOOTER = """
llm_load_tensors: offloaded 41/41 layers to GPU
llama_perf_context_print:        load time =     123.45 ms
llama_perf_context_print: prompt eval time =     456.78 ms /   100 tokens (218.92 tokens per second)
llama_perf_context_print:        eval time =     789.01 ms /    50 runs   (63.37 tokens per second)
llama_perf_context_print:       total time =    1345.67 ms /   150 tokens
"""


def test_parse_llama_cpp_diagnostics_complete_footer() -> None:
    parsed = parse_llama_cpp_diagnostics(_FOOTER)
    timing = parsed["llama_cpp_timing"]
    placement = parsed["llama_cpp_placement"]
    assert timing["load_time_seconds"] == pytest.approx(0.12345)
    assert timing["prompt_eval_time_seconds"] == pytest.approx(0.45678)
    assert timing["prompt_eval_token_count"] == 100
    assert timing["prompt_eval_tps"] == 218.92
    assert timing["eval_time_seconds"] == pytest.approx(0.78901)
    assert timing["eval_token_count"] == 50
    assert timing["generation_tps"] == 63.37
    assert timing["total_time_seconds"] == pytest.approx(1.34567)
    assert timing["source"] == "llama_perf_context_print"
    assert placement["offloaded_layers"] == 41
    assert placement["total_layers"] == 41
    assert placement["observed"] == "unknown"
    assert placement["source"] == "llm_load_tensors"


def test_parse_llama_cpp_diagnostics_ignores_unprefixed_lookalike() -> None:
    text = (
        "prompt eval time = 456.78 ms / 100 tokens (218.92 tokens per second)\n"
        "eval time = 789.01 ms / 50 runs (63.37 tokens per second)\n"
        "load time = 123.45 ms\n"
        "offloaded 41/41 layers to GPU\n"
    )
    parsed = parse_llama_cpp_diagnostics(text)
    timing = parsed["llama_cpp_timing"]
    assert timing["load_time_seconds"] is None
    assert timing["prompt_eval_tps"] is None
    assert timing["generation_tps"] is None
    assert parsed["llama_cpp_placement"]["observed"] == "unavailable"


def test_parse_llama_cpp_diagnostics_hybrid_and_cpu_placement() -> None:
    hybrid = parse_llama_cpp_diagnostics(
        "llm_load_tensors: offloaded 20/41 layers to GPU\n"
    )
    assert hybrid["llama_cpp_placement"]["observed"] == "hybrid_accelerator_cpu"
    cpu = parse_llama_cpp_diagnostics(
        "llm_load_tensors: offloaded 0/41 layers to GPU\n"
    )
    assert cpu["llama_cpp_placement"]["observed"] == "cpu_only"


def test_parse_llama_cpp_diagnostics_conflicting_timing_is_absent() -> None:
    text = """
llama_perf_context_print:        load time =     100.00 ms
llama_perf_context_print:        load time =     200.00 ms
"""
    parsed = parse_llama_cpp_diagnostics(text)
    assert parsed["llama_cpp_timing"]["load_time_seconds"] is None


def test_parse_llama_cpp_diagnostics_malformed_numeric_ignored() -> None:
    text = "llama_perf_context_print:        load time =     not-a-number ms\n"
    parsed = parse_llama_cpp_diagnostics(text)
    assert parsed["llama_cpp_timing"]["load_time_seconds"] is None


def test_parse_llama_cpp_diagnostics_zero_token_prompt_preserved() -> None:
    text = (
        "llama_perf_context_print: prompt eval time =     0.00 ms /     0 tokens "
        "(0.00 tokens per second)\n"
    )
    parsed = parse_llama_cpp_diagnostics(text)
    assert parsed["llama_cpp_timing"]["prompt_eval_token_count"] == 0
    assert parsed["llama_cpp_timing"]["prompt_eval_tps"] == 0.0


def test_parse_llama_cpp_diagnostics_conflicting_offload_unknown() -> None:
    text = """
llm_load_tensors: offloaded 20/41 layers to GPU
llm_load_tensors: offloaded 41/41 layers to GPU
"""
    parsed = parse_llama_cpp_diagnostics(text)
    assert parsed["llama_cpp_placement"]["observed"] == "unavailable"
    assert parsed["llama_cpp_placement"]["offloaded_layers"] is None
