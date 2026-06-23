You are reviewing whether LLMGauge v0.26 is ready to tag.

Current state:
- v0.25 is already released.
- v0.26 has added evaluation tier docs.
- v0.26 has added Practical Eval v1 prompt quality docs.
- v0.26 has added the 10-prompt seed Practical Eval v1 suite.
- v0.26 has added suite-aware score templates and label validation.
- The user wants conservative, reproducible releases.
- The user does not want to overclaim model quality.
- The project uses `uv run ruff check .` and `uv run pytest` as release gates.

Task:
Create a release-readiness plan for v0.26.

Requirements:
- Use 12 bullets or fewer.
- Separate blockers from optional polish.
- Include docs checks, suite validation, scoring workflow checks, and final git/tag checks.
- Include what claims v0.26 can and cannot make.
- Include rollback/revert guidance.
- Do not suggest running real model evaluations as part of unit tests.
