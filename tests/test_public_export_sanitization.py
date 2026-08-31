"""Synthetic regression for the public-export sanitizer contract.

This test deliberately avoids any real model-run evidence. It checks that the
public-export sanitizer rewrites absolute paths while leaving otherwise clean
synthetic prompt text intact.
"""

import json

import pytest

import llmgauge.core.public_export as public_export
from llmgauge.commands.run_helpers import build_combined_prompt, load_system_prompt


def test_sanitize_text_rewrites_injected_absolute_path() -> None:
    rendered = build_combined_prompt(
        load_system_prompt(),
        "Review this compose file at /srv/operator-stack/docker-compose.yml.",
    )

    categories: set[str] = set()
    sanitized = public_export._sanitize_text(rendered, categories)

    assert rendered != sanitized
    assert "/srv/operator-stack" not in sanitized
    assert "REDACTED_ABSOLUTE_PATH" in sanitized


def test_sanitize_text_preserves_exact_api_routes_without_path_bypass() -> None:
    text = (
        "GET /version\n"
        "GET /v1/models\n"
        "POST /v1/chat/completions\n"
        "Report route (/version): healthy\n"
        "private /home/test/private-model /tmp/private-result "
        "/mnt/data/private /var/lib/private /usr/local/private-model "
        "C:\\Users\\test\\private-model\n"
        "adversarial /version/../../home/user/secret\n"
    )

    categories: set[str] = set()
    sanitized = public_export._sanitize_text(text, categories)

    assert "/version\n" in sanitized
    assert "/v1/models\n" in sanitized
    assert "/v1/chat/completions\n" in sanitized
    assert "(/version):" in sanitized
    assert "/home/test/private-model" not in sanitized
    assert "/tmp/private-result" not in sanitized
    assert "/mnt/data/private" not in sanitized
    assert "/var/lib/private" not in sanitized
    assert "/usr/local/private-model" not in sanitized
    assert "C:\\Users\\test\\private-model" not in sanitized
    assert "/version/../../home/user/secret" not in sanitized
    assert "REDACTED_ABSOLUTE_PATH" in sanitized


@pytest.mark.parametrize(
    "payload",
    [
        {
            "runtime_neutral_metrics": {
                "measurements": [
                    {
                        "metrics": [
                            {
                                "metric_id": ("llmgauge.metric.v1.time_to_first_token"),
                                "value": 7.654321,
                                "evidence_refs": [
                                    "request/p1.stream.json#/first_token/elapsed_seconds"
                                ],
                            }
                        ]
                    }
                ]
            }
        },
        {"results": [{"metrics": {"time_to_first_token_seconds": 7.654321}}]},
        {
            "runtime_neutral_metrics": {
                "measurements": [
                    {
                        "metrics": [
                            {
                                "metric_id": ("llmgauge.metric.v1.time_to_first_token"),
                                "value": 7.654321,
                            }
                        ]
                    }
                ]
            },
            "results": [
                {
                    "stream_evidence_path": "request/p1.stream.json",
                    "metrics": {
                        "time_to_first_token_seconds": 7.654321,
                        "first_token_channel": "content",
                    },
                }
            ],
        },
        {
            "request_evidence": {
                "stream_evidence_path": "request/p1.stream.json",
                "first_token": {"elapsed_seconds": 7.654321},
            }
        },
    ],
    ids=["area4", "per-prompt", "both", "evidence-ref"],
)
def test_sanitize_public_ttft_removes_every_v1_projection(payload: object) -> None:
    categories: set[str] = set()

    sanitized = public_export._sanitize_public_ttft(payload, categories)
    serialized = json.dumps(sanitized)

    assert "7.654321" not in serialized
    assert "time_to_first_token" not in serialized
    assert "stream_evidence_path" not in serialized
    assert "first_token" not in serialized
    assert "area4_ttft_omitted" in categories


def test_sanitize_public_ttft_leaves_non_ttft_data_and_manifest_state_unchanged() -> (
    None
):
    payload = {"results": [{"metrics": {"request_wall_time_seconds": 1.25}}]}
    categories: set[str] = set()

    sanitized = public_export._sanitize_public_ttft(payload, categories)

    assert sanitized == payload
    assert "area4_ttft_omitted" not in categories


def test_sanitize_structured_omits_reasoning_but_retains_final_content() -> None:
    categories: set[str] = set()

    sanitized = public_export._sanitize_structured(
        {
            "reasoning": "PRIVATE_STRUCTURED_REASONING",
            "content": "authoritative final answer",
        },
        categories,
    )

    assert sanitized == {"content": "authoritative final answer"}
    assert "structured_reasoning_omitted" in categories


def test_sanitize_endpoint_identity_omits_private_port() -> None:
    categories: set[str] = set()

    sanitized = public_export._sanitize_endpoint_identity(
        {
            "scheme": "http",
            "loopback_class": "ipv4_loopback",
            "host": "127.0.0.1",
            "port": 18081,
        },
        categories,
    )

    assert sanitized == {
        "scheme": "http",
        "loopback_class": "ipv4_loopback",
    }
    assert "vllm_endpoint_field_omitted" in categories


def test_sanitize_text_on_clean_synthetic_prompts_is_benign_or_absolute_path_only() -> (
    None
):
    """Clean synthetic prompts stay unchanged except ordinary absolute paths,
    which public export must rewrite."""
    synthetic_prompts = [
        "Summarize this example run log in five bullet points.",
        "Explain how you would review this example compose file for service "
        "ordering problems.",
    ]
    for prompt_text in synthetic_prompts:
        rendered = build_combined_prompt(load_system_prompt(), prompt_text)

        categories: set[str] = set()
        sanitized = public_export._sanitize_text(rendered, categories)

        assert categories <= {"absolute_path"}
        assert rendered != sanitized or categories == set()
        if rendered != sanitized:
            assert "REDACTED_ABSOLUTE_PATH" in sanitized
