from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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
    recommended_contexts: list[int] | None = None

    @field_validator("path")
    @classmethod
    def validate_path_not_empty(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("path must not be empty")
        return value


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


class DefaultsConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    ctx_size: int | None = None
    max_tokens: int | None = None
    temperature: float | None = None
    top_p: float | None = None
    batch_size: int | None = None
    ubatch_size: int | None = None
    gpu_layers: int | None = None
    flash_attn: str | bool | None = None
    runtime_label: str | None = None


class LlmgaugeConfigDocument(BaseModel):
    model_config = ConfigDict(extra="allow")

    schema_version: Literal["llmgauge.config.v0"] = "llmgauge.config.v0"
    runtime: RuntimeConfig | None = None
    defaults: DefaultsConfig | None = None


def validate_model_profiles_document(data: dict[str, Any]) -> ModelProfilesDocument:
    return ModelProfilesDocument.model_validate(data)


def validate_llmgauge_config_document(data: dict[str, Any]) -> LlmgaugeConfigDocument:
    return LlmgaugeConfigDocument.model_validate(data)


def format_validation_error(exc: Exception) -> str:
    from pydantic import ValidationError

    if isinstance(exc, ValidationError):
        messages = []
        for error in exc.errors():
            location = ".".join(str(part) for part in error["loc"])
            messages.append(f"{location}: {error['msg']}")
        return "; ".join(messages)

    return str(exc)


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


def resolve_profile_path_status(raw_path: str | None) -> str:
    if not isinstance(raw_path, str) or not raw_path:
        return "missing-path"

    model_path = Path(raw_path)
    return "ok" if model_path.exists() else "missing-file"
