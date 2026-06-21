from llmgauge.core.output_cleaning import clean_llama_output


def test_clean_llama_output_strips_banner_echo_and_metrics() -> None:
    raw = """
Loading model...


▄▄ ▄▄
build      : b9672
model      : test.gguf
modalities : text

available commands:
  /exit or Ctrl+C     stop or exit

> SYSTEM:

You are a conservative local systems assistant.

USER:

# Agent Backend Test

Task:

Explain ... (truncated)

I would first verify that the command exists before running it.

[ Prompt: 123.4 t/s | Generation: 56.7 t/s ]

Exiting...
"""

    assert clean_llama_output(raw) == (
        "I would first verify that the command exists before running it.\n"
    )


def test_clean_llama_output_preserves_plain_model_output() -> None:
    raw = "First line\n\nSecond line\n"

    assert clean_llama_output(raw) == "First line\n\nSecond line\n"


def test_clean_llama_output_strips_trailing_metrics_only() -> None:
    raw = "Answer text\n\n[ Prompt: 100.0 t/s | Generation: 50.0 t/s ]\n\nExiting...\n"

    assert clean_llama_output(raw) == "Answer text\n"
