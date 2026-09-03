from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


MODEL_SOURCE_KINDS: tuple[str, ...] = (
    "gguf_file",
    "checkpoint_directory",
    "served_model_reference",
)


class ModelProfileEntry(BaseModel):
    model_config = ConfigDict(extra="allow")

    label: str | None = None
    family: str | None = None
    role: str | None = None
    quant: str | None = None
    path: str | None = None
    notes: str | None = None
    ctx_size: int | None = None
    max_tokens: int | None = None
    temperature: float | None = None
    top_p: float | None = None
    batch_size: int | None = None
    ubatch_size: int | None = None
    gpu_layers: int | None = None
    flash_attn: str | bool | None = None
    runtime_label: str | None = None
    reasoning_mode: str | None = None
    fit: str | bool | None = None
    reasoning_preserve: bool | None = None
    spec_type: str | None = None
    recommended_contexts: list[int] | None = None
    # Additive vLLM external-server fields (optional; llama.cpp profiles ignore).
    backend: str | None = None
    vllm_endpoint: str | None = None
    served_model: str | None = None
    connect_timeout: float | None = None
    request_timeout: float | None = None
    max_response_bytes: int | None = None
    vllm_streaming_evidence: bool | None = None
    # Additive runtime-neutral model source discriminator (M1). Declared last
    # so legacy profile serialization keeps its baseline field order.
    source_kind: str | None = None

    @field_validator("path")
    @classmethod
    def validate_path_not_empty(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("path must not be empty")
        return value

    @field_validator("backend")
    @classmethod
    def validate_backend(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if normalized not in {"llama.cpp", "vllm"}:
            raise ValueError("backend must be one of: llama.cpp, vllm")
        return normalized

    @field_validator("source_kind")
    @classmethod
    def validate_source_kind(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if normalized not in MODEL_SOURCE_KINDS:
            raise ValueError(
                "source_kind must be one of: " + ", ".join(sorted(MODEL_SOURCE_KINDS))
            )
        return normalized

    @model_validator(mode="after")
    def validate_source_shape(self) -> "ModelProfileEntry":
        # Cross-field source-shape rules apply only to profiles carrying an
        # explicit source_kind; legacy profiles keep their existing semantics.
        if self.source_kind is None:
            return self
        if self.source_kind in {"gguf_file", "checkpoint_directory"}:
            if self.path is None or not self.path.strip():
                raise ValueError(
                    f"source_kind {self.source_kind!r} requires a non-empty local path"
                )
        if self.source_kind == "served_model_reference":
            if self.served_model is None or not str(self.served_model).strip():
                raise ValueError(
                    "source_kind 'served_model_reference' requires a "
                    "non-empty served_model"
                )
            if self.path is not None and self.path.strip():
                raise ValueError(
                    "source_kind 'served_model_reference' does not accept a "
                    "local path in this contract; binding a served reference "
                    "to a local checkpoint is deferred"
                )
        return self


class ModelProfilesDocument(BaseModel):
    model_config = ConfigDict(extra="allow")

    schema_version: Literal["llmgauge.model_profiles.v0"] = "llmgauge.model_profiles.v0"
    models: dict[str, ModelProfileEntry] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def normalize_models_mapping(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        models = data.get("models")
        if models is None:
            data["models"] = {}
        elif not isinstance(models, dict):
            raise ValueError("Field 'models' must be a mapping")

        return data


class RuntimeConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    backend: str | None = None
    llama_cli: str | None = None
    llama_bench: str | None = None
    llama_tokenize: str | None = None
    build_label: str | None = None
    commit: str | None = None
    # Additive vLLM external-server defaults (optional).
    vllm_endpoint: str | None = None
    served_model: str | None = None
    connect_timeout: float | None = None
    request_timeout: float | None = None
    max_response_bytes: int | None = None
    vllm_streaming_evidence: bool | None = None

    @field_validator("backend")
    @classmethod
    def validate_backend(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if normalized not in {"llama.cpp", "vllm"}:
            raise ValueError("backend must be one of: llama.cpp, vllm")
        return normalized


class DefaultsConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    ctx_size: int | None = None
    max_tokens: int | None = None
    temperature: float | None = None
    top_p: float | None = None
    top_k: int | None = None
    min_p: float | None = None
    seed: int | None = None
    batch_size: int | None = None
    ubatch_size: int | None = None
    gpu_layers: int | None = None
    flash_attn: str | bool | None = None
    cache_type_k: str | None = None
    cache_type_v: str | None = None
    runtime_label: str | None = None
    reasoning_mode: str | None = None
    reasoning_effort: str | None = None
    reasoning_budget: int | None = None
    fit: str | bool | None = None
    reasoning_preserve: bool | None = None
    spec_type: str | None = None


class LlmgaugeConfigDocument(BaseModel):
    model_config = ConfigDict(extra="allow")

    schema_version: Literal["llmgauge.config.v0"] = "llmgauge.config.v0"
    runtime: RuntimeConfig | None = None
    defaults: DefaultsConfig | None = None


def effective_source_kind(profile: Mapping[str, Any]) -> str:
    """Resolve one canonical model source kind for a profile mapping.

    Explicit ``source_kind`` values win. Profiles without a discriminator keep
    their contractual legacy meaning: a ``backend: vllm`` profile is the
    bounded served-model shape, and every other legacy profile is a GGUF file.
    Legacy inference is never derived from filesystem path shape.
    """
    explicit = profile.get("source_kind")
    if isinstance(explicit, str) and explicit.strip():
        kind = explicit.strip().lower()
        if kind not in MODEL_SOURCE_KINDS:
            raise ValueError(
                f"Unknown model source kind: {explicit!r}; expected one of: "
                + ", ".join(MODEL_SOURCE_KINDS)
            )
        return kind

    backend = profile.get("backend")
    if isinstance(backend, str) and backend.strip().lower() == "vllm":
        return "served_model_reference"
    return "gguf_file"


def validate_model_profiles_document(data: dict[str, Any]) -> ModelProfilesDocument:
    return ModelProfilesDocument.model_validate(data)


def validate_llmgauge_config_document(data: dict[str, Any]) -> LlmgaugeConfigDocument:
    return LlmgaugeConfigDocument.model_validate(data)


def format_validation_error(exc: Exception, *, label: str | None = None) -> str:
    from pydantic import ValidationError

    if isinstance(exc, ValidationError):
        messages = []
        for error in exc.errors():
            location = ".".join(str(part) for part in error["loc"])
            messages.append(f"{location}: {error['msg']}")
        detail = "; ".join(messages)
    else:
        detail = str(exc)

    if label is None:
        return detail
    return f"{label}: {detail}"


def model_profile_entry_to_dict(entry: ModelProfileEntry) -> dict[str, Any]:
    return entry.model_dump(exclude_none=True)


def model_profiles_document_to_dict(document: ModelProfilesDocument) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": document.schema_version,
        "models": {
            name: model_profile_entry_to_dict(entry)
            for name, entry in document.models.items()
        },
    }
    return payload


def resolve_profile_source_status(profile: Mapping[str, Any]) -> str:
    """Truthful per-source-kind availability status for profile listings.

    A served-model reference is conservatively ``configured``: M1 never probes
    a server, so no status may imply observed availability or validation.
    """
    kind = effective_source_kind(profile)
    if kind == "served_model_reference":
        return "configured"

    raw_path = profile.get("path")
    if not isinstance(raw_path, str) or not raw_path:
        return "missing-path"

    model_path = Path(raw_path)
    if kind == "checkpoint_directory":
        if not model_path.exists():
            return "missing-directory"
        if not model_path.is_dir():
            return "not-a-directory"
        return "ok"

    return "ok" if model_path.exists() else "missing-file"
