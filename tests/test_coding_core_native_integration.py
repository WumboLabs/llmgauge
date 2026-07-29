from __future__ import annotations

import copy
import importlib
import json
import os
import socket
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import llmgauge.core.result_validation as result_validation_module
from llmgauge.commands import run_helpers
from llmgauge.core.coding_core_evidence import build_manual_review
from llmgauge.core.reports import build_markdown_report
from llmgauge.core.result_validation import validate_result_data
from llmgauge.core.scoring import apply_scores, build_score_template, validate_scores
from llmgauge.core.static_scoring import (
    CODING_CORE_APPLICABILITY,
    STATIC_RESPONSE_MAX_CHARS,
    apply_deterministic_check,
    compose_hybrid_score,
)
from llmgauge.core.suite import load_normalized_suite
from llmgauge.core.suite_paths import resolve_suite_path

PATCH_PASS = """*** Begin Patch
*** Update File: src/config.py
@@
-old
+new
*** Update File: tests/test_config.py
@@
 old
+new
*** End Patch
"""
CODE_PASS = """```python
def test_contract():
    assert True
```
"""
JSON_PASS = json.dumps(
    {
        "change_id": "CFG-017",
        "summary": "Reject boolean port values while retaining the integer range.",
        "files": [
            {"path": "src/config.py", "action": "modify"},
            {"path": "tests/test_config.py", "action": "modify"},
        ],
        "behavior": {
            "before": "True is accepted as port 1.",
            "after": "Booleans are rejected and valid integers remain accepted.",
        },
        "verification": [
            {
                "check": "focused-tests",
                "status": "not_run",
                "reason": "No tests were run in the supplied scenario.",
            },
            {
                "check": "static-review",
                "status": "not_run",
                "reason": "No review was run in the supplied scenario.",
            },
        ],
        "uncertainties": [
            "The unspecified invalid-value exception message remains unknown."
        ],
    }
)
HYBRID_OUTPUTS = {
    "patch/bounded-cross-file-change": PATCH_PASS,
    "tests/behavioral-contract-cases": CODE_PASS,
    "structured/closed-json-change-record": JSON_PASS,
}
SMOKE_PROMPT_IDS = (
    "debug/state-transition-defect",
    "patch/bounded-cross-file-change",
    "shell/safe-repository-maintenance",
    "structured/closed-json-change-record",
)


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


def _run_coding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    outputs: dict[str, tuple[str, int]],
    *,
    only: str | None = None,
    profile: str | None = None,
) -> tuple[dict[str, Any], Path]:
    _patch_provenance(monkeypatch)
    suite = load_normalized_suite(
        resolve_suite_path(Path("coding-core-v1")),
        profile=profile,
    )
    selected_ids = (only,) if only is not None else suite.selected_prompt_ids
    responses = iter(outputs[prompt_id] for prompt_id in selected_ids)

    def fake_run_llama_cpp(config: Any, prompt: str) -> SimpleNamespace:
        stdout, exit_status = next(responses)
        return SimpleNamespace(
            command=[str(config.llama_cli), "--model", str(config.model_path)],
            stdout=stdout,
            stderr="synthetic failure" if exit_status else "",
            exit_status=exit_status,
            vram_samples=[],
            vram_summary=None,
        )

    monkeypatch.setattr(run_helpers, "run_llama_cpp", fake_run_llama_cpp)
    result_dir = tmp_path / "result"
    result = run_helpers.execute_run(
        suite=Path("coding-core-v1"),
        only=only,
        include="all",
        profile=profile,
        resolved=_resolved(),
        out=result_dir,
        fail_on_failed_prompts=False,
    )
    return result, result_dir


def _all_outputs() -> dict[str, tuple[str, int]]:
    suite = load_normalized_suite(resolve_suite_path(Path("coding-core-v1")))
    return {
        prompt_id: (HYBRID_OUTPUTS.get(prompt_id, "Manual response."), 0)
        for prompt_id in suite.selected_prompt_ids
    }


def _fully_reviewed_entry(prompt_id: str, verdict: str = "pass") -> dict[str, Any]:
    entry = {dimension: 4 for dimension in CODING_CORE_APPLICABILITY[prompt_id]}
    entry.update(
        {
            "failure_labels": [],
            "good_labels": [],
            "reviewer_notes": "Reviewed manually.",
            "score_rationale": "Reviewed against the preserved prompt and raw response.",
            "verdict": verdict,
            "scoring_mode": "manual",
            "scorer_id": "reviewer-a",
            "scorer_version": "review-protocol-1",
            "confidence": "high",
            "evidence": ["Preserved raw response."],
            "warnings": [],
            "reviewed": True,
            "override_status": "none",
        }
    )
    return entry


def test_native_run_persists_all_hybrid_methods_and_bounded_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result, result_dir = _run_coding(tmp_path, monkeypatch, _all_outputs())

    selection = result["suite"]["selection"]
    assert selection["kind"] == "profile"
    assert selection["selected_profile"] == "core"
    assert selection["default_profile"] == "core"
    assert selection["selected_prompt_ids"] == [
        prompt["prompt_id"] for prompt in result["results"]
    ]
    assert selection["canonical_prompt_ids"] == selection["selected_prompt_ids"]
    assert "suite_path" not in json.dumps(selection)

    hybrid_count = 0
    for prompt_result in result["results"]:
        coding = prompt_result["coding_core"]
        assert coding["manual_review"]["review_state"] == "missing"
        assert coding["manual_review"]["verdict"] is None
        role = coding["scoring_method"]["role"]
        if role == "hybrid":
            hybrid_count += 1
            assert coding["deterministic_result"]["outcome"] == "pass"
            assert coding["hybrid_composition"]["complete"] is False
            assert (
                coding["hybrid_composition"]["manual_component"]["review_state"]
                == "missing"
            )
        else:
            assert role == "manual"
            assert "deterministic_check" not in coding["scoring_method"]
            assert "deterministic_result" not in coding
            assert "hybrid_composition" not in coding
    assert hybrid_count == 3
    assert result["summary"]["manual_score_total"] is None
    assert result["summary"]["manual_score_max"] is None
    assert "coding_core_score" not in result["summary"]
    assert validate_result_data(result_dir, result) == []

    report = (result_dir / "report.md").read_text(encoding="utf-8")
    assert "## Coding Core Evidence" in report
    assert "structural `pass` is not proof of semantic correctness" in report
    assert (
        "Generated code, tests, patches, commands, and JSON actions were not executed"
        in report
    )
    assert "Manual review remains the semantic authority" in report
    assert "Incomplete hybrid evidence is not a failed prompt" in report
    assert "No universal or profile-level numeric Coding Core score exists" in report
    assert "coding-core-bounded-patch-form-v0" in report


def test_native_run_named_smoke_profile_preserves_portable_selection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result, result_dir = _run_coding(
        tmp_path,
        monkeypatch,
        _all_outputs(),
        profile="smoke",
    )

    result_prompt_ids = tuple(prompt["prompt_id"] for prompt in result["results"])
    assert result_prompt_ids == SMOKE_PROMPT_IDS
    assert result["suite"]["include"] == "all"
    assert result["suite"]["only"] is None
    assert result["suite"]["prompt_count"] == len(SMOKE_PROMPT_IDS)
    assert result["suite"]["selection"] == {
        "kind": "profile",
        "selected_profile": "smoke",
        "selected_prompt_ids": list(SMOKE_PROMPT_IDS),
        "canonical_prompt_ids": list(
            load_normalized_suite(
                resolve_suite_path(Path("coding-core-v1"))
            ).canonical_prompt_ids
        ),
        "default_profile": "core",
    }
    assert validate_result_data(result_dir, result) == []


def test_static_check_uses_raw_response_not_cleaned_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wrapped = (
        "\n> SYSTEM:\n\nSystem prompt\n\nUSER:\n\nPrompt ... (truncated)\n\n"
        + PATCH_PASS
        + "\n[ Prompt: 1.0 t/s | Generation: 1.0 t/s ]\n\nExiting...\n"
    )
    prompt_id = "patch/bounded-cross-file-change"
    result, result_dir = _run_coding(
        tmp_path,
        monkeypatch,
        {prompt_id: (wrapped, 0)},
        only=prompt_id,
    )

    prompt = result["results"][0]
    cleaned = (result_dir / prompt["cleaned_output_path"]).read_text(encoding="utf-8")
    assert cleaned.strip() == PATCH_PASS.strip()
    assert prompt["coding_core"]["deterministic_result"]["outcome"] == "fail"
    assert validate_result_data(result_dir, result) == []


def test_generation_failure_is_not_run_without_changing_generation_status(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prompt_id = "tests/behavioral-contract-cases"
    result, result_dir = _run_coding(
        tmp_path,
        monkeypatch,
        {prompt_id: ("", 1)},
        only=prompt_id,
    )

    prompt = result["results"][0]
    assert prompt["status"] == "failed"
    assert prompt["coding_core"]["deterministic_result"]["outcome"] == "not_run"
    assert prompt["coding_core"]["hybrid_composition"]["complete"] is False
    assert validate_result_data(result_dir, result) == []


def test_oversized_resource_error_replays_and_generation_stays_completed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prompt_id = "patch/bounded-cross-file-change"
    result, result_dir = _run_coding(
        tmp_path,
        monkeypatch,
        {prompt_id: ("x" * (STATIC_RESPONSE_MAX_CHARS + 1), 0)},
        only=prompt_id,
    )

    prompt = result["results"][0]
    deterministic = prompt["coding_core"]["deterministic_result"]
    assert prompt["status"] == "completed"
    assert deterministic["outcome"] == "error"
    assert deterministic["error_classification"] == "resource-bound"
    assert prompt["coding_core"]["hybrid_composition"]["complete"] is False
    assert validate_result_data(result_dir, result) == []


def test_oversized_replay_reads_only_shared_limit_plus_one(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prompt_id = "patch/bounded-cross-file-change"
    result, result_dir = _run_coding(
        tmp_path,
        monkeypatch,
        {prompt_id: ("x" * (STATIC_RESPONSE_MAX_CHARS + 4096), 0)},
        only=prompt_id,
    )
    raw_path = _raw_output_path(result_dir, result)
    original_open = Path.open
    read_sizes: list[int] = []

    class RecordingReader:
        def __init__(self, handle: Any) -> None:
            self.handle = handle

        def __enter__(self) -> RecordingReader:
            self.handle.__enter__()
            return self

        def __exit__(self, *args: Any) -> Any:
            return self.handle.__exit__(*args)

        def read(self, size: int = -1) -> str:
            read_sizes.append(size)
            return self.handle.read(size)

    def recording_open(path: Path, *args: Any, **kwargs: Any) -> Any:
        handle = original_open(path, *args, **kwargs)
        if path == raw_path and kwargs.get("encoding") == "utf-8":
            return RecordingReader(handle)
        return handle

    monkeypatch.setattr(Path, "open", recording_open)

    assert validate_result_data(result_dir, _validation_copy(result)) == []
    assert raw_path.stat().st_size > STATIC_RESPONSE_MAX_CHARS + 1
    assert read_sizes == [STATIC_RESPONSE_MAX_CHARS + 1]


@pytest.mark.parametrize(
    "fabrication",
    ["pass", "fail", "not_run", "wrong-error-classification", "altered-evidence"],
)
def test_oversized_replay_rejects_fabricated_deterministic_records(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fabrication: str,
) -> None:
    prompt_id = "patch/bounded-cross-file-change"
    result, result_dir = _run_coding(
        tmp_path,
        monkeypatch,
        {prompt_id: ("x" * (STATIC_RESPONSE_MAX_CHARS + 1), 0)},
        only=prompt_id,
    )
    malformed = _validation_copy(result)
    suite = load_normalized_suite(resolve_suite_path(Path("coding-core-v1")))
    genuine = malformed["results"][0]["coding_core"]["deterministic_result"]

    if fabrication == "pass":
        fabricated = apply_deterministic_check(suite, prompt_id, PATCH_PASS)
    elif fabrication == "fail":
        fabricated = apply_deterministic_check(
            suite, prompt_id, "not a conforming patch"
        )
    elif fabrication == "not_run":
        fabricated = apply_deterministic_check(suite, prompt_id, None)
    else:
        fabricated = copy.deepcopy(genuine)
        if fabrication == "wrong-error-classification":
            fabricated["error_classification"] = "invalid-input"
        else:
            fabricated["evidence"][0]["detail"] = (
                "raw response evidence has an unsupported type"
            )

    coding = malformed["results"][0]["coding_core"]
    coding["deterministic_result"] = fabricated
    coding["hybrid_composition"] = compose_hybrid_score(
        suite, prompt_id, fabricated, None
    )

    errors = validate_result_data(result_dir, malformed)
    assert not any("malformed or inconsistent" in error for error in errors)
    assert any(
        "does not match authoritative raw response replay" in error for error in errors
    )


def test_score_application_updates_manual_and_hybrid_without_rerunning_check(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prompt_id = "patch/bounded-cross-file-change"
    result, result_dir = _run_coding(
        tmp_path,
        monkeypatch,
        {prompt_id: ("not a patch", 0)},
        only=prompt_id,
    )
    before = copy.deepcopy(result["results"][0]["coding_core"]["deterministic_result"])
    scores = build_score_template(result)
    scores["scores"][prompt_id] = _fully_reviewed_entry(prompt_id, verdict="pass")
    assert validate_scores(result, scores) == []

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError(
            "deterministic checks must not rerun during score application"
        )

    monkeypatch.setattr(
        "llmgauge.core.static_scoring.apply_deterministic_check", forbidden
    )
    updated = apply_scores(result, scores)
    prompt = updated["results"][0]
    coding = prompt["coding_core"]
    assert coding["deterministic_result"] == before
    assert coding["deterministic_result"]["outcome"] == "fail"
    assert coding["manual_review"] == {
        "rubric_id": "coding-core-manual-v0",
        "rubric_version": "0.1.0",
        "applicable_dimensions": list(CODING_CORE_APPLICABILITY[prompt_id]),
        "review_state": "reviewed",
        "reviewed": True,
        "verdict": "pass",
    }
    assert coding["hybrid_composition"]["complete"] is True
    assert coding["hybrid_composition"]["deterministic_result"] == before
    assert coding["hybrid_composition"]["manual_component"]["verdict"] == "pass"
    assert updated["summary"]["manual_score_total"] is None
    assert updated["summary"]["manual_score_max"] is None
    assert updated["summary"]["manual_score_average"] is None
    assert validate_result_data(result_dir, updated) == []


def test_manual_review_persistence_covers_all_accepted_states() -> None:
    suite = load_normalized_suite(resolve_suite_path(Path("coding-core-v1")))
    prompt = next(
        item for item in suite.prompts if item.id == "debug/state-transition-defect"
    )
    template = build_score_template(
        {
            "run": {"run_id": "states"},
            "suite": {
                "suite_id": "coding-core-v1",
                "suite_version": "0.1.0",
                "suite_path": str(suite.suite_root),
            },
            "summary": {},
            "results": [{"prompt_id": prompt.id, "score": None}],
        }
    )
    unreviewed = template["scores"][prompt.id]
    partial = copy.deepcopy(unreviewed)
    partial.update(
        {
            "diagnosis_accuracy": 3,
            "reviewed": True,
            "scorer_id": "reviewer-a",
            "score_rationale": "Only one dimension had enough evidence.",
            "verdict": "needs_review",
        }
    )
    reviewed = _fully_reviewed_entry(prompt.id)
    unscoreable = copy.deepcopy(unreviewed)
    unscoreable.update(
        {
            "reviewed": True,
            "scorer_id": "reviewer-a",
            "score_rationale": "No response evidence was available.",
            "verdict": "needs_review",
        }
    )

    assert build_manual_review(prompt, None)["review_state"] == "missing"
    assert build_manual_review(prompt, unreviewed)["review_state"] == "unreviewed"
    assert build_manual_review(prompt, partial)["review_state"] == "partial"
    assert build_manual_review(prompt, reviewed)["review_state"] == "reviewed"
    assert build_manual_review(prompt, unscoreable)["review_state"] == "unscoreable"


def test_result_validation_rejects_malformed_and_private_deterministic_data(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prompt_id = "patch/bounded-cross-file-change"
    result, result_dir = _run_coding(
        tmp_path,
        monkeypatch,
        {prompt_id: (PATCH_PASS, 0)},
        only=prompt_id,
    )
    malformed = copy.deepcopy(result)
    malformed.pop("run_fingerprint")
    deterministic = malformed["results"][0]["coding_core"]["deterministic_result"]
    deterministic["check_id"] = "/home/private/checkout/check.py"
    deterministic["private_path"] = "/home/private/checkout"

    errors = validate_result_data(result_dir, malformed)
    assert any("deterministic result" in error for error in errors)
    rendered = "\n".join(errors)
    assert "/home/private" not in rendered
    assert "checkout" not in rendered


def _validation_copy(result: dict[str, Any]) -> dict[str, Any]:
    copied = copy.deepcopy(result)
    copied.pop("run_fingerprint", None)
    return copied


def _raw_output_path(result_dir: Path, result: dict[str, Any]) -> Path:
    return result_dir / result["results"][0]["raw_output_path"]


def test_replay_rejects_false_pass_over_nonconforming_raw_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prompt_id = "patch/bounded-cross-file-change"
    result, result_dir = _run_coding(
        tmp_path,
        monkeypatch,
        {prompt_id: (PATCH_PASS, 0)},
        only=prompt_id,
    )
    _raw_output_path(result_dir, result).write_text(
        "not a conforming patch", encoding="utf-8"
    )

    errors = validate_result_data(result_dir, _validation_copy(result))
    assert any(
        "does not match authoritative raw response replay" in error for error in errors
    )


def test_replay_rejects_false_fail_over_conforming_raw_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prompt_id = "patch/bounded-cross-file-change"
    result, result_dir = _run_coding(
        tmp_path,
        monkeypatch,
        {prompt_id: ("not a conforming patch", 0)},
        only=prompt_id,
    )
    assert (
        result["results"][0]["coding_core"]["deterministic_result"]["outcome"] == "fail"
    )
    _raw_output_path(result_dir, result).write_text(PATCH_PASS, encoding="utf-8")

    errors = validate_result_data(result_dir, _validation_copy(result))
    assert any(
        "does not match authoritative raw response replay" in error for error in errors
    )


def test_replay_rejects_tampered_closed_evidence_details(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prompt_id = "patch/bounded-cross-file-change"
    result, result_dir = _run_coding(
        tmp_path,
        monkeypatch,
        {prompt_id: (PATCH_PASS, 0)},
        only=prompt_id,
    )
    tampered = _validation_copy(result)
    coding = tampered["results"][0]["coding_core"]
    coding["deterministic_result"]["evidence"][0]["detail"] = (
        "tampered but still closed and relationship-valid"
    )
    coding["hybrid_composition"]["deterministic_result"] = copy.deepcopy(
        coding["deterministic_result"]
    )

    errors = validate_result_data(result_dir, tampered)
    assert not any("hybrid composition" in error for error in errors)
    assert any(
        "does not match authoritative raw response replay" in error for error in errors
    )


@pytest.mark.parametrize(
    ("failure_kind", "expected_diagnostic"),
    [
        ("missing", "missing or not safely contained"),
        ("escaped", "missing or not safely contained"),
        ("unreadable", "authoritative raw response is unreadable"),
    ],
)
def test_replay_raw_evidence_failures_are_bounded_and_public_safe(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure_kind: str,
    expected_diagnostic: str,
) -> None:
    prompt_id = "patch/bounded-cross-file-change"
    result, result_dir = _run_coding(
        tmp_path,
        monkeypatch,
        {prompt_id: (PATCH_PASS, 0)},
        only=prompt_id,
    )
    raw_path = _raw_output_path(result_dir, result)
    private_content = "PRIVATE-RAW-RESPONSE-CONTENT"
    private_path = tmp_path / "private-source-output.txt"

    if failure_kind == "missing":
        raw_path.unlink()
    elif failure_kind == "escaped":
        private_path.write_text(private_content, encoding="utf-8")
        raw_path.unlink()
        raw_path.symlink_to(private_path)
    else:
        original_open = Path.open

        def guarded_open(path: Path, *args: Any, **kwargs: Any) -> Any:
            if path == raw_path:
                raise OSError("PRIVATE-READ-FAILURE")
            return original_open(path, *args, **kwargs)

        monkeypatch.setattr(Path, "open", guarded_open)

    errors = validate_result_data(result_dir, _validation_copy(result))
    rendered = "\n".join(errors)
    assert expected_diagnostic in rendered
    assert private_content not in rendered
    assert str(private_path) not in rendered
    assert "PRIVATE-READ-FAILURE" not in rendered


def test_replay_resolver_oserror_becomes_bounded_public_safe_diagnostic(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prompt_id = "patch/bounded-cross-file-change"
    result, result_dir = _run_coding(
        tmp_path,
        monkeypatch,
        {prompt_id: (PATCH_PASS, 0)},
        only=prompt_id,
    )
    original_resolver = result_validation_module.resolve_contained_result_artifact
    raw_output_resolution_count = 0

    def resolver_with_failure(*args: Any, **kwargs: Any) -> Path:
        nonlocal raw_output_resolution_count
        if str(kwargs.get("label", "")).endswith(".raw_output_path"):
            raw_output_resolution_count += 1
            if raw_output_resolution_count == 2:
                raise OSError("PRIVATE-RESOLVER-FAILURE")
        return original_resolver(*args, **kwargs)

    monkeypatch.setattr(
        result_validation_module,
        "resolve_contained_result_artifact",
        resolver_with_failure,
    )

    errors = validate_result_data(result_dir, _validation_copy(result))
    rendered = "\n".join(errors)
    assert "authoritative raw response is missing or not safely contained" in rendered
    assert "PRIVATE-RESOLVER-FAILURE" not in rendered
    assert str(result_dir) not in rendered


@pytest.mark.parametrize("evidence_kind", ["none", "partial"])
def test_selection_requires_complete_per_prompt_coding_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    evidence_kind: str,
) -> None:
    result, result_dir = _run_coding(tmp_path, monkeypatch, _all_outputs())
    malformed = _validation_copy(result)
    targets = (
        malformed["results"] if evidence_kind == "none" else malformed["results"][:1]
    )
    for prompt_result in targets:
        prompt_result.pop("coding_core")

    errors = validate_result_data(result_dir, malformed)
    assert any(
        "suite.selection requires closed Coding Core evidence" in error
        for error in errors
    )


@pytest.mark.parametrize(
    ("contradiction", "expected_diagnostic"),
    [
        ("prompt-count", "suite.prompt_count"),
        ("selected-order", "must exactly match result prompt ordering"),
        ("only", "suite.only must equal the sole selected prompt"),
    ],
)
def test_selection_rejects_count_order_and_only_contradictions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    contradiction: str,
    expected_diagnostic: str,
) -> None:
    prompt_id = "patch/bounded-cross-file-change"
    if contradiction == "only":
        result, result_dir = _run_coding(
            tmp_path,
            monkeypatch,
            {prompt_id: (PATCH_PASS, 0)},
            only=prompt_id,
        )
    else:
        result, result_dir = _run_coding(tmp_path, monkeypatch, _all_outputs())
    malformed = _validation_copy(result)
    if contradiction == "prompt-count":
        malformed["suite"]["prompt_count"] += 1
    elif contradiction == "selected-order":
        malformed["suite"]["selection"]["selected_prompt_ids"] = list(
            reversed(malformed["suite"]["selection"]["selected_prompt_ids"])
        )
    else:
        malformed["suite"]["only"] = "tests/behavioral-contract-cases"

    errors = validate_result_data(result_dir, malformed)
    assert any(expected_diagnostic in error for error in errors)


def test_legacy_coding_result_without_optional_evidence_remains_valid(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prompt_id = "patch/bounded-cross-file-change"
    result, result_dir = _run_coding(
        tmp_path,
        monkeypatch,
        {prompt_id: (PATCH_PASS, 0)},
        only=prompt_id,
    )
    legacy = _validation_copy(result)
    legacy["suite"].pop("selection")
    legacy["results"][0].pop("coding_core")

    assert validate_result_data(result_dir, legacy) == []


def test_legacy_suite_run_and_report_remain_without_coding_fields(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_provenance(monkeypatch)

    def fake_run_llama_cpp(config: Any, prompt: str) -> SimpleNamespace:
        return SimpleNamespace(
            command=[str(config.llama_cli), "--model", str(config.model_path)],
            stdout="Legacy response.",
            stderr="",
            exit_status=0,
            vram_samples=[],
            vram_summary=None,
        )

    monkeypatch.setattr(run_helpers, "run_llama_cpp", fake_run_llama_cpp)
    result_dir = tmp_path / "legacy"
    result = run_helpers.execute_run(
        suite=Path("agent-backend-v1"),
        only="tool-honesty/fake-tool-resistance",
        include="all",
        resolved=_resolved(),
        out=result_dir,
        fail_on_failed_prompts=True,
    )

    assert "selection" not in result["suite"]
    assert "coding_core" not in result["results"][0]
    assert "Coding Core Evidence" not in build_markdown_report(result)
    assert validate_result_data(result_dir, result) == []


def test_native_integration_does_not_execute_generated_content(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("generated content execution is forbidden")

    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(os, "system", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(importlib, "import_module", forbidden)

    result, result_dir = _run_coding(tmp_path, monkeypatch, _all_outputs())
    assert validate_result_data(result_dir, result) == []
