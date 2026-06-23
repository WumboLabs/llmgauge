from llmgauge.core.reports import build_markdown_report


def test_build_markdown_report_multiple_prompts() -> None:
    result = {
        "run": {
            "run_id": "test-run",
            "status": "completed",
            "timestamp_utc": "2026-06-16T00:00:00+00:00",
        },
        "model": {
            "model_id": "test-model",
            "model_path_policy": "redacted",
        },
        "runtime": {
            "backend": "llama.cpp",
            "llama_cli": "/tmp/llama-cli",
            "ctx_size": 8192,
            "max_tokens": 600,
            "temperature": 0.2,
            "top_p": 0.95,
            "batch_size": 256,
            "ubatch_size": 64,
            "gpu_layers": 999,
        },
        "suite": {
            "suite_id": "core-v1",
            "suite_version": "0.1.0",
            "prompt_count": 2,
        },
        "summary": {
            "completed": 2,
            "failed": 0,
        },
        "results": [
            {
                "prompt_id": "one",
                "category": "honesty",
                "status": "completed",
                "raw_prompt_path": "raw/one.prompt.md",
                "raw_output_path": "raw/one.output.txt",
                "cleaned_output_path": "cleaned/one.output.txt",
                "stderr_log_path": "logs/one.stderr.log",
                "exit_status": 0,
                "metrics": {
                    "prompt_eval_tps": 100.0,
                    "generation_tps": 50.0,
                },
                "vram": {
                    "available": True,
                    "peak_used_mib": 7535,
                    "peak_total_mib": 12227,
                },
                "vram_samples_path": "vram/one.samples.json",
            },
            {
                "prompt_id": "two",
                "category": "docker",
                "status": "completed",
                "raw_prompt_path": "raw/two.prompt.md",
                "raw_output_path": "raw/two.output.txt",
                "stderr_log_path": "logs/two.stderr.log",
                "exit_status": 0,
                "metrics": {
                    "prompt_eval_tps": None,
                    "generation_tps": None,
                },
            },
        ],
    }

    report = build_markdown_report(result)

    assert "# LLMGauge Report: test-run" in report
    assert (
        "| Prompt | Category | Status | Score avg | Prompt tok/s | Generation tok/s | Peak VRAM MiB | VRAM Headroom MiB | Exit |"
        in report
    )
    assert (
        "| one | honesty | completed | None | 100.0 | 50.0 | 7535 | 4692 | 0 |"
        in report
    )
    assert "| two | docker | completed | None | None | None | - | - | 0 |" in report
    assert "- Cleaned output: `cleaned/one.output.txt`" in report
    assert "- Cleaned output: not available" in report
    assert "- VRAM samples: `vram/one.samples.json`" in report


def test_build_markdown_report_with_scores() -> None:
    result = {
        "run": {
            "run_id": "scored-run",
            "status": "completed",
            "timestamp_utc": "2026-06-16T00:00:00+00:00",
        },
        "model": {
            "model_id": "test-model",
            "model_path_policy": "redacted",
        },
        "runtime": {
            "backend": "llama.cpp",
            "llama_cli": "/tmp/llama-cli",
            "ctx_size": 8192,
            "max_tokens": 600,
            "temperature": 0.2,
            "top_p": 0.95,
            "batch_size": 256,
            "ubatch_size": 64,
            "gpu_layers": 999,
        },
        "suite": {
            "suite_id": "core-v1",
            "suite_version": "0.1.0",
            "prompt_count": 1,
        },
        "summary": {
            "completed": 1,
            "failed": 0,
            "scored_prompt_count": 1,
            "manual_score_total": 36.0,
            "manual_score_max": 50.0,
            "manual_score_average": 3.6,
            "failure_labels": {
                "needs_review": 1,
            },
            "good_labels": {
                "good_verification": 1,
            },
        },
        "results": [
            {
                "prompt_id": "honesty-unknown-tool",
                "category": "honesty",
                "status": "completed",
                "raw_prompt_path": "raw/honesty-unknown-tool.prompt.md",
                "raw_output_path": "raw/honesty-unknown-tool.output.txt",
                "stderr_log_path": "logs/honesty-unknown-tool.stderr.log",
                "exit_status": 0,
                "metrics": {
                    "prompt_eval_tps": 100.0,
                    "generation_tps": 50.0,
                },
                "score": {
                    "prompt_average": 3.6,
                    "failure_labels": [],
                    "good_labels": ["good_verification"],
                    "reviewer_notes": "Solid answer.",
                    "score_rationale": "Good safety and useful answer.",
                    "verdict": "pass",
                },
            },
        ],
    }

    report = build_markdown_report(result)

    assert "## Score Summary" in report
    assert "- Manual score average: 3.6 / 5" in report
    assert "## Scored Interpretation" in report
    assert "- Scoring status: scored" in report
    assert "- Verdict counts: pass: 1" in report
    assert "- Highest scored prompt: honesty-unknown-tool (3.6 / 5)" in report
    assert "- Lowest scored prompt: honesty-unknown-tool (3.6 / 5)" in report
    assert "- Most common failure labels: needs_review: 1" in report
    assert "- Most common good labels: good_verification: 1" in report
    assert (
        "- Claim boundary: manual scores are review metadata from this run, not universal model rankings or recommendations."
        in report
    )
    assert (
        "| honesty-unknown-tool | honesty | completed | 3.6 | 100.0 | 50.0 | - | - | 0 |"
        in report
    )
    assert "## Manual Review Notes" in report
    assert "- Good labels: good_verification" in report
    assert "- Rationale: Good safety and useful answer." in report
