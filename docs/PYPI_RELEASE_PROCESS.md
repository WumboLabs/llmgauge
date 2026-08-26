# PyPI release process

This document defines LLMGauge's repository-side release machinery and the
human configuration gates required before any package reaches TestPyPI or
PyPI.

Current state:

- Production PyPI is NOT active. `llmgauge` has never been published to PyPI.
- TestPyPI is NOT configured yet.
- `.github/workflows/release.yml` is repository readiness only. Its first
  publication-capable execution is a deliberate human TestPyPI gate.
- The currently validated installation path remains Git-tag installation,
  documented in [INSTALL.md](INSTALL.md).

The workflow never publishes on branch pushes, pull requests, schedules, or
manual dispatches to production. There is no API token anywhere in the
release path: both publish jobs authenticate exclusively through
[Trusted Publishing](https://docs.pypi.org/trusted-publishers/) (OIDC).

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

Examples against package version `0.73.0`: `v0.73` passes, `v0.73.0`
passes, `v0.73.1` fails, `v0.74` fails, `0.73` and other arbitrary strings
fail. Production tag-push builds additionally require the tag to be
annotated and to resolve to the exact checked-out commit.

Manual TestPyPI dispatches do not need a release tag; they are
pre-release mechanics tests of whatever ref is dispatched.

## HUMAN gate: first TestPyPI publication

Perform these steps deliberately, in order:

1. Create/sign into a TestPyPI account and enable mandatory account
   security such as two-factor authentication.
2. Register the pending Trusted Publisher on TestPyPI:
   - owner: `WumboLabs`
   - repository: `llmgauge`
   - workflow: `release.yml`
   - environment: `testpypi`
3. Create the matching GitHub `testpypi` environment on the repository if
   desired (optional; lighter-weight than production). Do not store any
   secret in it — none is needed.
4. Run the release workflow manually from the reviewed ref
   (Actions → Release → Run workflow).
5. Approve the environment if a protection rule requires it.
6. Independently inspect the run, then verify by installing from TestPyPI:
   `uv pip install --index-url https://test.pypi.org/simple/ llmgauge`
   (or the pip equivalent) in a scratch environment.

Notes:

- No API token should be created or stored anywhere for this flow.
- A *pending* publisher does not reserve the `llmgauge` name on TestPyPI;
  the namespace is claimed by the first successful upload.
- A manual dispatch can never select the production index.

## HUMAN gate: production PyPI (later)

1. Establish the PyPI account/security posture (2FA).
2. Register the pending Trusted Publisher on PyPI with the same owner,
   repository, and workflow values, but environment `pypi`.
3. Create the GitHub `pypi` environment as protected: require reviewer
   approval; restrict deployment branches/tags to release tags where
   supported. If a second authorized reviewer exists, self-review can be
   prevented; do not assume one exists.
4. Cut the accepted release commit/version/tag per the release policy
   (`vX.Y` preferred) and push the annotated tag only after review.
5. Approve the production environment when the workflow runs.
6. Verify independently by installing from PyPI in a clean environment.

## Claim boundaries

- Structural validation (tests, Ruff, artifact checks) does not prove
  answer quality; see [PUBLIC_REPORTING.md](PUBLIC_REPORTING.md).
- Publication proves availability, not model-ranking claims.
- Never store recovery codes, tokens, or credentials in Git.
