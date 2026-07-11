from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from llmgauge.core.artifacts import write_json
from llmgauge.core.result_validation import validate_result_dir
from llmgauge.core.run_fingerprint import (
    RUN_FINGERPRINT_FIELD,
    RUN_FINGERPRINT_SCHEMA_VERSION,
    FingerprintUnavailable,
    attach_run_fingerprint,
    build_run_fingerprint_metadata,
    run_fingerprint_value,
    verify_run_fingerprint,
)


def _write_fingerprintable_run(
    tmp_path: Path,
    *,
    run_name: str = "run-a",
    run_id: str = "run-a",
    timestamp_utc: str = "2026-07-10T00:00:00+00:00",
) -> tuple[Path, dict]:
    result_dir = tmp_path / run_name
    (result_dir / "raw").mkdir(parents=True)
    (result_dir / "cleaned").mkdir()
    (result_dir / "logs").mkdir()
    (result_dir / "vram").mkdir()

    (result_dir / "raw" / "prompt.prompt.md").write_text("prompt\n", encoding="utf-8")
    (result_dir / "raw" / "prompt.output.txt").write_text("output\n", encoding="utf-8")
    (result_dir / "cleaned" / "prompt.output.txt").write_text(
        "cleaned output\n", encoding="utf-8"
    )
    (result_dir / "logs" / "prompt.stderr.log").write_text("stderr\n", encoding="utf-8")
    (result_dir / "vram" / "prompt.samples.json").write_text(
        json.dumps({"samples": []}) + "\n", encoding="utf-8"
    )
    (result_dir / "report.md").write_text("# Report\n", encoding="utf-8")
    (result_dir / "scores.yaml").write_text("reviewer_notes: ok\n", encoding="utf-8")

    result = {
        "schema_version": "llmgauge.result.v0",
        "llmgauge_version": "0.66.0",
        "run": {
            "run_id": run_id,
            "timestamp_utc": timestamp_utc,
            "status": "completed",
            "result_dir": str(result_dir),
        },
        "model": {
            "model_id": "test-model",
            "model_source": "model_profile",
            "model_profile": "test-profile",
            "model_path": "redacted",
            "model_path_policy": "redacted",
            "provenance": {
                "source_type": "model_profile",
                "filename": "model.gguf",
                "file_size_bytes": 5,
                "sha256": "a" * 64,
                "public_fingerprint": "sha256:aaaaaaaaaaaaaaaa",
                "status": "available",
            },
        },
        "runtime": {
            "backend": "llama.cpp",
            "llama_cli": str(tmp_path / "private" / "llama-cli"),
            "ctx_size": 8192,
            "max_tokens": 128,
            "temperature": 0.2,
            "top_p": 0.95,
            "batch_size": 256,
            "ubatch_size": 64,
            "gpu_layers": 999,
            "flash_attn": "auto",
            "runtime_label": "test-runtime",
            "reasoning_mode": "off",
            "runtime_command_captured": False,
            "backend_provenance": {
                "backend_name": "llama.cpp",
                "executable_filename": "llama-cli",
                "executable_file_size_bytes": 11,
                "executable_sha256": "b" * 64,
                "public_executable_fingerprint": "sha256:bbbbbbbbbbbbbbbb",
                "reported_version": "b1234",
                "commit": "abcdef1",
                "build_number": "1234",
                "build_type": None,
                "build_metadata": "gcc",
                "discovery_status": "available",
                "status": "available",
            },
        },
        "suite": {
            "suite_id": "core-v1",
            "suite_version": "0.1.0",
            "suite_path": str(tmp_path / "private" / "suite"),
            "prompt_count": 1,
            "include": "all",
            "only": None,
        },
        "summary": {"completed": 1, "failed": 0},
        "results": [
            {
                "prompt_id": "prompt",
                "title": "Prompt",
                "category": "honesty",
                "status": "completed",
                "raw_prompt_path": "raw/prompt.prompt.md",
                "raw_output_path": "raw/prompt.output.txt",
                "cleaned_output_path": "cleaned/prompt.output.txt",
                "stderr_log_path": "logs/prompt.stderr.log",
                "vram_samples_path": "vram/prompt.samples.json",
                "exit_status": 0,
                "metrics": {"generation_tps": 10.0},
                "score": None,
            }
        ],
    }
    attach_run_fingerprint(result_dir, result)
    write_json(result_dir / "llmgauge-result.json", result)
    return result_dir, result


def _value(result_dir: Path, result: dict) -> str:
    return run_fingerprint_value(result_dir, result)


def test_identical_evidence_produces_same_fingerprint(tmp_path: Path) -> None:
    first_dir, first = _write_fingerprintable_run(tmp_path, run_name="run-a")
    second_dir, second = _write_fingerprintable_run(tmp_path, run_name="run-b")

    assert _value(first_dir, first) == _value(second_dir, second)


def test_json_key_ordering_does_not_affect_fingerprint(tmp_path: Path) -> None:
    result_dir, result = _write_fingerprintable_run(tmp_path)
    reordered = {
        "results": result["results"],
        "suite": result["suite"],
        "runtime": result["runtime"],
        "model": result["model"],
        "run": result["run"],
        "llmgauge_version": result["llmgauge_version"],
        "schema_version": result["schema_version"],
        "summary": result["summary"],
    }

    assert _value(result_dir, result) == _value(result_dir, reordered)


def test_paths_run_id_and_timestamp_do_not_affect_fingerprint(tmp_path: Path) -> None:
    first_dir, first = _write_fingerprintable_run(
        tmp_path / "one",
        run_name="run",
        run_id="first",
        timestamp_utc="2026-07-10T00:00:00+00:00",
    )
    second_dir, second = _write_fingerprintable_run(
        tmp_path / "two",
        run_name="other-run",
        run_id="second",
        timestamp_utc="2026-07-11T00:00:00+00:00",
    )

    assert _value(first_dir, first) == _value(second_dir, second)


def test_material_identity_and_runtime_changes_affect_fingerprint(tmp_path: Path) -> None:
    result_dir, result = _write_fingerprintable_run(tmp_path)
    baseline = _value(result_dir, result)

    changed_model = copy.deepcopy(result)
    changed_model["model"]["provenance"]["sha256"] = "c" * 64
    assert _value(result_dir, changed_model) != baseline

    changed_backend = copy.deepcopy(result)
    changed_backend["runtime"]["backend_provenance"]["executable_sha256"] = "d" * 64
    assert _value(result_dir, changed_backend) != baseline

    changed_runtime = copy.deepcopy(result)
    changed_runtime["runtime"]["temperature"] = 0.7
    assert _value(result_dir, changed_runtime) != baseline

    changed_prompt = copy.deepcopy(result)
    changed_prompt["results"][0]["prompt_id"] = "other-prompt"
    assert _value(result_dir, changed_prompt) != baseline


def test_authoritative_artifact_bytes_affect_fingerprint(tmp_path: Path) -> None:
    result_dir, result = _write_fingerprintable_run(tmp_path)
    baseline = _value(result_dir, result)
    original_bytes = {
        relative_path: (result_dir / relative_path).read_bytes()
        for relative_path in [
            "raw/prompt.prompt.md",
            "raw/prompt.output.txt",
            "logs/prompt.stderr.log",
            "vram/prompt.samples.json",
        ]
    }

    for relative_path, original in original_bytes.items():
        (result_dir / relative_path).write_text(
            f"changed {relative_path}\n", encoding="utf-8"
        )
        assert _value(result_dir, result) != baseline
        (result_dir / relative_path).write_bytes(original)


def test_mutable_derived_and_review_artifacts_do_not_affect_fingerprint(
    tmp_path: Path,
) -> None:
    result_dir, result = _write_fingerprintable_run(tmp_path)
    baseline = _value(result_dir, result)

    (result_dir / "report.md").write_text("# Changed\n", encoding="utf-8")
    (result_dir / "cleaned" / "prompt.output.txt").write_text(
        "changed cleaned output\n", encoding="utf-8"
    )
    (result_dir / "scores.yaml").write_text("reviewer_notes: changed\n", encoding="utf-8")
    result["results"][0]["score"] = {
        "reviewer_notes": "changed",
        "score_rationale": "changed",
    }

    assert _value(result_dir, result) == baseline


def test_fingerprint_metadata_schema_and_validation(tmp_path: Path) -> None:
    result_dir, result = _write_fingerprintable_run(tmp_path)
    fingerprint = build_run_fingerprint_metadata(result_dir, result)

    assert fingerprint["schema_version"] == RUN_FINGERPRINT_SCHEMA_VERSION
    assert fingerprint["algorithm"] == "sha256"
    assert fingerprint["value"].startswith("sha256:")
    assert len(fingerprint["value"]) == len("sha256:") + 64
    assert validate_result_dir(result_dir) == []


def test_mismatched_and_malformed_fingerprints_fail_validation(tmp_path: Path) -> None:
    result_dir, result = _write_fingerprintable_run(tmp_path)

    result[RUN_FINGERPRINT_FIELD]["value"] = "sha256:" + "0" * 64
    write_json(result_dir / "llmgauge-result.json", result)
    assert any("does not match" in error for error in validate_result_dir(result_dir))

    result[RUN_FINGERPRINT_FIELD]["value"] = "not-a-fingerprint"
    write_json(result_dir / "llmgauge-result.json", result)
    assert any("sha256:<64 lowercase hex>" in error for error in validate_result_dir(result_dir))


def test_missing_authoritative_artifact_fails_fingerprint_verification(
    tmp_path: Path,
) -> None:
    result_dir, _result = _write_fingerprintable_run(tmp_path)

    (result_dir / "raw" / "prompt.output.txt").unlink()

    errors = validate_result_dir(result_dir)

    assert any("missing artifact" in error for error in errors)
    assert any("run_fingerprint cannot be verified" in error for error in errors)


def test_legacy_result_without_fingerprint_still_validates(tmp_path: Path) -> None:
    result_dir, result = _write_fingerprintable_run(tmp_path)
    result.pop(RUN_FINGERPRINT_FIELD)
    write_json(result_dir / "llmgauge-result.json", result)

    assert validate_result_dir(result_dir) == []


def test_non_material_runtime_metadata_does_not_affect_fingerprint(
    tmp_path: Path,
) -> None:
    result_dir, result = _write_fingerprintable_run(tmp_path)
    baseline = _value(result_dir, result)

    changed = copy.deepcopy(result)
    changed["runtime"]["runtime_label"] = "other-label"
    changed["runtime"]["vram_min_headroom_warn_mib"] = 9999

    assert _value(result_dir, changed) == baseline


def test_raw_output_symlink_outside_result_dir_is_rejected(tmp_path: Path) -> None:
    result_dir, result = _write_fingerprintable_run(tmp_path)
    external = tmp_path / "outside-output.txt"
    external.write_text("external secret output\n", encoding="utf-8")

    target = result_dir / "raw" / "prompt.output.txt"
    target.unlink()
    target.symlink_to(external)

    with pytest.raises(FingerprintUnavailable, match="escapes result directory"):
        _value(result_dir, result)

    errors = validate_result_dir(result_dir)
    assert any("run_fingerprint cannot be verified" in error for error in errors)
    assert any("escapes result directory" in error for error in errors)
    assert not any("external secret" in error for error in errors)


def test_symlinked_parent_directory_outside_result_dir_is_rejected(
    tmp_path: Path,
) -> None:
    result_dir, result = _write_fingerprintable_run(tmp_path)
    external_dir = tmp_path / "external-raw"
    external_dir.mkdir()
    external_file = external_dir / "prompt.output.txt"
    external_file.write_text("external via parent symlink\n", encoding="utf-8")

    raw_dir = result_dir / "raw"
    # Preserve non-output artifacts that still live under raw/.
    prompt_bytes = (raw_dir / "prompt.prompt.md").read_bytes()
    for child in raw_dir.iterdir():
        child.unlink()
    raw_dir.rmdir()
    raw_dir.symlink_to(external_dir)
    # Recreate prompt as a real file under the symlinked raw/ (external tree).
    # Fingerprint must still reject because raw/ is a symlink component.
    (raw_dir / "prompt.prompt.md").write_bytes(prompt_bytes)

    with pytest.raises(FingerprintUnavailable, match="escapes result directory"):
        _value(result_dir, result)

    errors = verify_run_fingerprint(result_dir, result)
    assert any("escapes result directory" in error for error in errors)


def test_artifact_read_oserror_becomes_fingerprint_unavailable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result_dir, result = _write_fingerprintable_run(tmp_path)
    original_open = Path.open

    def flaky_open(self: Path, *args: Any, **kwargs: Any):
        if self.name == "prompt.output.txt" and "raw" in self.parts:
            raise OSError("simulated read failure")
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", flaky_open)

    with pytest.raises(FingerprintUnavailable, match="unreadable") as exc_info:
        _value(result_dir, result)

    message = str(exc_info.value)
    assert "raw/prompt.output.txt" in message
    assert "simulated read failure" not in message

    errors = verify_run_fingerprint(result_dir, result)
    assert any("unreadable" in error for error in errors)
    assert any("raw/prompt.output.txt" in error for error in errors)
