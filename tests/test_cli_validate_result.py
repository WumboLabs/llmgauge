from pathlib import Path

import json
from typer.testing import CliRunner

from llmgauge.cli import app


runner = CliRunner()


def test_validate_result_cli_explains_artifact_only_validation(tmp_path: Path) -> None:
    result_dir = tmp_path / "result"
    (result_dir / "raw").mkdir(parents=True)
    (result_dir / "logs").mkdir(parents=True)
    result_data = {
        "schema_version": "llmgauge.result.v0",
        "llmgauge_version": "0.1.0",
        "run": {"run_id": "test-run", "status": "completed"},
        "model": {
            "model_id": "test-model",
            "model_path": "redacted",
            "model_path_policy": "redacted",
        },
        "runtime": {"backend": "llama.cpp"},
        "suite": {"suite_id": "core-v1", "prompt_count": 1},
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
                "metrics": {"prompt_eval_tps": 100.0, "generation_tps": 50.0},
                "score": None,
            }
        ],
    }
    (result_dir / "llmgauge-result.json").write_text(
        json.dumps(result_data, indent=2) + "\n",
        encoding="utf-8",
    )
    (result_dir / "raw" / "honesty-unknown-tool.prompt.md").write_text(
        "prompt\n",
        encoding="utf-8",
    )
    (result_dir / "raw" / "honesty-unknown-tool.output.txt").write_text(
        "output\n",
        encoding="utf-8",
    )
    (result_dir / "logs" / "honesty-unknown-tool.stderr.log").write_text(
        "stderr\n",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["validate-result", str(result_dir)])

    assert result.exit_code == 0
    assert "Artifact validation passed" in result.output
    assert "does not prove answer quality" in result.output
