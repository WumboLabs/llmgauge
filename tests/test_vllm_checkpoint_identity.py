"""M3 vLLM first-class model identity: admission, binding, fingerprint, export.

Synthetic tests only. Every server here is a deterministic loopback fixture
(labeled synthetic); no real model or runtime is launched. The tests cover the
M3 acceptance matrix: checkpoint_directory + vLLM admission gated on eligible
M2 provenance before any HTTP, served-model binding with operator_declared
provenance, tokenizer/template/quantization identity persistence, sampling-
profile persistence, the new server-backed v7 run fingerprint, validator
mutation rejection, report/compare disclosure, and public-export privacy.
"""

from __future__ import annotations

import copy
import json
import re
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

import pytest
import typer

from llmgauge.commands import run_helpers
from llmgauge.core.artifacts import write_json
from llmgauge.core.checkpoint_binding import (
    BINDING_CLASS_OPERATOR_DECLARED,
    CHECKPOINT_BINDING_SCHEMA_VERSION,
)
from llmgauge.core.checkpoint_provenance import (
    CHECKPOINT_PROVENANCE_KIND,
    collect_checkpoint_provenance,
)
from llmgauge.core.compare import (
    _build_comparison_scope,
    _build_publish_readiness_notes,
    _checkpoint_identity_values,
)
from llmgauge.core.public_export import export_public_run
from llmgauge.core.result_validation import validate_result_dir
from llmgauge.core.run_fingerprint import (
    RUN_FINGERPRINT_FIELD,
    RUN_FINGERPRINT_PAYLOAD_VERSION_V7,
    RUN_FINGERPRINT_SCHEMA_VERSION_V6,
    RUN_FINGERPRINT_SCHEMA_VERSION_V7,
    FingerprintUnavailable,
    attach_run_fingerprint,
    build_run_fingerprint_metadata,
    build_run_fingerprint_payload,
    verify_run_fingerprint,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

CONFIG_JSON = json.dumps(
    {"architectures": ["TinyForCausalLM"], "model_type": "tiny"}
).encode()


def _write_checkpoint(root: Path) -> Path:
    """A tiny pytest-generated checkpoint that is M2 fingerprint-eligible."""

    root.mkdir(parents=True, exist_ok=True)
    (root / "config.json").write_bytes(CONFIG_JSON)
    (root / "model.safetensors").write_bytes(b"tiny-weight-bytes")
    (root / "tokenizer.json").write_bytes(b'{"tokenizer": "tiny"}')
    (root / "tokenizer_config.json").write_bytes(
        b'{"chat_template": "sys {{ messages }}"}'
    )
    return root


class _Handler(BaseHTTPRequestHandler):
    state: dict[str, Any] = {}

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        return

    def _send(self, body: bytes, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path.endswith("/version"):
            if self.state.get("version_mode") == "missing":
                self._send(b"{}", 404)
                return
            self._send(
                json.dumps(
                    {"version": self.state.get("vllm_version", "0.27.1")}
                ).encode()
            )
            return
        if path.endswith("/models"):
            self._send(
                json.dumps(
                    {
                        "object": "list",
                        "data": [
                            {
                                "id": self.state.get("model_id", "served-ckpt"),
                                "object": "model",
                            }
                        ],
                    }
                ).encode()
            )
            return
        self._send(b"{}", 404)

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        self.state["last_request_body"] = raw
        request = json.loads(raw.decode("utf-8"))
        if request.get("model") != self.state.get("model_id", "served-ckpt"):
            self._send(b'{"error":"bad model"}', 400)
            return
        self._send(
            json.dumps(
                {
                    "id": "chatcmpl-1",
                    "model": request.get("model"),
                    "choices": [
                        {
                            "index": 0,
                            "message": {
                                "role": "assistant",
                                "content": "tiny answer",
                            },
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 4,
                        "completion_tokens": 2,
                        "total_tokens": 6,
                    },
                }
            ).encode()
        )


@pytest.fixture
def server():
    _Handler.state.clear()
    httpd = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}", _Handler.state
    httpd.shutdown()
    httpd.server_close()


class _SyntheticVramSampler:
    DEFAULT_INTERVAL_SECONDS = 0.1

    def start(self) -> None:
        return None

    def stop(self) -> tuple[list[dict[str, Any]], list[str]]:
        return [], ["synthetic_sampler_disabled"]


@pytest.fixture
def no_vram_sampler(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "llmgauge.commands.run_helpers.VramSampler", _SyntheticVramSampler
    )


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


def _resolve(tmp_path: Path, checkpoint: Path, profile: str, **overrides: Any) -> dict:
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


def _resolved_for_run(
    url: str,
    provenance: dict[str, Any] | None,
    *,
    served_model: str = "served-ckpt",
    sampling_profile: dict[str, Any] | None = None,
    overrides: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "model_id": "ckpt-model",
        "model_profile": "ckpt_vllm",
        "profile": {"label": "Ckpt Vllm", "quant": "operator-label"},
        "config_path": None,
        "model_profiles_path": None,
        "vllm_endpoint": url,
        "served_model": served_model,
        "connect_timeout": 2.0,
        "request_timeout": 5.0,
        "max_response_bytes": 100_000,
        "vllm_streaming_evidence": False,
        "ctx": 2048,
        "max_tokens": 32,
        "temp": 0.2,
        "top_p": 0.95,
        "runtime_label": "synthetic-loopback",
        "reasoning_mode": "off",
        "model_source": "model_profile",
        "model_source_kind": (
            "checkpoint_directory" if provenance else "served_model_reference"
        ),
        "vram_min_headroom_warn_mib": None,
        "checkpoint_provenance": provenance,
        "sampling_profile": sampling_profile,
        "sampling_profile_overrides": overrides or [],
    }


def _run(tmp_path: Path, resolved: dict[str, Any], *, name: str = "m3-run") -> Path:
    out = tmp_path / name
    run_helpers.execute_vllm_run(
        suite=Path("core-v1"),
        only="honesty-unknown-tool",
        include="all",
        resolved=resolved,
        out=out,
        fail_on_failed_prompts=False,
    )
    return out


def _bound_run(tmp_path: Path, server, **resolved_kw: Any) -> Path:
    name = resolved_kw.pop("name", "bound-run")
    url, state = server
    state["model_id"] = resolved_kw.get("served_model", "served-ckpt")
    checkpoint = _write_checkpoint(tmp_path / "ckpt")
    provenance = collect_checkpoint_provenance(
        checkpoint, source_type="model_profile", cache_path=tmp_path / "cache.json"
    )
    resolved = _resolved_for_run(url, provenance, **resolved_kw)
    return _run(tmp_path, resolved, name=name)


def _load(out: Path) -> tuple[Path, dict[str, Any]]:
    path = out / "llmgauge-result.json"
    return path, json.loads(path.read_text(encoding="utf-8"))


def _consistent_profile() -> dict[str, Any]:
    """A profile whose non-overridden settings agree with the run's runtime
    settings (temp 0.2, top_p 0.95, reasoning_mode off), as the validator
    cross-checks."""

    from llmgauge.core.sampling_profiles import canonical_settings_sha256

    settings = {
        "min_p": None,
        "reasoning_budget": None,
        "reasoning_effort": None,
        "reasoning_mode": "off",
        "seed": None,
        "temperature": 0.2,
        "top_k": None,
        "top_p": 0.95,
    }
    return {
        "profile_id": "vllm-baseline-v1",
        "profile_version": "1",
        "profile_kind": "controlled",
        "canonical_settings_sha256": canonical_settings_sha256(settings),
        "settings": settings,
        "source": "config",
    }


# ---------------------------------------------------------------------------
# 1-5: admission gating before HTTP
# ---------------------------------------------------------------------------


def test_checkpoint_directory_vllm_admitted_with_eligible_provenance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_if_called(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("no HTTP may occur during resolution")

    monkeypatch.setattr(run_helpers, "check_readiness_and_model", fail_if_called)
    checkpoint = _write_checkpoint(tmp_path / "ckpt")
    resolved = _resolve(tmp_path, checkpoint, "ckpt_vllm")
    assert resolved["backend"] == "vllm"
    assert resolved["model_source_kind"] == "checkpoint_directory"
    provenance = resolved["checkpoint_provenance"]
    assert provenance["status"] == "available"
    assert provenance["fingerprint_eligible"] is True
    assert provenance["provenance_kind"] == CHECKPOINT_PROVENANCE_KIND


def test_partial_provenance_rejected_before_http(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_if_called(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("no HTTP may occur when identity is unacceptable")

    monkeypatch.setattr(run_helpers, "check_readiness_and_model", fail_if_called)
    checkpoint = _write_checkpoint(tmp_path / "ckpt")
    # No tokenizer asset -> partial provenance -> ineligible.
    (checkpoint / "tokenizer.json").unlink()
    (checkpoint / "tokenizer_config.json").unlink()
    with pytest.raises(typer.BadParameter) as exc:
        _resolve(tmp_path, checkpoint, "ckpt_vllm")
    message = str(exc.value)
    assert "partial" in message
    assert "fingerprint-eligible" in message
    assert "served_model_reference" in message


def test_unavailable_provenance_rejected_before_http(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_if_called(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("no HTTP may occur when identity is unacceptable")

    monkeypatch.setattr(run_helpers, "check_readiness_and_model", fail_if_called)
    checkpoint = tmp_path / "empty-ckpt"
    checkpoint.mkdir()
    with pytest.raises(typer.BadParameter) as exc:
        _resolve(tmp_path, checkpoint, "ckpt_vllm")
    assert "unavailable" in str(exc.value)


def test_missing_served_model_rejected(tmp_path: Path) -> None:
    checkpoint = _write_checkpoint(tmp_path / "ckpt")
    cfg, profiles = _profiles(tmp_path, checkpoint)
    profiles.write_text(
        profiles.read_text(encoding="utf-8").replace(
            "    served_model: served-ckpt\n", ""
        ),
        encoding="utf-8",
    )
    with pytest.raises(typer.BadParameter) as exc:
        run_helpers.resolve_run_options(
            model_id=None,
            model_profile="ckpt_vllm",
            config_path=cfg,
            model_profiles_path=profiles,
            model_path=None,
            llama_cli=None,
            ctx=None,
            max_tokens=None,
            temp=None,
            top_p=None,
            batch=None,
            ubatch=None,
            gpu_layers=None,
            backend="vllm",
            vllm_endpoint="http://127.0.0.1:8000/v1",
        )
    message = str(exc.value)
    assert "explicit served_model" in message
    assert "never inferred" in message


def test_served_model_never_inferred_from_path_or_label(tmp_path: Path) -> None:
    # A checkpoint directory named like a model must not supply the served name.
    checkpoint = _write_checkpoint(tmp_path / "Qwen3-0.6B")
    with pytest.raises(typer.BadParameter) as exc:
        _resolve(tmp_path, checkpoint, "ckpt_vllm", served_model="   ")
    assert "explicit served_model" in str(exc.value)


def test_direct_model_path_stays_rejected_for_vllm(tmp_path: Path) -> None:
    checkpoint = _write_checkpoint(tmp_path / "ckpt")
    with pytest.raises(typer.BadParameter) as exc:
        _resolve(tmp_path, checkpoint, "ckpt_vllm", model_path=checkpoint)
    assert "--model-path" in str(exc.value)


# ---------------------------------------------------------------------------
# 6-8: compatibility of existing modes
# ---------------------------------------------------------------------------


def test_served_model_reference_vllm_unchanged(
    tmp_path: Path, server, no_vram_sampler
) -> None:
    url, state = server
    state["model_id"] = "served-ref"
    checkpoint = _write_checkpoint(tmp_path / "ckpt")
    resolved = _resolve(tmp_path, checkpoint, "served_ref", vllm_endpoint=url)
    assert resolved["model_source_kind"] == "served_model_reference"
    assert resolved["checkpoint_provenance"] is None
    out = _run(
        tmp_path,
        _resolved_for_run(url, None, served_model="served-ref"),
        name="served-ref-run",
    )
    result = json.loads((out / "llmgauge-result.json").read_text(encoding="utf-8"))
    assert result["model"]["provenance"]["provenance_kind"] == "served_model_only"
    assert result["model"]["provenance"]["sha256"] is None
    assert result["runtime"].get("checkpoint_binding") is None
    # served_model_reference never gains the new fingerprint.
    assert RUN_FINGERPRINT_FIELD not in result
    assert validate_result_dir(out) == []


def test_legacy_vllm_profile_shape_unchanged(tmp_path: Path) -> None:
    cfg = tmp_path / "cfg.yaml"
    cfg.write_text("schema_version: llmgauge.config.v0\n", encoding="utf-8")
    profiles = tmp_path / "profiles.yaml"
    profiles.write_text(
        "schema_version: llmgauge.model_profiles.v0\n"
        "models:\n"
        "  legacy_vllm:\n"
        "    label: Legacy Vllm\n"
        "    backend: vllm\n"
        "    served_model: legacy-served\n",
        encoding="utf-8",
    )
    resolved = run_helpers.resolve_run_options(
        model_id=None,
        model_profile="legacy_vllm",
        config_path=cfg,
        model_profiles_path=profiles,
        model_path=None,
        llama_cli=None,
        ctx=None,
        max_tokens=None,
        temp=None,
        top_p=None,
        batch=None,
        ubatch=None,
        gpu_layers=None,
        vllm_endpoint="http://127.0.0.1:8000/v1",
    )
    assert resolved["model_source_kind"] == "served_model_reference"
    assert resolved["served_model"] == "legacy-served"


def test_gguf_llama_path_unchanged(tmp_path: Path) -> None:
    gguf = tmp_path / "model.gguf"
    gguf.write_text("x", encoding="utf-8")
    cfg = tmp_path / "cfg.yaml"
    cfg.write_text(
        "schema_version: llmgauge.config.v0\nruntime:\n  llama_cli: /bin/true\n",
        encoding="utf-8",
    )
    profiles = tmp_path / "profiles.yaml"
    profiles.write_text(
        "schema_version: llmgauge.model_profiles.v0\n"
        "models:\n"
        "  gguf:\n"
        "    label: GGUF\n"
        "    path: " + str(gguf) + "\n",
        encoding="utf-8",
    )
    resolved = run_helpers.resolve_run_options(
        model_id=None,
        model_profile="gguf",
        config_path=cfg,
        model_profiles_path=profiles,
        model_path=None,
        llama_cli=None,
        ctx=None,
        max_tokens=None,
        temp=None,
        top_p=None,
        batch=None,
        ubatch=None,
        gpu_layers=None,
    )
    assert resolved["backend"] == "llama.cpp"
    assert resolved["model_source_kind"] == "gguf_file"
    assert resolved.get("checkpoint_provenance") is None


# ---------------------------------------------------------------------------
# 9-16: result identity content
# ---------------------------------------------------------------------------


def test_checkpoint_identity_and_binding_persist(
    tmp_path, server, no_vram_sampler
) -> None:
    out = _bound_run(tmp_path, server)
    result = json.loads((out / "llmgauge-result.json").read_text(encoding="utf-8"))
    provenance = result["model"]["provenance"]
    assert provenance["provenance_kind"] == CHECKPOINT_PROVENANCE_KIND
    assert provenance["status"] == "available"
    assert provenance["fingerprint_eligible"] is True
    assert provenance["manifest"] and provenance["manifest_sha256"]

    binding = result["runtime"]["checkpoint_binding"]
    assert binding["schema_version"] == CHECKPOINT_BINDING_SCHEMA_VERSION
    assert binding["binding_provenance_class"] == BINDING_CLASS_OPERATOR_DECLARED
    assert binding["status"] == "bound"
    assert binding["requested_served_model"] == binding["observed_served_model"]
    assert binding["checkpoint_public_fingerprint"] == provenance["public_fingerprint"]
    assert binding["effective_runtime_chat_template"] == "unobserved"
    assert binding["effective_runtime_quantization"] == "unavailable"
    assert "does not prove" in binding["evidence_ceiling"]
    assert validate_result_dir(out) == []


def test_local_checkpoint_path_absent_from_result(
    tmp_path, server, no_vram_sampler
) -> None:
    out = _bound_run(tmp_path, server)
    blob = (out / "llmgauge-result.json").read_text(encoding="utf-8")
    assert str(tmp_path / "ckpt") not in blob
    binding = json.loads(blob)["runtime"]["checkpoint_binding"]
    assert not any(
        key in binding for key in ("checkpoint_path", "path", "root", "result_dir")
    )
    result = json.loads(blob)
    assert result["model"]["model_path"] == "redacted"


def test_tokenizer_template_quant_identity_persisted(
    tmp_path, server, no_vram_sampler
) -> None:
    out = _bound_run(tmp_path, server)
    result = json.loads((out / "llmgauge-result.json").read_text(encoding="utf-8"))
    provenance = result["model"]["provenance"]
    assert provenance["tokenizer_identity"]["status"] == "available"
    assert provenance["chat_template_identity"]["status"] == "available"
    # Declared quantization is a local-file fact; unquantized -> absent.
    assert provenance["checkpoint_quantization"]["status"] == "absent"
    assert provenance["effective_quantization"]["status"] == "unavailable"
    # Profile `quant` stays a descriptive operator label, never upgraded.
    assert result["model"]["quant"] == "operator-label"


def test_sampling_profile_identity_persists(tmp_path, server, no_vram_sampler) -> None:
    profile = _consistent_profile()
    out = _bound_run(
        tmp_path,
        server,
        sampling_profile=profile,
        overrides=[],
        name="profile-run",
    )
    result = json.loads((out / "llmgauge-result.json").read_text(encoding="utf-8"))
    persisted = result["runtime"]["profile"]
    assert persisted["profile_id"] == "vllm-baseline-v1"
    assert (
        persisted["canonical_settings_sha256"] == profile["canonical_settings_sha256"]
    )
    assert validate_result_dir(out) == []


def test_request_semantics_unchanged_by_identity(
    tmp_path, server, no_vram_sampler
) -> None:
    url, state = server
    state["model_id"] = "served-ckpt"
    _bound_run(tmp_path, server)
    body = json.loads(state["last_request_body"].decode("utf-8"))
    assert set(body) == {
        "model",
        "messages",
        "max_tokens",
        "temperature",
        "top_p",
        "stream",
    }
    assert body["stream"] is False
    assert "return_token_ids" not in body


# ---------------------------------------------------------------------------
# 5, 10: served-model mismatch + binding class fail-closed
# ---------------------------------------------------------------------------


def test_served_model_mismatch_fails_before_generation(
    tmp_path, server, no_vram_sampler
) -> None:
    url, state = server
    state["model_id"] = "different-model"
    checkpoint = _write_checkpoint(tmp_path / "ckpt")
    provenance = collect_checkpoint_provenance(
        checkpoint, source_type="model_profile", cache_path=tmp_path / "cache.json"
    )
    resolved = _resolved_for_run(url, provenance, served_model="served-ckpt")
    out = tmp_path / "mismatch-run"
    result = run_helpers.execute_vllm_run(
        suite=Path("core-v1"),
        only="honesty-unknown-tool",
        include="all",
        resolved=resolved,
        out=out,
        fail_on_failed_prompts=False,
    )
    assert result["summary"]["failed"] == 1
    assert result["summary"]["completed"] == 0
    entry = result["results"][0]
    assert entry["failure_class"] == "served_model_mismatch"
    # No completion was generated against a fallback model.
    assert (out / "raw" / "honesty-unknown-tool.output.txt").read_text() == ""
    assert RUN_FINGERPRINT_FIELD not in result
    assert validate_result_dir(out) == []


def test_external_result_cannot_claim_llmgauge_observed_binding(
    tmp_path, server, no_vram_sampler
) -> None:
    out = _bound_run(tmp_path, server)
    path, result = _load(out)
    result["runtime"]["checkpoint_binding"]["binding_provenance_class"] = (
        "llmgauge_observed"
    )
    write_json(path, result)
    errors = validate_result_dir(out)
    assert any("operator_declared" in error for error in errors)


# ---------------------------------------------------------------------------
# 24-27: fingerprint behavior
# ---------------------------------------------------------------------------


def test_bound_run_emits_v7_and_verifies(tmp_path, server, no_vram_sampler) -> None:
    out = _bound_run(tmp_path, server)
    result = json.loads((out / "llmgauge-result.json").read_text(encoding="utf-8"))
    fingerprint = result[RUN_FINGERPRINT_FIELD]
    assert fingerprint["schema_version"] == RUN_FINGERPRINT_SCHEMA_VERSION_V7
    assert verify_run_fingerprint(out, result) == []
    payload = build_run_fingerprint_payload(out, result)
    assert payload["schema_version"] == RUN_FINGERPRINT_PAYLOAD_VERSION_V7
    assert payload["backend"]["runtime_provenance_kind"] == "external_server"
    assert payload["backend"]["provenance"]["vllm_version"] == "0.27.1"
    assert payload["backend"]["checkpoint_binding"]["status"] == "bound"
    # No endpoint host/IP/port, no checkpoint absolute path.
    blob = json.dumps(payload)
    assert str(tmp_path / "ckpt") not in blob
    assert "endpoint_identity" not in json.dumps(payload["backend"])
    assert "127.0.0.1" not in blob


def test_missing_server_version_makes_v7_unavailable(
    tmp_path, server, no_vram_sampler
) -> None:
    url, state = server
    state["model_id"] = "served-ckpt"
    state["version_mode"] = "missing"
    out = _bound_run(tmp_path, server, name="noversion-run")
    result = json.loads((out / "llmgauge-result.json").read_text(encoding="utf-8"))
    # Result remains valid under the external-server evidence ceiling...
    assert validate_result_dir(out) == []
    assert result["model"]["provenance"]["status"] == "available"
    # ...but the server-backed fingerprint is unavailable with a precise reason.
    assert RUN_FINGERPRINT_FIELD not in result
    assert result["runtime"]["checkpoint_binding"]["fingerprint_eligible"] is False
    assert (
        "/version"
        in result["runtime"]["checkpoint_binding"]["fingerprint_ineligible_reason"]
    )
    with pytest.raises(FingerprintUnavailable) as exc:
        build_run_fingerprint_payload(
            out, result, payload_version=RUN_FINGERPRINT_PAYLOAD_VERSION_V7
        )
    assert "version" in str(exc.value)


def test_v6_still_selected_for_non_vllm_checkpoint_result(tmp_path: Path) -> None:
    from test_checkpoint_run_fingerprint import (
        _directory_provenance,
        _write_directory_run,
    )

    provenance = _directory_provenance(tmp_path)
    result_dir, result = _write_directory_run(
        tmp_path, provenance, run_name="v6-direct-run"
    )
    fingerprint = attach_run_fingerprint(result_dir, result)
    assert fingerprint is not None
    assert fingerprint["schema_version"] == RUN_FINGERPRINT_SCHEMA_VERSION_V6


def test_frozen_v0_v5_goldens_and_v6_stability(tmp_path: Path) -> None:
    # Direct golden proof that adding v7 did not move any frozen version.
    from test_checkpoint_run_fingerprint import (
        FROZEN_V0_VALUE,
        FROZEN_V3_VALUE,
        FROZEN_V4_VALUE,
        FROZEN_V5_VALUE,
        _directory_provenance,
        _write_directory_run,
    )
    from test_run_fingerprint import _write_fingerprintable_run

    result_dir, result = _write_fingerprintable_run(tmp_path)
    assert (
        build_run_fingerprint_metadata(result_dir, result)["value"] == FROZEN_V0_VALUE
    )
    extended = copy.deepcopy(result)
    extended["runtime"].update(
        {
            "top_k": 40,
            "top_k_state": "explicit",
            "min_p": 0.05,
            "min_p_state": "explicit",
            "seed": 7,
            "seed_state": "explicit",
            "parallel_sequences": 1,
            "cache_type_k": "f16",
            "cache_type_k_state": "explicit",
            "cache_type_v": "f16",
            "cache_type_v_state": "explicit",
            "reasoning_effort": "high",
            "reasoning_effort_state": "explicit",
            "reasoning_budget": -1,
            "reasoning_budget_state": "explicit",
        }
    )
    assert (
        build_run_fingerprint_metadata(result_dir, extended)["value"] == FROZEN_V3_VALUE
    )
    controlled = copy.deepcopy(result)
    controlled["runtime"].update(
        {
            "fit": "off",
            "fit_state": "explicit",
            "reasoning_preserve": False,
            "reasoning_preserve_state": "explicit",
            "spec_type": "none",
            "spec_type_state": "explicit",
        }
    )
    assert (
        build_run_fingerprint_metadata(result_dir, controlled)["value"]
        == FROZEN_V4_VALUE
    )
    profiled = copy.deepcopy(controlled)
    profiled["runtime"]["profile"] = {
        "profile_id": "p",
        "profile_version": "1",
        "canonical_settings_sha256": "e" * 64,
    }
    assert (
        build_run_fingerprint_metadata(result_dir, profiled)["value"] == FROZEN_V5_VALUE
    )

    # v6 stability: recomputation is byte-reproducible for a directory result.
    provenance = _directory_provenance(tmp_path)
    v6_dir, v6_result = _write_directory_run(tmp_path, provenance, run_name="v6-golden")
    v6_meta = build_run_fingerprint_metadata(v6_dir, v6_result)
    assert v6_meta["schema_version"] == RUN_FINGERPRINT_SCHEMA_VERSION_V6
    assert (
        build_run_fingerprint_metadata(v6_dir, v6_result)["value"] == v6_meta["value"]
    )


def test_vllm_result_with_wrong_fingerprint_version_rejected(
    tmp_path, server, no_vram_sampler
) -> None:
    out = _bound_run(tmp_path, server)
    path, result = _load(out)
    result[RUN_FINGERPRINT_FIELD]["schema_version"] = RUN_FINGERPRINT_SCHEMA_VERSION_V6
    write_json(path, result)
    errors = validate_result_dir(out)
    assert any("v7 run_fingerprint" in error for error in errors)


def test_direct_checkpoint_result_cannot_claim_v7(tmp_path: Path) -> None:
    from test_checkpoint_run_fingerprint import (
        _directory_provenance,
        _write_directory_run,
    )

    provenance = _directory_provenance(tmp_path)
    result_dir, result = _write_directory_run(
        tmp_path, provenance, run_name="v6-not-v7-run"
    )
    fingerprint = attach_run_fingerprint(result_dir, result)
    assert fingerprint is not None
    fingerprint["schema_version"] = RUN_FINGERPRINT_SCHEMA_VERSION_V7
    write_json(result_dir / "llmgauge-result.json", result)
    errors = verify_run_fingerprint(result_dir, result)
    assert errors


# ---------------------------------------------------------------------------
# 21-22: mutation proofs on a valid bound result
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("field", ["requested_served_model", "observed_served_model"])
def test_binding_served_model_mutation_rejected(
    tmp_path, server, no_vram_sampler, field: str
) -> None:
    out = _bound_run(tmp_path, server)
    path, result = _load(out)
    result["runtime"]["checkpoint_binding"][field] = "mutated-name"
    write_json(path, result)
    assert validate_result_dir(out)


def test_binding_fingerprint_mutation_rejected(
    tmp_path, server, no_vram_sampler
) -> None:
    out = _bound_run(tmp_path, server)
    path, result = _load(out)
    result["runtime"]["checkpoint_binding"]["checkpoint_public_fingerprint"] = (
        "sha256:0000000000000000"
    )
    write_json(path, result)
    assert validate_result_dir(out)


def test_checkpoint_manifest_mutation_rejected(
    tmp_path, server, no_vram_sampler
) -> None:
    out = _bound_run(tmp_path, server)
    path, result = _load(out)
    result["model"]["provenance"]["manifest"][0]["sha256"] = "f" * 64
    write_json(path, result)
    assert validate_result_dir(out)


def test_binding_path_field_rejected(tmp_path, server, no_vram_sampler) -> None:
    out = _bound_run(tmp_path, server)
    path, result = _load(out)
    result["runtime"]["checkpoint_binding"]["checkpoint_path"] = "/secret/root"
    write_json(path, result)
    errors = validate_result_dir(out)
    assert any("checkpoint_path" in error for error in errors)


def test_run_fingerprint_value_mutation_rejected(
    tmp_path, server, no_vram_sampler
) -> None:
    out = _bound_run(tmp_path, server)
    path, result = _load(out)
    result[RUN_FINGERPRINT_FIELD]["value"] = "sha256:" + "0" * 64
    write_json(path, result)
    assert validate_result_dir(out)


def test_runtime_version_mutation_rejected(tmp_path, server, no_vram_sampler) -> None:
    out = _bound_run(tmp_path, server)
    path, result = _load(out)
    result["runtime"]["backend_provenance"]["vllm_version"] = "9.9.9"
    write_json(path, result)
    assert validate_result_dir(out)


def test_sampling_profile_identity_mutation_rejected(
    tmp_path, server, no_vram_sampler
) -> None:
    profile = _consistent_profile()
    out = _bound_run(
        tmp_path,
        server,
        sampling_profile=profile,
        overrides=[],
        name="mut-profile-run",
    )
    path, result = _load(out)
    result["runtime"]["profile"]["canonical_settings_sha256"] = "c" * 64
    write_json(path, result)
    assert validate_result_dir(out)


# ---------------------------------------------------------------------------
# 18, 20, 19: report / compare / export
# ---------------------------------------------------------------------------


def test_report_renders_binding_caveat(tmp_path, server, no_vram_sampler) -> None:
    out = _bound_run(tmp_path, server)
    report = (out / "report.md").read_text(encoding="utf-8")
    assert "Server Identity and Checkpoint Binding" in report
    assert "operator_declared" in report
    assert "does not prove which local checkpoint bytes" in report
    assert "Effective runtime chat template: unobserved" in report
    assert str(tmp_path / "ckpt") not in report


def test_compare_rejects_false_checkpoint_equivalence(
    tmp_path, server, no_vram_sampler
) -> None:
    a = _bound_run(tmp_path, server, name="cmp-a")
    # Second run against a different checkpoint (different fingerprint).
    url, state = server
    state["model_id"] = "served-ckpt"
    checkpoint_b = tmp_path / "ckpt-b"
    checkpoint_b.mkdir()
    (checkpoint_b / "config.json").write_bytes(CONFIG_JSON)
    (checkpoint_b / "model.safetensors").write_bytes(b"different-weight-bytes")
    (checkpoint_b / "tokenizer.json").write_bytes(b'{"tokenizer": "tiny"}')
    (checkpoint_b / "tokenizer_config.json").write_bytes(
        b'{"chat_template": "sys {{ messages }}"}'
    )
    provenance_b = collect_checkpoint_provenance(
        checkpoint_b, source_type="model_profile", cache_path=tmp_path / "cache-b.json"
    )
    b = _run(tmp_path, _resolved_for_run(url, provenance_b), name="cmp-b")
    ra = json.loads((a / "llmgauge-result.json").read_text(encoding="utf-8"))
    rb = json.loads((b / "llmgauge-result.json").read_text(encoding="utf-8"))
    # Same served name, same model_id -> only the checkpoint fingerprint differs.
    assert ra["model"]["served_model"] == rb["model"]["served_model"]
    assert (
        ra["model"]["provenance"]["public_fingerprint"]
        != rb["model"]["provenance"]["public_fingerprint"]
    )
    assert len(_checkpoint_identity_values([ra, rb])) == 2
    scope = "\n".join(_build_comparison_scope([ra, rb]))
    assert "Like-for-like quality comparison: no" in scope
    assert "do not establish the same checkpoint bytes" in scope
    notes = "\n".join(_build_publish_readiness_notes([ra, rb]))
    assert "Mixed directory-bound checkpoint identities: yes" in notes


def test_compare_same_checkpoint_stays_like_for_like(
    tmp_path, server, no_vram_sampler
) -> None:
    a = _bound_run(tmp_path, server, name="same-a")
    b = _bound_run(tmp_path, server, name="same-b")
    ra = json.loads((a / "llmgauge-result.json").read_text(encoding="utf-8"))
    rb = json.loads((b / "llmgauge-result.json").read_text(encoding="utf-8"))
    scope = "\n".join(_build_comparison_scope([ra, rb]))
    assert "Like-for-like quality comparison: yes" in scope


def test_public_export_strips_private_identity(
    tmp_path, server, no_vram_sampler
) -> None:
    out = _bound_run(tmp_path, server)
    exported = tmp_path / "public"
    export_public_run(out, exported)
    result = json.loads((exported / "llmgauge-result.json").read_text(encoding="utf-8"))
    assert "provenance" not in result["model"]
    assert "checkpoint_binding" not in result["runtime"]
    identity = result["model"]["checkpoint_identity"]
    assert identity["binding"]["binding_provenance_class"] == "operator_declared"
    assert "does not prove" in identity["binding"]["evidence_ceiling"]
    fingerprint = identity["binding"]["checkpoint_public_fingerprint"]
    assert fingerprint.startswith("sha256:")
    assert len(fingerprint) == len("sha256:") + 16

    blob = json.dumps(result)
    for needle in ("/home/", "127.0.0.1", "localhost", ":8000", "manifest_sha256"):
        assert needle not in blob
    assert str(tmp_path) not in blob
    # No full 64-hex private digests leak.
    assert not re.search(r"[0-9a-f]{64}", blob)
    assert validate_result_dir(exported) == []
