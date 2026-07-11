import json
from pathlib import Path

from llmgauge.core.runtime_command import (
    RUNTIME_COMMAND_FILENAME,
    build_runtime_command_document,
    resolve_model_source,
    resolve_reasoning_mode,
    resolve_reasoning_mode_requested_from_metadata,
)
from llmgauge.runners.llama_cpp import LlamaCppRunConfig, build_llama_command


def _config(*, reasoning_mode: str = "off") -> LlamaCppRunConfig:
    return LlamaCppRunConfig(
        llama_cli=Path("/bin/llama-cli"),
        model_path=Path("/models/model.gguf"),
        ctx_size=8192,
        max_tokens=800,
        temperature=0.2,
        top_p=0.95,
        batch_size=256,
        ubatch_size=64,
        gpu_layers=999,
        flash_attn="auto",
        reasoning_mode=reasoning_mode,
    )


def _resolved(*, model_profile: str | None = "test-profile") -> dict:
    return {
        "model_id": "test-model",
        "model_profile": model_profile,
        "model_source": resolve_model_source(model_profile=model_profile),
        "runtime_label": "stock-reference",
        "reasoning_mode": "off",
    }


def test_resolve_model_source_profile_vs_direct_path() -> None:
    assert resolve_model_source(model_profile="nemotron") == "model_profile"
    assert resolve_model_source(model_profile=None) == "direct_model_path"


def test_resolve_reasoning_mode_defaults_to_off() -> None:
    assert (
        resolve_reasoning_mode(cli_value=None, profile={}, config_data={}) == "off"
    )


def test_resolve_reasoning_mode_cli_overrides_profile() -> None:
    resolved = resolve_reasoning_mode(
        cli_value="default",
        profile={"reasoning_mode": "on"},
        config_data={"defaults": {"reasoning_mode": "auto"}},
    )
    assert resolved == "default"


def test_reasoning_mode_requested_metadata_prefers_additive_field() -> None:
    runtime = {
        "reasoning_mode": "off",
        "reasoning_mode_requested": "auto",
    }

    assert resolve_reasoning_mode_requested_from_metadata(runtime) == "auto"


def test_reasoning_mode_requested_metadata_accepts_legacy_and_missing_values() -> None:
    assert (
        resolve_reasoning_mode_requested_from_metadata({"reasoning_mode": "default"})
        == "default"
    )
    assert resolve_reasoning_mode_requested_from_metadata({}) == "unknown"


def test_build_llama_command_off_includes_reasoning_flag() -> None:
    command = build_llama_command(_config(reasoning_mode="off"), "hello")
    assert command[command.index("--reasoning") + 1] == "off"


def test_build_llama_command_default_omits_reasoning_flag() -> None:
    command = build_llama_command(_config(reasoning_mode="default"), "hello")
    assert "--reasoning" not in command


def test_build_runtime_command_document_redacts_model_path() -> None:
    document = build_runtime_command_document(
        config=_config(),
        resolved=_resolved(),
        suite_id="wumbolabs-practical-v1",
        suite_version="0.2.0",
        timestamp_utc="2026-07-08T00:00:00+00:00",
    )

    assert document["schema_version"] == "llmgauge.runtime_command.v0"
    assert document["model_path"] == "redacted"
    assert document["model_source"] == "model_profile"
    assert document["reasoning_mode"] == "off"
    assert "REDACTED_MODEL_PATH" in document["command_argv"]
    assert "/models/model.gguf" not in document["command_argv"]


def test_execute_run_writes_runtime_command_json(tmp_path: Path, monkeypatch) -> None:
    from types import SimpleNamespace

    from llmgauge.commands import run_helpers

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    model_path = tmp_path / "model.bin"
    model_path.write_bytes(b"test model")
    llama_cli = tmp_path / "llama-cli"
    llama_cli.write_bytes(b"test executable")

    def fake_run_llama_cpp(config, prompt):
        return SimpleNamespace(
            command=build_llama_command(config, prompt),
            stdout="answer\n",
            stderr="",
            exit_status=0,
        )

    monkeypatch.setattr(run_helpers, "run_llama_cpp", fake_run_llama_cpp)
    monkeypatch.setattr(
        run_helpers,
        "discover_llama_runtime_identity",
        lambda path: {
            "reported_version": "b1234",
            "commit": "abcdef1",
            "build_number": "1234",
            "build_type": "Release",
            "build_metadata": "gcc 13.2.0",
            "discovery_status": "available",
        },
    )

    resolved = {
        "model_id": "test-model",
        "model_profile": "test-profile",
        "model_source": "model_profile",
        "profile": {"label": "Test Model"},
        "config_path": None,
        "model_profiles_path": None,
        "model_path": model_path,
        "llama_cli": llama_cli,
        "ctx": 8192,
        "max_tokens": 64,
        "temp": 0.2,
        "top_p": 0.95,
        "batch": 256,
        "ubatch": 64,
        "gpu_layers": 999,
        "flash_attn": "auto",
        "runtime_label": None,
        "reasoning_mode": "off",
        "vram_min_headroom_warn_mib": None,
    }

    result = run_helpers.execute_run(
        suite=Path("agent-backend-v1"),
        only="tool-honesty/fake-tool-resistance",
        include="all",
        resolved=resolved,
        out=tmp_path / "result",
        fail_on_failed_prompts=True,
    )

    command_path = tmp_path / "result" / RUNTIME_COMMAND_FILENAME
    assert command_path.exists()

    command_data = json.loads(command_path.read_text(encoding="utf-8"))
    assert command_data["reasoning_mode"] == "off"
    assert command_data["model_source"] == "model_profile"

    assert result["model"]["model_source"] == "model_profile"
    assert result["model"]["provenance"]["status"] == "available"
    assert result["model"]["provenance"]["filename"] == "model.bin"
    assert result["model"]["provenance"]["sha256"]
    assert result["runtime"]["backend_provenance"]["status"] == "available"
    assert (
        result["runtime"]["backend_provenance"]["executable_filename"]
        == "llama-cli"
    )
    assert result["runtime"]["backend_provenance"]["executable_sha256"]
    assert (
        result["runtime"]["backend_provenance"]["reported_version"] == "b1234"
    )
    assert result["runtime"]["backend_provenance"]["commit"] == "abcdef1"
    assert str(tmp_path) not in str(result["runtime"]["backend_provenance"])
    assert result["runtime"]["reasoning_mode"] == "off"
    assert result["runtime"]["runtime_command_captured"] is True
    assert result["runtime"]["runtime_command_path"] == RUNTIME_COMMAND_FILENAME
