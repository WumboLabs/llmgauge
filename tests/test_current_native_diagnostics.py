"""Focused synthetic tests for current llama-cli native diagnostics capture.

All fixtures are minimized synthetic diagnostic structures. No real model
output, timing, or machine path is used.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from llmgauge.core.area4_evidence import (
    NATIVE_EXECUTION_EVIDENCE_SCHEMA,
    build_area4_evidence,
    build_native_execution_evidence,
)
from llmgauge.core.identity import parse_llama_version_output
from llmgauge.core.metrics import (
    parse_llama_cpp_diagnostics,
    parse_slot_print_timing,
    retain_native_diagnostics_stderr,
)
from llmgauge.core.native_diagnostics import (
    NATIVE_DIAGNOSTICS_VERBOSITY,
    current_native_diagnostics_admitted,
    native_diagnostics_capture_state,
)
from llmgauge.core.result_validation import validate_result_dir
from llmgauge.runners.llama_cpp import LlamaCppRunConfig, build_llama_command

QUALIFIED_PROVENANCE: dict[str, Any] = {
    "backend_name": "llama.cpp",
    "build_number": "10449",
    "commit": "0d9ceae1e",
    "reported_version": "0.1.0-dev (build 10449, commit 0d9ceae1e)",
    "status": "available",
}

# A complete request-final slot block (server_slot::print_timings).
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
SLOT_PROGRESS_TG = (
    "0.00.400.000 I slot print_timing: id  0 | task 0 | n_gen =    105,"
    " tg =   60.00 t/s, tg_3s =   58.00 t/s\n"
)
SLOT_PROGRESS_PP = (
    "0.00.310.000 I slot print_timing: id  0 | task 0 | prompt processing,"
    " n_tokens =    100, progress = 0.50, t =   3.20 s / 31.25 tokens per"
    " second\n"
)


def _placement(parsed: dict[str, Any]) -> dict[str, Any]:
    return parsed["llama_cpp_placement"]


# --------------------------------------------------------------------------
# Placement
# --------------------------------------------------------------------------


def test_historical_llm_load_tensors_still_works() -> None:
    parsed = parse_llama_cpp_diagnostics(
        "llm_load_tensors: offloaded 0/41 layers to GPU\n"
    )
    placement = _placement(parsed)
    assert placement["observed"] == "cpu_only"
    assert placement["source"] == "llm_load_tensors"


def test_current_load_tensors_zero_is_cpu_only_with_source() -> None:
    parsed = parse_llama_cpp_diagnostics(
        "",
        stderr="0.00.385.139 I load_tensors: offloaded 0/17 layers to GPU\n",
        current_diagnostics_admitted=True,
    )
    placement = _placement(parsed)
    assert placement["observed"] == "cpu_only"
    assert placement["source"] == "load_tensors"
    assert placement["offloaded_layers"] == 0
    assert placement["total_layers"] == 17


def test_current_load_tensors_partial_is_hybrid() -> None:
    parsed = parse_llama_cpp_diagnostics(
        "",
        stderr="0.00.232.437 I load_tensors: offloaded 5/17 layers to GPU\n",
        current_diagnostics_admitted=True,
    )
    assert _placement(parsed)["observed"] == "hybrid_accelerator_cpu"
    assert _placement(parsed)["source"] == "load_tensors"


def test_current_load_tensors_equal_layers_is_unknown() -> None:
    parsed = parse_llama_cpp_diagnostics(
        "",
        stderr="0.00.232.437 I load_tensors: offloaded 17/17 layers to GPU\n",
        current_diagnostics_admitted=True,
    )
    placement = _placement(parsed)
    assert placement["observed"] == "unknown"
    assert placement["source"] == "load_tensors"


def test_no_offload_line_is_unavailable() -> None:
    parsed = parse_llama_cpp_diagnostics(
        "model output text\n",
        stderr="no diagnostic here\n",
        current_diagnostics_admitted=True,
    )
    assert _placement(parsed)["observed"] == "unavailable"
    assert _placement(parsed)["source"] is None


def test_conflicting_current_offload_lines_fail_conservative() -> None:
    parsed = parse_llama_cpp_diagnostics(
        "",
        stderr=(
            "0.00.123.456 I load_tensors: offloaded 5/17 layers to GPU\n"
            "0.00.124.456 I load_tensors: offloaded 9/17 layers to GPU\n"
        ),
        current_diagnostics_admitted=True,
    )
    placement = _placement(parsed)
    assert placement["observed"] == "unavailable"
    assert placement["offloaded_layers"] is None


def test_offload_timestamp_prefix_tolerated() -> None:
    parsed = parse_llama_cpp_diagnostics(
        "",
        stderr="12.03.456.789 I load_tensors: offloaded 5/17 layers to GPU\n",
        current_diagnostics_admitted=True,
    )
    assert _placement(parsed)["observed"] == "hybrid_accelerator_cpu"


def test_current_prefix_on_unqualified_runtime_not_admitted() -> None:
    parsed = parse_llama_cpp_diagnostics(
        "",
        stderr="0.00.123.456 I load_tensors: offloaded 5/17 layers to GPU\n",
        current_diagnostics_admitted=False,
    )
    assert _placement(parsed)["observed"] == "unavailable"


def test_current_prefix_in_stdout_never_admitted() -> None:
    # Model output cannot forge current-prefix placement evidence.
    parsed = parse_llama_cpp_diagnostics(
        "load_tensors: offloaded 5/17 layers to GPU\n",
        stderr="",
        current_diagnostics_admitted=True,
    )
    assert _placement(parsed)["observed"] == "unavailable"


# --------------------------------------------------------------------------
# Timing
# --------------------------------------------------------------------------


def test_slot_final_block_prompt_fields() -> None:
    parsed = parse_slot_print_timing(SLOT_FINAL_BLOCK)
    assert parsed["availability"] == "available"
    assert parsed["source"] == "slot_print_timing"
    assert parsed["prompt_eval_time_seconds"] == pytest.approx(0.04338)
    assert parsed["prompt_eval_token_count"] == 16
    assert parsed["prompt_eval_tps"] == pytest.approx(368.85)


def test_slot_final_block_generation_fields() -> None:
    parsed = parse_slot_print_timing(SLOT_FINAL_BLOCK)
    assert parsed["eval_time_seconds"] == pytest.approx(0.01076)
    assert parsed["eval_token_count"] == 2
    assert parsed["generation_tps"] == pytest.approx(92.97)


def test_slot_rejects_load_time() -> None:
    assert parse_slot_print_timing(SLOT_FINAL_BLOCK)["load_time_seconds"] is None


def test_slot_rejects_total_time() -> None:
    assert parse_slot_print_timing(SLOT_FINAL_BLOCK)["total_time_seconds"] is None


def test_slot_rejects_graphs_reused() -> None:
    assert parse_slot_print_timing(SLOT_FINAL_BLOCK)["graphs_reused"] is None


def test_generation_tps_not_recomputed_as_count_over_time() -> None:
    # The source rate is over n_gen-1 decode steps; the displayed count is
    # n_gen. eval_token_count / eval_time_seconds would be 2 / 0.01076 =
    # 185.9, which must NOT replace the preserved 92.97 source rate.
    parsed = parse_slot_print_timing(SLOT_FINAL_BLOCK)
    naive = parsed["eval_token_count"] / parsed["eval_time_seconds"]
    assert parsed["generation_tps"] != pytest.approx(naive)
    assert parsed["raw"]["generation_rate_denominator"] == "eval_tokens_minus_one"


def test_progress_tg_line_alone_rejected() -> None:
    assert parse_slot_print_timing(SLOT_PROGRESS_TG)["availability"] == "unavailable"


def test_progress_pp_line_alone_rejected() -> None:
    assert parse_slot_print_timing(SLOT_PROGRESS_PP)["availability"] == "unavailable"


def test_progress_plus_one_final_block_selects_final() -> None:
    parsed = parse_slot_print_timing(
        SLOT_PROGRESS_PP + SLOT_FINAL_BLOCK + SLOT_PROGRESS_TG
    )
    assert parsed["availability"] == "available"
    assert parsed["prompt_eval_token_count"] == 16


def test_multiple_final_blocks_ambiguous() -> None:
    second = SLOT_FINAL_BLOCK.replace("task 0 |", "task 18 |")
    parsed = parse_slot_print_timing(SLOT_FINAL_BLOCK + second)
    assert parsed["availability"] == "unavailable"
    assert parsed["reason"] == "ambiguous_final_blocks"


def test_incomplete_final_block_rejected() -> None:
    partial = "".join(
        line
        for line in SLOT_FINAL_BLOCK.splitlines(keepends=True)
        if "graphs reused" not in line
    )
    assert parse_slot_print_timing(partial)["availability"] == "unavailable"


def test_slot_timestamp_prefix_handled() -> None:
    # Real lines already carry the prefix; a no-prefix variant must also parse.
    unprefixed = (
        SLOT_FINAL_BLOCK.replace("0.00.520.660 I ", "")
        .replace("0.00.520.663 I ", "")
        .replace("0.00.520.664 I ", "")
        .replace("0.00.520.668 I ", "")
    )
    assert parse_slot_print_timing(unprefixed)["availability"] == "available"


def test_slot_only_populated_when_admitted() -> None:
    parsed = parse_llama_cpp_diagnostics(
        SLOT_FINAL_BLOCK,
        stderr=SLOT_FINAL_BLOCK,
        current_diagnostics_admitted=False,
    )
    assert "slot_print_timing" not in parsed


# --------------------------------------------------------------------------
# Runtime qualification
# --------------------------------------------------------------------------


def test_qualified_runtime_admits_current_diagnostics() -> None:
    assert current_native_diagnostics_admitted(QUALIFIED_PROVENANCE) is True


@pytest.mark.parametrize(
    "provenance",
    [
        None,
        {},
        {"build_number": "10448", "commit": "0d9ceae1e"},
        {"build_number": "10449", "commit": "deadbeef"},
        {"build_number": None, "commit": "0d9ceae1e"},
        {"build_number": "10449", "commit": None},
    ],
)
def test_unqualified_runtime_fails_closed(provenance: Any) -> None:
    assert current_native_diagnostics_admitted(provenance) is False


def test_version_probe_extracts_qualified_build_and_commit() -> None:
    parsed = parse_llama_version_output(
        "version: 0.1.0-dev (build 10449, commit 0d9ceae1e)\n"
        "built with GNU 15.3.1 for Linux x86_64\n"
    )
    assert parsed["build_number"] == "10449"
    assert parsed["commit"] == "0d9ceae1e"
    assert current_native_diagnostics_admitted(parsed) is True


def test_capture_state_records_effective_verbosity() -> None:
    state = native_diagnostics_capture_state(QUALIFIED_PROVENANCE)
    assert state["current_diagnostics_admitted"] is True
    assert state["effective_verbosity"] == NATIVE_DIAGNOSTICS_VERBOSITY == 4


# --------------------------------------------------------------------------
# Runner command construction
# --------------------------------------------------------------------------


def _config(**overrides: Any) -> LlamaCppRunConfig:
    base = {
        "llama_cli": Path("/usr/local/bin/llama-cli"),
        "model_path": Path("/models/model.gguf"),
        "ctx_size": 2048,
        "max_tokens": 32,
        "temperature": 0.2,
        "top_p": 0.9,
        "batch_size": 512,
        "ubatch_size": 128,
        "gpu_layers": 5,
    }
    base.update(overrides)
    return LlamaCppRunConfig(**base)


def test_capture_adds_verbosity_and_parallel_one() -> None:
    command = build_llama_command(_config(native_diagnostics_capture=True), "hi")
    assert command[command.index("--verbosity") + 1] == "4"
    assert command[command.index("--parallel") + 1] == "1"
    assert "--single-turn" in command


def test_no_capture_omits_verbosity() -> None:
    command = build_llama_command(_config(), "hi")
    assert "--verbosity" not in command


# --------------------------------------------------------------------------
# Logging / privacy retention
# --------------------------------------------------------------------------


def test_retention_keeps_admitted_and_error_lines() -> None:
    stderr = (
        "0.00.064.132 I cmn  common_param: common_params_print_info:"
        " verbosity = 4 (adjust with the `-lv N` CLI arg)\n"
        "0.00.134.074 W srv  llama_server: a warning worth keeping\n"
        "0.00.232.436 I load_tensors: offloading 4 repeating layers to GPU\n"
        "0.00.232.437 I load_tensors: offloaded 5/17 layers to GPU\n"
        "0.00.232.438 I load_tensors:   CPU_Mapped model buffer size ="
        "   544.77 MiB\n"
        "0.00.252.194 I srv    load_model: loading model"
        " '/home/operator/private/model.gguf'\n" + SLOT_FINAL_BLOCK
    )
    kept = retain_native_diagnostics_stderr(stderr)
    assert "verbosity = 4" in kept
    assert "a warning worth keeping" in kept
    assert "offloaded 5/17 layers to GPU" in kept
    assert "slot print_timing:" in kept
    # verbosity-only noise and private absolute paths are dropped
    assert "CPU_Mapped model buffer size" not in kept
    assert "/home/operator/private/model.gguf" not in kept
    assert "offloading 4 repeating layers" not in kept


def test_retention_preserves_historical_perf_footer() -> None:
    stderr = (
        "llama_perf_context_print:        load time =     123.45 ms\n"
        "0.00.1 I some unrelated info noise\n"
    )
    kept = retain_native_diagnostics_stderr(stderr)
    assert "load time =     123.45 ms" in kept
    assert "unrelated info noise" not in kept


def test_retention_empty_when_only_noise() -> None:
    assert retain_native_diagnostics_stderr("0.00.1 I noise\n") == ""


# --------------------------------------------------------------------------
# Evidence build + validator recomputation
# --------------------------------------------------------------------------


def _evidence(
    *,
    stderr: str,
    admitted: bool,
    stdout: str = "answer",
) -> dict[str, Any]:
    return build_native_execution_evidence(
        prompt_id="prompt",
        elapsed_seconds=1.25,
        stdout=stdout,
        stderr=stderr,
        exit_status=0,
        timed_out=False,
        launch_error=None,
        current_diagnostics_admitted=admitted,
    )


def _base_result(tmp_path: Path, *, evidence: dict, runtime: dict) -> dict:
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
            "backend_provenance": dict(QUALIFIED_PROVENANCE),
            **runtime,
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


def _write(tmp_path: Path, result: dict) -> None:
    (tmp_path / "llmgauge-result.json").write_text(json.dumps(result), encoding="utf-8")


def test_slot_evidence_validates_when_consistent(tmp_path: Path) -> None:
    stderr = "0.00.123.456 I load_tensors: offloaded 5/17 layers to GPU\n" + SLOT_FINAL_BLOCK
    evidence = _evidence(stderr=stderr, admitted=True)
    assert evidence["slot_print_timing"]["availability"] == "available"
    assert evidence["llama_cpp_placement"]["source"] == "load_tensors"
    result = _base_result(tmp_path, evidence=evidence, runtime={})
    _write(tmp_path, result)
    assert validate_result_dir(tmp_path) == []


def test_validator_rejects_stored_source_without_evidence(tmp_path: Path) -> None:
    # stored slot source says slot_print_timing but evidence has only compact UI
    stderr = "[ Prompt: 368.9 t/s | Generation: 93.0 t/s ]\n"
    evidence = _evidence(stderr=stderr, admitted=True)
    evidence["slot_print_timing"]["availability"] = "available"
    evidence["slot_print_timing"]["generation_tps"] = 93.0
    result = _base_result(tmp_path, evidence=evidence, runtime={})
    _write(tmp_path, result)
    errors = validate_result_dir(tmp_path)
    assert any("no preserved" in error for error in errors)


def test_validator_rejects_mutated_generation_tps(tmp_path: Path) -> None:
    stderr = SLOT_FINAL_BLOCK
    evidence = _evidence(stderr=stderr, admitted=True)
    evidence["slot_print_timing"]["generation_tps"] = 999.0
    result = _base_result(tmp_path, evidence=evidence, runtime={})
    _write(tmp_path, result)
    errors = validate_result_dir(tmp_path)
    assert any("generation_tps differs from recomputed" in error for error in errors)


def test_validator_rejects_source_identity_mutation(tmp_path: Path) -> None:
    stderr = "0.00.123.456 I load_tensors: offloaded 5/17 layers to GPU\n"
    evidence = _evidence(stderr=stderr, admitted=True)
    evidence["llama_cpp_placement"]["source"] = "llm_load_tensors"
    result = _base_result(tmp_path, evidence=evidence, runtime={})
    _write(tmp_path, result)
    errors = validate_result_dir(tmp_path)
    assert any(
        "llama_cpp_placement.source differs from recomputed" in error
        for error in errors
    )


def test_validator_rejects_slot_timing_on_parallel_gt_one(tmp_path: Path) -> None:
    evidence = _evidence(stderr=SLOT_FINAL_BLOCK, admitted=True)
    result = _base_result(
        tmp_path,
        evidence=evidence,
        runtime={"parallel_sequences": 4},
    )
    _write(tmp_path, result)
    errors = validate_result_dir(tmp_path)
    assert any("parallel_sequences=1" in error for error in errors)


def test_validator_rejects_slot_timing_on_unqualified_runtime(
    tmp_path: Path,
) -> None:
    evidence = _evidence(stderr=SLOT_FINAL_BLOCK, admitted=True)
    result = _base_result(tmp_path, evidence=evidence, runtime={})
    result["runtime"]["backend_provenance"] = {
        "backend_name": "llama.cpp",
        "build_number": "9999",
        "commit": "aaaaaaa",
        "status": "available",
    }
    _write(tmp_path, result)
    errors = validate_result_dir(tmp_path)
    assert any("unqualified runtime" in error for error in errors)


def test_validator_rejects_total_time_from_slot(tmp_path: Path) -> None:
    evidence = _evidence(stderr=SLOT_FINAL_BLOCK, admitted=True)
    evidence["slot_print_timing"]["total_time_seconds"] = 0.05413
    result = _base_result(tmp_path, evidence=evidence, runtime={})
    _write(tmp_path, result)
    errors = validate_result_dir(tmp_path)
    assert any("total_time_seconds is rejected" in error for error in errors)


def test_validator_rejects_progress_only_as_final(tmp_path: Path) -> None:
    evidence = _evidence(stderr=SLOT_PROGRESS_PP, admitted=True)
    # forge an available claim from progress-only lines
    evidence["slot_print_timing"]["availability"] = "available"
    evidence["slot_print_timing"]["raw"] = {
        "lines": [SLOT_PROGRESS_PP.strip()],
        "generation_rate_denominator": "eval_tokens_minus_one",
    }
    evidence["slot_print_timing"]["generation_tps"] = 31.25
    result = _base_result(tmp_path, evidence=evidence, runtime={})
    _write(tmp_path, result)
    errors = validate_result_dir(tmp_path)
    assert any(
        "do not form a complete unambiguous final block" in error for error in errors
    )


def test_validator_rejects_current_placement_source_on_unqualified(
    tmp_path: Path,
) -> None:
    evidence = _evidence(
        stderr="0.00.123.456 I load_tensors: offloaded 5/17 layers to GPU\n",
        admitted=True,
    )
    result = _base_result(tmp_path, evidence=evidence, runtime={})
    result["runtime"]["backend_provenance"] = {
        "backend_name": "llama.cpp",
        "build_number": "1",
        "commit": "0000000",
        "status": "available",
    }
    _write(tmp_path, result)
    errors = validate_result_dir(tmp_path)
    assert any("current-prefix on an unqualified runtime" in error for error in errors)


# --------------------------------------------------------------------------
# Backward compatibility
# --------------------------------------------------------------------------


def test_historical_perf_footer_still_validates(tmp_path: Path) -> None:
    stderr = (
        "llm_load_tensors: offloaded 20/41 layers to GPU\n"
        "llama_perf_context_print:        load time =     1420.00 ms\n"
        "llama_perf_context_print: prompt eval time =     380.00 ms /"
        "   520 tokens (1368.42 tokens per second)\n"
        "llama_perf_context_print:        eval time =    2160.00 ms /"
        "   170 runs   (78.70 tokens per second)\n"
        "llama_perf_context_print:       total time =    3960.00 ms /"
        "   690 tokens\n"
    )
    evidence = _evidence(stderr=stderr, admitted=False)
    assert evidence["llama_cpp_timing"]["source"] == "llama_perf_context_print"
    assert evidence["llama_cpp_placement"]["source"] == "llm_load_tensors"
    result = _base_result(tmp_path, evidence=evidence, runtime={})
    _write(tmp_path, result)
    assert validate_result_dir(tmp_path) == []


def test_legacy_evidence_without_raw_lines_still_valid(tmp_path: Path) -> None:
    evidence = {
        "schema_version": NATIVE_EXECUTION_EVIDENCE_SCHEMA,
        "prompt_id": "prompt",
        "request_wall_time_seconds": 1.25,
        "request_wall_time_boundary": "process_launch_to_terminal_output_receipt",
        "llama_cpp_timing": {
            "load_time_seconds": 1.42,
            "prompt_eval_time_seconds": 0.38,
            "prompt_eval_token_count": 520,
            "prompt_eval_tps": 1368.42,
            "eval_time_seconds": 2.16,
            "eval_token_count": 170,
            "generation_tps": 78.7,
            "total_time_seconds": 3.96,
            "source": "llama_perf_context_print",
        },
        "llama_cpp_placement": {
            "offloaded_layers": 20,
            "total_layers": 41,
            "observed": "hybrid_accelerator_cpu",
            "source": "llm_load_tensors",
        },
        "failure": None,
    }
    result = _base_result(tmp_path, evidence=evidence, runtime={})
    _write(tmp_path, result)
    assert validate_result_dir(tmp_path) == []


def test_no_current_capture_result_remains_valid(tmp_path: Path) -> None:
    evidence = _evidence(stderr="answer only\n", admitted=False)
    result = _base_result(tmp_path, evidence=evidence, runtime={})
    _write(tmp_path, result)
    assert validate_result_dir(tmp_path) == []


def test_compact_trailer_populates_generic_metrics_not_native() -> None:
    from llmgauge.core.metrics import parse_llama_metrics

    metrics = parse_llama_metrics("[ Prompt: 368.9 t/s | Generation: 93.0 t/s ]")
    assert metrics["prompt_eval_tps"] == 368.9
    assert metrics["generation_tps"] == 93.0
    # the same trailer is not native timing evidence
    parsed = parse_llama_cpp_diagnostics(
        "[ Prompt: 368.9 t/s | Generation: 93.0 t/s ]",
        stderr="[ Prompt: 368.9 t/s | Generation: 93.0 t/s ]",
        current_diagnostics_admitted=True,
    )
    assert parsed["llama_cpp_timing"]["source"] is None
    assert parsed["slot_print_timing"]["availability"] == "unavailable"
