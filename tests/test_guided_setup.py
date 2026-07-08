from pathlib import Path

import pytest

from llmgauge.core.guided_setup import (
    discover_model_directory_candidates,
    scan_gguf_files,
    sanitize_profile_name,
    update_config_llama_cli,
)


def test_sanitize_profile_name_is_deterministic() -> None:
    assert sanitize_profile_name("My-Model_Q4_K_M.gguf") == "my_model_q4_k_m"
    assert sanitize_profile_name("My-Model_Q4_K_M.gguf") == sanitize_profile_name(
        "My-Model_Q4_K_M.gguf"
    )
    assert sanitize_profile_name("!!!.gguf") == "model"
    assert len(sanitize_profile_name("a" * 80 + ".gguf")) <= 48


def test_scan_gguf_files_finds_and_sorts_deterministically(tmp_path: Path) -> None:
    (tmp_path / "zeta.gguf").write_text("z\n", encoding="utf-8")
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "alpha.gguf").write_text("a\n", encoding="utf-8")

    files, total = scan_gguf_files(tmp_path)

    assert total == 2
    assert [path.name for path in files] == ["alpha.gguf", "zeta.gguf"]


def test_scan_gguf_files_caps_display_count(tmp_path: Path) -> None:
    for index in range(60):
        (tmp_path / f"model_{index:03d}.gguf").write_text("x\n", encoding="utf-8")

    files, total = scan_gguf_files(tmp_path, limit=50)

    assert total == 60
    assert len(files) == 50


def test_discover_model_directory_candidates_includes_local_models_dir(
    tmp_path: Path,
) -> None:
    models_dir = tmp_path / "models"
    models_dir.mkdir()

    candidates = discover_model_directory_candidates(cwd=tmp_path)

    assert models_dir.resolve() in candidates


def test_update_config_llama_cli_refuses_existing_without_force(tmp_path: Path) -> None:
    llama_cli = tmp_path / "llama-cli"
    llama_cli.write_text("#!/bin/sh\n", encoding="utf-8")
    llama_cli.chmod(0o755)

    other_cli = tmp_path / "other-llama-cli"
    other_cli.write_text("#!/bin/sh\n", encoding="utf-8")
    other_cli.chmod(0o755)

    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        f"""schema_version: llmgauge.config.v0
runtime:
  llama_cli: {llama_cli}
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="use --force"):
        update_config_llama_cli(config_path, other_cli, force=False)

    update_config_llama_cli(config_path, other_cli, force=True)
    assert str(other_cli.resolve()) in config_path.read_text(encoding="utf-8")


def test_update_config_llama_cli_replaces_placeholder(tmp_path: Path) -> None:
    llama_cli = tmp_path / "llama-cli"
    llama_cli.write_text("#!/bin/sh\n", encoding="utf-8")
    llama_cli.chmod(0o755)

    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """schema_version: llmgauge.config.v0
runtime:
  llama_cli: /path/to/llama-cli
""",
        encoding="utf-8",
    )

    update_config_llama_cli(config_path, llama_cli, force=False)
    assert str(llama_cli.resolve()) in config_path.read_text(encoding="utf-8")