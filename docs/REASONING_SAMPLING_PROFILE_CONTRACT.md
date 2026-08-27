# Reasoning and Sampling Profile Identity Contract

Status: **accepted-candidate — requires human architecture acceptance before
any implementation.** It supplements the reasoning-and-sampling-profiles area
of [Full Model Testing Capability Architecture](FULL_MODEL_TESTING_CAPABILITY_ARCHITECTURE.md)
and builds on the implemented comparison-readiness slice and the
`top_k`/`seed`/`min_p` requested-setting conventions. Until accepted, no
profile identity, version, or kind may be persisted by LLMGauge.

## Problem

Requested reasoning/sampling settings are already captured per run as
individual scalar facts with paired request states. What does not exist is a
**named, versioned identity** that answers: "which profile produced this
evidence, and can two runs be compared under their profiles?" Today that
question can only be answered by manually diffing every scalar, and
vendor-intended versus held-constant configurations are indistinguishable in
artifacts.

## Non-negotiable boundaries

1. A profile is a **named, versioned bundle of the existing scalar requested
   settings** — it introduces no parallel configuration mechanism, no new
   sampler semantics, and no automatic model/template behavior claim.
2. Requested remains distinct from observed. A profile records what the
   operator asked for; it never proves the model or chat template honored a
   reasoning mode or that the runtime applied a sampler identically.
3. Absence is valid. Every historical result without profile identity
   remains valid, unchanged, and fingerprint-identical.
4. Comparisons never treat differing profiles as like-for-like, and unknown
   profile facts fail closed to disclosure rather than inference.
5. Profile definitions are local operator configuration, never downloaded,
   synced, or published as product content.

## Identity and versioning

- `profile_id`: bounded identifier, same grammar as `runtime_label` plus
  `/`-free constraint (recommended `[A-Za-z0-9][A-Za-z0-9._-]{0,127}`).
- `profile_version`: operator-maintained version string; changing any
  setting inside a profile requires a new version. Versions are not ordered
  by LLMGauge; equality is the only relation used.
- `profile_kind`: closed vocabulary — `vendor_aligned` (a disclosed
  vendor/model-card-intended configuration, recorded as claimed by the
  operator, never verified) or `controlled` (LLMGauge-held settings kept
  constant for like-for-like evidence). Neither kind is more correct;
  both are disclosure, not quality claims.
- `canonical_settings_sha256`: SHA-256 over the canonical JSON of the
  profile's resolved requested settings (the same field set and request
  states already captured). Two profiles with equal content hash are
  setting-equivalent even under different names; the hash does not make
  names aliases, and the name does not override content.

## Representation

One optional object under the result's existing `runtime` metadata:

```json
"runtime": {
  "profile": {
    "profile_id": "qwen-daily-v2",
    "profile_version": "2.1.0",
    "profile_kind": "controlled",
    "canonical_settings_sha256": "…",
    "settings_ref": "runtime"
  }
}
```

`settings_ref` is the fixed pointer `runtime`: the profile's meaning is the
already-persisted requested settings in the same result. The object
duplicates no setting values. Every represented scalar must still be present
with its paired state exactly as without a profile; selecting a profile is
only a resolution source with the existing precedence (CLI > profile >
config defaults), and explicit CLI overrides of profile values are recorded
normally. A result whose scalars disagree with its referenced profile
definition is the operator's resolution outcome, not an error: the artifact
records what was requested, and the profile identity names the baseline.

## Selection surface (recommended, pending human naming confirmation)

- CLI: `--sampling-profile NAME` (avoids collision with the existing
  `--model-profile`, which selects model paths).
- Config: a new optional `sampling_profiles:` mapping in the existing
  local config document, each entry holding the same optional scalar keys
  as `defaults:` plus `profile_version` and `profile_kind`.
- Model profiles may reference a sampling profile by name but never inline
  one; there is exactly one authority per profile definition.

## Fingerprint participation

Results that represent a profile use a new run-fingerprint payload version
(V5) extending the current boundary with the profile identity block
(`profile_id`, `profile_version`, `profile_kind`,
`canonical_settings_sha256`). The block is content-derived from
already-fingerprinted scalars plus identity, so two setting-equivalent
profiles under different names produce different V5 fingerprints (names are
identity) while all non-profile results keep their existing payload
versions byte-for-byte.

## Comparison eligibility

`compare` treats profile identity as runtime evidence: differing
`profile_id`/`profile_version`/`profile_kind` or content hash marks the runs
mixed on runtime settings (existing mechanism). Additionally:

- differing profile kinds produce the advisory that vendor-aligned and
  controlled profiles are not interchangeable evidence baselines;
- `vendor_aligned` profiles carry a standing advisory that vendor intent is
  operator-claimed, not verified;
- unknown or absent profile identity keeps current behavior (no inference).

## Public export

Profile identity (id/version/kind/content hash) is public-safe disclosure.
Profile definitions themselves are operator-local configuration and are not
exported.

## Implementation prerequisites

(a) human acceptance of this contract including the `--sampling-profile`
naming; (b) one bounded implementation milestone covering config schema,
resolution precedence, result field, V5 fingerprint, validation, report and
comparison disclosure, docs, and synthetic tests; (c) no runtime execution
or model run is required to validate any of it.
