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

## Related documentation

- [Public reporting guidance](../PUBLIC_REPORTING.md)
- [Practical Eval v1](../PRACTICAL_EVAL_V1.md)
- [Artifact schemas](../ARTIFACT_SCHEMAS.md)
- [Roadmap](../ROADMAP.md)

Runtime and workflow evidence records that live outside this index remain under
`docs/` (for example Fit Ladder and vLLM smoke notes). Those records document
orchestration or integration boundaries; they are not scored practical model
packages unless listed above.
