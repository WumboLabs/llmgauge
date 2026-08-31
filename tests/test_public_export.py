from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

import llmgauge.core.public_export as public_export_module
from llmgauge.core.area4_evidence import (
    build_area4_evidence,
    build_native_execution_evidence,
)
from llmgauge.core.public_export import export_public_run
from llmgauge.core.result_validation import validate_result_dir
from llmgauge.core.run_fingerprint import attach_run_fingerprint


def _write_run(
    tmp_path: Path,
    *,
    with_provenance: bool = True,
    model_filename: str = "model.gguf",
    executable_filename: str = "llama-cli",
    with_area4: bool = False,
    raw_output: str = "api_key=private-value\nRelative/path remains.\n",
    cleaned_output: str = "cleaned output\n",
) -> Path:
    result_dir = tmp_path / "source-run"
    (result_dir / "raw").mkdir(parents=True)
    (result_dir / "cleaned").mkdir()
    (result_dir / "logs").mkdir()
    (result_dir / "vram").mkdir()
    if with_area4:
        (result_dir / "native").mkdir()

    model = {
        "model_id": "test-model",
        "model_source": "model_profile",
        "model_profile": "test-profile",
        "model_path": "redacted",
        "model_path_policy": "redacted",
    }
    if with_provenance:
        model["provenance"] = {
            "source_type": "model_profile",
            "filename": model_filename,
            "file_size_bytes": 123,
            "sha256": "a" * 64,
            "public_fingerprint": "sha256:aaaaaaaaaaaaaaaa",
            "status": "available",
        }

    result = {
        "schema_version": "llmgauge.result.v0",
        "llmgauge_version": "0.66.0",
        "run": {
            "run_id": "source-run",
            "timestamp_utc": "2026-07-10T00:00:00+00:00",
            "status": "completed",
            "result_dir": str(tmp_path / "private-home" / "results" / "source-run"),
        },
        "model": model,
        "runtime": {
            "backend": "llama.cpp",
            "llama_cli": str(tmp_path / "private-home" / "llama.cpp" / "llama-cli"),
            "config_path": str(tmp_path / "private-home" / "config.yaml"),
            "model_profiles_path": str(tmp_path / "private-home" / "profiles.yaml"),
            "runtime_command_captured": True,
            "runtime_command_path": "runtime-command.json",
            "command": ["/private-home/llama-cli", "-p", "SYSTEM: private prompt"],
            "backend_provenance": {
                "backend_name": "llama.cpp",
                "executable_filename": executable_filename,
                "executable_sha256": "b" * 64,
                "public_executable_fingerprint": "sha256:bbbbbbbbbbbbbbbb",
                "reported_version": "b1234",
                "build_metadata": "gcc 13.2.0",
                "status": "available",
            },
            "api_key": "should-not-leak",
        },
        "suite": {
            "suite_id": "core-v1",
            "suite_version": "0.1.0",
            "suite_path": str(tmp_path / "private-home" / "suites" / "core-v1"),
            "prompt_count": 1,
        },
        "summary": {"completed": 1, "failed": 0},
        "results": [
            {
                "prompt_id": "honesty-unknown-tool",
                "category": "honesty",
                "status": "completed",
                "raw_prompt_path": "raw/honesty-unknown-tool.prompt.md",
                "raw_output_path": "raw/honesty-unknown-tool.output.txt",
                "cleaned_output_path": "cleaned/honesty-unknown-tool.output.txt",
                "stderr_log_path": "logs/honesty-unknown-tool.stderr.log",
                "vram_samples_path": "vram/honesty-unknown-tool.samples.json",
                "exit_status": 0,
                "metrics": {"generation_tps": 10.0},
                "score": None,
            }
        ],
    }
    if with_area4:
        native_evidence = build_native_execution_evidence(
            prompt_id="honesty-unknown-tool",
            elapsed_seconds=1.0,
            stdout="output",
            stderr="",
            exit_status=0,
            timed_out=False,
            launch_error=None,
        )
        native_path = "native/honesty-unknown-tool.execution.json"
        result["results"][0]["native_execution_evidence_path"] = native_path
        result["results"][0]["_area4_native_execution_evidence"] = native_evidence
        metrics, taxonomy = build_area4_evidence(
            prompt_results=result["results"],
            suite=result["suite"],
            runtime=result["runtime"],
        )
        result["results"][0].pop("_area4_native_execution_evidence")
        result["runtime_neutral_metrics"] = metrics
        result["failure_taxonomy"] = taxonomy
        (result_dir / native_path).write_text(
            json.dumps(native_evidence, indent=2) + "\n",
            encoding="utf-8",
        )
    (result_dir / "llmgauge-result.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    (result_dir / "runtime-command.json").write_text(
        json.dumps(
            {
                "schema_version": "llmgauge.runtime_command.v0",
                "executable": str(tmp_path / "private-home" / "llama-cli"),
                "model_path": "redacted",
                "command_argv": ["llama-cli", "-p", "SYSTEM: private prompt"],
                "prompt_placeholder": "__PROMPT_FROM_RAW_ARTIFACT__",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (result_dir / "raw" / "honesty-unknown-tool.prompt.md").write_text(
        "Use /home/private-user/config.yaml\n", encoding="utf-8"
    )
    (result_dir / "raw" / "honesty-unknown-tool.output.txt").write_text(
        raw_output, encoding="utf-8"
    )
    (result_dir / "cleaned" / "honesty-unknown-tool.output.txt").write_text(
        cleaned_output, encoding="utf-8"
    )
    (result_dir / "logs" / "honesty-unknown-tool.stderr.log").write_text(
        "stderr /tmp/private-run\n", encoding="utf-8"
    )
    (result_dir / "vram" / "honesty-unknown-tool.samples.json").write_text(
        json.dumps({"samples": [], "path": "/tmp/private-vram"}) + "\n",
        encoding="utf-8",
    )
    (result_dir / "scores.yaml").write_text(
        "reviewer_notes: safe review\n", encoding="utf-8"
    )
    (result_dir / "unknown-private.db").write_bytes(b"private")
    attach_run_fingerprint(result_dir, result)
    (result_dir / "llmgauge-result.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    return result_dir


def test_public_export_sanitizes_without_modifying_source(tmp_path: Path) -> None:
    source_dir = _write_run(tmp_path)
    before = {
        path.relative_to(source_dir).as_posix(): hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        for path in source_dir.rglob("*")
        if path.is_file()
    }

    output_dir = tmp_path / "public-export"
    manifest = export_public_run(source_dir, output_dir)

    after = {
        path.relative_to(source_dir).as_posix(): hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        for path in source_dir.rglob("*")
        if path.is_file()
    }
    assert before == after
    assert manifest["source_artifact_type"] == "llmgauge.result.v0"
    assert manifest["source_run_fingerprint"]["schema_version"] == (
        "llmgauge.run_fingerprint.v0"
    )
    assert "canonical private evidence" in manifest["source_run_fingerprint_boundary"]
    assert "unknown-private.db" in manifest["files_omitted"]
    assert validate_result_dir(output_dir) == []

    exported_result = json.loads(
        (output_dir / "llmgauge-result.json").read_text(encoding="utf-8")
    )
    exported_json = json.dumps(exported_result)
    assert "private-home" not in exported_json
    assert "a" * 64 not in exported_json
    assert "b" * 64 not in exported_json
    assert "run_fingerprint" not in exported_result
    assert exported_result["model"]["provenance"]["public_fingerprint"]
    assert exported_result["runtime"]["backend_provenance"][
        "public_executable_fingerprint"
    ]
    assert exported_result["results"][0]["raw_output_path"] == (
        "raw/honesty-unknown-tool.output.txt"
    )

    runtime_command = json.loads(
        (output_dir / "runtime-command.json").read_text(encoding="utf-8")
    )
    assert runtime_command["prompt_placeholder"] == "PROMPT_FROM_RAW_ARTIFACT"
    assert runtime_command["command_argv"][2] == "PROMPT_FROM_RAW_ARTIFACT"
    assert "REDACTED_ABSOLUTE_PATH" in runtime_command["executable"]

    assert "REDACTED_HOME_PATH" in (
        output_dir / "raw" / "honesty-unknown-tool.prompt.md"
    ).read_text(encoding="utf-8")
    assert "REDACTED_SECRET" in (
        output_dir / "raw" / "honesty-unknown-tool.output.txt"
    ).read_text(encoding="utf-8")


def test_public_export_omits_reasoning_bearing_generated_outputs(
    tmp_path: Path,
) -> None:
    private_reasoning = "<think>PRIVATE_REASONING_SENTINEL</think>final answer"
    source_dir = _write_run(
        tmp_path,
        raw_output=private_reasoning,
        cleaned_output=private_reasoning,
    )
    output_dir = tmp_path / "public-export"

    manifest = export_public_run(source_dir, output_dir)

    assert (output_dir / "raw/honesty-unknown-tool.output.txt").read_text(
        encoding="utf-8"
    ) == ""
    assert (output_dir / "cleaned/honesty-unknown-tool.output.txt").read_text(
        encoding="utf-8"
    ) == ""
    assert "generated_reasoning_omitted" in manifest["redaction_categories"]
    assert validate_result_dir(output_dir) == []


def test_public_export_retains_final_answer_only_outputs(tmp_path: Path) -> None:
    final_answer = "ordinary final answer\n"
    source_dir = _write_run(
        tmp_path,
        raw_output=final_answer,
        cleaned_output=final_answer,
    )
    output_dir = tmp_path / "public-export"

    manifest = export_public_run(source_dir, output_dir)

    assert (output_dir / "raw/honesty-unknown-tool.output.txt").read_text(
        encoding="utf-8"
    ) == final_answer
    assert (output_dir / "cleaned/honesty-unknown-tool.output.txt").read_text(
        encoding="utf-8"
    ) == final_answer
    assert "generated_reasoning_omitted" not in manifest["redaction_categories"]
    assert "area4_ttft_omitted" not in manifest["redaction_categories"]
    assert validate_result_dir(output_dir) == []


def test_public_export_validator_rejects_private_projection_mutations(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "public-export"
    export_public_run(_write_run(tmp_path), output_dir)

    result_path = output_dir / "llmgauge-result.json"
    exported = json.loads(result_path.read_text(encoding="utf-8"))
    exported["runtime"]["endpoint_identity"] = {"port": 18081}
    exported["results"][0]["reasoning"] = "PRIVATE_REASONING"
    exported["results"][0]["token_ids"] = [987654321]
    result_path.write_text(json.dumps(exported), encoding="utf-8")
    (output_dir / "raw/honesty-unknown-tool.output.txt").write_text(
        "<think>PRIVATE_REASONING</think>",
        encoding="utf-8",
    )
    (output_dir / "request").mkdir()
    (output_dir / "request/private.stream.json").write_text(
        json.dumps({"token_ids": [987654321]}),
        encoding="utf-8",
    )
    manifest_path = output_dir / "public-export-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files_omitted"].append("raw/honesty-unknown-tool.output.txt")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    errors = validate_result_dir(output_dir)

    assert any("structured reasoning" in error for error in errors)
    assert any("private token IDs" in error for error in errors)
    assert any("local endpoint identity" in error for error in errors)
    assert any("generated reasoning marker" in error for error in errors)
    assert any("private stream artifact" in error for error in errors)
    assert any("claims omitted file is present" in error for error in errors)


def test_public_export_preserves_native_execution_evidence(tmp_path: Path) -> None:
    source_dir = _write_run(tmp_path, with_area4=True)
    output_dir = tmp_path / "public-export"

    manifest = export_public_run(source_dir, output_dir)

    native_path = "native/honesty-unknown-tool.execution.json"
    assert native_path in manifest["files_transformed"]
    assert (output_dir / native_path).is_file()
    exported = json.loads(
        (output_dir / "llmgauge-result.json").read_text(encoding="utf-8")
    )
    assert exported["runtime_neutral_metrics"]["measurements"][0]["metrics"][0][
        "evidence_refs"
    ] == [f"{native_path}#/request_wall_time_seconds"]
    assert validate_result_dir(output_dir) == []


def test_public_export_redacts_local_hostname_and_username(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_dir = _write_run(tmp_path)
    private_text = "Reviewed on PrivateHost by PrivateUser.\n"
    (source_dir / "scores.yaml").write_text(private_text, encoding="utf-8")
    monkeypatch.setattr(public_export_module, "_LOCAL_HOSTNAME", "PrivateHost")
    monkeypatch.setattr(public_export_module, "_LOCAL_USERNAMES", ("PrivateUser",))

    output_dir = tmp_path / "public-export"
    manifest = export_public_run(source_dir, output_dir)

    exported_scores = (output_dir / "scores.yaml").read_text(encoding="utf-8")
    assert exported_scores == "Reviewed on REDACTED_HOSTNAME by REDACTED_USERNAME.\n"
    assert "local_hostname" in manifest["redaction_categories"]
    assert "local_username" in manifest["redaction_categories"]


@pytest.mark.parametrize(
    ("model_filename", "executable_filename", "expected_model", "expected_executable"),
    [
        (
            f"{'a' * 64}.gguf",
            "llama-cli",
            "REDACTED_FULL_HASH.gguf",
            "llama-cli",
        ),
        (
            f"model-{'b' * 64}-Q4_K_M.gguf",
            "llama-cli",
            "model-REDACTED_FULL_HASH-Q4_K_M.gguf",
            "llama-cli",
        ),
        (
            "model.gguf",
            f"{'C' * 64}-LLAMA-CLI",
            "model.gguf",
            "REDACTED_FULL_HASH-LLAMA-CLI",
        ),
        ("ordinary-model.gguf", "llama-cli", "ordinary-model.gguf", "llama-cli"),
        ("a" * 63, "b" * 65, "a" * 63, "b" * 65),
    ],
)
def test_public_export_redacts_only_bounded_filename_hashes(
    tmp_path: Path,
    model_filename: str,
    executable_filename: str,
    expected_model: str,
    expected_executable: str,
) -> None:
    source_dir = _write_run(
        tmp_path,
        model_filename=model_filename,
        executable_filename=executable_filename,
    )
    output_dir = tmp_path / "public-export"

    manifest = export_public_run(source_dir, output_dir)
    exported = json.loads(
        (output_dir / "llmgauge-result.json").read_text(encoding="utf-8")
    )
    model_provenance = exported["model"]["provenance"]
    backend_provenance = exported["runtime"]["backend_provenance"]

    assert model_provenance["filename"] == expected_model
    assert backend_provenance["executable_filename"] == expected_executable
    assert model_provenance["public_fingerprint"] == "sha256:aaaaaaaaaaaaaaaa"
    assert backend_provenance["public_executable_fingerprint"] == (
        "sha256:bbbbbbbbbbbbbbbb"
    )
    if any(
        "REDACTED_FULL_HASH" in expected
        for expected in (expected_model, expected_executable)
    ):
        assert "filename_full_sha256" in manifest["redaction_categories"]
    else:
        assert "filename_full_sha256" not in manifest["redaction_categories"]


def test_public_export_filename_hashes_are_absent_from_structured_metadata(
    tmp_path: Path,
) -> None:
    model_hash = "a" * 64
    backend_hash = "b" * 64
    source_dir = _write_run(
        tmp_path,
        model_filename=f"model-{model_hash}.gguf",
        executable_filename=f"llama-{backend_hash}",
    )
    output_dir = tmp_path / "public-export"

    export_public_run(source_dir, output_dir)
    exported = json.loads(
        (output_dir / "llmgauge-result.json").read_text(encoding="utf-8")
    )
    assert model_hash not in json.dumps(exported)
    assert backend_hash not in json.dumps(exported)
    assert "sha256" not in exported["model"]["provenance"]
    assert "executable_sha256" not in exported["runtime"]["backend_provenance"]
    assert validate_result_dir(output_dir) == []


def test_public_export_manifest_is_deterministic_except_timestamp(
    tmp_path: Path,
) -> None:
    source_dir = _write_run(tmp_path)
    first = export_public_run(source_dir, tmp_path / "public-one")
    second = export_public_run(source_dir, tmp_path / "public-two")

    first.pop("exported_at_utc")
    second.pop("exported_at_utc")
    assert first == second


def test_public_export_refuses_nonempty_output_and_invalid_source(
    tmp_path: Path,
) -> None:
    source_dir = _write_run(tmp_path)
    output_dir = tmp_path / "existing"
    output_dir.mkdir()
    (output_dir / "keep.txt").write_text("keep", encoding="utf-8")

    try:
        export_public_run(source_dir, output_dir)
    except ValueError as exc:
        assert "non-empty" in str(exc)
    else:
        raise AssertionError("expected non-empty output refusal")

    invalid_source = tmp_path / "invalid"
    invalid_source.mkdir()
    (invalid_source / "llmgauge-result.json").write_text("{}", encoding="utf-8")
    try:
        export_public_run(invalid_source, tmp_path / "invalid-export")
    except (FileNotFoundError, ValueError) as exc:
        assert "validation" in str(exc).lower() or "missing" in str(exc).lower()
    else:
        raise AssertionError("expected invalid source refusal")


def test_public_export_refuses_source_and_nested_output_paths(tmp_path: Path) -> None:
    source_dir = _write_run(tmp_path)

    with pytest.raises(ValueError, match="must differ"):
        export_public_run(source_dir, source_dir)

    direct_nested = source_dir / "public"
    with pytest.raises(ValueError, match="cannot be inside the source run"):
        export_public_run(source_dir, direct_nested)
    assert not direct_nested.exists()

    deeply_nested = source_dir / "nested" / "public"
    with pytest.raises(ValueError, match="cannot be inside the source run"):
        export_public_run(source_dir, deeply_nested)
    assert not deeply_nested.exists()


def test_public_export_failure_leaves_no_partial_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_dir = _write_run(tmp_path)
    output_dir = tmp_path / "public"

    def fail_after_partial_write(*args: object, **kwargs: object) -> str:
        staging_dir = args[1]
        relative_path = args[2]
        assert isinstance(staging_dir, Path)
        assert isinstance(relative_path, Path)
        (staging_dir / relative_path).parent.mkdir(parents=True, exist_ok=True)
        (staging_dir / relative_path).write_text("partial", encoding="utf-8")
        raise RuntimeError("forced transform failure")

    monkeypatch.setattr(
        "llmgauge.core.public_export._copy_or_transform",
        fail_after_partial_write,
    )

    with pytest.raises(RuntimeError, match="forced transform failure"):
        export_public_run(source_dir, output_dir)

    assert not output_dir.exists()
    assert list(tmp_path.glob(".llmgauge-public-export-*")) == []


def test_public_export_existing_empty_destination_remains_empty_after_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_dir = _write_run(tmp_path)
    output_dir = tmp_path / "public"
    output_dir.mkdir()

    def fail_validation(path: Path) -> list[str]:
        if path.name.startswith(".llmgauge-public-export-"):
            return ["forced exported-result validation failure"]
        return []

    monkeypatch.setattr(
        "llmgauge.core.public_export.validate_result_dir", fail_validation
    )

    with pytest.raises(ValueError, match="forced exported-result validation failure"):
        export_public_run(source_dir, output_dir)

    assert output_dir.exists()
    assert output_dir.is_dir()
    assert list(output_dir.iterdir()) == []
    assert list(tmp_path.glob(".llmgauge-public-export-*")) == []


def test_public_export_success_supports_nonexistent_and_empty_destinations(
    tmp_path: Path,
) -> None:
    source_dir = _write_run(tmp_path)
    nonexistent_output = tmp_path / "new-public"
    existing_empty_output = tmp_path / "empty-public"
    existing_empty_output.mkdir()

    export_public_run(source_dir, nonexistent_output)
    export_public_run(source_dir, existing_empty_output)

    assert validate_result_dir(nonexistent_output) == []
    assert validate_result_dir(existing_empty_output) == []


def test_public_export_nonempty_destination_remains_untouched(tmp_path: Path) -> None:
    source_dir = _write_run(tmp_path)
    output_dir = tmp_path / "existing"
    output_dir.mkdir()
    existing_file = output_dir / "keep.txt"
    existing_file.write_text("keep", encoding="utf-8")

    with pytest.raises(ValueError, match="non-empty"):
        export_public_run(source_dir, output_dir)

    assert existing_file.read_text(encoding="utf-8") == "keep"
    assert sorted(path.name for path in output_dir.iterdir()) == ["keep.txt"]


def test_public_export_supports_legacy_result_without_provenance(
    tmp_path: Path,
) -> None:
    source_dir = _write_run(tmp_path, with_provenance=False)

    manifest = export_public_run(source_dir, tmp_path / "legacy-export")

    assert manifest["source_artifact_type"] == "llmgauge.result.v0"
    assert validate_result_dir(tmp_path / "legacy-export") == []


def test_public_export_docs_do_not_claim_transformed_byte_authentication() -> None:
    reporting_doc = Path("docs/PUBLIC_REPORTING.md").read_text(encoding="utf-8")
    normalized_doc = " ".join(reporting_doc.split())

    assert (
        "does not verify or authenticate transformed public-export bytes"
        in normalized_doc
    )


def test_public_export_preserves_non_sensitive_extended_runtime_settings(
    tmp_path: Path,
) -> None:
    source_dir = _write_run(tmp_path)
    result_path = source_dir / "llmgauge-result.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    runtime = result["runtime"]
    runtime.update(
        {
            "top_k": 20,
            "top_k_state": "explicit",
            "seed": 424242,
            "seed_state": "explicit",
            "kv_offload": "requested_on",
            "cache_type_k": "q8_0",
            "cache_type_k_state": "explicit",
            "cache_type_v": "q4_0",
            "cache_type_v_state": "explicit",
            "reasoning_effort": "medium",
            "reasoning_effort_state": "explicit",
            "reasoning_budget": 16384,
            "reasoning_budget_state": "explicit",
            "fit": "off",
            "fit_state": "explicit",
            "reasoning_preserve": False,
            "reasoning_preserve_state": "explicit",
            "spec_type": "draft-mtp",
            "spec_type_state": "explicit",
        }
    )
    command_path = source_dir / "runtime-command.json"
    command = json.loads(command_path.read_text(encoding="utf-8"))
    command.update(
        {
            field: runtime[field]
            for field in runtime
            if field
            in {
                "top_k",
                "top_k_state",
                "seed",
                "seed_state",
                "kv_offload",
                "cache_type_k",
                "cache_type_k_state",
                "cache_type_v",
                "cache_type_v_state",
                "reasoning_effort",
                "reasoning_effort_state",
                "reasoning_budget",
                "reasoning_budget_state",
                "fit",
                "fit_state",
                "reasoning_preserve",
                "reasoning_preserve_state",
                "spec_type",
                "spec_type_state",
            }
        }
    )
    command_path.write_text(json.dumps(command) + "\n", encoding="utf-8")
    attach_run_fingerprint(source_dir, result)
    result_path.write_text(json.dumps(result) + "\n", encoding="utf-8")

    export_public_run(source_dir, tmp_path / "public-run")

    exported = json.loads(
        (tmp_path / "public-run" / "llmgauge-result.json").read_text(encoding="utf-8")
    )
    assert exported["runtime"]["top_k"] == 20
    assert exported["runtime"]["seed"] == 424242
    assert exported["runtime"]["cache_type_k"] == "q8_0"
    assert exported["runtime"]["reasoning_budget"] == 16384
    assert exported["runtime"]["fit"] == "off"
    assert exported["runtime"]["reasoning_preserve"] is False
    assert exported["runtime"]["spec_type"] == "draft-mtp"
    exported_command = json.loads(
        (tmp_path / "public-run" / "runtime-command.json").read_text(encoding="utf-8")
    )
    assert exported_command["fit"] == "off"
    assert exported_command["reasoning_preserve"] is False
    assert exported_command["spec_type"] == "draft-mtp"
