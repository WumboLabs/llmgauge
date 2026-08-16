from __future__ import annotations

import io
import json
import urllib.error

import pytest
from typer.testing import CliRunner

from llmgauge.cli import app
from llmgauge.core import localmaxxing as lmx


runner = CliRunner()


def artifact() -> dict:
    return lmx.make_artifact(
        hf_id="Qwen/Qwen3-8B",
        quantization="Q4_K_M",
        model_path="model.gguf",
        engine_version="b10449+0d9ceae1e",
        backend="cuda",
        hardware={"hwClass": "DISCRETE_GPU", "gpuName": "RTX", "vramGb": 12},
        command="llama-bench -m model.gguf -p 512 -n 128 -b 2048 -ub 512 -ngl -1 -o json -r 1",
        executable="/opt/llama-bench",
        measurements=[
            {"tok_s_out": 10.0 + index, "tok_s_prefill": 100.0 + index}
            for index in range(5)
        ],
    )


def write_artifact(tmp_path) -> object:
    path = tmp_path / "benchmark.json"
    path.write_text(json.dumps(artifact()), encoding="utf-8")
    return path


def context(*, submit: bool = False) -> dict:
    meta = {
        "dryRunEndpoint": f"POST {lmx.API_ROOT}{lmx.DRY_RUN_PATH}",
        "submitEndpoint": f"POST {lmx.API_ROOT}{lmx.SUBMIT_PATH}",
    }
    if submit:
        return {"_meta": meta}
    return {"_meta": meta}


def openapi() -> dict:
    return {
        "info": {"version": lmx.API_VERSION},
        "paths": {lmx.DRY_RUN_PATH: {}, lmx.SUBMIT_PATH: {}},
    }


@pytest.mark.parametrize(
    "command",
    [
        ["localmaxxing", "--help"],
        ["localmaxxing", "run", "--help"],
        ["localmaxxing", "validate", "--help"],
        ["localmaxxing", "export", "--help"],
        ["localmaxxing", "dry-run", "--help"],
        ["localmaxxing", "submit", "--help"],
    ],
)
def test_localmaxxing_help(command: list[str]) -> None:
    result = runner.invoke(app, command)
    assert result.exit_code == 0
    assert "Usage:" in result.output


def test_checked_online_request_accepts_current_contract(monkeypatch) -> None:
    monkeypatch.setenv("LOCALMAXXING_API_KEY", "test-secret")
    calls = []

    def request(path, payload=None, api_key=None):
        calls.append((path, payload, api_key))
        if path == "/api/openapi.json":
            return openapi()
        return context() if path == lmx.AGENT_CONTEXT_PATH else {"valid": True}

    monkeypatch.setattr(lmx, "request_api", request)
    assert lmx.checked_online_request(artifact()) == {"valid": True}
    assert calls == [
        ("/api/openapi.json", None, None),
        (lmx.AGENT_CONTEXT_PATH, None, None),
        (lmx.DRY_RUN_PATH, lmx.export_payload(artifact()), "test-secret"),
    ]


@pytest.mark.parametrize(
    "response", [{}, {"_meta": []}, {"_meta": {"dryRunEndpoint": "/wrong"}}]
)
def test_checked_online_request_rejects_incompatible_context(
    monkeypatch, response
) -> None:
    monkeypatch.setenv("LOCALMAXXING_API_KEY", "test-secret")
    monkeypatch.setattr(lmx, "request_api", lambda *args: response)
    with pytest.raises(ValueError, match="contract mismatch"):
        lmx.checked_online_request(artifact())


def test_request_api_rejects_malformed_and_nonobject_responses(monkeypatch) -> None:
    class Response:
        def __init__(self, body):
            self.body = body

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return self.body

    monkeypatch.setattr(
        lmx.urllib.request, "urlopen", lambda *_args, **_kwargs: Response(b"{")
    )
    with pytest.raises(ValueError, match="malformed JSON"):
        lmx.request_api(lmx.AGENT_CONTEXT_PATH)
    monkeypatch.setattr(
        lmx.urllib.request, "urlopen", lambda *_args, **_kwargs: Response(b"[]")
    )
    with pytest.raises(ValueError, match="invalid response"):
        lmx.request_api(lmx.AGENT_CONTEXT_PATH)


def test_request_api_identifies_the_integration(monkeypatch) -> None:
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return b"{}"

    requests = []
    monkeypatch.setattr(
        lmx.urllib.request,
        "urlopen",
        lambda request, **_kwargs: requests.append(request) or Response(),
    )
    assert lmx.request_api(lmx.AGENT_CONTEXT_PATH) == {}
    assert requests[0].get_header("User-agent") == "LLMGauge LocalMaxxing integration"


@pytest.mark.parametrize("status", [400, 401, 404, 429, 500])
def test_request_api_reports_http_failures_without_response_body(
    monkeypatch, status: int
) -> None:
    error = urllib.error.HTTPError(
        "https://example.invalid", status, "failure", {}, io.BytesIO(b"secret")
    )
    monkeypatch.setattr(
        lmx.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(error),
    )
    with pytest.raises(ValueError, match=rf"HTTP {status}") as exc_info:
        lmx.request_api(lmx.DRY_RUN_PATH, {})
    assert "secret" not in str(exc_info.value)


def test_request_api_reports_network_failure_without_secret(monkeypatch) -> None:
    monkeypatch.setattr(
        lmx.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            urllib.error.URLError("secret")
        ),
    )
    with pytest.raises(ValueError, match="network failure") as exc_info:
        lmx.request_api(lmx.DRY_RUN_PATH, {})
    assert "secret" not in str(exc_info.value)


def test_dry_run_cli_requires_auth_without_network(tmp_path, monkeypatch) -> None:
    path = write_artifact(tmp_path)
    monkeypatch.delenv("LOCALMAXXING_API_KEY", raising=False)
    monkeypatch.setattr(
        lmx, "request_api", lambda *_args: pytest.fail("network called")
    )
    result = runner.invoke(app, ["localmaxxing", "dry-run", str(path)])
    assert result.exit_code != 0
    assert "LOCALMAXXING_API_KEY" in str(result.exception)


@pytest.mark.parametrize(
    "failure",
    [
        ValueError("HTTP 400"),
        ValueError("HTTP 401"),
        ValueError("HTTP 404"),
        ValueError("HTTP 429"),
        ValueError("HTTP 500"),
        ValueError("network failure"),
    ],
)
def test_dry_run_cli_reports_fail_closed_failures(
    tmp_path, monkeypatch, failure
) -> None:
    path = write_artifact(tmp_path)
    monkeypatch.setattr(
        lmx,
        "checked_online_request",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(failure),
    )
    result = runner.invoke(app, ["localmaxxing", "dry-run", str(path)])
    assert result.exit_code != 0
    assert str(failure) in str(result.exception)


def test_dry_run_cli_success_does_not_persist_key(tmp_path, monkeypatch) -> None:
    path = write_artifact(tmp_path)
    monkeypatch.setenv("LOCALMAXXING_API_KEY", "test-secret")
    monkeypatch.setattr(
        lmx, "checked_online_request", lambda *_args, **_kwargs: {"valid": True}
    )
    result = runner.invoke(app, ["localmaxxing", "dry-run", str(path)])
    assert result.exit_code == 0
    assert "test-secret" not in path.read_text(encoding="utf-8")
    assert "test-secret" not in result.output


def test_submit_dry_runs_before_successful_submission(tmp_path, monkeypatch) -> None:
    path = write_artifact(tmp_path)
    original = path.read_text(encoding="utf-8")
    calls = []

    def request(_artifact, *, submit=False):
        calls.append(submit)
        return {"valid": True} if not submit else {"id": "server-123"}

    monkeypatch.setattr(lmx, "checked_online_request", request)
    result = runner.invoke(
        app, ["localmaxxing", "submit", str(path), "--confirm-public"]
    )
    receipt = tmp_path / "localmaxxing-submission-receipt.json"
    assert result.exit_code == 0
    assert calls == [False, True]
    assert path.read_text(encoding="utf-8") == original
    assert json.loads(receipt.read_text(encoding="utf-8"))["server_id"] == "server-123"
    assert "test-secret" not in receipt.read_text(encoding="utf-8")


def test_submit_failed_dry_run_never_submits_or_writes_receipt(
    tmp_path, monkeypatch
) -> None:
    path = write_artifact(tmp_path)
    calls = []

    def request(_artifact, *, submit=False):
        calls.append(submit)
        raise ValueError("dry-run rejected")

    monkeypatch.setattr(lmx, "checked_online_request", request)
    result = runner.invoke(
        app, ["localmaxxing", "submit", str(path), "--confirm-public"]
    )
    assert result.exit_code != 0
    assert calls == [False]
    assert not (tmp_path / "localmaxxing-submission-receipt.json").exists()


def test_submit_failure_writes_no_receipt_and_duplicate_refuses_before_network(
    tmp_path, monkeypatch
) -> None:
    path = write_artifact(tmp_path)
    calls = []

    def request(_artifact, *, submit=False):
        calls.append(submit)
        if submit:
            raise ValueError("submit rejected")
        return {"valid": True}

    monkeypatch.setattr(lmx, "checked_online_request", request)
    result = runner.invoke(
        app, ["localmaxxing", "submit", str(path), "--confirm-public"]
    )
    receipt = tmp_path / "localmaxxing-submission-receipt.json"
    assert result.exit_code != 0 and calls == [False, True] and not receipt.exists()
    receipt.write_text("{}", encoding="utf-8")
    result = runner.invoke(
        app, ["localmaxxing", "submit", str(path), "--confirm-public"]
    )
    assert result.exit_code != 0 and calls == [False, True]


def test_offline_commands_and_ordinary_cli_never_use_network(
    tmp_path, monkeypatch
) -> None:
    path = write_artifact(tmp_path)
    monkeypatch.setattr(
        lmx, "request_api", lambda *_args: pytest.fail("network called")
    )
    assert runner.invoke(app, ["localmaxxing", "validate", str(path)]).exit_code == 0
    assert runner.invoke(app, ["localmaxxing", "export", str(path)]).exit_code == 0
    assert runner.invoke(app, ["version"]).exit_code == 0


def test_run_is_offline_and_executes_warmup_plus_five_measurements(
    tmp_path, monkeypatch
) -> None:
    model = tmp_path / "model.gguf"
    model.write_bytes(b"model")
    profiles = tmp_path / "profiles.yaml"
    profiles.write_text(
        "schema_version: llmgauge.model_profiles.v0\nmodels:\n  qwen:\n    path: "
        + str(model)
        + "\n    quant: Q4_K_M\n",
        encoding="utf-8",
    )
    base_output = json.dumps(
        [
            {
                "build_number": 10449,
                "build_commit": "0d9ceae1e",
                "n_prompt": 512,
                "n_gen": 0,
                "avg_ts": 100.0,
            },
            {"n_prompt": 0, "n_gen": 128, "avg_ts": 10.0},
        ]
    )
    combined_output = json.dumps(
        [
            {
                "build_number": 10449,
                "build_commit": "0d9ceae1e",
                "n_prompt": 512,
                "n_gen": 128,
                "avg_ts": 50.0,
            }
        ]
    )
    outputs = [combined_output] * 6 + [base_output] * 6
    commands = []
    monkeypatch.setattr(
        lmx, "request_api", lambda *_args: pytest.fail("network called")
    )
    monkeypatch.setattr(
        lmx,
        "run_llama_bench",
        lambda command: commands.append(command) or outputs.pop(),
    )
    result = runner.invoke(
        app,
        [
            "localmaxxing",
            "run",
            "--output",
            str(tmp_path / "output"),
            "--profile",
            "qwen",
            "--hf-id",
            "Qwen/Qwen3-8B",
            "--revision",
            "test-revision",
            "--gpu-name",
            "RTX",
            "--vram-gb",
            "12",
            "--model-profiles",
            str(profiles),
        ],
    )
    assert result.exit_code == 0, result.exception
    saved = lmx.load_artifact(tmp_path / "output")
    assert result.exit_code == 0 and len(commands) == 12
    assert commands[0][-14:] == [
        "-p",
        "512",
        "-n",
        "128",
        "-b",
        "2048",
        "-ub",
        "512",
        "-ngl",
        "-1",
        "-o",
        "json",
        "-r",
        "1",
    ]
    assert "-d" not in commands[0]
    assert saved["workload"]["batch_size"] == 1
    assert "-b 2048 -ub 512" in saved["command_provenance"]
    assert saved["workload"]["repetitions"] == 5
    assert saved["model"]["local_reference"] == "model.gguf"
    assert saved["model"]["revision"] == "test-revision"
    assert str(tmp_path) not in saved["command_provenance"]
    assert saved["engine"]["executable"] == "llama-bench"
    assert saved["engine"]["version"] == "b10449+0d9ceae1e"
    assert saved["combined_measurements"] == [50.0] * 5
    assert saved["aggregate"]["tok_s_total"] == 50.0
    assert commands[6][3:5] == ["-pg", "512,128"]


def test_run_rejects_unresolved_profile_and_missing_model(tmp_path) -> None:
    profiles = tmp_path / "profiles.yaml"
    profiles.write_text(
        "schema_version: llmgauge.model_profiles.v0\nmodels: {}\n", encoding="utf-8"
    )
    result = runner.invoke(
        app,
        [
            "localmaxxing",
            "run",
            "--output",
            str(tmp_path / "out"),
            "--profile",
            "missing",
            "--hf-id",
            "Qwen/Qwen3-8B",
            "--gpu-name",
            "RTX",
            "--vram-gb",
            "12",
            "--model-profiles",
            str(profiles),
        ],
    )
    assert result.exit_code != 0


def test_validate_cli_reports_valid_but_ineligible_artifact(tmp_path) -> None:
    value = artifact()
    value["model"]["hf_id"] = None
    value["fingerprint"] = lmx.fingerprint(value)
    path = tmp_path / "benchmark.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    result = runner.invoke(app, ["localmaxxing", "validate", str(path)])
    assert result.exit_code == 0
    assert "locally_valid" in result.output
    assert "localmaxxing_ineligible" in result.output
