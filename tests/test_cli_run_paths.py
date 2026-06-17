from pathlib import Path
from types import SimpleNamespace

import llmgauge.cli as cli


def test_execute_run_resolves_builtin_suite_prompt_paths(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    def fake_run_llama_cpp(config, prompt):
        return SimpleNamespace(
            command=[
                str(config.llama_cli),
                "--model",
                str(config.model_path),
            ],
            stdout="[ Prompt: 100.0 t/s | Generation: 50.0 t/s ]",
            stderr="",
            exit_status=0,
        )

    monkeypatch.setattr(cli, "run_llama_cpp", fake_run_llama_cpp)

    result = cli._execute_run(
        suite=Path("agent-backend-v1"),
        only="tool-honesty/fake-tool-resistance",
        include="all",
        resolved={
            "model_id": "test-model",
            "model_profile": "test-profile",
            "profile": {
                "label": "Test Model",
                "family": "Test",
                "role": "test",
                "quant": "test",
            },
            "config_path": None,
            "model_profiles_path": None,
            "model_path": Path("/models/test.gguf"),
            "llama_cli": Path("/bin/llama-cli"),
            "ctx": 8192,
            "max_tokens": 64,
            "temp": 0.2,
            "top_p": 0.95,
            "batch": 256,
            "ubatch": 64,
            "gpu_layers": 999,
            "vram_min_headroom_warn_mib": None,
        },
        out=tmp_path / "result",
        fail_on_failed_prompts=True,
    )

    assert result["run"]["status"] == "completed"
    assert result["suite"]["suite_id"] == "agent-backend-v1"
    assert result["summary"]["completed"] == 1
    assert result["summary"]["failed"] == 0

    raw_prompt = (
        tmp_path / "result" / "raw" / "tool-honesty" / "fake-tool-resistance.prompt.md"
    )
    raw_output = (
        tmp_path / "result" / "raw" / "tool-honesty" / "fake-tool-resistance.output.txt"
    )

    assert raw_prompt.exists()
    assert raw_output.exists()
    assert "Fake Tool Resistance" in raw_prompt.read_text(encoding="utf-8")


def test_execute_run_records_vram_guardrail_warning(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    def fake_run_llama_cpp(config, prompt):
        return SimpleNamespace(
            command=[
                str(config.llama_cli),
                "--model",
                str(config.model_path),
            ],
            stdout="[ Prompt: 100.0 t/s | Generation: 50.0 t/s ]",
            stderr="",
            exit_status=0,
            vram_samples=[],
            vram_summary={
                "schema_version": "llmgauge.vram.summary.v0",
                "available": True,
                "peak_used_mib": 11800,
                "peak_total_mib": 12227,
            },
        )

    monkeypatch.setattr(cli, "run_llama_cpp", fake_run_llama_cpp)

    result = cli._execute_run(
        suite=Path("agent-backend-v1"),
        only="tool-honesty/fake-tool-resistance",
        include="all",
        resolved={
            "model_id": "test-model",
            "model_profile": "test-profile",
            "profile": {
                "label": "Test Model",
                "family": "Test",
                "role": "test",
                "quant": "test",
            },
            "config_path": None,
            "model_profiles_path": None,
            "model_path": Path("/models/test.gguf"),
            "llama_cli": Path("/bin/llama-cli"),
            "ctx": 8192,
            "max_tokens": 64,
            "temp": 0.2,
            "top_p": 0.95,
            "batch": 256,
            "ubatch": 64,
            "gpu_layers": 999,
            "vram_min_headroom_warn_mib": 1000,
        },
        out=tmp_path / "result",
        fail_on_failed_prompts=True,
    )

    guardrails = result["results"][0]["vram_guardrails"]

    assert guardrails["schema_version"] == "llmgauge.vram.guardrails.v0"
    assert guardrails["status"] == "warning"
    assert guardrails["min_headroom_warn_mib"] == 1000
    assert guardrails["observed_headroom_mib"] == 427
    assert guardrails["warnings"] == ["vram_headroom_below_warning_threshold"]
    assert result["runtime"]["vram_min_headroom_warn_mib"] == 1000


def test_execute_run_records_vram_guardrail_ok(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    def fake_run_llama_cpp(config, prompt):
        return SimpleNamespace(
            command=[
                str(config.llama_cli),
                "--model",
                str(config.model_path),
            ],
            stdout="[ Prompt: 100.0 t/s | Generation: 50.0 t/s ]",
            stderr="",
            exit_status=0,
            vram_samples=[],
            vram_summary={
                "schema_version": "llmgauge.vram.summary.v0",
                "available": True,
                "peak_used_mib": 7000,
                "peak_total_mib": 12227,
            },
        )

    monkeypatch.setattr(cli, "run_llama_cpp", fake_run_llama_cpp)

    result = cli._execute_run(
        suite=Path("agent-backend-v1"),
        only="tool-honesty/fake-tool-resistance",
        include="all",
        resolved={
            "model_id": "test-model",
            "model_profile": "test-profile",
            "profile": {
                "label": "Test Model",
                "family": "Test",
                "role": "test",
                "quant": "test",
            },
            "config_path": None,
            "model_profiles_path": None,
            "model_path": Path("/models/test.gguf"),
            "llama_cli": Path("/bin/llama-cli"),
            "ctx": 8192,
            "max_tokens": 64,
            "temp": 0.2,
            "top_p": 0.95,
            "batch": 256,
            "ubatch": 64,
            "gpu_layers": 999,
            "vram_min_headroom_warn_mib": 1000,
        },
        out=tmp_path / "result",
        fail_on_failed_prompts=True,
    )

    guardrails = result["results"][0]["vram_guardrails"]

    assert guardrails["status"] == "ok"
    assert guardrails["observed_headroom_mib"] == 5227
    assert guardrails["warnings"] == []
