# Generic Core Schema and Loader Contract

Status: Accepted architecture contract for representing and loading
`generic-core-v1` version `0.1.0`.

This contract defines the smallest backward-compatible extension to the current
suite manifest and loader boundary. It is architecture only: it does not create
a suite, change a manifest, add a schema model, select prompts at the CLI, load a
fixture, run a check, alter scoring, or change result artifacts.

The accepted [Generic Core suite contract](GENERIC_CORE_SUITE_CONTRACT.md)
remains authoritative for suite identity, profile meaning, capability
vocabularies, versioning, comparison, and claim boundaries. The
[Generic Core prompt and scoring design](GENERIC_CORE_PROMPT_SCORING_DESIGN.md)
remains authoritative for the proposed `0.1.0` inventory, membership, fixture
ownership, and scoring roles. This document decides only how a future
implementation represents, validates, resolves, and normalizes those decisions.

## Decision summary

Generic Core uses additive fields in the existing `llmgauge.suite.v0` manifest,
not a new manifest format. The existing required `schema_version` field is the
format version discriminator; no second schema or format version field is
added.

A manifest adopts the profile-aware contract by declaring both `profiles` and
`default_profile`. In that mode every prompt must declare the complete new
capability, scoring, and fixture metadata set. When both top-level fields are
absent, the manifest remains a legacy manifest: its canonical `prompts` order is
selected in full by default, and none of the new per-prompt metadata is required.
The two top-level fields may not appear separately, and contract-owned
per-prompt metadata may not appear partially or without profile adoption.

This preserves all current suites without edits while making Generic Core's
ordered profiles and scoring ownership explicit and reproducible.

## Current compatibility baseline

The current manifest contract requires
`schema_version: llmgauge.suite.v0`; `suite_id`, `suite_version`, and `prompts`
retain their established meanings. The loader currently discovers editable
suite data under `suites/` and installed data under the package's
`builtin_suites/` tree. That source choice must not change suite meaning.

The following identities, versions, ordering, aliases, and evidence remain
unchanged:

- `core-v1` `0.1.0`;
- `wumbolabs-practical-v1` `0.2.0`;
- `agent-backend-v1` `0.1.0`;
- `context-v1` `0.1.0`.

`generic-core-v1` is a new identity, not a rename, replacement, version, or
alias of `core-v1`. Existing aliases continue to resolve to their current
identities. This contract adds no Generic Core alias. Existing source/package
mirrors keep their current identity and order, and the future packaged Generic
Core definition must be byte-equivalent in all suite-relative owned files to
its editable source. Historical result evidence is not migrated, reinterpreted,
or made subject to the new optional metadata.
Existing manifests already conform to these canonical identity fields and
require no edits. This contract introduces no `schema`, `id`, or `version`
aliases for suite identity and no compatibility shim or migration behavior.

## Additive manifest shape

The future representation is equivalent to this abbreviated YAML shape. It is
illustrative; it does not create a manifest or finalize fixture filenames.

```yaml
schema_version: llmgauge.suite.v0
suite_id: generic-core-v1
suite_version: 0.1.0
default_profile: core
profiles:
  core:
    prompt_ids:
      - generic-core-instruction-rewrite-01
      # remaining members in canonical prompt order
  smoke:
    prompt_ids:
      - generic-core-instruction-rewrite-01
      - generic-core-structured-json-01
      - generic-core-honesty-evidence-gap-01
      - generic-core-extraction-ledger-01
prompts:
  - id: generic-core-instruction-rewrite-01
    file: prompts/generic-core-instruction-rewrite-01.txt
    primary_capability: instruction-following
    secondary_stressors:
      - late-constraints
      - strict-length
    scoring:
      role: hybrid
      deterministic_check:
        id: generic-core-constraint-envelope-v0
        version: 0.1.0
      manual_rubric:
        id: default-manual-v0
        version: 0.1.0
      hybrid_rule: side-by-side
    fixtures: []
```

The current required top-level fields remain required with their current
meaning. The additive fields and their ownership are:

| Field | Cardinality and default | Owner | Failure behavior |
| --- | --- | --- | --- |
| `schema_version` | Exactly one; required for every manifest; only `llmgauge.suite.v0` is supported by this contract | Suite format | Missing, wrong type, or unsupported value fails closed as a root definition error; no alias is accepted |
| `profiles` | Legacy mode: absent; profile-aware mode: one non-empty mapping of unique profile names to profile objects; no implicit entries | Suite version | Presence without `default_profile`, an empty mapping, malformed names or objects, or invalid membership is a definition error |
| `default_profile` | Legacy mode: absent; profile-aware mode: exactly one name present in `profiles`; no implicit profile | Suite version | Presence without `profiles` or a name not declared by `profiles` is a definition error |
| `profiles.<name>.prompt_ids` | Exactly one non-empty ordered list of prompt IDs; no default and no inherited members | Suite version | Unknown, duplicate, or out-of-canonical-order members are definition errors |
| `primary_capability` | In profile-aware mode, exactly one per prompt; absent in legacy mode | Prompt definition under the suite version | Missing, wrong type, or unknown enum is a definition error |
| `secondary_stressors` | In profile-aware mode, exactly one list per prompt containing zero or more unique controlled values; no inferred values | Prompt definition under the suite version | Missing list, duplicate value, or unknown enum is a definition error |
| `scoring` | In profile-aware mode, exactly one object per prompt | Prompt definition and scoring owner | Missing, unknown nested field, invalid role/reference combination, or malformed reference is a definition error |
| `fixtures` | In profile-aware mode, exactly one list per prompt containing zero or more fixture references; empty means no fixture | Suite definition | Missing list, duplicate logical reference, malformed reference, or unsafe target is a definition error |

Profile names and reference IDs are non-empty stable identifiers, not display
labels. Profile names are unique mapping keys. Prompt IDs remain unique in the
canonical `prompts` inventory. Duplicate YAML mapping keys are invalid rather
than last-value-wins.

Unknown top-level manifest fields and unknown fields directly on a prompt retain
the current forward-compatible behavior: the loader preserves them as opaque
metadata and does not assign semantics to them. Unknown fields inside the new
contract-owned `profiles`, `scoring`, deterministic-check, manual-rubric, or
fixture objects are errors. This boundary prevents misspelled safety- or
scoring-relevant fields from being silently ignored without making legacy
extension data invalid.

## Legacy mode and profile selection

A manifest with neither `profiles` nor `default_profile` is valid legacy input.
It needs no new prompt fields and no rewrite. With no profile selection, its
selected prompt IDs are the complete `prompts` inventory in manifest order.
Existing category and explicit-prompt selection behavior remains outside this
contract and is unchanged.

A profile-aware manifest requires an explicit `default_profile`. When a caller
does not request a profile, the loader selects that declared default. Generic
Core `0.1.0` must declare `default_profile: core`; there is no loader-chosen or
CLI-chosen fallback. When a caller requests a profile, the name must exist in
the manifest. A requested unknown profile, or any requested profile for a legacy
manifest, is a selection error. It is not repaired by selecting the default,
`core`, or all prompts.

Profile selection does not mutate the suite definition. The normalized output
retains both the complete canonical inventory and the exact selected ordered
membership. A later subset, category, or explicit prompt filter must be recorded
as a custom prompt set and must not be reported as the complete named profile.

## Ordered membership and Generic Core invariants

The position of a prompt in top-level `prompts` defines canonical inventory
order. Each profile's `prompt_ids` must:

1. contain only IDs declared exactly once in that inventory;
2. contain each member at most once;
3. be non-empty; and
4. have strictly increasing canonical inventory positions.

The loader does not sort, deduplicate, insert, or drop members. Unknown members,
duplicate members, and a known member placed before an earlier canonical member
are separate definition diagnostics. Any such error prevents normalized output.

For `generic-core-v1` `0.1.0`, suite-specific validation additionally requires:

- exactly the profiles `core` and `smoke`; `extended` is not defined for this
  version;
- `core.prompt_ids` exactly equals the complete 13-prompt canonical inventory;
- `smoke.prompt_ids` is non-empty, smaller than `core`, and a strict subsequence
  of `core.prompt_ids`;
- `smoke.prompt_ids` is exactly, in this order:
  `generic-core-instruction-rewrite-01`,
  `generic-core-structured-json-01`,
  `generic-core-honesty-evidence-gap-01`, and
  `generic-core-extraction-ledger-01`; and
- the same prompt entry, source, fixtures, rendering metadata, and scoring
  references serve every profile containing that prompt. Profiles cannot
  override prompt definitions.

These checks enforce Smoke as a strict Core subset preserving Core-relative
order. Smoke is not a separate suite, alternate rendering, abbreviated Core
score, or dynamically sampled set.

## Per-prompt capability metadata

Every prompt in a profile-aware manifest declares exactly one
`primary_capability`. For Generic Core `0.1.0`, the allowed values are the 13
controlled values in the suite contract:

- `instruction-following`;
- `structured-output`;
- `honesty-uncertainty`;
- `summarization`;
- `extraction`;
- `planning`;
- `technical-explanation`;
- `coding`;
- `code-review`;
- `troubleshooting`;
- `safety-refusal`;
- `tool-preparation`; and
- `bounded-context`.

`secondary_stressors` is an explicit list, including an empty list when none
apply. Its values are unique and drawn only from `noise`, `late-constraints`,
`adversarial-instructions`, and `strict-length`. No tag is inferred from prompt
text, filenames, categories, fixtures, or scoring. Unknown enum values fail
closed. Capability and stressor values describe coverage; they do not create
scores.

Generic Core-specific validation must also confirm the accepted prompt design's
one-to-one primary capability assignment and exact stressor lists. A metadata
change that affects a released inventory requires a new suite version; the
loader does not reinterpret an old version under a new vocabulary.

## Scoring roles and reference consistency

The `scoring.role` value is exactly one of `deterministic`, `manual`, or
`hybrid`. Its sibling fields have these cardinalities:

| Role | `deterministic_check` | `manual_rubric` | `hybrid_rule` |
| --- | --- | --- | --- |
| `deterministic` | Exactly one | Absent | Absent |
| `manual` | Absent | Exactly one | Absent |
| `hybrid` | Exactly one | Exactly one | Exactly `side-by-side` |

No field is synthesized. A forbidden field, a missing required field, an
unknown role, or an unknown hybrid rule is a definition error. `side-by-side`
means deterministic and manual evidence remain independent: neither is blended,
weighted, promoted, substituted for, or used to fill the other. The scoring
role is declaration and provenance, not a loader-time score.

For Generic Core `0.1.0`, deterministic references must match the accepted D1
through D7 mapping and version `0.1.0`; manual and hybrid prompts must reference
`default-manual-v0` version `0.1.0`. The stable deterministic IDs are:

- D1: `generic-core-constraint-envelope-v0`;
- D2: `generic-core-typed-record-json-v0`;
- D3: `generic-core-summary-envelope-v0`;
- D4: `generic-core-ledger-extraction-v0`;
- D5: `generic-core-interval-function-v0`;
- D6: `generic-core-tool-request-v0`; and
- D7: `generic-core-context-reconciliation-v0`.

A suite may not replace a missing deterministic check with lexical scoring,
replace a missing rubric with a default, or downgrade `hybrid` to another role.
Reference identity and version validation establishes declared ownership only;
it does not report that a check ran or that manual review exists.

## Versioned references

Checks and rubrics are logical references with exactly this closed shape:

```yaml
id: <non-empty stable logical ID>
version: <supported MAJOR.MINOR.PATCH version>
```

They contain no path. Their implementation or rubric ownership is resolved by
the scoring boundary, not by importing code or files named by the manifest.
Unsupported logical IDs or versions are definition errors once the owning
registry is admitted. `generic-core-v1` must not ship as executable while any of
its declared scoring references is unsupported.

Fixture references have exactly this closed shape:

```yaml
id: <non-empty stable logical ID>
version: <supported MAJOR.MINOR.PATCH version>
path: <normalized suite-relative POSIX path>
```

Within one prompt, each fixture `(id, version)` pair is unique. Different
prompts may deliberately reference the same suite-owned fixture. A fixture path
does not confer semantics, select a check, or authorize execution. Material
fixture or scoring-reference changes require a new suite version under the
Generic Core suite contract.

The schema layer validates reference field presence, types, identifier syntax,
version syntax, and role cardinality. The owner of each admitted logical
reference defines which IDs and versions are supported. Unsupported manifest,
fixture, check, or rubric versions fail closed; there is no nearest-version,
latest-version, or unversioned fallback.

## Relative paths, containment, and source equivalence

Every loader-resolved suite file, including the existing prompt `file` field and
new fixture `path` fields, must use a normalized relative POSIX path rooted at
the resolved suite directory. A valid path:

- is a non-empty string;
- is not absolute and has no drive prefix, URI scheme, backslash separator,
  empty segment, `.` segment, or `..` segment;
- resolves after symlink handling to a target contained by the resolved suite
  root;
- names an existing regular file, not a directory, device, socket, or other
  special target; and
- retains its normalized relative form separately from any internal resolved
  host path.

Absolute fixture paths and traversal are definition errors. Lexical checks are
required before filesystem resolution; resolved containment is required after
resolution so a symlink cannot escape the suite root. Missing, unreadable, or
non-regular targets are definition errors. The loader never searches another
suite, the working directory, a user home, an environment path, or the network
to repair a reference.

Editable and packaged loading must produce the same logical normalized suite
for the same suite version: identical manifest values, canonical and profile
order, relative prompt and fixture paths, and owned file bytes. Only the
internal physical suite root and resolved host paths may differ. Those private
physical paths are execution details and must not become portable provenance.
A missing packaged resource is a definition/package-data failure, not permission
to fall back to editable source or a network retrieval.

## Loader ownership and deferred behavior

The suite loader may resolve only structural fixture facts:

- the declared fixture ID and version;
- the normalized relative path;
- the contained resolved regular-file target;
- existence and basic file type; and
- association with the declaring prompt.

The loader does not parse fixture content, infer a fixture type from its suffix,
validate expected mappings, choose check inputs, render fixture data into a
prompt, execute generated code, establish containment for D5, apply a check,
score an answer, or decide whether a manual rubric is applicable. Those duties
belong to separately admitted prompt rendering, deterministic-check, D5
containment, execution, and manual-review boundaries. A structurally resolved
fixture is not evidence that its semantics, safety, or score are valid.

The loader performs no imports, plugin discovery, dynamic attribute lookup,
template evaluation, shell invocation, or code execution from suite data. It
does not inspect or trust paths emitted by a model. Model output cannot add,
override, or redirect a manifest reference.

## Normalized loader output

Successful validation and selection returns one immutable normalized suite
value suitable for later execution and provenance. It contains at minimum:

- the manifest schema, suite ID, and suite version;
- the resolved suite root for internal resource access only;
- the complete canonical ordered prompt IDs;
- all declared profiles as exact ordered prompt-ID tuples;
- the declared default profile;
- the selected profile name, or an explicit legacy-all marker;
- the exact selected ordered prompt IDs;
- normalized prompt entries in canonical order, including prompt ID, normalized
  prompt-source path, contained resolved source target, capability metadata,
  scoring role, logical check/rubric references, hybrid rule, and fixture
  references where declared;
- contained resolved fixture targets alongside their portable normalized
  relative paths; and
- preserved opaque legacy top-level and prompt metadata.

The selection view references canonical normalized prompt entries rather than
copying or modifying them. Portable provenance records suite identity/version,
selected profile or custom-selection state, exact ordered membership, relative
resource identities, and declared scoring-reference identities/versions. It
must not rely on, or expose as portable identity, the checkout path or installed
package path.

A legacy suite normalizes with no declared profiles, no new capability/scoring
metadata, an explicit legacy-all selection marker, and selected membership equal
to canonical prompt order. This is not converted into a synthetic `core`
profile.

## Fail-closed validation and diagnostics

Suite loading is a transaction: parse, structurally validate, resolve contained
resources, validate suite-specific invariants, select, and then return one
normalized value. Any definition error returns no normalized suite and creates
no run attempt or partial result. The loader must not sort, deduplicate, drop an
unknown field it owns, repair a path, infer metadata, choose a fallback version,
or continue into execution.

Duplicate YAML mapping keys, YAML parse failures, a non-mapping root, a missing
or unsupported `schema_version`, or an unidentifiable suite root make later
interpretation unsafe and therefore short-circuit validation. Unsupported
`schema_version` values fail closed; they are not repaired through an alias,
fallback, or compatibility shim. Once the root is safe to inspect, independent
definition diagnostics accumulate in stable
manifest order, followed by profile and resource checks in declared order.

Diagnostics are structured with a stable code, bounded logical location, and
bounded message. A load emits at most 100 diagnostics; when more exist, the last
slot is a `diagnostics-truncated` record. Each rendered location and message is
limited to 512 Unicode code points. Diagnostics must not include fixture
contents, prompt contents, raw YAML, environment values, credentials, model
output, absolute private paths, or unbounded exception text.

Unknown behavior is explicit:

- unknown top-level and direct prompt fields are preserved as opaque legacy
  metadata;
- unknown fields inside contract-owned objects are definition errors;
- unknown controlled capability, stressor, scoring-role, or hybrid-rule enums
  are definition errors;
- unknown profile selections are selection errors with no fallback;
- unsupported manifest or reference versions are definition errors; and
- malformed combinations accumulate with other independent errors only after a
  safe root parse; they never produce partial normalized output.

## Failure-domain separation

A suite-definition failure occurs before model or provider execution. It is
reported as invalid suite input and cannot create an attempt, failed response,
check result, manual score, or reviewed outcome.

After a valid definition is loaded, later domains remain distinct:

- provider startup, transport, protocol, model, timeout, OOM, cancellation, and
  partial-output failures are execution outcomes;
- deterministic `pass`, `fail`, `error`, and `not_run` are check outcomes tied to
  a supported check identity/version and preserved input references;
- manual `missing`, `unreviewed`, `partial`, and `reviewed` are review states,
  not loader states; and
- hybrid evidence preserves its deterministic outcome and manual state
  side-by-side without blending.

No later failure is relabeled as a suite-definition failure, and no definition
failure is hidden inside provider, model, check, or review output. Structural
validity establishes neither answer quality nor scoring success.

## Security boundaries

The loader boundary is local, deterministic, and data-only:

- no absolute prompt or fixture paths;
- no lexical or symlink traversal outside the resolved suite root;
- no network retrieval or URL references;
- no loader-time code, template, plugin, or shell execution;
- no trust in model-generated paths or model output as suite metadata;
- no filesystem search or fallback outside the selected suite root;
- no unbounded diagnostics or inclusion of private contents in diagnostics; and
- no execution of D5 generated code without its separately accepted containment
  and resource-limit gate.

Failure to preserve any boundary is an admission failure, not a reason to add a
fallback or weaken validation.

## Bounded implementation sequence

The architecture admits only this ordered sequence. Each item remains a
separate bounded milestone unless a later handoff explicitly admits it:

1. **Schema model and validation** — add the additive manifest fields, strict
   contract-owned objects, legacy mode, controlled enums, role/reference
   consistency, bounded diagnostics, and fail-closed validation without changing
   existing manifests.
2. **Profile selection and reference resolution** — normalize canonical and
   selected order, enforce Generic Core profile invariants, and resolve contained
   prompt and fixture paths with editable/package-source equivalence.
3. **Fixture and package-data support** — admit the concrete bounded fixture
   files and packaging rules without scoring or execution.
4. **Compatibility and security tests** — prove all five existing identities,
   aliases, order, mirrors, and legacy behavior remain unchanged, and cover
   duplicate keys, malformed metadata, unsupported versions, traversal,
   symlink escape, missing targets, diagnostic bounds, and package equivalence.
5. **Generic Core suite implementation** — add the versioned 13-prompt suite,
   exact Core/Smoke membership, final prompts, and declared references.
6. **Deterministic-check implementation** — implement D1-D7 and preserve check
   provenance without lexical semantic substitution or model execution in tests.
7. **Separate D5 containment gate** — accept and prove local isolation and
   resource limits before any generated candidate code executes; fail admission
   rather than substitute a heuristic.
8. **Result-provenance integration** — record selected profile, exact ordered
   membership, reference identities/versions, check outcomes, and manual-review
   state without changing historical evidence.

## Selected next milestone

Suite-content sequence item 5 is implemented: `generic-core-v1` `0.1.0` is a
loadable native suite with exact Core/Smoke membership, final prompts, and
declared references. The next admitted implementation milestone is
**deterministic-check implementation**, corresponding to sequence item 6. It
may implement D1-D7 and preserve check provenance without lexical semantic
substitution or model execution in tests. D5 generated-code execution still
requires the separate containment gate in item 7.
