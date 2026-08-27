# LLMGauge Usage

See [Installation](INSTALL.md) for source-checkout, editable local install, and GitHub install workflows.

This page is a compact command map for common LLMGauge workflows.

For a first run, start with [Quickstart](QUICKSTART.md). For a fresh-clone audit
checklist (including `uv run pytest`), see [Clean clone testing](CLEAN_CLONE_TESTING.md).
For local model evaluation process guidance, see [Local model testing workflow](LOCAL_MODEL_TESTING.md).

## Command forms

From a repository checkout, use:

    uv run llmgauge ...

After installing the CLI into your environment, use:

    llmgauge ...

Most current examples use the source-checkout form.

## Setup and inspection

Show top-level help:

    uv run llmgauge --help

Guided first-run setup (preferred):

    uv run llmgauge setup

Read-only scan for likely `llama-cli` and GGUF paths:

    uv run llmgauge setup --scan

Non-interactive setup with explicit paths:

    uv run llmgauge setup --non-interactive \
      --llama-cli /path/to/llama-cli \
      --model-path /path/to/model.gguf \
      --profile-name my_model

`setup` writes user config files under `~/.config/llmgauge/` when needed and does
not launch a model. `XDG_CONFIG_HOME` is respected.

Manual fallback — create user config files from templates:

    uv run llmgauge init

Use `uv run llmgauge init-config` only when you specifically want project-local
ignored files under `examples/configs/`.

Recommended first-run order:

    uv run llmgauge setup
    uv run llmgauge doctor
    uv run llmgauge smoke
    uv run llmgauge run --suite practical --only honesty-uncertainty/fake-package-currentness --model-profile my_model --dry-run

Manual alternative after `init`:

    uv run llmgauge model add my_model --path /path/to/model.gguf --label "My Model"
    uv run llmgauge model list

Installed CLI users can drop `uv run` after installing the command.

Check the environment in more detail:

    uv run llmgauge doctor

Check one configured model profile:

    uv run llmgauge doctor --model-profile example_model

Run a safe setup smoke check:

    uv run llmgauge smoke

Check one configured model profile without launching a model:

    uv run llmgauge smoke --model-profile example_model

`doctor` and `smoke` are inspection-only. They do not launch `llama.cpp`.

Status meanings:

- `ok` — check completed
- `skip` — config or profile checks were skipped because no file was found
- `warn` — optional or incomplete setup, such as placeholder paths or missing
  `nvidia-smi`
- `fail` — blocking problem; command exits nonzero

When config or profiles are missing, both commands print next-step guidance.
Smoke may report `passed with warnings` while setup is still incomplete.

Config discovery checks explicit CLI paths first, then project-local
`examples/configs/*.local.yaml` relative to the current working directory, then
user config under `~/.config/llmgauge/`.

List configured model profiles:

    uv run llmgauge model list

`list-model-profiles` remains a compatibility alias for `model list`.

## Model profile management

Manage profiles with the `model` command group:

    uv run llmgauge model list
    uv run llmgauge model add my_model --path /path/to/model.gguf --label "My Model"
    uv run llmgauge model update example_model --path /path/to/model.gguf
    uv run llmgauge model remove my_model --yes

Pass an explicit profiles YAML path with `--model-profile-file`. The older
`--model-profiles` flag remains supported with identical behavior.

When no path is given, LLMGauge discovers the profiles file in this order:

1. explicit `--model-profile-file` or `--model-profiles`
2. project-local `examples/configs/model-profiles.local.yaml` if present
3. user config `~/.config/llmgauge/model-profiles.yaml` if present

Lifecycle notes:

- `model update` merges only the fields you pass and preserves unknown YAML
  extras on the profile entry.
- `model add --force` replaces the entire profile entry; unknown extras on
  that entry are not preserved.
- `model remove` requires `--yes`.
- Structured CLI writes may not preserve YAML comments.

List built-in suites:

    uv run llmgauge list-suites

Built-in aliases:

    practical -> wumbolabs-practical-v1
    core      -> core-v1
    agent     -> agent-backend-v1
    context   -> context-v1

`generic-core-v1` is a profile-aware built-in suite with no alias. Omit
`--profile` to use its declared default (`core`), or pass `--profile smoke`
or `--profile core`. Declared D1-D7 scoring references are identities only;
those checks are not implemented yet.

Aliases are accepted anywhere a built-in suite is resolved. Result artifacts
still record canonical suite IDs.


Validate a suite:

    uv run llmgauge validate-suite practical

## Run planning

Preview one exact prompt without launching `llama.cpp`:

    uv run llmgauge run \
      --suite practical \
      --only honesty-uncertainty/fake-package-currentness \
      --model-profile example_model \
      --ctx 8192 \
      --max-tokens 800 \
      --top-k 20 \
      --seed 424242 \
      --cache-type-k q8_0 \
      --cache-type-v q4_0 \
      --flash-attn auto \
      --runtime-label stock-reference \
      --reasoning-mode on \
      --reasoning-effort medium \
      --reasoning-budget 16384 \
      --fit off \
      --reasoning-preserve \
      --spec-type none \
      --dry-run

Discover the built-in reasoning/sampling profiles and inspect one profile's
exact requested controls:

    uv run llmgauge profiles list
    uv run llmgauge profiles show qwen3-thinking-v1

Select that named profile for a dry run:

    uv run llmgauge run \
      --suite practical \
      --only honesty-uncertainty/fake-package-currentness \
      --model-profile example_model \
      --sampling-profile qwen3-thinking-v1 \
      --dry-run

`--sampling-profile` records requested controls from a versioned profile.
Vendor-aligned IDs are derived from documented vendor settings; they are not
vendor endorsement and do not prove thinking occurred. See
[Vendor-aligned sampling profiles](VENDOR_ALIGNED_SAMPLING_PROFILES.md).
Unknown IDs fail before launch. There is no remote profile catalog.


Preview a category:

    uv run llmgauge run \
      --suite practical \
      --include honesty-uncertainty \
      --model-profile example_model \
      --dry-run

Preview one named suite profile:

    uv run llmgauge run \
      --suite coding-core-v1 \
      --profile smoke \
      --model-profile example_model \
      --dry-run

Use `--only <prompt-id>` for one exact prompt. Use `--include <category>` for a category, or `--include all` for a full suite.
For suites that declare profiles, `--profile <profile-name>` selects one named
profile; omitting it uses the manifest default. `--profile` cannot be combined
with `--only` or category-based `--include`; explicit `--include all` remains
compatible.

### Native multi-turn planning

Create a local, closed task document that schedules supplied inert feedback:

    {
      "schema_version": "llmgauge.multi_turn_task.v0",
      "protocol_id": "llmgauge.sequential_supplied_feedback",
      "protocol_version": "0.1.0",
      "task_id": "tool-honesty/fake-tool-resistance",
      "task_version": "0.1.0",
      "initial_state_id": "initial-state-v1",
      "limits": {
        "max_model_turns": 2,
        "max_attempts_per_turn": 1,
        "max_feedback_items": 1,
        "per_turn_timeout_seconds": 120
      },
      "feedback": [{
        "feedback_id": "operator-feedback-1",
        "content": "The first answer missed the stated constraint.",
        "origin": "operator_local",
        "after_model_turn": 1
      }]
    }

Preview declared and effective limits separately, the actual
runtime-conditional request/supply sequence, the complete feedback plan with
origin, schedule, exact content and reachability, runtime, and output plan
without launching or contacting a runtime:

    uv run llmgauge run \
      --suite agent-backend-v1 \
      --only tool-honesty/fake-tool-resistance \
      --conversation-task conversation-task.json \
      --conversation-id review-001 \
      --model-profile example_model \
      --dry-run

`--conversation-task` requires exact `--only` and `--conversation-id`; it cannot
be combined with `--profile` or category selection. `--max-turns` may only
reduce the task limit. Coding Core remains static single-turn evidence.
The declared turn limit is an upper bound, not a promise that every request
will occur. A no-feedback task plans only its initial request. Feedback beyond
an effective `--max-turns` limit is shown as declared but unreachable. Feedback
scheduled after the final admitted request is shown as conditionally supplied
but unconsumable if that request completes.

Feedback is supplied inert text. LLMGauge does not execute generated code,
patches, commands, compilers, tests, analyzers, or tools in this protocol.

## Run execution

Run one exact prompt:

    uv run llmgauge run \
      --suite practical \
      --only honesty-uncertainty/fake-package-currentness \
      --model-profile example_model \
      --ctx 8192 \
      --max-tokens 800 \
      --auto-name \
      --runs-root results \
      --run-name practical-smoke

Run a full suite:

    uv run llmgauge run \
      --suite practical \
      --include all \
      --model-profile example_model \
      --ctx 8192 \
      --max-tokens 1200 \
      --auto-name \
      --runs-root results \
      --run-name practical-full

Run the same bounded native conversation by removing `--dry-run` and providing
`--out` or `--auto-name`. Both llama.cpp and externally managed local vLLM use
the same sequential orchestration; vLLM lifecycle remains operator-owned.
The result contains authoritative `transcript/transcript.json`, source turn and
state artifacts, cleaned derivatives, an additive result reference, and a
transcript-aware report. Partial, failed, retried, and unconsumed evidence is
preserved.

## Runtime metadata

Record the llama.cpp flash-attention mode:

    --flash-attn auto
    --flash-attn on
    --flash-attn off

Record the run methodology:

    --runtime-label stock-reference
    --runtime-label daily-tuned
    --runtime-label experimental

Runtime labels are manual metadata. They do not change hardware settings.

Record reasoning intent for reasoning-capable models:

    --reasoning-mode off
    --reasoning-mode on
    --reasoning-mode auto
    --reasoning-mode default
    --reasoning-mode unknown

`default` and `unknown` are metadata-only modes that do not add a llama.cpp
`--reasoning` flag. When omitted, LLMGauge defaults to `off` to preserve prior
behavior.

For llama.cpp runs, sampling and KV-cache controls are first-class:

    --top-k 20
    --seed 424242
    --cache-type-k q8_0
    --cache-type-v q4_0
    --reasoning-effort medium
    --reasoning-budget 16384
    --fit off
    --reasoning-preserve
    --no-reasoning-preserve
    --spec-type none
    --spec-type draft-mtp

`--top-k 0` disables top-k. Omitting `--top-k` leaves the runtime default in
effect. Omitting `--seed` likewise leaves llama.cpp's default/random behavior
in effect; `--seed -1` records an explicit request for llama.cpp random seeding.
The supported cache types are the admitted current llama.cpp values: `f32`,
`f16`, `bf16`, `q8_0`, `q4_0`, `q4_1`, `iq4_nl`, `q5_0`, and `q5_1`.
LLMGauge always requests KV offload for this runner and records the request; it
does not infer observed GPU residency from that request.

Reasoning effort accepts `default`, `minimal`, `low`, `medium`, `high`, `xhigh`,
or `max`; the model template can still ignore a runtime-accepted request.
Reasoning budget accepts `-1` for unrestricted, `0` for immediate end, or a
positive token budget. The artifact distinguishes an explicit request from a
runtime default, but command acceptance is not proof that a model template
honored it. Reasoning-off means the llama.cpp `--reasoning off` request; it is
never represented by post-generation output stripping.

Fit accepts `on` or `off`; YAML may also use booleans, normalized to those
canonical values. Omission leaves llama.cpp's runtime default in effect and is
distinct from explicit `on` or `off`. A successful load does not prove which
fit behavior was used.

`--reasoning-preserve` and `--no-reasoning-preserve` explicitly request whether
llama.cpp retains prior reasoning in multi-turn chat history. Omission leaves
the template/runtime default. Passing either flag proves only the request, not
that the selected template or model complied.

`--spec-type` accepts a canonical comma-separated selection from `none`,
`draft-simple`, `draft-eagle3`, `draft-mtp`, `draft-dflash`, `draft-dspark`,
`ngram-simple`, `ngram-map-k`, `ngram-map-k4v`, `ngram-mod`, and
`ngram-cache`. Duplicate values, unsupported values, and combining `none` with
another mode are rejected. Omission uses the runtime default; explicit `none`
records speculation off. LLMGauge never enables speculation implicitly.

Prompts up to 64 KiB UTF-8 are passed as structured argv. Larger prompts are
written to a temporary local UTF-8 file and supplied with llama.cpp `--file`;
the original prompt remains authoritative under `raw/*.prompt.md`. Per-prompt
transport mode and a sanitized command argv are recorded in
`runtime-command.json`. This removes the per-argument Linux limit without shell
interpolation.

Native function/tool schemas are not supported by the current `llama-cli`
execution contract. LLMGauge continues to distinguish static tool-related
prompts from native schemas; it neither pretends schemas were supplied nor
executes model-requested tools. A llama-server native-tools backend requires a
separate accepted runtime contract.

Dry-run output shows `model_source`, resolved runtime controls, a normalized
command preview, and where `runtime-command.json` would be written for a real
run.

## Import Agent Harness evidence

Import one local WumboLabs OMP session-format-v3 JSONL file into a new,
self-contained LLMGauge result:

    uv run llmgauge import-agent-harness \
      /path/to/session.jsonl \
      results/imported-agent-session

When the session contains `blob:sha256:<digest>` references, supply the
operator-selected blob root explicitly:

    uv run llmgauge import-agent-harness \
      /path/to/session.jsonl \
      results/imported-agent-session \
      --blob-dir /path/to/omp-blobs

Inspect source admission without writing result artifacts:

    uv run llmgauge import-agent-harness \
      /path/to/session.jsonl \
      results/imported-agent-session \
      --dry-run

The importer reads only the selected session and its format-defined referenced
objects. It does not replay or resume the session, execute commands or tools,
inspect or mutate a repository, contact a model/provider/network service, or
modify source evidence. Imports are bounded, secret-scanned, copied as exact
private evidence, and atomically published. Repeating an identical import to
the same destination is an unchanged no-op; other existing or conflicting
destinations fail closed.

Validate the contained result with `validate-result`. Import or validation
success does not prove harness task success, tests passing, quality,
scoreability, sanitization, or publication readiness. Native `score`, native
report, comparison, export-index, and public-export paths reject imported Agent
Harness results.

Create an editable template, copy and complete it as candidate review metadata,
validate the completed candidate, apply it, then generate the derivative report:

    uv run llmgauge agent-session-review results/imported-agent-session --init
    cp results/imported-agent-session/agent-harness/review/agent-session-review.template.json \
      results/imported-agent-session/review-candidate.json
    # Edit results/imported-agent-session/review-candidate.json with reviewer metadata.
    uv run llmgauge agent-session-review results/imported-agent-session \
      --review results/imported-agent-session/review-candidate.json --check
    uv run llmgauge agent-session-review results/imported-agent-session \
      --review results/imported-agent-session/review-candidate.json --apply
    uv run llmgauge agent-session-review results/imported-agent-session --report

The editable template and canonical review are bounded mutable metadata under
`agent-harness/review/`; neither changes imported evidence or its fingerprint.
The generated Agent Harness report is a derivative review aid, not a transcript,
score, comparison, or publication decision.

## Import external benchmark evidence

Import one local EleutherAI `lm-eval` results JSON file or result directory
into a new, self-contained LLMGauge result:

    uv run llmgauge benchmark import \
      /path/to/results.json \
      results/imported-lm-eval

Inspect source admission without writing result artifacts:

    uv run llmgauge benchmark import \
      /path/to/results.json \
      results/imported-lm-eval \
      --dry-run

Validate the contained imported evidence:

    uv run llmgauge benchmark validate results/imported-lm-eval

Write a read-only imported-benchmark report and Bundle 1 qualification view:

    uv run llmgauge benchmark report results/imported-lm-eval

`validate-result` also understands this dedicated imported result. Import or
validation success does not prove official harness acceptance, answer quality,
or publication readiness. The importer copies admitted source bytes and writes
normalized `external-benchmark/evidence.json`; it does not repair, rescore,
reinterpret, or overwrite the authoritative lm-eval result. It does not
execute generated code, install lm-eval, download datasets, or contact a
network service.

`benchmark report` writes regenerable `external-benchmark/report.md`. Bundle 1
qualification is computed from pinned official identities at report time and
is not written into evidence. A generic lm-eval import remains valid when it
is not Bundle 1-qualified. See
[Bundle 1 qualification](BUNDLE1_QUALIFICATION.md).

Native `score`, native report, comparison, export-index, and public-export
paths reject imported external-benchmark results. The existing
`llmgauge localmaxxing` namespace remains the llama.cpp speed/performance
integration and is unchanged.


## Validation

`validate-result` confirms artifact structure and file references. It does not
prove answer quality, safety, scoring completeness, or publication readiness.

Validate a single run:

    uv run llmgauge validate-result results/<run-directory>

Validate a context ladder:

    uv run llmgauge validate-ladder results/<ladder-directory>

Validate a Fit Ladder artifact:

    uv run llmgauge validate-fit-ladder results/<fit-ladder-directory>

Validate a model batch:

    uv run llmgauge validate-batch results/<batch-directory>

## Scoring

Initialize a manual score file:

    uv run llmgauge score results/<run-directory> --init

Validate scores without applying them:

    uv run llmgauge score \
      results/<run-directory> \
      --scores results/<run-directory>/scores.yaml \
      --check

Apply scores:

    uv run llmgauge score \
      results/<run-directory> \
      --scores results/<run-directory>/scores.yaml

Re-validate after applying scores:

    uv run llmgauge validate-result results/<run-directory>

Create a deterministic assisted draft for review:

    uv run llmgauge score results/<run-directory> --auto-draft

Run `score --check` before applying scores. Manual scores are review metadata.
They are not automatic LLM judgments. Do not publish auto-drafts as final review.

## Compare and export

Create a sanitized public derivative of one completed run:

    uv run llmgauge export-public results/<run-directory> --out public/<run-directory>

`export-public` validates the source run, preserves safe relative evidence,
redacts private paths and secret-like metadata, omits unknown files, and writes
`public-export-manifest.json`. It never modifies the source run and refuses a
non-empty output directory. Review the derived export before publication;
sanitization is not answer-quality validation.

Compare two or more runs:

    uv run llmgauge compare \
      results/run-a \
      results/run-b \
      --out results/compare.md

Create an export index:

    uv run llmgauge export-index \
      results/<artifact-directory> \
      --validate \
      --out results/llmgauge-index.json

## Context ladders

Preview a context ladder:

    uv run llmgauge run-ladder \
      --suite wumbolabs-practical-v1 \
      --only honesty-uncertainty/fake-package-currentness \
      --model-profile example_model \
      --ctx-ladder 8192,16384,32768 \
      --dry-run

Run a context ladder:

    uv run llmgauge run-ladder \
      --suite wumbolabs-practical-v1 \
      --only honesty-uncertainty/fake-package-currentness \
      --model-profile example_model \
      --ctx-ladder 8192,16384,32768 \
      --max-tokens 800 \
      --out results/example-ladder

## Fit Ladder

Preview adaptive fit attempts:

    uv run llmgauge fit-ladder \
      --suite wumbolabs-practical-v1 \
      --only honesty-uncertainty/fake-package-currentness \
      --model-profile example_model \
      --ctx 65536 \
      --fallback-contexts 32768,16384,8192 \
      --dry-run

Run Fit Ladder:

    uv run llmgauge fit-ladder \
      --suite wumbolabs-practical-v1 \
      --only honesty-uncertainty/fake-package-currentness \
      --model-profile example_model \
      --ctx 65536 \
      --fallback-contexts 32768,16384,8192 \
      --out results/example-fit-ladder

Fit Ladder preserves failed attempts and records the selected working configuration. It does not hide the originally requested configuration.

## Model batches

Run a manifest-driven model batch:

    uv run llmgauge run-batch \
      --manifest tmp/example-batch.yaml \
      --out results/example-batch

Batch manifests reference configured model profile names. They do not accept arbitrary model paths.

See [Model batch runs](MODEL_BATCHES.md).

## Public-proof workflow

See `docs/PUBLIC_REPORTING.md` for the full checklist. Short form:

    run -> validate-result -> inspect outputs -> score --init
    -> edit scores.yaml -> score --check -> score --scores
    -> validate-result -> report.md -> compare -> export-index

Read **Report Scope**, **Evidence Summary**, **Audit Checklist**, **Prompt Artifact Audit**, and **Publish Readiness Notes** in `report.md` before publication. Use `compare.md` **Comparison Scope** for multi-run caveats. See `docs/ARTIFACT_SCHEMAS.md` for auditing a result directory.

New single-run results may include a canonical run fingerprint. It identifies
the immutable private evidence for that run, excluding run ID, timestamp, local
paths, reports, cleaned output, and scores. `validate-result` verifies the
fingerprint when present, but the fingerprint is not a quality score, signature,
or proof that transformed public-export bytes match the private run.

## Claim boundary

A single run proves only that a model produced output under the recorded settings.

A scored comparison report is evidence for review. It is not a universal leaderboard or model recommendation.
