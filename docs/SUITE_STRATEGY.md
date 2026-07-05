# Suite Strategy

LLMGauge prompt suites should separate generic framework tests from local/operator-specific smoke tests.

## Goals

- Keep the default core suite portable.
- Keep generated long-context tests separate from hand-written operational tests.
- Keep agent-backend tests focused on tool honesty, shell/config safety, and long-context constraint retention.
- Keep WumboLabs-specific/local smoke tests useful without making them the public default.

## Public suite philosophy

Bundled public suites should produce evidence that is practical, inspectable, and bounded.

Public suites should:

- use self-contained prompts
- avoid private machine names, private project memory, and hidden local context
- test practical usefulness rather than benchmark theater
- reward honesty under uncertainty
- reward conservative technical advice when system changes are involved
- preserve clear claim boundaries
- support manual review rather than pretending to be an automatic judge
- remain reproducible across machines and reviewers

Public suites should not:

- require private WumboLabs context
- depend on old internal roadmap notes
- imply universal model rankings
- imply daily-driver recommendations from a single smoke run
- encourage unsafe commands, hidden tool use, or fabricated currentness claims

Internal or local-flavor prompts may exist during development, but they should either be generalized before public release or kept outside the public repository.

## Suite roles

### core-v1

Generic practical local LLM evaluation.

Use for:

- honesty under uncertainty
- Linux/admin guidance
- Docker/networking troubleshooting
- ZFS/snapshot safety
- small coding tasks
- Docker Compose/config review
- basic long-context sanity
- niche factual honesty only if kept optional or clearly labeled

Design constraints:

- portable outside WumboLabs
- no private machine paths
- no real secrets
- no project-specific assumptions required to answer
- safe for public examples

### context-v1

Generated or generated-style context-retention tests.

Use for:

- synthetic needle prompts
- context placement tests
- context ladder workflows
- future tokenizer-verified prompt sizing
- future 96k-256k extreme-context prompts

Design constraints:

- generated artifacts should not be committed unless intentionally curated
- metadata should record target tokens, estimated tokens, placement, needle, and question
- model execution remains separate from generation

### agent-backend-v1

Agent-backend suitability tests.

Use for:

- tool honesty
- fake tool/package/command resistance
- shell safety
- config edit safety
- coding task usefulness
- long-context instruction retention
- synthetic agent preload prompts

Design constraints:

- should test agentic workload suitability without requiring a real agent framework
- should avoid tool schemas that imply real privileged access
- should make failure modes visible and scoreable

### wumbolabs-smoke-v1

Local smoke tests for project workflows.

Use for:

- Wumbo-flavored fake command checks
- niche factual-honesty check
- homelab-flavored Docker/ZFS/networking checks
- local model comparison workflows
- downstream integration smoke checks

Design constraints:

- optional, not the public default
- can contain local flavor, but not secrets
- useful for practical model rotation decisions
- should not be required for generic LLMGauge users

## Current state

`core-v1` should be interpreted as Tier 1 practical smoke evidence, not a definitive recommendation suite. See `docs/EVALUATION_TIERS.md` for the claim boundaries for each tier.

`core-v1` currently contains a mix of generic practical tests and a small amount of local flavor.

Known local-flavor prompts:

- fake `wumbo-gpu-daemon` unknown-tool honesty prompt
- niche factual-honesty prompt

These are acceptable during early development. Before a broader public polish pass, either:

- keep them clearly labeled as optional smoke tests, or
- move/duplicate them into `wumbolabs-smoke-v1`, or
- replace local-flavor names with generic fake names in `core-v1`.

## Near-term plan

- Keep `core-v1` stable unless a compatibility-breaking suite revision is intentional.
- Use `contextgen` for generated context prompts rather than committing many generated files.
- Maintain `agent-backend-v1` as a separate agent-oriented suite.
- Add `wumbolabs-smoke-v1` after the generic workflows are stable.
- Do not block LLMGauge engine work on prompt taxonomy cleanup.
