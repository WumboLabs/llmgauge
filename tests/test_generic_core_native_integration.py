from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from llmgauge.commands import run_helpers
from llmgauge.core.generic_core_scoring import (
    GENERIC_CORE_APPLICABILITY,
    GENERIC_CORE_SUITE_ID,
    GENERIC_CORE_VERSION,
)
from llmgauge.core.reports import build_markdown_report
from llmgauge.core.result_validation import validate_result_data, validate_result_dir
from llmgauge.core.scoring import (
    apply_scores,
    build_score_template,
    load_result,
    validate_scores,
    write_result,
)
from llmgauge.core.suite import load_normalized_suite
from llmgauge.core.suite_paths import resolve_suite_path

ROOT = Path(__file__).parents[1]

D1_PASS = (
    "1. Harborview repair clinic 18 October\n"
    "2. North Hall 09:30\n"
    "3. Registration free by 15 October"
)
D3_PASS = (
    "Decisions\nThe review copy stays on the laptop.\n"
    "Open questions\nWhich checklist applies?"
)
D5_CANDIDATE = "def merge_intervals(intervals):\n    return sorted(intervals)"


def _fixture_json(relative_path: str) -> Any:
    fixture_path = ROOT / "suites/generic-core-v1/fixtures/v0.1.0" / relative_path
    return json.loads(fixture_path.read_text())


def _closed_answer(fixture_path: str) -> str:
    fixture = _fixture_json(fixture_path)
    if "expected_value" in fixture:
        expected = fixture["expected_value"]
    elif "expected_request" in fixture:
        expected = fixture["expected_request"]
    else:
        expected = {"answers": fixture["answers"]}
    return json.dumps(expected, separators=(",", ":"))


PASS_OUTPUTS = {
    "generic-core-instruction-rewrite-01": D1_PASS,
    "generic-core-structured-json-01": _closed_answer(
        "deterministic/typed-record-json.json"
    ),
    "generic-core-honesty-evidence-gap-01": "The observations support the trend but not the causal claim.",
    "generic-core-summary-decision-log-01": D3_PASS,
    "generic-core-extraction-ledger-01": _closed_answer(
        "deterministic/ledger-extraction.json"
    ),
    "generic-core-plan-dependencies-01": "Ordered plan respecting every stated limit.",
    "generic-core-explain-cache-protocol-01": "The identity check prevents a stale read because...",
    "generic-core-code-interval-merge-01": D5_CANDIDATE,
    "generic-core-review-window-average-01": "The off-by-one bound is the central defect.",
    "generic-core-troubleshoot-staged-pipeline-01": "Compare stage-two counts against stage-one counts.",
    "generic-core-safety-risky-heating-01": "I cannot provide operational steps; use qualified supervision.",
    "generic-core-tool-record-lookup-01": _closed_answer(
        "deterministic/tool-request.json"
    ),
    "generic-core-context-policy-reconcile-01": _closed_answer(
        "bounded-context/reconciliation.json"
    ),
}


def _resolved() -> dict[str, Any]:
    return {
        "model_id": "synthetic-model",
        "model_profile": "synthetic-profile",
        "profile": {
            "label": "Synthetic Model",
            "family": "Synthetic",
            "role": "test",
            "quant": "none",
        },
        "config_path": None,
        "model_profiles_path": None,
        "model_path": Path("/synthetic/model.gguf"),
        "llama_cli": Path("/synthetic/llama-cli"),
        "ctx": 8192,
        "max_tokens": 256,
        "temp": 0.2,
        "top_p": 0.95,
        "batch": 256,
        "ubatch": 64,
        "gpu_layers": 0,
        "flash_attn": "off",
        "runtime_label": "synthetic",
        "reasoning_mode": "off",
        "model_source": "model_profile",
        "vram_min_headroom_warn_mib": None,
    }


def _patch_provenance(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        run_helpers,
        "collect_model_provenance",
        lambda *args, **kwargs: {
            "source_type": "model_profile",
            "filename": "model.gguf",
            "file_size_bytes": 1,
            "sha256": "a" * 64,
            "public_fingerprint": "sha256:aaaaaaaaaaaaaaaa",
            "status": "available",
        },
    )
    monkeypatch.setattr(
        run_helpers,
        "collect_backend_provenance",
        lambda *args, **kwargs: {
            "backend_name": "llama.cpp",
            "executable_filename": "llama-cli",
            "executable_file_size_bytes": 1,
            "executable_sha256": "b" * 64,
            "public_executable_fingerprint": "sha256:bbbbbbbbbbbbbbbb",
            "status": "available",
        },
    )
    monkeypatch.setattr(
        run_helpers,
        "discover_llama_runtime_identity",
        lambda *args, **kwargs: {
            "reported_version": "synthetic",
            "commit": None,
            "build_number": None,
            "build_type": None,
            "build_metadata": None,
            "discovery_status": "available",
        },
    )


def _run_generic(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    profile: str | None = None,
    only: str | None = None,
    outputs: dict[str, str] | None = None,
) -> tuple[dict[str, Any], Path]:
    _patch_provenance(monkeypatch)
    suite = load_normalized_suite(
        resolve_suite_path(Path(GENERIC_CORE_SUITE_ID)),
        profile=profile,
    )
    selected_ids = (only,) if only is not None else suite.selected_prompt_ids
    responses = iter((outputs or PASS_OUTPUTS)[prompt_id] for prompt_id in selected_ids)

    def fake_run_llama_cpp(config: Any, prompt: str) -> SimpleNamespace:
        stdout = next(responses)
        return SimpleNamespace(
            command=[str(config.llama_cli), "--model", str(config.model_path)],
            stdout=stdout,
            stderr="",
            exit_status=0,
            vram_samples=[],
            vram_summary=None,
        )

    monkeypatch.setattr(run_helpers, "run_llama_cpp", fake_run_llama_cpp)
    result_dir = tmp_path / "result"
    result = run_helpers.execute_run(
        suite=Path(GENERIC_CORE_SUITE_ID),
        only=only,
        include="all",
        profile=profile,
        resolved=_resolved(),
        out=result_dir,
        fail_on_failed_prompts=False,
    )
    return result, result_dir


def test_core_profile_run_records_selection_and_full_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    contract = load_normalized_suite(resolve_suite_path(Path(GENERIC_CORE_SUITE_ID)))
    result, result_dir = _run_generic(tmp_path, monkeypatch)

    assert validate_result_data(result_dir, result) == []

    selection = result["suite"]["selection"]
    assert selection["kind"] == "profile"
    assert selection["selected_profile"] == "core"
    assert selection["default_profile"] == "core"
    assert selection["selected_prompt_ids"] == list(contract.canonical_prompt_ids)
    assert selection["canonical_prompt_ids"] == list(contract.canonical_prompt_ids)
    assert len(result["results"]) == 13

    by_id = {item["prompt_id"]: item for item in result["results"]}
    for prompt_id in contract.canonical_prompt_ids:
        assert "generic_core" in by_id[prompt_id]
        method = by_id[prompt_id]["generic_core"]["scoring_method"]
        assert method["role"] in {"deterministic", "manual", "hybrid"}
        if method["role"] != "manual":
            assert method["deterministic_check"]["version"] == GENERIC_CORE_VERSION
        if method["role"] != "deterministic":
            assert method["manual_rubric"]["id"] == "default-manual-v0"

    d5 = by_id["generic-core-code-interval-merge-01"]["generic_core"]
    assert d5["deterministic_result"]["outcome"] == "not_run"
    assert d5["deterministic_result"]["check_id"] == (
        "generic-core-interval-function-v0"
    )
    assert d5["hybrid_composition"]["complete"] is False


def test_core_report_exposes_components_and_d5_non_execution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result, result_dir = _run_generic(tmp_path, monkeypatch)
    report = build_markdown_report(result, result_dir=result_dir)

    assert "## Generic Core Evidence" in report
    assert "Selection kind: profile" in report
    assert "Selected profile: core" in report
    assert "did not execute generated code" in report
    assert "generic-core-interval-function-v0 (0.1.0)" in report
    assert "| generic-core-code-interval-merge-01 |" in report
    assert "not_run" in report
    assert "No profile-level or overall numeric Generic Core score exists." in report


def test_smoke_profile_run_exact_ordered_membership(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    smoke_ids = [
        "generic-core-instruction-rewrite-01",
        "generic-core-structured-json-01",
        "generic-core-honesty-evidence-gap-01",
        "generic-core-extraction-ledger-01",
    ]
    result, result_dir = _run_generic(tmp_path, monkeypatch, profile="smoke")

    assert validate_result_data(result_dir, result) == []
    selection = result["suite"]["selection"]
    assert selection["kind"] == "profile"
    assert selection["selected_profile"] == "smoke"
    assert selection["selected_prompt_ids"] == smoke_ids
    assert [item["prompt_id"] for item in result["results"]] == smoke_ids


def test_custom_only_run_is_disclosed_custom_selection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    only = "generic-core-instruction-rewrite-01"
    result, result_dir = _run_generic(tmp_path, monkeypatch, only=only)

    assert validate_result_data(result_dir, result) == []
    selection = result["suite"]["selection"]
    assert selection["kind"] == "custom"
    assert selection["selected_profile"] is None
    assert selection["selected_prompt_ids"] == [only]
    assert selection["canonical_prompt_ids"] != [only]


def test_validation_rejects_fabricated_profile_membership(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result, result_dir = _run_generic(
        tmp_path, monkeypatch, only="generic-core-instruction-rewrite-01"
    )
    fabricated = json.loads(json.dumps(result))
    fabricated["suite"]["selection"]["kind"] = "profile"
    fabricated["suite"]["selection"]["selected_profile"] = "smoke"

    errors = validate_result_data(result_dir, fabricated)
    assert any(
        "profile identity and membership are inconsistent" in error for error in errors
    )


def test_validation_requires_evidence_for_every_selected_prompt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result, result_dir = _run_generic(tmp_path, monkeypatch, profile="smoke")
    stripped = json.loads(json.dumps(result))
    stripped["results"][1].pop("generic_core")

    errors = validate_result_data(result_dir, stripped)
    assert any(
        "evidence must be present for every selected prompt" in error
        for error in errors
    )


def test_validation_fails_generic_result_without_any_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result, result_dir = _run_generic(tmp_path, monkeypatch, profile="smoke")
    stripped = json.loads(json.dumps(result))
    for item in stripped["results"]:
        item.pop("generic_core")

    errors = validate_result_data(result_dir, stripped)
    assert any(
        "evidence must be present for every selected prompt" in error
        for error in errors
    )
    assert any("Generic Core" in error for error in errors)


def test_score_application_updates_manual_and_hybrid_without_rerunning_check(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prompt_id = "generic-core-instruction-rewrite-01"
    result, result_dir = _run_generic(
        tmp_path,
        monkeypatch,
        only=prompt_id,
        outputs={prompt_id: "one line"},
    )
    before = json.loads(
        json.dumps(result["results"][0]["generic_core"]["deterministic_result"])
    )
    assert before["outcome"] == "fail"

    scores = build_score_template(result)
    entry = scores["scores"][prompt_id]
    for dimension in GENERIC_CORE_APPLICABILITY[prompt_id]:
        entry[dimension] = 4
    entry.update(
        {
            "score_rationale": "Reviewed against the preserved raw response.",
            "verdict": "fail",
            "scoring_mode": "manual",
            "scorer_id": "reviewer-a",
            "reviewed": True,
        }
    )
    assert validate_scores(result, scores) == []

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError(
            "deterministic checks must not rerun during score application"
        )

    monkeypatch.setattr(
        "llmgauge.core.static_scoring.apply_deterministic_check", forbidden
    )
    updated = apply_scores(result, scores)
    generic = updated["results"][0]["generic_core"]

    assert generic["deterministic_result"] == before
    assert generic["manual_review"]["review_state"] == "reviewed"
    assert generic["manual_review"]["rubric_id"] == "default-manual-v0"
    assert generic["manual_review"]["verdict"] == "fail"
    assert generic["hybrid_composition"]["complete"] is True
    assert generic["hybrid_composition"]["deterministic_result"] == before
    assert generic["hybrid_composition"]["manual_component"]["reviewed"] is True
    assert updated["summary"]["manual_score_average"] is None
    assert updated["summary"]["scored_prompt_count"] == 1
    assert validate_result_data(result_dir, updated) == []

    write_result(result_dir, updated)
    reloaded = load_result(result_dir)
    assert validate_result_dir(result_dir) == []
    assert (
        reloaded["results"][0]["generic_core"]["hybrid_composition"]["complete"] is True
    )


def test_unreviewed_draft_keeps_hybrid_incomplete(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prompt_id = "generic-core-instruction-rewrite-01"
    result, result_dir = _run_generic(tmp_path, monkeypatch, only=prompt_id)

    scores = build_score_template(result)
    scores["scores"][prompt_id]["instruction_following"] = 4
    # No reviewed flag, no scorer: stays a draft.
    updated = apply_scores(result, scores)
    generic = updated["results"][0]["generic_core"]
    assert generic["manual_review"]["review_state"] == "unreviewed"
    assert generic["hybrid_composition"]["complete"] is False
    assert validate_result_data(result_dir, updated) == []
