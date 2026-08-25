# Current Suite and Prompt Review

## Status and decision

This document reviews the tracked native-response suites at the current
repository baseline. It inventories existing suite and prompt identities,
examines ownership and overlap, assesses capability coverage, and recommends a
bounded direction for a future generic Core suite. It does not change any suite,
prompt, rubric, loader, schema, test, or evidence artifact, and it does not
provide new prompt text.

All five tracked suite identities remain valid for their recorded purposes.
Existing suite IDs and versions are evidence provenance, not names to normalize
retroactively. In particular, the historical
`wumbolabs-practical-use-v1` version `0.1.0` source and its evidence-bound
renderings remain immutable under the
[Historical Practical Suite v0.1.0 contract](PRACTICAL_SUITE_V1_CONTRACT.md).
This review neither authorizes suite removal nor makes old and new results
interchangeable.

The selected next milestone is a **Generic Core suite contract**. That contract
must define identity, profile composition, capability tags, scoring roles,
versioning, comparison eligibility, and coexistence before prompt wording or
implementation is selected.

## Review basis and boundaries

The review applies the [General evaluation taxonomy](GENERAL_EVALUATION_TAXONOMY.md),
the accepted contracts listed in [Design Notes](DESIGN.md), the current
[Suite Strategy](SUITE_STRATEGY.md), the [Practical Eval v1](PRACTICAL_EVAL_V1.md)
prompt and scoring contract, and the [Manual Scoring Rubrics](SCORING_RUBRICS.md).

Every suite below is an LLMGauge-owned **native response** evaluation or native
suite support metadata. Native raw prompts, outputs, failures, settings, and
scoring provenance remain authoritative. Deterministic, manual, and hybrid
scoring must be disclosed rather than blended implicitly. Comparisons should use
the same suite identity, version, prompt set, scoring mode, rubric, and
materially equivalent runtime conditions; mismatches require disclosure and
bounded claims.

This review keeps the following evaluation classes separate:

- a generic Core suite evaluates model responses to LLMGauge-owned prompts;
- practical profiles retain domain and operator-workflow emphasis;
- performance benchmarks, including later LocalMaxxing work, measure controlled
  runtime and hardware behavior under a separate protocol;
- external text benchmarks retain their official datasets, harnesses, and
  metrics;
- agent-environment evaluations include an agent loop, tools, environment, and
  verifier, rather than simulated tool-use preparation in a response prompt.

`context-v1` is included because it is a tracked native suite identity, although
its manifest currently contains presets and no prompts. The inventory covers the
five tracked `suites/*/suite.yaml` identities and their four packaged mirrors.

## Suite inventory

### `core-v1` version `0.1.0`

- **Location and ownership:** editable source at `suites/core-v1/`; byte-mirrored
  packaged suite at `src/llmgauge/builtin_suites/core-v1/`. LLMGauge-owned,
  bundled, and reusable, with the `core` alias.
- **Current role:** Tier 1 practical smoke evidence. Despite its name, it is not
  a complete generic capability core. It mixes portable operational prompts
  with Wumbo/local flavor.
- **Status:** current and reusable as its existing fixed identity; not historical
  or immutable, but any material prompt or scoring change requires a new suite
  version rather than reinterpretation of recorded results.
- **Scoring:** suite-declared 0–5 default manual dimensions. The
  `niche-factual-honesty` prompt also has a local checklist baseline based on
  forbidden substrings. That check is narrow deterministic triage, not a full
  answer-quality score.

| Prompt ID | Category | Present scoring approach |
| --- | --- | --- |
| `honesty-unknown-tool` | `honesty` | Default manual rubric |
| `linux-admin-update` | `linux` | Default manual rubric |
| `docker-dns-nftables` | `docker` | Default manual rubric |
| `zfs-snapshot-rollback` | `zfs` | Default manual rubric |
| `python-log-parser` | `coding` | Default manual rubric |
| `docker-compose-review` | `config` | Default manual rubric |
| `long-context-needle-mini` | `long-context` | Default manual rubric |
| `niche-factual-honesty` | `niche` | Manual rubric plus substring checklist baseline |

**Dependencies:** `tests/test_suite_loading.py` fixes the identity, prompt count,
and validation result; `tests/test_suite_paths.py` fixes built-in availability;
`tests/test_cli_suite_aliases.py` fixes the alias and canonical identity; and
`tests/test_suite_mirror.py` is the general source/package byte-mirror guard.
No tracked reviewed evidence package is bound to this suite.

### `context-v1` version `0.1.0`

- **Location and ownership:** editable source at `suites/context-v1/`; byte-mirrored
  packaged metadata at `src/llmgauge/builtin_suites/context-v1/`. LLMGauge-owned,
  bundled, and addressable through the `context` alias.
- **Current role:** context-ladder preset metadata for `standard`, `long`, and
  `extreme` ranges. It declares zero prompts and explicitly defers prompt-bearing
  context suites.
- **Status:** current support metadata and experimental design surface, not a
  capability-bearing prompt profile and not evidence that long-context behavior
  has been evaluated.
- **Scoring:** none; there are no prompt responses to score.

| Prompt ID | Category | Present scoring approach |
| --- | --- | --- |
| _None_ | _None_ | Presets only; no prompt scoring |

**Dependencies:** `tests/test_suite_loading.py` fixes loadability and identity;
`tests/test_cli_suite_aliases.py` fixes the alias; and
`tests/test_suite_mirror.py` guards the source/package mirror. No tracked
prompt-level evidence package depends on it.

### `agent-backend-v1` version `0.1.0`

- **Location and ownership:** editable source at `suites/agent-backend-v1/`;
  byte-mirrored packaged suite at
  `src/llmgauge/builtin_suites/agent-backend-v1/`. LLMGauge-owned, bundled, and
  reusable for its bounded simulated-agent role through the `agent` alias.
- **Current role:** native-response screening for agent-backend suitability,
  tool/action-boundary risk, conservative shell/config behavior, coding
  usefulness, and constraint retention. It is not an executed agent environment
  and cannot certify autonomous-agent safety or production readiness.
- **Status:** current specialized profile.
- **Scoring:** default manual scoring because the suite declares no separate
  scoring profile. `tool-honesty/fake-tool-resistance` also has a local
  must-include/must-not-include checklist baseline. The lexical checklist is
  triage evidence, not semantic proof.

| Prompt ID | Category | Present scoring approach |
| --- | --- | --- |
| `tool-honesty/fake-tool-resistance` | `tool-honesty` | Default manual rubric plus substring checklist baseline |
| `shell-safety/failed-command-recovery` | `shell-safety` | Default manual rubric |
| `config-safety/docker-compose-edit-plan` | `config-safety` | Default manual rubric |
| `coding/log-summary-helper` | `coding` | Default manual rubric |
| `long-context/synthetic-agent-preload` | `long-context` | Default manual rubric |

**Dependencies:** `tests/test_suite_loading.py`, `tests/test_suite_paths.py`,
`tests/test_cli_suite_aliases.py`, and `tests/test_suite_mirror.py` protect
loading, built-in presence, aliasing, and mirror equality. The fake-tool and
failed-command prompts are bound to the live vLLM smoke and two-prompt
cross-runtime evidence described in [Roadmap](ROADMAP.md); those records remain
prompt-specific native-response evidence, not an agent benchmark.

### `wumbolabs-practical-v1` version `0.2.0`

- **Location and ownership:** editable source at
  `suites/wumbolabs-practical-v1/`; byte-mirrored packaged suite at
  `src/llmgauge/builtin_suites/wumbolabs-practical-v1/`. LLMGauge-owned,
  bundled, and available through `practical` and WumboLabs aliases.
- **Current role:** Tier 2 publication-grade practical comparison under tested
  conditions, governed by [Practical Eval v1](PRACTICAL_EVAL_V1.md). It is not a
  universal ranking, daily-driver recommendation, or generic capability survey.
- **Status:** current reusable practical profile. Several prompts deliberately
  test LLMGauge or public-proof workflows, so the whole suite is not a candidate
  generic Core.
- **Scoring:** explicit `wumbolabs-practical-v1` 0–5 manual scoring profile with
  eight dimensions, expected behaviors, and labels. There are no prompt
  baseline files in the suite.

| Prompt ID | Category | Present scoring approach |
| --- | --- | --- |
| `technical-correctness/linux-gpu-update-boundary` | `technical-correctness` | Practical v1 manual profile |
| `honesty-uncertainty/fake-package-currentness` | `honesty-uncertainty` | Practical v1 manual profile |
| `code-usefulness/result-summary-script` | `code-usefulness` | Practical v1 manual profile |
| `config-reasoning/flawed-compose-review` | `config-reasoning` | Practical v1 manual profile |
| `long-context-retrieval/noisy-report-metrics` | `long-context-retrieval` | Practical v1 manual profile |
| `multi-step-planning/release-readiness-plan` | `multi-step-planning` | Practical v1 manual profile |
| `output-discipline/json-only-risk-register` | `output-discipline` | Practical v1 manual profile |
| `practical-judgment/public-proof-vs-private-progress` | `practical-judgment` | Practical v1 manual profile |
| `niche-hallucination/fake-llmgauge-field` | `niche-hallucination` | Practical v1 manual profile |
| `adversarial-realism/stale-instructions-late-constraint` | `adversarial-realism` | Practical v1 manual profile |

**Dependencies:** `tests/test_suite_loading.py` fixes identity, Tier 2, prompt
count, and validation; `tests/test_suite_paths.py` fixes packaged presence;
`tests/test_cli_suite_aliases.py` fixes aliases; `tests/test_suite_mirror.py`
guards mirrored bytes; and focused scoring tests in `tests/test_scoring.py` and
`tests/test_cli_scoring.py` exercise its rubric metadata. No reviewed
practical evidence package uses this exact version; the historical runs used
the separate source-only identity below (those run records were operator
evaluation artifacts and are no longer tracked in this repository).

### `wumbolabs-practical-use-v1` version `0.1.0`

- **Location and ownership:** canonical historical source at
  `suites/wumbolabs-practical-use-v1/`. It is intentionally source-only, has no
  packaged built-in mirror or alias, and is owned by the accepted historical
  suite contract and evidence chain rather than current prompt development.
- **Current role:** exact source for the six-prompt historical practical
  evaluation runs; the run records themselves were operator evaluation
  artifacts and are not tracked in this repository.
- **Status:** historical, immutable, and evidence-bound. Do not rename, reorder,
  modernize, reclassify, fold into `wumbolabs-practical-v1`, or infer that its
  evidence applies to another suite version.
- **Scoring:** the suite manifest declares no scoring profile or deterministic
  baseline. The historical runs applied manual reviewed scores with recorded
  provenance; those result artifacts were never part of this repository's
  durable product content.

| Prompt ID | Category | Present scoring approach |
| --- | --- | --- |
| `linux/arch-nvidia-update-advice` | `linux` | Manual reviewed evidence |
| `coding/python-log-parser` | `coding` | Manual reviewed evidence |
| `docker/compose-review` | `docker` | Manual reviewed evidence |
| `honesty/unknown-package` | `honesty` | Manual reviewed evidence |
| `summarization/technical-run-summary` | `summarization` | Manual reviewed evidence |
| `local-llm/consumer-gpu-advice` | `local-llm` | Manual reviewed evidence |

**Dependencies:** `tests/test_practical_suite_v1_sanitization.py` fixes suite
ID, version, prompt IDs and order with synthetic content only; suite-level
integrity and the source-only mirror policy are owned by
`tests/test_suite_mirror.py`. Formerly tracked practical evidence packages
under `docs/evidence/practical/` depended on the exact six-prompt overlap;
those operator evaluation artifacts were removed from this repository, while
the historical source suite itself remains tracked and unchanged.

`tests/test_suite_mirror.py` currently discovers all top-level source suite
files while asserting equality with packaged built-ins. Its broad discovery
boundary also sees this intentionally source-only historical suite. That is a
low-severity maintenance mismatch in the test's scope, not authority to package,
modify, or exclude the historical source; this documentation milestone does not
change tests.

## Overlap, ancestry, and ownership findings

The suites share useful task families, but shared topics do not make their
identities or evidence interchangeable.

| Prompt family | Current overlap | Direction for future Core |
| --- | --- | --- |
| Unknown fake tool/package honesty | `core-v1`, `agent-backend-v1`, Practical v0.2, historical Practical v0.1 | Keep one generic uncertainty task family; leave agent pressure and practical/currentness variants specialized |
| Small log/result parser | `core-v1`, `agent-backend-v1`, Practical v0.2, historical Practical v0.1 | Keep at most one generic coding task; do not carry four near-duplicates |
| Docker Compose/config review | All prompt-bearing suites | Keep a generic review capability only if it adds code/config review coverage; retain operational variants in practical or agent profiles |
| Linux/NVIDIA update safety | `core-v1`, Practical v0.2, historical Practical v0.1 | Exclude platform/hardware-specific wording from generic Core; preserve as practical-domain evidence |
| Constraint or contamination retention | `core-v1`, `agent-backend-v1`, Practical v0.2 | Define distinct short instruction-following and genuine long-context objectives; do not relabel short prompts as long-context evidence |
| Practical planning and judgment | Primarily Practical v0.2 | Retain project/release/public-proof tasks in the practical profile, not generic Core |

`wumbolabs-practical-v1` version `0.2.0` and historical
`wumbolabs-practical-use-v1` version `0.1.0` share practical lineage and several
task families, but the historical contract explicitly makes them separate
identities. Version `0.2.0` is not a modernization, replacement, or scoring
reinterpretation of the historical evidence.

Current ownership is therefore best expressed as coexistence:

- preserve each recorded suite ID and version for reproduction and comparison;
- treat source/package mirrors as one bundled suite identity, not two suites;
- keep the historical source and evidence chain immutable;
- use practical and agent suites for their bounded domains;
- create a new explicitly versioned generic Core identity rather than rewriting
  `core-v1` in place.

## Capability coverage assessment

Coverage ratings describe prompt coverage and scoreability, not demonstrated
model quality.

| Capability | Current coverage | Assessment |
| --- | --- | --- |
| Instruction following | Strong | Repeated explicit constraints, late constraints, format limits, and contamination traps; some duplication is substantial. |
| Constrained or structured output | Moderate | One strong JSON-only task and one table extraction task; little variety in schemas, exact cardinality, or multi-field validation. |
| Honesty and uncertainty | Strong | Multiple fake tool, package, field, niche-fact, and currentness boundaries; overrepresented relative to other general capabilities. |
| Summarization and extraction | Weak to moderate | Historical technical summarization and Practical v0.2 metric extraction exist; generic summarization, grounded synthesis, and broader extraction are thin. |
| Planning and technical explanation | Moderate | Operational plans and troubleshooting explanations are common, but most are project, Linux, Docker, storage, release, or agent flavored. |
| Coding and code review | Weak to moderate | Several small Python generation tasks and Compose review tasks exist; debugging, test reasoning, patch review, and language breadth are missing. |
| Troubleshooting and practical workflows | Strong | Linux, Docker, ZFS, shell/config, and release workflows are the dominant strength; breadth outside operations is limited. |
| Deterministic checks | Weak | Two brittle substring baselines exist. JSON validity, exact keys/counts, extraction correctness, and fixture-based code behavior are not captured as suite checks. |
| Safety and refusal boundaries | Moderate | Conservative operational safety is strong. Calibrated refusal, benign-request over-refusal, privacy, and non-operational harm boundaries are sparse. |
| Tool-use preparation | Weak to moderate | The agent suite tests plans, honesty, and action boundaries, but no generic structured tool selection or argument construction exists. Executed tool use correctly remains out of class. |
| Long-context behavior | Weak | `context-v1` has presets only; existing prompt files are small constraint-retention or noisy-context tasks, not controlled long-context stress at declared lengths. |

### Covered well

- honesty about unknown tools, packages, fields, currentness, and niche facts;
- conservative operational safety with verification and rollback;
- short-form instruction following and explicit output discipline;
- Linux, Docker, storage, shell, and local-LLM practical workflows;
- manual review metadata with expected behaviors and failure labels.

### Missing or weak

- portable summarization, synthesis, and multi-source reconciliation;
- varied structured extraction and constrained formats;
- debugging, code review, test design, and defect localization;
- balanced refusal behavior beyond destructive operational commands;
- structured tool-call preparation without an executed agent loop;
- controlled long-context placement, length, retrieval, and synthesis evidence;
- deterministic checks that validate objectively specified properties;
- domain breadth beyond system administration and LLMGauge-adjacent workflows.

## Generality and scoring findings

### Too specific for a generic Core

The following remain useful evidence but should not define generic Core:

- Wumbo-branded fake tools and project-specific niche facts;
- LLMGauge result schemas, reports, releases, and public-proof prioritization;
- Arch Linux, NVIDIA, ZFS, homelab, and local-model GPU purchasing details;
- current package or repository state tied to a named platform;
- simulated agent-role framing and action-pressure scenarios.

These prompts should remain in their existing identities or future practical,
operator, or agent-preparation profiles. Their specificity is a feature when the
tested use case matches; it is a portability defect only if promoted to generic
Core.

### Useful practical-domain tests

Conservative system changes, recovery planning, config review, troubleshooting,
small utility scripts, and hardware/runtime advice remain valuable practical
coverage. They should preserve their domain tags, tested-condition claims, and
manual safety judgment rather than being duplicated into Core merely to inflate
coverage.

### Deterministic and hybrid opportunities

A future contract should admit deterministic checks only where the prompt makes
the property objective:

- parseability, exact keys, types, cardinality, ordering, and no-extra-text rules
  for structured output;
- exact source-to-field extraction with explicit unknown handling;
- fixture-backed execution for small self-contained code tasks, with time and
  resource bounds;
- exact needle retrieval and controlled constraint selection;
- closed classification or transformation tasks with an explicit answer set.

Semantic correctness, explanation quality, practical judgment, uncertainty,
safety tradeoffs, and calibrated refusal remain manual. Hybrid scoring is
appropriate when objective format or execution evidence and human semantic
judgment both matter. The result must preserve each component and an explicit
combination rule; deterministic failure must not silently replace or fabricate a
manual verdict.

The two existing lexical baselines are useful triage but should not be copied as
the default Core scoring design. Phrase matching is easy to evade and can reject
semantically correct wording.

## Recommended future native-suite structure

This is a design direction for the next contract, not an implementation or
prompt-selection decision.

### Small smoke profile

- A very small, stable subset of the future generic Core identity.
- Covers fast end-to-end health signals: basic instruction following, one
  objective structured response, one grounded transformation or extraction, and
  one honesty/safety boundary.
- Uses only prompts that also belong to Core, so smoke-to-Core results retain
  explicit profile provenance without creating a second competing suite.
- Optimizes for rapid operator feedback, not representative quality ranking.

### General Core profile

- A balanced, portable native-response profile with no private, project,
  platform, hardware, or user-specific knowledge requirement.
- Covers instruction following, structured output, honesty, summarization,
  extraction, planning, technical explanation, coding, code review,
  troubleshooting, safety/refusal calibration, tool-use preparation, and a
  bounded context objective.
- Limits repeated task families. Each prompt needs a distinct primary capability
  and documented secondary tags rather than another variant of fake-package,
  parser, Compose, or update advice.
- Remains small enough for routine comparison; extended breadth belongs outside
  the base profile.

### Optional extended and specialized profiles

- **Extended general:** additional difficulty, format, domain, and context
  coverage under the same accepted capability model.
- **Practical/operator:** current Linux, Docker, storage, local-runtime, and
  publication workflows, including `wumbolabs-practical-v1` coexistence.
- **Agent preparation:** simulated tool selection, argument planning, action
  boundaries, and recovery while remaining native response. Executed tools and
  environment verification stay in the agent-environment class.
- **Context:** generated or curated length/placement profiles with declared
  tokenization and target sizes; context presets alone are not results.
- **Performance and external benchmarks:** separate evaluation identities and
  authority, never Core extensions or aggregate quality dimensions.

### Capability tags

The next contract should define a controlled, many-to-many tag vocabulary
separate from one display category. At minimum it should cover
`instruction-following`, `structured-output`, `honesty-uncertainty`,
`summarization`, `extraction`, `planning`, `technical-explanation`, `coding`,
`code-review`, `troubleshooting`, `safety-refusal`, `tool-preparation`, and
`long-context`. It should distinguish primary capability from secondary stressors
such as noise, late constraints, adversarial instructions, and strict length.
Tags support coverage audits; they must not imply score comparability or create
an undisclosed aggregate.

### Scoring roles

- **Deterministic:** objective local properties with versioned rules and
  inspectable inputs/calculations.
- **Manual:** semantic quality, factual and technical correctness, calibrated
  uncertainty, safety, usefulness, and explanation under a named rubric.
- **Hybrid:** both components preserved explicitly when format/execution and
  semantic quality are independently material.

Every prompt should declare its intended scoring role before implementation.
Automatic drafts remain review-required triage and cannot be relabeled as manual
scores.

### Versioning and coexistence

- Accept a new stable suite identity and version in the Generic Core suite
  contract; do not mutate `core-v1` into the new contract.
- Fix material prompt selection, profile membership, rendering, completion,
  scoring method, and aggregation semantics by evaluation version.
- Require a new version for material changes and preserve prompt identity/order
  needed to interpret old results.
- Keep all five current identities available according to their existing
  ownership and evidence obligations. Historical suites remain immutable;
  current specialized suites may evolve only through explicit new versions.
- Compare like-for-like versions and profiles. Cross-suite summaries must expose
  mismatches and cannot collapse scores into a universal rank.

## Bounded next milestone

The only selected next milestone is **Generic Core suite contract**. It should
settle:

1. native-response subject, authority, claims, and comparison boundaries;
2. new suite identity, version, and smoke/Core/optional profile relationship;
3. capability-tag vocabulary and coverage requirements;
4. deterministic, manual, and hybrid scoring roles and provenance;
5. coexistence with all current and historical suite identities;
6. acceptance gates for later prompt design without writing prompt text.

Prompt wording, suite files, loaders, schemas, CLI changes, models, benchmarks,
LocalMaxxing, external benchmark import, agent drift, Terminal-Bench, and agent
harness work remain outside that milestone.
