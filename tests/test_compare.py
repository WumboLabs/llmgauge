from llmgauge.core.compare import build_compare_report


def _result(
    run_id: str,
    model_id: str,
    score: float | None,
    gen_tps: float,
    *,
    peak_used_mib: int | None = None,
    peak_total_mib: int | None = None,
) -> dict:
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
            "flash_attn": "on",
        },
        "summary": {
            "completed": 1,
            "failed": 0,
            "scored_prompt_count": 1 if score is not None else None,
            "manual_score_total": score * 10 if score is not None else None,
            "manual_score_max": 50.0 if score is not None else None,
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
                "vram": {
                    "available": True,
                    "peak_used_mib": peak_used_mib,
                    "peak_total_mib": peak_total_mib,
                }
                if peak_used_mib is not None and peak_total_mib is not None
                else None,
                "score": {
                    "prompt_average": score,
                    "verdict": "pass" if score >= 4 else "mixed",
                    "failure_labels": [] if score >= 4 else ["needs_review"],
                    "dimensions": {
                        "overall_trust": 4 if score >= 4 else 3,
                    },
                }
                if score is not None
                else None,
            }
        ],
    }


def test_build_compare_report() -> None:
    report = build_compare_report(
        [
            _result(
                "run-a", "model-a", 4.0, 50.0, peak_used_mib=7535, peak_total_mib=12227
            ),
            _result(
                "run-b", "model-b", 3.5, 70.0, peak_used_mib=8200, peak_total_mib=12227
            ),
        ]
    )

    assert "# LLMGauge Comparison Report" in report
    assert "This report compares completed local evaluation runs" in report
    assert "## Interpretation Notes" in report
    assert "Manual score averages are review aids, not universal model rankings." in report
    assert (
        "| run-a | model-a | core-v1 | completed | 1 | 0 | 1 | 40.0/50.0 | 4.0 | 7535 | 4692 |"
        in report
    )
    assert "## Score Summary" in report
    assert (
        "| model-a (run-a) | 40.0/50.0 | 4.0 | 1 | 0 | 1 | honesty-unknown-tool (4) | honesty-unknown-tool (4) |"
        in report
    )
    assert "## Quality Signals" in report
    assert "| model-b (run-b) | 3.5 | mixed: 1 | 0 | 1 | honesty-unknown-tool (3.5) |" in report
    assert "## Performance Signals" in report
    assert "| Run | Backend | Context | Max tokens | Temp | Top-p | Batch | UBatch | GPU layers | Flash attention |" in report
    assert "| model-a (run-a) | llama.cpp | 8192 | 600 | 0.2 | 0.95 | 256 | 64 | 999 | on |" in report
    assert "| model-a (run-a) | 50.0 | 1000.0 | 7535 | 4692 |" in report
    assert "| honesty-unknown-tool | 4.0 | 3.5 |" in report
    assert (
        "| honesty-unknown-tool | verdict=pass; trust=4; failures=None | verdict=mixed; trust=3; failures=needs_review |"
        in report
    )
    assert "| honesty-unknown-tool | 50.0 | 70.0 |" in report
    assert "## Peak VRAM MiB" in report
    assert "| honesty-unknown-tool | 7535 | 8200 |" in report
    assert "## VRAM Headroom MiB" in report
    assert "| honesty-unknown-tool | 4692 | 4027 |" in report
    assert "good_verification: 1" in report
