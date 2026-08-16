from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from statistics import fmean
from typing import Any

SCHEMA_VERSION = "llmgauge.localmaxxing_benchmark.v1"
METHOD = "localmaxxing-llama-cpp-v1"
API_VERSION = "1.6.0"
API_ROOT = "https://www.localmaxxing.com"
AGENT_CONTEXT_PATH = "/api/agent-context"
DRY_RUN_PATH = "/api/speed-tests/dry-run"
SUBMIT_PATH = "/api/speed-tests"


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def fingerprint(artifact: dict[str, Any]) -> str:
    copy = dict(artifact)
    copy.pop("fingerprint", None)
    return hashlib.sha256(canonical_json(copy).encode()).hexdigest()


def _positive(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0


def validate_artifact(artifact: dict[str, Any]) -> tuple[bool, list[str], list[str]]:
    errors: list[str] = []
    ineligible: list[str] = []
    if (
        artifact.get("schema_version") != SCHEMA_VERSION
        or artifact.get("artifact_version") != 1
    ):
        errors.append("unsupported LocalMaxxing artifact schema/version")
    if artifact.get("method") != METHOD:
        errors.append("unsupported benchmark method")
    if artifact.get("fingerprint") != fingerprint(artifact):
        errors.append("artifact fingerprint mismatch")
    measurements = artifact.get("measurements")
    if not isinstance(measurements, list) or len(measurements) != 5:
        errors.append("artifact requires exactly five measured repetitions")
    elif any(
        not isinstance(item, dict)
        or not _positive(item.get("tok_s_out"))
        or not _positive(item.get("tok_s_prefill"))
        for item in measurements
    ):
        errors.append(
            "every measured repetition requires positive prefill and output throughput"
        )
    aggregate = artifact.get("aggregate", {})
    expected_out = None
    expected_prefill = None
    if (
        isinstance(measurements, list)
        and len(measurements) == 5
        and all(
            isinstance(item, dict)
            and _positive(item.get("tok_s_out"))
            and _positive(item.get("tok_s_prefill"))
            for item in measurements
        )
    ):
        expected_out = fmean(item["tok_s_out"] for item in measurements)
        expected_prefill = fmean(item["tok_s_prefill"] for item in measurements)
    if not _positive(aggregate.get("tok_s_out")):
        errors.append("aggregate requires positive output throughput")
    elif expected_out is not None and aggregate["tok_s_out"] != expected_out:
        errors.append("aggregate output throughput must be the arithmetic mean")
    if (
        expected_prefill is not None
        and aggregate.get("tok_s_prefill") != expected_prefill
    ):
        errors.append("aggregate prefill throughput must be the arithmetic mean")
    combined = artifact.get("combined_measurements")
    if combined is not None:
        if (
            not isinstance(combined, list)
            or len(combined) != 5
            or not all(_positive(value) and math.isfinite(value) for value in combined)
        ):
            errors.append(
                "combined throughput requires five positive finite measurements"
            )
        elif aggregate.get("tok_s_total") != fmean(combined):
            errors.append("aggregate combined throughput must be the arithmetic mean")
    elif "tok_s_total" in aggregate:
        errors.append("aggregate combined throughput requires source measurements")
    ttft = artifact.get("ttft")
    if ttft is not None:
        samples = ttft.get("samples_ms") if isinstance(ttft, dict) else None
        if (
            not isinstance(samples, list)
            or len(samples) != 5
            or not all(_positive(value) and math.isfinite(value) for value in samples)
        ):
            errors.append("TTFT requires five positive finite companion samples")
        elif ttft.get("mean_ms") != fmean(samples):
            errors.append("TTFT aggregate must be the arithmetic mean")
    telemetry = artifact.get("telemetry")
    if isinstance(telemetry, dict) and telemetry.get("available"):
        samples = telemetry.get("samples")
        if not isinstance(samples, list) or not samples:
            errors.append("available telemetry requires samples")
        elif any(
            not isinstance(sample, dict)
            or not all(
                _finite_nonnegative(sample.get(field))
                for field in (
                    "timestamp_monotonic",
                    "memory_used_mib",
                    "power_draw_w",
                    "utilization_gpu_pct",
                    "temperature_c",
                )
            )
            for sample in samples
        ):
            errors.append("telemetry samples must be finite and non-negative")
        elif telemetry.get("peak_total_vram_mib") != max(
            sample["memory_used_mib"] for sample in samples
        ) or telemetry.get("mean_power_w") != fmean(
            sample["power_draw_w"] for sample in samples
        ):
            errors.append("telemetry aggregates must match samples")
    model = artifact.get("model", {})
    if not model.get("hf_id"):
        ineligible.append("missing canonical HuggingFace ID")
    if not model.get("quantization"):
        ineligible.append("missing explicit quantization")
    engine = artifact.get("engine", {})
    if (
        engine.get("name") != "llama.cpp"
        or not engine.get("version")
        or not engine.get("backend")
    ):
        ineligible.append("incomplete llama.cpp engine provenance")
    hardware = artifact.get("hardware", {})
    if (
        hardware.get("hwClass") != "DISCRETE_GPU"
        or not hardware.get("gpuName")
        or not _positive(hardware.get("vramGb"))
    ):
        ineligible.append("invalid discrete-GPU hardware identity")
    if not _positive(aggregate.get("tok_s_prefill")):
        ineligible.append("missing required prefill throughput secondary metric")
    if not artifact.get("command_provenance"):
        ineligible.append("missing command provenance")
    return not errors, errors, ineligible


def export_payload(artifact: dict[str, Any]) -> dict[str, Any]:
    valid, errors, ineligible = validate_artifact(artifact)
    if not valid:
        raise ValueError("invalid artifact: " + "; ".join(errors))
    if ineligible:
        raise ValueError("LocalMaxxing-ineligible artifact: " + "; ".join(ineligible))
    model = artifact["model"]
    engine = artifact["engine"]
    workload = artifact["workload"]
    aggregate = artifact["aggregate"]
    runtime = artifact.get("runtime", {})
    engine_flags: dict[str, Any] = {"commandSnippet": artifact["command_provenance"]}
    if isinstance(runtime, dict):
        if isinstance(runtime.get("split_mode"), str):
            engine_flags["splitMode"] = runtime["split_mode"]
        kv_cache = runtime.get("kv_cache")
        if (
            isinstance(kv_cache, dict)
            and kv_cache.get("type_k") == kv_cache.get("type_v")
            and kv_cache.get("type_k") in {"q8_0", "q4_0", "f16", "fp16"}
        ):
            engine_flags["kvCacheDtype"] = (
                "fp16" if kv_cache["type_k"] == "f16" else kv_cache["type_k"]
            )
        if runtime.get("flash_attention_effective") is True:
            engine_flags["flashAttn"] = True
        elif runtime.get("flash_attention_effective") is False:
            engine_flags["flashAttn"] = False
    payload: dict[str, Any] = {
        "hfId": model["hf_id"],
        "modelRevision": model.get("revision", "main"),
        "hardware": artifact["hardware"],
        "engineName": engine["name"],
        "engineVersion": engine["version"],
        "backend": engine["backend"],
        "quantization": model["quantization"],
        "promptTokens": workload["prompt_tokens"],
        "outputTokens": workload["output_tokens"],
        "batchSize": workload["batch_size"],
        "tokSOut": aggregate["tok_s_out"],
        "tokSPrefill": aggregate["tok_s_prefill"],
        "engineFlags": engine_flags,
        "notes": (
            "LLMGauge localmaxxing-llama-cpp-v1; one warmup excluded; "
            "five measured repetitions; full-GPU llama.cpp."
        ),
    }
    if _positive(workload.get("context_length")):
        payload["contextLength"] = workload["context_length"]
    if _positive(aggregate.get("tok_s_total")):
        payload["tokSTotal"] = aggregate["tok_s_total"]
    ttft = artifact.get("ttft")
    if isinstance(ttft, dict) and _positive(ttft.get("mean_ms")):
        payload["ttftMs"] = ttft["mean_ms"]
    telemetry = artifact.get("telemetry")
    if isinstance(telemetry, dict) and telemetry.get("available"):
        if _positive(telemetry.get("peak_total_vram_mib")):
            payload["peakVramGb"] = telemetry["peak_total_vram_mib"] / 1024
        if _positive(telemetry.get("mean_power_w")):
            payload["gpuPowerWatts"] = [telemetry["mean_power_w"]]
    return payload


def make_artifact(
    *,
    hf_id: str | None,
    quantization: str | None,
    model_path: str,
    engine_version: str,
    backend: str,
    hardware: dict[str, Any],
    command: str,
    measurements: list[dict[str, float]],
    profile: str | None = None,
    revision: str | None = None,
    executable: str | None = None,
    runtime: dict[str, Any] | None = None,
    combined_measurements: list[float] | None = None,
    ttft: dict[str, Any] | None = None,
    telemetry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    out = [item["tok_s_out"] for item in measurements]
    prefill = [
        item["tok_s_prefill"]
        for item in measurements
        if _positive(item.get("tok_s_prefill"))
    ]
    artifact: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "artifact_version": 1,
        "method": METHOD,
        "created_at": datetime.now(UTC).isoformat(),
        "model": {
            "hf_id": hf_id,
            "revision": revision or "main",
            "local_reference": model_path,
            "quantization": quantization,
            "profile": profile,
        },
        "engine": {
            "name": "llama.cpp",
            "version": engine_version,
            "backend": backend,
            "executable": executable,
        },
        "hardware": hardware,
        "workload": {
            "prompt_tokens": 512,
            "output_tokens": 128,
            "batch_size": 1,
            "repetitions": len(measurements),
            "warmup_repetitions": 1,
            "gpu_layers": -1,
            "sampling": "llama-bench deterministic",
        },
        "measurements": measurements,
        "aggregate": {
            "tok_s_out": fmean(out),
            **({"tok_s_prefill": fmean(prefill)} if prefill else {}),
            **(
                {"tok_s_total": fmean(combined_measurements)}
                if combined_measurements
                else {}
            ),
        },
        "command_provenance": command,
        **({"runtime": runtime} if runtime else {}),
        **(
            {"combined_measurements": combined_measurements}
            if combined_measurements is not None
            else {}
        ),
        **({"ttft": ttft} if ttft else {}),
        **({"telemetry": telemetry} if telemetry else {}),
    }
    artifact["fingerprint"] = fingerprint(artifact)
    return artifact


def save_artifact(
    artifact: dict[str, Any],
    destination: Path,
    evidence: dict[str, Any] | None = None,
    ttft_evidence: dict[str, Any] | None = None,
) -> Path:
    """Atomically publish an already validated benchmark result without overwrite."""
    valid, errors, _ = validate_artifact(artifact)
    if not valid:
        raise ValueError("cannot publish invalid artifact: " + "; ".join(errors))
    if destination.exists():
        raise FileExistsError(f"artifact destination already exists: {destination}")
    temporary = destination.with_name(f".{destination.name}.tmp-{os.getpid()}")
    temporary.mkdir(parents=True, exist_ok=False)
    try:
        path = temporary / "benchmark.json"
        path.write_text(
            json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        if evidence is not None:
            (temporary / "execution-evidence.json").write_text(
                json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
        telemetry = artifact.get("telemetry")
        if isinstance(telemetry, dict):
            (temporary / "telemetry-evidence.json").write_text(
                json.dumps(telemetry, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        if ttft_evidence is not None:
            (temporary / "ttft-evidence.json").write_text(
                json.dumps(ttft_evidence, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        os.replace(temporary, destination)
        return destination / "benchmark.json"
    except Exception:
        import shutil

        shutil.rmtree(temporary, ignore_errors=True)
        raise


def load_artifact(path: Path) -> dict[str, Any]:
    artifact_path = path / "benchmark.json" if path.is_dir() else path
    return json.loads(artifact_path.read_text(encoding="utf-8"))


def request_api(
    path: str, payload: dict[str, Any] | None = None, api_key: str | None = None
) -> dict[str, Any]:
    headers = {
        "Accept": "application/json",
        "User-Agent": "LLMGauge LocalMaxxing integration",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    data = None if payload is None else canonical_json(payload).encode()
    if data is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        API_ROOT + path,
        data=data,
        headers=headers,
        method="GET" if data is None else "POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            try:
                decoded = json.loads(response.read())
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                raise ValueError("LocalMaxxing API returned malformed JSON") from exc
            if not isinstance(decoded, dict):
                raise ValueError("LocalMaxxing API returned an invalid response")
            return decoded
    except urllib.error.HTTPError as exc:
        raise ValueError(f"LocalMaxxing API HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise ValueError("LocalMaxxing network failure") from exc


def checked_online_request(
    artifact: dict[str, Any], *, submit: bool = False
) -> dict[str, Any]:
    key = os.environ.get("LOCALMAXXING_API_KEY")
    if not key:
        raise ValueError(
            "LOCALMAXXING_API_KEY is required for LocalMaxxing online operations"
        )
    specification = request_api("/api/openapi.json")
    info = specification.get("info")
    paths = specification.get("paths")
    if (
        not isinstance(info, dict)
        or info.get("version") != API_VERSION
        or not isinstance(paths, dict)
        or DRY_RUN_PATH not in paths
        or SUBMIT_PATH not in paths
    ):
        raise ValueError("LocalMaxxing OpenAPI contract mismatch")
    context = request_api(AGENT_CONTEXT_PATH)
    meta = context.get("_meta")
    if not isinstance(meta, dict):
        raise ValueError("LocalMaxxing agent context contract mismatch")
    expected = SUBMIT_PATH if submit else DRY_RUN_PATH
    endpoint = meta.get("submitEndpoint" if submit else "dryRunEndpoint")
    if not isinstance(endpoint, str) or not endpoint.endswith(expected):
        raise ValueError("LocalMaxxing agent context endpoint contract mismatch")
    return request_api(expected, export_payload(artifact), key)


def run_llama_bench(command: list[str]) -> str:
    completed = subprocess.run(
        command, check=False, capture_output=True, text=True, timeout=900
    )
    if completed.returncode:
        raise ValueError(
            f"llama-bench failed with exit {completed.returncode}: {completed.stderr[-500:]}"
        )
    return completed.stdout


def parse_llama_bench_json(output: str) -> list[dict[str, float]]:
    """Return one measured prefill/decode pair from llama-bench JSON output."""
    try:
        rows = json.loads(output)
    except json.JSONDecodeError as exc:
        raise ValueError("llama-bench did not emit JSON") from exc
    if not isinstance(rows, list):
        raise ValueError("llama-bench JSON must be a list")
    prefill = next(
        (
            row.get("avg_ts")
            for row in rows
            if row.get("n_prompt", 0) > 0 and row.get("n_gen", 0) == 0
        ),
        None,
    )
    decode = next(
        (
            row.get("avg_ts")
            for row in rows
            if row.get("n_prompt", 0) == 0 and row.get("n_gen", 0) > 0
        ),
        None,
    )
    if not _positive(prefill) or not _positive(decode):
        raise ValueError("llama-bench output lacks positive prefill/decode throughput")
    return [{"tok_s_prefill": float(prefill), "tok_s_out": float(decode)}]


def probe_nvidia_gpu_count() -> int | None:
    try:
        completed = subprocess.run(
            ["nvidia-smi", "--list-gpus"],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    count = len([line for line in completed.stdout.splitlines() if line.strip()])
    return count if completed.returncode == 0 and count else None


def llama_bench_version(output: str) -> str:
    rows = json.loads(output)
    if not isinstance(rows, list) or not rows:
        raise ValueError("llama-bench JSON must contain a result")
    row = rows[0]
    build = row.get("build_number")
    commit = row.get("build_commit")
    if not isinstance(build, int) or not isinstance(commit, str) or not commit:
        raise ValueError("llama-bench output lacks build provenance")
    return f"b{build}+{commit}"


def _finite_nonnegative(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value >= 0
    )


def probe_host_hardware() -> dict[str, Any]:
    """Return bounded Linux host metadata when it can be source-backed."""
    cpu = None
    ram_gb = None
    try:
        for line in Path("/proc/cpuinfo").read_text(encoding="utf-8").splitlines():
            if line.startswith("model name"):
                cpu = line.partition(":")[2].strip() or None
                break
    except OSError:
        pass
    try:
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            if line.startswith("MemTotal:"):
                kib = int(line.split()[1])
                ram_gb = kib / (1024 * 1024)
                break
    except (OSError, ValueError, IndexError):
        pass
    os_identity = f"{platform.system()} {platform.release()} {platform.machine()}"
    return {
        **({"cpu": cpu} if cpu else {}),
        **({"ramGb": ram_gb} if _positive(ram_gb) else {}),
        **({"os": os_identity[:64]} if os_identity else {}),
    }


def parse_nvidia_smi_csv(output: str, timestamp: float) -> dict[str, float]:
    """Parse exactly one nvidia-smi noheader CSV row."""
    fields = [field.strip() for field in output.strip().split(",")]
    if len(fields) != 4:
        raise ValueError("nvidia-smi telemetry must contain four fields")
    try:
        memory, power, utilization, temperature = (
            float(field.removesuffix(" MiB").removesuffix(" W")) for field in fields
        )
    except ValueError as exc:
        raise ValueError("nvidia-smi telemetry contains nonnumeric values") from exc
    sample = {
        "timestamp_monotonic": timestamp,
        "memory_used_mib": memory,
        "power_draw_w": power,
        "utilization_gpu_pct": utilization,
        "temperature_c": temperature,
    }
    if not all(_finite_nonnegative(value) for value in sample.values()):
        raise ValueError("nvidia-smi telemetry contains invalid values")
    return sample


class NvidiaTelemetrySampler:
    """Bounded total-device telemetry sampler; unavailable telemetry is optional."""

    def __init__(self, cadence_seconds: float = 0.2) -> None:
        self.cadence_seconds = cadence_seconds
        self.samples: list[dict[str, float]] = []
        self.error: str | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def _sample(self) -> None:
        try:
            completed = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=memory.used,power.draw,utilization.gpu,temperature.gpu",
                    "--format=csv,noheader,nounits",
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=2,
            )
            if completed.returncode:
                raise OSError("nvidia-smi failed")
            self.samples.append(
                parse_nvidia_smi_csv(completed.stdout, time.monotonic())
            )
        except (OSError, subprocess.SubprocessError, ValueError) as exc:
            self.error = type(exc).__name__

    def _run(self) -> None:
        while not self._stop.is_set():
            self._sample()
            self._stop.wait(self.cadence_seconds)

    def start(self) -> None:
        self._sample()
        if self.error:
            return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> dict[str, Any] | None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
        if self.error and not self.samples:
            return {"available": False, "source": "nvidia-smi", "error": self.error}
        return summarize_telemetry(self.samples, self.cadence_seconds, self.error)


def summarize_telemetry(
    samples: list[dict[str, float]], cadence_seconds: float, error: str | None = None
) -> dict[str, Any]:
    if not samples:
        return {
            "available": False,
            "source": "nvidia-smi",
            **({"error": error} if error else {}),
        }
    memory = [sample["memory_used_mib"] for sample in samples]
    power = [sample["power_draw_w"] for sample in samples]
    return {
        "available": True,
        "source": "nvidia-smi",
        "scope": "total_device",
        "cadence_ms": int(cadence_seconds * 1000),
        "samples": samples,
        "baseline_vram_mib": memory[0],
        "peak_total_vram_mib": max(memory),
        "mean_power_w": fmean(power),
        "peak_power_w": max(power),
        "peak_utilization_gpu_pct": max(
            sample["utilization_gpu_pct"] for sample in samples
        ),
        "peak_temperature_c": max(sample["temperature_c"] for sample in samples),
        **({"error": error} if error else {}),
    }


def llama_bench_runtime_metadata(output: str) -> dict[str, Any]:
    rows = json.loads(output)
    if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict):
        raise ValueError("llama-bench JSON must contain runtime metadata")
    row = rows[0]
    requested_flash = {0: "off", 1: "on", -1: "auto"}.get(row.get("flash_attn"))
    type_k, type_v = row.get("type_k"), row.get("type_v")
    return {
        "gpu_placement": "full_gpu" if row.get("n_gpu_layers") == -1 else "unknown",
        "gpu_layers_requested": row.get("n_gpu_layers"),
        "logical_batch": row.get("n_batch"),
        "physical_ubatch": row.get("n_ubatch"),
        "split_mode": row.get("split_mode"),
        "main_gpu": row.get("main_gpu"),
        "kv_offload": not row.get("no_kv_offload"),
        "kv_cache": {"type_k": type_k, "type_v": type_v},
        "flash_attention_requested": requested_flash,
        "device": row.get("devices"),
        "load_mode": row.get("load_mode"),
    }


def parse_llama_bench_combined_json(output: str) -> float:
    try:
        rows = json.loads(output)
    except json.JSONDecodeError as exc:
        raise ValueError("llama-bench did not emit JSON") from exc
    if not isinstance(rows, list):
        raise ValueError("llama-bench JSON must be a list")
    combined = next(
        (
            row.get("avg_ts")
            for row in rows
            if row.get("n_prompt", 0) > 0 and row.get("n_gen", 0) > 0
        ),
        None,
    )
    if not _positive(combined):
        raise ValueError("llama-bench output lacks positive combined throughput")
    return float(combined)


def _free_local_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _stream_ttft(url: str) -> float:
    payload = canonical_json(
        {"prompt": "x " * 512, "n_predict": 128, "stream": True, "cache_prompt": False}
    ).encode()
    request = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = time.monotonic()
    with urllib.request.urlopen(request, timeout=120) as response:
        for raw_line in response:
            line = raw_line.decode("utf-8", "replace").strip()
            if line.startswith("data:") and line[5:].strip() not in {"", "[DONE]"}:
                elapsed_ms = (time.monotonic() - started) * 1000
                if _positive(elapsed_ms):
                    return elapsed_ms
    raise ValueError("llama-server stream ended before first generated chunk")


def measure_ttft(
    server_command: list[str], repetitions: int = 5
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Run an isolated localhost llama-server TTFT companion probe."""
    port = _free_local_port()
    command = [*server_command, "--host", "127.0.0.1", "--port", str(port)]
    process = subprocess.Popen(
        command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, text=True
    )
    evidence: dict[str, Any] = {
        "command": command,
        "repetitions": repetitions,
        "warmup_excluded": True,
    }
    url = f"http://127.0.0.1:{port}/completion"
    try:
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            try:
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/health", timeout=2
                ) as response:
                    if response.status == 200:
                        break
            except urllib.error.URLError:
                time.sleep(0.2)
        else:
            raise ValueError("llama-server did not become ready")
        _stream_ttft(url)
        samples = [_stream_ttft(url) for _ in range(repetitions)]
        if not all(_positive(sample) and math.isfinite(sample) for sample in samples):
            raise ValueError("llama-server TTFT samples must be positive and finite")
        evidence["samples_ms"] = samples
        return {"samples_ms": samples, "mean_ms": fmean(samples)}, evidence
    except (OSError, urllib.error.URLError, ValueError) as exc:
        evidence["unavailable_reason"] = type(exc).__name__
        return None, evidence
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)
