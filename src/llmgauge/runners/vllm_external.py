"""Externally managed vLLM OpenAI-compatible client (first production slice).

Does not start, stop, supervise, or recover the server. Operator owns lifecycle.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

from llmgauge.runners.vllm_http import (
    PROXY_BYPASS_POLICY,
    VllmTransportError,
    decode_json_object,
    http_request,
    sanitize_endpoint_identity,
    validate_vllm_endpoint,
)

VLLM_RUNTIME_EVIDENCE_SCHEMA = "llmgauge.vllm_runtime_evidence.v0"
VLLM_REQUEST_EVIDENCE_SCHEMA = "llmgauge.vllm_request_evidence.v0"
VLLM_RUNTIME_EVIDENCE_FILENAME = "vllm-runtime-evidence.json"

DEFAULT_CONNECT_TIMEOUT = 5.0
DEFAULT_REQUEST_TIMEOUT = 120.0
DEFAULT_MAX_RESPONSE_BYTES = 2_000_000

FAILURE_CLASSES = frozenset(
    {
        "endpoint_unavailable",
        "readiness_failure",
        "served_model_mismatch",
        "request_timeout",
        "malformed_response",
        "server_request_error",
        "request_execution_failure",
        "incomplete_usage_metadata",
        "unsupported_capability",
        "operator_cancellation",
        "model_admission_load_failure",
    }
)


@dataclass(frozen=True)
class VllmExternalConfig:
    endpoint_url: str
    served_model: str
    max_tokens: int
    temperature: float
    top_p: float
    connect_timeout: float = DEFAULT_CONNECT_TIMEOUT
    request_timeout: float = DEFAULT_REQUEST_TIMEOUT
    max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES
    # Requested context is recorded for evidence only; not sent as a vLLM field
    # unless a later contract admits it.
    ctx_size: int | None = None


@dataclass
class VllmRequestResult:
    success: bool
    generated_text: str = ""
    finish_reason: str | None = None
    backend_finish_reason: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    usage_complete: bool = False
    request_wall_time_seconds: float | None = None
    end_to_end_completion_tps: float | None = None
    failure_class: str | None = None
    failure_detail: str | None = None
    http_status: int | None = None
    observed_model: str | None = None
    endpoint_identity: dict[str, Any] = field(default_factory=dict)
    request_evidence: dict[str, Any] = field(default_factory=dict)
    incomplete_usage: bool = False


@dataclass
class VllmReadinessResult:
    success: bool
    endpoint_identity: dict[str, Any]
    served_models: list[str] = field(default_factory=list)
    observed_model: str | None = None
    failure_class: str | None = None
    failure_detail: str | None = None
    http_status: int | None = None
    wall_time_seconds: float | None = None
    evidence: dict[str, Any] = field(default_factory=dict)


def build_endpoint_identity(url: str) -> dict[str, Any]:
    endpoint = validate_vllm_endpoint(url)
    return sanitize_endpoint_identity(endpoint)


def _error_result(
    *,
    failure_class: str,
    detail: str,
    endpoint_identity: dict[str, Any] | None = None,
    http_status: int | None = None,
    wall_time: float | None = None,
    observed_model: str | None = None,
) -> VllmRequestResult:
    return VllmRequestResult(
        success=False,
        failure_class=failure_class,
        failure_detail=detail,
        http_status=http_status,
        request_wall_time_seconds=wall_time,
        endpoint_identity=endpoint_identity or {},
        observed_model=observed_model,
        request_evidence={
            "schema_version": VLLM_REQUEST_EVIDENCE_SCHEMA,
            "lifecycle_ownership": "external_operator",
            "streaming": False,
            "failure_class": failure_class,
            "failure_detail": detail,
            "http_status": http_status,
            "endpoint_identity": endpoint_identity or {},
            "request_wall_time_seconds": wall_time,
        },
    )


def _map_transport_error(
    exc: VllmTransportError,
    *,
    wall_time: float | None = None,
    readiness: bool = False,
) -> VllmRequestResult | VllmReadinessResult:
    failure_class = exc.failure_class
    if readiness and failure_class in {
        "endpoint_unavailable",
        "request_timeout",
        "malformed_response",
        "server_request_error",
    }:
        # Readiness-specific class when the check itself cannot establish ready API.
        if failure_class == "endpoint_unavailable":
            mapped = failure_class
        elif failure_class == "request_timeout":
            mapped = "readiness_failure"
        else:
            mapped = "readiness_failure"
    else:
        mapped = failure_class

    if readiness:
        return VllmReadinessResult(
            success=False,
            endpoint_identity=exc.endpoint_identity or {},
            failure_class=mapped,
            failure_detail=exc.detail,
            http_status=exc.http_status,
            wall_time_seconds=wall_time,
            evidence={
                "schema_version": VLLM_RUNTIME_EVIDENCE_SCHEMA,
                "lifecycle_ownership": "external_operator",
                "proxy_bypass_policy": PROXY_BYPASS_POLICY,
                "failure_class": mapped,
                "failure_detail": exc.detail,
                "http_status": exc.http_status,
                "endpoint_identity": exc.endpoint_identity or {},
            },
        )

    return _error_result(
        failure_class=mapped,
        detail=exc.detail,
        endpoint_identity=exc.endpoint_identity,
        http_status=exc.http_status,
        wall_time=wall_time,
    )


def _server_error_class(status: int) -> str:
    if status >= 500:
        return "server_request_error"
    if status >= 400:
        return "server_request_error"
    return "malformed_response"


def check_readiness_and_model(
    config: VllmExternalConfig,
) -> VllmReadinessResult:
    """Bounded readiness + served-model discovery/validation (not an eval request)."""
    started = time.monotonic()
    try:
        endpoint = validate_vllm_endpoint(config.endpoint_url)
    except VllmTransportError as exc:
        return _map_transport_error(exc, wall_time=time.monotonic() - started, readiness=True)  # type: ignore[return-value]

    identity = sanitize_endpoint_identity(endpoint)
    base_path = endpoint.path.rstrip("/")
    # OpenAI-compatible models listing under /v1/models (or endpoint base + /v1/models).
    if base_path in {"", "/"}:
        models_path = "/v1/models"
    elif base_path.endswith("/v1"):
        models_path = f"{base_path}/models"
    else:
        models_path = f"{base_path}/v1/models"

    try:
        response = http_request(
            endpoint,
            method="GET",
            path=models_path,
            body=None,
            connect_timeout=config.connect_timeout,
            request_timeout=min(config.request_timeout, config.connect_timeout + 30.0),
            max_response_bytes=config.max_response_bytes,
        )
    except VllmTransportError as exc:
        if not exc.endpoint_identity:
            exc.endpoint_identity = identity
        return _map_transport_error(  # type: ignore[return-value]
            exc,
            wall_time=time.monotonic() - started,
            readiness=True,
        )
    except KeyboardInterrupt:
        return VllmReadinessResult(
            success=False,
            endpoint_identity=identity,
            failure_class="operator_cancellation",
            failure_detail="keyboard_interrupt",
            wall_time_seconds=time.monotonic() - started,
        )

    wall = time.monotonic() - started
    if response.status != 200:
        return VllmReadinessResult(
            success=False,
            endpoint_identity=response.endpoint_identity or identity,
            failure_class="readiness_failure",
            failure_detail=f"models_http_{response.status}",
            http_status=response.status,
            wall_time_seconds=wall,
            evidence={
                "schema_version": VLLM_RUNTIME_EVIDENCE_SCHEMA,
                "lifecycle_ownership": "external_operator",
                "proxy_bypass_policy": PROXY_BYPASS_POLICY,
                "failure_class": "readiness_failure",
                "failure_detail": f"models_http_{response.status}",
                "http_status": response.status,
                "endpoint_identity": response.endpoint_identity or identity,
            },
        )

    try:
        payload = decode_json_object(response.body)
    except VllmTransportError as exc:
        return VllmReadinessResult(
            success=False,
            endpoint_identity=response.endpoint_identity or identity,
            failure_class="readiness_failure",
            failure_detail=exc.detail,
            http_status=response.status,
            wall_time_seconds=wall,
        )

    data = payload.get("data")
    if not isinstance(data, list):
        return VllmReadinessResult(
            success=False,
            endpoint_identity=response.endpoint_identity or identity,
            failure_class="readiness_failure",
            failure_detail="models_list_missing",
            http_status=response.status,
            wall_time_seconds=wall,
        )

    served: list[str] = []
    for item in data:
        if isinstance(item, dict) and isinstance(item.get("id"), str):
            served.append(item["id"])

    requested = config.served_model
    if requested not in served:
        return VllmReadinessResult(
            success=False,
            endpoint_identity=response.endpoint_identity or identity,
            served_models=served,
            failure_class="served_model_mismatch",
            failure_detail="requested_model_not_listed",
            http_status=response.status,
            wall_time_seconds=wall,
            evidence={
                "schema_version": VLLM_RUNTIME_EVIDENCE_SCHEMA,
                "lifecycle_ownership": "external_operator",
                "proxy_bypass_policy": PROXY_BYPASS_POLICY,
                "requested_served_model": requested,
                "observed_served_models": served,
                "failure_class": "served_model_mismatch",
                "failure_detail": "requested_model_not_listed",
                "endpoint_identity": response.endpoint_identity or identity,
            },
        )

    return VllmReadinessResult(
        success=True,
        endpoint_identity=response.endpoint_identity or identity,
        served_models=served,
        observed_model=requested,
        wall_time_seconds=wall,
        evidence={
            "schema_version": VLLM_RUNTIME_EVIDENCE_SCHEMA,
            "lifecycle_ownership": "external_operator",
            "proxy_bypass_policy": PROXY_BYPASS_POLICY,
            "requested_served_model": requested,
            "observed_served_models": served,
            "observed_served_model": requested,
            "readiness_status": "ready",
            "endpoint_identity": response.endpoint_identity or identity,
            "vllm_version": "unknown",
            "server_state": "unknown",
        },
    )


def _extract_chat_text(payload: dict[str, Any]) -> tuple[str, str | None, str | None]:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise VllmTransportError("malformed_response", "choices_missing")
    first = choices[0]
    if not isinstance(first, dict):
        raise VllmTransportError("malformed_response", "choice_not_object")

    backend_finish = first.get("finish_reason")
    finish_reason = backend_finish if isinstance(backend_finish, str) else None

    message = first.get("message")
    if isinstance(message, dict):
        content = message.get("content")
        if isinstance(content, str):
            return content, finish_reason, finish_reason
        if content is None:
            return "", finish_reason, finish_reason
        raise VllmTransportError("malformed_response", "message_content_not_string")

    text = first.get("text")
    if isinstance(text, str):
        return text, finish_reason, finish_reason

    raise VllmTransportError("malformed_response", "message_missing")


def _extract_usage(
    payload: dict[str, Any],
) -> tuple[int | None, int | None, bool]:
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        return None, None, False

    prompt_tokens = usage.get("prompt_tokens")
    completion_tokens = usage.get("completion_tokens")
    prompt_ok = isinstance(prompt_tokens, int) and not isinstance(prompt_tokens, bool)
    completion_ok = isinstance(completion_tokens, int) and not isinstance(
        completion_tokens, bool
    )
    if prompt_ok and completion_ok:
        return int(prompt_tokens), int(completion_tokens), True
    return (
        int(prompt_tokens) if prompt_ok else None,
        int(completion_tokens) if completion_ok else None,
        False,
    )


def run_chat_completion(
    config: VllmExternalConfig,
    *,
    prompt: str,
    system_prompt: str | None = None,
) -> VllmRequestResult:
    """One non-streaming text chat-completions request with wall-time measurement."""
    if not isinstance(prompt, str) or not prompt:
        return _error_result(
            failure_class="unsupported_capability",
            detail="empty_prompt",
        )

    started = time.monotonic()
    try:
        endpoint = validate_vllm_endpoint(config.endpoint_url)
    except VllmTransportError as exc:
        return _map_transport_error(exc, wall_time=time.monotonic() - started)  # type: ignore[return-value]

    identity = sanitize_endpoint_identity(endpoint)
    base_path = endpoint.path.rstrip("/")
    if base_path in {"", "/"}:
        chat_path = "/v1/chat/completions"
    elif base_path.endswith("/v1"):
        chat_path = f"{base_path}/chat/completions"
    else:
        chat_path = f"{base_path}/v1/chat/completions"

    messages: list[dict[str, str]] = []
    if isinstance(system_prompt, str) and system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    request_body = {
        "model": config.served_model,
        "messages": messages,
        "max_tokens": int(config.max_tokens),
        "temperature": float(config.temperature),
        "top_p": float(config.top_p),
        "stream": False,
    }
    body_bytes = json.dumps(request_body, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )

    # Wall time: immediately before request transmission through complete response validation.
    transmit_start = time.monotonic()
    try:
        response = http_request(
            endpoint,
            method="POST",
            path=chat_path,
            body=body_bytes,
            connect_timeout=config.connect_timeout,
            request_timeout=config.request_timeout,
            max_response_bytes=config.max_response_bytes,
        )
    except VllmTransportError as exc:
        if not exc.endpoint_identity:
            exc.endpoint_identity = identity
        return _map_transport_error(  # type: ignore[return-value]
            exc,
            wall_time=time.monotonic() - transmit_start,
        )
    except KeyboardInterrupt:
        return _error_result(
            failure_class="operator_cancellation",
            detail="keyboard_interrupt",
            endpoint_identity=identity,
            wall_time=time.monotonic() - transmit_start,
        )

    wall = time.monotonic() - transmit_start
    identity = response.endpoint_identity or identity

    if response.status >= 400:
        # Do not copy full error bodies into evidence.
        return _error_result(
            failure_class=_server_error_class(response.status),
            detail=f"http_{response.status}",
            endpoint_identity=identity,
            http_status=response.status,
            wall_time=wall,
        )

    if response.status != 200:
        return _error_result(
            failure_class="malformed_response",
            detail=f"unexpected_http_{response.status}",
            endpoint_identity=identity,
            http_status=response.status,
            wall_time=wall,
        )

    try:
        payload = decode_json_object(response.body)
        text, finish_reason, backend_finish = _extract_chat_text(payload)
        prompt_tokens, completion_tokens, usage_complete = _extract_usage(payload)
    except VllmTransportError as exc:
        return _error_result(
            failure_class=exc.failure_class,
            detail=exc.detail,
            endpoint_identity=identity,
            http_status=response.status,
            wall_time=wall,
        )

    observed_model = payload.get("model")
    if not isinstance(observed_model, str):
        observed_model = None
    if observed_model is not None and observed_model != config.served_model:
        return _error_result(
            failure_class="served_model_mismatch",
            detail="response_model_mismatch",
            endpoint_identity=identity,
            http_status=response.status,
            wall_time=wall,
            observed_model=observed_model,
        )

    e2e_tps: float | None = None
    if (
        completion_tokens is not None
        and wall > 0
        and completion_tokens >= 0
    ):
        e2e_tps = float(completion_tokens) / wall

    incomplete_usage = not usage_complete
    system_text = (
        system_prompt if isinstance(system_prompt, str) and system_prompt else None
    )
    evidence = {
        "schema_version": VLLM_REQUEST_EVIDENCE_SCHEMA,
        "lifecycle_ownership": "external_operator",
        "streaming": False,
        "input_form": "chat_messages",
        "system_text": system_text,
        "user_text": prompt,
        "request_messages": list(messages),
        "combined_prompt_artifact_note": (
            "raw/*.prompt.md is a human-readable SYSTEM/USER combined form for "
            "compatibility; it is not claimed identical to request_messages"
        ),
        "requested_served_model": config.served_model,
        "observed_served_model": observed_model or config.served_model,
        "endpoint_identity": identity,
        "http_status": response.status,
        "finish_reason": finish_reason,
        "backend_finish_reason": backend_finish,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "usage_complete": usage_complete,
        "token_count_source": "backend_usage" if usage_complete else "backend_usage_partial",
        "request_wall_time_seconds": wall,
        "end_to_end_completion_tps": e2e_tps,
        "connect_seconds": response.connect_seconds,
        "proxy_bypass_policy": PROXY_BYPASS_POLICY,
        "max_tokens_field": "max_tokens",
        "incomplete_usage_metadata": incomplete_usage,
    }

    return VllmRequestResult(
        success=True,
        generated_text=text,
        finish_reason=finish_reason,
        backend_finish_reason=backend_finish,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        usage_complete=usage_complete,
        request_wall_time_seconds=wall,
        end_to_end_completion_tps=e2e_tps,
        observed_model=observed_model or config.served_model,
        endpoint_identity=identity,
        request_evidence=evidence,
        incomplete_usage=incomplete_usage,
        failure_class="incomplete_usage_metadata" if incomplete_usage else None,
        failure_detail="usage_fields_incomplete" if incomplete_usage else None,
    )


def build_vllm_metrics(result: VllmRequestResult) -> dict[str, Any]:
    """Additive metrics map; does not claim llama.cpp decode-equivalent throughput."""
    return {
        "prompt_eval_tokens": result.prompt_tokens,
        "prompt_eval_tps": None,
        "generation_tokens": result.completion_tokens,
        # Intentionally null: e2e throughput is not decode-only generation_tps.
        "generation_tps": None,
        "peak_vram_mib": None,
        "vram_headroom_mib": None,
        "request_wall_time_seconds": result.request_wall_time_seconds,
        "end_to_end_completion_tps": result.end_to_end_completion_tps,
        "prompt_tokens_source": (
            "backend_usage" if result.prompt_tokens is not None else "unknown"
        ),
        "completion_tokens_source": (
            "backend_usage" if result.completion_tokens is not None else "unknown"
        ),
        "finish_reason": result.finish_reason,
        "backend_finish_reason": result.backend_finish_reason,
        "usage_complete": result.usage_complete,
    }


def build_runtime_evidence_document(
    *,
    config: VllmExternalConfig,
    readiness: VllmReadinessResult,
    endpoint_identity: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": VLLM_RUNTIME_EVIDENCE_SCHEMA,
        "lifecycle_ownership": "external_operator",
        "backend": "vllm",
        "proxy_bypass_policy": PROXY_BYPASS_POLICY,
        "endpoint_identity": endpoint_identity,
        "requested_served_model": config.served_model,
        "observed_served_model": readiness.observed_model,
        "observed_served_models": readiness.served_models,
        "readiness_status": "ready" if readiness.success else "failed",
        "readiness_failure_class": readiness.failure_class,
        "readiness_failure_detail": readiness.failure_detail,
        "readiness_wall_time_seconds": readiness.wall_time_seconds,
        "connect_timeout_seconds": config.connect_timeout,
        "request_timeout_seconds": config.request_timeout,
        "max_response_bytes": config.max_response_bytes,
        "vllm_version": "unknown",
        "server_state": "unknown",
        "streaming": False,
        "authentication": "none",
    }


def format_failure_log(result: VllmRequestResult | VllmReadinessResult) -> str:
    """Sanitized transport/error log text (no raw URLs, headers, or bodies)."""
    lines = [
        "llmgauge vllm external adapter",
        f"failure_class={getattr(result, 'failure_class', None) or 'none'}",
        f"failure_detail={getattr(result, 'failure_detail', None) or 'none'}",
        f"http_status={getattr(result, 'http_status', None)}",
    ]
    identity = getattr(result, "endpoint_identity", {}) or {}
    if identity:
        lines.append(
            "endpoint_identity="
            f"scheme={identity.get('scheme')},"
            f"loopback_class={identity.get('loopback_class')},"
            f"port={identity.get('port')}"
        )
    return "\n".join(lines) + "\n"
