# Publication Checklist

LLMGauge is suitable for private GitHub backup now. Public release should wait until the v0.13 hardening checkpoint.

## Before making the repository public

- Confirm no local config files are tracked.
- Confirm no generated `results/` artifacts are tracked.
- Confirm no generated `tmp/` artifacts are tracked.
- Confirm no `.venv/`, cache files, model files, GGUF files, SQLite files, secrets, tokens, or private machine paths are tracked.
- Review README for public-facing accuracy.
- Review examples for generic paths and model names.
- Review suite prompts for local/private assumptions.
- Decide license.
- Add issue templates if useful.
- Add release notes for public alpha.
- Confirm `uv run pytest` passes.
- Confirm `uv run ruff check .` passes.

## Current intended path

- v0.11: agent-backend suite.
- v0.12: Monolith bridge/export contract.
- v0.13: hardening and public-readiness review.
