from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from llmgauge.core.vram import sample_nvidia_smi_memory, summarize_vram_samples


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


@dataclass(frozen=True)
class LlamaCppRunResult:
    command: list[str]
    stdout: str
    stderr: str
    exit_status: int
    vram_samples: list[dict[str, Any]] = field(default_factory=list)
    vram_summary: dict[str, Any] | None = None


def build_llama_command(config: LlamaCppRunConfig, prompt: str) -> list[str]:
    return [
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
        "--reasoning",
        "off",
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
) -> LlamaCppRunResult:
    command = build_llama_command(config, prompt)
    vram_samples: list[dict[str, Any]] = []
    vram_errors: list[str] = []

    poll_seconds = max(vram_poll_seconds, 0.1)

    if capture_vram:
        _capture_vram_sample(vram_samples, vram_errors)

    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    while True:
        try:
            stdout, stderr = process.communicate(timeout=poll_seconds)
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
        vram_samples=vram_samples,
        vram_summary=_build_vram_summary(vram_samples, vram_errors)
        if capture_vram
        else None,
    )
