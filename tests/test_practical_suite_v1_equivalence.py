from pathlib import Path


import pytest
import llmgauge.core.public_export as public_export
from llmgauge.commands.run_helpers import build_combined_prompt, load_system_prompt
from llmgauge.core.suite import load_suite


SUITE_DIR = Path("suites/wumbolabs-practical-use-v1")
PUBLIC_EXPORT_DIRS = (
    Path("docs/evidence/practical/grug-12b-q4-k-m/public-export"),
    Path("docs/evidence/practical/qwen3-6-35b-a3b-ud-iq2-m/public-export"),
)
EXPECTED_PROMPT_IDS = [
    "linux/arch-nvidia-update-advice",
    "coding/python-log-parser",
    "docker/compose-review",
    "honesty/unknown-package",
    "summarization/technical-run-summary",
    "local-llm/consumer-gpu-advice",
]


def test_historical_practical_suite_public_derivatives_are_exact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(public_export, "_LOCAL_HOSTNAME", "")
    monkeypatch.setattr(public_export, "_LOCAL_USERNAMES", ())
    suite = load_suite(SUITE_DIR)

    assert suite["suite_id"] == "wumbolabs-practical-use-v1"
    assert suite["suite_version"] == "0.1.0"
    assert [prompt["id"] for prompt in suite["prompts"]] == EXPECTED_PROMPT_IDS

    for prompt in suite["prompts"]:
        prompt_id = prompt["id"]
        source_text = (SUITE_DIR / prompt["file"]).read_text(encoding="utf-8")
        rendered = build_combined_prompt(load_system_prompt(), source_text.strip())
        categories: set[str] = set()
        sanitized = public_export._sanitize_text(rendered, categories).encode("utf-8")

        for export_dir in PUBLIC_EXPORT_DIRS:
            public_prompt = export_dir / "raw" / f"{prompt_id}.prompt.md"
            assert sanitized == public_prompt.read_bytes()

        if prompt_id == "docker/compose-review":
            assert rendered.encode("utf-8") != sanitized
            assert categories == {"absolute_path"}
        else:
            assert rendered.encode("utf-8") == sanitized
            assert categories == set()
