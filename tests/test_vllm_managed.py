"""M4 managed-local vLLM lifecycle: launch, admission, shutdown, evidence.

Synthetic tests only. The "vLLM server" is a scripted fake executable (a
deterministic loopback HTTP server in a child process) launched through the
real VllmManagedServer process-ownership path. No real model, vLLM install,
or GPU is involved. The tests cover the M4 acceptance matrix: bounded
launch-configuration validation, executable resolution without installation,
port pre-check without touching foreign processes, readiness polling with
model admission, bounded shutdown with escalation, the startup-scope evidence
artifact kept separate from request-scope evidence, managed binding-class
rules in the validator, and the fail-closed CLI gates.
"""

from __future__ import annotations

import json
import socket
import stat
from pathlib import Path
from typing import Any

import pytest
import typer

from llmgauge.commands import run_helpers
from llmgauge.core.checkpoint_binding import (
    BINDING_CLASS_LLMGAUGE_OBSERVED,
    BINDING_EVIDENCE_CEILING_MANAGED,
    CHECKPOINT_BINDING_SCHEMA_VERSION,
)
from llmgauge.core.checkpoint_provenance import collect_checkpoint_provenance
from llmgauge.core.result_validation import validate_result_dir
from llmgauge.core.run_fingerprint import RUN_FINGERPRINT_FIELD
from llmgauge.runners.vllm_external import VllmExternalConfig
from llmgauge.runners.vllm_managed import (
    DEFAULT_STARTUP_TIMEOUT_SECONDS,
    LIFECYCLE_OWNERSHIP_MANAGED,
    VLLM_STARTUP_EVIDENCE_FILENAME,
    VLLM_STARTUP_EVIDENCE_SCHEMA,
    VllmManagedLaunchConfig,
    VllmManagedLaunchError,
    VllmManagedServer,
    build_launch_argv,
    managed_readiness_config,
    resolve_vllm_executable,
    validate_managed_launch_config,
)

# ---------------------------------------------------------------------------
# Synthetic fake-vllm fixture
# ---------------------------------------------------------------------------

_FAKE_VLLM_SCRIPT = '''#!/usr/bin/env python3
"""Synthetic stand-in for an operator-installed vllm command.

Parses the real launch argv (serve MODEL --host H --port P
--served-model-name NAME ...) and behaves per FAKE_VLLM_MODE:
  ready        serve /version, /v1/models, /v1/chat/completions
  exit         exit(3) immediately (model load failure)
  hang         never serve (startup deadline path)
  ignore_term  serve but ignore SIGTERM (shutdown escalation path)
"""
import json
import os
import signal
import sys
import time
from http.server import BaseHTTPRequestHandler, HTTPServer


def parse(argv):
    model = argv[0]
    name, host, port = model, "127.0.0.1", 8000
    i = 1
    while i < len(argv):
        arg = argv[i]
        if arg == "--host":
            i += 1
            host = argv[i]
        elif arg == "--port":
            i += 1
            port = int(argv[i])
        elif arg == "--served-model-name":
            i += 1
            name = argv[i]
        i += 1
    return model, host, port, name


MODEL, HOST, PORT, NAME = parse(sys.argv[1:])
MODE = os.environ.get("FAKE_VLLM_MODE", "ready")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        return

    def _send(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/version":
            self._send({"version": "0.27.1+synthetic"})
        elif path == "/v1/models":
            self._send({"object": "list", "data": [{"id": NAME, "object": "model"}]})
        else:
            self._send({"error": "not found"}, 404)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        request = json.loads(raw or b"{}")
        if self.path.startswith("/v1/chat/completions"):
            self._send({
                "id": "synthetic-1",
                "object": "chat.completion",
                "model": request.get("model", NAME),
                "choices": [{
                    "index": 0,
                    "message": {"role": "assistant", "content": "synthetic answer"},
                    "finish_reason": "stop",
                }],
                "usage": {"prompt_tokens": 5, "completion_tokens": 2, "total_tokens": 7},
            })
        else:
            self._send({"error": "not found"}, 404)


if MODE == "exit":
    print("synthetic vllm: model load failed", file=sys.stderr)
    sys.exit(3)
if MODE == "hang":
    print("synthetic vllm: hanging before readiness", file=sys.stderr)
    while True:
        time.sleep(3600)
if MODE == "ignore_term":
    signal.signal(signal.SIGTERM, signal.SIG_IGN)

HTTPServer((HOST, PORT), Handler).serve_forever()
'''


def _fake_vllm(tmp_path: Path) -> Path:
    script = tmp_path / "fake-vllm"
    script.write_text(_FAKE_VLLM_SCRIPT, encoding="utf-8")
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    return script


def _free_port() -> int:
    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    port = int(probe.getsockname()[1])
    probe.close()
    return port


def _launch_config(
    tmp_path: Path, *, port: int, **overrides: Any
) -> VllmManagedLaunchConfig:
    (tmp_path / "ckpt").mkdir(exist_ok=True)
    defaults: dict[str, Any] = {
        "executable": str(_fake_vllm(tmp_path)),
        "model_path": str(tmp_path / "ckpt"),
        "served_model_name": "served-ckpt",
        "host": "127.0.0.1",
        "port": port,
        "startup_timeout_seconds": 30.0,
        "shutdown_timeout_seconds": 5.0,
        "readiness_poll_interval_seconds": 0.05,
    }
    defaults.update(overrides)
    return VllmManagedLaunchConfig(**defaults)


def _server(tmp_path: Path, *, port: int, **overrides: Any) -> VllmManagedServer:
    from llmgauge.runners.vllm_http import validate_vllm_endpoint

    launch_config = _launch_config(tmp_path, port=port, **overrides)
    validate_managed_launch_config(launch_config)
    base = VllmExternalConfig(
        endpoint_url=f"http://127.0.0.1:{port}/v1",
        served_model=launch_config.served_model_name,
        max_tokens=32,
        temperature=0.2,
        top_p=0.95,
        connect_timeout=1.0,
        request_timeout=3.0,
        max_response_bytes=100_000,
        ctx_size=2048,
        lifecycle_ownership=LIFECYCLE_OWNERSHIP_MANAGED,
    )
    return VllmManagedServer(
        launch_config=launch_config,
        endpoint=validate_vllm_endpoint(f"http://127.0.0.1:{port}/v1"),
        stdout_log_path=tmp_path / "server.stdout.log",
        stderr_log_path=tmp_path / "server.stderr.log",
        readiness_config=managed_readiness_config(base, launch_config),
    )


# ---------------------------------------------------------------------------
# Launch-configuration admission (no process launched)
# ---------------------------------------------------------------------------


def test_resolve_executable_requires_existing_executable(tmp_path: Path) -> None:
    with pytest.raises(VllmManagedLaunchError, match="never"):
        resolve_vllm_executable(str(tmp_path / "definitely-not-here"))

    non_exec = tmp_path / "not-exec"
    non_exec.write_text("nothing", encoding="utf-8")
    with pytest.raises(VllmManagedLaunchError, match="not executable"):
        resolve_vllm_executable(str(non_exec))

    script = _fake_vllm(tmp_path)
    assert resolve_vllm_executable(str(script)) == str(script)


def test_launch_argv_is_structured_and_bounded(tmp_path: Path) -> None:
    config = _launch_config(
        tmp_path,
        port=8123,
        max_model_len=4096,
        gpu_memory_utilization=0.85,
        dtype="bfloat16",
    )
    argv = build_launch_argv(config)
    assert argv[:3] == [config.executable, "serve", config.model_path]
    assert "--host" in argv and "127.0.0.1" in argv
    assert "--port" in argv and "8123" in argv
    assert "--served-model-name" in argv and "served-ckpt" in argv
    assert "--max-model-len" in argv and "4096" in argv
    assert "--gpu-memory-utilization" in argv and "0.85" in argv
    assert "--dtype" in argv and "bfloat16" in argv
    flags = {item for item in argv if item.startswith("--")}
    assert flags == {
        "--host",
        "--port",
        "--served-model-name",
        "--max-model-len",
        "--gpu-memory-utilization",
        "--dtype",
    }


@pytest.mark.parametrize(
    "overrides,match",
    [
        ({"dtype": "float4"}, "dtype"),
        ({"gpu_memory_utilization": 0.0}, "gpu-memory-utilization"),
        ({"gpu_memory_utilization": 1.5}, "gpu-memory-utilization"),
        ({"max_model_len": 0}, "max-model-len"),
        ({"port": 0}, "port"),
        ({"startup_timeout_seconds": 4.0}, "startup timeout"),
        ({"startup_timeout_seconds": 7201.0}, "startup timeout"),
        ({"shutdown_timeout_seconds": 0.5}, "shutdown timeout"),
        ({"readiness_poll_interval_seconds": 0.01}, "poll interval"),
        ({"served_model_name": "  "}, "served model name"),
    ],
)
def test_validate_launch_config_fails_closed(
    tmp_path: Path, overrides: dict[str, Any], match: str
) -> None:
    (tmp_path / "ckpt").mkdir()
    config = _launch_config(tmp_path, port=overrides.pop("port", 8123), **overrides)
    with pytest.raises(VllmManagedLaunchError, match=match):
        validate_managed_launch_config(config)


def test_validate_launch_config_rejects_missing_model_dir(tmp_path: Path) -> None:
    config = _launch_config(tmp_path, port=8123, model_path=str(tmp_path / "absent"))
    with pytest.raises(VllmManagedLaunchError, match="never downloads"):
        validate_managed_launch_config(config)


def test_managed_readiness_config_bounds_poll_budget() -> None:
    base = VllmExternalConfig(
        endpoint_url="http://127.0.0.1:8123/v1",
        served_model="served-ckpt",
        max_tokens=32,
        temperature=0.2,
        top_p=0.95,
        connect_timeout=30.0,
        request_timeout=600.0,
        max_response_bytes=100_000,
        ctx_size=2048,
    )
    launch = VllmManagedLaunchConfig(
        executable="vllm",
        model_path="/tmp/ckpt",
        served_model_name="served-ckpt",
        host="127.0.0.1",
        port=8123,
    )
    bounded = managed_readiness_config(base, launch)
    assert bounded.connect_timeout <= 2.0
    assert bounded.request_timeout <= 10.0
    assert bounded.lifecycle_ownership == LIFECYCLE_OWNERSHIP_MANAGED
    assert launch.startup_timeout_seconds == DEFAULT_STARTUP_TIMEOUT_SECONDS


# ---------------------------------------------------------------------------
# Process lifecycle (synthetic child processes only)
# ---------------------------------------------------------------------------


def test_startup_ready_admission_and_graceful_shutdown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_VLLM_MODE", "ready")
    port = _free_port()
    server = _server(tmp_path, port=port)
    startup = server.start()
    try:
        assert startup.status == "ready"
        assert startup.pid is not None
        assert startup.readiness is not None and startup.readiness.success
        assert startup.readiness.observed_model == "served-ckpt"
        assert startup.readiness.vllm_version == "0.27.1+synthetic"
    finally:
        shutdown = server.shutdown()
    assert shutdown.status == "graceful"
    assert shutdown.escalation_used is False
    assert shutdown.exit_signal == "SIGTERM"
    # Idempotent: a second shutdown returns the cached record.
    assert server.shutdown() is shutdown

    doc = server.startup_evidence_document()
    assert doc["schema_version"] == VLLM_STARTUP_EVIDENCE_SCHEMA
    assert doc["lifecycle_ownership"] == LIFECYCLE_OWNERSHIP_MANAGED
    assert doc["launch"]["shell"] is False
    assert doc["launch"]["argv"][0] == server.launch_config.executable
    assert (
        doc["launch"]["executable_sha256"]
        and len(doc["launch"]["executable_sha256"]) == 64
    )
    assert doc["process"]["owned_by_llmgauge"] is True
    assert doc["startup"]["status"] == "ready"
    assert doc["model_admission"]["status"] == "admitted"
    assert doc["model_admission"]["observed_served_models"] == ["served-ckpt"]
    assert doc["shutdown"]["status"] == "graceful"
    assert doc["unobserved"]
    assert doc["claim_boundary"]


def test_port_occupied_fails_closed_without_touching_occupant(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_VLLM_MODE", "ready")
    occupant = socket.socket()
    occupant.bind(("127.0.0.1", 0))
    occupant.listen(1)
    port = int(occupant.getsockname()[1])
    try:
        server = _server(tmp_path, port=port)
        startup = server.start()
        assert startup.status == "failed"
        assert startup.failure_class == "endpoint_unavailable"
        assert startup.failure_detail == "endpoint_port_in_use"
        assert server.process is None
        # The foreign listener is untouched: still accepting a connection.
        client = socket.create_connection(("127.0.0.1", port), timeout=1)
        client.close()
    finally:
        occupant.close()
    assert server.shutdown().status == "not_started"


def test_premature_exit_is_recorded_not_retried(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_VLLM_MODE", "exit")
    port = _free_port()
    server = _server(tmp_path, port=port)
    startup = server.start()
    assert startup.status == "failed"
    assert startup.premature_exit is True
    assert startup.exit_code == 3
    assert startup.failure_class == "model_admission_load_failure"
    # Startup failure already shut the (dead) process down.
    assert server.shutdown().status == "already_exited"
    doc = server.startup_evidence_document()
    assert doc["startup"]["premature_exit"] is True
    assert doc["model_admission"]["status"] == "not_observed"


def test_unexpected_readiness_error_shuts_down_and_records_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # An unexpected internal error during polling must not leak the owned
    # process and must leave a validator-acceptable failed startup record.
    monkeypatch.setenv("FAKE_VLLM_MODE", "ready")

    def _boom(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("synthetic transport bug")

    monkeypatch.setattr(
        "llmgauge.runners.vllm_managed.check_readiness_and_model", _boom
    )
    port = _free_port()
    server = _server(tmp_path, port=port)
    startup = server.start()
    assert startup.status == "failed"
    assert startup.failure_class == "startup_failure"
    assert startup.failure_detail == "unexpected_startup_error:RuntimeError"
    # The owned process is never leaked: startup failure already shut it down.
    assert server.shutdown().status in {"graceful", "forced", "already_exited"}
    doc = server.startup_evidence_document()
    assert doc["startup"]["status"] == "failed"
    assert doc["model_admission"]["status"] == "not_observed"


def test_startup_deadline_bounded_and_escalation_used(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_VLLM_MODE", "hang")
    port = _free_port()
    server = _server(
        tmp_path,
        port=port,
        startup_timeout_seconds=5.0,
        shutdown_timeout_seconds=1.0,
    )
    startup = server.start()
    assert startup.status == "failed"
    assert startup.failure_class == "readiness_failure"
    assert startup.readiness_attempts >= 1
    assert startup.startup_duration_seconds is not None
    assert startup.startup_duration_seconds < 20.0
    # The hung process ignored nothing yet; startup cleanup terminated it.
    record = server.shutdown()
    assert record.status in {"graceful", "already_exited", "forced"}

    monkeypatch.setenv("FAKE_VLLM_MODE", "ignore_term")
    port = _free_port()
    stubborn = _server(tmp_path, port=port, shutdown_timeout_seconds=1.0)
    ready = stubborn.start()
    assert ready.status == "ready"
    forced = stubborn.shutdown()
    assert forced.status == "forced"
    assert forced.escalation_used is True
    assert forced.exit_signal == "SIGKILL"


# ---------------------------------------------------------------------------
# End-to-end managed run (synthetic server, real lifecycle controller)
# ---------------------------------------------------------------------------

CONFIG_JSON = json.dumps(
    {"architectures": ["TinyForCausalLM"], "model_type": "tiny"}
).encode()


def _write_checkpoint(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "config.json").write_bytes(CONFIG_JSON)
    (root / "model.safetensors").write_bytes(b"tiny-weight-bytes")
    (root / "tokenizer.json").write_bytes(b'{"tokenizer": "tiny"}')
    (root / "tokenizer_config.json").write_bytes(
        b'{"chat_template": "sys {{ messages }}"}'
    )
    return root


def _managed_resolved(
    tmp_path: Path,
    *,
    url: str,
    port: int,
    provenance: dict[str, Any],
) -> dict[str, Any]:
    return {
        "backend": "vllm",
        "model_id": "ckpt-model",
        "model_profile": "ckpt_vllm",
        "profile": {"label": "Ckpt Vllm", "quant": "operator-label"},
        "config_path": None,
        "model_profiles_path": None,
        "vllm_endpoint": url,
        "served_model": "served-ckpt",
        "connect_timeout": 2.0,
        "request_timeout": 5.0,
        "max_response_bytes": 100_000,
        "vllm_streaming_evidence": False,
        "vllm_managed": True,
        "vllm_launch": {
            "executable": str(_fake_vllm(tmp_path)),
            "model_path": str(tmp_path / "ckpt"),
            "served_model_name": "served-ckpt",
            "host": "127.0.0.1",
            "port": port,
            "max_model_len": None,
            "gpu_memory_utilization": None,
            "dtype": None,
            "startup_timeout_seconds": 30.0,
            "shutdown_timeout_seconds": 5.0,
        },
        "ctx": 2048,
        "max_tokens": 32,
        "temp": 0.2,
        "top_p": 0.95,
        "runtime_label": "synthetic-managed",
        "reasoning_mode": "off",
        "model_source": "model_profile",
        "model_source_kind": "checkpoint_directory",
        "vram_min_headroom_warn_mib": None,
        "checkpoint_provenance": provenance,
        "sampling_profile": None,
        "sampling_profile_overrides": [],
    }


def test_managed_run_end_to_end(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_VLLM_MODE", "ready")
    checkpoint = _write_checkpoint(tmp_path / "ckpt")
    provenance = collect_checkpoint_provenance(
        checkpoint, source_type="model_profile", cache_path=tmp_path / "cache.json"
    )
    port = _free_port()
    out = tmp_path / "m4-run"
    run_helpers.execute_vllm_run(
        suite=Path("core-v1"),
        only="honesty-unknown-tool",
        include="all",
        resolved=_managed_resolved(
            tmp_path,
            url=f"http://127.0.0.1:{port}/v1",
            port=port,
            provenance=provenance,
        ),
        out=out,
        fail_on_failed_prompts=False,
    )
    data = json.loads((out / "llmgauge-result.json").read_text(encoding="utf-8"))
    runtime = data["runtime"]
    assert runtime["lifecycle_ownership"] == LIFECYCLE_OWNERSHIP_MANAGED
    assert runtime["vllm_startup_evidence_captured"] is True
    assert runtime["vllm_startup_evidence_path"] == VLLM_STARTUP_EVIDENCE_FILENAME
    assert runtime["run_fingerprint_eligibility"]["eligible"] is False
    assert RUN_FINGERPRINT_FIELD not in data

    binding = data["runtime"]["checkpoint_binding"]
    assert binding["schema_version"] == CHECKPOINT_BINDING_SCHEMA_VERSION
    assert binding["binding_provenance_class"] == BINDING_CLASS_LLMGAUGE_OBSERVED
    assert binding["lifecycle_ownership"] == LIFECYCLE_OWNERSHIP_MANAGED
    assert binding["status"] == "bound"
    assert binding["evidence_ceiling"] == BINDING_EVIDENCE_CEILING_MANAGED

    startup_doc = json.loads(
        (out / VLLM_STARTUP_EVIDENCE_FILENAME).read_text(encoding="utf-8")
    )
    assert startup_doc["startup"]["status"] == "ready"
    assert startup_doc["model_admission"]["status"] == "admitted"
    assert startup_doc["shutdown"]["status"] == "graceful"

    request_evidence = json.loads(
        (out / "request" / "honesty-unknown-tool.json").read_text(encoding="utf-8")
    )
    assert request_evidence["lifecycle_ownership"] == LIFECYCLE_OWNERSHIP_MANAGED

    assert (out / "logs" / "vllm-server.stderr.log").exists()
    assert validate_result_dir(out) == []


def test_managed_startup_failure_fails_all_prompts_deterministically(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_VLLM_MODE", "exit")
    checkpoint = _write_checkpoint(tmp_path / "ckpt")
    provenance = collect_checkpoint_provenance(
        checkpoint, source_type="model_profile", cache_path=tmp_path / "cache.json"
    )
    port = _free_port()
    out = tmp_path / "m4-fail"
    run_helpers.execute_vllm_run(
        suite=Path("core-v1"),
        only="honesty-unknown-tool",
        include="all",
        resolved=_managed_resolved(
            tmp_path,
            url=f"http://127.0.0.1:{port}/v1",
            port=port,
            provenance=provenance,
        ),
        out=out,
        fail_on_failed_prompts=False,
    )
    data = json.loads((out / "llmgauge-result.json").read_text(encoding="utf-8"))
    assert data["run"]["status"] == "failed"
    assert data["summary"]["failed"] == 1
    startup_doc = json.loads(
        (out / VLLM_STARTUP_EVIDENCE_FILENAME).read_text(encoding="utf-8")
    )
    assert startup_doc["startup"]["status"] == "failed"
    assert startup_doc["startup"]["premature_exit"] is True
    assert startup_doc["model_admission"]["status"] == "not_observed"
    assert startup_doc["shutdown"]["status"] == "already_exited"
    request_evidence = json.loads(
        (out / "request" / "honesty-unknown-tool.json").read_text(encoding="utf-8")
    )
    assert request_evidence["skipped"] is True
    assert request_evidence["failure_class"] == "model_admission_load_failure"
    assert validate_result_dir(out) == []


# ---------------------------------------------------------------------------
# Fail-closed configuration gates
# ---------------------------------------------------------------------------


def _profiles(tmp_path: Path, checkpoint: Path) -> tuple[Path, Path]:
    cfg = tmp_path / "cfg.yaml"
    cfg.write_text("schema_version: llmgauge.config.v0\n", encoding="utf-8")
    profiles = tmp_path / "profiles.yaml"
    profiles.write_text(
        "schema_version: llmgauge.model_profiles.v0\n"
        "models:\n"
        "  ckpt_vllm:\n"
        "    label: Ckpt Vllm\n"
        "    backend: vllm\n"
        "    source_kind: checkpoint_directory\n"
        "    path: " + str(checkpoint) + "\n"
        "    served_model: served-ckpt\n"
        "    vllm_endpoint: http://127.0.0.1:8000/v1\n"
        "  served_ref:\n"
        "    label: Served Ref\n"
        "    backend: vllm\n"
        "    source_kind: served_model_reference\n"
        "    served_model: served-ref\n"
        "    vllm_endpoint: http://127.0.0.1:8000/v1\n",
        encoding="utf-8",
    )
    return cfg, profiles


def _resolve(tmp_path: Path, profile: str, **overrides: Any) -> dict[str, Any]:
    checkpoint = _write_checkpoint(tmp_path / "ckpt")
    cfg, profiles = _profiles(tmp_path, checkpoint)
    kwargs: dict[str, Any] = {
        "model_id": None,
        "model_profile": profile,
        "config_path": cfg,
        "model_profiles_path": profiles,
        "model_path": None,
        "llama_cli": None,
        "ctx": None,
        "max_tokens": None,
        "temp": None,
        "top_p": None,
        "batch": None,
        "ubatch": None,
        "gpu_layers": None,
        "backend": "vllm",
        "vllm_endpoint": "http://127.0.0.1:8000/v1",
    }
    kwargs.update(overrides)
    return run_helpers.resolve_run_options(**kwargs)


def test_managed_requires_checkpoint_directory_profile(tmp_path: Path) -> None:
    with pytest.raises(typer.BadParameter, match="checkpoint_directory"):
        _resolve(tmp_path, "served_ref", vllm_managed=True, vllm_executable="vllm")


def test_managed_requires_executable_without_installing(tmp_path: Path) -> None:
    with pytest.raises(typer.BadParameter, match="vllm-executable"):
        _resolve(tmp_path, "ckpt_vllm", vllm_managed=True)
    with pytest.raises(typer.BadParameter, match="not found"):
        _resolve(
            tmp_path,
            "ckpt_vllm",
            vllm_managed=True,
            vllm_executable=str(tmp_path / "absent-vllm"),
        )


def test_managed_rejects_endpoint_path_component(tmp_path: Path) -> None:
    with pytest.raises(typer.BadParameter, match="root-served"):
        _resolve(
            tmp_path,
            "ckpt_vllm",
            vllm_managed=True,
            vllm_executable=str(_fake_vllm(tmp_path)),
            vllm_endpoint="http://127.0.0.1:8000/prefix/v1",
        )


def test_managed_rejects_non_vllm_backend(tmp_path: Path) -> None:
    with pytest.raises(typer.BadParameter, match="backend=vllm"):
        _resolve(
            tmp_path,
            "ckpt_vllm",
            backend="llama.cpp",
            vllm_managed=True,
            vllm_executable=str(_fake_vllm(tmp_path)),
        )


def test_managed_rejects_bad_dtype(tmp_path: Path) -> None:
    with pytest.raises(typer.BadParameter, match="dtype"):
        _resolve(
            tmp_path,
            "ckpt_vllm",
            vllm_managed=True,
            vllm_executable=str(_fake_vllm(tmp_path)),
            vllm_dtype="float4",
        )


def test_managed_multi_turn_fails_closed(tmp_path: Path) -> None:
    resolved = _managed_resolved(
        tmp_path, url="http://127.0.0.1:8000/v1", port=8000, provenance={}
    )
    with pytest.raises(typer.Exit):
        run_helpers.execute_multi_turn_run(
            suite=Path("core-v1"),
            only=None,
            include="all",
            profile=None,
            resolved=resolved,
            out=tmp_path / "unused",
            fail_on_failed_prompts=False,
            conversation_task=tmp_path / "absent-task.yaml",
            conversation_id=None,
            max_turns=None,
        )
