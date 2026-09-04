"""M2 run-fingerprint v6, validator recomputation, export, and report tests."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from test_run_fingerprint import _write_fingerprintable_run

from llmgauge.core.artifacts import write_json
from llmgauge.core.checkpoint_provenance import (
    CHECKPOINT_MANIFEST_SCHEMA_VERSION,
    CHECKPOINT_PROVENANCE_KIND,
    checkpoint_manifest_fingerprint,
    checkpoint_tokenizer_identity_fingerprint,
    collect_checkpoint_provenance,
)
from llmgauge.core.identity import public_model_fingerprint
from llmgauge.core.result_validation import validate_result_dir
from llmgauge.core.run_fingerprint import (
    RUN_FINGERPRINT_FIELD,
    RUN_FINGERPRINT_PAYLOAD_VERSION,
    RUN_FINGERPRINT_PAYLOAD_VERSION_V6,
    RUN_FINGERPRINT_SCHEMA_VERSION,
    RUN_FINGERPRINT_SCHEMA_VERSION_V3,
    RUN_FINGERPRINT_SCHEMA_VERSION_V4,
    RUN_FINGERPRINT_SCHEMA_VERSION_V5,
    RUN_FINGERPRINT_SCHEMA_VERSION_V6,
    FingerprintUnavailable,
    attach_run_fingerprint,
    build_run_fingerprint_metadata,
    build_run_fingerprint_payload,
    canonical_payload_bytes,
    run_fingerprint_value,
    verify_run_fingerprint,
)

CONFIG = b'{"architectures": ["TinyForCausalLM"], "model_type": "tiny"}'


def _write_checkpoint(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "config.json").write_bytes(CONFIG)
    (root / "model.safetensors").write_bytes(b"weights-bytes")
    (root / "tokenizer.json").write_bytes(b'{"tokenizer": "tiny"}')
    (root / "tokenizer_config.json").write_bytes(
        b'{"chat_template": "hello {{ message }}"}'
    )
    return root


def _directory_provenance(tmp_path: Path) -> dict[str, Any]:
    root = _write_checkpoint(tmp_path / "ckpt")
    return collect_checkpoint_provenance(
        root, source_type="model_profile", cache_path=tmp_path / "cache.json"
    )


def _write_directory_run(
    tmp_path: Path,
    provenance: dict[str, Any],
    *,
    run_name: str = "ckpt-run",
) -> tuple[Path, dict[str, Any]]:
    result_dir, result = _write_fingerprintable_run(tmp_path, run_name=run_name)
    result["model"]["provenance"] = provenance
    result.pop(RUN_FINGERPRINT_FIELD, None)
    write_json(result_dir / "llmgauge-result.json", result)
    return result_dir, result


def _persist(result_dir: Path, result: dict[str, Any]) -> None:
    write_json(result_dir / "llmgauge-result.json", result)


# --- frozen v0-v5 compatibility ----------------------------------------------

# Goldens captured from the pre-M2 implementation at baseline 99f00e2.
FROZEN_V0_VALUE = (
    "sha256:ba342b6993714a805debd86c8357eb7cabba146d6734814fa5d353f23cfd36ae"
)
FROZEN_V3_VALUE = (
    "sha256:678817a825736dc07b77920007bfdd4d2c2f784c5d7ecbd4b81fc59662faf33a"
)
FROZEN_V4_VALUE = (
    "sha256:9116dbbd42eba9ff7e20786ea58ffa56c8d2d8a67aa3e9a20dd9b0ea23cf944f"
)
FROZEN_V5_VALUE = (
    "sha256:c96aabeda1c520eaa747c757fac4c0c44a8344a406792ecfc943d6d582cb861b"
)


def _controlled_runtime(result: dict[str, Any]) -> dict[str, Any]:
    controlled = copy.deepcopy(result)
    controlled["runtime"].update(
        {
            "fit": "off",
            "fit_state": "explicit",
            "reasoning_preserve": False,
            "reasoning_preserve_state": "explicit",
            "spec_type": "none",
            "spec_type_state": "explicit",
        }
    )
    return controlled


def test_existing_gguf_fingerprints_are_byte_frozen(tmp_path: Path) -> None:
    result_dir, result = _write_fingerprintable_run(tmp_path)

    v0 = build_run_fingerprint_metadata(result_dir, result)
    assert v0["schema_version"] == RUN_FINGERPRINT_SCHEMA_VERSION
    assert v0["value"] == FROZEN_V0_VALUE
    payload = build_run_fingerprint_payload(result_dir, result)
    assert payload["schema_version"] == RUN_FINGERPRINT_PAYLOAD_VERSION
    assert hashlib.sha256(
        canonical_payload_bytes(payload)
    ).hexdigest() == FROZEN_V0_VALUE.removeprefix("sha256:")

    extended = copy.deepcopy(result)
    extended["runtime"].update(
        {
            "top_k": 40,
            "top_k_state": "explicit",
            "min_p": 0.05,
            "min_p_state": "explicit",
            "seed": 7,
            "seed_state": "explicit",
            "parallel_sequences": 1,
            "cache_type_k": "f16",
            "cache_type_k_state": "explicit",
            "cache_type_v": "f16",
            "cache_type_v_state": "explicit",
            "reasoning_effort": "high",
            "reasoning_effort_state": "explicit",
            "reasoning_budget": -1,
            "reasoning_budget_state": "explicit",
        }
    )
    v3 = build_run_fingerprint_metadata(result_dir, extended)
    assert v3["schema_version"] == RUN_FINGERPRINT_SCHEMA_VERSION_V3
    assert v3["value"] == FROZEN_V3_VALUE

    controlled = _controlled_runtime(result)
    v4 = build_run_fingerprint_metadata(result_dir, controlled)
    assert v4["schema_version"] == RUN_FINGERPRINT_SCHEMA_VERSION_V4
    assert v4["value"] == FROZEN_V4_VALUE

    profiled = copy.deepcopy(controlled)
    profiled["runtime"]["profile"] = {
        "profile_id": "p",
        "profile_version": "1",
        "canonical_settings_sha256": "e" * 64,
    }
    v5 = build_run_fingerprint_metadata(result_dir, profiled)
    assert v5["schema_version"] == RUN_FINGERPRINT_SCHEMA_VERSION_V5
    assert v5["value"] == FROZEN_V5_VALUE


def test_gguf_results_do_not_start_emitting_v6(tmp_path: Path) -> None:
    result_dir, result = _write_fingerprintable_run(tmp_path)
    fingerprint = build_run_fingerprint_metadata(result_dir, result)
    assert fingerprint["schema_version"] != RUN_FINGERPRINT_SCHEMA_VERSION_V6
    assert (
        verify_run_fingerprint(
            result_dir, {**result, RUN_FINGERPRINT_FIELD: fingerprint}
        )
        == []
    )


def test_eligible_directory_result_produces_v6_fingerprint(tmp_path: Path) -> None:
    provenance = _directory_provenance(tmp_path)
    assert provenance["fingerprint_eligible"] is True
    result_dir, result = _write_directory_run(tmp_path, provenance)

    fingerprint = build_run_fingerprint_metadata(result_dir, result)
    assert fingerprint["schema_version"] == RUN_FINGERPRINT_SCHEMA_VERSION_V6
    assert fingerprint["algorithm"] == "sha256"
    assert fingerprint["value"].startswith("sha256:")
    assert len(fingerprint["value"]) == len("sha256:") + 64

    payload = build_run_fingerprint_payload(result_dir, result)
    assert payload["schema_version"] == RUN_FINGERPRINT_PAYLOAD_VERSION_V6
    model_identity = payload["model"]
    assert (
        model_identity["provenance"]["manifest_sha256"]
        == (provenance["manifest_sha256"])
    )
    assert model_identity["provenance"]["manifest_schema"] == (
        CHECKPOINT_MANIFEST_SCHEMA_VERSION
    )
    assert model_identity["manifest_entries"] == provenance["manifest"]
    # The cryptographic identity is the manifest, not the local directory path.
    assert str(tmp_path) not in json.dumps(payload)

    # Existing GGUF results keep their existing fingerprint version.
    gguf_dir, gguf_result = _write_fingerprintable_run(tmp_path / "gguf")
    assert (
        build_run_fingerprint_metadata(gguf_dir, gguf_result)["schema_version"]
        == RUN_FINGERPRINT_SCHEMA_VERSION
    )


def test_v6_verifies_from_persisted_evidence_without_checkpoint(tmp_path) -> None:
    provenance = _directory_provenance(tmp_path)
    result_dir, result = _write_directory_run(tmp_path, provenance)
    attach_run_fingerprint(result_dir, result)
    assert result[RUN_FINGERPRINT_FIELD]["schema_version"] == (
        RUN_FINGERPRINT_SCHEMA_VERSION_V6
    )
    _persist(result_dir, result)
    # Delete the original checkpoint directory: validation must still pass
    # because it recomputes from persisted manifest evidence only.
    import shutil

    from llmgauge.core.result_validation import load_result_json

    shutil.rmtree(tmp_path / "ckpt")
    reloaded = load_result_json(result_dir)
    assert verify_run_fingerprint(result_dir, reloaded) == []
    assert validate_result_dir(result_dir) == []


def test_v6_manifest_mutation_is_detected(tmp_path) -> None:
    provenance = _directory_provenance(tmp_path)
    result_dir, result = _write_directory_run(tmp_path, provenance)
    attach_run_fingerprint(result_dir, result)

    for mutate in (
        lambda p: p["manifest"][0].__setitem__("path", "renamed.json"),
        lambda p: p["manifest"][0].__setitem__("size", 9999),
        lambda p: p["manifest"][0].__setitem__("sha256", "f" * 64),
        lambda p: p.__setitem__("manifest_sha256", "0" * 64),
        lambda p: p.__setitem__("public_fingerprint", "sha256:0000000000000000"),
        lambda p: p["tokenizer_identity"].__setitem__("sha256", "1" * 64),
    ):
        mutated = copy.deepcopy(result)
        mutate(mutated["model"]["provenance"])
        errors = verify_run_fingerprint(result_dir, mutated)
        assert errors, "mutated directory provenance must fail verification"


def test_ineligible_directory_identity_refuses_fingerprint(tmp_path) -> None:
    provenance = _directory_provenance(tmp_path)
    provenance["fingerprint_eligible"] = False
    provenance["fingerprint_ineligible_reason"] = "tokenizer identity is incomplete"
    result_dir, result = _write_directory_run(tmp_path, provenance)

    with pytest.raises(FingerprintUnavailable) as exc:
        run_fingerprint_value(result_dir, result)
    assert "not fingerprint eligible" in str(exc.value)
    assert attach_run_fingerprint(result_dir, result) is None


def test_fingerprint_never_fabricated_from_names(tmp_path) -> None:
    # An unavailable directory record has no manifest: no identity is invented.
    result_dir, result = _write_fingerprintable_run(tmp_path)
    result["model"]["provenance"] = {
        "source_type": "model_profile",
        "provenance_kind": CHECKPOINT_PROVENANCE_KIND,
        "status": "unavailable",
        "manifest_schema": CHECKPOINT_MANIFEST_SCHEMA_VERSION,
        "manifest": None,
        "manifest_sha256": None,
        "public_fingerprint": None,
        "fingerprint_eligible": False,
        "fingerprint_ineligible_reason": "config.json is missing",
    }
    with pytest.raises(FingerprintUnavailable):
        run_fingerprint_value(result_dir, result)
    assert attach_run_fingerprint(result_dir, result) is None


def test_v6_requires_admitted_manifest_schema(tmp_path) -> None:
    provenance = _directory_provenance(tmp_path)
    provenance["manifest_schema"] = "llmgauge.checkpoint_directory_manifest.v99"
    result_dir, result = _write_directory_run(tmp_path, provenance)
    with pytest.raises(FingerprintUnavailable) as exc:
        run_fingerprint_value(result_dir, result)
    assert "manifest schema" in str(exc.value)


def test_v6_rejects_manifest_hash_incoherence(tmp_path) -> None:
    provenance = _directory_provenance(tmp_path)
    # Stored manifest hash no longer matches the persisted entries.
    provenance["manifest"][1]["size"] += 1
    result_dir, result = _write_directory_run(tmp_path, provenance)
    with pytest.raises(FingerprintUnavailable) as exc:
        run_fingerprint_value(result_dir, result)
    assert "does not match" in str(exc.value)


def test_v6_rejects_tokenizer_hash_incoherence(tmp_path) -> None:
    provenance = _directory_provenance(tmp_path)
    provenance["tokenizer_identity"]["sha256"] = "9" * 64
    result_dir, result = _write_directory_run(tmp_path, provenance)
    with pytest.raises(FingerprintUnavailable) as exc:
        run_fingerprint_value(result_dir, result)
    assert "tokenizer" in str(exc.value)


def test_v6_rejects_template_public_fingerprint_incoherence(tmp_path) -> None:
    provenance = _directory_provenance(tmp_path)
    provenance["chat_template_identity"]["public_fingerprint"] = (
        "sha256:ffffffffffffffff"
    )
    result_dir, result = _write_directory_run(tmp_path, provenance)
    with pytest.raises(FingerprintUnavailable) as exc:
        run_fingerprint_value(result_dir, result)
    assert "chat-template" in str(exc.value)


def test_v6_identity_is_independent_of_descriptive_fields(tmp_path) -> None:
    provenance = _directory_provenance(tmp_path)
    result_dir, result = _write_directory_run(tmp_path, provenance)
    baseline = run_fingerprint_value(result_dir, result)

    descriptive = copy.deepcopy(result)
    descriptive["model"]["provenance"]["repository_id"] = "Other/Name"
    descriptive["model"]["provenance"]["revision"] = "a" * 40
    # Descriptive metadata is part of the payload identity, so this changes the
    # fingerprint; but the cryptographic checkpoint manifest identity does not:
    # the manifest_sha256 stays equal.
    assert run_fingerprint_value(result_dir, descriptive) != baseline
    assert (
        descriptive["model"]["provenance"]["manifest_sha256"]
        == (provenance["manifest_sha256"])
    )


# --- validator recomputation -------------------------------------------------


def test_validator_recomputes_manifest_public_and_tokenizer(tmp_path) -> None:
    provenance = _directory_provenance(tmp_path)
    result_dir, result = _write_directory_run(tmp_path, provenance)
    attach_run_fingerprint(result_dir, result)
    _persist(result_dir, result)
    assert validate_result_dir(result_dir) == []

    # Independent recomputation from the persisted manifest entries.
    entries = provenance["manifest"]
    assert provenance["manifest_sha256"] == checkpoint_manifest_fingerprint(entries)
    assert provenance["public_fingerprint"] == public_model_fingerprint(
        provenance["manifest_sha256"]
    )
    by_path = {entry["path"]: entry for entry in entries}
    tokenizer_entries = [
        by_path[name] for name in provenance["tokenizer_identity"]["files"]
    ]
    assert provenance["tokenizer_identity"]["sha256"] == (
        checkpoint_tokenizer_identity_fingerprint(tokenizer_entries)
    )


@pytest.mark.parametrize(
    ("mutate", "fragment"),
    [
        (
            lambda p: p["manifest"][2].__setitem__("sha256", "e" * 64),
            "manifest_sha256 does not match",
        ),
        (
            lambda p: p["manifest"][2].__setitem__("size", 4242),
            "manifest_sha256 does not match",
        ),
        (
            lambda p: p["manifest"].__setitem__(
                0, {**p["manifest"][0], "path": "zzz-config.json"}
            ),
            "sorted by path",
        ),
        (
            lambda p: p["manifest"].append(dict(p["manifest"][0])),
            "duplicates",
        ),
        (
            lambda p: p["manifest"][0].__setitem__("path", "/etc/passwd"),
            "normalized relative path",
        ),
        (
            lambda p: p["manifest"][0].__setitem__("path", "../escape"),
            "normalized relative path",
        ),
        (
            lambda p: p["manifest"][0].__setitem__("sha256", "A" * 64),
            "lowercase hex",
        ),
        (
            lambda p: p["manifest"][0].__setitem__("size", -5),
            "non-negative integer",
        ),
        (
            lambda p: p.__setitem__("manifest_sha256", "0" * 64),
            "does not match the recomputed canonical manifest",
        ),
        (
            lambda p: p.__setitem__("public_fingerprint", "sha256:0000000000000000"),
            "public_fingerprint does not match",
        ),
        (
            lambda p: p["tokenizer_identity"].__setitem__("sha256", "1" * 64),
            "tokenizer_identity.sha256 does not match",
        ),
        (
            lambda p: p["tokenizer_identity"].__setitem__("files", ["not-in-manifest"]),
            "must list manifest entry paths",
        ),
        (
            lambda p: p.__setitem__("status", "mostly-available"),
            "status must be available",
        ),
        (
            lambda p: p.__setitem__("entry_count", 99),
            "entry_count must match",
        ),
        (
            lambda p: p.__setitem__("fingerprint_eligible", False)
            or p.__setitem__("fingerprint_ineligible_reason", "manual mutation"),
            "available status must be fingerprint eligible",
        ),
        (
            lambda p: p["chat_template_identity"].__setitem__("status", "guessed"),
            "chat_template_identity.status",
        ),
        (
            lambda p: p["checkpoint_quantization"].__setitem__("status", "definitely-awq"),
            "checkpoint_quantization.status",
        ),
        (
            lambda p: p["checkpoint_quantization"].__setitem__("sources", "config.json"),
            "sources must be a list",
        ),
    ],
)
def test_validator_rejects_mutated_directory_evidence(
    tmp_path, mutate, fragment
) -> None:
    provenance = _directory_provenance(tmp_path)
    result_dir, result = _write_directory_run(tmp_path, provenance)
    attach_run_fingerprint(result_dir, result)
    mutate(result["model"]["provenance"])
    _persist(result_dir, result)

    errors = validate_result_dir(result_dir)
    assert any(fragment in error for error in errors), errors


def test_validator_accepts_partial_directory_provenance(tmp_path) -> None:
    root = _write_checkpoint(tmp_path / "ckpt")
    (root / "tokenizer_config.json").write_bytes(b'{"chat_template": {"a": "x", "b": "y"}}')
    provenance = collect_checkpoint_provenance(
        root, source_type="model_profile", cache_path=tmp_path / "cache.json"
    )
    assert provenance["status"] == "partial"
    assert provenance["fingerprint_eligible"] is False
    result_dir, result = _write_directory_run(tmp_path, provenance)
    assert attach_run_fingerprint(result_dir, result) is None
    _persist(result_dir, result)
    assert validate_result_dir(result_dir) == []


def test_historical_results_without_directory_provenance_remain_valid(
    tmp_path,
) -> None:
    result_dir, result = _write_fingerprintable_run(tmp_path)
    assert validate_result_dir(result_dir) == []


# --- public export ------------------------------------------------------------


def _write_directory_export_run(tmp_path) -> tuple[Path, dict[str, Any]]:
    provenance = _directory_provenance(tmp_path)
    result_dir, result = _write_directory_run(tmp_path, provenance)
    attach_run_fingerprint(result_dir, result)
    _persist(result_dir, result)
    (tmp_path / "ckpt" / "README.md").touch()  # unrelated file, no effect
    return result_dir, provenance


def test_public_export_strips_private_checkpoint_evidence(tmp_path) -> None:
    from llmgauge.core.public_export import export_public_run

    result_dir, provenance = _write_directory_export_run(tmp_path)
    output_dir = tmp_path / "public"
    manifest = export_public_run(result_dir, output_dir)

    exported = json.loads(
        (output_dir / "llmgauge-result.json").read_text(encoding="utf-8")
    )
    exported_json = json.dumps(exported)

    # Private evidence withheld.
    assert "provenance" not in exported["model"]
    assert "manifest_sha256" not in exported_json
    assert "checkpoint_identity" in exported["model"]
    identity = exported["model"]["checkpoint_identity"]
    assert identity["public_fingerprint"] == provenance["public_fingerprint"]
    assert identity["tokenizer_identity"]["public_fingerprint"] == (
        provenance["tokenizer_identity"]["public_fingerprint"]
    )
    assert identity["chat_template_identity"]["public_fingerprint"] == (
        provenance["chat_template_identity"]["public_fingerprint"]
    )
    assert identity["status"] == provenance["status"]
    assert identity["effective_quantization_status"] == "unavailable"
    assert "manifest" not in identity
    assert "manifest_sha256" not in identity
    assert "private_checkpoint_manifest_omitted" in manifest["redaction_categories"]

    # Negative privacy search: no full 64-hex digests, no local paths, no
    # manifest filenames, no cache paths.
    import re

    assert not re.search(r"(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])", exported_json)
    assert "/home/" not in exported_json
    assert "/tmp/" not in exported_json
    assert str(tmp_path) not in exported_json
    for entry in provenance["manifest"]:
        assert entry["sha256"] not in exported_json
    assert "tokenizer.json" not in json.dumps(identity)

    # The public derivative validates.
    from llmgauge.core.result_validation import validate_result_dir

    assert validate_result_dir(output_dir) == []

    # The private source is unmodified.
    source = json.loads(
        (result_dir / "llmgauge-result.json").read_text(encoding="utf-8")
    )
    assert source["model"]["provenance"]["manifest_sha256"] == (
        provenance["manifest_sha256"]
    )


def test_public_export_symlink_blob_paths_are_absent(tmp_path) -> None:
    from llmgauge.core.public_export import export_public_run

    blobs = tmp_path / "hf-cache" / "blobs"
    blobs.mkdir(parents=True)
    root = tmp_path / "ckpt"
    root.mkdir()
    files = {
        "config.json": CONFIG,
        "model.safetensors": b"weights-bytes",
        "tokenizer.json": b'{"tokenizer": "tiny"}',
        "tokenizer_config.json": b'{"chat_template": "t"}',
    }
    for name, data in files.items():
        blob = blobs / hashlib.sha256(name.encode("utf-8")).hexdigest()
        blob.write_bytes(data)
        (root / name).symlink_to(blob)
    provenance = collect_checkpoint_provenance(
        root, source_type="model_profile", cache_path=tmp_path / "cache.json"
    )
    assert provenance["status"] == "available"
    result_dir, result = _write_directory_run(tmp_path, provenance)
    attach_run_fingerprint(result_dir, result)
    _persist(result_dir, result)

    output_dir = tmp_path / "public"
    export_public_run(result_dir, output_dir)
    exported_json = (output_dir / "llmgauge-result.json").read_text(encoding="utf-8")
    assert str(blobs) not in exported_json
    assert "hf-cache" not in exported_json


# --- report rendering ----------------------------------------------------------


def test_report_renders_bounded_directory_identity(tmp_path) -> None:
    from llmgauge.core.reports import build_markdown_report

    provenance = _directory_provenance(tmp_path)
    result_dir, result = _write_directory_run(tmp_path, provenance)
    attach_run_fingerprint(result_dir, result)
    report = build_markdown_report(result, result_dir=result_dir)

    assert "### Checkpoint Directory Provenance" in report
    assert provenance["public_fingerprint"] in report
    assert provenance["tokenizer_identity"]["public_fingerprint"] in report
    assert provenance["chat_template_identity"]["public_fingerprint"] in report
    assert "Effective runtime quantization: unavailable" in report
    assert "Run-fingerprint eligibility: eligible" in report

    # No private manifest dump.
    assert provenance["manifest_sha256"] not in report
    for entry in provenance["manifest"]:
        assert entry["sha256"] not in report
    # The checkpoint root locator never appears (the fixture's unrelated
    # llama_cli path is pre-existing private-report behavior).
    assert str(tmp_path / "ckpt") not in report


def test_gguf_report_rendering_remains_stable(tmp_path) -> None:
    from llmgauge.core.reports import build_markdown_report

    result_dir, result = _write_fingerprintable_run(tmp_path)
    attach_run_fingerprint(result_dir, result)
    report = build_markdown_report(result, result_dir=result_dir)
    assert "### Checkpoint Directory Provenance" not in report
