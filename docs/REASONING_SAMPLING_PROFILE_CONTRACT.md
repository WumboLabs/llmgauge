# Reasoning and Sampling Profile Identity Contract

Status: **accepted.** This contract supplements the reasoning-and-sampling-profiles
area of [Full Model Testing Capability Architecture](FULL_MODEL_TESTING_CAPABILITY_ARCHITECTURE.md)
and builds on the implemented comparison-readiness slice and the
`top_k`/`seed`/`min_p` requested-setting conventions.

## Problem

Requested reasoning/sampling settings are already captured per run as individual
scalar facts with paired request states where the runtime can leave a control to
its default. What does not exist is a **named, versioned identity** that answers:
"which declared profile resolved these controls, and what profile provenance
applies when comparing runs?" Manual setting comparison alone cannot distinguish
a deliberate controlled baseline from a vendor-aligned operator declaration.

## Non-negotiable boundaries

1. A profile is a named, versioned declaration of the existing reasoning and
   sampling controls. It introduces no parallel command builder, sampler
   semantics, automatic model/template behavior, download, discovery, or remote
   catalog.
2. Requested remains distinct from observed. A profile proves what LLMGauge
   resolved and requested; it never proves model reasoning, template behavior,
   vendor endorsement, or identical runtime-internal sampling.
3. Absence is valid. Historical results without profile evidence remain valid and
   keep their existing fingerprint versions and values.
4. Individual runtime-setting evidence remains authoritative and is never
   replaced by profile metadata.
5. Unknown, missing, or contradictory represented profile evidence fails closed
   in validation or comparison disclosure; it is never inferred.

## Profile definition and identity

A profile has exactly these material fields:

- `profile_id`: bounded `/`-free identifier matching
  `[A-Za-z0-9][A-Za-z0-9._-]{0,127}`.
- `profile_version`: bounded non-empty ASCII version token matching
  `[A-Za-z0-9][A-Za-z0-9._-]{0,127}`. LLMGauge uses equality only.
- `profile_kind`: closed vocabulary:
  - `controlled`: LLMGauge-defined controls intended to hold generation
    conditions constant.
  - `vendor_aligned`: an operator-declared configuration intended to match a
    cited/documented vendor or model-family recommendation. This is neither
    vendor endorsement nor proof that the model honored a semantic protocol.
- `settings`: the closed canonical declaration described below.
- `canonical_settings_sha256`: lowercase SHA-256 over canonical JSON bytes of
  `settings` only. It excludes `profile_id`, `profile_version`, `profile_kind`,
  display wording, and source location so equal controls have equal content
  identity across names and versions.

The supported setting keys are narrowly limited to currently implemented
reasoning/sampling controls: `temperature`, `top_p`, `top_k`, `min_p`, `seed`,
`reasoning_mode`, `reasoning_effort`, and `reasoning_budget`. They exclude
context, output length, batching, placement, cache, flash attention, fitting,
speculation, and all performance/runtime lifecycle controls.

Canonical `settings` is an object containing every supported key in lexicographic
JSON serialization order. Its values use the existing result semantics:

- `temperature` and `top_p` are finite numeric explicit values.
- `reasoning_mode` is one of the existing requested modes (`off`, `on`, `auto`,
  `default`, `unknown`). `default` means the runtime flag is intentionally
  omitted; `unknown` must not occur in a selected profile.
- each of `top_k`, `min_p`, `seed`, `reasoning_effort`, and `reasoning_budget` is
  either an explicit supported scalar or `null`, which deliberately requests the
  runtime default and is part of the content identity.

Canonical JSON is UTF-8, `sort_keys=True`, compact separators `(',', ':')`, and
`allow_nan=False`. A selected profile must have explicit `temperature` and
`top_p`; it must never silently depend on moving config or runtime defaults for
those controls. `null` is not unavailable or unknown: it records an intentional
runtime-default request. Runtime observation remains separately unavailable or
unknown unless supported evidence records it.

Changing any material setting requires a new `profile_version`; the same
`profile_id` plus version must never resolve to a different settings hash.
Documentation, display wording, aliases outside the selector, and
backward-compatible loader/schema additions do not change a profile version.

## Sources and resolution

The first implementation exposes two local sources only:

- an immutable built-in controlled profile set shipped with the package;
- an optional `sampling_profiles` mapping in the existing local config document
  for custom local definitions.

A custom config profile cannot shadow a built-in identifier. There is no profile
filesystem search path, inline definition, model-profile reference, or remote
source in this slice.

CLI selection is `--sampling-profile PROFILE_ID`. Resolution happens once before
runtime configuration using this precedence for eligible settings:

`explicit CLI > selected sampling profile > model profile > config defaults > existing command default`.

Explicit CLI options may override profile values. The result still records the
selected profile plus the final individual requested settings; the profile names
the declared baseline, not a claim that no override occurred. A selected profile
with an explicit override is therefore not a profile-content contradiction.
Unknown profile IDs, malformed definitions, unsupported keys, non-canonical
values, and duplicate identifiers fail before runtime launch. Config receives
parity because all comparable controls already participate in configuration.

## Result representation and validation

A selected profile adds this object under the existing `runtime` object:

```json
"profile": {
  "profile_id": "controlled-deterministic-v1",
  "profile_version": "1",
  "profile_kind": "controlled",
  "canonical_settings_sha256": "<64 lowercase hex>",
  "settings": { "...canonical full settings..." },
  "source": "builtin",
  "overrides": []
}
```

`source` is `builtin` or `config`; `overrides` is the sorted set of eligible
settings explicitly supplied by CLI after profile selection. The embedded
canonical settings make the artifact independently verifiable; they do not
replace individual runtime fields. Validators recompute the hash, validate the
closed shape and every setting, and reject a profile whose non-overridden
resolved setting disagrees with the corresponding persisted runtime request.
Legacy results with no `runtime.profile` remain valid and are not reinterpreted.

## Fingerprint and comparison

A represented profile uses additive run-fingerprint V5. Its canonical payload
includes the complete profile evidence object alongside the existing material
runtime settings. Thus profile identity is provenance-bearing: equal resolved
controls with different profile identities are not byte-identical V5 evidence.
Results without profile evidence retain their current V0-V4 behavior.

Comparison retains every existing per-setting compatibility check. It additionally
discloses profile provenance:

- identical profile identity, hash, and compatible settings: directly comparable
  under the disclosed profile;
- different profile identity/hash with equal resolved material controls:
  comparable with profile-provenance disclosure, not silently presented as the
  same declared baseline;
- differing material controls: mixed runtime settings, with existing limited
  claims;
- legacy/manual no-profile results: comparable according to existing material
  setting evidence, with no profile provenance inferred;
- malformed, missing partial, or inconsistent represented profile evidence:
  invalid or limited/unknown, never equivalent by inference.

`vendor_aligned` comparisons carry a standing disclosure that alignment is
operator-declared rather than verified. No profile assertion proves semantic
reasoning behavior.

## Reporting and export

Human-readable run and comparison reports disclose profile ID, version, kind,
content identity, and source when represented. They retain individual requested
settings and state that profile selection is requested/resolved provenance only.
Profile identity is safe to export; profile source files and unrelated config
content are not exported.

## First implementation boundary

The first slice ships the reusable schema/resolver/substrate and one neutral
built-in controlled profile, `controlled-deterministic-v1` version `1`. It
selects explicit deterministic sampling controls without making quality or
vendor claims. Vendor-aligned content, a broader catalog, model-profile
references, profile file discovery, and inline definitions remain separate
milestones.
