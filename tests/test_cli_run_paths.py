import json
from pathlib import Path
from types import SimpleNamespace

from typer.testing import CliRunner

from llmgauge import __version__
import llmgauge.cli as cli
from llmgauge.commands import run_helpers

runner = CliRunner()


def test_execute_run_resolves_builtin_suite_prompt_paths(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    def fake_run_llama_cpp(config, prompt):
        return SimpleNamespace(
            command=[
                str(config.llama_cli),
                "--model",
                str(config.model_path),
            ],
            stdout="\n> SYSTEM:\n\nSystem prompt\n\nUSER:\n\nPrompt text ... (truncated)\n\nModel answer.\n\n[ Prompt: 100.0 t/s | Generation: 50.0 t/s ]\n\nExiting...\n",
            stderr="",
            exit_status=0,
        )

    monkeypatch.setattr(run_helpers, "run_llama_cpp", fake_run_llama_cpp)

    result = cli._execute_run(
        suite=Path("agent-backend-v1"),
        only="tool-honesty/fake-tool-resistance",
        include="all",
        resolved={
            "model_id": "test-model",
            "model_profile": "test-profile",
            "profile": {
                "label": "Test Model",
                "family": "Test",
                "role": "test",
                "quant": "test",
            },
            "config_path": None,
            "model_profiles_path": None,
            "model_path": Path("/models/test.gguf"),
            "llama_cli": Path("/bin/llama-cli"),
            "ctx": 8192,
            "max_tokens": 64,
            "temp": 0.2,
            "top_p": 0.95,
            "batch": 256,
            "ubatch": 64,
            "gpu_layers": 999,
            "flash_attn": "auto",
            "runtime_label": None,
            "vram_min_headroom_warn_mib": None,
        },
        out=tmp_path / "result",
        fail_on_failed_prompts=True,
    )

    assert result["llmgauge_version"] == __version__
    assert result["run"]["status"] == "completed"
    assert result["suite"]["suite_id"] == "agent-backend-v1"
    assert result["summary"]["completed"] == 1
    assert result["summary"]["failed"] == 0

    result_json = json.loads(
        (tmp_path / "result" / "llmgauge-result.json").read_text(encoding="utf-8")
    )
    assert result_json["llmgauge_version"] == __version__

    raw_prompt = (
        tmp_path / "result" / "raw" / "tool-honesty" / "fake-tool-resistance.prompt.md"
    )
    raw_output = (
        tmp_path / "result" / "raw" / "tool-honesty" / "fake-tool-resistance.output.txt"
    )
    cleaned_output = (
        tmp_path
        / "result"
        / "cleaned"
        / "tool-honesty"
        / "fake-tool-resistance.output.txt"
    )

    assert raw_prompt.exists()
    assert raw_output.exists()
    assert cleaned_output.exists()
    assert "Fake Tool Resistance" in raw_prompt.read_text(encoding="utf-8")
    assert "> SYSTEM:" in raw_output.read_text(encoding="utf-8")
    assert cleaned_output.read_text(encoding="utf-8") == "Model answer.\n"
    assert (
        result["results"][0]["cleaned_output_path"]
        == "cleaned/tool-honesty/fake-tool-resistance.output.txt"
    )


def test_execute_run_records_vram_guardrail_warning(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    def fake_run_llama_cpp(config, prompt):
        return SimpleNamespace(
            command=[
                str(config.llama_cli),
                "--model",
                str(config.model_path),
            ],
            stdout="[ Prompt: 100.0 t/s | Generation: 50.0 t/s ]",
            stderr="",
            exit_status=0,
            vram_samples=[],
            vram_summary={
                "schema_version": "llmgauge.vram.summary.v0",
                "available": True,
                "peak_used_mib": 11800,
                "peak_total_mib": 12227,
            },
        )

    monkeypatch.setattr(run_helpers, "run_llama_cpp", fake_run_llama_cpp)

    result = cli._execute_run(
        suite=Path("agent-backend-v1"),
        only="tool-honesty/fake-tool-resistance",
        include="all",
        resolved={
            "model_id": "test-model",
            "model_profile": "test-profile",
            "profile": {
                "label": "Test Model",
                "family": "Test",
                "role": "test",
                "quant": "test",
            },
            "config_path": None,
            "model_profiles_path": None,
            "model_path": Path("/models/test.gguf"),
            "llama_cli": Path("/bin/llama-cli"),
            "ctx": 8192,
            "max_tokens": 64,
            "temp": 0.2,
            "top_p": 0.95,
            "batch": 256,
            "ubatch": 64,
            "gpu_layers": 999,
            "flash_attn": "auto",
            "runtime_label": None,
            "vram_min_headroom_warn_mib": 1000,
        },
        out=tmp_path / "result",
        fail_on_failed_prompts=True,
    )

    guardrails = result["results"][0]["vram_guardrails"]

    assert guardrails["schema_version"] == "llmgauge.vram.guardrails.v0"
    assert guardrails["status"] == "warning"
    assert guardrails["min_headroom_warn_mib"] == 1000
    assert guardrails["observed_headroom_mib"] == 427
    assert guardrails["warnings"] == ["vram_headroom_below_warning_threshold"]
    assert result["runtime"]["vram_min_headroom_warn_mib"] == 1000


def test_execute_run_records_vram_guardrail_ok(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    def fake_run_llama_cpp(config, prompt):
        return SimpleNamespace(
            command=[
                str(config.llama_cli),
                "--model",
                str(config.model_path),
            ],
            stdout="[ Prompt: 100.0 t/s | Generation: 50.0 t/s ]",
            stderr="",
            exit_status=0,
            vram_samples=[],
            vram_summary={
                "schema_version": "llmgauge.vram.summary.v0",
                "available": True,
                "peak_used_mib": 7000,
                "peak_total_mib": 12227,
            },
        )

    monkeypatch.setattr(run_helpers, "run_llama_cpp", fake_run_llama_cpp)

    result = cli._execute_run(
        suite=Path("agent-backend-v1"),
        only="tool-honesty/fake-tool-resistance",
        include="all",
        resolved={
            "model_id": "test-model",
            "model_profile": "test-profile",
            "profile": {
                "label": "Test Model",
                "family": "Test",
                "role": "test",
                "quant": "test",
            },
            "config_path": None,
            "model_profiles_path": None,
            "model_path": Path("/models/test.gguf"),
            "llama_cli": Path("/bin/llama-cli"),
            "ctx": 8192,
            "max_tokens": 64,
            "temp": 0.2,
            "top_p": 0.95,
            "batch": 256,
            "ubatch": 64,
            "gpu_layers": 999,
            "flash_attn": "auto",
            "runtime_label": None,
            "vram_min_headroom_warn_mib": 1000,
        },
        out=tmp_path / "result",
        fail_on_failed_prompts=True,
    )

    guardrails = result["results"][0]["vram_guardrails"]

    assert guardrails["status"] == "ok"
    assert guardrails["observed_headroom_mib"] == 5227
    assert guardrails["warnings"] == []


def test_run_batch_uses_manifest_model_profiles(
    tmp_path: Path,
    monkeypatch,
) -> None:
    manifest = tmp_path / "batch.yaml"
    manifest.write_text(
        "\n".join(
            [
                "schema_version: llmgauge.batch_manifest.v0",
                "batch_id: batch-test",
                "suite: agent-backend-v1",
                "only: tool-honesty/fake-tool-resistance",
                "include: all",
                "max_tokens: 300",
                "models:",
                "  - gemma4_12b_qat_q4",
                "  - gemma4_12b_q5",
                "",
            ]
        ),
        encoding="utf-8",
    )

    resolved_calls = []

    def fake_resolve_run_options(**kwargs):
        resolved_calls.append(kwargs)
        return {
            "model_id": kwargs["model_profile"],
            "model_profile": kwargs["model_profile"],
            "profile": {},
            "config_path": kwargs["config_path"],
            "model_profiles_path": kwargs["model_profiles_path"],
            "model_path": Path("/models/test.gguf"),
            "llama_cli": Path("/bin/llama-cli"),
            "ctx": 8192,
            "max_tokens": kwargs["max_tokens"],
            "temp": 0.2,
            "top_p": 0.95,
            "batch": 256,
            "ubatch": 64,
            "gpu_layers": 999,
            "flash_attn": "auto",
            "runtime_label": None,
            "vram_min_headroom_warn_mib": None,
        }

    def fake_execute_run(**kwargs):
        resolved = kwargs["resolved"]
        return {
            "run": {"status": "completed"},
            "model": {"model_id": resolved["model_id"]},
            "summary": {"completed": 1, "failed": 0},
        }

    monkeypatch.setattr(run_helpers, "resolve_run_options", fake_resolve_run_options)
    monkeypatch.setattr(run_helpers, "execute_run", fake_execute_run)

    cli.run_batch(
        manifest=manifest,
        config_path=tmp_path / "llmgauge.local.yaml",
        model_profiles_path=tmp_path / "model-profiles.local.yaml",
        out=tmp_path / "batch-out",
    )

    assert [call["model_profile"] for call in resolved_calls] == [
        "gemma4_12b_qat_q4",
        "gemma4_12b_q5",
    ]
    assert [call["max_tokens"] for call in resolved_calls] == [300, 300]
    assert all(call["model_path"] is None for call in resolved_calls)

    summary_path = tmp_path / "batch-out" / "batch-summary.json"
    report_path = tmp_path / "batch-out" / "batch-report.md"

    assert summary_path.exists()
    assert report_path.exists()
    assert "gemma4_12b_qat_q4" in report_path.read_text(encoding="utf-8")
    assert "gemma4_12b_q5" in report_path.read_text(encoding="utf-8")


def test_run_dry_run_resolves_without_output_dir(
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
defaults:
  ctx_size: 8192
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

    def fake_run_llama_cpp(config, prompt):
        raise AssertionError("dry-run must not launch llama.cpp")

    monkeypatch.setattr(run_helpers, "run_llama_cpp", fake_run_llama_cpp)

    result = runner.invoke(
        cli.app,
        [
            "run",
            "--suite",
            "core-v1",
            "--include",
            "honesty",
            "--model-profile",
            "example_model",
            "--dry-run",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "LLMGauge Run Dry Run" in result.output
    assert "Dry run complete" in result.output
    assert "example_model" in result.output
    assert "honesty-unknown-tool" in result.output
    assert not Path("results").exists()


def test_run_without_output_still_requires_output_when_not_dry_run(
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
        cli.app,
        [
            "run",
            "--suite",
            "core-v1",
            "--include",
            "honesty",
            "--model-profile",
            "example_model",
        ],
    )

    assert result.exit_code != 0
    assert "Use --out PATH or --auto-name" in result.output


def test_run_ladder_dry_run_resolves_without_output_dir(
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
defaults:
  ctx_size: 8192
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

    def fake_execute_run(**kwargs):
        raise AssertionError("ladder dry-run must not execute child runs")

    monkeypatch.setattr(run_helpers, "execute_run", fake_execute_run)

    result = runner.invoke(
        cli.app,
        [
            "run-ladder",
            "--suite",
            "core-v1",
            "--include",
            "honesty",
            "--model-profile",
            "example_model",
            "--ctx-ladder",
            "8192,12288",
            "--dry-run",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "LLMGauge Run Ladder Dry Run" in result.output
    assert "Ladder dry run complete" in result.output
    assert "example_model" in result.output
    assert "8192" in result.output
    assert "12288" in result.output
    assert "honesty-unknown-tool" in result.output
    assert not Path("results").exists()
