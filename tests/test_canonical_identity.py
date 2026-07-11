from llmgauge.core.identity import (
    canonical_sha256,
    prompt_definition_identity,
    suite_definition_identity,
)


def test_canonical_hash_is_stable_across_mapping_key_order() -> None:
    left = {"suite": {"id": "demo", "version": "1"}, "values": [1, 2]}
    right = {"values": [1, 2], "suite": {"version": "1", "id": "demo"}}

    assert canonical_sha256(left) == canonical_sha256(right)


def test_canonical_hash_changes_when_relevant_content_changes() -> None:
    base = {"prompt": "answer safely", "max_tokens": 128}
    changed = {"prompt": "answer safely and cite uncertainty", "max_tokens": 128}

    assert canonical_sha256(base) != canonical_sha256(changed)


def test_prompt_identity_includes_rubric_and_output_contract() -> None:
    prompt = {
        "id": "honesty/fake-package",
        "title": "Fake Package",
        "category": "honesty",
        "file": "prompts/honesty/fake-package.md",
    }
    base = prompt_definition_identity(
        prompt=prompt,
        prompt_text="Do not invent package facts.",
        system_text="Be conservative.",
        output_contract={"format": "markdown"},
        scoring_rubric={"rubric_id": "default", "dimensions": ["honesty"]},
    )

    contract_changed = prompt_definition_identity(
        prompt=prompt,
        prompt_text="Do not invent package facts.",
        system_text="Be conservative.",
        output_contract={"format": "json"},
        scoring_rubric={"rubric_id": "default", "dimensions": ["honesty"]},
    )
    rubric_changed = prompt_definition_identity(
        prompt=prompt,
        prompt_text="Do not invent package facts.",
        system_text="Be conservative.",
        output_contract={"format": "markdown"},
        scoring_rubric={"rubric_id": "default", "dimensions": ["safety"]},
    )

    assert base != contract_changed
    assert base != rubric_changed


def test_suite_identity_includes_prompt_definitions() -> None:
    suite = {
        "schema_version": "llmgauge.suite.v0",
        "suite_id": "demo-suite",
        "suite_version": "0.1.0",
        "prompts": [{"id": "a", "file": "a.md"}],
    }

    first = suite_definition_identity(
        suite=suite,
        prompt_identities={"a": "0" * 64},
    )
    second = suite_definition_identity(
        suite=suite,
        prompt_identities={"a": "1" * 64},
    )

    assert first != second


def test_irrelevant_yaml_mapping_order_does_not_alter_identities() -> None:
    prompt_left = {
        "id": "a",
        "title": "Prompt A",
        "metadata": {"purpose": "test", "tier": 2},
    }
    prompt_right = {
        "metadata": {"tier": 2, "purpose": "test"},
        "title": "Prompt A",
        "id": "a",
    }

    assert prompt_definition_identity(
        prompt=prompt_left,
        prompt_text="same prompt",
        output_contract={"required": ["answer", "evidence"]},
    ) == prompt_definition_identity(
        prompt=prompt_right,
        prompt_text="same prompt",
        output_contract={"required": ["answer", "evidence"]},
    )
