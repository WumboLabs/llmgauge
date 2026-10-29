"""Managed-local vLLM server lifecycle (M4).

Launches, verifies, operates, and shuts down an operator-installed local vLLM
server under LLMGauge process ownership, per
docs/FIRST_CLASS_RUNTIME_ARCHITECTURE.md §5.2/§5.3 and
docs/VLLM_RUNTIME_CONTRACT.md.

Ownership rule: LLMGauge may terminate only the process it launched. An
already-occupied endpoint port is a fail-closed startup condition; the
occupant is never touched. LLMGauge never installs vLLM, never downloads
models, and never restarts a failed server mid-run.
"""

from __future__ import annotations

import errno
import hashlib
import os
import shutil
import signal
import socket
import subprocess
import time
from datetime import UTC, datetime
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from llmgauge.runners.vllm_external import (
    VllmExternalConfig,
    VllmReadinessResult,
    check_readiness_and_model,
)
from llmgauge.runners.vllm_http import (
    ValidatedEndpoint,
    resolve_loopback_addresses,
)

VLLM_STARTUP_EVIDENCE_SCHEMA = "llmgauge.vllm_startup_evidence.v0"
VLLM_STARTUP_EVIDENCE_FILENAME = "vllm-startup-evidence.json"
LIFECYCLE_OWNERSHIP_MANAGED = "llmgauge_managed"

DEFAULT_STARTUP_TIMEOUT_SECONDS = 600.0
MIN_STARTUP_TIMEOUT_SECONDS = 5.0
MAX_STARTUP_TIMEOUT_SECONDS = 7200.0
DEFAULT_SHUTDOWN_TIMEOUT_SECONDS = 30.0
MIN_SHUTDOWN_TIMEOUT_SECONDS = 1.0
MAX_SHUTDOWN_TIMEOUT_SECONDS = 300.0
DEFAULT_READINESS_POLL_INTERVAL_SECONDS = 1.0
MIN_READINESS_POLL_INTERVAL_SECONDS = 0.05
MAX_READINESS_POLL_INTERVAL_SECONDS = 30.0
# Per-poll HTTP budget inside the startup loop. Bounded readiness polling is
# not a hidden evaluation retry: it never reaches the chat-completions path.
READINESS_POLL_CONNECT_SECONDS = 2.0
READINESS_POLL_REQUEST_SECONDS = 10.0
KILL_WAIT_SECONDS = 10.0

DTYPE_ALLOWLIST = frozenset({"auto", "half", "float16", "bfloat16", "float32"})

STARTUP_STATUSES = frozenset({"ready", "failed", "cancelled"})
SHUTDOWN_STATUSES = frozenset(
    {"graceful", "forced", "already_exited", "failed", "not_started"}
)
ADMISSION_STATUSES = frozenset({"admitted", "failed", "not_observed"})

#: Facts a managed-local launch does not observe; recorded explicitly so the
#: evidence never implies server load time, GPU allocation, or warm state.
UNOBSERVED_STARTUP_FACTS = [
    "server_model_load_seconds",
    "gpu_memory_allocation",
    "cache_warm_state",
    "effective_runtime_chat_template",
    "effective_runtime_quantization",
]

STARTUP_EVIDENCE_CLAIM = (
    "startup evidence records LLMGauge-owned launch, readiness, admission, and "
    "shutdown observations; launch settings are configuration evidence, not "
    "proof of observed hardware behavior"
)


class VllmManagedLaunchError(ValueError):
    """Actionable launch-configuration or pre-launch admission failure."""


@dataclass(frozen=True)
class VllmManagedLaunchConfig:
    """Bounded, validated managed-local launch configuration.

    Launch arguments come only from these validated options; there is no
    arbitrary argument passthrough and no shell command string.
    """

    executable: str
    model_path: str
    served_model_name: str
    host: str
    port: int
    max_model_len: int | None = None
    gpu_memory_utilization: float | None = None
    dtype: str | None = None
    startup_timeout_seconds: float = DEFAULT_STARTUP_TIMEOUT_SECONDS
    shutdown_timeout_seconds: float = DEFAULT_SHUTDOWN_TIMEOUT_SECONDS
    readiness_poll_interval_seconds: float = DEFAULT_READINESS_POLL_INTERVAL_SECONDS


def validate_managed_launch_config(config: VllmManagedLaunchConfig) -> None:
    """Fail closed on any launch option outside the admitted bounded surface."""
    if not config.executable or not config.executable.strip():
        raise VllmManagedLaunchError("vLLM executable is empty")
    if not config.model_path or not config.model_path.strip():
        raise VllmManagedLaunchError("vLLM managed model path is empty")
    if not Path(config.model_path).is_dir():
        raise VllmManagedLaunchError(
            f"vLLM managed model path is not an existing local directory: "
            f"{config.model_path}; managed mode never downloads models"
        )
    if not config.served_model_name or not config.served_model_name.strip():
        raise VllmManagedLaunchError("vLLM served model name is empty")
    if not (1 <= int(config.port) <= 65535):
        raise VllmManagedLaunchError("vLLM managed port must be between 1 and 65535")
    if config.max_model_len is not None and int(config.max_model_len) <= 0:
        raise VllmManagedLaunchError("--vllm-max-model-len must be a positive integer")
    if config.gpu_memory_utilization is not None:
        utilization = float(config.gpu_memory_utilization)
        if not 0.0 < utilization <= 1.0:
            raise VllmManagedLaunchError(
                "--vllm-gpu-memory-utilization must be in (0, 1]"
            )
    if config.dtype is not None and config.dtype not in DTYPE_ALLOWLIST:
        raise VllmManagedLaunchError(
            "--vllm-dtype must be one of: " + ", ".join(sorted(DTYPE_ALLOWLIST))
        )
    if (
        not MIN_STARTUP_TIMEOUT_SECONDS
        <= float(config.startup_timeout_seconds)
        <= MAX_STARTUP_TIMEOUT_SECONDS
    ):
        raise VllmManagedLaunchError(
            "vLLM startup timeout must be between "
            f"{MIN_STARTUP_TIMEOUT_SECONDS} and {MAX_STARTUP_TIMEOUT_SECONDS} seconds"
        )
    if (
        not MIN_SHUTDOWN_TIMEOUT_SECONDS
        <= float(config.shutdown_timeout_seconds)
        <= MAX_SHUTDOWN_TIMEOUT_SECONDS
    ):
        raise VllmManagedLaunchError(
            "vLLM shutdown timeout must be between "
            f"{MIN_SHUTDOWN_TIMEOUT_SECONDS} and {MAX_SHUTDOWN_TIMEOUT_SECONDS} seconds"
        )
    if (
        not MIN_READINESS_POLL_INTERVAL_SECONDS
        <= float(config.readiness_poll_interval_seconds)
        <= MAX_READINESS_POLL_INTERVAL_SECONDS
    ):
        raise VllmManagedLaunchError(
            "vLLM readiness poll interval must be between "
            f"{MIN_READINESS_POLL_INTERVAL_SECONDS} and "
            f"{MAX_READINESS_POLL_INTERVAL_SECONDS} seconds"
        )


def resolve_vllm_executable(value: str) -> str:
    """Resolve the operator-installed vLLM executable without installing it."""
    candidate = Path(value)
    if candidate.exists():
        resolved = candidate
    else:
        found = shutil.which(value)
        if found is None:
            raise VllmManagedLaunchError(
                f"vLLM executable not found: {value}; managed mode never "
                "installs vLLM. Provide --vllm-executable with the path to "
                "the operator-installed vllm command."
            )
        resolved = Path(found)
    if not resolved.is_file():
        raise VllmManagedLaunchError(f"vLLM executable is not a file: {resolved}")
    if not os.access(resolved, os.X_OK):
        raise VllmManagedLaunchError(f"vLLM executable is not executable: {resolved}")
    return str(resolved)


def executable_sha256(path: str) -> str | None:
    """Full SHA-256 of the resolved executable, or None when unreadable."""
    try:
        digest = hashlib.sha256()
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(262_144), b""):
                digest.update(chunk)
    except OSError:
        return None
    return digest.hexdigest()


def build_launch_argv(config: VllmManagedLaunchConfig) -> list[str]:
    """Structured vLLM API-server argv (never a shell string).

    The server is bound to the validated loopback host only; the model root
    must be a local directory (managed mode never downloads models).
    """
    argv = [
        config.executable,
        "serve",
        config.model_path,
        "--host",
        config.host,
        "--port",
        str(int(config.port)),
        "--served-model-name",
        config.served_model_name,
    ]
    if config.max_model_len is not None:
        argv.extend(["--max-model-len", str(int(config.max_model_len))])
    if config.gpu_memory_utilization is not None:
        argv.extend(
            ["--gpu-memory-utilization", str(float(config.gpu_memory_utilization))]
        )
    if config.dtype is not None:
        argv.extend(["--dtype", config.dtype])
    return argv


def _signal_name(termination_signal: int | None) -> str | None:
    if termination_signal is None:
        return None
    try:
        return signal.Signals(int(termination_signal)).name
    except ValueError:
        return f"signal_{int(termination_signal)}"


def _exit_observations(returncode: int | None) -> tuple[int | None, str | None]:
    """Map a Popen returncode to (exit_code, signal_name)."""
    if returncode is None:
        return None, None
    if returncode < 0:
        return None, _signal_name(-returncode)
    return int(returncode), None


@dataclass
class VllmStartupResult:
    """Startup-scope outcome; never carries request-scope metrics."""

    status: str  # ready | failed | cancelled
    failure_class: str | None = None
    failure_detail: str | None = None
    readiness: VllmReadinessResult | None = None
    readiness_attempts: int = 0
    startup_duration_seconds: float | None = None
    premature_exit: bool = False
    exit_code: int | None = None
    exit_signal: str | None = None
    pid: int | None = None
    launch_timestamp_utc: str | None = None
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass
class VllmShutdownRecord:
    status: str
    exit_code: int | None = None
    exit_signal: str | None = None
    duration_seconds: float | None = None
    escalation_used: bool = False


class VllmManagedServer:
    """LLMGauge-owned vLLM server process with bounded startup/shutdown.

    The instance owns exactly one subprocess. Shutdown escalates SIGTERM to
    SIGKILL within the owned process group only. Nothing here ever signals a
    process LLMGauge did not launch.
    """

    def __init__(
        self,
        *,
        launch_config: VllmManagedLaunchConfig,
        endpoint: ValidatedEndpoint,
        stdout_log_path: Path,
        stderr_log_path: Path,
        readiness_config: VllmExternalConfig,
    ) -> None:
        validate_managed_launch_config(launch_config)
        if endpoint.path.rstrip("/") not in {"", "/v1"}:
            raise VllmManagedLaunchError(
                "managed-local mode requires the standard root-served vLLM "
                "API path (endpoint path / or /v1); the launched server does "
                "not serve custom path prefixes"
            )
        self.launch_config = launch_config
        self.endpoint = endpoint
        self.stdout_log_path = stdout_log_path
        self.stderr_log_path = stderr_log_path
        self.readiness_config = readiness_config
        self.argv = build_launch_argv(launch_config)
        self.process: subprocess.Popen[bytes] | None = None
        self.startup: VllmStartupResult | None = None
        self.shutdown_record: VllmShutdownRecord | None = None
        self._stdout_handle = None
        self._stderr_handle = None

    # -- startup -----------------------------------------------------------

    def _check_port_free(self) -> tuple[bool, str | None]:
        """True when no socket already occupies the launch endpoint.

        A bind failure means another process owns the port. It is never
        terminated; managed startup fails closed instead.
        """
        try:
            addresses = resolve_loopback_addresses(self.endpoint)
        except Exception:  # noqa: BLE001 — endpoint already validated
            return False, "endpoint_unresolvable"
        for host, port, _family in addresses:
            probe = socket.socket(
                socket.AF_INET if _family == "ipv4" else socket.AF_INET6
            )
            try:
                probe.bind((host, port))
            except OSError as exc:
                probe.close()
                if exc.errno in {errno.EADDRINUSE, errno.EADDRNOTAVAIL}:
                    return False, "endpoint_port_in_use"
                probe.close()
                return False, "endpoint_bind_check_failed"
            probe.close()
        return True, None

    def start(self) -> VllmStartupResult:
        """Launch, poll readiness, and verify model admission (bounded).

        Returns a startup-scope result. On any failure the owned process is
        shut down before returning; no evaluation request is ever issued
        before model admission succeeds, and a failed server is never
        restarted.
        """
        started = time.monotonic()
        free, conflict = self._check_port_free()
        if not free:
            self.startup = VllmStartupResult(
                status="failed",
                failure_class="endpoint_unavailable",
                failure_detail=conflict or "endpoint_port_in_use",
                startup_duration_seconds=time.monotonic() - started,
            )
            return self.startup

        stdout_handle = self.stdout_log_path.open("wb")
        stderr_handle = self.stderr_log_path.open("wb")
        self._stdout_handle = stdout_handle
        self._stderr_handle = stderr_handle
        try:
            self.process = subprocess.Popen(  # noqa: S603 — structured argv, no shell
                self.argv,
                stdin=subprocess.DEVNULL,
                stdout=stdout_handle,
                stderr=stderr_handle,
                start_new_session=True,
            )
        except OSError as exc:
            self._close_log_handles()
            self.startup = VllmStartupResult(
                status="failed",
                failure_class="endpoint_unavailable",
                failure_detail=f"launch_failed:{type(exc).__name__}",
                startup_duration_seconds=time.monotonic() - started,
            )
            return self.startup

        pid = self.process.pid
        launch_timestamp_utc = datetime.now(UTC).replace(microsecond=0).isoformat()

        try:
            return self._poll_until_ready(started, pid, launch_timestamp_utc)
        except Exception as exc:  # noqa: BLE001 — record, shut down, fail closed
            # An unexpected internal error must never leak the owned process
            # and must not leave the startup record unset.
            self.startup = VllmStartupResult(
                status="failed",
                failure_class="startup_failure",
                failure_detail=f"unexpected_startup_error:{type(exc).__name__}",
                startup_duration_seconds=time.monotonic() - started,
                pid=pid,
                launch_timestamp_utc=launch_timestamp_utc,
            )
            self._cleanup_after_startup_failure()
            return self.startup

    def _poll_until_ready(
        self, started: float, pid: int, launch_timestamp_utc: str
    ) -> VllmStartupResult:
        deadline = started + float(self.launch_config.startup_timeout_seconds)
        attempts = 0
        readiness: VllmReadinessResult | None = None
        cancelled = False
        while True:
            returncode = self.process.poll()
            if returncode is not None:
                exit_code, exit_signal = _exit_observations(returncode)
                self.startup = VllmStartupResult(
                    status="failed",
                    failure_class="model_admission_load_failure",
                    failure_detail=(
                        f"server_exited_before_readiness:exit_code={exit_code}"
                        if exit_code is not None
                        else f"server_exited_before_readiness:signal={exit_signal}"
                    ),
                    readiness_attempts=attempts,
                    startup_duration_seconds=time.monotonic() - started,
                    premature_exit=True,
                    exit_code=exit_code,
                    exit_signal=exit_signal,
                    pid=pid,
                    launch_timestamp_utc=launch_timestamp_utc,
                )
                self._cleanup_after_startup_failure()
                return self.startup

            attempts += 1
            readiness = check_readiness_and_model(self.readiness_config)
            if readiness.success:
                self.startup = VllmStartupResult(
                    status="ready",
                    readiness=readiness,
                    readiness_attempts=attempts,
                    startup_duration_seconds=time.monotonic() - started,
                    pid=pid,
                    launch_timestamp_utc=launch_timestamp_utc,
                )
                return self.startup

            if time.monotonic() >= deadline:
                exit_code, exit_signal = _exit_observations(self.process.poll())
                self.startup = VllmStartupResult(
                    status="failed",
                    failure_class="readiness_failure",
                    failure_detail=(
                        "startup_readiness_deadline_exceeded:"
                        f"{readiness.failure_class or 'unknown'}"
                    ),
                    readiness=readiness,
                    readiness_attempts=attempts,
                    startup_duration_seconds=time.monotonic() - started,
                    exit_code=exit_code,
                    exit_signal=exit_signal,
                    pid=pid,
                    launch_timestamp_utc=launch_timestamp_utc,
                )
                self._cleanup_after_startup_failure()
                return self.startup

            try:
                time.sleep(float(self.launch_config.readiness_poll_interval_seconds))
            except KeyboardInterrupt:
                cancelled = True
                break

        exit_code, exit_signal = _exit_observations(self.process.poll())
        self.startup = VllmStartupResult(
            status="cancelled",
            failure_class="operator_cancellation",
            failure_detail="keyboard_interrupt_during_startup",
            readiness_attempts=attempts,
            startup_duration_seconds=time.monotonic() - started,
            exit_code=exit_code,
            exit_signal=exit_signal,
            pid=pid,
            launch_timestamp_utc=launch_timestamp_utc,
        )
        if cancelled:
            self._cleanup_after_startup_failure()
        return self.startup

    # -- shutdown ----------------------------------------------------------

    def _signal_group(self, sig: int) -> bool:
        """Signal the owned process group; False when it is already gone."""
        if self.process is None:
            return False
        pid = self.process.pid
        try:
            os.killpg(os.getpgid(pid), sig)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            # Never signal outside the owned session; fall back to the
            # direct child only, which is the process we launched.
            try:
                self.process.send_signal(sig)
                return True
            except (ProcessLookupError, PermissionError):
                return False

    def shutdown(self) -> VllmShutdownRecord:
        """Terminate only the owned process group, with bounded escalation."""
        if self.shutdown_record is not None:
            return self.shutdown_record
        if self.process is None:
            self.shutdown_record = VllmShutdownRecord(status="not_started")
            self._close_log_handles()
            return self.shutdown_record

        started = time.monotonic()
        returncode = self.process.poll()
        if returncode is not None:
            exit_code, exit_signal = _exit_observations(returncode)
            self.shutdown_record = VllmShutdownRecord(
                status="already_exited",
                exit_code=exit_code,
                exit_signal=exit_signal,
                duration_seconds=0.0,
            )
            self._close_log_handles()
            return self.shutdown_record

        self._signal_group(signal.SIGTERM)
        grace = float(self.launch_config.shutdown_timeout_seconds)
        try:
            returncode = self.process.wait(timeout=grace)
            self.shutdown_record = VllmShutdownRecord(
                status="graceful",
                **_exit_kwargs(returncode),
                duration_seconds=time.monotonic() - started,
            )
        except subprocess.TimeoutExpired:
            self._signal_group(signal.SIGKILL)
            self.shutdown_record = VllmShutdownRecord(
                status="forced",
                escalation_used=True,
                duration_seconds=time.monotonic() - started,
            )
            try:
                returncode = self.process.wait(timeout=KILL_WAIT_SECONDS)
                self.shutdown_record.exit_code, self.shutdown_record.exit_signal = (
                    _exit_observations(returncode)
                )
            except subprocess.TimeoutExpired:
                self.shutdown_record.status = "failed"
        self._close_log_handles()
        return self.shutdown_record

    def _cleanup_after_startup_failure(self) -> None:
        self.shutdown()

    def _close_log_handles(self) -> None:
        for handle in (self._stdout_handle, self._stderr_handle):
            if handle is not None:
                try:
                    handle.close()
                except OSError:
                    pass
        self._stdout_handle = None
        self._stderr_handle = None

    # -- evidence ----------------------------------------------------------

    def startup_evidence_document(self) -> dict[str, Any]:
        """Startup-scope artifact; separate from request-scope evidence."""
        startup = self.startup
        shutdown = self.shutdown_record
        executable_sha = executable_sha256(self.launch_config.executable)
        doc: dict[str, Any] = {
            "schema_version": VLLM_STARTUP_EVIDENCE_SCHEMA,
            "lifecycle_ownership": LIFECYCLE_OWNERSHIP_MANAGED,
            "backend": "vllm",
            "launch": {
                "argv": list(self.argv),
                "argv_form": "structured_execve",
                "shell": False,
                "executable": self.launch_config.executable,
                "executable_sha256": executable_sha,
                "executable_identity_source": (
                    "llmgauge_local_file_observation"
                    if executable_sha is not None
                    else "unavailable"
                ),
                "launch_config": {
                    "host": self.launch_config.host,
                    "port": int(self.launch_config.port),
                    "max_model_len": self.launch_config.max_model_len,
                    "gpu_memory_utilization": self.launch_config.gpu_memory_utilization,
                    "dtype": self.launch_config.dtype,
                    "startup_timeout_seconds": self.launch_config.startup_timeout_seconds,
                    "shutdown_timeout_seconds": self.launch_config.shutdown_timeout_seconds,
                    "readiness_poll_interval_seconds": (
                        self.launch_config.readiness_poll_interval_seconds
                    ),
                },
                "environment_policy": {
                    "secrets_captured": False,
                    "proxy_bypass": True,
                    "model_download": "disabled_by_contract",
                },
            },
            "process": {
                "owned_by_llmgauge": True,
                "pid": startup.pid if startup is not None else None,
                "process_group": "owned_session",
            },
            "startup": {
                "status": startup.status if startup is not None else "not_started",
                "launch_timestamp_utc": (
                    startup.launch_timestamp_utc if startup is not None else None
                ),
                "duration_seconds": (
                    startup.startup_duration_seconds if startup is not None else None
                ),
                "readiness_attempts": (
                    startup.readiness_attempts if startup is not None else 0
                ),
                "failure_class": startup.failure_class if startup is not None else None,
                "failure_detail": startup.failure_detail
                if startup is not None
                else None,
                "premature_exit": bool(startup.premature_exit) if startup else False,
                "exit_code": startup.exit_code if startup is not None else None,
                "exit_signal": startup.exit_signal if startup is not None else None,
            },
            "model_admission": {
                "status": "not_observed",
                "requested_served_model": self.launch_config.served_model_name,
                "observed_served_models": [],
                "observation_source": "server_/v1/models_listing",
            },
            "shutdown": {
                "status": shutdown.status if shutdown is not None else "not_started",
                "exit_code": shutdown.exit_code if shutdown is not None else None,
                "exit_signal": shutdown.exit_signal if shutdown is not None else None,
                "duration_seconds": shutdown.duration_seconds if shutdown else None,
                "escalation_used": (
                    shutdown.escalation_used if shutdown is not None else False
                ),
            },
            "logs": {
                "stdout_log_path": self.stdout_log_path.name,
                "stderr_log_path": self.stderr_log_path.name,
                "stdout_log_bytes": _file_size(self.stdout_log_path),
                "stderr_log_bytes": _file_size(self.stderr_log_path),
            },
            "unobserved": list(UNOBSERVED_STARTUP_FACTS),
            "claim_boundary": STARTUP_EVIDENCE_CLAIM,
        }
        readiness = startup.readiness if startup is not None else None
        if readiness is not None:
            admission = doc["model_admission"]
            admission["observed_served_models"] = list(readiness.served_models)
            if readiness.success:
                admission["status"] = "admitted"
                admission["observed_served_model"] = readiness.observed_model
            else:
                admission["status"] = "failed"
                admission["failure_class"] = readiness.failure_class
                admission["failure_detail"] = readiness.failure_detail
        return doc


def _exit_kwargs(returncode: int | None) -> dict[str, Any]:
    exit_code, exit_signal = _exit_observations(returncode)
    return {"exit_code": exit_code, "exit_signal": exit_signal}


def _file_size(path: Path) -> int | None:
    try:
        return path.stat().st_size
    except OSError:
        return None


def managed_readiness_config(
    base: VllmExternalConfig,
    launch_config: VllmManagedLaunchConfig,
) -> VllmExternalConfig:
    """Bounded readiness-poll config derived from the run config."""
    return VllmExternalConfig(
        endpoint_url=base.endpoint_url,
        served_model=launch_config.served_model_name,
        max_tokens=base.max_tokens,
        temperature=base.temperature,
        top_p=base.top_p,
        connect_timeout=min(base.connect_timeout, READINESS_POLL_CONNECT_SECONDS),
        request_timeout=min(base.request_timeout, READINESS_POLL_REQUEST_SECONDS),
        max_response_bytes=base.max_response_bytes,
        ctx_size=base.ctx_size,
        lifecycle_ownership=LIFECYCLE_OWNERSHIP_MANAGED,
    )
