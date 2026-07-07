from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from llmgauge.core.schemas import (
    ModelProfileEntry,
    ModelProfilesDocument,
    format_validation_error,
    model_profiles_document_to_dict,
    validate_model_profiles_document,
)


def _load_raw_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Model profiles file does not exist: {path}")

    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if data is None:
        return {"schema_version": "llmgauge.model_profiles.v0", "models": {}}

    if not isinstance(data, dict):
        raise ValueError(
            f"Model profiles file must be a YAML mapping at the top level: {path}"
        )

    return data


def load_model_profiles_document(path: Path) -> ModelProfilesDocument:
    try:
        return validate_model_profiles_document(_load_raw_yaml(path))
    except Exception as exc:
        raise ValueError(
            format_validation_error(exc, label="Invalid model profiles file")
        ) from exc


def save_model_profiles_document(path: Path, document: ModelProfilesDocument) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = model_profiles_document_to_dict(document)
    path.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def ensure_model_profiles_file(path: Path) -> ModelProfilesDocument:
    if path.exists():
        return load_model_profiles_document(path)

    document = ModelProfilesDocument()
    save_model_profiles_document(path, document)
    return document


def add_model_profile(
    path: Path,
    *,
    profile_name: str,
    model_path: Path,
    label: str | None = None,
    family: str | None = None,
    role: str | None = None,
    quant: str | None = None,
    ctx_size: int | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
    notes: str | None = None,
    overwrite: bool = False,
) -> tuple[ModelProfilesDocument, bool]:
    if not profile_name.strip():
        raise ValueError("Model profile name must not be empty")

    if profile_name in {"schema_version", "models"}:
        raise ValueError(
            f"Model profile name '{profile_name}' is reserved; choose a different name"
        )

    document = ensure_model_profiles_file(path)
    created = profile_name not in document.models

    if not created and not overwrite:
        raise ValueError(
            f"Model profile '{profile_name}' already exists; "
            "pass --force to replace it"
        )

    entry = ModelProfileEntry(
        label=label or profile_name,
        family=family,
        role=role,
        quant=quant,
        path=str(model_path),
        ctx_size=ctx_size,
        max_tokens=max_tokens,
        temperature=temperature,
        notes=notes,
    )
    document.models[profile_name] = entry
    save_model_profiles_document(path, document)
    return document, created


def remove_model_profile(path: Path, *, profile_name: str) -> ModelProfilesDocument:
    document = load_model_profiles_document(path)

    if profile_name not in document.models:
        raise KeyError(
            f"No model profile named '{profile_name}' in the profiles file"
        )

    del document.models[profile_name]
    save_model_profiles_document(path, document)
    return document


def update_model_profile(
    path: Path,
    *,
    profile_name: str,
    model_path: Path | None = None,
    label: str | None = None,
    family: str | None = None,
    role: str | None = None,
    quant: str | None = None,
    ctx_size: int | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
    notes: str | None = None,
) -> ModelProfilesDocument:
    document = load_model_profiles_document(path)

    if profile_name not in document.models:
        raise KeyError(
            f"No model profile named '{profile_name}' in the profiles file"
        )

    current = document.models[profile_name].model_dump(exclude_none=True)

    if label is not None:
        current["label"] = label
    if family is not None:
        current["family"] = family
    if role is not None:
        current["role"] = role
    if quant is not None:
        current["quant"] = quant
    if model_path is not None:
        current["path"] = str(model_path)
    if ctx_size is not None:
        current["ctx_size"] = ctx_size
    if max_tokens is not None:
        current["max_tokens"] = max_tokens
    if temperature is not None:
        current["temperature"] = temperature
    if notes is not None:
        current["notes"] = notes

    document.models[profile_name] = ModelProfileEntry.model_validate(current)
    save_model_profiles_document(path, document)
    return document
