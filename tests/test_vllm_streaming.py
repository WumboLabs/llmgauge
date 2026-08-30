"""Synthetic loopback SSE tests for vLLM streaming TTFT evidence.

Uses a local HTTPServer only; no real vLLM, no model, no network.
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

import pytest

from llmgauge.runners.vllm_external import (
    DEFAULT_MAX_RESPONSE_BYTES,
    VLLM_STREAM_EVIDENCE_SCHEMA,
    VllmExternalConfig,
    run_chat_completion,
    run_chat_completion_stream,
    streaming_ttft_version_admitted,
)
from llmgauge.runners.vllm_http import (
    StreamEvent,
    VllmTransportError,
    http_request_stream,
    validate_vllm_endpoint,
)


@dataclass
class SseScenario:
    """Scripted chat-completions behavior for one request."""

    events: list[dict[str, Any]] = field(default_factory=list)
    chat_mode: str = "ok"
    http_status: int = 200
    vllm_version: str = "0.27.1"
    model_id: str = "test-model"
    last_request_body: bytes = b""


def chunk(
    *,
    content: str | None = None,
    reasoning: str | None = None,
    token_ids: list[int] | None = None,
    finish_reason: str | None = None,
    role: str | None = None,
    index: int = 0,
    model: str = "test-model",
) -> dict[str, Any]:
    """Build one vLLM-style ChatCompletionStreamResponse event."""
    delta: dict[str, Any] = {}
    if role is not None:
        delta["role"] = role
    if content is not None:
        delta["content"] = content
    if reasoning is not None:
        delta["reasoning"] = reasoning
    choice: dict[str, Any] = {
        "index": index,
        "delta": delta,
        "finish_reason": finish_reason,
    }
    if token_ids is not None:
        choice["token_ids"] = token_ids
    return {
        "type": "chunk",
        "payload": {
            "id": "chatcmpl-stream-1",
            "object": "chat.completion.chunk",
            "created": 1720000000,
            "model": model,
            "choices": [choice],
        },
    }


def done() -> dict[str, Any]:
    return {"type": "done"}


def finish(reason: str = "stop") -> dict[str, Any]:
    """vLLM terminal chunk carrying finish_reason (no content)."""
    return chunk(finish_reason=reason)


def usage_chunk(
    *,
    prompt_tokens: int,
    completion_tokens: int,
    model: str = "test-model",
) -> dict[str, Any]:
    return {
        "type": "usage",
        "payload": {
            "id": "chatcmpl-stream-1",
            "object": "chat.completion.chunk",
            "created": 1720000000,
            "model": model,
            "choices": [],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
        },
    }


def error_object(message: str = "stream error") -> dict[str, Any]:
    return {
        "type": "error",
        "payload": {"error": {"type": "server_error", "message": message}},
    }


class _SseHandler(BaseHTTPRequestHandler):
    scenario: SseScenario = SseScenario()

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        return

    def _send_status(self, status: int, content_type: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        scenario = self.scenario
        if path == "/version" or path.endswith("/version"):
            body = json.dumps({"version": scenario.vllm_version}).encode()
            self._send_status(200, "application/json", body)
            return
        if path.endswith("/models") or path == "/v1/models":
            body = json.dumps(
                {
                    "object": "list",
                    "data": [{"id": scenario.model_id, "object": "model"}],
                }
            ).encode()
            self._send_status(200, "application/json", body)
            return
        self._send_status(404, "application/json", b"{}")

    def do_POST(self) -> None:  # noqa: N802
        scenario = self.scenario
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b""
        scenario.last_request_body = raw
        try:
            request = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            request = {}
        stream_flag = request.get("stream") is True

        if scenario.chat_mode == "http_error":
            self._send_status(
                scenario.http_status, "application/json", b'{"error":"fail"}'
            )
            return
        if scenario.chat_mode == "redirect":
            self.send_response(302)
            self.send_header("Location", "/elsewhere")
            self.end_headers()
            return

        if not stream_flag:
            # Non-streaming JSON response path (regression fixture).
            payload = {
                "id": "chatcmpl-1",
                "object": "chat.completion",
                "model": scenario.model_id,
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": "hello from vllm",
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 4,
                    "total_tokens": 14,
                },
            }
            self._send_status(200, "application/json", json.dumps(payload).encode())
            return

        # Streaming SSE path.
        self.send_response(scenario.http_status)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()
        try:
            for event in scenario.events:
                if event.get("delay"):
                    time.sleep(event["delay"])
                kind = event.get("type")
                if kind == "done":
                    self.wfile.write(b"data: [DONE]\n\n")
                elif kind == "error":
                    payload = json.dumps(event["payload"]).encode()
                    self.wfile.write(b"data: " + payload + b"\n\n")
                elif kind == "malformed":
                    self.wfile.write(b"data: {not json\n\n")
                elif kind == "chunk" or kind == "usage":
                    payload = json.dumps(event["payload"]).encode()
                    self.wfile.write(b"data: " + payload + b"\n\n")
                elif kind == "raw":
                    self.wfile.write(event["payload"])
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass


@pytest.fixture
def sse_server():
    handler = _SseHandler
    handler.scenario = SseScenario()
    server = HTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    try:
        yield f"http://127.0.0.1:{port}", handler.scenario
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _config(url: str, **kwargs: Any) -> VllmExternalConfig:
    return VllmExternalConfig(
        endpoint_url=url,
        served_model="test-model",
        max_tokens=16,
        temperature=0.2,
        top_p=0.95,
        streaming_evidence=True,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# Version qualification
# ---------------------------------------------------------------------------


def test_version_qualification_exact_0_27_1() -> None:
    """Admitted: exactly 0.27.1."""
    assert streaming_ttft_version_admitted("0.27.1") == (
        True,
        "observed_version_exact_0.27.1",
    )


def test_version_qualification_rejects_parseable_not_qualified() -> None:
    """Well-formed X.Y.Z that is not 0.27.1."""
    for v in ("0.27.0", "0.27.2", "0.15.1", "0.14.0", "0.28.0", "1.0.0", "99.0.0"):
        admitted, rule = streaming_ttft_version_admitted(v)
        assert admitted is False, f"{v} should not be admitted"
        assert rule == "observed_version_not_qualified", (
            f"{v}: expected not_qualified, got {rule}"
        )


def test_version_qualification_rejects_unparseable() -> None:
    """Strings that are not canonical X.Y.Z."""
    for v in (
        "unknown",
        "0.27.1rc1",
        "0.27.1.dev0",
        "0.27.1+local",
        "0.27.1.post1",
        "garbage",
    ):
        admitted, rule = streaming_ttft_version_admitted(v)
        assert admitted is False, f"{v} should not be admitted"
        assert rule == "observed_version_unparseable", (
            f"{v}: expected unparseable, got {rule}"
        )


def test_version_qualification_rejects_unavailable() -> None:
    """Empty or invalid strings."""
    for v in ("", "x" * 65, "\x00"):
        admitted, rule = streaming_ttft_version_admitted(v)
        assert admitted is False, f"{v!r} should not be admitted"
        assert rule == "observed_version_unavailable", (
            f"{v!r}: expected unavailable, got {rule}"
        )


def test_stream_evidence_records_exact_qualified_version(sse_server) -> None:
    url, scenario = sse_server
    scenario.events = [
        chunk(role="assistant", content=""),
        chunk(content="Hello", token_ids=[101]),
        usage_chunk(prompt_tokens=5, completion_tokens=1),
        finish(),
        done(),
    ]
    result = run_chat_completion_stream(
        _config(url), prompt="x", vllm_version="0.27.1"
    )
    assert result.success is True
    assert result.stream_evidence is not None
    qual = result.stream_evidence["version_qualification"]
    assert qual["admitted"] is True
    assert qual["rule"] == "observed_version_exact_0.27.1"
    assert qual["observed_vllm_version"] == "0.27.1"


def test_stream_evidence_records_unqualified_version(sse_server) -> None:
    url, scenario = sse_server
    scenario.events = [
        chunk(role="assistant", content=""),
        chunk(content="Hello", token_ids=[101]),
        usage_chunk(prompt_tokens=5, completion_tokens=1),
        finish(),
        done(),
    ]
    result = run_chat_completion_stream(
        _config(url), prompt="x", vllm_version="0.27.2"
    )
    assert result.success is True
    assert result.stream_evidence is not None
    qual = result.stream_evidence["version_qualification"]
    assert qual["admitted"] is False
    assert qual["rule"] == "observed_version_not_qualified"
    assert qual["observed_vllm_version"] == "0.27.2"


# ---------------------------------------------------------------------------
# Transport-level SSE reading
# ---------------------------------------------------------------------------


def test_http_request_stream_yields_events_in_order(sse_server) -> None:
    url, scenario = sse_server
    scenario.events = [
        chunk(role="assistant", content=""),
        chunk(content="Hello", token_ids=[101]),
        chunk(content=" world", token_ids=[102]),
        usage_chunk(prompt_tokens=5, completion_tokens=2),
        done(),
    ]
    endpoint = validate_vllm_endpoint(url)
    events: list[StreamEvent] = list(
        http_request_stream(
            endpoint,
            method="POST",
            path="/v1/chat/completions",
            body=b'{"stream":true}',
            connect_timeout=5.0,
            request_timeout=10.0,
            max_response_bytes=DEFAULT_MAX_RESPONSE_BYTES,
            max_event_bytes=1_000_000,
            max_event_count=1_000_000,
        )
    )
    assert [e.index for e in events] == [0, 1, 2, 3, 4]
    assert events[0].is_done is False
    assert events[0].data == json.dumps(chunk(role="assistant", content="")["payload"])
    assert events[-1].is_done is True
    assert events[-1].data == "[DONE]"
    stamps = [e.monotonic_seconds for e in events]
    assert all(b >= a for a, b in zip(stamps, stamps[1:]))


def test_http_request_stream_oversize_event_rejected(sse_server) -> None:
    url, scenario = sse_server
    scenario.events = [
        {"type": "raw", "payload": b"data: " + b"x" * 2000 + b"\n\n"},
        finish(),
        done(),
    ]
    endpoint = validate_vllm_endpoint(url)
    with pytest.raises(VllmTransportError) as exc:
        list(
            http_request_stream(
                endpoint,
                method="POST",
                path="/v1/chat/completions",
                body=b'{"stream":true}',
                connect_timeout=5.0,
                request_timeout=10.0,
                max_response_bytes=DEFAULT_MAX_RESPONSE_BYTES,
                max_event_bytes=100,
                max_event_count=1_000_000,
            )
        )
    assert exc.value.failure_class == "malformed_response"
    # The single over-long data line trips the per-line bound first.
    assert exc.value.detail == "stream_line_exceeds_limit"


def test_http_request_stream_http_error(sse_server) -> None:
    url, scenario = sse_server
    scenario.chat_mode = "http_error"
    scenario.http_status = 500
    endpoint = validate_vllm_endpoint(url)
    with pytest.raises(VllmTransportError) as exc:
        list(
            http_request_stream(
                endpoint,
                method="POST",
                path="/v1/chat/completions",
                body=b'{"stream":true}',
                connect_timeout=5.0,
                request_timeout=10.0,
                max_response_bytes=DEFAULT_MAX_RESPONSE_BYTES,
                max_event_bytes=1_000_000,
                max_event_count=1_000_000,
            )
        )
    assert exc.value.failure_class == "server_request_error"
    assert exc.value.http_status == 500


def test_http_request_stream_redirect_disallowed(sse_server) -> None:
    url, scenario = sse_server
    scenario.chat_mode = "redirect"
    endpoint = validate_vllm_endpoint(url)
    with pytest.raises(VllmTransportError) as exc:
        list(
            http_request_stream(
                endpoint,
                method="POST",
                path="/v1/chat/completions",
                body=b'{"stream":true}',
                connect_timeout=5.0,
                request_timeout=10.0,
                max_response_bytes=DEFAULT_MAX_RESPONSE_BYTES,
                max_event_bytes=1_000_000,
                max_event_count=1_000_000,
            )
        )
    assert exc.value.detail == "redirect_disallowed"


# ---------------------------------------------------------------------------
# Streaming completion scenarios (Area 4 TTFT contract)
# ---------------------------------------------------------------------------


def test_stream_role_first_no_ttft_trigger(sse_server) -> None:
    url, scenario = sse_server
    scenario.events = [
        chunk(role="assistant", content=""),
        chunk(content="Hello", token_ids=[101]),
        usage_chunk(prompt_tokens=5, completion_tokens=1),
        finish(),
        done(),
    ]
    result = run_chat_completion_stream(_config(url), prompt="x")
    assert result.success is True
    assert result.generated_text == "Hello"
    assert result.streaming is True
    assert result.transport_mode == "openai_compatible_sse"
    assert result.time_to_first_token_seconds is not None
    assert result.first_token_channel == "content"
    stream_ev = result.stream_evidence
    assert stream_ev["schema_version"] == VLLM_STREAM_EVIDENCE_SCHEMA
    assert stream_ev["first_token"]["event_index"] == 1
    assert stream_ev["first_token"]["channel"] == "content"
    assert stream_ev["events"][0]["ttft_trigger"] is False
    assert stream_ev["events"][1]["ttft_trigger"] is True
    assert stream_ev["terminal"]["state"] == "done_received"
    assert stream_ev["terminal"]["done_received"] is True
    assert stream_ev["terminal"]["usage_present"] is True


def test_stream_reasoning_token_counts_for_ttft(sse_server) -> None:
    url, scenario = sse_server
    scenario.events = [
        chunk(role="assistant", content=""),
        chunk(reasoning="Let me think", token_ids=[200]),
        chunk(content="42", token_ids=[201]),
        usage_chunk(prompt_tokens=5, completion_tokens=2),
        finish(),
        done(),
    ]
    result = run_chat_completion_stream(_config(url), prompt="x")
    assert result.success is True
    assert result.time_to_first_token_seconds is not None
    assert result.first_token_channel == "reasoning"
    # Canonical generated text is final content only, never reasoning text.
    assert result.generated_text == "42"
    stream_ev = result.stream_evidence
    assert stream_ev["first_token"]["event_index"] == 1
    assert stream_ev["first_token"]["channel"] == "reasoning"


def test_stream_empty_decoded_token_counts_when_token_id_proves(sse_server) -> None:
    url, scenario = sse_server
    scenario.events = [
        chunk(role="assistant", content=""),
        chunk(content="", token_ids=[202]),
        chunk(content="done", token_ids=[203]),
        usage_chunk(prompt_tokens=5, completion_tokens=2),
        finish(),
        done(),
    ]
    result = run_chat_completion_stream(_config(url), prompt="x")
    assert result.success is True
    assert result.time_to_first_token_seconds is not None
    assert result.first_token_channel == "other_generated"
    assert result.generated_text == "done"


def test_stream_coalesced_tokens_one_chunk_timestamp(sse_server) -> None:
    url, scenario = sse_server
    scenario.events = [
        chunk(role="assistant", content=""),
        chunk(content="abc", token_ids=[301, 302, 303]),
        usage_chunk(prompt_tokens=5, completion_tokens=3),
        finish(),
        done(),
    ]
    result = run_chat_completion_stream(_config(url), prompt="x")
    assert result.success is True
    assert result.time_to_first_token_seconds is not None
    assert result.first_token_channel == "content"
    stream_ev = result.stream_evidence
    assert stream_ev["first_token"]["token_ids_in_event"] == 3
    assert stream_ev["events"][1]["token_ids_count"] == 3


def test_stream_content_without_token_ids_does_not_trigger_ttft(sse_server) -> None:
    url, scenario = sse_server
    scenario.events = [
        chunk(role="assistant", content=""),
        chunk(content="visible"),
        chunk(content="more", token_ids=[501]),
        usage_chunk(prompt_tokens=5, completion_tokens=2),
        finish(),
        done(),
    ]
    result = run_chat_completion_stream(_config(url), prompt="x")
    assert result.success is True
    assert result.time_to_first_token_seconds is not None
    # The content-only chunk without token IDs is not the TTFT boundary.
    stream_ev = result.stream_evidence
    assert stream_ev["first_token"]["event_index"] == 2
    assert stream_ev["events"][1]["ttft_trigger"] is False


def test_stream_multiple_token_events_first_wins(sse_server) -> None:
    url, scenario = sse_server
    scenario.events = [
        chunk(role="assistant", content=""),
        chunk(content="a", token_ids=[10]),
        chunk(content="b", token_ids=[11]),
        usage_chunk(prompt_tokens=5, completion_tokens=2),
        finish(),
        done(),
    ]
    result = run_chat_completion_stream(_config(url), prompt="x")
    assert result.success is True
    assert result.time_to_first_token_seconds is not None
    assert result.first_token_channel == "content"
    stream_ev = result.stream_evidence
    assert stream_ev["first_token"]["event_index"] == 1


def test_stream_done_without_token_ttft_unavailable(sse_server) -> None:
    url, scenario = sse_server
    scenario.events = [
        chunk(role="assistant", content=""),
        usage_chunk(prompt_tokens=5, completion_tokens=0),
        finish(),
        done(),
    ]
    result = run_chat_completion_stream(_config(url), prompt="x")
    assert result.success is True
    assert result.time_to_first_token_seconds is None
    assert result.first_token_channel is None
    stream_ev = result.stream_evidence
    assert stream_ev["first_token"] is None
    assert stream_ev["terminal"]["state"] == "done_received"


def test_stream_usage_final_extracted(sse_server) -> None:
    url, scenario = sse_server
    scenario.events = [
        chunk(role="assistant", content=""),
        chunk(content="hi", token_ids=[5]),
        usage_chunk(prompt_tokens=12, completion_tokens=1),
        finish(),
        done(),
    ]
    result = run_chat_completion_stream(_config(url), prompt="x")
    assert result.success is True
    assert result.prompt_tokens == 12
    assert result.completion_tokens == 1
    assert result.usage_complete is True
    assert result.request_evidence["token_count_source"] == "backend_usage"


def test_stream_missing_usage_incomplete_semantics(sse_server) -> None:
    url, scenario = sse_server
    scenario.events = [
        chunk(role="assistant", content=""),
        chunk(content="hi", token_ids=[5]),
        finish(),
        done(),
    ]
    result = run_chat_completion_stream(_config(url), prompt="x")
    assert result.success is True
    assert result.incomplete_usage is True
    assert result.failure_class == "incomplete_usage_metadata"
    assert result.prompt_tokens is None
    assert result.completion_tokens is None


def test_stream_malformed_json_before_token(sse_server) -> None:
    url, scenario = sse_server
    scenario.events = [
        chunk(role="assistant", content=""),
        {"type": "malformed"},
        finish(),
        done(),
    ]
    result = run_chat_completion_stream(_config(url), prompt="x")
    assert result.success is False
    assert result.failure_class == "malformed_response"
    assert result.failure_detail == "stream_json_decode_error"
    assert result.time_to_first_token_seconds is None
    stream_ev = result.stream_evidence
    assert stream_ev["terminal"]["state"] == "malformed"


def test_stream_malformed_json_after_token_retains_ttft(sse_server) -> None:
    url, scenario = sse_server
    scenario.events = [
        chunk(role="assistant", content=""),
        chunk(content="hi", token_ids=[5]),
        {"type": "malformed"},
        finish(),
        done(),
    ]
    result = run_chat_completion_stream(_config(url), prompt="x")
    assert result.success is False
    assert result.failure_class == "malformed_response"
    assert result.time_to_first_token_seconds is not None
    assert result.first_token_channel == "content"
    stream_ev = result.stream_evidence
    assert stream_ev["terminal"]["state"] == "malformed"
    assert stream_ev["first_token"] is not None


def test_stream_malformed_token_ids_fail_closed(sse_server) -> None:
    url, scenario = sse_server
    scenario.events = [
        chunk(role="assistant", content=""),
        chunk(content="bad", token_ids=["not-an-int"]),
        finish(),
        done(),
    ]
    result = run_chat_completion_stream(_config(url), prompt="x")
    assert result.success is False
    assert result.failure_class == "malformed_response"
    assert result.failure_detail == "malformed_token_ids"
    assert result.time_to_first_token_seconds is None


def test_stream_embedded_error_object_before_token(sse_server) -> None:
    url, scenario = sse_server
    scenario.events = [
        chunk(role="assistant", content=""),
        error_object("boom"),
        finish(),
        done(),
    ]
    result = run_chat_completion_stream(_config(url), prompt="x")
    assert result.success is False
    assert result.failure_class == "server_request_error"
    assert result.time_to_first_token_seconds is None
    stream_ev = result.stream_evidence
    assert stream_ev["terminal"]["state"] == "server_error"
    assert stream_ev["terminal"]["server_error"] is True


def test_stream_embedded_error_after_token_retains_ttft(sse_server) -> None:
    url, scenario = sse_server
    scenario.events = [
        chunk(role="assistant", content=""),
        chunk(content="partial", token_ids=[7]),
        error_object("boom"),
        finish(),
        done(),
    ]
    result = run_chat_completion_stream(_config(url), prompt="x")
    assert result.success is False
    assert result.time_to_first_token_seconds is not None
    stream_ev = result.stream_evidence
    assert stream_ev["first_token"] is not None
    assert stream_ev["terminal"]["state"] == "server_error"


def test_stream_premature_eof_before_token(sse_server) -> None:
    url, scenario = sse_server
    scenario.events = [
        chunk(role="assistant", content=""),
        # EOF without [DONE].
    ]
    result = run_chat_completion_stream(_config(url), prompt="x")
    assert result.success is False
    assert result.time_to_first_token_seconds is None
    assert result.stream_evidence["terminal"]["state"] == "premature_eof"


def test_stream_premature_eof_after_token(sse_server) -> None:
    url, scenario = sse_server
    scenario.events = [
        chunk(role="assistant", content=""),
        chunk(content="partial", token_ids=[7]),
        # EOF without [DONE].
    ]
    result = run_chat_completion_stream(_config(url), prompt="x")
    assert result.success is False
    assert result.time_to_first_token_seconds is not None
    assert result.stream_evidence["terminal"]["state"] == "premature_eof"


def test_stream_http_error_ttft_unavailable(sse_server) -> None:
    url, scenario = sse_server
    scenario.chat_mode = "http_error"
    scenario.http_status = 400
    result = run_chat_completion_stream(_config(url), prompt="x")
    assert result.success is False
    assert result.failure_class == "server_request_error"
    assert result.http_status == 400
    assert result.time_to_first_token_seconds is None
    assert result.stream_evidence is None


def test_stream_served_model_mismatch_fail_closed(sse_server) -> None:
    url, scenario = sse_server
    scenario.events = [
        chunk(role="assistant", content="", model="test-model"),
        chunk(content="hi", token_ids=[5], model="other-model"),
        finish(),
        done(),
    ]
    result = run_chat_completion_stream(_config(url), prompt="x")
    assert result.success is False
    assert result.failure_class == "malformed_response"
    assert result.failure_detail == "served_model_contradiction"


def test_stream_system_fingerprint_captured(sse_server) -> None:
    url, scenario = sse_server
    scenario.events = [
        chunk(role="assistant", content="", model="test-model"),
        chunk(content="hi", token_ids=[5], model="test-model"),
        {
            "type": "usage",
            "payload": {
                "id": "chatcmpl-stream-1",
                "object": "chat.completion.chunk",
                "created": 1720000000,
                "model": "test-model",
                "choices": [],
                "usage": {"prompt_tokens": 5, "completion_tokens": 1},
                "system_fingerprint": "fp-stream-1",
            },
        },
        finish(),
        done(),
    ]
    result = run_chat_completion_stream(_config(url), prompt="x")
    assert result.success is True
    assert result.system_fingerprint == "fp-stream-1"
    assert result.system_fingerprint_status == "present"


def test_stream_request_body_contains_required_fields(sse_server) -> None:
    url, scenario = sse_server
    scenario.events = [chunk(role="assistant", content=""), done()]
    run_chat_completion_stream(_config(url), prompt="x")
    request = json.loads(scenario.last_request_body.decode("utf-8"))
    assert request["stream"] is True
    assert request["return_token_ids"] is True
    assert request["stream_options"] == {"include_usage": True}
    assert request["model"] == "test-model"


def test_stream_empty_prompt_unsupported(sse_server) -> None:
    url, _scenario = sse_server
    result = run_chat_completion_stream(_config(url), prompt="")
    assert result.success is False
    assert result.failure_class == "unsupported_capability"
    assert result.failure_detail == "empty_prompt"
    assert result.request_evidence["request_transmitted"] is False


def test_stream_request_evidence_identity(sse_server) -> None:
    url, scenario = sse_server
    scenario.events = [
        chunk(role="assistant", content=""),
        chunk(content="hi", token_ids=[5]),
        usage_chunk(prompt_tokens=5, completion_tokens=1),
        finish(),
        done(),
    ]
    result = run_chat_completion_stream(_config(url), prompt="x")
    assert result.request_evidence["streaming"] is True
    assert result.request_evidence["transport_mode"] == "openai_compatible_sse"
    assert result.request_evidence["return_token_ids"] is True
    assert result.request_evidence["stream_options"] == {"include_usage": True}
    assert result.request_evidence["time_to_first_token_seconds"] is not None
    assert result.request_evidence["first_token_channel"] == "content"


# ---------------------------------------------------------------------------
# Output assembly
# ---------------------------------------------------------------------------


def test_output_assembly_many_chunks_exact(sse_server) -> None:
    url, scenario = sse_server
    chunks_text = ["The", " quick", " brown", " fox", " jumps"]
    scenario.events = [chunk(role="assistant", content="")]
    for i, text in enumerate(chunks_text):
        scenario.events.append(chunk(content=text, token_ids=[100 + i]))
    scenario.events.extend(
        [
            finish(),
            usage_chunk(prompt_tokens=5, completion_tokens=len(chunks_text)),
            done(),
        ]
    )
    result = run_chat_completion_stream(_config(url), prompt="x")
    assert result.success is True
    assert result.generated_text == "The quick brown fox jumps"
    assert "\n" not in result.generated_text


def test_output_assembly_utf8(sse_server) -> None:
    url, scenario = sse_server
    scenario.events = [
        chunk(role="assistant", content=""),
        chunk(content="Héllo", token_ids=[1]),
        chunk(content=" wörld ✓", token_ids=[2]),
        usage_chunk(prompt_tokens=5, completion_tokens=2),
        finish(),
        done(),
    ]
    result = run_chat_completion_stream(_config(url), prompt="x")
    assert result.success is True
    assert result.generated_text == "Héllo wörld ✓"


def test_output_assembly_reasoning_separated(sse_server) -> None:
    url, scenario = sse_server
    scenario.events = [
        chunk(role="assistant", content=""),
        chunk(reasoning="step", token_ids=[10]),
        chunk(reasoning=" step", token_ids=[11]),
        chunk(content="final", token_ids=[12]),
        usage_chunk(prompt_tokens=5, completion_tokens=3),
        finish(),
        done(),
    ]
    result = run_chat_completion_stream(_config(url), prompt="x")
    assert result.success is True
    # Canonical generated output excludes reasoning deltas.
    assert result.generated_text == "final"


def test_output_assembly_finish_chunk_no_content(sse_server) -> None:
    url, scenario = sse_server
    scenario.events = [
        chunk(role="assistant", content=""),
        chunk(content="done", token_ids=[5]),
        chunk(finish_reason="stop"),
        usage_chunk(prompt_tokens=5, completion_tokens=1),
        finish(),
        done(),
    ]
    result = run_chat_completion_stream(_config(url), prompt="x")
    assert result.success is True
    assert result.generated_text == "done"
    assert result.finish_reason == "stop"


# ---------------------------------------------------------------------------
# Non-streaming regression
# ---------------------------------------------------------------------------


def test_non_streaming_default_unaffected(sse_server) -> None:
    url, scenario = sse_server
    config = VllmExternalConfig(
        endpoint_url=url,
        served_model="test-model",
        max_tokens=16,
        temperature=0.2,
        top_p=0.95,
        streaming_evidence=False,
    )
    result = run_chat_completion(config, prompt="x")
    assert result.success is True
    assert result.generated_text == "hello from vllm"
    assert result.streaming is False
    assert result.time_to_first_token_seconds is None
    assert result.stream_evidence is None
    assert result.request_evidence["streaming"] is False
    request = json.loads(scenario.last_request_body.decode("utf-8"))
    assert request["stream"] is False
    assert "return_token_ids" not in request


def test_non_streaming_produces_no_stream_artifact(sse_server) -> None:
    url, _scenario = sse_server
    config = VllmExternalConfig(
        endpoint_url=url,
        served_model="test-model",
        max_tokens=16,
        temperature=0.2,
        top_p=0.95,
        streaming_evidence=False,
    )
    result = run_chat_completion(config, prompt="x")
    assert result.stream_evidence is None
    assert result.request_evidence.get("stream_evidence_path") is None
