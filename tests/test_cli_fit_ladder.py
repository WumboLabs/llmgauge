from pathlib import Path

from typer.testing import CliRunner

import llmgauge.cli as cli
from llmgauge.commands import run_helpers

runner = CliRunner()


def _resolved(ctx: int | None) -> dict:
    return {
        "model_id": "test-model",
        "model_profile": "test-profile",
        "profile": {},
        "config_path": None,
        "model_profiles_path": None,
        "model_path": Path("/models/test.gguf"),
        "llama_cli": Path("/bin/llama-cli"),
        "ctx": ctx or 65536,
        "max_tokens": 64,
        "temp": 0.2,
        "top_p": 0.95,
        "batch": 256,
        "ubatch": 64,
        "gpu_layers": 999,
        "flash_attn": "auto",
        "runtime_label": None,
        "vram_min_headroom_warn_mib": None,
    }


def test_fit_ladder_dry_run_does_not_execute(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    def fake_resolve_run_options(**kwargs):
        return _resolved(kwargs["ctx"])

    def fake_execute_run(**kwargs):
        raise AssertionError("fit-ladder dry-run must not execute attempts")

    monkeypatch.setattr(run_helpers, "resolve_run_options", fake_resolve_run_options)
    monkeypatch.setattr(run_helpers, "execute_run", fake_execute_run)

    result = runner.invoke(
        cli.app,
        [
            "fit-ladder",
            "--suite",
            "core-v1",
            "--include",
            "honesty",
            "--model-profile",
            "test-profile",
            "--ctx",
            "65536",
            "--fallback-contexts",
            "8192,32768",
            "--dry-run",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "LLMGauge Fit Ladder Dry Run" in result.output
    assert "attempt-01" in result.output
    assert "65536" in result.output
    assert "32768" in result.output
    assert not Path("results").exists()


def test_fit_ladder_executes_until_first_completed(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    def fake_resolve_run_options(**kwargs):
        return _resolved(kwargs["ctx"])

    calls = []

    def fake_execute_run(**kwargs):
        calls.append(kwargs)
        out = kwargs["out"]
        out.mkdir(parents=True, exist_ok=True)

        if len(calls) == 1:
            stderr_path = out / "logs" / "honesty-unknown-tool.stderr.log"
            stdout_path = out / "raw" / "honesty-unknown-tool.output.txt"
            stderr_path.parent.mkdir(parents=True, exist_ok=True)
            stdout_path.parent.mkdir(parents=True, exist_ok=True)
            stderr_path.write_text("CUDA error: out of memory", encoding="utf-8")
            stdout_path.write_text("", encoding="utf-8")

            return {
                "run": {"status": "failed"},
                "results": [
                    {
                        "prompt_id": "honesty-unknown-tool",
                        "status": "failed",
                        "exit_status": 1,
                        "raw_output_path": "raw/honesty-unknown-tool.output.txt",
                        "stderr_log_path": "logs/honesty-unknown-tool.stderr.log",
                        "error": "llama-cli exited nonzero",
                        "vram": {"available": True, "peak_used_mib": 12000},
                    }
                ],
                "summary": {"completed": 0, "failed": 1},
            }

        return {
            "run": {"status": "completed"},
            "results": [
                {
                    "prompt_id": "honesty-unknown-tool",
                    "status": "completed",
                    "exit_status": 0,
                    "raw_output_path": "raw/honesty-unknown-tool.output.txt",
                    "stderr_log_path": "logs/honesty-unknown-tool.stderr.log",
                    "error": None,
                }
            ],
            "summary": {"completed": 1, "failed": 0},
        }

    monkeypatch.setattr(run_helpers, "resolve_run_options", fake_resolve_run_options)
    monkeypatch.setattr(run_helpers, "execute_run", fake_execute_run)

    out = tmp_path / "fit-out"
    result = runner.invoke(
        cli.app,
        [
            "fit-ladder",
            "--suite",
            "core-v1",
            "--include",
            "honesty",
            "--model-profile",
            "test-profile",
            "--ctx",
            "65536",
            "--fallback-contexts",
            "8192,32768",
            "--out",
            str(out),
        ],
    )

    assert result.exit_code == 0, result.output
    assert [call["resolved"]["ctx"] for call in calls] == [65536, 32768]
    assert "oom detected at ctx=65536; retrying at ctx=32768" in result.output.lower()
    assert "Fit ladder report:" in result.output

    summary_path = out / "fit-ladder-summary.json"
    assert summary_path.exists()
    assert (out / "fit-ladder-report.md").exists()

    summary_text = summary_path.read_text(encoding="utf-8")
    assert '"final_status": "completed_with_fallback"' in summary_text
    assert '"ctx_size": 32768' in summary_text
    assert '"failure_class": "oom"' in summary_text


def test_fit_ladder_stops_on_nonretryable_failure(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    def fake_resolve_run_options(**kwargs):
        return _resolved(kwargs["ctx"])

    calls = []

    def fake_execute_run(**kwargs):
        calls.append(kwargs)
        out = kwargs["out"]
        stderr_path = out / "logs" / "honesty-unknown-tool.stderr.log"
        stdout_path = out / "raw" / "honesty-unknown-tool.output.txt"
        stderr_path.parent.mkdir(parents=True, exist_ok=True)
        stdout_path.parent.mkdir(parents=True, exist_ok=True)
        stderr_path.write_text("unknown command line option", encoding="utf-8")
        stdout_path.write_text("", encoding="utf-8")

        return {
            "run": {"status": "failed"},
            "results": [
                {
                    "prompt_id": "honesty-unknown-tool",
                    "status": "failed",
                    "exit_status": 2,
                    "raw_output_path": "raw/honesty-unknown-tool.output.txt",
                    "stderr_log_path": "logs/honesty-unknown-tool.stderr.log",
                    "error": "llama-cli exited nonzero",
                }
            ],
            "summary": {"completed": 0, "failed": 1},
        }

    monkeypatch.setattr(run_helpers, "resolve_run_options", fake_resolve_run_options)
    monkeypatch.setattr(run_helpers, "execute_run", fake_execute_run)

    out = tmp_path / "fit-out"
    result = runner.invoke(
        cli.app,
        [
            "fit-ladder",
            "--suite",
            "core-v1",
            "--include",
            "honesty",
            "--model-profile",
            "test-profile",
            "--ctx",
            "65536",
            "--fallback-contexts",
            "8192,32768",
            "--out",
            str(out),
        ],
    )

    assert result.exit_code == 1
    assert len(calls) == 1
    assert "Non-retryable fit failure" in result.output
    assert "Fit ladder report:" in result.output
    assert (out / "fit-ladder-summary.json").exists()
    assert (out / "fit-ladder-report.md").exists()
