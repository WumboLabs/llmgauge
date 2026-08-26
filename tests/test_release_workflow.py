"""Security-sensitive contract tests for the release workflow shape.

These tests protect the publication architecture, not the YAML formatting.
They load the workflow with ``yaml.BaseLoader`` so GitHub Actions' top-level
``on`` key is preserved as a string instead of being coerced to boolean by
YAML 1.1 parsing.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

REPOSITORY_ROOT = Path(__file__).parents[1]
WORKFLOW_PATH = REPOSITORY_ROOT / ".github" / "workflows" / "release.yml"

SHA_PIN = re.compile(r"^[A-Za-z0-9_./-]+@[0-9a-f]{40}$")


@pytest.fixture(scope="module")
def workflow() -> dict:
    assert WORKFLOW_PATH.is_file()
    loaded = yaml.load(
        WORKFLOW_PATH.read_text(encoding="utf-8"), Loader=yaml.BaseLoader
    )
    assert isinstance(loaded, dict)
    return loaded


def _jobs(workflow: dict) -> dict:
    return workflow["jobs"]


def test_workflow_exists() -> None:
    assert WORKFLOW_PATH.is_file()


def test_production_trigger_is_version_tag_push_only(workflow: dict) -> None:
    triggers = workflow[True] if True in workflow else workflow["on"]
    assert isinstance(triggers["push"], dict)
    assert list(triggers["push"]["tags"]) == ["v*"]


def test_manual_dispatch_trigger_exists(workflow: dict) -> None:
    triggers = workflow[True] if True in workflow else workflow["on"]
    assert "workflow_dispatch" in triggers


def test_no_pull_request_trigger(workflow: dict) -> None:
    triggers = workflow[True] if True in workflow else workflow["on"]
    assert "pull_request" not in triggers


def test_no_branch_or_main_publication_trigger(workflow: dict) -> None:
    triggers = workflow[True] if True in workflow else workflow["on"]
    push = triggers["push"]
    assert "branches" not in push
    # The only non-dispatch trigger is the version-tag push.
    assert set(push.keys()) == {"tags"}


def test_no_workflow_dispatch_input_can_select_production(workflow: dict) -> None:
    triggers = workflow[True] if True in workflow else workflow["on"]
    dispatch = triggers["workflow_dispatch"]
    assert not dispatch or "inputs" not in dispatch


def test_build_job_has_no_oidc_write_permission(workflow: dict) -> None:
    build = _jobs(workflow)["build"]
    permissions = build.get("permissions") or {}
    assert permissions.get("id-token", "none") != "write"
    assert permissions == {"contents": "read"}


def test_testpypi_job_has_oidc_write_permission(workflow: dict) -> None:
    permissions = _jobs(workflow)["publish-testpypi"]["permissions"]
    assert permissions == {"id-token": "write"}


def test_pypi_job_has_oidc_write_permission(workflow: dict) -> None:
    permissions = _jobs(workflow)["publish-pypi"]["permissions"]
    assert permissions == {"id-token": "write"}


def test_testpypi_job_uses_testpypi_environment(workflow: dict) -> None:
    environment = _jobs(workflow)["publish-testpypi"]["environment"]
    assert environment["name"] == "testpypi"
    assert "test.pypi.org" in environment["url"]


def test_pypi_job_uses_pypi_environment(workflow: dict) -> None:
    environment = _jobs(workflow)["publish-pypi"]["environment"]
    assert environment["name"] == "pypi"
    assert environment["url"].startswith("https://pypi.org/")


def test_testpypi_job_is_dispatch_only(workflow: dict) -> None:
    condition = _jobs(workflow)["publish-testpypi"]["if"]
    assert condition.strip() == "github.event_name == 'workflow_dispatch'"


def test_pypi_job_is_tag_push_only(workflow: dict) -> None:
    condition = _jobs(workflow)["publish-pypi"]["if"]
    assert "github.event_name == 'push'" in condition
    assert "refs/tags/v" in condition


def test_no_pypi_token_or_password_secrets(workflow: dict) -> None:
    text = WORKFLOW_PATH.read_text(encoding="utf-8")
    lowered = text.lower()
    for forbidden in ("secrets.pypi", "password:", "api_token", "api-token"):
        assert forbidden not in lowered


def test_build_artifact_uploaded_once_and_downloaded_by_publish_jobs(
    workflow: dict,
) -> None:
    jobs = _jobs(workflow)
    build_steps = [step.get("uses", "") for step in jobs["build"]["steps"]]
    uploads = [use for use in build_steps if "actions/upload-artifact" in use]
    assert len(uploads) == 1
    upload_step = next(
        step
        for step in jobs["build"]["steps"]
        if "upload-artifact" in step.get("uses", "")
    )
    artifact_name = upload_step["with"]["name"]

    for job_name in ("publish-testpypi", "publish-pypi"):
        downloads = [
            step
            for step in jobs[job_name]["steps"]
            if "actions/download-artifact" in step.get("uses", "")
        ]
        assert len(downloads) == 1
        assert downloads[0]["with"]["name"] == artifact_name


def test_publish_jobs_never_rebuild(workflow: dict) -> None:
    for job_name in ("publish-testpypi", "publish-pypi"):
        for step in _jobs(workflow)[job_name]["steps"]:
            script = str(step.get("run", ""))
            assert "uv build" not in script
            assert "python -m build" not in script


def test_build_invocation_suppresses_gitignore_creation(workflow: dict) -> None:
    build_steps = [
        str(step.get("run", ""))
        for step in _jobs(workflow)["build"]["steps"]
        if step.get("name") == "Build distribution"
    ]
    assert len(build_steps) == 1
    script = build_steps[0]
    assert "rm -rf dist" in script
    assert "uv build --no-create-gitignore --out-dir dist" in script


def _all_step_uses(workflow: dict) -> list[str]:
    uses = []
    for job in _jobs(workflow).values():
        for step in job["steps"]:
            if "uses" in step:
                uses.append(step["uses"])
    return uses


def test_publish_action_pinned_to_full_commit_sha(workflow: dict) -> None:
    publish_uses = [
        use for use in _all_step_uses(workflow) if "gh-action-pypi-publish" in use
    ]
    assert len(publish_uses) == 2
    for use in publish_uses:
        assert SHA_PIN.match(use), f"publish action is not SHA-pinned: {use}"


def test_all_third_party_actions_are_sha_pinned(workflow: dict) -> None:
    for use in _all_step_uses(workflow):
        assert SHA_PIN.match(use), f"action is not pinned to a full commit SHA: {use}"
        assert not use.endswith("@main")
        assert not re.search(r"@\w+\.\d+$|@v\d+$", use)


def test_testpypi_endpoint_not_used_by_production_job(workflow: dict) -> None:
    jobs = _jobs(workflow)

    def job_text(job: dict) -> str:
        return repr(job).lower()

    assert "test.pypi.org" not in job_text(jobs["publish-pypi"])
    assert "test.pypi.org/legacy/" in job_text(jobs["publish-testpypi"])


def test_no_skip_existing_concealment(workflow: dict) -> None:
    text = WORKFLOW_PATH.read_text(encoding="utf-8").lower()
    assert "skip-existing" not in text


def test_release_tag_validator_runs_for_tag_push_builds(workflow: dict) -> None:
    steps = _jobs(workflow)["build"]["steps"]
    validator_steps = [
        step for step in steps if "check_release_tag.py" in str(step.get("run", ""))
    ]
    assert len(validator_steps) == 1
    condition = validator_steps[0].get("if", "")
    assert "github.event_name == 'push'" in condition


def test_concurrency_prevents_duplicate_publication_races(workflow: dict) -> None:
    concurrency = workflow["concurrency"]
    assert concurrency["cancel-in-progress"] == "false"


def test_top_level_permissions_are_none(workflow: dict) -> None:
    assert not workflow.get("permissions")
