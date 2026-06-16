from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


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


@dataclass(frozen=True)
class LlamaCppRunResult:
    command: list[str]
    stdout: str
    stderr: str
    exit_status: int


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


def run_llama_cpp(config: LlamaCppRunConfig, prompt: str) -> LlamaCppRunResult:
    command = build_llama_command(config, prompt)

    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
    )

    return LlamaCppRunResult(
        command=command,
        stdout=completed.stdout,
        stderr=completed.stderr,
        exit_status=completed.returncode,
    )
