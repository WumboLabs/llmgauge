from llmgauge.core.metrics import parse_llama_metrics


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
