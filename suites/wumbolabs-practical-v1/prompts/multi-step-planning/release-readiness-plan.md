You are reviewing whether a local LLM evaluation CLI is ready to tag a documentation-focused release.

Current state:
- The previous release is already tagged.
- The release has added evaluation tier docs.
- The release has added practical evaluation prompt quality docs.
- The release has added a seed practical evaluation suite.
- The release has added suite-aware score templates and label validation.
- The user wants conservative, reproducible releases.
- The user does not want to overclaim model quality.
- The project uses `uv run ruff check .` and `uv run pytest` as release gates.

Task:
Create a release-readiness plan for the tag.

Requirements:
- Use 12 bullets or fewer.
- Separate blockers from optional polish.
- Include docs checks, suite validation, scoring workflow checks, and final git/tag checks.
- Include what claims the release can and cannot make.
- Include rollback/revert guidance.
- Do not suggest running real model evaluations as part of unit tests.
