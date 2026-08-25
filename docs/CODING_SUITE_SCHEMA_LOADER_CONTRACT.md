# Coding Suite Schema and Loader Contract

## Status and scope

Status: accepted architecture contract for representing and loading
`coding-core-v1` version `0.1.0`.

This document defines the smallest additive suite-manifest, prompt metadata,
normalization, loading, source/package, compatibility, and validation boundary
needed to represent the accepted
[Coding Suite Prompt and Task-Family Design](CODING_SUITE_PROMPT_TASK_FAMILY_DESIGN.md)
and [Coding Suite Scoring-Method Design](CODING_SUITE_SCORING_METHOD_DESIGN.md).
The [Coding Suite Architecture and Scoring Contract](CODING_SUITE_ARCHITECTURE_SCORING_CONTRACT.md)
remains authoritative for suite identity, evaluated subject, containment class,
and claims.

This is documentation only. It creates no manifest, prompt, fixture,
response-form resource, schema model, validator, loader behavior, normalized
runtime value, scoring implementation, result field, package-data declaration,
or execution capability. `coding-core-v1` remains unavailable.

## Decision summary

Admission is **PASS** for an additive extension of the existing
`llmgauge.suite.v0` profile-aware manifest. No new manifest schema version is
required. Existing generic fields already represent suite identity, prompt ID
and source, ordered profiles and default selection, custom selection, capability
metadata, scoring role and references, fixture references, and contained
resources. Coding adds only prompt metadata that the existing contract cannot
state honestly:

- `task_family`;
- `interaction_mode`;
- `execution_mode`;
- a closed `response_form` category plus versioned form-definition reference;
  and
- a versioned `hybrid_composition` reference for hybrid prompts.

These fields are optional at the generic `llmgauge.suite.v0` layer and required
as a complete set only for `coding-core-v1` `0.1.0`. Coding capability and
stressor values extend the existing controlled vocabularies. The loader must
normalize every admitted field explicitly and apply exact coding-suite
invariants; it must not infer them from prompt text, IDs, paths, or checks.

The existing `hybrid_rule: side-by-side` remains the generic structural
cardinality declaration for profile-aware manifests. For Coding Core hybrid
prompts, `hybrid_composition` supplies the versioned scoring identity and is the
semantic authority; `hybrid_rule` must also be present and equal
`side-by-side`. A disagreement is invalid. This narrow compatibility assertion
avoids changing the existing field while preventing duplicated, conflicting
behavior.

## Current-contract assessment

The classifications below are exhaustive for this milestone.

| Coding-suite requirement | Classification | Representation or decision |
|---|---|---|
| Suite ID `coding-core-v1` | Already represented | Existing required top-level `suite_id` |
| Suite version `0.1.0` | Already represented | Existing required top-level `suite_version` |
| Exact `smoke` and default `core` membership/order | Already represented | Existing `profiles.<name>.prompt_ids`, `default_profile`, top-level prompt order, plus suite-specific invariants |
| Custom prompt selection | Already represented | Existing explicit custom selection; normalized as custom, never a named profile |
| Prompt ID | Already represented | Existing prompt `id`, unique in canonical inventory |
| Prompt source | Already represented | Existing prompt `file`, resolved as a contained regular file |
| Task family | Requires additive optional field | Prompt `task_family`, controlled and mandatory for this suite/version |
| Primary capability | Representable through existing generic field | Existing `primary_capability`; controlled enum gains coding values |
| Secondary stressors | Representable through existing generic field | Existing `secondary_stressors`; controlled enum gains coding values |
| Static single-turn classification | Requires additive optional field | Prompt `interaction_mode`, exactly `static-single-turn` for this suite/version |
| Generated-output execution prohibition | Requires additive optional field | Prompt `execution_mode`, exactly `none`; no execution value is admitted |
| Owned inert input or fixture references | Representable through existing generic field | Existing closed `fixtures` references; empty list is explicit |
| Permitted response form | Requires additive optional field | Closed prompt `response_form` with category and versioned definition reference |
| Manual rubric reference | Already represented | Existing `scoring.manual_rubric` logical ID/version |
| Deterministic check references | Already represented | Existing singular `scoring.deterministic_check` logical ID/version; one check suffices for each admitted hybrid role |
| Manual/hybrid scoring role | Already represented | Existing `scoring.role` and `hybrid_rule` cardinality |
| Versioned hybrid composition | Requires additive optional field | `scoring.hybrid_composition` logical ID/version, mandatory only for coding hybrid prompts |
| Comparison-relevant normalized identity | Representable by extending normalized output | Normalize the additive logical fields and owned resource identities; no private root |
| Editable/package/installed ownership | Already represented by loader/package convention | Fixed roots and `importlib.resources`; not manifest data |
| Source/package byte equivalence | Already represented by validation/build contract | Compare all suite-owned relative paths and bytes; not a second manifest authority |
| Result artifact scoring state | Already represented outside suite loading | Existing execution, deterministic, and manual result authorities remain unchanged; no result-schema delta |
| Multi-turn repair membership | Not admitted | `repair/prior-response-test-feedback` is not a static prompt or profile member |
| Generated code, test, patch, or command execution | Not admitted | Any execution declaration other than `none` fails for this suite/version |
| Patch application, dynamic import, network retrieval | Not admitted | No schema field or loader behavior is added |

Because all required facts are either already representable or need additive
optional metadata, `schema_version: llmgauge.suite.v0` remains correct. A new
schema version would add compatibility cost without representing a breaking
format change.

## Ownership and precedence

Each fact has one authority:

| Fact | Authoritative location | Normalized/result treatment |
|---|---|---|
| Suite ID/version, canonical prompt inventory | Manifest top level | Preserved in normalized suite and later suite identity |
| Named/default profile membership | Manifest `profiles` and `default_profile` | Exact ordered tuples plus selected profile/custom state |
| Prompt source | Prompt `file` | Portable relative path and owned bytes; resolved host path remains internal |
| Task family, capability, stressors, interaction/execution mode | Prompt metadata | Preserved exactly; never inferred |
| Permitted response boundary | Prompt `response_form` | Category and logical form ID/version preserved |
| Owned inert resources | Prompt `fixtures` | Logical ID/version/path and contained target preserved |
| Scoring role and method references | Prompt `scoring` | Role, check/rubric/composition IDs and versions preserved |
| Response-form delimiter, patch grammar, JSON fields, extraction rules | Later versioned response-form resource selected by the manifest reference | Deferred; not duplicated in prompt metadata |
| Rubric/check/composition semantics | Versioned scoring owners named by logical references | Loader validates support only; scoring boundary applies behavior |
| Source/package equivalence | Repository validation and packaging checks | No runtime search for a second copy |
| Generation and scoring outcomes | Existing result artifacts | Never synthesized by the suite loader |

Prompt metadata cannot override top-level profile membership. Profiles cannot
override prompt entries. Response-form definitions cannot change scoring role.
Scoring registries cannot reinterpret manifest paths. Result artifacts record
observed outcomes and never repair suite declarations.

## Additive manifest shape

The future manifest remains `llmgauge.suite.v0`. This abbreviated example fixes
field shape but deliberately does not create final filenames or form resources:

```yaml
schema_version: llmgauge.suite.v0
suite_id: coding-core-v1
suite_version: 0.1.0
default_profile: core
profiles:
  core:
    prompt_ids:
      - debug/state-transition-defect
      # seven remaining members in canonical order
  smoke:
    prompt_ids:
      - debug/state-transition-defect
      - patch/bounded-cross-file-change
      - shell/safe-repository-maintenance
      - structured/closed-json-change-record
prompts:
  - id: debug/state-transition-defect
    file: prompts/debug-state-transition-defect.txt
    task_family: supplied-code-debugging
    primary_capability: debugging
    secondary_stressors:
      - scope-control
      - dependency-api-uncertainty
    interaction_mode: static-single-turn
    execution_mode: none
    response_form:
      category: explanation-plus-code
      definition:
        id: coding-core-explanation-plus-code-form-v0
        version: 0.1.0
    scoring:
      role: manual
      manual_rubric:
        id: coding-core-manual-v0
        version: 0.1.0
    fixtures: []
```

The illustrative prompt filename is not accepted final content. The field names,
closed object shapes, logical IDs, versions, and mappings in this contract are
the implementation contract.

### Additive field shapes

For a coding prompt, the new fields have these closed meanings:

| Field | Shape and allowed value | Failure behavior |
|---|---|---|
| `task_family` | One non-empty controlled identifier; exact mapping below | Missing, wrong type, unknown value, or wrong prompt mapping is invalid |
| `interaction_mode` | One controlled string; only `static-single-turn` is supported for `coding-core-v1` `0.1.0` | Missing or any other value is invalid; no downgrade or transcript inference |
| `execution_mode` | One controlled string; only `none` is supported | Missing or any execution-bearing value is invalid |
| `response_form` | One closed object with exactly `category` and `definition` | Missing, unknown nested field, unsupported category/reference, or wrong prompt mapping is invalid |
| `response_form.category` | One of `code-only`, `explanation-plus-code`, `explanation-only`, `bounded-patch`, `closed-json-record` | Unknown category is invalid |
| `response_form.definition` | Closed logical reference with exactly `id` and semantic `version` | Malformed or unsupported reference is invalid; no path or latest-version fallback |
| `scoring.hybrid_composition` | Closed logical reference with exactly `id` and `version`; present only for `hybrid` coding prompts | Missing for hybrid, present for manual, malformed, unsupported, or inconsistent with `hybrid_rule` is invalid |

Unknown top-level and direct prompt fields retain existing opaque-metadata
compatibility. Unknown fields inside `response_form`, `definition`, `scoring`,
method references, profile, or fixture objects are errors because those objects
are contract-owned. Partial adoption of coding-required metadata is invalid for
this suite/version.

## Exact inventory and metadata

Top-level `prompts` defines this canonical order and exact metadata. Controlled
vocabularies are identifiers, not display text.

| Order | Prompt ID | Task family | Primary capability | Secondary stressors |
|---:|---|---|---|---|
| 1 | `debug/state-transition-defect` | `supplied-code-debugging` | `debugging` | `scope-control`, `dependency-api-uncertainty` |
| 2 | `patch/bounded-cross-file-change` | `minimal-patch-generation` | `minimal-patch-generation` | `scope-control`, `structured-output-compliance` |
| 3 | `tests/behavioral-contract-cases` | `test-design-and-creation` | `test-creation` | `scope-control`, `structured-output-compliance` |
| 4 | `diagnosis/supplied-failure-output` | `failure-output-diagnosis` | `failure-diagnosis` | `debugging`, `scope-control`, `dependency-api-uncertainty` |
| 5 | `shell/safe-repository-maintenance` | `safe-command-recommendation` | `shell-command-safety` | `scope-control`, `dependency-api-uncertainty` |
| 6 | `api/closed-evidence-integration` | `dependency-api-uncertainty` | `dependency-api-uncertainty` | `scope-control`, `debugging` |
| 7 | `scope/distractor-aware-change-plan` | `scoped-change-planning` | `scope-control` | `minimal-patch-generation`, `dependency-api-uncertainty` |
| 8 | `structured/closed-json-change-record` | `structured-coding-response` | `structured-output-compliance` | `scope-control`, `instruction-compliance` |

The primary-capability vocabulary gains these eight values for the coding suite:
`debugging`, `minimal-patch-generation`, `test-creation`, `failure-diagnosis`,
`shell-command-safety`, `dependency-api-uncertainty`, `scope-control`, and
`structured-output-compliance`.

The secondary-stressor vocabulary gains the values used above that are not
already supported: `scope-control`, `dependency-api-uncertainty`,
`structured-output-compliance`, `debugging`, `minimal-patch-generation`, and
`instruction-compliance`. No value is inferred from a primary capability. Exact
lists, including order, are suite-version invariants.

The debug role's dependency/API stressor requires the final prompt to retain the
accepted explicitly unknown contract fact. It does not authorize external
lookup. If content cannot honestly instantiate that stressor, content admission
fails rather than silently dropping the declared value.

## Exact response-form and scoring mapping

Every prompt selects exactly one response form and the scoring references below.
There is no prompt-level override by profile.

| Prompt ID | Response category and definition | Role | Deterministic check | Manual rubric | Composition |
|---|---|---|---|---|---|
| `debug/state-transition-defect` | `explanation-plus-code`; `coding-core-explanation-plus-code-form-v0` `0.1.0` | `manual` | none | `coding-core-manual-v0` `0.1.0` | none |
| `patch/bounded-cross-file-change` | `bounded-patch`; `coding-core-bounded-patch-form-v0` `0.1.0` | `hybrid` | `coding-core-bounded-patch-envelope-v0` `0.1.0` | `coding-core-manual-v0` `0.1.0` | `coding-core-side-by-side-v0` `0.1.0` |
| `tests/behavioral-contract-cases` | `code-only`; `coding-core-code-only-tests-form-v0` `0.1.0` | `hybrid` | `coding-core-code-only-tests-envelope-v0` `0.1.0` | `coding-core-manual-v0` `0.1.0` | `coding-core-side-by-side-v0` `0.1.0` |
| `diagnosis/supplied-failure-output` | `explanation-only`; `coding-core-explanation-only-form-v0` `0.1.0` | `manual` | none | `coding-core-manual-v0` `0.1.0` | none |
| `shell/safe-repository-maintenance` | `explanation-only`; `coding-core-explanation-only-form-v0` `0.1.0` | `manual` | none | `coding-core-manual-v0` `0.1.0` | none |
| `api/closed-evidence-integration` | `explanation-plus-code`; `coding-core-explanation-plus-code-form-v0` `0.1.0` | `manual` | none | `coding-core-manual-v0` `0.1.0` | none |
| `scope/distractor-aware-change-plan` | `explanation-only`; `coding-core-explanation-only-form-v0` `0.1.0` | `manual` | none | `coding-core-manual-v0` `0.1.0` | none |
| `structured/closed-json-change-record` | `closed-json-record`; `coding-core-closed-json-record-form-v0` `0.1.0` | `hybrid` | `coding-core-closed-json-record-v0` `0.1.0` | `coding-core-manual-v0` `0.1.0` | `coding-core-side-by-side-v0` `0.1.0` |

For every hybrid entry, existing `hybrid_rule` is exactly `side-by-side` in
addition to the listed composition reference. Manual entries prohibit
`deterministic_check`, `hybrid_rule`, and `hybrid_composition`. No deterministic
role exists. Unknown IDs or versions, role-incompatible references, missing
references, or extra scoring fields fail closed. The loader validates declared
support and compatibility but does not run a check or create a score.

## Profiles and selection

`coding-core-v1` `0.1.0` has exactly two profiles, `smoke` and `core`, and
`default_profile` is exactly `core`. The canonical top-level inventory is the
`core` order.

`smoke.prompt_ids` is exactly:

1. `debug/state-transition-defect`;
2. `patch/bounded-cross-file-change`;
3. `shell/safe-repository-maintenance`; and
4. `structured/closed-json-change-record`.

`core.prompt_ids` is exactly:

1. `debug/state-transition-defect`;
2. `patch/bounded-cross-file-change`;
3. `tests/behavioral-contract-cases`;
4. `diagnosis/supplied-failure-output`;
5. `shell/safe-repository-maintenance`;
6. `api/closed-evidence-integration`;
7. `scope/distractor-aware-change-plan`; and
8. `structured/closed-json-change-record`.

The loader preserves declared order and never sorts, deduplicates, inserts, or
drops members. There is no `full`, `extended`, implicit remainder, alternate
rendering, or dynamic profile. `smoke` is a strict `core` subsequence and uses
the same prompt entry, source, resources, response form, and scoring references.

Existing custom selection remains compatible. Any subset or explicit prompt
selection is normalized as an exact ordered custom set, not relabeled as a named
profile or complete capability coverage. Unknown or duplicate requested prompt
IDs fail under existing selection behavior.

`repair/prior-response-test-feedback` is multi-turn-only, is not a prompt ID in
this suite version, and may not appear in canonical inventory, either profile,
or a custom selection resolved from this manifest.

## Resource representation and containment

The existing `file` field owns prompt source. The existing `fixtures` list owns
all separately referenced, suite-controlled inert input needed by a coding
prompt. A fixture reference remains the closed shape:

```yaml
id: <stable logical ID>
version: <MAJOR.MINOR.PATCH>
path: <normalized suite-relative POSIX path>
```

No coding-specific input field is added. The later content milestone decides
which prompts need fixtures and their IDs, versions, paths, bytes, and prompt
rendering. A fixture path does not imply type, semantics, scoring input,
execution, or filesystem authority.

Every loader-resolved prompt, fixture, or later form resource path must:

- be a non-empty normalized relative POSIX path rooted at the resolved suite;
- have no absolute or drive prefix, URI scheme, backslash, empty segment, `.`
  segment, or `..` segment;
- pass lexical checks before resolution;
- resolve after symlink handling inside the selected suite root;
- identify an existing readable regular file, not a directory, symlink escape,
  FIFO, socket, device, or other special file; and
- retain its portable relative spelling separately from an internal host path.

Missing, unreadable, escaped, or non-regular references are definition errors.
The loader never searches the working directory, checkout, another suite, home
directory, environment path, mutable external repository, or network. It does
not retrieve a URL. A missing installed resource cannot fall back to editable
source.

Generated content is untrusted response data. A path, patch header, JSON field,
command, or code fragment emitted by a model cannot add, override, redirect, or
cause resolution of any manifest resource. The loader performs no import,
template evaluation, plugin discovery, shell call, patch application, or code,
test, command, or response execution.

## Source, package, and installed ownership

The future content has exactly these roots:

- editable source: `suites/coding-core-v1/`;
- packaged mirror and package-data owner:
  `src/llmgauge/builtin_suites/coding-core-v1/`; and
- installed discovery: the `llmgauge.builtin_suites` package through
  `importlib.resources`, following current builtin-suite behavior.

The editable and packaged trees must contain exactly the same suite-owned
relative files with byte-identical contents: manifest, prompts, inert resources,
and versioned response-form resources admitted by the content milestone. A
missing, extra, renamed, or byte-different owned file is a source/package
mismatch. Repository validation and package/build tests compare the two roots
and fail before release. The runtime loader validates only the one resolved root
and never searches for or merges a second copy.

Installed discovery must use packaged resources and produce the same logical
normalized suite as editable discovery: same manifest values, canonical/profile
order, metadata, logical references, relative paths, and owned bytes. Only the
internal physical root and resolved host paths may differ.

Portable normalized identity includes suite ID/version, manifest schema, exact
selected profile or custom state and ordered membership, prompt IDs, task and
capability metadata, interaction/execution mode, response-form category and
logical definition ID/version, scoring role and method IDs/versions, fixture
IDs/versions/relative paths, prompt/resource relative paths, and the applicable
owned bytes or their canonical identity. It excludes checkout, current working
directory, install, home, executable, temporary, and other physical private
paths.

A missing packaged manifest or resource is a package-data/definition failure.
There is no source, checkout, current-directory, network, or nearest-version
fallback. Errors name bounded logical suite locations, not private roots.

## Compatibility

Legacy manifests with neither `profiles` nor `default_profile` remain valid and
need none of the coding fields. Their full canonical prompt list remains the
default legacy-all selection. Existing profile-aware suites retain their current
field requirements and do not acquire `task_family`, `interaction_mode`,
`execution_mode`, `response_form`, or `hybrid_composition` requirements merely
because those optional generic fields exist.

Current suite identities, aliases, versions, prompt orders, resources, and
results are unchanged. The formerly tracked source-only historical suite
`wumbolabs-practical-use-v1` `0.1.0` has since been removed from the repository;
this contract never created a package mirror for it or made it subject to Coding
Core metadata. Existing Generic Core source/package behavior and accepted method
identities remain Generic Core-owned.

Unknown top-level and direct prompt metadata continues to be preserved opaquely.
The new coding fields gain semantics only when recognized by the implemented
schema, and coding-specific exact mappings apply only to `coding-core-v1`
`0.1.0`. There is no migration, alias, inferred default, latest-version lookup,
or compatibility shim. Valid historical result directories are not modified or
re-scored.

## Normalized loader output

After complete validation and selection, the loader returns one immutable
normalized suite containing at minimum:

- manifest schema, suite ID, and suite version;
- internal resolved suite root, excluded from portable identity;
- complete canonical ordered prompt IDs;
- exact ordered profile mappings and declared default profile;
- selected named profile or explicit custom/legacy selection state and exact
  ordered members;
- for every canonical prompt: ID, normalized prompt-source path, contained
  regular-file target, task family, primary capability, ordered secondary
  stressors, interaction mode, execution mode, response-form category and
  definition ID/version, scoring role and check/rubric/composition references,
  generic hybrid rule where applicable, and fixture references;
- each fixture's logical ID/version, portable path, and contained regular-file
  target; and
- preserved opaque compatible top-level and direct prompt metadata.

The selected view references canonical normalized prompt entries rather than
copying or mutating them. Normalization never reads semantic meaning from prompt
or fixture contents, applies a scoring method, invents a missing declaration,
or creates a result outcome.

A suite-definition failure returns no normalized suite and creates no attempt,
response, check result, manual review, or partial result. Later generation,
check, and review states remain separate domains.

## Validation and public-safe errors

Validation is transactional: parse; validate root and schema; validate generic
objects; validate coding-suite identities and exact mappings; resolve contained
resources; validate selection; then return one normalized value. Independent
safe diagnostics may accumulate in stable manifest and profile order, but any
error prevents output.

The implementation must reject at least:

| Condition | Required failure |
|---|---|
| Duplicate YAML keys or prompt IDs | Definition error; never last-value-wins |
| Unknown or duplicate profile member | Definition error naming bounded logical profile/member |
| Profile member out of canonical order | Definition error; never sort or repair |
| Missing or invalid default profile | Definition error; no implicit `core` or all-prompts fallback |
| Wrong profile set or exact membership | Coding-suite invariant error |
| Unknown scoring-method or form reference/version | Definition error; no default/latest/nearest fallback |
| Scoring role/method incompatibility | Definition error, including forbidden extras and wrong hybrid rule/composition |
| Unsupported response category or wrong role mapping | Definition error |
| Partial coding metadata | Definition error; no inference from ID, filename, prompt, or scoring reference |
| Invalid, absolute, non-normalized, escaped, missing, unreadable, or non-regular reference | Containment/definition error; no fallback |
| Source/package missing, extra, or byte mismatch during repository/package validation | Equivalence failure; no preferred-copy repair |
| Incomplete hybrid declaration | Definition error unless check, rubric, `side-by-side`, and composition ref all match |
| Illegal multi-turn prompt or profile membership | Definition error; repair role is not admitted |
| Any `interaction_mode` other than `static-single-turn` | Definition error |
| Any `execution_mode` other than `none`, or another generated-output execution declaration | Definition error; no execution setup |
| Unknown field inside a contract-owned object | Definition error; opaque compatibility applies only outside owned nested objects |

Diagnostics use stable codes, bounded logical locations, and bounded messages
under the existing diagnostic limits. They may include suite ID, prompt ID,
profile name, reference ID/version, and portable relative path when safe. They
must not include prompt or fixture contents, raw YAML, model output, environment
values, credentials, unbounded exception text, or absolute checkout, working,
home, install, temporary, model, or executable paths. A source/package mismatch
reports a bounded relative logical file identity, not either private root or file
contents.

A check implementation `error`, model generation failure, truncated response,
or absent manual review is not a suite-definition error. Conversely, a manifest
or resource error cannot be hidden as a failed model response. Structural suite
validity establishes neither response conformance nor semantic quality.

## Deferred implementation boundary

The selected next milestone is **Coding-suite schema model and loader
implementation**. It is limited to implementing the five additive optional
generic fields (`task_family`, `interaction_mode`, `execution_mode`,
`response_form`, and `hybrid_composition`); extending only the accepted coding
capability and stressor vocabularies; normalizing the accepted fields and logical
references; validating the exact `coding-core-v1` `0.1.0` role, profile, form,
scoring, and non-execution invariants; preserving contained-reference and
no-fallback behavior; and adding focused schema, loader, compatibility,
package-source, and public-safe diagnostic tests.

It excludes final coding prompts, the coding suite manifest, suite-owned content
resources, source/package coding-suite trees, package-data inclusion for
`coding-core-v1`, scoring or deterministic-check implementation, result
integration, generated-code execution, multi-turn evaluation, Agent Harness
import, LocalMaxxing or Generic Core implementation, and release/version
changes. It adds no prompt, manifest, suite-content, scoring, execution, or
runtime work.

After that implementation passes, the next admitted gate remains **Coding-suite
content and package implementation**, limited to final prompt text, suite-owned
inert resources, manifest, exact profile membership, source/package mirrors,
package-data inclusion, and validation fixtures/tests required for that content.
If either implementation cannot satisfy this contract, admission fails rather
than weakening a mapping, reference, compatibility, or containment boundary.
