from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from llmgauge.core.vram import sample_nvidia_smi_memory, summarize_vram_samples


def reasoning_flag_for_mode(mode: str) -> str | None:
    if mode in {"off", "on", "auto"}:
        return mode
    return None


@dataclass(frozen=True)
class LlamaCppRunConfig:
    llama_cli: Path
    model_path: Path
    ctx_size: int
    max_tokens: int
    temperature: float
    top_p: float
    batch_size: int
    ubatch_size: int
    gpu_layers: int
    flash_attn: str = "auto"
    reasoning_mode: str = "off"


@dataclass(frozen=True)
class LlamaCppRunResult:
    command: list[str]
    stdout: str
    stderr: str
    exit_status: int
    timed_out: bool = False
    elapsed_seconds: float | None = None
    launch_error: str | None = None
    vram_samples: list[dict[str, Any]] = field(default_factory=list)
    vram_summary: dict[str, Any] | None = None


def build_llama_command(config: LlamaCppRunConfig, prompt: str) -> list[str]:
    command = [
        str(config.llama_cli),
        "--model",
        str(config.model_path),
        "--ctx-size",
        str(config.ctx_size),
        "--batch-size",
        str(config.batch_size),
        "--ubatch-size",
        str(config.ubatch_size),
        "--n-gpu-layers",
        str(config.gpu_layers),
        "-fa",
        config.flash_attn,
    ]

    reasoning_flag = reasoning_flag_for_mode(config.reasoning_mode)
    if reasoning_flag is not None:
        command.extend(["--reasoning", reasoning_flag])

    command.extend(
        [
            "--no-mmproj",
            "--no-display-prompt",
            "--simple-io",
            "--single-turn",
            "--temp",
            str(config.temperature),
            "--top-p",
            str(config.top_p),
            "--n-predict",
            str(config.max_tokens),
            "-p",
            prompt,
        ]
    )
    return command


def _capture_vram_sample(
    samples: list[dict[str, Any]],
    errors: list[str],
) -> None:
    report = sample_nvidia_smi_memory()
    if report.get("available"):
        samples.extend(report.get("samples", []))
        return

    error = report.get("error")
    if isinstance(error, str) and error:
        errors.append(error)


def _build_vram_summary(
    samples: list[dict[str, Any]],
    errors: list[str],
) -> dict[str, Any]:
    summary = summarize_vram_samples(samples)
    if not summary.get("available") and errors:
        summary["error"] = "; ".join(dict.fromkeys(errors))
    return summary


def run_llama_cpp(
    config: LlamaCppRunConfig,
    prompt: str,
    *,
    capture_vram: bool = True,
    vram_poll_seconds: float = 0.5,
    timeout_seconds: float | None = None,
) -> LlamaCppRunResult:
    command = build_llama_command(config, prompt)
    vram_samples: list[dict[str, Any]] = []
    vram_errors: list[str] = []

    poll_seconds = max(vram_poll_seconds, 0.1)
    if timeout_seconds is not None and timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")
    timed_out = False

    if capture_vram:
        _capture_vram_sample(vram_samples, vram_errors)

    started_at = time.monotonic()
    deadline = started_at + timeout_seconds if timeout_seconds is not None else None
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except OSError as exc:
        if capture_vram:
            _capture_vram_sample(vram_samples, vram_errors)
        return LlamaCppRunResult(
            command=command,
            stdout="",
            stderr=f"llmgauge: failed to launch llama-cli: {exc}\n",
            exit_status=1,
            elapsed_seconds=time.monotonic() - started_at,
            launch_error="process_launch_failed",
            vram_samples=vram_samples,
            vram_summary=_build_vram_summary(vram_samples, vram_errors)
            if capture_vram
            else None,
        )

    while True:
        wait_seconds = poll_seconds
        if deadline is not None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                process.kill()
                stdout, stderr = process.communicate()
                stderr = f"{stderr}\nllmgauge: per-turn timeout\n"
                timed_out = True
                break
            wait_seconds = min(wait_seconds, remaining)
        try:
            stdout, stderr = process.communicate(timeout=wait_seconds)
            break
        except subprocess.TimeoutExpired:
            if capture_vram:
                _capture_vram_sample(vram_samples, vram_errors)

    if capture_vram:
        _capture_vram_sample(vram_samples, vram_errors)

    return LlamaCppRunResult(
        command=command,
        stdout=stdout,
        stderr=stderr,
        exit_status=process.returncode if process.returncode is not None else 1,
        timed_out=timed_out,
        elapsed_seconds=time.monotonic() - started_at,
        vram_samples=vram_samples,
        vram_summary=_build_vram_summary(vram_samples, vram_errors)
        if capture_vram
        else None,
    )
