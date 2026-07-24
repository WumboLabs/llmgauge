# Public evidence index

Tracked, human-reviewed evidence packages for LLMGauge. Each package is a
**bounded** record under disclosed conditions. Packages are not leaderboards,
universal rankings, purchasing guides, or daily-driver recommendations.

Structural validation checks artifact shape and references. It does not prove
model quality, safety, or publication readiness. Manual scores are reviewer
metadata, not objective truth.

## Practical suite evidence

| Package | Model / quant | Runtime | Scope | Classification |
|---|---|---|---|---|
| [grug-12b-q4-k-m](practical/grug-12b-q4-k-m/) | Grug-12B Q4_K_M | llama.cpp | One six-prompt practical run | `review_ready_with_caveats` |
| [qwen3-6-35b-a3b-ud-iq2-m](practical/qwen3-6-35b-a3b-ud-iq2-m/) | Qwen3.6-35B-A3B UD-IQ2_M | llama.cpp | One six-prompt practical run (provenance-complete source) | `review_ready_with_caveats` |

## Bounded comparisons

| Comparison | Scope | Claim boundary |
|---|---|---|
| [Grug-12B Q4_K_M versus Qwen3.6-35B-A3B UD-IQ2_M practical v1](comparisons/grug-vs-qwen3-6-practical-v1/) | Six shared, manually reviewed practical prompts | Methodology-disclosed prompt and operational observations; no winner, ranking, or recommendation |

## Related documentation

- [Public reporting guidance](../PUBLIC_REPORTING.md)
- [Practical Eval v1](../PRACTICAL_EVAL_V1.md)
- [Artifact schemas](../ARTIFACT_SCHEMAS.md)
- [Roadmap](../ROADMAP.md)

Runtime and workflow evidence records that live outside this index remain under
`docs/` (for example Fit Ladder and vLLM smoke notes). Those records document
orchestration or integration boundaries; they are not scored practical model
packages unless listed above.
