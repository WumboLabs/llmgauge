# Monolith Bridge Contract

This document defines the conservative file-based contract between LLMGauge and Monolith.

LLMGauge is the evaluation engine. Monolith may consume LLMGauge outputs, but LLMGauge should not depend on Monolith internals.

## Design goals

- Keep LLMGauge usable without Monolith.
- Keep Monolith integration file-based and inspectable.
- Avoid direct writes to Monolith SQLite databases from LLMGauge.
- Preserve raw model outputs.
- Keep result artifacts portable across machines.
- Make validation possible before import.
- Avoid private absolute paths where public/exported metadata is expected.
- Keep backwards compatibility with old Monolith Quant Lab imports.

## Non-goals

- No direct Monolith database mutation.
- No background daemon.
- No network service.
- No automatic model download.
- No model execution from Monolith-specific paths.
- No assumption that Monolith and LLMGauge live in the same parent directory.
- No migration or deletion of Monolith `quant_lab_*`, `context_scaling_*`, or `hermes_eval_*` tables.

## Ownership boundary

LLMGauge owns:

- prompt suite schema and validation
- evaluation execution
- llama.cpp/GGUF command construction
- raw prompt/output/log capture
- result directory layout
- context ladder execution
- synthetic context prompt generation
- agent-backend prompt suites
- manual scoring schema
- comparison report generation
- export/index artifacts
- engine-level reproducibility metadata

Monolith owns:

- local web UI
- dashboards and navigation
- model inventory/operator views
- setup diagnostics
- profile management UI
- importing LLMGauge artifacts
- local application database
- task state for Monolith-launched jobs
- annotations and review workflows
- backwards-compatible display of old Quant Lab/core-v2/Hermes data

## Stable artifacts Monolith may consume

### Single run result directory

A normal LLMGauge run directory may contain:

    llmgauge-result.json
    report.md
    raw/
    logs/

Monolith may treat `llmgauge-result.json` as the primary machine-readable artifact and `report.md` as the human-readable summary.

Raw outputs and logs should remain available for audit.

### Context ladder directory

A context ladder directory may contain:

    ladder-summary.json
    ladder-report.md
    ctx-8192/
    ctx-16384/
    ctx-32768/

Each child `ctx-*` directory is a normal single run result directory.

Monolith may consume `ladder-summary.json` as the primary machine-readable artifact and use child result directories for detail views.

### Export index

An export index may contain:

    llmgauge-index.json

The index schema is:

    llmgauge.export_index.v0

The export index is a discovery artifact. It helps Monolith find and classify LLMGauge result directories before import.

It is not a database replacement.

### Comparison report

A comparison report is currently Markdown-first.

Monolith may link to or render the Markdown report, but should not rely on its exact table formatting as a stable machine-readable schema.

## Recommended import flow

1. User selects or points Monolith at an LLMGauge result directory or export index.
2. Monolith checks for known artifact files:
   - `llmgauge-result.json`
   - `ladder-summary.json`
   - `llmgauge-index.json`
   - `report.md`
   - `ladder-report.md`
3. Monolith validates artifacts where possible.
4. Monolith imports metadata into its own database.
5. Monolith stores source path, schema version, import timestamp, and artifact references.
6. Monolith keeps links to raw artifacts rather than copying or rewriting them by default.

## Validation expectations

Before import, a normal result directory should pass:

    uv run llmgauge validate-result <result-dir>

A suite should pass:

    uv run llmgauge validate-suite <suite-dir>

A result collection can be indexed with:

    uv run llmgauge export-index <result-dir> [<result-dir> ...] --out <index-json>

Context ladder validation should verify:

- `ladder-summary.json` exists.
- every child run listed in `child_runs` exists.
- every completed child run has a valid `llmgauge-result.json`.
- failed child runs preserve error information.

## Output naming

LLMGauge supports explicit output paths:

    uv run llmgauge run ... --out results/my-run

LLMGauge also supports automatic timestamped output directories:

    uv run llmgauge run ... --auto-name --runs-root results --run-name agent-backend-smoke

Auto-named directories follow this pattern:

    YYYY-MM-DD_HH-MM-SS-name-slug-001

This is intended to make Monolith import/discovery workflows predictable without making LLMGauge a database application.

## Metadata policy

LLMGauge result metadata should avoid exposing private data where possible.

Current policy:

- model paths are redacted in public result metadata
- raw prompts are preserved as artifacts
- raw outputs are preserved as artifacts
- runtime command metadata uses a redacted model path
- local config paths may still appear and may need future hardening before public release

## Versioning

Monolith should check schema versions before import.

Known schemas:

- `llmgauge.result.v0`
- `llmgauge.context_ladder.v0`
- `llmgauge.context_prompt.v0`
- `llmgauge.suite.v0`
- `llmgauge.export_index.v0`

Schema changes should be additive whenever possible.

## Backwards compatibility

Monolith should keep existing legacy data readable.

Do not drop or rewrite these table families as part of initial LLMGauge import support:

- `quant_lab_*`
- `context_scaling_*`
- `hermes_eval_*`

Do not break existing routes:

- `/eval`
- `/eval/imports/{id}`
- `/context`

Future Monolith LLMGauge support should be additive.

## Future bridge improvements

Potential later additions:

- JSON comparison reports
- dedicated ladder validation command
- richer score summaries
- import manifest hashes
- Monolith-side import preview
- Monolith-side manual scoring UI
- controlled Monolith launch UI for LLMGauge commands

## Boundary rule

If a feature can exist cleanly in LLMGauge without Monolith, implement it in LLMGauge first.

If a feature is visual, interactive, dashboard-oriented, or application-state-oriented, implement it in Monolith later.
