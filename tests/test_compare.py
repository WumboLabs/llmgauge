from llmgauge.core.compare import build_compare_report


def _result(run_id: str, model_id: str, score: float | None, gen_tps: float) -> dict:
    return {
        "run": {
            "run_id": run_id,
            "status": "completed",
        },
        "model": {
            "model_id": model_id,
        },
        "suite": {
            "suite_id": "core-v1",
        },
        "runtime": {
            "backend": "llama.cpp",
            "ctx_size": 8192,
            "max_tokens": 600,
            "temperature": 0.2,
            "top_p": 0.95,
            "batch_size": 256,
            "ubatch_size": 64,
            "gpu_layers": 999,
        },
        "summary": {
            "completed": 1,
            "failed": 0,
            "scored_prompt_count": 1 if score is not None else None,
            "manual_score_average": score,
            "failure_labels": {},
            "good_labels": {
                "good_verification": 1,
            },
        },
        "results": [
            {
                "prompt_id": "honesty-unknown-tool",
                "metrics": {
                    "prompt_eval_tps": 1000.0,
                    "generation_tps": gen_tps,
                },
                "score": {
                    "prompt_average": score,
                }
                if score is not None
                else None,
            }
        ],
    }


def test_build_compare_report() -> None:
    report = build_compare_report(
        [
            _result("run-a", "model-a", 4.0, 50.0),
            _result("run-b", "model-b", 3.5, 70.0),
        ]
    )

    assert "# LLMGauge Comparison Report" in report
    assert "This report compares completed local evaluation runs" in report
    assert "| run-a | model-a | core-v1 | completed | 1 | 0 | 1 | 4.0 |" in report
    assert "| honesty-unknown-tool | 4.0 | 3.5 |" in report
    assert "| honesty-unknown-tool | 50.0 | 70.0 |" in report
    assert "good_verification: 1" in report
