"""Deterministic local tests for the stdlib vLLM HTTP transport."""

from __future__ import annotations

import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

import pytest

from llmgauge.runners.vllm_http import (
    VllmTransportError,
    http_request,
    resolve_loopback_addresses,
    validate_vllm_endpoint,
)


class _Handler(BaseHTTPRequestHandler):
    behavior: dict[str, Any] = {}

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        return

    def do_GET(self) -> None:  # noqa: N802
        self._handle()

    def do_POST(self) -> None:  # noqa: N802
        self._handle()

    def _handle(self) -> None:
        mode = self.behavior.get("mode", "ok")
        if mode == "redirect":
            self.send_response(302)
            self.send_header("Location", "http://127.0.0.1:9/elsewhere")
            self.end_headers()
            self.wfile.write(b"redirect")
            return
        if mode == "huge":
            body = b"x" * int(self.behavior.get("size", 1000))
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if mode == "slow":
            import time

            time.sleep(float(self.behavior.get("sleep", 2.0)))
            body = b'{"ok":true}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if mode == "server_error":
            body = b'{"error":"boom"}'
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if mode == "bad_json":
            body = b"not-json"
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        body = self.behavior.get("body", b'{"ok":true}')
        if isinstance(body, str):
            body = body.encode("utf-8")
        status = int(self.behavior.get("status", 200))
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        # Echo Host for assertions via trailing path store.
        self.behavior["last_host"] = self.headers.get("Host")
        self.behavior["last_path"] = self.path
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture
def loopback_server():
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    _Handler.behavior = {"mode": "ok", "body": b'{"ok":true}'}
    yield f"http://127.0.0.1:{port}", port, _Handler.behavior
    server.shutdown()
    server.server_close()


def test_validate_ipv4_loopback_literal() -> None:
    endpoint = validate_vllm_endpoint("http://127.0.0.1:8000/v1")
    assert endpoint.host == "127.0.0.1"
    assert endpoint.port == 8000
    assert endpoint.path == "/v1"
    assert endpoint.identity["scheme"] == "http"
    assert endpoint.identity["loopback_class"] == "ipv4_loopback"
    assert endpoint.identity["port"] == 8000
    assert "url" not in endpoint.identity


def test_validate_ipv6_loopback_literal() -> None:
    endpoint = validate_vllm_endpoint("http://[::1]:8000")
    assert endpoint.host == "::1"
    assert endpoint.port == 8000
    assert endpoint.identity["loopback_class"] == "ipv6_loopback"
    assert endpoint.host_header in {"[::1]:8000", "::1:8000"} or endpoint.host_header.startswith(
        "["
    )


def test_reject_non_loopback_literal() -> None:
    with pytest.raises(VllmTransportError) as exc:
        validate_vllm_endpoint("http://8.8.8.8:8000")
    assert exc.value.failure_class == "endpoint_unavailable"
    assert exc.value.detail == "non_loopback_literal"


def test_reject_userinfo_query_fragment_scheme() -> None:
    with pytest.raises(VllmTransportError) as exc:
        validate_vllm_endpoint("http://user:pass@127.0.0.1:8000")
    assert exc.value.detail == "userinfo_disallowed"

    with pytest.raises(VllmTransportError) as exc:
        validate_vllm_endpoint("http://127.0.0.1:8000?x=1")
    assert exc.value.detail == "query_disallowed"

    with pytest.raises(VllmTransportError) as exc:
        validate_vllm_endpoint("http://127.0.0.1:8000#frag")
    assert exc.value.detail == "fragment_disallowed"

    with pytest.raises(VllmTransportError) as exc:
        validate_vllm_endpoint("https://127.0.0.1:8000")
    assert exc.value.failure_class == "unsupported_capability"
    assert exc.value.detail == "scheme_not_http"


def test_mixed_resolution_rejection(monkeypatch) -> None:
    endpoint = validate_vllm_endpoint("http://localhost:8000")

    def fake_getaddrinfo(host, port, *args, **kwargs):
        return [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", port)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", port)),
        ]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)
    with pytest.raises(VllmTransportError) as exc:
        resolve_loopback_addresses(endpoint)
    assert exc.value.detail == "mixed_loopback_non_loopback_resolution"


def test_non_loopback_resolution_rejection(monkeypatch) -> None:
    endpoint = validate_vllm_endpoint("http://localhost:8000")

    def fake_getaddrinfo(host, port, *args, **kwargs):
        return [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("1.2.3.4", port)),
        ]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)
    with pytest.raises(VllmTransportError) as exc:
        resolve_loopback_addresses(endpoint)
    assert exc.value.detail == "non_loopback_resolution"


def test_proxy_env_does_not_affect_routing(loopback_server, monkeypatch) -> None:
    url, port, behavior = loopback_server
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:1")
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:1")
    monkeypatch.setenv("ALL_PROXY", "http://127.0.0.1:1")
    monkeypatch.setenv("NO_PROXY", "")

    endpoint = validate_vllm_endpoint(url)
    response = http_request(
        endpoint,
        method="GET",
        path="/",
        connect_timeout=2.0,
        request_timeout=5.0,
        max_response_bytes=10_000,
    )
    assert response.status == 200
    assert json.loads(response.body) == {"ok": True}
    assert behavior.get("last_host") in {f"127.0.0.1:{port}", "127.0.0.1"}


def test_redirect_not_followed(loopback_server) -> None:
    url, _port, behavior = loopback_server
    behavior["mode"] = "redirect"
    endpoint = validate_vllm_endpoint(url)
    with pytest.raises(VllmTransportError) as exc:
        http_request(
            endpoint,
            method="GET",
            path="/",
            connect_timeout=2.0,
            request_timeout=5.0,
            max_response_bytes=10_000,
        )
    assert exc.value.failure_class == "malformed_response"
    assert exc.value.detail == "redirect_disallowed"


def test_connect_timeout_classification() -> None:
    # Non-listening high port on loopback should refuse quickly; force short
    # connect budget against a black-hole style bind is hard without raw sockets.
    # Connection refused maps to endpoint_unavailable.
    endpoint = validate_vllm_endpoint("http://127.0.0.1:1")
    with pytest.raises(VllmTransportError) as exc:
        http_request(
            endpoint,
            method="GET",
            path="/",
            connect_timeout=0.5,
            request_timeout=1.0,
            max_response_bytes=1000,
        )
    assert exc.value.failure_class == "endpoint_unavailable"


def test_whole_request_timeout_classification(loopback_server) -> None:
    url, _port, behavior = loopback_server
    behavior["mode"] = "slow"
    behavior["sleep"] = 2.0
    endpoint = validate_vllm_endpoint(url)
    with pytest.raises(VllmTransportError) as exc:
        http_request(
            endpoint,
            method="GET",
            path="/",
            connect_timeout=0.5,
            request_timeout=0.3,
            max_response_bytes=10_000,
        )
    assert exc.value.failure_class in {"request_timeout", "endpoint_unavailable"}


def test_bounded_response_body(loopback_server) -> None:
    url, _port, behavior = loopback_server
    behavior["mode"] = "huge"
    behavior["size"] = 5000
    endpoint = validate_vllm_endpoint(url)
    with pytest.raises(VllmTransportError) as exc:
        http_request(
            endpoint,
            method="GET",
            path="/",
            connect_timeout=2.0,
            request_timeout=5.0,
            max_response_bytes=100,
        )
    assert exc.value.failure_class == "malformed_response"
    assert exc.value.detail == "response_body_exceeds_limit"


def test_successful_get_and_host_header(loopback_server) -> None:
    url, port, behavior = loopback_server
    endpoint = validate_vllm_endpoint(url)
    response = http_request(
        endpoint,
        method="GET",
        path="/health",
        connect_timeout=2.0,
        request_timeout=5.0,
        max_response_bytes=10_000,
    )
    assert response.status == 200
    assert behavior["last_path"] == "/health"
    assert "127.0.0.1" in (behavior.get("last_host") or "")
    assert str(port) in (behavior.get("last_host") or "") or port == 80
    assert response.endpoint_identity["scheme"] == "http"
    assert "url" not in response.endpoint_identity


def test_connection_cleanup_after_error(loopback_server) -> None:
    url, _port, behavior = loopback_server
    behavior["mode"] = "redirect"
    endpoint = validate_vllm_endpoint(url)
    with pytest.raises(VllmTransportError):
        http_request(
            endpoint,
            method="GET",
            path="/",
            connect_timeout=2.0,
            request_timeout=5.0,
            max_response_bytes=10_000,
        )
    # A second request should still succeed after cleanup.
    behavior["mode"] = "ok"
    behavior["body"] = b'{"ok":true}'
    response = http_request(
        endpoint,
        method="GET",
        path="/",
        connect_timeout=2.0,
        request_timeout=5.0,
        max_response_bytes=10_000,
    )
    assert response.status == 200


def test_ipv6_loopback_request_when_supported() -> None:
    try:
        server = HTTPServer(("::1", 0), _Handler)
    except OSError:
        pytest.skip("IPv6 loopback not available")
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    _Handler.behavior = {"mode": "ok", "body": b'{"ok":true}'}
    try:
        endpoint = validate_vllm_endpoint(f"http://[::1]:{port}")
        response = http_request(
            endpoint,
            method="GET",
            path="/",
            connect_timeout=2.0,
            request_timeout=5.0,
            max_response_bytes=10_000,
        )
        assert response.status == 200
        assert response.endpoint_identity["loopback_class"] == "ipv6_loopback"
    finally:
        server.shutdown()
        server.server_close()
