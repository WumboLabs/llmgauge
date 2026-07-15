"""Deterministic tests for the externally managed vLLM adapter."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

import pytest

from llmgauge.core.artifacts import write_json, write_text
from llmgauge.core.public_export import export_public_run
from llmgauge.core.reports import build_markdown_report
from llmgauge.core.result_validation import validate_result_data, validate_result_dir
from llmgauge.runners.vllm_external import (
    VllmExternalConfig,
    build_vllm_metrics,
    check_readiness_and_model,
    format_failure_log,
    run_chat_completion,
)


class _VllmHandler(BaseHTTPRequestHandler):
    state: dict[str, Any] = {}

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        return

    def do_GET(self) -> None:  # noqa: N802
        if self.path.endswith("/models") or self.path == "/v1/models":
            mode = self.state.get("models_mode", "ok")
            if mode == "mismatch":
                body = json.dumps(
                    {"object": "list", "data": [{"id": "other-model", "object": "model"}]}
                ).encode()
            elif mode == "error":
                self.send_response(503)
                self.end_headers()
                self.wfile.write(b"unavailable")
                return
            elif mode == "malformed":
                body = b'{"data":"nope"}'
            else:
                model = self.state.get("model_id", "test-model")
                body = json.dumps(
                    {"object": "list", "data": [{"id": model, "object": "model"}]}
                ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b""
        self.state["last_request_body"] = raw
        mode = self.state.get("chat_mode", "ok")

        if mode == "server_error":
            body = b'{"error":{"message":"fail"}}'
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if mode == "malformed_openai":
            body = b'{"choices":[]}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if mode == "bad_json":
            body = b"{not json"
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if mode == "model_mismatch":
            body = json.dumps(
                {
                    "id": "chatcmpl-1",
                    "model": "wrong-model",
                    "choices": [
                        {
                            "index": 0,
                            "message": {"role": "assistant", "content": "hi"},
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
                }
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if mode == "incomplete_usage":
            body = json.dumps(
                {
                    "id": "chatcmpl-1",
                    "model": self.state.get("model_id", "test-model"),
                    "choices": [
                        {
                            "index": 0,
                            "message": {"role": "assistant", "content": "partial"},
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {"prompt_tokens": 3},
                }
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        model = self.state.get("model_id", "test-model")
        body = json.dumps(
            {
                "id": "chatcmpl-1",
                "object": "chat.completion",
                "model": model,
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "hello from vllm"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 4,
                    "total_tokens": 14,
                },
            }
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture
def vllm_server():
    server = HTTPServer(("127.0.0.1", 0), _VllmHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    _VllmHandler.state = {"model_id": "test-model", "models_mode": "ok", "chat_mode": "ok"}
    yield f"http://127.0.0.1:{port}", _VllmHandler.state
    server.shutdown()
    server.server_close()


def _config(url: str, **kwargs: Any) -> VllmExternalConfig:
    return VllmExternalConfig(
        endpoint_url=url,
        served_model=kwargs.get("served_model", "test-model"),
        max_tokens=kwargs.get("max_tokens", 32),
        temperature=0.2,
        top_p=0.95,
        connect_timeout=kwargs.get("connect_timeout", 2.0),
        request_timeout=kwargs.get("request_timeout", 5.0),
        max_response_bytes=kwargs.get("max_response_bytes", 100_000),
    )


def test_successful_readiness_check(vllm_server) -> None:
    url, _state = vllm_server
    result = check_readiness_and_model(_config(url))
    assert result.success is True
    assert result.observed_model == "test-model"
    assert "test-model" in result.served_models
    assert result.endpoint_identity["scheme"] == "http"
    assert "url" not in result.endpoint_identity


def test_served_model_mismatch(vllm_server) -> None:
    url, state = vllm_server
    state["models_mode"] = "mismatch"
    result = check_readiness_and_model(_config(url))
    assert result.success is False
    assert result.failure_class == "served_model_mismatch"


def test_successful_chat_completion(vllm_server) -> None:
    url, state = vllm_server
    result = run_chat_completion(
        _config(url),
        prompt="Say hello",
        system_prompt="You are careful.",
    )
    assert result.success is True
    assert result.generated_text == "hello from vllm"
    assert result.finish_reason == "stop"
    assert result.prompt_tokens == 10
    assert result.completion_tokens == 4
    assert result.usage_complete is True
    assert result.request_wall_time_seconds is not None
    assert result.request_wall_time_seconds > 0
    assert result.end_to_end_completion_tps is not None
    assert result.end_to_end_completion_tps > 0
    body = json.loads(state["last_request_body"].decode())
    assert body["stream"] is False
    assert body["model"] == "test-model"
    assert body["messages"] == [
        {"role": "system", "content": "You are careful."},
        {"role": "user", "content": "Say hello"},
    ]
    assert result.request_evidence["system_text"] == "You are careful."
    assert result.request_evidence["user_text"] == "Say hello"
    assert result.request_evidence["request_messages"] == body["messages"]
    assert result.request_evidence["input_form"] == "chat_messages"


def test_chat_completion_ordered_roles_without_claiming_combined_parity(
    vllm_server,
) -> None:
    url, state = vllm_server
    system = "SYSTEM RULES"
    user = "USER TASK"
    result = run_chat_completion(
        _config(url),
        prompt=user,
        system_prompt=system,
    )
    assert result.success is True
    body = json.loads(state["last_request_body"].decode())
    assert [m["role"] for m in body["messages"]] == ["system", "user"]
    assert body["messages"][0]["content"] == system
    assert body["messages"][1]["content"] == user
    # Combined human-readable form must not be substituted as the user message.
    combined = f"SYSTEM:\n\n{system}\n\nUSER:\n\n{user}"
    assert body["messages"][1]["content"] != combined
    assert "combined_prompt_artifact_note" in result.request_evidence


def test_malformed_json_response(vllm_server) -> None:
    url, state = vllm_server
    state["chat_mode"] = "bad_json"
    result = run_chat_completion(_config(url), prompt="x")
    assert result.success is False
    assert result.failure_class == "malformed_response"
    assert result.failure_detail == "response_not_json"


def test_malformed_openai_response(vllm_server) -> None:
    url, state = vllm_server
    state["chat_mode"] = "malformed_openai"
    result = run_chat_completion(_config(url), prompt="x")
    assert result.success is False
    assert result.failure_class == "malformed_response"
    assert result.failure_detail == "choices_missing"


def test_server_error_response(vllm_server) -> None:
    url, state = vllm_server
    state["chat_mode"] = "server_error"
    result = run_chat_completion(_config(url), prompt="x")
    assert result.success is False
    assert result.failure_class == "server_request_error"
    assert result.http_status == 500


def test_response_model_mismatch(vllm_server) -> None:
    url, state = vllm_server
    state["chat_mode"] = "model_mismatch"
    result = run_chat_completion(_config(url), prompt="x")
    assert result.success is False
    assert result.failure_class == "served_model_mismatch"


def test_incomplete_usage_metadata(vllm_server) -> None:
    url, state = vllm_server
    state["chat_mode"] = "incomplete_usage"
    result = run_chat_completion(_config(url), prompt="x")
    assert result.success is True
    assert result.incomplete_usage is True
    assert result.failure_class == "incomplete_usage_metadata"
    assert result.generated_text == "partial"
    assert result.usage_complete is False
    metrics = build_vllm_metrics(result)
    assert metrics["generation_tps"] is None
    assert metrics["prompt_eval_tokens"] == 3
    assert metrics["generation_tokens"] is None


def test_sanitized_failure_log_has_no_raw_url(vllm_server) -> None:
    url, state = vllm_server
    state["models_mode"] = "error"
    result = check_readiness_and_model(_config(url))
    log = format_failure_log(result)
    assert "http://" not in log
    assert "127.0.0.1" not in log
    assert "failure_class=" in log


def test_vllm_result_validation_and_report(tmp_path: Path) -> None:
    result_dir = tmp_path / "vllm-result"
    (result_dir / "raw").mkdir(parents=True)
    (result_dir / "logs").mkdir(parents=True)
    (result_dir / "request").mkdir(parents=True)

    write_text(result_dir / "raw/p1.prompt.md", "prompt")
    write_text(result_dir / "raw/p1.output.txt", "output")
    write_text(result_dir / "logs/p1.stderr.log", "ok")
    write_json(
        result_dir / "request/p1.json",
        {
            "schema_version": "llmgauge.vllm_request_evidence.v0",
            "lifecycle_ownership": "external_operator",
            "endpoint_identity": {
                "scheme": "http",
                "loopback_class": "ipv4_loopback",
                "port": 8000,
            },
            "finish_reason": "stop",
            "request_wall_time_seconds": 0.5,
        },
    )
    write_json(
        result_dir / "vllm-runtime-evidence.json",
        {
            "schema_version": "llmgauge.vllm_runtime_evidence.v0",
            "lifecycle_ownership": "external_operator",
            "endpoint_identity": {
                "scheme": "http",
                "loopback_class": "ipv4_loopback",
                "port": 8000,
                "proxy_bypass_policy": "stdlib_http_client_no_env_proxy",
            },
            "requested_served_model": "test-model",
            "observed_served_model": "test-model",
        },
    )

    data = {
        "schema_version": "llmgauge.result.v0",
        "llmgauge_version": "0.70.0",
        "run": {"run_id": "vllm-result", "status": "completed", "timestamp_utc": "t"},
        "model": {
            "model_id": "test-model",
            "model_path": "redacted",
            "model_path_policy": "redacted",
            "served_model": "test-model",
        },
        "runtime": {
            "backend": "vllm",
            "lifecycle_ownership": "external_operator",
            "endpoint_identity": {
                "scheme": "http",
                "loopback_class": "ipv4_loopback",
                "port": 8000,
            },
            "requested_served_model": "test-model",
            "observed_served_model": "test-model",
            "ctx_size": 8192,
            "max_tokens": 32,
            "temperature": 0.2,
            "top_p": 0.95,
            "runtime_command_captured": False,
            "vllm_runtime_evidence_captured": True,
            "vllm_runtime_evidence_path": "vllm-runtime-evidence.json",
            "proxy_bypass_policy": "stdlib_http_client_no_env_proxy",
        },
        "suite": {"suite_id": "core-v1", "suite_version": "1", "prompt_count": 1},
        "summary": {"completed": 1, "failed": 0},
        "results": [
            {
                "prompt_id": "p1",
                "category": "test",
                "status": "completed",
                "raw_prompt_path": "raw/p1.prompt.md",
                "raw_output_path": "raw/p1.output.txt",
                "stderr_log_path": "logs/p1.stderr.log",
                "request_evidence_path": "request/p1.json",
                "exit_status": 0,
                "finish_reason": "stop",
                "metrics": {
                    "prompt_eval_tokens": 10,
                    "generation_tokens": 4,
                    "prompt_eval_tps": None,
                    "generation_tps": None,
                    "request_wall_time_seconds": 0.5,
                    "end_to_end_completion_tps": 8.0,
                    "finish_reason": "stop",
                },
            }
        ],
    }
    write_json(result_dir / "llmgauge-result.json", data)

    assert validate_result_dir(result_dir) == []
    report = build_markdown_report(data)
    assert "Backend: vllm" in report
    assert "Endpoint identity:" in report
    assert "Requested served model: test-model" in report
    assert "End-to-end completion" in report or "E2E completion" in report
    assert "not claimed equivalent" in report

    public_dir = tmp_path / "public"
    source_before = (result_dir / "llmgauge-result.json").read_text(encoding="utf-8")
    export_public_run(result_dir, public_dir)
    source_after = (result_dir / "llmgauge-result.json").read_text(encoding="utf-8")
    assert source_before == source_after
    public_result = json.loads(
        (public_dir / "llmgauge-result.json").read_text(encoding="utf-8")
    )
    identity = public_result["runtime"]["endpoint_identity"]
    assert set(identity.keys()) <= {
        "scheme",
        "loopback_class",
        "port",
        "proxy_bypass_policy",
    }
    assert "url" not in identity


def test_legacy_llama_result_still_valid(tmp_path: Path) -> None:
    result_dir = tmp_path / "legacy"
    (result_dir / "raw").mkdir(parents=True)
    (result_dir / "logs").mkdir(parents=True)
    write_text(result_dir / "raw/p.prompt.md", "p")
    write_text(result_dir / "raw/p.output.txt", "o")
    write_text(result_dir / "logs/p.stderr.log", "e")
    data = {
        "schema_version": "llmgauge.result.v0",
        "llmgauge_version": "0.1.0",
        "run": {"run_id": "legacy", "status": "completed"},
        "model": {
            "model_id": "m",
            "model_path": "redacted",
            "model_path_policy": "redacted",
        },
        "runtime": {"backend": "llama.cpp"},
        "suite": {"suite_id": "core-v1", "prompt_count": 1},
        "summary": {"completed": 1, "failed": 0},
        "results": [
            {
                "prompt_id": "p",
                "category": "c",
                "status": "completed",
                "raw_prompt_path": "raw/p.prompt.md",
                "raw_output_path": "raw/p.output.txt",
                "stderr_log_path": "logs/p.stderr.log",
                "exit_status": 0,
                "metrics": {},
            }
        ],
    }
    write_json(result_dir / "llmgauge-result.json", data)
    assert validate_result_data(result_dir, data) == []
