# Historical Practical Suite v0.1.0 Contract

## Decision

The historical `wumbolabs-practical-use-v1` suite version `0.1.0` is a distinct,
accepted benchmark identity. A later implementation milestone will track it at
`suites/wumbolabs-practical-use-v1/` without modernizing its content.

This identity is separate from the tracked `wumbolabs-practical-v1` version
`0.2.0` seed suite. Similar purpose, ancestry, or prompt coverage does not make
the two suites interchangeable. Results must retain the suite ID and version
that were actually used.

## Source authority and byte roles

For `wumbolabs-practical-use-v1` version `0.1.0`, the private historical suite
source is authoritative for:

- suite ID and suite version;
- the six prompt IDs and their order in `suite.yaml`;
- every original prompt file's source bytes; and
- the private canonical rendered prompt bytes produced from those source files
  and the historical rendering inputs.

The authoritative prompt order is:

1. `linux/arch-nvidia-update-advice`
2. `coding/python-log-parser`
3. `docker/compose-review`
4. `honesty/unknown-package`
5. `summarization/technical-run-summary`
6. `local-llm/consumer-gpu-advice`

"Original source prompt bytes" means the bytes of each prompt file before UTF-8
decoding, outer-whitespace stripping, system-prompt composition, or export
redaction. "Private canonical rendered bytes" means the exact raw prompt
artifact bytes written by the historical LLMGauge rendering path: the resolved
historical system prompt and UTF-8 prompt text, each stripped as that path
specified, composed in its `SYSTEM:` / `USER:` form, and written without a
redaction pass. The system-prompt bytes and rendering behavior are therefore
material rendering inputs even though they are not part of the historical suite
directory.

The tracked prompt artifacts in both practical evidence packages are sanitized
public-export derivatives. They are authoritative for the bytes published in
their respective packages, not for private suite source or private canonical
rendering. A path-bearing private prompt can and normally will differ byte for
byte from its sanitized public derivative. Public-export redaction must never
redefine, modernize, or replace the historical benchmark source.

This contract does not change the canonical-private/source-derived roles in
[Artifact Schemas](ARTIFACT_SCHEMAS.md#public-single-run-export) or
[Public Reporting](PUBLIC_REPORTING.md#required-evidence).

## Verification invariants

The later implementation must establish two separate invariants. Passing one
does not imply the other.

### 1. Private canonical equivalence

The source tracked at `suites/wumbolabs-practical-use-v1/` must match an
authorized private historical reference for suite ID, version, ordered prompt
IDs, `suite.yaml` bytes, and each original prompt file's bytes. Rendering the
tracked source with the recorded historical system prompt and rendering behavior
must then produce exactly the private historical raw prompt bytes for every
prompt, in suite order.

This check is byte equality, not semantic similarity. Normalizing paths,
line endings, whitespace, wording, metadata, or formatting to make the check
pass is prohibited.

### 2. Public derivative equivalence

Applying the accepted public-export sanitization policy to each tracked private
canonical rendering, with the same recorded private-token redaction context,
must deterministically produce the exact prompt bytes already tracked in each
applicable public evidence package. This check compares the sanitized output to
the package's public `raw/<prompt-id>.prompt.md` artifact; it does not compare
that public artifact directly to private source or private rendered bytes.

The redaction context is part of the reproducibility input. A mismatch must fail
closed and be investigated; neither the historical source nor either evidence
package may be rewritten to force agreement.

## Authorized private reference

Canonical equivalence may be proved with an ignored, access-controlled reference
assembled from the original historical suite directory and canonical private run
artifacts underlying the existing evidence packages. The reference may contain:

- the original `suite.yaml` and prompt files, or full SHA-256 digests plus byte
  sizes and relative paths for those files;
- the ordered suite ID/version/prompt-ID inventory;
- the resolved historical system-prompt bytes and the renderer identity or exact
  rendering procedure;
- the private raw rendered prompt artifacts, or their full SHA-256 digests and
  byte sizes keyed by prompt ID; and
- the private hostname, username, home/path tokens, or equivalent explicit
  redaction mapping needed to reproduce the historical public sanitization.

A digest-only record proves equality only when the candidate bytes are hashed
with the stated full SHA-256 procedure; it is not a substitute for retaining the
private source and raw evidence for audit. The reference must record which
canonical private run or preserved historical source supplied each fact. It
must not be reconstructed from a public export.

Private machine paths, local identifiers, full private hashes, and the reference
itself remain ignored and untracked. Tracked documentation may record only
privacy-safe relative names, counts, procedures, and shortened display
digests. This preserves proof of byte equivalence without publishing unrelated
machine identity. The existing evidence packages remain sanitized derivatives
and continue to require human review before publication.

## Later implementation milestone

The later implementation must copy the historical source to
`suites/wumbolabs-practical-use-v1/` without content modernization. It must not
rename the suite, bump its version, reorder prompts, rewrite prompt text, or fold
it into `wumbolabs-practical-v1` version `0.2.0`.

Minimum focused verification:

1. validate the tracked suite structurally;
2. compare suite ID/version and ordered prompt IDs with the authorized private
   reference;
3. compare full SHA-256, byte size, and relative path for `suite.yaml` and every
   prompt source file;
4. render every prompt using the recorded historical system prompt and renderer,
   then compare full rendered bytes or their full SHA-256 and byte size with the
   private reference;
5. sanitize every tracked canonical rendering using the recorded redaction
   context and compare exact bytes with the corresponding tracked public prompt
   artifacts in both evidence packages;
6. confirm both evidence-package trees are byte-for-byte unchanged before and
   after verification; and
7. fail closed on any identity, order, source-byte, rendering, redaction, or
   source-mutation mismatch.

The implementation milestone may add focused deterministic verification, but it
must not run a model. It must preserve both existing evidence packages exactly.
This architecture milestone tracks no suite files and adds no implementation or
verification script.

## Boundaries

This contract does not change CLI behavior, suite/result schemas, rendering or
exporter behavior, dependencies, runtime configuration, either evidence package,
or release metadata. Structural and byte-equivalence checks establish benchmark
and derivative integrity only. They do not establish answer quality, scoring
correctness, privacy completeness, model provenance, or publication readiness.
