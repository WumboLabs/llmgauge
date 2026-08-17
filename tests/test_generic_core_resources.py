import json
import os
from pathlib import Path
import subprocess
import tarfile
import venv
import zipfile

import pytest


REPOSITORY_ROOT = Path(__file__).parents[1]
SOURCE_SUITE_ROOT = REPOSITORY_ROOT / "suites"
BUILTIN_SUITE_ROOT = REPOSITORY_ROOT / "src/llmgauge/builtin_suites"
GENERIC_CORE_RESOURCE_ROOT = Path("generic-core-v1/fixtures/v0.1.0")
EXPECTED_GENERIC_CORE_FIXTURES = frozenset(
    {
        GENERIC_CORE_RESOURCE_ROOT / "bounded-context/policy-excerpts.json",
        GENERIC_CORE_RESOURCE_ROOT / "bounded-context/reconciliation.json",
        GENERIC_CORE_RESOURCE_ROOT / "coding/execution-limits.json",
        GENERIC_CORE_RESOURCE_ROOT / "coding/interval-function-cases.json",
        GENERIC_CORE_RESOURCE_ROOT / "deterministic/constraint-envelope.json",
        GENERIC_CORE_RESOURCE_ROOT / "deterministic/ledger-extraction.json",
        GENERIC_CORE_RESOURCE_ROOT / "deterministic/summary-envelope.json",
        GENERIC_CORE_RESOURCE_ROOT / "deterministic/tool-request.json",
        GENERIC_CORE_RESOURCE_ROOT / "deterministic/typed-record-json.json",
    }
)
EXPECTED_GENERIC_CORE_RESOURCES = EXPECTED_GENERIC_CORE_FIXTURES | frozenset(
    {
        Path("generic-core-v1/suite.yaml"),
        Path("generic-core-v1/prompts/generic-core-instruction-rewrite-01.md"),
        Path("generic-core-v1/prompts/generic-core-structured-json-01.md"),
        Path("generic-core-v1/prompts/generic-core-honesty-evidence-gap-01.md"),
        Path("generic-core-v1/prompts/generic-core-summary-decision-log-01.md"),
        Path("generic-core-v1/prompts/generic-core-extraction-ledger-01.md"),
        Path("generic-core-v1/prompts/generic-core-plan-dependencies-01.md"),
        Path("generic-core-v1/prompts/generic-core-explain-cache-protocol-01.md"),
        Path("generic-core-v1/prompts/generic-core-code-interval-merge-01.md"),
        Path("generic-core-v1/prompts/generic-core-review-window-average-01.md"),
        Path("generic-core-v1/prompts/generic-core-troubleshoot-staged-pipeline-01.md"),
        Path("generic-core-v1/prompts/generic-core-safety-risky-heating-01.md"),
        Path("generic-core-v1/prompts/generic-core-tool-record-lookup-01.md"),
        Path("generic-core-v1/prompts/generic-core-context-policy-reconcile-01.md"),
    }
)


def _files_below(root: Path) -> frozenset[Path]:
    return frozenset(
        path.relative_to(root)
        for path in root.rglob("*")
        if path.is_file()
        and path.name != "__init__.py"
        and path.suffix != ".pyc"
        and "__pycache__" not in path.parts
    )


@pytest.fixture(scope="module")
def built_distributions(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    dist_dir = tmp_path_factory.mktemp("generic-core-dist")
    subprocess.run(
        ["uv", "build", "--out-dir", str(dist_dir)],
        cwd=REPOSITORY_ROOT,
        check=True,
        timeout=120,
    )
    wheel = next(dist_dir.glob("*.whl"))
    sdist = next(dist_dir.glob("*.tar.gz"))
    return wheel, sdist


def test_generic_core_resource_inventory_and_mirror_are_exact() -> None:
    source_files = {
        Path("generic-core-v1") / path
        for path in _files_below(SOURCE_SUITE_ROOT / "generic-core-v1")
    }
    package_files = {
        Path("generic-core-v1") / path
        for path in _files_below(BUILTIN_SUITE_ROOT / "generic-core-v1")
    }

    assert source_files == EXPECTED_GENERIC_CORE_RESOURCES
    assert package_files == EXPECTED_GENERIC_CORE_RESOURCES
    for relative_path in EXPECTED_GENERIC_CORE_RESOURCES:
        source = SOURCE_SUITE_ROOT / relative_path
        packaged = BUILTIN_SUITE_ROOT / relative_path
        assert source.read_bytes() == packaged.read_bytes()
    for relative_path in EXPECTED_GENERIC_CORE_FIXTURES:
        source = SOURCE_SUITE_ROOT / relative_path
        assert json.loads(source.read_bytes())["version"] == "0.1.0"


def test_historical_suite_remains_source_only() -> None:
    historical = SOURCE_SUITE_ROOT / "wumbolabs-practical-use-v1"

    assert (historical / "suite.yaml").is_file()
    assert not (BUILTIN_SUITE_ROOT / historical.name).exists()


def test_wheel_and_sdist_include_exact_generic_core_resources(
    built_distributions: tuple[Path, Path],
) -> None:
    wheel, sdist = built_distributions
    wheel_prefix = "llmgauge/builtin_suites/"
    with zipfile.ZipFile(wheel) as archive:
        wheel_resources = {
            Path(name.removeprefix(wheel_prefix))
            for name in archive.namelist()
            if name.startswith(f"{wheel_prefix}generic-core-v1/")
            and not name.endswith("/")
        }
        assert wheel_resources == EXPECTED_GENERIC_CORE_RESOURCES
        assert not any(
            "wumbolabs-practical-use-v1" in name for name in archive.namelist()
        )

    with tarfile.open(sdist, "r:gz") as archive:
        members = [member for member in archive.getmembers() if member.isfile()]
        names = [member.name for member in members]
        package_marker = "/src/llmgauge/builtin_suites/"
        packaged_resources = {
            Path(name.split(package_marker, 1)[1])
            for name in names
            if f"{package_marker}generic-core-v1/" in name
        }
        assert packaged_resources == EXPECTED_GENERIC_CORE_RESOURCES
        assert not any("wumbolabs-practical-use-v1" in name for name in names)


def test_isolated_wheel_install_can_read_every_resource(
    built_distributions: tuple[Path, Path],
    tmp_path: Path,
) -> None:
    wheel, _ = built_distributions
    environment = tmp_path / "environment"
    venv.EnvBuilder(with_pip=False).create(environment)
    python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    subprocess.run(
        [
            "uv",
            "pip",
            "install",
            "--python",
            str(python),
            "--no-deps",
            str(wheel),
        ],
        cwd=tmp_path,
        check=True,
        timeout=120,
    )
    expected = sorted(path.as_posix() for path in EXPECTED_GENERIC_CORE_RESOURCES)
    fixtures = sorted(path.as_posix() for path in EXPECTED_GENERIC_CORE_FIXTURES)
    script = f"""
import importlib.resources
import json

root = importlib.resources.files('llmgauge.builtin_suites')
expected = {expected!r}
fixtures = {fixtures!r}
for relative in expected:
    payload = root.joinpath(relative).read_bytes()
    assert payload
for relative in fixtures:
    payload = root.joinpath(relative).read_bytes()
    assert json.loads(payload)['version'] == '0.1.0'
print(len(expected))
"""
    completed = subprocess.run(
        [str(python), "-I", "-c", script],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.stdout.strip() == str(len(EXPECTED_GENERIC_CORE_RESOURCES))
