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

## HUMAN gate: first production PyPI publication (executed 2026-08-27)

The step-by-step flow below was executed for the first production
publication: v0.74.0 was published to production PyPI on 2026-08-27 (UTC
2026-08-27T00:20Z) after the protected `pypi` environment reviewer approved
the deployment. The numbered flow is retained below as the standing release
procedure for future releases; the remaining text historically described the
first publication and is preserved for reference.

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
## Publication failure response and recovery procedures

Published PyPI files and versions are permanently immutable. They cannot be
overwritten, replaced, or deleted through normal project-owner controls. Do
not re-upload under the same version, do not reuse a published version, and
do not pretend a published version never existed. These procedures follow
current official PyPI guidance (docs.pypi.org/project-management/yanking and
/storage-limits; packaging.python.org/specifications/file-yanking).

### A. Failed build before publication

Nothing was published. Fix the failing build on a bounded branch, validate
(`uv run pytest -q`, `uv run ruff check .`, `git diff --check`, artifact
checks), merge, push `main`, create the tag, push it, and let the workflow
rebuild. No user-visible impact and no PyPI state change.

### B. Failed publish before any files accepted

No version is claimed by PyPI until the first file of a release is accepted.
Diagnose the publish job failure, correct the cause, validate, and retry the
publish job (or re-push the tag if the workflow requires it). The version
remains usable as long as no file was uploaded for it.

### C. Partial publication failure

PyPI rejects mixed/partial uploads of the same release: if some files were
accepted but the release is incomplete, do not re-upload expecting strict
replacement of identical filenames. Assess which files landed. If the release
must change, yank that release (release-level) and publish a corrected
release under a new version. Identical-content re-upload of the intended file
set for the same version is permissible; different content requires a new
version.

### D. Bad published release

Yank the release with a concise reason (for example "broken wheel; use
X.Y.Z"). Yanked files remain downloadable for exact pins but installers
avoid the release under normal resolution. Never overwrite the files. Then
publish the corrected fix under a new version.

### E. Yank criteria and procedure

Yanking is release-level and reversible metadata, not deletion. Use it for
defective, uninstallable, or vulnerable releases (security issues: yank
promptly, publish the fix, communicate). The yanked release's files and
hashes stay stable, so existing lock files and pinned deployments keep
working. Deletion is permanent and reserved for exceptional accidental or
sensitive-data publications; assess downstream pinned-installation impact
first.

### F. Immutable version rule

One version maps to exactly one immutable content set, forever. To change
behavior, bump the version. LLMGauge's `vX.Y` ↔ `X.Y.0` tag mapping and the
`scripts/check_release_tag.py` exact-commit guard keep the tag and version
tied to one immutable release.

### G. Bad/moved tag incident

The Release workflow's tag guard rejects a tag whose version does not match
`pyproject.toml` or whose commit is not the exact main HEAD. A tag is not
rewritten after push (no history rewriting or force pushes in this project).
If a tag must be corrected *before* any publication, and only then, it may be
deleted and recreated while unpublished; once a release is published, treat
the tag as immutable and record corrections in a new patch release instead.

### H. Compromised Trusted Publisher response

Trusted Publishing uses OIDC, so there are no long-lived tokens to rotate,
but a compromised or unexpected publisher mapping must be treated as a
production-security incident: revoke the Trusted Publisher mapping in the
PyPI project's publish settings, confirm the GitHub `pypi` environment still
requires a reviewer with administrator bypass disabled, yank any affected
published release, and publish a corrected version only after reconfiguration
and manual review. Never introduce a token-based fallback.

### I. Publisher revocation

Revoke by removing the GitHub Trusted Publisher entry in the PyPI project
settings (and, if needed, the GitHub `pypi` environment's deployment entry).
This stops all workflow-driven production uploads. Restore only after
reconfiguration by the human and verification in a fresh TestPyPI path.

### J. Patch-release recovery

For a defect in a published version: yank it if needed, bump the package
version (for example 0.74.1 → tag `v0.74` cannot be reused; use the matching
`v0.74.x` tag per the tag↔version contract), then follow the normal release
procedure: main merge, full validation, tag push, protected-environment
approval, publication, independent install verification. Never reuse a
published version number.

No fallback to secrets or tokens exists or will be added; OIDC Trusted
Publishing remains the only production publish path.
