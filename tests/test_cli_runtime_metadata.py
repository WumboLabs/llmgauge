import json
from pathlib import Path

from typer.testing import CliRunner

from llmgauge.cli import app
from llmgauge.core.export_index import build_run_index_item
from llmgauge.core.reports import build_markdown_report

runner = CliRunner()


def test_run_dry_run_shows_reasoning_mode_and_command_preview(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    examples_dir = tmp_path / "examples" / "configs"
    examples_dir.mkdir(parents=True)

    llama_cli = tmp_path / "llama-cli"
    llama_cli.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    llama_cli.chmod(0o755)

    model_path = tmp_path / "model.gguf"
    model_path.write_text("fake model placeholder\n", encoding="utf-8")

    (examples_dir / "llmgauge.local.yaml").write_text(
        f"""schema_version: llmgauge.config.v0
runtime:
  llama_cli: {llama_cli}
""",
        encoding="utf-8",
    )

    (examples_dir / "model-profiles.local.yaml").write_text(
        f"""schema_version: llmgauge.model_profiles.v0
models:
  example_model:
    label: Example Model
    path: {model_path}
""",
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "run",
            "--suite",
            "core-v1",
            "--include",
            "honesty",
            "--model-profile",
            "example_model",
            "--reasoning-mode",
            "default",
            "--dry-run",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Reasoning mode" in result.output
    assert "default" in result.output
    assert "Command preview" in result.output
    assert "--reasoning" not in result.output


def test_report_and_export_index_include_runtime_metadata(tmp_path: Path) -> None:
    result_dir = tmp_path / "run-metadata"
    (result_dir / "raw").mkdir(parents=True)
    (result_dir / "logs").mkdir(parents=True)

    result = {
        "schema_version": "llmgauge.result.v0",
        "llmgauge_version": "0.66.0",
        "run": {
            "run_id": "run-metadata",
            "timestamp_utc": "2026-07-08T00:00:00+00:00",
            "status": "completed",
            "result_dir": str(result_dir),
        },
        "model": {
            "model_id": "nemotron",
            "model_source": "model_profile",
            "model_profile": "nemotron_profile",
            "model_path": "redacted",
            "model_path_policy": "redacted",
        },
        "runtime": {
            "backend": "llama.cpp",
            "llama_cli": "/bin/llama-cli",
            "ctx_size": 8192,
            "max_tokens": 800,
            "temperature": 0.2,
            "top_p": 0.95,
            "batch_size": 256,
            "ubatch_size": 64,
            "gpu_layers": 999,
            "flash_attn": "auto",
            "runtime_label": "stock-reference",
            "reasoning_mode": "off",
            "runtime_command_captured": True,
            "runtime_command_path": "runtime-command.json",
        },
        "suite": {
            "suite_id": "wumbolabs-practical-v1",
            "suite_version": "0.2.0",
            "prompt_count": 1,
        },
        "summary": {"completed": 1, "failed": 0},
        "results": [
            {
                "prompt_id": "honesty-unknown-tool",
                "category": "honesty",
                "status": "completed",
                "raw_prompt_path": "raw/honesty-unknown-tool.prompt.md",
                "raw_output_path": "raw/honesty-unknown-tool.output.txt",
                "stderr_log_path": "logs/honesty-unknown-tool.stderr.log",
                "exit_status": 0,
                "metrics": {
                    "prompt_eval_tps": 100.0,
                    "generation_tps": 50.0,
                },
            }
        ],
    }

    (result_dir / "llmgauge-result.json").write_text(
        json.dumps(result),
        encoding="utf-8",
    )
    (result_dir / "runtime-command.json").write_text(
        json.dumps(
            {
                "schema_version": "llmgauge.runtime_command.v0",
                "reasoning_mode": "off",
                "model_source": "model_profile",
            }
        ),
        encoding="utf-8",
    )
    (result_dir / "raw" / "honesty-unknown-tool.prompt.md").write_text(
        "prompt",
        encoding="utf-8",
    )
    (result_dir / "raw" / "honesty-unknown-tool.output.txt").write_text(
        "output",
        encoding="utf-8",
    )
    (result_dir / "logs" / "honesty-unknown-tool.stderr.log").write_text(
        "stderr",
        encoding="utf-8",
    )

    report = build_markdown_report(result)
    assert "Model source: model_profile" in report
    assert "Reasoning mode: off" in report
    assert "Command metadata: captured" in report
    assert "`runtime-command.json`" in report

    index_item = build_run_index_item(result_dir)
    assert index_item["model_source"] == "model_profile"
    assert index_item["reasoning_mode"] == "off"
    assert index_item["runtime_command_captured"] is True
    assert index_item["runtime_command_path"] == str(
        result_dir / "runtime-command.json"
    )


def test_direct_model_path_run_sets_model_source(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    examples_dir = tmp_path / "examples" / "configs"
    examples_dir.mkdir(parents=True)

    llama_cli = tmp_path / "llama-cli"
    llama_cli.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    llama_cli.chmod(0o755)

    model_path = tmp_path / "model.gguf"
    model_path.write_text("fake model placeholder\n", encoding="utf-8")

    (examples_dir / "llmgauge.local.yaml").write_text(
        f"""schema_version: llmgauge.config.v0
runtime:
  llama_cli: {llama_cli}
""",
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "run",
            "--suite",
            "core-v1",
            "--include",
            "honesty",
            "--model-id",
            "direct-model",
            "--model-path",
            str(model_path),
            "--dry-run",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "direct_model_path" in result.output
    assert "None" in result.output