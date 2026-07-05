from pathlib import Path
import subprocess

from llmgauge.runners import llama_cpp
from llmgauge.runners.llama_cpp import LlamaCppRunConfig, run_llama_cpp


def _config() -> LlamaCppRunConfig:
    return LlamaCppRunConfig(
        llama_cli=Path("/bin/llama-cli"),
        model_path=Path("/models/model.gguf"),
        ctx_size=8192,
        max_tokens=100,
        temperature=0.2,
        top_p=0.95,
        batch_size=256,
        ubatch_size=64,
        gpu_layers=999,
    )


def test_run_llama_cpp_captures_vram(monkeypatch) -> None:
    class FakeProcess:
        def __init__(self) -> None:
            self.returncode = 0
            self.calls = 0

        def communicate(self, timeout=None):
            self.calls += 1
            if self.calls == 1:
                raise subprocess.TimeoutExpired(cmd=["llama-cli"], timeout=timeout)
            return ("stdout text", "stderr text")

    captured = {}

    def fake_popen(command, stdout, stderr, text):
        captured["command"] = command
        captured["stdout"] = stdout
        captured["stderr"] = stderr
        captured["text"] = text
        return FakeProcess()

    reports = [
        {
            "available": True,
            "samples": [
                {
                    "timestamp_utc": "2026-06-17T04:30:00+00:00",
                    "gpu_index": 0,
                    "gpu_name": "NVIDIA GeForce RTX 5070",
                    "used_mib": 4000,
                    "total_mib": 12227,
                }
            ],
        },
        {
            "available": True,
            "samples": [
                {
                    "timestamp_utc": "2026-06-17T04:30:01+00:00",
                    "gpu_index": 0,
                    "gpu_name": "NVIDIA GeForce RTX 5070",
                    "used_mib": 9000,
                    "total_mib": 12227,
                }
            ],
        },
        {
            "available": True,
            "samples": [
                {
                    "timestamp_utc": "2026-06-17T04:30:02+00:00",
                    "gpu_index": 0,
                    "gpu_name": "NVIDIA GeForce RTX 5070",
                    "used_mib": 7000,
                    "total_mib": 12227,
                }
            ],
        },
    ]

    def fake_sample_nvidia_smi_memory():
        return reports.pop(0)

    monkeypatch.setattr(llama_cpp.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(
        llama_cpp,
        "sample_nvidia_smi_memory",
        fake_sample_nvidia_smi_memory,
    )

    result = run_llama_cpp(_config(), "hello", vram_poll_seconds=0.1)

    assert result.exit_status == 0
    assert result.stdout == "stdout text"
    assert result.stderr == "stderr text"
    assert result.vram_summary is not None
    assert result.vram_summary["available"] is True
    assert result.vram_summary["peak_used_mib"] == 9000
    assert len(result.vram_samples) == 3
    assert captured["stdout"] == subprocess.PIPE
    assert captured["stderr"] == subprocess.PIPE
    assert captured["text"] is True


def test_run_llama_cpp_handles_unavailable_vram(monkeypatch) -> None:
    class FakeProcess:
        returncode = 0

        def communicate(self, timeout=None):
            return ("stdout text", "stderr text")

    def fake_popen(command, stdout, stderr, text):
        return FakeProcess()

    def fake_sample_nvidia_smi_memory():
        return {
            "available": False,
            "samples": [],
            "error": "nvidia-smi not found",
        }

    monkeypatch.setattr(llama_cpp.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(
        llama_cpp,
        "sample_nvidia_smi_memory",
        fake_sample_nvidia_smi_memory,
    )

    result = run_llama_cpp(_config(), "hello", vram_poll_seconds=0.1)

    assert result.exit_status == 0
    assert result.vram_samples == []
    assert result.vram_summary is not None
    assert result.vram_summary["available"] is False
    assert result.vram_summary["error"] == "nvidia-smi not found"


def test_build_llama_command_includes_flash_attention_mode() -> None:
    config = LlamaCppRunConfig(
        llama_cli=Path("/bin/llama-cli"),
        model_path=Path("/models/model.gguf"),
        ctx_size=8192,
        max_tokens=100,
        temperature=0.2,
        top_p=0.95,
        batch_size=1024,
        ubatch_size=256,
        gpu_layers=999,
        flash_attn="on",
    )

    command = llama_cpp.build_llama_command(config, "hello")

    assert "-fa" in command
    assert command[command.index("-fa") + 1] == "on"
