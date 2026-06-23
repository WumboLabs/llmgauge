from __future__ import annotations

from typing import Any

FIT_LADDER_SCHEMA_VERSION = "llmgauge.fit_ladder.v0"
FIT_ATTEMPT_SCHEMA_VERSION = "llmgauge.fit_attempt.v0"

OOM_MARKERS = (
    "out of memory",
    "cuda out of memory",
    "cuda error: out of memory",
    "cudamalloc failed",
    "cuda malloc failed",
    "cublas status alloc failed",
    "memory allocation failed",
    "cannot allocate memory",
    "failed to allocate",
)

PROCESS_KILLED_MARKERS = (
    "killed",
    "sigkill",
    "signal 9",
)


def _require_positive_int(value: int, *, field_name: str) -> None:
    if value <= 0:
        raise ValueError(f"{field_name} must be positive: {value}")


def _combined_failure_text(stdout: str, stderr: str) -> str:
    return f"{stdout}\n{stderr}".lower()


def _excerpt(value: str, *, max_chars: int = 1200) -> str:
    if len(value) <= max_chars:
        return value
    return value[-max_chars:]


def build_context_fallback_plan(
    requested_ctx: int,
    fallback_contexts: list[int],
) -> list[int]:
    """Build a descending context-first fallback plan.

    The requested context is always attempted first. Lower fallback contexts are
    attempted from largest to smallest. Contexts above the requested context are
    ignored because they are not fallbacks.
    """
    _require_positive_int(requested_ctx, field_name="requested_ctx")

    for ctx in fallback_contexts:
        _require_positive_int(ctx, field_name="fallback context")

    lower_or_equal = sorted(
        {ctx for ctx in fallback_contexts if ctx <= requested_ctx},
        reverse=True,
    )

    if requested_ctx not in lower_or_equal:
        lower_or_equal.insert(0, requested_ctx)

    return lower_or_equal


def build_fit_attempt_plan(
    *,
    requested_ctx: int,
    fallback_contexts: list[int],
    batch_size: int,
    ubatch_size: int,
    gpu_layers: int,
) -> list[dict[str, Any]]:
    """Build explicit fit attempts without executing them."""
    _require_positive_int(batch_size, field_name="batch_size")
    _require_positive_int(ubatch_size, field_name="ubatch_size")

    contexts = build_context_fallback_plan(
        requested_ctx=requested_ctx,
        fallback_contexts=fallback_contexts,
    )

    attempts: list[dict[str, Any]] = []
    for index, ctx in enumerate(contexts, start=1):
        attempts.append(
            {
                "attempt_id": f"attempt-{index:02d}",
                "ctx_size": ctx,
                "batch_size": batch_size,
                "ubatch_size": ubatch_size,
                "gpu_layers": gpu_layers,
                "is_requested_settings": index == 1,
                "fallback_axes": [] if index == 1 else ["context"],
            }
        )

    return attempts


def classify_fit_failure(
    *,
    exit_status: int,
    stdout: str = "",
    stderr: str = "",
) -> dict[str, Any]:
    """Classify whether a llama.cpp attempt failed in a retry-relevant way."""
    if exit_status == 0:
        return {
            "status": "completed",
            "failure_class": None,
            "retryable": False,
            "reason": "completed",
        }

    failure_text = _combined_failure_text(stdout, stderr)

    if any(marker in failure_text for marker in OOM_MARKERS):
        return {
            "status": "failed",
            "failure_class": "oom",
            "retryable": True,
            "reason": "out-of-memory marker detected",
        }

    if exit_status == 137 or any(
        marker in failure_text for marker in PROCESS_KILLED_MARKERS
    ):
        return {
            "status": "failed",
            "failure_class": "process_killed",
            "retryable": True,
            "reason": "process-killed marker detected",
        }

    return {
        "status": "failed",
        "failure_class": "runtime_error",
        "retryable": False,
        "reason": "nonzero exit without recognized fit-failure marker",
    }


def build_fit_attempt_record(
    *,
    attempt_id: str,
    ctx_size: int,
    batch_size: int,
    ubatch_size: int,
    gpu_layers: int,
    exit_status: int,
    stdout: str = "",
    stderr: str = "",
    result_dir: str | None = None,
    vram_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    classification = classify_fit_failure(
        exit_status=exit_status,
        stdout=stdout,
        stderr=stderr,
    )

    return {
        "schema_version": FIT_ATTEMPT_SCHEMA_VERSION,
        "attempt_id": attempt_id,
        "ctx_size": ctx_size,
        "batch_size": batch_size,
        "ubatch_size": ubatch_size,
        "gpu_layers": gpu_layers,
        "status": classification["status"],
        "failure_class": classification["failure_class"],
        "retryable": classification["retryable"],
        "failure_reason": classification["reason"],
        "exit_status": exit_status,
        "stderr_excerpt": _excerpt(stderr),
        "result_dir": result_dir,
        "vram": vram_summary,
    }


def build_fit_ladder_summary(
    *,
    fit_ladder_id: str,
    requested_settings: dict[str, Any],
    retry_policy: dict[str, Any],
    attempts: list[dict[str, Any]],
) -> dict[str, Any]:
    completed_attempt = next(
        (attempt for attempt in attempts if attempt.get("status") == "completed"),
        None,
    )
    failed_attempts = [
        attempt for attempt in attempts if attempt.get("status") == "failed"
    ]
    oom_detected = any(
        attempt.get("failure_class") == "oom" for attempt in failed_attempts
    )

    selected_working_settings = None
    if completed_attempt is not None:
        selected_working_settings = {
            "ctx_size": completed_attempt["ctx_size"],
            "batch_size": completed_attempt["batch_size"],
            "ubatch_size": completed_attempt["ubatch_size"],
            "gpu_layers": completed_attempt["gpu_layers"],
            "attempt_id": completed_attempt["attempt_id"],
        }

    requested_ctx = requested_settings.get("ctx_size")
    selected_ctx = (
        selected_working_settings.get("ctx_size")
        if selected_working_settings is not None
        else None
    )
    fallback_changed_context = (
        selected_ctx is not None
        and requested_ctx is not None
        and selected_ctx != requested_ctx
    )

    if completed_attempt is None:
        final_status = "failed"
    elif failed_attempts:
        final_status = "completed_with_fallback"
    else:
        final_status = "completed_without_fallback"

    return {
        "schema_version": FIT_LADDER_SCHEMA_VERSION,
        "fit_ladder_id": fit_ladder_id,
        "requested_settings": requested_settings,
        "retry_policy": retry_policy,
        "selected_working_settings": selected_working_settings,
        "final_status": final_status,
        "summary": {
            "attempted": len(attempts),
            "completed": 1 if completed_attempt is not None else 0,
            "failed": len(failed_attempts),
            "oom_detected": oom_detected,
            "fallback_changed_context": fallback_changed_context,
        },
        "attempts": attempts,
    }
