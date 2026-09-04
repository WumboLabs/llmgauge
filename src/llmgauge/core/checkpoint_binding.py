"""External-vLLM local-checkpoint <-> served-model binding evidence (M3).

Implements the binding portion of the accepted first-class model-identity
contract (docs/FIRST_CLASS_RUNTIME_ARCHITECTURE.md §4.3, §5.3;
docs/VLLM_RUNTIME_CONTRACT.md). An operator-managed vLLM server never proves
which local checkpoint bytes it admitted, so the relationship between a
locally-observed checkpoint identity and a server-listed served-model name is
recorded as ``operator_declared`` — the operator configured the checkpoint
path and served-model name as one profile/run. Stronger binding classes
(``llmgauge_observed``) belong to the later managed-lifecycle milestone (M4)
and are rejected for external-server results by the validator.

The record is deliberately small: it links to the M2 checkpoint provenance by
its public fingerprint and never duplicates the private manifest, full hashes,
or the absolute checkpoint root path.
"""

from __future__ import annotations

from typing import Any

CHECKPOINT_BINDING_SCHEMA_VERSION = "llmgauge.vllm_checkpoint_binding.v0"

#: The only binding class an external-server run may record in M3.
BINDING_CLASS_OPERATOR_DECLARED = "operator_declared"

#: Closed vocabulary for the binding relation class. ``llmgauge_observed`` is
#: reserved for the future managed lifecycle (M4) where LLMGauge owns the
#: server launch/admission path; ``server_reported`` is deliberately NOT
#: admitted for the checkpoint association because a server listing a
#: served-model name never attests the local checkpoint bytes behind it.
BINDING_PROVENANCE_CLASSES = frozenset(
    {
        BINDING_CLASS_OPERATOR_DECLARED,
        "server_reported",
        "llmgauge_observed",
    }
)

#: Classes admissible for external-operator lifecycle results in this contract.
EXTERNAL_ADMISSIBLE_BINDING_CLASSES = frozenset({BINDING_CLASS_OPERATOR_DECLARED})

BINDING_STATUS_BOUND = "bound"
BINDING_STATUS_UNBOUND = "unbound"

BINDING_EVIDENCE_CEILING = (
    "The server-listed served-model name does not prove which local checkpoint "
    "bytes the server loaded; the checkpoint-to-server association is "
    "operator-declared, not server-attested."
)


def build_checkpoint_binding_record(
    *,
    requested_served_model: str,
    observed_served_model: str | None,
    checkpoint_public_fingerprint: str | None,
    observed_vllm_version: str | None,
    lifecycle_ownership: str = "external_operator",
) -> dict[str, Any]:
    """Build the additive run-level binding evidence record.

    ``checkpoint_public_fingerprint`` is the M2 shortened display fingerprint
    (``sha256:`` + 16 hex); it links this record to the full private
    ``model.provenance`` block without duplicating it. The absolute checkpoint
    root is never an input.

    ``observed_vllm_version`` is the server-reported ``/version`` string. A
    server-backed run fingerprint requires it; when it is unavailable the
    result stays valid under the external-server evidence ceiling and this
    record carries the precise ineligibility reason.
    """

    bound = observed_served_model == requested_served_model
    version_observed = (
        isinstance(observed_vllm_version, str)
        and bool(observed_vllm_version)
        and observed_vllm_version != "unknown"
    )
    record: dict[str, Any] = {
        "schema_version": CHECKPOINT_BINDING_SCHEMA_VERSION,
        "status": BINDING_STATUS_BOUND if bound else BINDING_STATUS_UNBOUND,
        "binding_provenance_class": BINDING_CLASS_OPERATOR_DECLARED,
        "lifecycle_ownership": lifecycle_ownership,
        "requested_served_model": requested_served_model,
        "observed_served_model": observed_served_model,
        "served_model_observation_source": "server_/v1/models_listing",
        "checkpoint_public_fingerprint": checkpoint_public_fingerprint,
        "checkpoint_identity_source": "llmgauge_local_file_observation",
        "evidence_ceiling": BINDING_EVIDENCE_CEILING,
        # Effective-runtime boundaries: the local checkpoint carries the
        # tokenizer/chat-template/quantization identity recorded in
        # model.provenance. What the external server actually used for
        # rendering and quantization is not observable from the client side,
        # so these remain explicitly unobserved rather than claimed equal.
        "effective_runtime_chat_template": "unobserved",
        "effective_runtime_quantization": "unavailable",
        "fingerprint_eligible": bound and version_observed,
    }
    if not record["fingerprint_eligible"]:
        record["fingerprint_ineligible_reason"] = (
            "observed vLLM server /version is unavailable; a server-backed run "
            "fingerprint requires a non-empty server version observation"
            if bound
            else "the requested served model was not observed in the server "
            "listing; no checkpoint-to-server binding is established"
        )
    return record
