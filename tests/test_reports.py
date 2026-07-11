from llmgauge.core.reports import build_markdown_report


def _result_with_metrics(metrics: dict[str, object]) -> dict[str, object]:
    return {
        "run": {
            "run_id": "metrics-run",
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
        },
        "results": [
            {
                "prompt_id": "metrics",
                "category": "speed",
                "status": "completed",
                "raw_prompt_path": "raw/metrics.prompt.md",
                "raw_output_path": "raw/metrics.output.txt",
                "stderr_log_path": "logs/metrics.stderr.log",
                "exit_status": 0,
                "metrics": metrics,
            },
        ],
    }


def _prompt_results_row(report: str, prompt_id: str = "metrics") -> str:
    for line in report.splitlines():
        if line.startswith(f"| {prompt_id} |"):
            return line
    raise AssertionError(f"missing prompt results row for {prompt_id}")


def test_build_markdown_report_handles_missing_prompt_eval_tps() -> None:
    report = build_markdown_report(
        _result_with_metrics(
            {
                "generation_tps": 50.0,
            }
        )
    )

    assert _prompt_results_row(report) == (
        "| metrics | speed | completed | None | - | 50.0 | - | - | 0 |"
    )


def test_build_markdown_report_handles_missing_generation_tps() -> None:
    report = build_markdown_report(
        _result_with_metrics(
            {
                "prompt_eval_tps": 100.0,
            }
        )
    )

    assert _prompt_results_row(report) == (
        "| metrics | speed | completed | None | 100.0 | - | - | - | 0 |"
    )


def test_build_markdown_report_handles_missing_throughput_metrics() -> None:
    report = build_markdown_report(_result_with_metrics({}))

    assert _prompt_results_row(report) == (
        "| metrics | speed | completed | None | - | - | - | - | 0 |"
    )


def test_build_markdown_report_renders_none_prompt_eval_tps_as_unavailable() -> None:
    report = build_markdown_report(
        _result_with_metrics(
            {
                "prompt_eval_tps": None,
                "generation_tps": 50.0,
            }
        )
    )

    assert _prompt_results_row(report) == (
        "| metrics | speed | completed | None | - | 50.0 | - | - | 0 |"
    )


def test_build_markdown_report_renders_none_generation_tps_as_unavailable() -> None:
    report = build_markdown_report(
        _result_with_metrics(
            {
                "prompt_eval_tps": 100.0,
                "generation_tps": None,
            }
        )
    )

    assert _prompt_results_row(report) == (
        "| metrics | speed | completed | None | 100.0 | - | - | - | 0 |"
    )


def test_build_markdown_report_preserves_present_throughput_formatting() -> None:
    report = build_markdown_report(
        _result_with_metrics(
            {
                "prompt_eval_tps": 100.0,
                "generation_tps": 50.0,
            }
        )
    )

    assert _prompt_results_row(report) == (
        "| metrics | speed | completed | None | 100.0 | 50.0 | - | - | 0 |"
    )


def test_build_markdown_report_renders_zero_throughput_as_zero() -> None:
    report = build_markdown_report(
        _result_with_metrics(
            {
                "prompt_eval_tps": 0,
                "generation_tps": 0.0,
            }
        )
    )

    assert _prompt_results_row(report) == (
        "| metrics | speed | completed | None | 0 | 0.0 | - | - | 0 |"
    )


def test_build_markdown_report_handles_malformed_throughput_values() -> None:
    report = build_markdown_report(
        _result_with_metrics(
            {
                "prompt_eval_tps": "fast",
                "generation_tps": {"value": 50.0},
            }
        )
    )

    assert _prompt_results_row(report) == (
        "| metrics | speed | completed | None | - | - | - | - | 0 |"
    )
    assert "fast" not in report
    assert "{'value': 50.0}" not in report


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
            "flash_attn": "on",
            "runtime_label": "daily-tuned",
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
        "run_fingerprint": {
            "schema_version": "llmgauge.run_fingerprint.v0",
            "algorithm": "sha256",
            "value": "sha256:" + "1" * 64,
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
    assert "not a universal ranking, model recommendation, or production-readiness proof" in report
    assert "## Report Scope" in report
    assert "Use this report for:" in report
    assert "Do not use this report for:" in report
    assert "## Evidence Summary" in report
    assert "- Run ID: test-run" in report
    assert "- Peak VRAM MiB: 7535" in report
    assert "- Run evidence fingerprint: `sha256:" + "1" * 64 + "`" in report
    assert "canonical private source evidence" in report
    assert "## Publish Readiness Notes" in report
    assert "- Scoring status: unscored" in report
    assert "## Test Configuration" in report
    assert "- Flash attention: on" in report
    assert "- Runtime label: daily-tuned" in report
    assert (
        "| Prompt | Category | Status | Score avg (0-5) | Prompt tok/s | Generation tok/s | Peak VRAM MiB | VRAM Headroom MiB | Exit |"
        in report
    )
    assert (
        "| one | honesty | completed | None | 100.0 | 50.0 | 7535 | 4692 | 0 |"
        in report
    )
    assert "| two | docker | completed | None | - | - | - | - | 0 |" in report
    assert "## Audit Checklist" in report
    assert "validate-result" in report
    assert "## Prompt Artifact Audit" in report
    assert "Raw output (source audit evidence)" in report
    assert "Cleaned output (derived review aid)" in report
    assert "| one | completed | `raw/one.output.txt` | `cleaned/one.output.txt` |" in report
    assert "| two | completed | `raw/two.output.txt` | not available |" in report
    assert "- Score audit: unscored" in report
    assert "- VRAM samples (operational telemetry): `vram/one.samples.json`" in report
    assert "## Artifact integration" in report
    assert "single-run human review artifact" in report


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

    assert "## Evidence Summary" in report
    assert "- Manual score average: 3.6 / 5" in report
    assert "## Publish Readiness Notes" in report
    assert "- Scoring status: scored" in report
    assert "## Score Summary" in report
    assert "Manual scores are review metadata" in report
    assert "- Manual score average: 3.6 / 5" in report
    assert "## Scored Interpretation" in report
    assert "- Scoring status: scored" in report
    assert "- Verdict counts: pass: 1" in report
    assert "- Highest scored prompt: honesty-unknown-tool (3.6 / 5)" in report
    assert "- Lowest scored prompt: honesty-unknown-tool (3.6 / 5)" in report
    assert "- Most common failure labels: needs_review: 1" in report
    assert "- Most common good labels: good_verification: 1" in report
    assert (
        "- Claim boundary: scores summarize this run under the configured rubric; they are not universal model rankings or recommendations."
        in report
    )
    assert "### Scoring Provenance" in report
    assert "- Scoring modes: manual: 1" in report
    assert "- Reviewed scores: 1" in report
    assert "- Unreviewed scores: 0" in report
    assert "- Scorer IDs: None" in report
    assert (
        "| honesty-unknown-tool | honesty | completed | 3.6 | 100.0 | 50.0 | - | - | 0 |"
        in report
    )
    assert "## Prompt Artifact Audit" in report
    assert "- Score rationale: Good safety and useful answer." in report
    assert "- Good labels: good_verification" in report


def test_build_markdown_report_warns_for_unreviewed_auto_scores() -> None:
    result = {
        "run": {
            "run_id": "auto-scored-run",
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
            "manual_score_total": 2.0,
            "manual_score_max": 5.0,
            "manual_score_average": 2.0,
            "failure_labels": {},
            "good_labels": {},
        },
        "results": [
            {
                "prompt_id": "drafted",
                "category": "honesty",
                "status": "completed",
                "raw_prompt_path": "raw/drafted.prompt.md",
                "raw_output_path": "raw/drafted.output.txt",
                "stderr_log_path": "logs/drafted.stderr.log",
                "exit_status": 0,
                "metrics": {
                    "prompt_eval_tps": 100.0,
                    "generation_tps": 50.0,
                },
                "score": {
                    "prompt_average": 2.0,
                    "failure_labels": [],
                    "good_labels": [],
                    "reviewer_notes": "",
                    "score_rationale": "Draft needs review.",
                    "verdict": "needs_review",
                    "scoring_mode": "automatic_rules",
                    "scorer_id": "llmgauge-auto-rules",
                    "reviewed": False,
                },
            },
        ],
    }

    report = build_markdown_report(result)

    assert "- Scoring modes: automatic_rules: 1" in report
    assert "- Reviewed scores: 0" in report
    assert "- Unreviewed scores: 1" in report
    assert "- Scorer IDs: llmgauge-auto-rules" in report
    assert "- Needs-review verdicts: 1" in report
    assert (
        "- Warning: some applied scores are unreviewed assisted drafts. Treat them as review-required metadata."
        in report
    )
    assert "unreviewed assisted drafts" in report


def test_build_markdown_report_shows_provenance_for_nonnumeric_auto_scores() -> None:
    result = {
        "run": {
            "run_id": "nonnumeric-auto-scored-run",
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
            "manual_score_average": None,
            "failure_labels": {},
            "good_labels": {},
        },
        "results": [
            {
                "prompt_id": "drafted",
                "category": "honesty",
                "status": "completed",
                "raw_prompt_path": "raw/drafted.prompt.md",
                "raw_output_path": "raw/drafted.output.txt",
                "stderr_log_path": "logs/drafted.stderr.log",
                "exit_status": 0,
                "metrics": {
                    "prompt_eval_tps": 100.0,
                    "generation_tps": 50.0,
                },
                "score": {
                    "prompt_average": None,
                    "failure_labels": [],
                    "good_labels": [],
                    "reviewer_notes": "",
                    "score_rationale": "Draft needs review.",
                    "verdict": "needs_review",
                    "scoring_mode": "automatic_rules",
                    "scorer_id": "llmgauge-auto-rules",
                    "reviewed": False,
                },
            },
        ],
    }

    report = build_markdown_report(result)

    assert "## Publish Readiness Notes" in report
    assert "- Scoring status: review_metadata_only" in report
    assert "## Scored Interpretation" in report
    assert "- Scoring status: review_metadata_only" in report
    assert "### Scoring Provenance" in report
    assert "- Verdict counts: needs_review: 1" in report
    assert "- Highest scored prompt: None" in report
    assert "- Lowest scored prompt: None" in report
    assert "- Scoring modes: automatic_rules: 1" in report
    assert "- Reviewed scores: 0" in report
    assert "- Unreviewed scores: 1" in report
    assert "- Scorer IDs: llmgauge-auto-rules" in report
    assert (
        "- Warning: some applied scores are unreviewed assisted drafts. Treat them as review-required metadata."
        in report
    )
    assert "## Prompt Artifact Audit" in report
    assert "- Score rationale: Draft needs review." in report


def test_build_markdown_report_treats_legacy_scores_as_reviewed_manual() -> None:
    result = {
        "run": {
            "run_id": "legacy-scored-run",
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
            "manual_score_total": 4.0,
            "manual_score_max": 5.0,
            "manual_score_average": 4.0,
            "failure_labels": {},
            "good_labels": {},
        },
        "results": [
            {
                "prompt_id": "legacy",
                "category": "honesty",
                "status": "completed",
                "raw_prompt_path": "raw/legacy.prompt.md",
                "raw_output_path": "raw/legacy.output.txt",
                "stderr_log_path": "logs/legacy.stderr.log",
                "exit_status": 0,
                "metrics": {
                    "prompt_eval_tps": 100.0,
                    "generation_tps": 50.0,
                },
                "score": {
                    "prompt_average": 4.0,
                    "failure_labels": [],
                    "good_labels": [],
                    "reviewer_notes": "",
                    "score_rationale": "Legacy applied score.",
                    "verdict": "pass",
                },
            },
        ],
    }

    report = build_markdown_report(result)

    assert "- Scoring modes: manual: 1" in report
    assert "- Reviewed scores: 1" in report
    assert "- Unreviewed scores: 0" in report
    assert "unreviewed assisted drafts" not in report
