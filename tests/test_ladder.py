from pathlib import Path

import pytest

from llmgauge.core.ladder import (
    build_ladder_report,
    build_ladder_summary,
    parse_ctx_ladder,
    write_ladder_report,
    write_ladder_summary,
)


def test_parse_ctx_ladder_default() -> None:
    assert parse_ctx_ladder(None) == [8192, 16384, 32768]


def test_parse_ctx_ladder_explicit() -> None:
    assert parse_ctx_ladder("8192,16384,32768,65536") == [
        8192,
        16384,
        32768,
        65536,
    ]


def test_parse_ctx_ladder_rejects_unsorted_values() -> None:
    with pytest.raises(ValueError, match="sorted"):
        parse_ctx_ladder("16384,8192")


def test_parse_ctx_ladder_rejects_duplicates() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        parse_ctx_ladder("8192,8192")


def test_parse_ctx_ladder_rejects_over_64k_by_default() -> None:
    with pytest.raises(ValueError, match="opt-in"):
        parse_ctx_ladder("8192,131072")


def test_parse_ctx_ladder_allows_extreme_context_with_opt_in() -> None:
    assert parse_ctx_ladder(
        "8192,65536,131072",
        allow_extreme_context=True,
    ) == [8192, 65536, 131072]


def test_parse_ctx_ladder_rejects_over_extreme_max() -> None:
    with pytest.raises(ValueError, match="exceeds"):
        parse_ctx_ladder(
            "8192,524288",
            allow_extreme_context=True,
        )


def test_build_ladder_summary_counts_child_runs() -> None:
    summary = build_ladder_summary(
        ladder_id="ladder-test",
        suite_id="core-v1",
        include="honesty",
        only=None,
        model_id="test-model",
        contexts=[8192, 16384],
        child_runs=[
            {
                "ctx_size": 8192,
                "status": "completed",
                "result_dir": "results/ladder-test/ctx-8192",
                "completed": 1,
                "failed": 0,
                "error": None,
            },
            {
                "ctx_size": 16384,
                "status": "failed",
                "result_dir": "results/ladder-test/ctx-16384",
                "completed": None,
                "failed": None,
                "error": "example failure",
            },
        ],
    )

    assert summary["summary"]["completed"] == 1
    assert summary["summary"]["failed"] == 1
    assert summary["summary"]["total"] == 2
    assert summary["max_context_policy"]["normal_max_context"] == 65536
    assert summary["max_context_policy"]["allow_extreme_context"] is False


def test_build_ladder_summary_records_extreme_policy() -> None:
    summary = build_ladder_summary(
        ladder_id="ladder-test",
        suite_id="core-v1",
        include="honesty",
        only=None,
        model_id="test-model",
        contexts=[8192, 131072],
        child_runs=[
            {
                "ctx_size": 8192,
                "status": "completed",
                "result_dir": "ctx-8192",
                "completed": 1,
                "failed": 0,
                "error": None,
            },
            {
                "ctx_size": 131072,
                "status": "completed",
                "result_dir": "ctx-131072",
                "completed": 1,
                "failed": 0,
                "error": None,
            },
        ],
        allow_extreme_context=True,
    )

    assert summary["max_context_policy"]["allow_extreme_context"] is True
    assert summary["max_context_policy"]["has_extreme_context"] is True


def test_build_ladder_report() -> None:
    summary = build_ladder_summary(
        ladder_id="ladder-test",
        suite_id="core-v1",
        include="honesty",
        only=None,
        model_id="test-model",
        contexts=[8192],
        child_runs=[
            {
                "ctx_size": 8192,
                "status": "completed",
                "result_dir": "results/ladder-test/ctx-8192",
                "completed": 1,
                "failed": 0,
                "error": None,
            }
        ],
    )

    report = build_ladder_report(summary)

    assert "# LLMGauge Context Ladder: ladder-test" in report
    assert (
        "| 8192 | completed | results/ladder-test/ctx-8192 | 1 | 0 | None |" in report
    )
    assert "Default context ladder is 8192, 16384, 32768" in report
    assert "Contexts above 65536 require explicit extreme-context opt-in" in report


def test_write_ladder_artifacts(tmp_path: Path) -> None:
    summary = build_ladder_summary(
        ladder_id="ladder-test",
        suite_id="core-v1",
        include="honesty",
        only=None,
        model_id="test-model",
        contexts=[8192],
        child_runs=[
            {
                "ctx_size": 8192,
                "status": "completed",
                "result_dir": "ctx-8192",
                "completed": 1,
                "failed": 0,
                "error": None,
            }
        ],
    )

    summary_path = write_ladder_summary(tmp_path, summary)
    report_path = write_ladder_report(tmp_path, summary)

    assert summary_path.exists()
    assert report_path.exists()
