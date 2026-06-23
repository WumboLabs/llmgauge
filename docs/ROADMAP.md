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

## Later milestones

- comparison/report workflow polish
- example public report bundle
- expanded Practical Eval v1 prompt set
- richer installed-CLI validation
- Monolith import polish
