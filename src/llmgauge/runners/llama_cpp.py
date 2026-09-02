from __future__ import annotations

import os
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from llmgauge.core.metrics import retain_native_diagnostics_stderr
from llmgauge.core.native_diagnostics import NATIVE_DIAGNOSTICS_VERBOSITY
from llmgauge.core.vram import sample_nvidia_smi_memory, summarize_vram_samples


def reasoning_flag_for_mode(mode: str) -> str | None:
    if mode in {"off", "on", "auto"}:
        return mode
    return None


PROMPT_FILE_THRESHOLD_BYTES = 64 * 1024


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
    top_k: int | None = None
    min_p: float | None = None
    seed: int | None = None
    cache_type_k: str | None = None
    cache_type_v: str | None = None
    reasoning_effort: str | None = None
    reasoning_budget: int | None = None
    fit: str | None = None
    reasoning_preserve: bool | None = None
    spec_type: str | None = None
    native_diagnostics_capture: bool = False


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
    prompt_transport: dict[str, Any] = field(default_factory=dict)
    diagnostics_capture: dict[str, Any] = field(default_factory=dict)


def build_llama_command(
    config: LlamaCppRunConfig,
    prompt: str,
    *,
    prompt_file: Path | None = None,
) -> list[str]:
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
        "--parallel",
        "1",
        "--n-gpu-layers",
        str(config.gpu_layers),
        "--kv-offload",
        "-fa",
        config.flash_attn,
    ]
    if config.native_diagnostics_capture:
        # Deterministic evidence-capture verbosity for lineage-qualified
        # llama-cli runtimes (load_tensors placement needs >=4; slot
        # print_timing needs >=3 and is covered by the same setting).
        command.extend(["--verbosity", str(NATIVE_DIAGNOSTICS_VERBOSITY)])

    if config.cache_type_k is not None:
        command.extend(["--cache-type-k", config.cache_type_k])
    if config.cache_type_v is not None:
        command.extend(["--cache-type-v", config.cache_type_v])
    if config.fit is not None:
        command.extend(["--fit", config.fit])

    reasoning_flag = reasoning_flag_for_mode(config.reasoning_mode)
    if reasoning_flag is not None:
        command.extend(["--reasoning", reasoning_flag])
    if config.reasoning_effort is not None:
        command.extend(["--reasoning-effort", config.reasoning_effort])
    if config.reasoning_budget is not None:
        command.extend(["--reasoning-budget", str(config.reasoning_budget)])
    if config.reasoning_preserve is True:
        command.append("--reasoning-preserve")
    elif config.reasoning_preserve is False:
        command.append("--no-reasoning-preserve")
    if config.spec_type is not None:
        command.extend(["--spec-type", config.spec_type])

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
        ]
    )
    if config.top_k is not None:
        command.extend(["--top-k", str(config.top_k)])
    if config.min_p is not None:
        command.extend(["--min-p", str(config.min_p)])
    if config.seed is not None:
        command.extend(["--seed", str(config.seed)])
    command.extend(["--n-predict", str(config.max_tokens)])
    if prompt_file is not None:
        command.extend(["--file", str(prompt_file)])
    else:
        command.extend(["-p", prompt])
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
    prompt_bytes = len(prompt.encode("utf-8"))
    prompt_file: Path | None = None
    if prompt_bytes > PROMPT_FILE_THRESHOLD_BYTES:
        descriptor, prompt_file_text = tempfile.mkstemp(
            prefix="llmgauge-prompt-",
            suffix=".txt",
            text=True,
        )
        prompt_file = Path(prompt_file_text)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(prompt)
        command = build_llama_command(config, "", prompt_file=prompt_file)
        prompt_transport = {
            "mode": "file",
            "utf8_bytes": prompt_bytes,
            "file_flag": "--file",
            "temporary_file": True,
        }
    else:
        command = build_llama_command(config, prompt)
        prompt_transport = {
            "mode": "argv",
            "utf8_bytes": prompt_bytes,
            "argument_flag": "--prompt",
            "temporary_file": False,
        }
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
            # Verbosity-4 trace output can contain invalid UTF-8 (vocab
            # dumps). Replace undecodable bytes instead of crashing; the
            # admitted diagnostic grammars are pure ASCII.
            errors="replace",
        )
    except OSError as exc:
        if capture_vram:
            _capture_vram_sample(vram_samples, vram_errors)
        if prompt_file is not None:
            prompt_file.unlink(missing_ok=True)
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
            prompt_transport=prompt_transport,
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

    captured_stderr = stderr
    diagnostics_capture: dict[str, Any] = {}
    succeeded = process.returncode == 0 and not timed_out
    if config.native_diagnostics_capture and succeeded:
        # Verbosity 4 emits unrelated info/trace stderr (buffer sizes,
        # absolute model paths). Successful runs persist only the admitted
        # diagnostic lines plus warning/error output; failed runs keep the
        # full trace so failures stay diagnosable.
        captured_stderr = retain_native_diagnostics_stderr(stderr)
        diagnostics_capture = {
            "effective_verbosity": NATIVE_DIAGNOSTICS_VERBOSITY,
            "stderr_selectively_retained": True,
            "raw_stderr_lines": len(stderr.splitlines()),
            "retained_stderr_lines": len(captured_stderr.splitlines()),
        }

    result = LlamaCppRunResult(
        command=command,
        stdout=stdout,
        stderr=captured_stderr,
        exit_status=process.returncode if process.returncode is not None else 1,
        timed_out=timed_out,
        elapsed_seconds=time.monotonic() - started_at,
        vram_samples=vram_samples,
        vram_summary=_build_vram_summary(vram_samples, vram_errors)
        if capture_vram
        else None,
        prompt_transport=prompt_transport,
        diagnostics_capture=diagnostics_capture,
    )
    if prompt_file is not None:
        prompt_file.unlink(missing_ok=True)
    return result
