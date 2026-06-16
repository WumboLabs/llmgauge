# Monolith Import Example

This document records the proven LLMGauge-to-Monolith import workflow.

LLMGauge remains the evaluation engine. Monolith imports LLMGauge filesystem artifacts into its own database for display and indexing.

## Boundary

LLMGauge owns:

- evaluation execution
- result artifacts
- validation
- export indexes

Monolith owns:

- SQLite application database
- import records
- UI display
- dashboard state
- legacy Quant Lab/core-v2/Hermes compatibility

LLMGauge does not write directly to Monolith SQLite.

## Tested artifact types

Monolith currently supports importing:

- a single LLMGauge run directory
- a LLMGauge context ladder directory
- a LLMGauge export index JSON file containing one or more artifact references

Supported schema versions:

- `llmgauge.result.v0`
- `llmgauge.context_ladder.v0`
- `llmgauge.export_index.v0`

## Generate a single run artifact

Example:

    uv run llmgauge run \
      --suite suites/agent-backend-v1 \
      --only tool-honesty/fake-tool-resistance \
      --model-profile gemma4_12b_qat_q4 \
      --config examples/configs/llmgauge.local.yaml \
      --model-profiles examples/configs/model-profiles.local.yaml \
      --max-tokens 300 \
      --auto-name \
      --runs-root results \
      --run-name agent-backend-fake-tool

Validate it:

    RUN_DIR="$(find results -mindepth 1 -maxdepth 1 -type d | sort | tail -1)"
    uv run llmgauge validate-result "$RUN_DIR"

## Generate a ladder artifact

Example:

    uv run llmgauge run-ladder \
      --suite suites/agent-backend-v1 \
      --only tool-honesty/fake-tool-resistance \
      --model-profile gemma4_12b_qat_q4 \
      --config examples/configs/llmgauge.local.yaml \
      --model-profiles examples/configs/model-profiles.local.yaml \
      --ctx-ladder 8192,12288 \
      --max-tokens 200 \
      --auto-name \
      --runs-root results \
      --run-name ladder-agent-backend-fake-tool

Validate it:

    LADDER_DIR="$(find results -mindepth 1 -maxdepth 1 -type d | grep ladder-agent-backend-fake-tool | sort | tail -1)"
    uv run llmgauge validate-ladder "$LADDER_DIR"

## Create a validated export index

Example:

    uv run llmgauge export-index "$RUN_DIR" "$LADDER_DIR" \
      --validate \
      --out results/monolith-import-smoke-index.json

Expected result:

    Indexed artifacts: 2

The export index should contain:

    "schema_version": "llmgauge.export_index.v0"
    "validation_checked": true

Each item should contain:

    "validation": {
      "checked": true,
      "status": "valid",
      "errors": []
    }

## Import into Monolith

From the Monolith repository:

    cd ~/Projects/local-llm/monolith

    python scripts/import_llmgauge_results.py \
      ~/Projects/local-llm/llmgauge/results/monolith-import-smoke-index.json

The importer may also accept direct artifact paths:

    python scripts/import_llmgauge_results.py /path/to/llmgauge-run-dir

    python scripts/import_llmgauge_results.py /path/to/llmgauge-ladder-dir

## Monolith UI

Imported artifacts are displayed in Monolith at:

    /eval/llmgauge

Imported artifact detail pages use:

    /eval/llmgauge/imports/{id}

Existing legacy routes should remain available:

    /eval
    /eval/imports/{suite_run_id}
    /eval/context-scaling
    /eval/agent-backend
    /context
    /setup

## Environment variable

Monolith now prefers:

    MONOLITH_LLMGAUGE_ROOT

Legacy fallback remains:

    MONOLITH_QUANT_LAB_ROOT

Recommended local setup example:

    export MONOLITH_LLMGAUGE_ROOT="$HOME/Projects/local-llm/llmgauge"

## Current Monolith-side importer behavior

The Monolith importer:

- detects artifact type
- parses LLMGauge v0.13 metadata
- preserves source paths
- stores source hashes
- upserts by source path and artifact type
- writes into additive `llmgauge_*` tables
- does not mutate LLMGauge output directories
- does not remove legacy Quant Lab/core-v2/Hermes data

Known Monolith tables added:

- `llmgauge_artifact_imports`
- `llmgauge_run_summaries`
- `llmgauge_ladder_summaries`

Legacy Monolith tables intentionally remain:

- `quant_lab_suite_runs`
- `quant_lab_prompt_results`
- `context_scaling_runs`
- `context_scaling_results`
- `hermes_eval_runs`
- `hermes_eval_results`
- `hermes_eval_scores`

## Current recommendation

Keep LLMGauge v0.14 focused on importer feedback.

Do not add direct Monolith database writes.

Do not add a LLMGauge daemon, service, or UI.

Do not add Monolith launch controls until import/display behavior is stable.
