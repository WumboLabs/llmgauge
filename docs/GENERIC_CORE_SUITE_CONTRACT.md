# Generic Core Suite Contract

Status: Accepted architecture contract.

This contract defines the identity, profiles, capability coverage, scoring roles,
comparison boundaries, and coexistence rules for a future general-purpose
native-response suite. It selects no final prompt wording and implements no
suite, loader, schema, CLI, rubric, baseline, or scoring behavior.

## Scope and evaluation subject

The suite belongs to the native-response class defined by the
[general evaluation taxonomy](GENERAL_EVALUATION_TAXONOMY.md). Its subject is a
model response to an LLMGauge-owned prompt under disclosed model, runtime,
generation settings, and hardware conditions. It evaluates only the response
and the evidence produced around that response. Preparing a tool request may be
evaluated as text; executing tools or verifying effects in an environment is
agent-environment evaluation and is outside this suite.

The versioned suite source and rendering rules are authoritative for what the
suite asks. For an executed run, the authoritative evidence is the rendered raw
prompt, raw model output, stderr and logs, every failed attempt and completion
state, result metadata, requested and observed settings, and applied scoring
provenance. Reports, comparisons, indexes, cleaned output, score drafts, and
public exports are derived views. They never replace or silently repair the
source or raw run evidence.

Structural validity is not answer quality. A completed Generic Core run supports
claims only about the tested suite version, profile, prompt membership, scoring
state, model, runtime, settings, and hardware conditions.

## Stable identity and profiles

The new stable identity is:

- suite ID: `generic-core-v1`;
- initial suite version: `0.1.0`.

The `v1` identity names this accepted evaluation contract. The suite version
fixes one reproducible realization of that identity. Neither value aliases,
renames, replaces, or repurposes `core-v1`.

`generic-core-v1` has named profiles within each suite version:

- **`smoke`** is a very small, stable, ordered, strict subset of `core` for fast
  end-to-end health signals. It is not a separate suite or an undisclosed
  competing benchmark.
- **`core`** is the balanced, portable, general-purpose profile and the normal
  unit for Generic Core quality review.
- **`extended`** may be added in a future suite version for additional general
  difficulty, format, domain, or bounded-context breadth. If admitted, it is an
  explicitly versioned ordered profile under the same suite identity, not an
  implicit expansion of `core`.

Every `smoke` prompt must also appear in `core`, in the same relative order.
`smoke` may not substitute alternate prompt wording, rendering, or scoring rules.
A future `extended` profile may contain all of `core` plus additional prompts,
but its exact relationship and membership must be declared by its suite version.
Results must record the selected profile and exact prompt membership; a profile
name alone is insufficient provenance.

Practical/operator, agent-preparation, dedicated context, and other specialized
work are separate suite identities rather than Generic Core profiles. A proposed
addition belongs in `generic-core-v1` only when it remains general-purpose,
native-response, portable, and governed by this contract. Performance and
external text benchmarks are separate evaluation classes, never profiles of
this identity.

## Prompt identity, order, membership, and versioning

Each future prompt must have one stable prompt ID within `generic-core-v1`.
Prompt IDs are never recycled or repurposed for a materially different task.
Each suite version must fix:

- the complete prompt source and deterministic rendering rules;
- the canonical ordered prompt inventory;
- every profile's explicit ordered list of prompt IDs;
- each prompt's primary capability and secondary stressor tags;
- each prompt's declared scoring role and versioned scoring references;
- completion rules and any aggregation rule used by the profile.

Execution order is the declared profile order. Implementations must not sort,
sample, insert, omit, or select prompts dynamically while reporting the declared
profile unchanged. A subset run is a disclosed custom prompt set, not a complete
profile result. Reordering membership is material even when prompt text is
unchanged.

A new suite version is required for any change that can alter interpretation,
comparability, selection, or score, including:

- adding, removing, replacing, or reordering a prompt or profile member;
- materially changing prompt source, fixtures, rendering, or completion rules;
- changing a prompt's identity, primary capability, scoring role, deterministic
  check, manual rubric, hybrid combination rule, or score meaning;
- changing profile definitions, profile aggregation, required coverage, or the
  relationship among `smoke`, `core`, and `extended`;
- changing defaults or metadata semantics needed to reproduce or compare the
  evaluation.

Editorial documentation changes that cannot affect execution, evidence
interpretation, or scoring do not require a suite version. When that safety is
uncertain, treat the change as material. Old versions, their prompt ordering,
and the evidence needed to interpret their results remain available and
unchanged.

## Controlled capability vocabulary

Every prompt declares exactly one `primary capability` from this controlled
vocabulary. The primary capability states the main behavior the task is designed
to evaluate; it is the only tag counted toward required profile coverage.

| Tag | Capability boundary |
| --- | --- |
| `instruction-following` | Follows explicit, relevant constraints and resolves instruction priority within the supplied task. |
| `structured-output` | Produces a specified parseable structure, fields, types, cardinality, ordering, or no-extra-text form. |
| `honesty-uncertainty` | Distinguishes known, inferable, missing, and unknowable information without fabrication. |
| `summarization` | Compresses supplied material while preserving its material meaning and boundaries. |
| `extraction` | Maps grounded source information into requested fields or categories with explicit unknown handling. |
| `planning` | Produces a bounded, ordered, dependency-aware plan without claiming execution. |
| `technical-explanation` | Explains a technical concept, mechanism, or tradeoff accurately for the stated audience. |
| `coding` | Produces or changes self-contained code against stated behavioral requirements. |
| `code-review` | Identifies and prioritizes defects, risks, or contract violations in supplied code or patches. |
| `troubleshooting` | Diagnoses supplied symptoms and proposes discriminating, safe next checks. |
| `safety-refusal` | Calibrates assistance, caution, or refusal to the actual risk without unsafe compliance or needless over-refusal. |
| `tool-preparation` | Selects a declared tool or prepares structured arguments without executing it or claiming effects. |
| `bounded-context` | Retrieves, reconciles, or follows information within an explicitly declared, controlled context bound. |

`bounded-context` is deliberately narrower than a general long-context claim. A
short constraint-retention task or a context-window preset alone does not
establish this coverage.

A prompt may also declare zero or more unique `secondary stressors`. These do not
satisfy primary coverage and do not create separate scores. The initial
controlled stressor vocabulary is:

- `noise` — relevant material must be distinguished from supplied distractors;
- `late-constraints` — a material constraint occurs late in the supplied input;
- `adversarial-instructions` — supplied content contains conflicting or
  untrusted instructions that must not control the response;
- `strict-length` — the response must obey an objectively bounded length.

The primary capability must not be repeated as a secondary tag. Tags support
coverage audits and prompt-role disclosure; they do not imply equal difficulty,
score comparability, or an aggregate capability score. Adding or redefining a
tag is an architecture decision. Using that change in a released prompt
inventory requires a new suite version.

## Profile coverage and duplication

The `smoke` profile must cover, through primary capabilities:

1. basic `instruction-following`;
2. one objective `structured-output` task;
3. one grounded `summarization` or `extraction` task;
4. one `honesty-uncertainty` or `safety-refusal` boundary.

It remains a strict subset of `core` and must be small enough for rapid operator
feedback. Secondary stressors cannot satisfy these requirements. Smoke results
are health signals, not a representative quality ranking, abbreviated Core
score, or basis for broad model recommendations.

The `core` profile must cover every capability in the controlled vocabulary at
least once as a primary capability. Coverage by a secondary stressor does not
count. The accepted prompt-role inventory must demonstrate balance as well as
presence; repeated uncertainty, operations, or formatting tasks may not crowd
out weak capabilities merely because each has a different surface form.

A task family is a shared underlying task pattern, input transformation, or
judgment objective, regardless of renamed entities or changed surface domain. A
task family may appear at most once in `smoke` and at most twice in `core`. A
second Core member requires a documented, materially distinct observable
objective and explicit approval in the duplication review. Additional variants
belong in a later `extended` version or a separate specialized suite. In
particular, fake-package honesty, small parser generation, configuration review,
and platform-update advice must not be multiplied to simulate breadth.

## Portability boundary

Every `core` and `smoke` prompt must be self-contained and answerable without
private or user-owned information. Generic Core excludes dependencies on:

- LLMGauge, WumboLabs, another private project, repository state, result schema,
  release process, publication workflow, or organization-specific convention;
- a particular operating system, distribution, shell, package manager, service,
  agent harness, or vendor platform unless all necessary behavior is fully
  supplied as inert task material;
- specific GPUs, accelerators, drivers, storage stacks, host configuration, or
  consumer hardware;
- current events, current prices, live package or API state, network access, or
  knowledge that can become stale relative to the versioned prompt;
- private paths, credentials, environment state, personal data, or unstated
  external tools.

Portable technical material may mention a platform or hardware concept only
when the prompt supplies every fact needed and evaluates a general capability
rather than familiarity with that platform. Practical, operator, currentness,
and hardware-specific tasks remain valuable in their own identities; they are
not duplicated into Generic Core.

## Scoring roles and provenance

Every future prompt must declare exactly one scoring role before prompt
implementation is admitted:

- **`deterministic`** — evaluates only objective, locally inspectable properties
  under versioned rules, such as parseability, exact fields and types, explicit
  extraction mappings, bounded fixture-backed execution, or a closed answer
  set.
- **`manual`** — evaluates semantic correctness, reasoning quality, usefulness,
  uncertainty, safety calibration, explanation, or other judgment under a named,
  versioned rubric.
- **`hybrid`** — retains both a deterministic component and an independent manual
  component when objective conformance and semantic quality are both material.

The role, check or rubric identity and version, inputs, outcome, reviewer state,
and any combination rule are scoring provenance. They must be preserved with the
result. A deterministic result is evidence about its declared objective; it is
not a manual quality verdict. A manual score must remain distinguishable as
reviewed, unreviewed, partial, or missing. Automatic or assisted drafts remain
review-required drafts and must never be relabeled as manual review.

Hybrid scoring must store the deterministic and manual components separately.
Its combination rule must be declared before execution and must not infer,
replace, fabricate, or silently zero one component when the other is absent or
fails. Reports and comparisons must expose the component states and the applied
rule rather than presenting an unexplained blended number.

Lexical checks may enforce an explicitly required literal token or serve as
clearly labeled triage. They must not stand in for general semantic correctness,
honesty, safety, explanation quality, or instruction following. A phrase
checklist is not a general answer-quality scorer.

## Comparison and claim boundaries

Aggregate like-for-like comparison requires the same suite ID, suite version,
profile, exact ordered prompt membership, scoring roles and scoring-rule
versions, rubric and review state, and aggregation method. Comparisons must also
disclose model and provenance, prompt set, scoring mode, rubric, runtime,
generation settings, hardware disclosure state, and any difference among them.

A deliberate comparison across runtimes or other tested conditions may describe
prompt-level or profile-level observations only when the differing variable and
non-equivalent metrics are explicit. Different suite versions, profile
memberships, custom prompt sets, scoring modes, or rubrics must not be collapsed
into one score or rank. Missing or partial manual review remains visible and
cannot be filled by deterministic evidence.

`smoke` must always be labeled as `smoke`; it is not representative of Core
quality and must not be extrapolated into a general capability ranking. Generic
Core quality scores must not be combined with throughput, latency, VRAM,
LocalMaxxing or other performance measures, external benchmark scores, or
agent-environment outcomes. Those metrics have different subjects and authority
and must remain separate comparison dimensions.

No Generic Core result alone proves universal model rank, daily-driver fit,
untested safety, agent effectiveness, or performance efficiency.

## Coexistence and non-mutation

The new identity coexists with every current suite:

| Suite identity | Protected role |
| --- | --- |
| `core-v1` `0.1.0` | Existing Tier 1 practical smoke suite; remains valid under its current identity and `core` alias and is not Generic Core. |
| `wumbolabs-practical-v1` `0.2.0` | Current practical/operator profile with its existing manual scoring and evidence boundaries. |
| `agent-backend-v1` `0.1.0` | Native-response agent-preparation suite; it does not establish executed agent-environment behavior. |
| `context-v1` `0.1.0` | Context preset metadata; it is not prompt capability evidence or a Generic Core profile. |

Existing aliases, loading behavior, suite source, prompts, baselines, rubrics,
results, reports, and evidence remain unchanged by this contract. Historical and
evidence-bound identities must never be edited in place to adopt this contract.
Current specialized suites may evolve only through explicit new versions that
preserve old evidence. No Generic Core implementation may rewrite, relabel,
rescore, migrate, or claim supersession of an existing result.

## Acceptance gates for prompt and scoring design

The later **Generic Core prompt and scoring design** milestone is admitted only
when one reviewable design package provides all of the following without
mutating historical suites:

1. **Approved capability coverage:** a matrix proving all Core primary coverage
   and the four smoke obligations from the controlled vocabulary.
2. **Prompt-role inventory:** stable proposed prompt IDs, task-family ownership,
   exactly one primary capability, optional controlled secondary stressors, and
   no final implementation hidden outside the inventory.
3. **Deterministic-check feasibility:** each proposed deterministic component has
   an objective property, bounded local method, inspectable inputs and outcome,
   and documented false-positive and false-negative risks.
4. **Duplication review:** every task family is identified, the smoke/Core limits
   are met, and any second Core variant has an approved distinct objective.
5. **Scoring provenance:** every prompt declares `deterministic`, `manual`, or
   `hybrid`, with proposed versioned checks or rubric ownership and explicit
   hybrid component handling.
6. **Version and profile membership:** the design fixes `generic-core-v1`
   `0.1.0`, canonical prompt order, and explicit ordered `smoke` and `core`
   membership; any proposed `extended` membership remains separately declared.
7. **Portability review:** every prompt is self-contained and free of private,
   project-specific, platform-specific, hardware-specific, current-event, live
   network, or user-environment dependencies.
8. **Historical protection:** the design changes no existing suite, prompt,
   baseline, rubric, result, report, loader, schema, alias, or evidence artifact.

Passing these gates authorizes prompt and scoring design review only. It does not
authorize suite manifests, prompt files, baselines, rubrics, loaders, schemas,
CLI changes, scoring code, model execution, benchmarks, or agent harnesses.
