"""Focused regression tests for vLLM adapter review corrections."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import typer

from llmgauge.commands import run_helpers
from llmgauge.core.artifacts import write_json, write_text
from llmgauge.core.result_validation import validate_result_data
from llmgauge.core.run_fingerprint import (
    FingerprintUnavailable,
    resolve_contained_result_artifact,
)


def test_reject_unsupported_vllm_command_allows_llama() -> None:
    run_helpers.reject_unsupported_vllm_command(
        {"backend": "llama.cpp"},
        command="run-batch",
    )


def test_reject_unsupported_vllm_command_blocks_vllm() -> None:
    with pytest.raises(typer.BadParameter) as exc:
        run_helpers.reject_unsupported_vllm_command(
            {"backend": "vllm"},
            command="run-batch",
        )
    assert "does not support backend=vllm" in str(exc.value)
    assert "llmgauge run" in str(exc.value)


def test_batch_path_rejects_vllm_before_execute(monkeypatch, tmp_path: Path) -> None:
    calls: list[str] = []

    def fake_resolve(**kwargs: Any) -> dict[str, Any]:
        calls.append("resolve")
        return {
            "backend": "vllm",
            "model_id": "m",
            "served_model": "m",
            "vllm_endpoint": "http://127.0.0.1:9",
        }

    def fake_execute(**kwargs: Any) -> dict[str, Any]:
        calls.append("execute")
        raise AssertionError("execute_run must not be called for vLLM batch")

    monkeypatch.setattr(run_helpers, "resolve_run_options", fake_resolve)
    monkeypatch.setattr(run_helpers, "execute_run", fake_execute)

    from llmgauge.commands import batch as batch_mod

    monkeypatch.setattr(
        batch_mod,
        "load_batch_manifest",
        lambda path: {
            "batch_id": "b1",
            "suite": "core-v1",
            "models": ["vllm-profile"],
            "max_tokens": 16,
            "only": None,
            "include": "all",
        },
    )
    monkeypatch.setattr(
        batch_mod,
        "resolve_suite_path",
        lambda p: tmp_path,
    )
    monkeypatch.setattr(
        batch_mod,
        "load_suite",
        lambda p: {"suite_id": "core-v1", "suite_version": "1", "prompts": []},
    )
    monkeypatch.setattr(
        batch_mod,
        "prepare_result_dir",
        lambda p: p.mkdir(parents=True, exist_ok=True),
    )
    monkeypatch.setattr(batch_mod, "write_batch_summary", lambda *a, **k: None)
    monkeypatch.setattr(batch_mod, "write_batch_report", lambda *a, **k: None)

    def fake_summary(**kwargs: Any) -> dict[str, Any]:
        child_runs = kwargs.get("child_runs", [])
        return {
            "child_runs": child_runs,
            "summary": {
                "failed": sum(1 for c in child_runs if c.get("status") == "failed"),
                "completed": sum(
                    1 for c in child_runs if c.get("status") == "completed"
                ),
            },
        }

    monkeypatch.setattr(batch_mod, "build_batch_summary", fake_summary)

    # run_batch catches exceptions per model; ensure vllm rejection is recorded
    # and execute never runs.
    out = tmp_path / "batch-out"
    with pytest.raises(typer.Exit):
        batch_mod.run_batch(
            manifest=tmp_path / "manifest.yaml",
            config_path=tmp_path / "cfg.yaml",
            model_profiles_path=tmp_path / "mp.yaml",
            out=out,
        )
    assert "resolve" in calls
    assert "execute" not in calls


def test_ladder_rejects_vllm_before_execute(monkeypatch, tmp_path: Path) -> None:
    calls: list[str] = []

    def fake_resolve(**kwargs: Any) -> dict[str, Any]:
        calls.append("resolve")
        return {
            "backend": "vllm",
            "model_id": "m",
            "model_path": None,
            "llama_cli": None,
            "ctx": kwargs.get("ctx") or 1024,
            "batch": 256,
            "ubatch": 64,
            "gpu_layers": 999,
            "max_tokens": 16,
            "temp": 0.2,
            "top_p": 0.95,
            "flash_attn": "auto",
            "runtime_label": None,
            "reasoning_mode": "off",
            "served_model": "m",
            "vllm_endpoint": "http://127.0.0.1:9",
        }

    def fake_execute(**kwargs: Any) -> dict[str, Any]:
        calls.append("execute")
        raise AssertionError("execute_run must not run for vLLM ladder")

    monkeypatch.setattr(run_helpers, "resolve_run_options", fake_resolve)
    monkeypatch.setattr(run_helpers, "execute_run", fake_execute)

    from llmgauge.commands import ladders as ladders_mod

    monkeypatch.setattr(ladders_mod, "resolve_suite_path", lambda p: tmp_path)
    monkeypatch.setattr(
        ladders_mod,
        "load_suite",
        lambda p: {"suite_id": "core-v1", "suite_version": "1", "prompts": []},
    )
    monkeypatch.setattr(
        ladders_mod,
        "parse_ctx_ladder",
        lambda text, allow_extreme_context=False: [1024, 2048],
    )
    monkeypatch.setattr(
        ladders_mod,
        "prepare_result_dir",
        lambda p: p.mkdir(parents=True, exist_ok=True),
    )

    with pytest.raises(typer.BadParameter) as exc:
        # dry-run path rejects after resolve
        ladders_mod.run_ladder(
            suite=tmp_path,
            only=None,
            include="all",
            model_id="m",
            model_profile=None,
            config_path=None,
            model_profiles_path=None,
            model_path=None,
            llama_cli=None,
            ctx_ladder="1024,2048",
            max_tokens=None,
            temp=None,
            top_p=None,
            batch=None,
            ubatch=None,
            gpu_layers=None,
            flash_attn=None,
            runtime_label=None,
            reasoning_mode=None,
            allow_extreme_context=False,
            out=None,
            auto_name=False,
            runs_root=tmp_path / "results",
            run_name=None,
            dry_run=True,
        )
    assert "does not support backend=vllm" in str(exc.value)
    assert "execute" not in calls


def test_resolve_contained_valid_relative(tmp_path: Path) -> None:
    result_dir = tmp_path / "result"
    nested = result_dir / "request"
    nested.mkdir(parents=True)
    target = nested / "p1.json"
    target.write_text("{}", encoding="utf-8")
    resolved = resolve_contained_result_artifact(
        result_dir,
        "request/p1.json",
        label="request_evidence_path",
    )
    assert resolved == target


def test_resolve_contained_rejects_traversal(tmp_path: Path) -> None:
    result_dir = tmp_path / "result"
    result_dir.mkdir()
    (tmp_path / "secret.txt").write_text("nope", encoding="utf-8")
    with pytest.raises(FingerprintUnavailable) as exc:
        resolve_contained_result_artifact(
            result_dir,
            "../secret.txt",
            label="request_evidence_path",
        )
    assert "must be relative" in str(exc.value)


def test_resolve_contained_rejects_absolute(tmp_path: Path) -> None:
    result_dir = tmp_path / "result"
    result_dir.mkdir()
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")
    with pytest.raises(FingerprintUnavailable) as exc:
        resolve_contained_result_artifact(
            result_dir,
            str(outside),
            label="runtime.vllm_runtime_evidence_path",
        )
    assert "must be relative" in str(exc.value)


def test_resolve_contained_nested_path(tmp_path: Path) -> None:
    result_dir = tmp_path / "result"
    path = result_dir / "a" / "b" / "c.json"
    path.parent.mkdir(parents=True)
    path.write_text("{}", encoding="utf-8")
    resolved = resolve_contained_result_artifact(
        result_dir,
        "a/b/c.json",
        label="nested",
    )
    assert resolved == path


def test_resolve_contained_rejects_symlink_escape(tmp_path: Path) -> None:
    result_dir = tmp_path / "result"
    result_dir.mkdir()
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")
    link = result_dir / "escape.json"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("symlinks not supported")
    with pytest.raises(FingerprintUnavailable) as exc:
        resolve_contained_result_artifact(
            result_dir,
            "escape.json",
            label="request_evidence_path",
        )
    assert "escapes result directory" in str(exc.value)


def test_validation_rejects_escaping_request_evidence_path(tmp_path: Path) -> None:
    result_dir = tmp_path / "result"
    (result_dir / "raw").mkdir(parents=True)
    (result_dir / "logs").mkdir(parents=True)
    write_text(result_dir / "raw/p.prompt.md", "p")
    write_text(result_dir / "raw/p.output.txt", "o")
    write_text(result_dir / "logs/p.stderr.log", "e")
    data = {
        "schema_version": "llmgauge.result.v0",
        "llmgauge_version": "0.70.0",
        "run": {"run_id": "r", "status": "completed"},
        "model": {
            "model_id": "m",
            "model_path": "redacted",
            "model_path_policy": "redacted",
        },
        "runtime": {
            "backend": "vllm",
            "vllm_runtime_evidence_captured": True,
            "vllm_runtime_evidence_path": "../escape.json",
        },
        "suite": {"suite_id": "core-v1", "prompt_count": 1},
        "summary": {"completed": 1, "failed": 0},
        "results": [
            {
                "prompt_id": "p",
                "category": "c",
                "status": "completed",
                "raw_prompt_path": "raw/p.prompt.md",
                "raw_output_path": "raw/p.output.txt",
                "stderr_log_path": "logs/p.stderr.log",
                "request_evidence_path": "../escape.json",
                "exit_status": 0,
                "metrics": {},
            }
        ],
    }
    write_json(result_dir / "llmgauge-result.json", data)
    errors = validate_result_data(result_dir, data)
    joined = "\n".join(errors)
    assert "must be relative" in joined


def test_vllm_rejects_model_path(tmp_path: Path, monkeypatch) -> None:
    cfg = tmp_path / "cfg.yaml"
    cfg.write_text(
        "schema_version: llmgauge.config.v0\n"
        "runtime:\n"
        "  backend: vllm\n"
        "  vllm_endpoint: http://127.0.0.1:8000\n"
        "  served_model: test-model\n",
        encoding="utf-8",
    )
    profiles = tmp_path / "profiles.yaml"
    profiles.write_text(
        "schema_version: llmgauge.model_profiles.v0\n"
        "models:\n"
        "  m:\n"
        "    label: m\n"
        "    backend: vllm\n"
        "    served_model: test-model\n"
        "    vllm_endpoint: http://127.0.0.1:8000\n",
        encoding="utf-8",
    )
    with pytest.raises(typer.BadParameter) as exc:
        run_helpers.resolve_run_options(
            model_id="m",
            model_profile="m",
            config_path=cfg,
            model_profiles_path=profiles,
            model_path=tmp_path / "model.gguf",
            llama_cli=None,
            ctx=None,
            max_tokens=None,
            temp=None,
            top_p=None,
            batch=None,
            ubatch=None,
            gpu_layers=None,
        )
    assert "does not accept --model-path" in str(exc.value)


def test_vllm_rejects_profile_path(tmp_path: Path) -> None:
    cfg = tmp_path / "cfg.yaml"
    cfg.write_text("schema_version: llmgauge.config.v0\n", encoding="utf-8")
    model_file = tmp_path / "weights.gguf"
    model_file.write_text("x", encoding="utf-8")
    profiles = tmp_path / "profiles.yaml"
    profiles.write_text(
        "schema_version: llmgauge.model_profiles.v0\n"
        "models:\n"
        "  m:\n"
        "    label: m\n"
        "    backend: vllm\n"
        "    path: " + str(model_file) + "\n"
        "    served_model: test-model\n"
        "    vllm_endpoint: http://127.0.0.1:8000\n",
        encoding="utf-8",
    )
    with pytest.raises(typer.BadParameter) as exc:
        run_helpers.resolve_run_options(
            model_id=None,
            model_profile="m",
            config_path=cfg,
            model_profiles_path=profiles,
            model_path=None,
            llama_cli=None,
            ctx=None,
            max_tokens=None,
            temp=None,
            top_p=None,
            batch=None,
            ubatch=None,
            gpu_layers=None,
        )
    assert "profile path" in str(exc.value)


def test_vllm_resolve_without_path_ok(tmp_path: Path) -> None:
    cfg = tmp_path / "cfg.yaml"
    cfg.write_text("schema_version: llmgauge.config.v0\n", encoding="utf-8")
    profiles = tmp_path / "profiles.yaml"
    profiles.write_text(
        "schema_version: llmgauge.model_profiles.v0\n"
        "models:\n"
        "  m:\n"
        "    label: m\n"
        "    backend: vllm\n"
        "    served_model: test-model\n"
        "    vllm_endpoint: http://127.0.0.1:8000\n",
        encoding="utf-8",
    )
    resolved = run_helpers.resolve_run_options(
        model_id=None,
        model_profile="m",
        config_path=cfg,
        model_profiles_path=profiles,
        model_path=None,
        llama_cli=None,
        ctx=None,
        max_tokens=None,
        temp=None,
        top_p=None,
        batch=None,
        ubatch=None,
        gpu_layers=None,
    )
    assert resolved["backend"] == "vllm"
    assert resolved["model_path"] is None
    assert resolved["served_model"] == "test-model"
