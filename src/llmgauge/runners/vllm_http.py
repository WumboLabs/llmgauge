"""Bounded loopback HTTP transport for the externally managed vLLM adapter.

Uses only Python standard-library networking admitted by
docs/VLLM_HTTP_TRANSPORT_ASSESSMENT.md. Never uses urllib.request proxy
openers, never follows redirects, and never retries evaluation requests.
"""

from __future__ import annotations

import http.client
import ipaddress
import json
import socket
import time
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

# Fixed minimal headers only; no arbitrary or credential-bearing headers.
_ACCEPT_JSON = "application/json"
_CONTENT_JSON = "application/json"
_ACCEPT_EVENT_STREAM = "text/event-stream"

PROXY_BYPASS_POLICY = "stdlib_http_client_no_env_proxy"


class VllmTransportError(Exception):
    """Transport or policy failure with a contract failure class."""

    def __init__(
        self,
        failure_class: str,
        detail: str,
        *,
        http_status: int | None = None,
        endpoint_identity: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(detail)
        self.failure_class = failure_class
        self.detail = detail
        self.http_status = http_status
        self.endpoint_identity = endpoint_identity or {}


@dataclass(frozen=True)
class ValidatedEndpoint:
    """Validated local HTTP endpoint (no credentials, query, or fragment)."""

    scheme: str
    host: str
    port: int
    path: str
    host_header: str
    identity: dict[str, Any]


@dataclass(frozen=True)
class HttpResponse:
    status: int
    reason: str
    body: bytes
    connect_seconds: float
    transfer_seconds: float
    total_seconds: float
    endpoint_identity: dict[str, Any]


@dataclass(frozen=True)
class StreamEvent:
    """One complete bounded SSE event with its monotonic receipt timestamp.

    `monotonic_seconds` is captured at event completion (terminating blank
    line, `[DONE]` marker, or EOF), so elapsed time is computable against any
    request-start monotonic origin chosen by the caller.
    """

    index: int
    monotonic_seconds: float
    data: str
    is_done: bool


def sanitize_endpoint_identity(endpoint: ValidatedEndpoint) -> dict[str, Any]:
    """Sanitized identity: scheme, loopback class, and port only."""
    return dict(endpoint.identity)


def _loopback_class_for_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> str:
    if isinstance(ip, ipaddress.IPv4Address):
        return "ipv4_loopback"
    return "ipv6_loopback"


def validate_vllm_endpoint(url: str) -> ValidatedEndpoint:
    """Parse and validate an HTTP loopback endpoint before any network I/O."""
    if not isinstance(url, str) or not url.strip():
        raise VllmTransportError(
            "malformed_response",
            "endpoint_empty",
        )

    parts = urlsplit(url.strip())
    if parts.scheme.lower() != "http":
        raise VllmTransportError(
            "unsupported_capability",
            "scheme_not_http",
        )
    if parts.username is not None or parts.password is not None:
        raise VllmTransportError(
            "malformed_response",
            "userinfo_disallowed",
        )
    if parts.query:
        raise VllmTransportError(
            "malformed_response",
            "query_disallowed",
        )
    if parts.fragment:
        raise VllmTransportError(
            "malformed_response",
            "fragment_disallowed",
        )
    if not parts.hostname:
        raise VllmTransportError(
            "malformed_response",
            "host_missing",
        )

    host = parts.hostname
    port = parts.port if parts.port is not None else 80
    path = parts.path if parts.path else "/"

    # Prefer literal IP classification when the host is already an address.
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None

    if literal is not None and not literal.is_loopback:
        raise VllmTransportError(
            "endpoint_unavailable",
            "non_loopback_literal",
            endpoint_identity={
                "scheme": "http",
                "loopback_class": "non_loopback",
                "port": port,
            },
        )

    if host.startswith("[") and host.endswith("]"):
        host_for_header = host
    else:
        try:
            ip_for_header = ipaddress.ip_address(host)
        except ValueError:
            host_for_header = host
        else:
            if isinstance(ip_for_header, ipaddress.IPv6Address):
                host_for_header = f"[{host}]"
            else:
                host_for_header = host

    if port != 80:
        host_header = f"{host_for_header}:{port}"
    else:
        host_header = host_for_header

    if literal is not None:
        loopback_class = _loopback_class_for_ip(literal)
    else:
        loopback_class = "hostname_loopback_pending_resolution"

    identity = {
        "scheme": "http",
        "loopback_class": loopback_class,
        "port": port,
        "proxy_bypass_policy": PROXY_BYPASS_POLICY,
    }

    return ValidatedEndpoint(
        scheme="http",
        host=host,
        port=port,
        path=path,
        host_header=host_header,
        identity=identity,
    )


def resolve_loopback_addresses(
    endpoint: ValidatedEndpoint,
) -> list[tuple[str, int, str]]:
    """Resolve hostname and require every address to be loopback.

    Returns a list of (connect_host, port, family_label) tuples. connect_host is
    an IP literal suitable for socket connection (IPv6 without brackets).
    """
    try:
        infos = socket.getaddrinfo(
            endpoint.host,
            endpoint.port,
            type=socket.SOCK_STREAM,
            proto=socket.IPPROTO_TCP,
        )
    except socket.gaierror as exc:
        raise VllmTransportError(
            "endpoint_unavailable",
            "dns_resolution_failed",
            endpoint_identity=sanitize_endpoint_identity(endpoint),
        ) from exc

    if not infos:
        raise VllmTransportError(
            "endpoint_unavailable",
            "dns_resolution_empty",
            endpoint_identity=sanitize_endpoint_identity(endpoint),
        )

    resolved: list[tuple[str, int, str]] = []
    seen: set[tuple[str, int]] = set()
    non_loopback_found = False

    for family, _socktype, _proto, _canonname, sockaddr in infos:
        if family == socket.AF_INET:
            ip_text = sockaddr[0]
            port = int(sockaddr[1])
        elif family == socket.AF_INET6:
            ip_text = sockaddr[0]
            port = int(sockaddr[1])
        else:
            continue

        try:
            ip_obj = ipaddress.ip_address(ip_text)
        except ValueError:
            non_loopback_found = True
            continue

        if not ip_obj.is_loopback:
            non_loopback_found = True
            continue

        key = (ip_text, port)
        if key in seen:
            continue
        seen.add(key)
        label = "ipv4" if family == socket.AF_INET else "ipv6"
        resolved.append((ip_text, port, label))

    if non_loopback_found and not resolved:
        raise VllmTransportError(
            "endpoint_unavailable",
            "non_loopback_resolution",
            endpoint_identity={
                "scheme": "http",
                "loopback_class": "non_loopback",
                "port": endpoint.port,
                "proxy_bypass_policy": PROXY_BYPASS_POLICY,
            },
        )

    if non_loopback_found and resolved:
        raise VllmTransportError(
            "endpoint_unavailable",
            "mixed_loopback_non_loopback_resolution",
            endpoint_identity={
                "scheme": "http",
                "loopback_class": "mixed",
                "port": endpoint.port,
                "proxy_bypass_policy": PROXY_BYPASS_POLICY,
            },
        )

    if not resolved:
        raise VllmTransportError(
            "endpoint_unavailable",
            "no_loopback_addresses",
            endpoint_identity=sanitize_endpoint_identity(endpoint),
        )

    return resolved


def _remaining_timeout(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise VllmTransportError("request_timeout", "whole_request_deadline_exceeded")
    return remaining


def _read_bounded_body(
    response: http.client.HTTPResponse,
    *,
    max_bytes: int,
    deadline: float,
) -> bytes:
    content_length = response.getheader("Content-Length")
    if content_length is not None:
        try:
            declared = int(content_length)
        except ValueError:
            declared = -1
        if declared > max_bytes:
            raise VllmTransportError(
                "malformed_response",
                "response_body_exceeds_limit",
            )

    chunks: list[bytes] = []
    total = 0
    # Chunked reads keep memory bounded and allow deadline checks.
    while True:
        _remaining_timeout(deadline)
        chunk = response.read(min(65536, max_bytes - total + 1))
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise VllmTransportError(
                "malformed_response",
                "response_body_exceeds_limit",
            )
        chunks.append(chunk)
    return b"".join(chunks)


def _read_bounded_line(
    response: http.client.HTTPResponse,
    *,
    max_line_bytes: int,
    deadline: float,
) -> bytes:
    """Read one SSE line under a byte bound and the whole-request deadline.

    Returns b"" at EOF. Over-long lines raise a malformed-response transport
    error instead of buffering an unbounded line.
    """
    parts: list[bytes] = []
    total = 0
    while True:
        _remaining_timeout(deadline)
        chunk = response.readline(65536)
        if not chunk:
            break
        total += len(chunk)
        parts.append(chunk)
        if total > max_line_bytes:
            raise VllmTransportError(
                "malformed_response",
                "stream_line_exceeds_limit",
            )
        if chunk.endswith(b"\n"):
            break
    return b"".join(parts)


def _classify_connect_error(exc: BaseException) -> VllmTransportError:
    if isinstance(exc, TimeoutError) or isinstance(exc, socket.timeout):
        return VllmTransportError("endpoint_unavailable", "connect_timeout")
    if isinstance(exc, ConnectionRefusedError):
        return VllmTransportError("endpoint_unavailable", "connection_refused")
    if isinstance(exc, ConnectionResetError):
        return VllmTransportError("endpoint_unavailable", "connection_reset")
    if isinstance(exc, BrokenPipeError):
        return VllmTransportError("endpoint_unavailable", "broken_pipe")
    if isinstance(exc, OSError):
        return VllmTransportError("endpoint_unavailable", "connect_os_error")
    return VllmTransportError("endpoint_unavailable", "connect_failed")


def _classify_transfer_error(exc: BaseException) -> VllmTransportError:
    if isinstance(exc, TimeoutError) or isinstance(exc, socket.timeout):
        return VllmTransportError("request_timeout", "transfer_timeout")
    if isinstance(exc, ConnectionResetError):
        return VllmTransportError("endpoint_unavailable", "connection_reset")
    if isinstance(exc, BrokenPipeError):
        return VllmTransportError("endpoint_unavailable", "broken_pipe")
    if isinstance(exc, OSError):
        return VllmTransportError("request_execution_failure", "transfer_os_error")
    return VllmTransportError("request_execution_failure", "transfer_failed")


def http_request(
    endpoint: ValidatedEndpoint,
    *,
    method: str,
    path: str,
    body: bytes | None = None,
    connect_timeout: float,
    request_timeout: float,
    max_response_bytes: int,
) -> HttpResponse:
    """Issue one non-streaming HTTP request to a validated loopback endpoint.

    Connects to a resolved loopback IP while sending the validated Host header.
    Does not follow redirects, does not retry, and does not consult proxy env.
    """
    if connect_timeout <= 0 or request_timeout <= 0:
        raise VllmTransportError("malformed_response", "timeout_not_positive")
    if max_response_bytes <= 0:
        raise VllmTransportError(
            "malformed_response", "max_response_bytes_not_positive"
        )

    method_upper = method.upper()
    if method_upper not in {"GET", "POST"}:
        raise VllmTransportError("unsupported_capability", "method_not_allowed")

    request_path = path if path.startswith("/") else f"/{path}"
    deadline = time.monotonic() + float(request_timeout)
    addresses = resolve_loopback_addresses(endpoint)

    # Prefer the first resolved loopback address; sequential single-request use.
    connect_host, connect_port, family_label = addresses[0]
    identity = {
        "scheme": "http",
        "loopback_class": (
            "ipv4_loopback" if family_label == "ipv4" else "ipv6_loopback"
        ),
        "port": endpoint.port,
        "proxy_bypass_policy": PROXY_BYPASS_POLICY,
    }

    conn: http.client.HTTPConnection | None = None
    sock: socket.socket | None = None
    started = time.monotonic()
    connect_seconds = 0.0

    try:
        try:
            connect_budget = min(float(connect_timeout), _remaining_timeout(deadline))
            sock = socket.create_connection(
                (connect_host, connect_port),
                timeout=connect_budget,
            )
            connect_seconds = time.monotonic() - started
        except VllmTransportError:
            raise
        except Exception as exc:  # noqa: BLE001 — mapped to failure class
            raise _classify_connect_error(exc) from exc

        remaining = _remaining_timeout(deadline)
        sock.settimeout(remaining)

        # HTTPConnection does not consult HTTP(S)_PROXY / ALL_PROXY / NO_PROXY.
        conn = http.client.HTTPConnection(connect_host, connect_port, timeout=remaining)
        conn.sock = sock

        headers = {
            "Host": endpoint.host_header,
            "Accept": _ACCEPT_JSON,
            "Connection": "close",
        }
        if body is not None:
            headers["Content-Type"] = _CONTENT_JSON
            headers["Content-Length"] = str(len(body))

        transfer_start = time.monotonic()
        try:
            conn.request(method_upper, request_path, body=body, headers=headers)
            response = conn.getresponse()
            status = int(response.status)
            reason = str(response.reason or "")

            if 300 <= status < 400:
                # Drain/close without following Location.
                try:
                    response.read(max_response_bytes + 1)
                except Exception:  # noqa: BLE001
                    pass
                raise VllmTransportError(
                    "malformed_response",
                    "redirect_disallowed",
                    http_status=status,
                    endpoint_identity=identity,
                )

            body_bytes = _read_bounded_body(
                response,
                max_bytes=max_response_bytes,
                deadline=deadline,
            )
        except VllmTransportError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise _classify_transfer_error(exc) from exc

        transfer_seconds = time.monotonic() - transfer_start
        total_seconds = time.monotonic() - started
        return HttpResponse(
            status=status,
            reason=reason,
            body=body_bytes,
            connect_seconds=connect_seconds,
            transfer_seconds=transfer_seconds,
            total_seconds=total_seconds,
            endpoint_identity=identity,
        )
    except KeyboardInterrupt as exc:
        raise VllmTransportError(
            "operator_cancellation",
            "keyboard_interrupt",
            endpoint_identity=identity,
        ) from exc
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:  # noqa: BLE001
                pass
        elif sock is not None:
            try:
                sock.close()
            except Exception:  # noqa: BLE001
                pass


def http_request_stream(
    endpoint: ValidatedEndpoint,
    *,
    method: str,
    path: str,
    body: bytes | None = None,
    connect_timeout: float,
    request_timeout: float,
    max_response_bytes: int,
    max_event_bytes: int,
    max_event_count: int,
) -> Iterator[StreamEvent]:
    """Issue one streaming HTTP request and yield bounded SSE events.

    Shares the loopback-only validation, proxy bypass, redirect refusal,
    fixed headers, and whole-request deadline of ``http_request``. Reads the
    response incrementally as SSE lines, enforcing per-line, per-event,
    total-body, and event-count bounds, and timestamps each complete event
    with the monotonic clock. Every terminal path closes the connection.
    """
    if connect_timeout <= 0 or request_timeout <= 0:
        raise VllmTransportError("malformed_response", "timeout_not_positive")
    if max_response_bytes <= 0:
        raise VllmTransportError(
            "malformed_response",
            "max_response_bytes_not_positive",
        )
    if max_event_bytes <= 0 or max_event_count <= 0:
        raise VllmTransportError("malformed_response", "stream_bounds_not_positive")

    method_upper = method.upper()
    if method_upper not in {"GET", "POST"}:
        raise VllmTransportError("unsupported_capability", "method_not_allowed")

    request_path = path if path.startswith("/") else f"/{path}"
    deadline = time.monotonic() + float(request_timeout)
    addresses = resolve_loopback_addresses(endpoint)

    # Prefer the first resolved loopback address; sequential single-request use.
    connect_host, connect_port, family_label = addresses[0]
    identity = {
        "scheme": "http",
        "loopback_class": (
            "ipv4_loopback" if family_label == "ipv4" else "ipv6_loopback"
        ),
        "port": endpoint.port,
        "proxy_bypass_policy": PROXY_BYPASS_POLICY,
    }

    conn: http.client.HTTPConnection | None = None
    sock: socket.socket | None = None

    try:
        try:
            connect_budget = min(float(connect_timeout), _remaining_timeout(deadline))
            sock = socket.create_connection(
                (connect_host, connect_port),
                timeout=connect_budget,
            )
        except VllmTransportError:
            raise
        except Exception as exc:  # noqa: BLE001 — mapped to failure class
            raise _classify_connect_error(exc) from exc

        remaining = _remaining_timeout(deadline)
        sock.settimeout(remaining)

        # HTTPConnection does not consult HTTP(S)_PROXY / ALL_PROXY / NO_PROXY.
        conn = http.client.HTTPConnection(connect_host, connect_port, timeout=remaining)
        conn.sock = sock

        headers = {
            "Host": endpoint.host_header,
            "Accept": _ACCEPT_EVENT_STREAM,
            "Connection": "close",
        }
        if body is not None:
            headers["Content-Type"] = _CONTENT_JSON
            headers["Content-Length"] = str(len(body))

        try:
            conn.request(method_upper, request_path, body=body, headers=headers)
            response = conn.getresponse()
            status = int(response.status)

            if 300 <= status < 400:
                # Drain/close without following Location.
                try:
                    response.read(max_response_bytes + 1)
                except Exception:  # noqa: BLE001
                    pass
                raise VllmTransportError(
                    "malformed_response",
                    "redirect_disallowed",
                    http_status=status,
                    endpoint_identity=identity,
                )
            if status >= 400:
                # Drain a bounded error body so the connection can close.
                try:
                    _read_bounded_body(
                        response,
                        max_bytes=max_response_bytes,
                        deadline=deadline,
                    )
                except VllmTransportError:
                    pass
                raise VllmTransportError(
                    "server_request_error",
                    f"http_{status}",
                    http_status=status,
                    endpoint_identity=identity,
                )
        except VllmTransportError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise _classify_transfer_error(exc) from exc

        total_bytes = 0
        event_count = 0
        try:
            while True:
                # The socket timeout is set once (like the non-streaming path);
                # each read still enforces the whole-request deadline, and a
                # stalled single read times out against the socket budget.
                # Re-arming here is unsafe: http.client may already have closed
                # the socket after a `Connection: close` response, and calling
                # settimeout on a closed descriptor raises OSError.
                _remaining_timeout(deadline)
                data_parts: list[str] = []
                event_bytes = 0
                saw_line = False
                while True:
                    _remaining_timeout(deadline)
                    line = _read_bounded_line(
                        response,
                        max_line_bytes=max_event_bytes,
                        deadline=deadline,
                    )
                    if not line:
                        break  # EOF
                    saw_line = True
                    event_bytes += len(line)
                    total_bytes += len(line)
                    if event_bytes > max_event_bytes:
                        raise VllmTransportError(
                            "malformed_response",
                            "stream_event_exceeds_limit",
                        )
                    if total_bytes > max_response_bytes:
                        raise VllmTransportError(
                            "malformed_response",
                            "stream_body_exceeds_limit",
                        )
                    if line in (b"\n", b"\r\n"):
                        break  # SSE event terminator
                    if line.startswith(b"data:"):
                        payload = line[len(b"data:") :].strip(b" \t\r\n")
                        try:
                            data_parts.append(payload.decode("utf-8"))
                        except UnicodeDecodeError as exc:
                            raise VllmTransportError(
                                "malformed_response",
                                "stream_not_utf8",
                            ) from exc
                    # Other SSE fields and comment lines are ignored.
                if not saw_line and not data_parts:
                    break  # clean EOF before any further event
                event_count += 1
                if event_count > max_event_count:
                    raise VllmTransportError(
                        "malformed_response",
                        "stream_event_count_exceeds_limit",
                    )
                data_text = "\n".join(data_parts)
                yield StreamEvent(
                    index=event_count - 1,
                    monotonic_seconds=time.monotonic(),
                    data=data_text,
                    is_done=data_text.strip() == "[DONE]",
                )
                if data_text.strip() == "[DONE]":
                    break
        except VllmTransportError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise _classify_transfer_error(exc) from exc
    except KeyboardInterrupt as exc:
        raise VllmTransportError(
            "operator_cancellation",
            "keyboard_interrupt",
            endpoint_identity=identity,
        ) from exc
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:  # noqa: BLE001
                pass
        elif sock is not None:
            try:
                sock.close()
            except Exception:  # noqa: BLE001
                pass


def decode_json_object(body: bytes) -> dict[str, Any]:
    """Decode a bounded JSON object body."""
    if not body:
        raise VllmTransportError("malformed_response", "empty_response_body")
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise VllmTransportError(
            "malformed_response",
            "response_not_utf8",
        ) from exc
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise VllmTransportError(
            "malformed_response",
            "response_not_json",
        ) from exc
    if not isinstance(data, dict):
        raise VllmTransportError(
            "malformed_response",
            "response_json_not_object",
        )
    return data
