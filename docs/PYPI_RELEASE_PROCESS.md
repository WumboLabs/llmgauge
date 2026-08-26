# PyPI release process

This document defines LLMGauge's repository-side release machinery and the
human configuration gates required before any package reaches TestPyPI or
PyPI.

Current state:

- Production PyPI is NOT active. `llmgauge` has not been published to
  production PyPI yet.
- TestPyPI publication is PROVEN: the Trusted Publisher published
  llmgauge 0.73.0, an independent fresh-environment installation from TestPyPI
  succeeded, and installed package resources (including Generic Core) were
  validated. The TestPyPI project exists.
- A production pending Trusted Publisher is configured on PyPI
  (owner: `WumboLabs`, repository: `llmgauge`, workflow: `release.yml`,
  environment: `pypi`). A pending publisher does NOT reserve the project name.
- The GitHub `pypi` environment is configured with a required reviewer,
  deployment restricted to tags matching `v*`, self-review prevention
  disabled, administrator bypass disabled, and no secrets or variables.

The workflow never publishes on branch pushes, pull requests, schedules, or
manual dispatches to production.

## Workflow architecture

Two intentionally different publication paths share one build job:

| Path | Trigger | Environment | Index |
|---|---|---|---|
| TestPyPI | manual `workflow_dispatch` only | `testpypi` | `https://test.pypi.org/legacy/` |
| PyPI | push of tag `v*` only | `pypi` | default PyPI |

- The `build` job checks out the exact ref, validates the release tag and
  (for tag pushes) that an annotated tag resolves to the checked-out commit
  via `scripts/check_release_tag.py`, runs the frozen dependency install,
  full test suite, and Ruff, builds with `uv build`, validates artifact
  contents with `scripts/check_release_dist.py`, and uploads exactly the two
  distribution files as the `python-package-distributions` artifact.
- The `publish-testpypi` and `publish-pypi` jobs download that exact
  artifact and publish it with OIDC (`id-token: write`, no rebuild). The
  bits validated by `build` are the bits uploaded to the index.
- A reused version fails at the index; nothing skips or overwrites existing
  releases.
- Concurrency is serialized per event/ref (`cancel-in-progress: false`), so
  a duplicate run waits instead of racing or cancelling an in-flight
  publication.

## Tag ↔ version contract

Accepted mapping, enforced fail-closed by `scripts/check_release_tag.py`:

    vX.Y       <-> X.Y.0      (preferred for `.0` releases)
    vX.Y.Z     <-> X.Y.Z
    vX.Y[.Z]S  <-> X.Y[.Z]S   (prerelease suffix S: aN, bN, rcN)

Examples against package version `0.74.0`: `v0.74` passes, `v0.74.0`
passes, `v0.74.1` fails, `v0.75` fails, `0.74` and other arbitrary strings
fail. Production tag-push builds additionally require the tag to be
annotated and to resolve to the exact checked-out commit.

Manual TestPyPI dispatches do not need a release tag; they are
pre-release mechanics tests of whatever ref is dispatched.

## TestPyPI gate: COMPLETED AND PROVEN

The first TestPyPI publication gate was completed deliberately, in order:

1. The pending Trusted Publisher was registered on TestPyPI:
   owner `WumboLabs`, repository `llmgauge`, workflow `release.yml`,
   environment `testpypi`.
2. The release workflow ran manually from a reviewed ref
   (Actions → Release → Run workflow).
3. Publication of llmgauge 0.73.0 to TestPyPI succeeded.
4. An independent fresh-environment installation from TestPyPI succeeded
   (`uv pip install --index-url https://test.pypi.org/simple/ llmgauge`),
   and installed package resources (including Generic Core) were validated.

No API token was created or stored anywhere for this flow. A manual dispatch
can never select the production index.

## HUMAN gate: first production PyPI publication (next)

The human configuration is complete: the production pending Trusted
Publisher exists on PyPI, and the GitHub `pypi` environment is protected with
a required reviewer and `v*`-only deployment restriction; administrator
bypass is disabled and the environment holds no secrets or variables. The
remaining flow is deliberate and human-gated:

1. Review and accept the prepared release branch on its release-prep branch;
   the human stages and commits the release-prep changes.
2. Merge to `main` and run full post-merge validation.
3. Push `main` to the remote.
4. Create the annotated release tag:
   `git tag -a v0.74 -m "LLMGauge v0.74.0"`.
5. Push the tag: `git push origin v0.74`. This triggers the Release workflow.
6. The workflow validates tag/version/exact-commit identity, runs tests,
   builds once with `uv build --no-create-gitignore`, validates the exact
   distribution contents, uploads exactly those artifacts, and waits on the
   protected `pypi` environment approval.
7. The required reviewer approves the production deployment.
8. Trusted Publishing uploads the exact built artifacts via OIDC — no token.
9. Verify independently by installing from PyPI in a clean environment
   (`uv tool install llmgauge`, then `llmgauge --version`) and inspecting the
   PyPI project page rendering.

A *pending* publisher does not reserve the `llmgauge` name on production
PyPI either; the namespace is claimed by the first successful upload.

## Claim boundaries

- Structural validation (tests, Ruff, artifact checks) does not prove
  answer quality; see [PUBLIC_REPORTING.md](PUBLIC_REPORTING.md).
- Publication proves availability, not model-ranking claims.
- Never store recovery codes, tokens, or credentials in Git.
