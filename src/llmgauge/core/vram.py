from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


NVIDIA_SMI_QUERY_FIELDS = [
    "index",
    "name",
    "memory.used",
    "memory.total",
]


@dataclass(frozen=True)
class VramSample:
    timestamp_utc: str
    gpu_index: int
    gpu_name: str
    used_mib: int
    total_mib: int


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def parse_nvidia_smi_memory_csv(
    output: str, *, timestamp_utc: str | None = None
) -> list[VramSample]:
    """Parse nvidia-smi CSV output for GPU memory use.

    Expected command shape:

        nvidia-smi --query-gpu=index,name,memory.used,memory.total --format=csv,noheader,nounits

    Example line:

        0, NVIDIA GeForce RTX 5070, 8123, 12227
    """
    timestamp = timestamp_utc or _utc_now_iso()
    samples: list[VramSample] = []

    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        parts = [part.strip() for part in line.split(",")]
        if len(parts) != 4:
            continue

        try:
            gpu_index = int(parts[0])
            used_mib = int(parts[2])
            total_mib = int(parts[3])
        except ValueError:
            continue

        samples.append(
            VramSample(
                timestamp_utc=timestamp,
                gpu_index=gpu_index,
                gpu_name=parts[1],
                used_mib=used_mib,
                total_mib=total_mib,
            )
        )

    return samples


def sample_nvidia_smi_memory(
    *,
    nvidia_smi: Path | str = "nvidia-smi",
    timeout_seconds: float = 2.0,
) -> dict[str, Any]:
    """Take one read-only GPU memory sample using nvidia-smi.

    This function never raises for missing nvidia-smi or nvidia-smi failure.
    It returns an unavailable status instead, so LLMGauge runs can continue.
    """
    command = [
        str(nvidia_smi),
        "--query-gpu=index,name,memory.used,memory.total",
        "--format=csv,noheader,nounits",
    ]

    timestamp = _utc_now_iso()

    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except FileNotFoundError:
        return {
            "schema_version": "llmgauge.vram.sample.v0",
            "available": False,
            "source": "nvidia-smi",
            "timestamp_utc": timestamp,
            "samples": [],
            "error": "nvidia-smi not found",
        }
    except subprocess.TimeoutExpired:
        return {
            "schema_version": "llmgauge.vram.sample.v0",
            "available": False,
            "source": "nvidia-smi",
            "timestamp_utc": timestamp,
            "samples": [],
            "error": "nvidia-smi timed out",
        }

    if completed.returncode != 0:
        return {
            "schema_version": "llmgauge.vram.sample.v0",
            "available": False,
            "source": "nvidia-smi",
            "timestamp_utc": timestamp,
            "samples": [],
            "error": completed.stderr.strip()
            or f"nvidia-smi exited {completed.returncode}",
        }

    parsed = parse_nvidia_smi_memory_csv(completed.stdout, timestamp_utc=timestamp)
    return {
        "schema_version": "llmgauge.vram.sample.v0",
        "available": bool(parsed),
        "source": "nvidia-smi",
        "timestamp_utc": timestamp,
        "samples": [sample.__dict__ for sample in parsed],
        "error": None if parsed else "no GPU memory samples parsed",
    }


def summarize_vram_samples(samples: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize a list of VRAM sample dictionaries.

    The initial v0.19 schema keeps this intentionally simple and transparent.
    """
    valid_samples = [
        sample
        for sample in samples
        if isinstance(sample.get("used_mib"), int)
        and isinstance(sample.get("total_mib"), int)
        and isinstance(sample.get("gpu_index"), int)
    ]

    if not valid_samples:
        return {
            "schema_version": "llmgauge.vram.summary.v0",
            "available": False,
            "sample_count": 0,
            "peak_used_mib": None,
            "peak_total_mib": None,
            "peak_gpu_index": None,
            "peak_gpu_name": None,
            "initial_used_mib": None,
            "final_used_mib": None,
            "error": "no valid VRAM samples",
        }

    peak = max(valid_samples, key=lambda item: item["used_mib"])

    return {
        "schema_version": "llmgauge.vram.summary.v0",
        "available": True,
        "sample_count": len(valid_samples),
        "peak_used_mib": peak["used_mib"],
        "peak_total_mib": peak["total_mib"],
        "peak_gpu_index": peak["gpu_index"],
        "peak_gpu_name": peak.get("gpu_name"),
        "initial_used_mib": valid_samples[0]["used_mib"],
        "final_used_mib": valid_samples[-1]["used_mib"],
        "error": None,
    }
