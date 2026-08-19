from dataclasses import replace
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
    assert result.elapsed_seconds is not None
    assert result.elapsed_seconds >= 0


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


def test_run_llama_cpp_enforces_total_timeout(monkeypatch) -> None:
    class FakeProcess:
        returncode = -9

        def __init__(self) -> None:
            self.killed = False

        def kill(self) -> None:
            self.killed = True

        def communicate(self, timeout=None):
            assert self.killed is True
            assert timeout is None
            return ("partial stdout", "runtime stderr")

    process = FakeProcess()
    monotonic_values = iter([0.0, 2.0, 3.0])
    monkeypatch.setattr(llama_cpp.subprocess, "Popen", lambda *args, **kwargs: process)
    monkeypatch.setattr(llama_cpp.time, "monotonic", lambda: next(monotonic_values))

    result = run_llama_cpp(
        _config(),
        "hello",
        capture_vram=False,
        timeout_seconds=1.0,
    )

    assert result.timed_out is True
    assert result.exit_status == -9
    assert result.stdout == "partial stdout"
    assert "per-turn timeout" in result.stderr
    assert result.elapsed_seconds == 3.0


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
    assert command[command.index("--reasoning") + 1] == "off"


def test_build_llama_command_default_reasoning_mode_omits_flag() -> None:
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
        reasoning_mode="default",
    )

    command = llama_cpp.build_llama_command(config, "hello")

    assert "--reasoning" not in command


def test_build_llama_command_includes_extended_runtime_controls() -> None:
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
        top_k=20,
        seed=424242,
        cache_type_k="q8_0",
        cache_type_v="q4_0",
        reasoning_effort="medium",
        reasoning_budget=16384,
        fit="off",
        reasoning_preserve=True,
        spec_type="draft-mtp",
    )

    command = llama_cpp.build_llama_command(config, "hello")

    assert command[command.index("--parallel") + 1] == "1"
    assert "--kv-offload" in command
    assert command[command.index("--top-k") + 1] == "20"
    assert command[command.index("--seed") + 1] == "424242"
    assert command[command.index("--cache-type-k") + 1] == "q8_0"
    assert command[command.index("--cache-type-v") + 1] == "q4_0"
    assert command[command.index("--reasoning-effort") + 1] == "medium"
    assert command[command.index("--reasoning-budget") + 1] == "16384"
    assert command[command.index("--fit") + 1] == "off"
    assert "--reasoning-preserve" in command
    assert command[command.index("--spec-type") + 1] == "draft-mtp"


def test_build_llama_command_distinguishes_defaults_and_explicit_disables() -> None:
    default_command = llama_cpp.build_llama_command(_config(), "hello")
    disabled_command = llama_cpp.build_llama_command(
        replace(
            _config(),
            fit="on",
            reasoning_preserve=False,
            spec_type="none",
        ),
        "hello",
    )
    assert "--fit" not in default_command
    assert "--reasoning-preserve" not in default_command
    assert "--no-reasoning-preserve" not in default_command
    assert "--spec-type" not in default_command
    assert disabled_command[disabled_command.index("--fit") + 1] == "on"
    assert "--no-reasoning-preserve" in disabled_command
    assert disabled_command[disabled_command.index("--spec-type") + 1] == "none"


def test_run_llama_cpp_transports_large_prompt_by_temporary_file(monkeypatch) -> None:
    class FakeProcess:
        returncode = 0

        def communicate(self, timeout=None):
            return ("answer", "")

    captured: dict[str, str] = {}

    def fake_popen(command, stdout, stderr, text):
        prompt_file = Path(command[command.index("--file") + 1])
        captured["path"] = str(prompt_file)
        captured["content"] = prompt_file.read_text(encoding="utf-8")
        return FakeProcess()

    monkeypatch.setattr(llama_cpp.subprocess, "Popen", fake_popen)

    prompt = "x" * (llama_cpp.PROMPT_FILE_THRESHOLD_BYTES + 1)
    result = run_llama_cpp(_config(), prompt, capture_vram=False)

    assert result.exit_status == 0
    assert result.prompt_transport["mode"] == "file"
    assert captured["content"] == prompt
    assert not Path(captured["path"]).exists()
