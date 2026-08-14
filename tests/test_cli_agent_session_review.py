from __future__ import annotations

import json
import re
from pathlib import Path

from typer.testing import CliRunner

from agent_harness_fixtures import write_synthetic_omp_session
from llmgauge.cli import app
from llmgauge.core.agent_harness import import_agent_harness_session

runner = CliRunner()
_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def normalized(value: str) -> str:
    return " ".join(_ANSI_ESCAPE_RE.sub("", value).split())


def imported(tmp_path: Path) -> Path:
    source = write_synthetic_omp_session(tmp_path / "source")
    result = tmp_path / "result"
    import_agent_harness_session(source.source, result)
    return result


def test_agent_session_review_cli_workflow(tmp_path: Path) -> None:
    result_dir = imported(tmp_path)
    help_result = runner.invoke(app, ["agent-session-review", "--help"])
    assert help_result.exit_code == 0
    assert "--report" in normalized(help_result.output)
    init = runner.invoke(app, ["agent-session-review", str(result_dir), "--init"])
    assert init.exit_code == 0
    template = result_dir / "agent-harness/review/agent-session-review.template.json"
    check = runner.invoke(
        app,
        ["agent-session-review", str(result_dir), "--review", str(template), "--check"],
    )
    assert check.exit_code != 0  # Templates are never candidate review input.
    review = json.loads(template.read_text(encoding="utf-8"))
    review.update(
        {
            "reviewer": {"reviewer_id": "reviewer-1"},
            "reviewed_at_utc": "2026-08-13T00:00:00Z",
        }
    )
    review["scoreability"] = {
        "value": "scoreable",
        "required_evidence_basis": [
            {
                "basis_id": "terminal",
                "target": "task_completion_evidence",
                "state": "sufficient",
                "rationale": "Terminal is contained.",
                "source_references": [
                    {
                        "reference_type": "source_terminal",
                        "reference_id": "source_terminal",
                    }
                ],
                "applicability_mismatch": None,
            }
        ],
    }
    review["review_state"] = "awaiting_review"
    candidate = tmp_path / "review.json"
    candidate.write_text(json.dumps(review), encoding="utf-8")
    assert (
        runner.invoke(
            app,
            [
                "agent-session-review",
                str(result_dir),
                "--review",
                str(candidate),
                "--check",
            ],
        ).exit_code
        == 0
    )
    assert (
        runner.invoke(
            app,
            [
                "agent-session-review",
                str(result_dir),
                "--review",
                str(candidate),
                "--apply",
            ],
        ).exit_code
        == 0
    )
    assert (
        runner.invoke(
            app, ["agent-session-review", str(result_dir), "--report"]
        ).exit_code
        == 0
    )


def test_agent_session_review_rejects_invalid_combinations_and_native(
    tmp_path: Path,
) -> None:
    result_dir = imported(tmp_path)
    invalid = runner.invoke(
        app, ["agent-session-review", str(result_dir), "--init", "--report"]
    )
    assert invalid.exit_code != 0
    native = tmp_path / "native"
    native.mkdir()
    (native / "llmgauge-result.json").write_text("{}", encoding="utf-8")
    rejected = runner.invoke(app, ["agent-session-review", str(native), "--init"])
    assert rejected.exit_code != 0
