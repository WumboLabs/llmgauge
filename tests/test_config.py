from pathlib import Path

import yaml

from llmgauge.core.config import (
    get_config_value,
    load_llmgauge_config,
    load_model_profiles,
    resolve_model_profile,
)


def test_get_config_value_nested() -> None:
    config = {"runtime": {"llama_cli": "/tmp/llama-cli"}}

    assert get_config_value(config, "runtime.llama_cli") == "/tmp/llama-cli"
    assert get_config_value(config, "runtime.missing", "fallback") == "fallback"


def test_load_model_profiles(tmp_path: Path) -> None:
    path = tmp_path / "models.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "schema_version": "llmgauge.model_profiles.v0",
                "models": {
                    "test_model": {
                        "label": "Test Model",
                        "path": "/tmp/model.gguf",
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    profiles = load_model_profiles(path)

    assert profiles["test_model"]["label"] == "Test Model"


def test_resolve_model_profile() -> None:
    profiles = {
        "test_model": {
            "label": "Test Model",
            "path": "/tmp/model.gguf",
            "ctx_size": 8192,
        }
    }

    profile = resolve_model_profile(profiles, "test_model")

    assert profile["profile_name"] == "test_model"
    assert profile["path"] == "/tmp/model.gguf"


def test_load_llmgauge_config_none() -> None:
    assert load_llmgauge_config(None) == {}
