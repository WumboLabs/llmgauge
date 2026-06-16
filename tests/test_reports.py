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
                "stderr_log_path": "logs/one.stderr.log",
                "exit_status": 0,
                "metrics": {
                    "prompt_eval_tps": 100.0,
                    "generation_tps": 50.0,
                },
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
    assert "| one | honesty | completed | 100.0 | 50.0 | 0 |" in report
    assert "| two | docker | completed | None | None | 0 |" in report
