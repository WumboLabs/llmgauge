from __future__ import annotations

from copy import deepcopy

from pathlib import Path

from typer.testing import CliRunner

from llmgauge.cli import app
from llmgauge.commands import run_helpers
import pytest

from llmgauge.core.compare import build_compare_report
from llmgauge.core.reports import _runtime_section_lines
from llmgauge.core.run_fingerprint import (
    RUN_FINGERPRINT_SCHEMA_VERSION_V5,
    _fingerprint_versions,
)
from llmgauge.core.sampling_profiles import (
    SamplingProfileError,
    builtin_sampling_profile_ids,
    canonical_settings_sha256,
    resolve_sampling_profile,
    validate_runtime_profile,
)


def test_builtin_profile_has_deterministic_canonical_identity() -> None:
    first = resolve_sampling_profile({}, "controlled-deterministic-v1")
    second = resolve_sampling_profile({}, "controlled-deterministic-v1")

    assert first == second
    assert first is not None
    assert first["profile_kind"] == "controlled"
    assert first["canonical_settings_sha256"] == canonical_settings_sha256(
        first["settings"]
    )


def test_custom_profile_requires_closed_canonical_settings() -> None:
    with pytest.raises(
        SamplingProfileError, match="must contain exactly supported keys"
    ):
        resolve_sampling_profile(
            {
                "sampling_profiles": {
                    "bad": {
                        "profile_version": "1",
                        "profile_kind": "controlled",
                        "settings": {"temperature": 0.0},
                    }
                }
            },
            "bad",
        )


def test_runtime_profile_rejects_hash_and_runtime_contradictions() -> None:
    profile = resolve_sampling_profile({}, "controlled-deterministic-v1")
    assert profile is not None
    evidence = {**profile, "overrides": []}
    runtime = deepcopy(profile["settings"])

    assert validate_runtime_profile(evidence, runtime) == []
    evidence["canonical_settings_sha256"] = "0" * 64
    assert "does not match settings" in validate_runtime_profile(evidence, runtime)[0]

    evidence["canonical_settings_sha256"] = profile["canonical_settings_sha256"]
    runtime["temperature"] = 0.8
    assert (
        "disagrees with runtime.temperature"
        in validate_runtime_profile(evidence, runtime)[0]
    )


def test_runtime_profile_allows_recorded_cli_override() -> None:
    profile = resolve_sampling_profile({}, "controlled-deterministic-v1")
    assert profile is not None
    evidence = {**profile, "overrides": ["temperature"]}
    runtime = {**profile["settings"], "temperature": 0.8}

    assert validate_runtime_profile(evidence, runtime) == []


_VENDOR_SETTINGS = {
    "qwen3-thinking-v1": {
        "min_p": 0.0,
        "reasoning_budget": None,
        "reasoning_effort": None,
        "reasoning_mode": "on",
        "seed": None,
        "temperature": 0.6,
        "top_k": 20,
        "top_p": 0.95,
    },
    "qwen3-nonthinking-v1": {
        "min_p": 0.0,
        "reasoning_budget": None,
        "reasoning_effort": None,
        "reasoning_mode": "off",
        "seed": None,
        "temperature": 0.7,
        "top_k": 20,
        "top_p": 0.8,
    },
    "gemma-4-instruct-v1": {
        "min_p": None,
        "reasoning_budget": None,
        "reasoning_effort": None,
        "reasoning_mode": "default",
        "seed": None,
        "temperature": 1.0,
        "top_k": 64,
        "top_p": 0.95,
    },
    "deepseek-r1-v1": {
        "min_p": None,
        "reasoning_budget": None,
        "reasoning_effort": None,
        "reasoning_mode": "default",
        "seed": None,
        "temperature": 0.6,
        "top_k": None,
        "top_p": 0.95,
    },
}


def test_builtin_ids_are_unique_and_include_controlled_and_vendor() -> None:
    ids = builtin_sampling_profile_ids()
    assert ids == tuple(sorted(ids, key=str))
    assert len(ids) == len(set(ids))
    assert "controlled-deterministic-v1" in ids
    for profile_id in _VENDOR_SETTINGS:
        assert profile_id in ids


def test_vendor_aligned_builtins_have_expected_identity() -> None:
    hashes = set()
    for profile_id, settings in _VENDOR_SETTINGS.items():
        first = resolve_sampling_profile({}, profile_id)
        second = resolve_sampling_profile({}, profile_id)
        assert first == second
        assert first is not None
        assert first["profile_version"] == "1"
        assert first["profile_kind"] == "vendor_aligned"
        assert first["source"] == "builtin"
        assert first["settings"] == settings
        digest = canonical_settings_sha256(settings)
        assert first["canonical_settings_sha256"] == digest
        hashes.add(digest)
    assert len(hashes) == len(_VENDOR_SETTINGS)


def test_unknown_sampling_profile_fails_closed() -> None:
    with pytest.raises(SamplingProfileError, match="not found"):
        resolve_sampling_profile({}, "not-a-real-profile")


def test_vendor_profile_runtime_evidence_keeps_requested_settings() -> None:
    profile = resolve_sampling_profile({}, "qwen3-thinking-v1")
    assert profile is not None
    evidence = {**profile, "overrides": []}
    runtime = deepcopy(profile["settings"])
    assert validate_runtime_profile(evidence, runtime) == []


def test_vendor_profile_selects_v5_fingerprint_version() -> None:
    profile = resolve_sampling_profile({}, "gemma-4-instruct-v1")
    other = resolve_sampling_profile({}, "deepseek-r1-v1")
    assert profile is not None and other is not None
    schema, _payload = _fingerprint_versions(
        {"runtime": {"profile": {**profile, "overrides": []}}}
    )
    assert schema == RUN_FINGERPRINT_SCHEMA_VERSION_V5
    assert profile["canonical_settings_sha256"] != other["canonical_settings_sha256"]


def test_report_discloses_vendor_aligned_without_endorsement() -> None:
    profile = resolve_sampling_profile({}, "qwen3-thinking-v1")
    assert profile is not None
    lines = _runtime_section_lines(
        {"backend": "llama.cpp", "profile": {**profile, "overrides": []}}
    )
    joined = "\n".join(lines)
    assert "Sampling profile: qwen3-thinking-v1" in joined
    assert "Sampling profile kind: vendor_aligned" in joined
    assert "does not prove semantic model reasoning" in joined
    assert "endors" not in joined.lower()
    assert "compatible" not in joined.lower()


def test_compare_discloses_operator_declared_vendor_alignment() -> None:
    profile = resolve_sampling_profile({}, "deepseek-r1-v1")
    assert profile is not None
    result = {
        "run": {"run_id": "run-a", "status": "completed"},
        "model": {"model_id": "model-a"},
        "suite": {"suite_id": "core-v1"},
        "runtime": {
            "backend": "llama.cpp",
            "ctx_size": 8192,
            "max_tokens": 600,
            "temperature": 0.6,
            "top_p": 0.95,
            "batch_size": 256,
            "ubatch_size": 64,
            "gpu_layers": 999,
            "flash_attn": "on",
            "runtime_label": "daily-tuned",
            "profile": {**profile, "overrides": []},
        },
        "summary": {
            "completed": 1,
            "failed": 0,
            "scored_prompt_count": None,
            "manual_score_total": None,
            "manual_score_max": None,
            "manual_score_average": None,
            "failure_labels": {},
            "good_labels": {},
        },
        "results": [{"prompt_id": "honesty-unknown-tool", "metrics": {}}],
    }
    report = build_compare_report([result, deepcopy(result)])
    assert "Sampling profile provenance:" in report
    assert "deepseek-r1-v1" in report
    assert "operator-declared" in report
    assert "not vendor endorsement" in report


def test_run_dry_run_resolves_vendor_sampling_profile(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    examples_dir = tmp_path / "examples" / "configs"
    examples_dir.mkdir(parents=True)
    llama_cli = tmp_path / "llama-cli"
    llama_cli.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    llama_cli.chmod(0o755)
    model_path = tmp_path / "model.gguf"
    model_path.write_text("fake model placeholder\n", encoding="utf-8")
    monkeypatch.setattr(
        run_helpers,
        "collect_backend_provenance",
        lambda path: (_ for _ in ()).throw(
            AssertionError("dry-run must not collect executable provenance")
        ),
    )
    (examples_dir / "llmgauge.local.yaml").write_text(
        f"""schema_version: llmgauge.config.v0
runtime:
  llama_cli: {llama_cli}
""",
        encoding="utf-8",
    )
    (examples_dir / "model-profiles.local.yaml").write_text(
        f"""schema_version: llmgauge.model_profiles.v0
models:
  example_model:
    label: Example Model
    path: {model_path}
""",
        encoding="utf-8",
    )
    result = CliRunner().invoke(
        app,
        [
            "run",
            "--suite",
            "core-v1",
            "--include",
            "honesty",
            "--model-profile",
            "example_model",
            "--sampling-profile",
            "qwen3-thinking-v1",
            "--dry-run",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "qwen3-thinking-v1" in result.output
    assert "vendor_aligned" in result.output
    assert "0.6" in result.output


def test_run_unknown_sampling_profile_fails_before_launch(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    examples_dir = tmp_path / "examples" / "configs"
    examples_dir.mkdir(parents=True)
    llama_cli = tmp_path / "llama-cli"
    llama_cli.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    llama_cli.chmod(0o755)
    model_path = tmp_path / "model.gguf"
    model_path.write_text("fake\n", encoding="utf-8")
    (examples_dir / "llmgauge.local.yaml").write_text(
        f"""schema_version: llmgauge.config.v0
runtime:
  llama_cli: {llama_cli}
""",
        encoding="utf-8",
    )
    (examples_dir / "model-profiles.local.yaml").write_text(
        f"""schema_version: llmgauge.model_profiles.v0
models:
  example_model:
    label: Example Model
    path: {model_path}
""",
        encoding="utf-8",
    )
    result = CliRunner().invoke(
        app,
        [
            "run",
            "--suite",
            "core-v1",
            "--include",
            "honesty",
            "--model-profile",
            "example_model",
            "--sampling-profile",
            "missing-profile",
            "--dry-run",
        ],
    )
    assert result.exit_code != 0
    combined = (result.output or "") + (result.stderr or "") + str(result.exception)
    assert "not found" in combined.lower() or "Sampling profile" in combined
