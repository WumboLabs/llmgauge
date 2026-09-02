"""Focused tests for the frozen llama.cpp runtime-lineage manifest.

Covers manifest integrity, conservative commit-identity resolution (never
blind truncation), independent placement/slot-timing admission, and
source-specific capture/validation. All fixtures are synthetic or derived
from the frozen packaged manifest; no real model output or runtime is used.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from llmgauge.core.area4_evidence import build_native_execution_evidence
from llmgauge.core.native_diagnostics import (
    REASON_AMBIGUOUS_PREFIX,
    REASON_BUILD_MISMATCH,
    REASON_MATCHED,
    REASON_MISSING_METADATA,
    REASON_NOT_IN_MANIFEST,
    LineageManifest,
    LineageRecord,
    native_diagnostics_capture_state,
    packaged_lineage_manifest,
    parse_lineage_manifest,
    qualify_current_native_diagnostics,
)
from llmgauge.core.result_validation import validate_result_dir
from llmgauge.runners.llama_cpp import LlamaCppRunConfig, build_llama_command

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = REPO_ROOT / "src" / "llmgauge" / "data" / "llama_runtime_lineage.json"
GENERATOR_PATH = REPO_ROOT / "scripts" / "generate_llama_runtime_lineage.py"

# Frozen contract anchors (docs/AREA4_NATIVE_LLAMA_CPP_EVIDENCE_V1.md).
PLACEMENT_FLOOR = ("5343f4502", "5343f4502ab5273d7cef85012af020cad0182376", 9538)
TIMING_FLOOR = ("decaf508b", "decaf508bb9ef683c93f58d320b6d6faef507895", 10406)
CEILING = ("0d9ceae1e", "0d9ceae1e38291035605613ab41a8f5e693d6fcd", 10449)
BUILD_9672 = ("74ade5274", "74ade52741203e5c8f81eaf06a96cb1cfe15f2a3", 9672)


def _provenance(build: str | int, commit: str) -> dict[str, Any]:
    return {
        "backend_name": "llama.cpp",
        "build_number": str(build),
        "commit": commit,
        "status": "available",
    }


def _record(short: str, build: int, timing: bool = False) -> LineageRecord:
    return LineageRecord(
        full_commit=short + "0" * (40 - len(short)),
        short_commit=short,
        build_number=build,
        placement_admitted=True,
        slot_timing_admitted=timing,
    )


# A small synthetic manifest with a deliberate 7-character prefix collision
# (records `111111110` and `111111120` share the first seven hex characters)
# and one admitted record whose 9-character prefix is shared by a foreign
# full SHA that is NOT in the manifest.
SYNTHETIC_RECORDS = [
    _record("111111110", 100),
    _record("111111120", 101),
    _record("aaaaaaaaa", 102, timing=True),
    _record("bbbbbbbbb", 103),
]
SYNTHETIC = LineageManifest(SYNTHETIC_RECORDS)


# ---------------------------------------------------------------------------
# Manifest integrity
# ---------------------------------------------------------------------------


def test_manifest_record_count() -> None:
    assert len(packaged_lineage_manifest().records) == 912


def test_manifest_placement_count() -> None:
    assert packaged_lineage_manifest().placement_count == 912


def test_manifest_slot_timing_count() -> None:
    assert packaged_lineage_manifest().slot_timing_count == 44


def test_timing_records_are_subset_of_placement() -> None:
    manifest = packaged_lineage_manifest()
    timing = {r.full_commit for r in manifest.records if r.slot_timing_admitted}
    placement = {r.full_commit for r in manifest.records if r.placement_admitted}
    assert timing <= placement
    assert len(timing) == 44


def test_no_duplicate_full_shas() -> None:
    fulls = [r.full_commit for r in packaged_lineage_manifest().records]
    assert len(set(fulls)) == len(fulls)


def test_no_duplicate_short_shas() -> None:
    shorts = [r.short_commit for r in packaged_lineage_manifest().records]
    assert len(set(shorts)) == len(shorts)


def test_no_duplicate_build_numbers() -> None:
    builds = [r.build_number for r in packaged_lineage_manifest().records]
    assert len(set(builds)) == len(builds)


def test_build_mapping_monotonic_bijective() -> None:
    records = packaged_lineage_manifest().records
    builds = [record.build_number for record in records]
    assert builds == sorted(builds)
    assert builds[0] == PLACEMENT_FLOOR[2]
    assert builds[-1] == CEILING[2]
    # one-to-one build<->commit mapping: distinct builds and distinct commits
    assert len({(r.build_number, r.full_commit) for r in records}) == len(records)


def test_placement_floor_anchor() -> None:
    record = packaged_lineage_manifest().records[0]
    assert (record.short_commit, record.full_commit, record.build_number) == tuple(
        PLACEMENT_FLOOR
    )
    assert record.placement_admitted is True
    assert record.slot_timing_admitted is False


def test_timing_floor_anchor() -> None:
    timing = [r for r in packaged_lineage_manifest().records if r.slot_timing_admitted]
    first = timing[0]
    assert (first.short_commit, first.full_commit, first.build_number) == tuple(
        TIMING_FLOOR
    )
    assert len(timing) == 44


def test_ceiling_anchor() -> None:
    record = packaged_lineage_manifest().records[-1]
    assert (record.short_commit, record.full_commit, record.build_number) == tuple(
        CEILING
    )
    assert record.placement_admitted is True
    assert record.slot_timing_admitted is True


def test_manifest_provenance_fields() -> None:
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    provenance = data["provenance"]
    assert provenance["upstream_repository"] == "ggml-org/llama.cpp"
    assert provenance["placement_floor"]["short"] == PLACEMENT_FLOOR[0]
    assert provenance["placement_floor"]["full"] == PLACEMENT_FLOOR[1]
    assert provenance["timing_floor"]["short"] == TIMING_FLOOR[0]
    assert provenance["ceiling"]["short"] == CEILING[0]
    assert provenance["ceiling"]["full"] == CEILING[1]
    assert provenance["placement_record_count"] == 912
    assert provenance["slot_timing_record_count"] == 44
    assert provenance["generator"] == "llmgauge.llama_runtime_lineage.v1"


def test_packaged_resource_resolves_and_matches_tracked_file() -> None:
    from importlib import resources

    text = (
        resources.files("llmgauge")
        .joinpath("data", "llama_runtime_lineage.json")
        .read_text(encoding="utf-8")
    )
    assert json.loads(text) == json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


@pytest.mark.skipif(
    not os.environ.get("LLMGAUGE_LLAMA_CPP_REPO"),
    reason="set LLMGAUGE_LLAMA_CPP_REPO to a verified upstream clone to run",
)
def test_generator_reproduces_tracked_manifest(tmp_path: Path) -> None:
    out = tmp_path / "manifest.json"
    completed = subprocess.run(
        [
            sys.executable,
            str(GENERATOR_PATH),
            "--repo",
            os.environ["LLMGAUGE_LLAMA_CPP_REPO"],
            "--out",
            str(out),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert out.read_bytes() == MANIFEST_PATH.read_bytes()


def test_generator_rejects_non_upstream_repository(tmp_path: Path) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(GENERATOR_PATH),
            "--repo",
            str(tmp_path),
            "--out",
            str(tmp_path / "out.json"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode != 0


def test_generator_ceiling_bounded_by_contract(tmp_path: Path) -> None:
    """A newer repository HEAD cannot silently extend the manifest.

    The enumeration range is fixed by the contract floor/ceiling constants,
    never by the repository tip. Behaviorally: a repository whose history
    does not contain the exact contract identities is refused outright, even
    when it carries a newer HEAD and an upstream-looking remote URL.
    """
    repo = tmp_path / "newer-fork"
    repo.mkdir()
    subprocess.run(
        ["git", "init", "-q", str(repo)],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "remote",
            "add",
            "origin",
            "https://github.com/ggml-org/llama.cpp.git",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    (repo / "file.txt").write_text("newer tip\n", encoding="utf-8")
    for args in (
        ("add", "file.txt"),
        (
            "-c",
            "user.email=t@t",
            "-c",
            "user.name=t",
            "commit",
            "-qm",
            "unreviewed future commit",
        ),
    ):
        subprocess.run(
            ["git", "-C", str(repo), *args],
            check=True,
            capture_output=True,
            text=True,
        )
    completed = subprocess.run(
        [
            sys.executable,
            str(GENERATOR_PATH),
            "--repo",
            str(repo),
            "--out",
            str(tmp_path / "out.json"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode != 0
    assert "not present" in completed.stderr
    assert not (tmp_path / "out.json").exists()


# ---------------------------------------------------------------------------
# Commit identity matching
# ---------------------------------------------------------------------------


def test_canonical_short_commit_exact_match() -> None:
    qualification = qualify_current_native_diagnostics(_provenance(10449, "0d9ceae1e"))
    assert qualification.matched is True
    assert qualification.placement_admitted is True
    assert qualification.slot_timing_admitted is True


def test_full_sha_resolves_uniquely() -> None:
    qualification = qualify_current_native_diagnostics(_provenance(10449, CEILING[1]))
    assert qualification.matched is True
    assert qualification.identity is not None
    assert qualification.identity["short_commit"] == "0d9ceae1e"


def test_extended_prefix_resolves_uniquely() -> None:
    qualification = qualify_current_native_diagnostics(
        _provenance(9672, "74ade52741203e")
    )
    assert qualification.matched is True
    assert qualification.placement_admitted is True
    assert qualification.slot_timing_admitted is False


def test_unique_eight_char_prefix_resolves() -> None:
    prefix = BUILD_9672[1][:8]
    # prove uniqueness against the real manifest before expecting a match
    matches = [
        r
        for r in packaged_lineage_manifest().records
        if r.full_commit.startswith(prefix)
    ]
    assert len(matches) == 1
    qualification = qualify_current_native_diagnostics(_provenance(9672, prefix))
    assert qualification.matched is True


def test_unique_seven_char_prefix_resolves() -> None:
    prefix = TIMING_FLOOR[1][:7]
    matches = [
        r
        for r in packaged_lineage_manifest().records
        if r.full_commit.startswith(prefix)
    ]
    assert len(matches) == 1
    qualification = qualify_current_native_diagnostics(_provenance(10406, prefix))
    assert qualification.matched is True
    assert qualification.slot_timing_admitted is True


def test_ambiguous_seven_char_prefix_rejects() -> None:
    record, reason = SYNTHETIC.resolve("1111111", "100")
    assert record is None
    assert reason == REASON_AMBIGUOUS_PREFIX


def test_unique_eight_char_prefix_in_synthetic_resolves() -> None:
    record, reason = SYNTHETIC.resolve("11111111", "100")
    assert record is not None
    assert reason == REASON_MATCHED
    assert record is not None
    assert record.short_commit == "111111110"


def test_prefix_with_zero_matches_rejects() -> None:
    record, reason = SYNTHETIC.resolve("abcdef1", "100")
    assert record is None
    assert reason == REASON_NOT_IN_MANIFEST


def test_correct_short_wrong_build_rejects() -> None:
    qualification = qualify_current_native_diagnostics(_provenance(10448, "0d9ceae1e"))
    assert qualification.matched is False
    assert qualification.reason == REASON_BUILD_MISMATCH


def test_correct_build_foreign_commit_rejects() -> None:
    qualification = qualify_current_native_diagnostics(_provenance(10449, "deadbeef9"))
    assert qualification.matched is False
    assert qualification.reason == REASON_NOT_IN_MANIFEST


def test_foreign_full_sha_sharing_admitted_prefix_rejects() -> None:
    # Same first 9 characters as admitted synthetic record `aaaaaaaaa`, but a
    # different full SHA. Blind truncation to 9 characters would wrongly admit.
    foreign = "aaaaaaaaa" + "1" * 31
    record, reason = SYNTHETIC.resolve(foreign, "102")
    assert record is None
    assert reason == REASON_NOT_IN_MANIFEST
    # also as a 10-character extended prefix
    record, reason = SYNTHETIC.resolve(foreign[:10], "102")
    assert record is None
    assert reason == REASON_NOT_IN_MANIFEST


def test_uppercase_commit_normalizes() -> None:
    qualification = qualify_current_native_diagnostics(_provenance(10449, "0D9CEAE1E"))
    assert qualification.matched is True


def test_non_hex_commit_rejects() -> None:
    record, reason = SYNTHETIC.resolve("0d9ceae1z", "10449")
    assert record is None
    assert reason == REASON_MISSING_METADATA


def test_commit_below_minimum_length_rejects() -> None:
    record, reason = SYNTHETIC.resolve("0d9cea", "10449")
    assert record is None
    assert reason == REASON_MISSING_METADATA


def test_commit_above_maximum_length_rejects() -> None:
    record, reason = SYNTHETIC.resolve("0" * 41, "10449")
    assert record is None
    assert reason == REASON_MISSING_METADATA


def test_whitespace_padded_commit_rejects() -> None:
    # The provenance parser never emits padded commits; the matcher must also
    # fail closed rather than strip arbitrary input.
    record, reason = SYNTHETIC.resolve(" 0d9ceae1e ", "10449")
    assert record is None
    assert reason == REASON_MISSING_METADATA


def test_non_string_metadata_rejects() -> None:
    assert (
        qualify_current_native_diagnostics(
            {"build_number": 10449, "commit": "0d9ceae1e"}
        ).matched
        is False
    )
    assert (
        qualify_current_native_diagnostics(
            {"build_number": "10449", "commit": 123}
        ).matched
        is False
    )


def test_build_only_admission_impossible() -> None:
    # In-range build with any non-manifest commit never admits.
    for commit in ("0000000", "fffffffff", "1234567890abcdef"):
        qualification = qualify_current_native_diagnostics(_provenance(10000, commit))
        assert qualification.matched is False
        assert qualification.placement_admitted is False


def test_commit_only_admission_impossible() -> None:
    # Admitted commit with any wrong build never admits.
    for build in ("9537", "10450", "1", "99999999"):
        qualification = qualify_current_native_diagnostics(
            _provenance(build, "0d9ceae1e")
        )
        assert qualification.matched is False


# ---------------------------------------------------------------------------
# Source-specific admission
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("build", "commit", "placement", "timing"),
    [
        (9538, "5343f4502", True, False),
        (9672, "74ade5274", True, False),
        (10405, "e79e4bf66", True, False),
        (10406, "decaf508b", True, True),
        (10449, "0d9ceae1e", True, True),
        (9537, "123456789", False, False),
        (10450, "fffffffff", False, False),
        (10000, "abcdefabc", False, False),
    ],
)
def test_independent_admission_flags(
    build: int, commit: str, placement: bool, timing: bool
) -> None:
    qualification = qualify_current_native_diagnostics(_provenance(build, commit))
    assert qualification.placement_admitted is placement
    assert qualification.slot_timing_admitted is timing


def test_manifest_parser_rejects_invalid_documents() -> None:
    with pytest.raises(ValueError):
        parse_lineage_manifest({"schema_version": "wrong", "records": []})
    with pytest.raises(ValueError):
        # full SHA must begin with the canonical short SHA
        parse_lineage_manifest(
            {
                "schema_version": "llmgauge.llama_runtime_lineage.v1",
                "records": [
                    {
                        "full_commit": "x" * 40,
                        "short_commit": "aaaaaaaaa",
                        "build_number": 1,
                        "placement_admitted": True,
                        "slot_timing_admitted": False,
                    }
                ],
            }
        )
    with pytest.raises(ValueError):
        # duplicate short SHA
        parse_lineage_manifest(
            {
                "schema_version": "llmgauge.llama_runtime_lineage.v1",
                "records": [
                    {
                        "full_commit": "a" * 40,
                        "short_commit": "aaaaaaaaa",
                        "build_number": 1,
                        "placement_admitted": True,
                        "slot_timing_admitted": False,
                    },
                    {
                        "full_commit": "b" * 40,
                        "short_commit": "aaaaaaaaa",
                        "build_number": 2,
                        "placement_admitted": True,
                        "slot_timing_admitted": False,
                    },
                ],
            }
        )


# ---------------------------------------------------------------------------
# Capture / validation behavior
# ---------------------------------------------------------------------------

PLACEMENT_LINE = "0.00.123.456 I load_tensors: offloaded 5/17 layers to GPU\n"
SLOT_FINAL_BLOCK = (
    "0.00.520.660 I slot print_timing: id  0 | task 0 | prompt eval time ="
    "      43.38 ms /    16 tokens (    2.71 ms per token,   368.85 tokens"
    " per second)\n"
    "0.00.520.663 I slot print_timing: id  0 | task 0 |        eval time ="
    "      10.76 ms /     2 tokens (   10.76 ms per token,    92.97 tokens"
    " per second)\n"
    "0.00.520.664 I slot print_timing: id  0 | task 0 |       total time ="
    "      54.13 ms /    18 tokens\n"
    "0.00.520.668 I slot print_timing: id  0 | task 0 |    graphs reused ="
    "          1\n"
)


def _config(**overrides: Any) -> LlamaCppRunConfig:
    base: dict[str, Any] = {
        "llama_cli": Path("llama-cli"),
        "model_path": Path("model.gguf"),
        "ctx_size": 1024,
        "max_tokens": 8,
        "temperature": 0.0,
        "top_p": 1.0,
        "batch_size": 512,
        "ubatch_size": 512,
        "gpu_layers": 5,
        "flash_attn": "off",
        "reasoning_mode": "auto",
    }
    base.update(overrides)
    return LlamaCppRunConfig(**base)


def test_placement_only_identity_enables_capture() -> None:
    qualification = qualify_current_native_diagnostics(_provenance(9672, "74ade5274"))
    assert qualification.placement_admitted is True
    command = build_llama_command(
        _config(native_diagnostics_capture=qualification.placement_admitted), "hi"
    )
    assert command[command.index("--verbosity") + 1] == "4"


def test_placement_only_identity_never_emits_slot_timing() -> None:
    # Even with matching slot lines present at verbosity 4, a placement-only
    # lineage identity must not produce a trusted slot_print_timing object.
    evidence = build_native_execution_evidence(
        prompt_id="prompt",
        elapsed_seconds=1.0,
        stdout="answer",
        stderr=PLACEMENT_LINE + SLOT_FINAL_BLOCK,
        exit_status=0,
        timed_out=False,
        launch_error=None,
        placement_admitted=True,
        slot_timing_admitted=False,
    )
    assert "slot_print_timing" not in evidence
    assert evidence["llama_cpp_placement"]["observed"] == "hybrid_accelerator_cpu"
    assert evidence["llama_cpp_placement"]["source"] == "load_tensors"


def test_both_source_identity_captures_placement_and_slot() -> None:
    evidence = build_native_execution_evidence(
        prompt_id="prompt",
        elapsed_seconds=1.0,
        stdout="answer",
        stderr=PLACEMENT_LINE + SLOT_FINAL_BLOCK,
        exit_status=0,
        timed_out=False,
        launch_error=None,
        placement_admitted=True,
        slot_timing_admitted=True,
    )
    assert evidence["llama_cpp_placement"]["observed"] == "hybrid_accelerator_cpu"
    assert evidence["slot_print_timing"]["availability"] == "available"


def test_unqualified_identity_does_not_enable_verbosity_capture() -> None:
    qualification = qualify_current_native_diagnostics(_provenance(10000, "abcdefabc"))
    assert qualification.placement_admitted is False
    command = build_llama_command(
        _config(native_diagnostics_capture=qualification.placement_admitted), "hi"
    )
    assert "--verbosity" not in command


def _write_result(tmp_path: Path, result: dict) -> None:
    (tmp_path / "llmgauge-result.json").write_text(json.dumps(result), encoding="utf-8")


def _base_result(tmp_path: Path, *, evidence: dict, provenance: dict) -> dict:
    from llmgauge.core.area4_evidence import build_area4_evidence

    (tmp_path / "raw").mkdir()
    (tmp_path / "logs").mkdir()
    (tmp_path / "native").mkdir()
    (tmp_path / "raw/prompt.prompt.md").write_text("prompt", encoding="utf-8")
    (tmp_path / "raw/prompt.output.txt").write_text("output", encoding="utf-8")
    (tmp_path / "logs/prompt.stderr.log").write_text("stderr", encoding="utf-8")
    (tmp_path / "native/prompt.execution.json").write_text(
        json.dumps(evidence), encoding="utf-8"
    )
    prompt = {
        "prompt_id": "prompt",
        "title": "Prompt",
        "category": "test",
        "status": "completed",
        "raw_prompt_path": "raw/prompt.prompt.md",
        "raw_output_path": "raw/prompt.output.txt",
        "cleaned_output_path": "raw/prompt.output.txt",
        "stderr_log_path": "logs/prompt.stderr.log",
        "native_execution_evidence_path": "native/prompt.execution.json",
        "_area4_native_execution_evidence": evidence,
        "metrics": {},
        "vram": None,
        "vram_samples_path": None,
        "vram_guardrails": None,
        "score": None,
        "failure_labels": [],
        "notes": "",
        "exit_status": 0,
        "error": None,
    }
    result = {
        "schema_version": "llmgauge.result.v0",
        "llmgauge_version": "0.77.0",
        "run": {
            "run_id": "run",
            "timestamp_utc": "2026-09-01T00:00:00+00:00",
            "status": "completed",
            "result_dir": str(tmp_path),
        },
        "model": {
            "model_id": "model",
            "model_path": "redacted",
            "provenance": {
                "source_type": "test",
                "filename": "model.gguf",
                "file_size_bytes": 1,
                "sha256": "a" * 64,
                "status": "available",
            },
        },
        "runtime": {
            "backend": "llama.cpp",
            "max_tokens": 1,
            "batch_size": 1,
            "ubatch_size": 1,
            "parallel_sequences": 1,
            "backend_provenance": provenance,
        },
        "suite": {
            "suite_id": "suite",
            "suite_version": "1",
            "prompt_count": 1,
            "include": [],
            "only": ["prompt"],
        },
        "results": [prompt],
        "summary": {"completed": 1, "failed": 0},
    }
    metrics, taxonomy = build_area4_evidence(
        prompt_results=result["results"],
        suite=result["suite"],
        runtime=result["runtime"],
    )
    prompt.pop("_area4_native_execution_evidence")
    result["runtime_neutral_metrics"] = metrics
    result["failure_taxonomy"] = taxonomy
    return result


def test_current_placement_on_manifest_unqualified_identity_fails(
    tmp_path: Path,
) -> None:
    # build 10000 is inside the old semantic interval but the commit is a
    # foreign fork SHA: the exact-pair rule must reject the placement claim.
    evidence = build_native_execution_evidence(
        prompt_id="prompt",
        elapsed_seconds=1.0,
        stdout="answer",
        stderr=PLACEMENT_LINE,
        exit_status=0,
        timed_out=False,
        launch_error=None,
        placement_admitted=True,  # forged producer state
        slot_timing_admitted=False,
    )
    result = _base_result(
        tmp_path, evidence=evidence, provenance=_provenance(10000, "abcdefabc")
    )
    _write_result(tmp_path, result)
    errors = validate_result_dir(tmp_path)
    assert any(
        "current-prefix on a lineage-unqualified runtime" in error for error in errors
    )


def test_slot_timing_on_placement_only_identity_fails(tmp_path: Path) -> None:
    evidence = build_native_execution_evidence(
        prompt_id="prompt",
        elapsed_seconds=1.0,
        stdout="answer",
        stderr=SLOT_FINAL_BLOCK,
        exit_status=0,
        timed_out=False,
        launch_error=None,
        placement_admitted=True,
        slot_timing_admitted=True,  # forged: 9672 lineage says timing false
    )
    result = _base_result(
        tmp_path, evidence=evidence, provenance=_provenance(9672, "74ade5274")
    )
    _write_result(tmp_path, result)
    errors = validate_result_dir(tmp_path)
    assert any("does not admit slot timing" in error for error in errors)


def test_valid_placement_only_result_passes_validator(tmp_path: Path) -> None:
    evidence = build_native_execution_evidence(
        prompt_id="prompt",
        elapsed_seconds=1.0,
        stdout="answer",
        stderr=PLACEMENT_LINE + SLOT_FINAL_BLOCK,
        exit_status=0,
        timed_out=False,
        launch_error=None,
        placement_admitted=True,
        slot_timing_admitted=False,
    )
    result = _base_result(
        tmp_path, evidence=evidence, provenance=_provenance(9672, "74ade5274")
    )
    _write_result(tmp_path, result)
    assert validate_result_dir(tmp_path) == []


def test_valid_both_source_result_passes_validator(tmp_path: Path) -> None:
    evidence = build_native_execution_evidence(
        prompt_id="prompt",
        elapsed_seconds=1.0,
        stdout="answer",
        stderr=PLACEMENT_LINE + SLOT_FINAL_BLOCK,
        exit_status=0,
        timed_out=False,
        launch_error=None,
        placement_admitted=True,
        slot_timing_admitted=True,
    )
    result = _base_result(
        tmp_path, evidence=evidence, provenance=_provenance(10449, "0d9ceae1e")
    )
    _write_result(tmp_path, result)
    assert validate_result_dir(tmp_path) == []


def test_stored_capture_flags_mutated_away_from_recomputation_fail(
    tmp_path: Path,
) -> None:
    evidence = build_native_execution_evidence(
        prompt_id="prompt",
        elapsed_seconds=1.0,
        stdout="answer",
        stderr=PLACEMENT_LINE,
        exit_status=0,
        timed_out=False,
        launch_error=None,
        placement_admitted=True,
        slot_timing_admitted=False,
    )
    result = _base_result(
        tmp_path, evidence=evidence, provenance=_provenance(9672, "74ade5274")
    )
    result["runtime"]["native_diagnostics_capture"] = {
        **native_diagnostics_capture_state(_provenance(9672, "74ade5274")),
        "slot_timing_admitted": True,  # mutation away from recomputation
    }
    _write_result(tmp_path, result)
    errors = validate_result_dir(tmp_path)
    assert any("native_diagnostics_capture" in error for error in errors)


def test_historical_exact_shape_capture_blob_remains_valid(tmp_path: Path) -> None:
    # v0.77-era artifacts carry the pre-lineage blob; it must not be
    # reinterpreted or rejected by lineage validation.
    evidence = build_native_execution_evidence(
        prompt_id="prompt",
        elapsed_seconds=1.0,
        stdout="answer",
        stderr=PLACEMENT_LINE,
        exit_status=0,
        timed_out=False,
        launch_error=None,
        placement_admitted=True,
        slot_timing_admitted=True,
    )
    result = _base_result(
        tmp_path, evidence=evidence, provenance=_provenance(10449, "0d9ceae1e")
    )
    result["runtime"]["native_diagnostics_capture"] = {
        "current_diagnostics_admitted": True,
        "qualified_build": "10449",
        "qualified_commit": "0d9ceae1e",
        "effective_verbosity": 4,
        "reason": "exact_qualified_llama_cli_build_10449",
    }
    _write_result(tmp_path, result)
    assert validate_result_dir(tmp_path) == []
