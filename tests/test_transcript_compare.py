from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from typer.testing import CliRunner

import llmgauge.cli as cli
from llmgauge.commands import run_helpers
from llmgauge.core.compare import compare_results, load_compare_result
from llmgauge.core.multi_turn import (
    build_result_transcript_reference,
    load_transcript,
    write_transcript,
)
from llmgauge.core.public_export import export_public_run
from llmgauge.core.transcript_compare import (
    TranscriptComparisonError,
    structural_facts,
    transcript_identity,
)
from tests.test_multi_turn import (
    TASK_ID,
    _patch_identity,
    _resolved,
    _write_task,
)

runner = CliRunner()

_COMPLETED_TASK: dict[str, Any] = {"feedback": False, "max_turns": 1}
_OK = [("answer", "", 0)]
_FAILED = [("partial answer", "runtime exploded", 1)]


def _run_transcript_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    *,
    task_kwargs: dict[str, Any],
    responses: list[tuple[str, str, int]],
    conversation_id: str,
) -> Path:
    task_path = _write_task(tmp_path / f"{name}-task.json", **task_kwargs)
    iterator = iter(responses)

    def fake_run(config, prompt, *, timeout_seconds):
        stdout, stderr, exit_status = next(iterator)
        return SimpleNamespace(
            command=[str(config.llama_cli)],
            stdout=stdout,
            stderr=stderr,
            exit_status=exit_status,
            timed_out=False,
            vram_samples=[],
            vram_summary=None,
        )

    monkeypatch.setattr(run_helpers, "run_llama_cpp", fake_run)
    _patch_identity(monkeypatch)
    result_dir = tmp_path / name
    run_helpers.execute_run(
        suite=Path("agent-backend-v1"),
        only=TASK_ID,
        include="all",
        resolved=_resolved(),
        out=result_dir,
        fail_on_failed_prompts=False,
        conversation_task=task_path,
        conversation_id=conversation_id,
    )
    return result_dir


def _pair(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    left_task: dict[str, Any],
    left_responses: list[tuple[str, str, int]],
    right_task: dict[str, Any],
    right_responses: list[tuple[str, str, int]],
) -> list[dict[str, Any]]:
    left = _run_transcript_result(
        tmp_path,
        monkeypatch,
        "left",
        task_kwargs=left_task,
        responses=left_responses,
        conversation_id="conversation-left",
    )
    right = _run_transcript_result(
        tmp_path,
        monkeypatch,
        "right",
        task_kwargs=right_task,
        responses=right_responses,
        conversation_id="conversation-right",
    )
    return [load_compare_result(left), load_compare_result(right)]


def test_identity_and_structural_facts_are_closed_views(tmp_path, monkeypatch) -> None:
    results = _pair(
        tmp_path,
        monkeypatch,
        left_task=_COMPLETED_TASK,
        left_responses=_OK,
        right_task=_COMPLETED_TASK,
        right_responses=_OK,
    )
    identity = transcript_identity(load_transcript(Path(results[0]["_result_dir"])))
    assert identity["protocol_id"] == "llmgauge.sequential_supplied_feedback"
    assert identity["task_id"] == TASK_ID
    assert identity["effective_max_model_turns"] == 1
    facts = structural_facts(load_transcript(Path(results[0]["_result_dir"])))
    assert facts["completion_state"] == "completed"
    assert facts["logical_model_turns"] == 1
    assert facts["model_attempts"] == 1
    assert facts["terminal_reason"] == "completed"
    assert facts["attempt_outcomes"] == ["attempt-001-001:completed:exit=0"]


def test_identical_structure_classification(tmp_path, monkeypatch) -> None:
    results = _pair(
        tmp_path,
        monkeypatch,
        left_task=_COMPLETED_TASK,
        left_responses=_OK,
        right_task=_COMPLETED_TASK,
        right_responses=_OK,
    )
    report = compare_results(results)
    assert "- Eligibility: **eligible for bounded structural comparison**" in report
    assert "- Classification: **identical structure**" in report
    assert "(match)" in report
    assert "MISMATCH" not in report


def test_retry_difference_is_structurally_comparable(tmp_path, monkeypatch) -> None:
    retry_task = {"feedback": False, "max_turns": 1, "attempts": 2}
    results = _pair(
        tmp_path,
        monkeypatch,
        left_task=retry_task,
        left_responses=[("bad bytes", "recovery failed", 1), ("corrected", "", 0)],
        right_task=retry_task,
        right_responses=[("corrected", "", 0)],
    )
    report = compare_results(results)
    assert "- Eligibility: **eligible for bounded structural comparison**" in report
    assert "- Classification: **structurally comparable**" in report
    assert "`model_attempts`" in report
    assert "relationship `retry`" in report
    assert "retry of `event-" in report


def test_partial_versus_completed_is_incomparable_with_asymmetry(
    tmp_path, monkeypatch
) -> None:
    results = _pair(
        tmp_path,
        monkeypatch,
        left_task=_COMPLETED_TASK,
        left_responses=_OK,
        right_task=_COMPLETED_TASK,
        right_responses=_FAILED,
    )
    report = compare_results(results)
    assert "- Classification: **structurally incomparable**" in report
    assert (
        "Completion asymmetry: completed/completed; partial/runtime_failure" in report
    )
    assert "never presented as though completion occurred" in report


def test_identity_mismatch_is_not_comparable(tmp_path, monkeypatch) -> None:
    results = _pair(
        tmp_path,
        monkeypatch,
        left_task={"feedback": True, "max_turns": 1},
        left_responses=_OK,
        right_task={"feedback": False, "max_turns": 1},
        right_responses=_OK,
    )
    report = compare_results(results)
    assert "- Eligibility: **not comparable**" in report
    assert "`max_feedback_items`" in report
    assert "(MISMATCH)" in report
    assert "independent evidence" in report


def test_review_hooks_are_shown_as_recorded(tmp_path, monkeypatch) -> None:
    results = _pair(
        tmp_path,
        monkeypatch,
        left_task=_COMPLETED_TASK,
        left_responses=_OK,
        right_task=_COMPLETED_TASK,
        right_responses=_OK,
    )
    left_dir = Path(results[0]["_result_dir"])
    transcript = load_transcript(left_dir)
    transcript.review.final_response = "unscoreable"
    write_transcript(left_dir, transcript)
    result_json = left_dir / "llmgauge-result.json"
    result = json.loads(result_json.read_text(encoding="utf-8"))
    result["transcript"] = build_result_transcript_reference(left_dir, transcript)
    result_json.write_text(json.dumps(result), encoding="utf-8")

    report = compare_results(results)
    assert "| `final_response` | `unscoreable` | `unreviewed` |" in report
    assert "| `scoreability` | `unreviewed` | `unreviewed` |" in report
    assert "no verdict is invented or implied" in report


def test_roles_and_order_are_preserved(tmp_path, monkeypatch) -> None:
    results = _pair(
        tmp_path,
        monkeypatch,
        left_task={"feedback": True, "max_turns": 2},
        left_responses=[("first", "", 0), ("corrected", "", 0)],
        right_task={"feedback": True, "max_turns": 2},
        right_responses=[("first", "", 0), ("corrected", "", 0)],
    )
    report = compare_results(results)
    assert "role `user`" in report
    assert "role `assistant`" in report
    assert "role `protocol`" in report
    assert "task first, terminal last" in report
    assert "inert supply occurrence (not executed work)" in report


def test_report_declares_no_aggregate_no_ranking(tmp_path, monkeypatch) -> None:
    results = _pair(
        tmp_path,
        monkeypatch,
        left_task=_COMPLETED_TASK,
        left_responses=_OK,
        right_task=_COMPLETED_TASK,
        right_responses=_OK,
    )
    report = compare_results(results)
    assert "No transcript/session aggregate score exists in V1." in report
    assert "does not rank runs, declare winners" in report
    assert "implies no universal rank" in report


def test_mixed_transcript_and_single_turn_fails_closed(tmp_path, monkeypatch) -> None:
    results = _pair(
        tmp_path,
        monkeypatch,
        left_task=_COMPLETED_TASK,
        left_responses=_OK,
        right_task=_COMPLETED_TASK,
        right_responses=_OK,
    )
    flat_dir = tmp_path / "flat"
    flat_dir.mkdir()
    flat = json.loads(
        (Path(results[1]["_result_dir"]) / "llmgauge-result.json").read_text(
            encoding="utf-8"
        )
    )
    flat["transcript"] = None
    (flat_dir / "llmgauge-result.json").write_text(json.dumps(flat), encoding="utf-8")
    mixed = [results[0], load_compare_result(flat_dir)]
    with pytest.raises(ValueError, match="fails closed"):
        compare_results(mixed)


def test_single_turn_comparison_is_unchanged(tmp_path, monkeypatch) -> None:
    results = _pair(
        tmp_path,
        monkeypatch,
        left_task=_COMPLETED_TASK,
        left_responses=_OK,
        right_task=_COMPLETED_TASK,
        right_responses=_OK,
    )
    flat_results = []
    for index, result in enumerate(results):
        flat_dir = tmp_path / f"flat-{index}"
        flat_dir.mkdir()
        flat = json.loads(
            (Path(result["_result_dir"]) / "llmgauge-result.json").read_text(
                encoding="utf-8"
            )
        )
        flat["transcript"] = None
        (flat_dir / "llmgauge-result.json").write_text(
            json.dumps(flat), encoding="utf-8"
        )
        flat_results.append(load_compare_result(flat_dir))
    report = compare_results(flat_results)
    assert "# LLMGauge Comparison Report" in report
    assert "Transcript Comparison" not in report


def test_transcript_public_export_still_fails_closed(tmp_path, monkeypatch) -> None:
    results = _pair(
        tmp_path,
        monkeypatch,
        left_task=_COMPLETED_TASK,
        left_responses=_OK,
        right_task=_COMPLETED_TASK,
        right_responses=_OK,
    )
    with pytest.raises(ValueError, match="public export is not implemented"):
        export_public_run(Path(results[0]["_result_dir"]), tmp_path / "exported")


def test_compare_command_writes_transcript_report(tmp_path, monkeypatch) -> None:
    results = _pair(
        tmp_path,
        monkeypatch,
        left_task=_COMPLETED_TASK,
        left_responses=_OK,
        right_task=_COMPLETED_TASK,
        right_responses=_OK,
    )
    out = tmp_path / "transcript-compare.md"
    exit_code = runner.invoke(
        cli.app,
        [
            "compare",
            results[0]["_result_dir"],
            results[1]["_result_dir"],
            "--out",
            str(out),
        ],
    ).exit_code
    assert exit_code == 0
    report = out.read_text(encoding="utf-8")
    assert "# LLMGauge Transcript Comparison" in report
    assert "- Classification:" in report


def test_comparison_requires_two_results(tmp_path, monkeypatch) -> None:
    results = _pair(
        tmp_path,
        monkeypatch,
        left_task=_COMPLETED_TASK,
        left_responses=_OK,
        right_task=_COMPLETED_TASK,
        right_responses=_OK,
    )
    with pytest.raises(TranscriptComparisonError):
        compare_results([results[0]])


def test_cli_mixed_comparison_exits_cleanly(tmp_path, monkeypatch) -> None:
    results = _pair(
        tmp_path,
        monkeypatch,
        left_task=_COMPLETED_TASK,
        left_responses=_OK,
        right_task=_COMPLETED_TASK,
        right_responses=_OK,
    )
    flat_dir = tmp_path / "flat-cli"
    flat_dir.mkdir()
    flat = json.loads(
        (Path(results[1]["_result_dir"]) / "llmgauge-result.json").read_text(
            encoding="utf-8"
        )
    )
    flat["transcript"] = None
    (flat_dir / "llmgauge-result.json").write_text(json.dumps(flat), encoding="utf-8")
    out = tmp_path / "mixed.md"
    run = runner.invoke(
        cli.app,
        [
            "compare",
            results[0]["_result_dir"],
            str(flat_dir),
            "--out",
            str(out),
        ],
    )
    assert run.exit_code == 1
    assert "Comparison failed" in run.output
    assert "fails closed" in run.output
    assert not out.exists()
