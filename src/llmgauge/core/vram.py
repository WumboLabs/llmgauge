from __future__ import annotations

import subprocess
import threading
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


class VramSampler:
    """Bounded concurrent NVIDIA VRAM sampler for one owned observation window.

    Polls a probe (``nvidia-smi`` memory by default) on one daemon worker
    thread at a fixed conservative interval. The first sample is taken
    synchronously on ``start`` and the final sample is taken on ``stop``, so
    the preserved sample stream is ordered and its window is explicit.
    Probe failures never raise: they are collected as errors and do not
    affect the calling request. The sampler performs no HTTP, no runtime
    control, and no mutation of request data; it only observes.
    """

    DEFAULT_INTERVAL_SECONDS = 0.5
    _JOIN_TIMEOUT_SECONDS = 2.0

    def __init__(
        self,
        *,
        interval_seconds: float = DEFAULT_INTERVAL_SECONDS,
        probe: Any = None,
    ) -> None:
        self._interval = max(float(interval_seconds), 0.05)
        self._probe = probe if probe is not None else sample_nvidia_smi_memory
        self._samples: list[dict[str, Any]] = []
        self._errors: list[str] = []
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Take the initial sample and start the bounded worker thread."""
        if self._thread is not None and self._thread.is_alive():
            raise RuntimeError("VRAM sampler is already running")
        self._sample_once()
        self._thread = threading.Thread(
            target=self._run,
            name="llmgauge-vram-sampler",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> tuple[list[dict[str, Any]], list[str]]:
        """Stop the worker, take the final sample, and return (samples, errors).

        Safe to call on every terminal request path; calling before ``start``
        or twice returns the current preserved state.
        """
        self._stop.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=self._JOIN_TIMEOUT_SECONDS)
        self._sample_once()
        with self._lock:
            return list(self._samples), list(self._errors)

    def is_alive(self) -> bool:
        thread = self._thread
        return thread is not None and thread.is_alive()

    def _run(self) -> None:
        while not self._stop.wait(self._interval):
            self._sample_once()

    def _sample_once(self) -> None:
        try:
            report = self._probe()
        except Exception as exc:  # noqa: BLE001 - optional telemetry never raises
            with self._lock:
                self._errors.append(f"VRAM probe raised: {exc}")
            return
        if not isinstance(report, dict):
            with self._lock:
                self._errors.append("VRAM probe returned a non-object report")
            return
        if report.get("available") is True:
            samples = report.get("samples")
            if isinstance(samples, list) and samples:
                with self._lock:
                    self._samples.extend(samples)
                return
            with self._lock:
                self._errors.append(
                    "VRAM probe reported available without a non-empty sample list"
                )
            return
        error = report.get("error")
        if isinstance(error, str) and error:
            with self._lock:
                self._errors.append(error)
