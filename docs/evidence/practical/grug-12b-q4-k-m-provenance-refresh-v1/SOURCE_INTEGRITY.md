# Source Integrity

## Scored canonical source

Private canonical directory:

`results/grug_12b_q4_k_m-provenance-refresh-v1-wumbolabs-practical-use-v1-8k`

The source was validated, manually scored through the existing LLMGauge
workflow, validated again, and then inventoried. It was not edited after that
scored-source inventory during public export or package assembly. Tracked
public artifacts live only under
`docs/evidence/practical/grug-12b-q4-k-m-provenance-refresh-v1/`.

## Original live-run preservation limit

An ignored pre-scoring inventory captured the original 36-file live-run tree's
paths, sizes, and hashes. No complete pre-scoring directory, copy, backup, or
archive was found. In-place scoring then changed `llmgauge-result.json` and
`report.md` and added `scores.yaml`. The exact pre-scoring byte tree therefore
is **not preserved** and cannot be verified as an immutable original or
recovered from the inventory alone.

The accepted public-proof workflow applies reviewed scores to the result
directory before export, and the artifact contract treats the applied
`llmgauge-result.json` as the score/run metadata source of truth. Accordingly,
the current 37-file result is the **scored canonical private working source** for
this package. Every immutability statement below applies only to that scored
source during export and package assembly, not to the original unscored
live-run bytes.


## Deterministic inventory method

For each regular file below the canonical directory, the private review record
stores the source-relative POSIX path, byte size, and full SHA-256 digest. Entries
are sorted by path. A deterministic tree digest is computed from the canonical
JSON representation of those records.

The method covers file content, size, and relative path. It excludes timestamps,
ownership, permissions, and empty directory entries. Full per-file hashes and
full tree digests remain only in ignored private review records.

## Scored-source comparison result

| Property | Scored source before export | Scored source after export | Result |
|---|---:|---:|---|
| File count | 37 | 37 | identical |
| Total bytes | 113,074 | 113,074 | identical |
| Tree digest prefix | `708d9ae15aca0742` | `708d9ae15aca0742` | identical |
| Per-file path/size/digest records | recorded | recorded | identical |

Conclusion: the complete scored private working tree matched exactly
immediately before and after export. This proves only export/package-stage
non-mutation; it does not prove original live-run byte preservation.

## Derivative relationship

`export-public` selected known result artifacts, sanitized text and structured
fields, validated its staged output, and wrote a new derivative directory. Its
manifest records:

- 17 copied files;
- 17 transformed files;
- 3 omitted unknown private sidecars;
- redactions for absolute paths, home-directory paths, local username, full
  local SHA-256 values, and duplicated prompt content.

The omitted files are private operator capture, operator console, and private
preflight provenance. Their omission does not remove referenced result evidence;
they are supplemental private preparation/capture records outside the public
artifact schema.

The derivative is not byte-identical to the source. Sanitization redacts private
paths and full local hashes and changes path-like text in benchmark prompts,
Docker output, and llama-cli banners. The scored private working source remains
authoritative for applied-score and public-export audit.

## Fingerprint roles

| Carrier | Role |
|---|---|
| Private result run fingerprint | Identifies the canonical private evidence |
| Export-manifest source run fingerprint | Public source identifier with an explicit transformed-byte non-authentication boundary |
| Public model/executable fingerprints | Short display identifiers for the tested local files |
| Public result/index run-fingerprint field | May be absent after sanitization; not proof the private source lacked one |

Fingerprints do not prove model authorship, upstream provenance, hardware
identity, answer quality, safety, or transformed export bytes. The private
inventory comparison demonstrates local non-mutation only.

## Validation boundary

The result passed `validate-result` before scoring and after the six manual
scores were applied. The derivative passed `validate-result` and appears as
valid in the regenerated export index. Accepted scoring contracts permit this
in-place score application, but no exact unscored source copy remains. These
checks establish artifact structure and references, not original-byte
preservation, answer quality, scoring correctness, privacy completeness, or
publication claims. Human review remains mandatory.
