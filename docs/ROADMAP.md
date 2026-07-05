# LLMGauge Roadmap

This roadmap is conservative and may change as real local testing exposes friction.

## Current direction

LLMGauge should become a practical, independently usable local LLM evaluation bench before publishing many model findings. Priority is external usability, reproducible workflows, clear artifacts, and honest claim boundaries.

## Near-term milestones

### v0.30: first-run command polish and model-profile onboarding

Goals:

- make local setup easier to initialize
- make configured model profiles easier to inspect
- reduce first-run confusion around config/profile paths
- keep behavior explicit and conservative

Planned or active work:

- `llmgauge init-config`
- `llmgauge list-model-profiles`
- `llmgauge doctor` local config/profile auto-detection
- quickstart updates for the shorter first-run path

### v0.31: run command ergonomics

Potential work:

- consider default local config/profile discovery for `run`
- print resolved config/model profile/model path summary before execution
- improve error messages for missing model profile, missing model path, and missing llama-cli
- keep direct explicit flags supported

### v0.32: run-ladder preflight

Goals:

- make multi-context ladder execution inspectable before GPU work
- preview parsed context ladders, selected prompt count, model/profile resolution, and child output plans
- avoid creating ladder/result directories in dry-run mode

### v0.33: Fit Ladder foundation

Goals:

- add context-first fallback planning helpers
- classify OOM, process-killed, and generic runtime failures
- define attempt records and fit-ladder summary structures
- keep execution opt-in and avoid silent fallback in normal commands

### v0.34: Fit Ladder execution loop

Potential work:

- add an explicit fit-ladder command or option
- execute planned attempts in bounded order
- preserve failed attempt artifacts
- print retry status such as `OOM detected at ctx=65536; retrying at ctx=32768`
- lower context first, then batch/ubatch if configured
- keep GPU-layer fallback explicit only

See `docs/FIT_LADDER.md`.

### v0.35: Fit Ladder artifact polish

Goals:

- validate Fit Ladder artifact directories
- index Fit Ladder artifacts through export-index
- write human-readable Fit Ladder reports
- preserve conservative claim boundaries around requested vs selected settings

## Later milestones

- comparison/report workflow polish
- example public report bundle
- expanded Practical Eval v1 prompt set
- richer installed-CLI validation
- downstream import polish

## Future GitHub and branch-name maintenance

- Use `main` as the default branch name for new GitHub repositories going forward.
- Keep existing LLMGauge `master` branch as-is unless a separate branch-rename maintenance task is intentionally scheduled.
- If LLMGauge is later renamed from `master` to `main`, handle it as a standalone compatibility task:
  - update GitHub default branch settings before deleting or retiring `master`
  - review branch protection and repository rules
  - update docs, badges, scripts, release notes, and examples that mention `master`
  - verify local and remote tracking branches after the rename
  - avoid bundling the rename with feature work or release-critical fixes
- Future CLI polish idea: keep `--model-profile` as the configured model selector, and consider adding `--model-profile-file` as the clearer preferred name for the YAML file path currently passed with `--model-profiles`.
- If `--model-profile-file` is added, keep `--model-profiles` as a compatibility alias for at least one release cycle and document the transition clearly.

## Future LocalMaxxing integration interest

Interest pending; not a current development priority.

LLMGauge and LocalMaxxing solve different problems:

- LLMGauge focuses on reproducible quality evaluation and reporting.
- LocalMaxxing focuses on standardized public `llama-bench` performance benchmarking.

A future optional addon could allow LLMGauge to export, or optionally submit,
LocalMaxxing-compatible benchmark payloads after a standard `llama-bench` run.

Possible future commands:

- `llmgauge export-localmaxxing`
- `llmgauge submit-localmaxxing`

Design constraints:

- entirely optional
- no LocalMaxxing dependency for normal LLMGauge users
- no automatic network or API activity
- no change to LLMGauge's primary quality-evaluation mission
- optional benchmark IDs could be stored as supplemental metadata in LLMGauge result artifacts

Revisit only if there is sufficient user demand or a future collaboration opportunity with LottoLabs/LocalMaxxing.

## Completed v0.43 runtime metadata trust work

v0.43 made runtime settings that affect reproducibility visible in artifacts and reports.

Completed scope:

- added explicit `--flash-attn auto|on|off`
- allowed `flash_attn` in model profiles and default config
- stored `runtime.flash_attn` in result JSON
- showed Flash attention in run reports and comparison reports
- added explicit runtime methodology labels such as `stock-reference`, `daily-tuned`, or `experimental`
- kept power-limit and deeper GPU telemetry capture for a later, separate slice

## Active v0.44 public-understandable documentation work

Current focus: make the repository understandable to a technically curious public user without requiring prior project context.

Initial v0.44 scope:

- refresh README as a concise public front door
- make the source-checkout workflow explicit with `uv run llmgauge ...`
- keep installed CLI usage separate from development/source-checkout usage
- clarify the first-run path in Quickstart
- keep public install/package polish for a later release

## Future user-friendly installation and onboarding

Goal: make LLMGauge feel like a normal installed CLI tool for users, while preserving the current `uv run` development workflow for contributors.

Current development workflow:

- `uv run llmgauge ...`
- `uv run pytest`
- `uv run ruff check .`

Target user workflow:

- `llmgauge doctor`
- `llmgauge init`
- `llmgauge model add ...`
- `llmgauge run ...`
- `llmgauge score ...`
- `llmgauge compare ...`

Planned direction:

1. Runtime reproducibility metadata and reporting
   - capture and report runtime settings that affect comparability
   - include fields such as power limit, batch, ubatch, flash-attn mode, llama.cpp build/commit, GPU name, driver version, model path/quant, and runtime profile metadata when available
   - avoid silently mixing tuned daily runs with stock/reference comparison artifacts

2. Installation and usage documentation split
   - clearly document normal installed CLI usage with `llmgauge ...`
   - separately document development usage with `uv run llmgauge ...`
   - explain editable local installs with `uv tool install --editable .`
   - add or improve `llmgauge --version` if needed

3. User config discovery
   - support user-level config under `~/.config/llmgauge/`
   - keep project-local config discovery for repo/development workflows
   - prefer explicit CLI paths over discovered config
   - keep built-in defaults conservative

4. `llmgauge init`
   - create initial user config files
   - configure the llama.cpp binary path
   - configure default results directory
   - optionally record default backend/runtime settings
   - keep the first version conservative and non-magical

5. Model onboarding polish
   - improve `llmgauge model add`
   - improve `llmgauge model list`
   - add or improve model update/remove flows if needed
   - validate missing model paths clearly
   - preserve the mental model that `--model-profile` selects a configured model and `--model-path` loads an exact GGUF file

6. Suite discovery and built-in suite aliases
   - add or improve `llmgauge suite list`
   - allow users to run built-in suites by ID rather than repo-relative paths
   - keep explicit suite paths supported for custom/local suites

7. Smoke-test workflow
   - add a simple `llmgauge smoke` path
   - run one short built-in prompt against a configured/default model
   - validate artifact creation
   - print the report path and next recommended command

8. Public install polish
   - support a clean GitHub install path first, such as `uv tool install git+https://github.com/WumboLabs/llmgauge`
   - consider PyPI later only when packaging, docs, versioning, and bundled suite behavior are stable
   - keep public quickstart examples free of machine-specific local paths

Non-goals:

- do not remove the `uv run` development workflow
- do not require network activity for normal runs
- do not make setup overly magical
- do not bundle unrelated feature work into installation polish
