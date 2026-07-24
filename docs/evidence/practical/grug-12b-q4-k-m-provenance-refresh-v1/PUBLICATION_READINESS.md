# Publication Readiness

Classification: `review_ready_with_caveats`

Decision: suitable for human publication review as one bounded practical
evidence package. It is not approved for automatic or unreviewed publication.

## Source selection

The selected source is the new private provenance-refresh result:

`results/grug_12b_q4_k_m-provenance-refresh-v1-wumbolabs-practical-use-v1-8k`

It was created from the tracked historical suite and is distinct from the legacy
Grug result and package. The legacy package was not overwritten, rescored, or
selected as this source.

This directory was scored in place before any complete immutable copy was
retained. A 36-file pre-scoring hash inventory exists, but the original
pre-scoring bytes do not. The selected export source is therefore the resulting
37-file **scored private working source**, not a preserved byte-identical
original live-run tree. The accepted LLMGauge public-proof workflow permits
in-place score application before export; this package proceeds only with that
integrity limitation disclosed.


Selection facts:

- one completed six-prompt run, exit 0, no interruption, zero retries;
- stable suite path, identity, version, and accepted prompt order;
- model, executable/backend, observed runtime, and run provenance present;
- explicit context, generation, sampling, batch, GPU-layer, flash-attention,
  reasoning, and runtime-label settings;
- resolved `runtime-command.json`;
- private privacy-safe hardware/timing sidecars and public GPU/VRAM telemetry;
- all scores manual, reviewed, and applied with no `needs_review` state.

## Readiness checks

| Check | Result |
|---|---|
| Live-run completion evidence | PASS: 6 completed, 0 failed, 0 retries |
| Operator capture | PASS: start/end present, exit 0, not interrupted |
| Private structural validation | PASS before and after scoring |
| Prompt evidence | PASS: 6 raw prompts/outputs, 6 cleaned outputs, 6 stderr logs, 6 VRAM files |
| Runtime and provenance | PASS: model, executable/backend, observed identity, run fingerprint, resolved command |
| Requested settings | PASS: 8192 / 1200 / 0.2 / 0.95 / 256 / 64 / 999; flash `auto`; reasoning `off`; `stock-reference` |
| Score consistency | PASS across `scores.yaml`, `llmgauge-result.json`, and `report.md` |
| Review state | PASS: 6 manual, 6 reviewed, 0 unreviewed, 0 `needs_review` |
| Verdict disclosure | PASS: 2 pass, 3 mixed, 1 fail; all labels and rationales retained |
| Original live-run byte preservation | FAIL: inventory retained, exact pre-scoring tree not preserved |
| Scored-source export immutability | PASS: pre/post 37-file scored-source inventories identical |
| Transactional public export | PASS: generated into a new package path |
| Public structural validation | PASS |
| Export-index validation | PASS: one valid indexed result |
| Export completeness | PASS: scores, provenance, runtime command, outputs, logs, and VRAM retained |
| Privacy scan | PASS with classified expected source-run fingerprint and task-context redactions |
| Legacy/Qwen preservation | PASS: no tracked changes under either existing package |

Structural PASS and scored-source export immutability do not establish original
live-run byte preservation, answer quality, safety, privacy completeness, or
publication readiness.

## Privacy and sanitization review

The review scanned every public-export file and `export-index.json` for:

- local username and hostname;
- home, model, and executable paths;
- full local model/executable hashes;
- CPU/kernel/OS private capture values;
- credentials, assignments, credential-bearing URLs, and unrelated environment
  data;
- duplicated private command paths and metadata.

No private identifier, path, credential, full model hash, or full executable
hash remained. The source run fingerprint remains in the manifest and generated
report by export contract, with an explicit non-authentication boundary. The
operating-system phrase also occurs in the benchmark subject matter; that
context is task evidence, not leaked host identity.

The manifest reports 17 copied files, 17 transformed files, and 3 omitted unknown
private sidecars: `operator-capture.json`, `operator-console.log`, and
`private-preflight-provenance.json`. Omission is intentional. Public runtime
command fields retain settings while replacing executable and model paths with
redaction tokens.

Path redaction is visible in Docker prompt/output material and llama-cli banner
commands. This protects local data but reduces specificity. Sanitization remains
a bounded control, not proof that all private information is removed.

## Scoring and claim review

No review-state blocker remains. Material caveats must remain prominent:

- Arch/NVIDIA: unsupported source and recovery assumptions; incomplete
  verification.
- Docker Compose: invented tag/endpoint details, incorrect healthcheck behavior,
  and unsupported configuration changes.
- Unknown package: sound uncertainty boundary weakened by unsupported fallback
  claims.
- Consumer GPU: failed because it made explicitly prohibited fit, VRAM, speed,
  and quality claims.

The 3.71 manual average and per-prompt verdicts are one reviewer's metadata for
this generated response set. They must not be converted into a ranking,
regression claim, winner, recommendation, safety conclusion, or fit guarantee.

## Provenance and hardware boundaries

- Observed runtime: version 9672, commit `74ade5274`, GNU 16.1.1, Linux x86_64.
- Public model and executable fingerprints are shortened display identifiers;
  full local hashes remain private.
- The source run fingerprint identifies canonical evidence but does not
  authenticate transformed bytes or prove a unique execution.
- Private capture depth includes privacy-safe OS/kernel/CPU/RAM/GPU/driver facts,
  start/end timestamps, and console evidence. Those sidecars are not public.
- Public GPU and VRAM values are observed telemetry, not authenticated hardware
  identity.

## Required human actions before publication

1. Read `PUBLIC_EVIDENCE_SUMMARY.md` against all six cleaned outputs and the raw
   outputs for the three mixed and one failed prompt.
2. Confirm surrounding copy retains the fail verdict and all material caveats.
3. Confirm no copy treats this package as replacing the legacy Grug source or as
   proof of regression.
4. Confirm no ranking, winner, purchasing, daily-driver, safety, or generalized
   fit claim is added.
5. Publish only files marked publication-intended by `PACKAGE_MANIFEST.md`.
6. Keep the private source, operator sidecars, and private inventories nonpublic.

No external publication, network submission, model rerun, retry, legacy/Qwen
rescore, comparison rewrite, release, stage, commit, merge, or push occurred.
