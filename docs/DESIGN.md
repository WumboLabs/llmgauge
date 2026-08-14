# LLMGauge Design Notes

LLMGauge is a standalone local LLM evaluation CLI/tool for practical testing on real hardware.

It grew out of earlier local evaluation workflows, but it must remain independently usable.

Core goals:

- practical local LLM evaluation
- llama.cpp / GGUF first, with optional external local vLLM
- raw prompt and raw output preservation
- reproducible run metadata
- Markdown reports for humans
- JSON results for machine import
- manual scoring first
- context-scaling support
- portable artifacts for optional downstream tooling later

Current non-goals / deliberate project boundaries:

- no web UI
- no model downloads
- no driver/CUDA/package/firewall mutation
- no automatic LLM-based scoring
- no SQLite dependency
- no external application database migration
- no migration of unrelated legacy internals

## Accepted architecture contracts and evidence

- [General evaluation taxonomy](GENERAL_EVALUATION_TAXONOMY.md) — accepted
  boundaries for native response, performance benchmark, external text
  benchmark, and agent-environment evaluation, including authority, scoring,
  comparison, and integration sequencing.

- [Full Model Testing Capability Architecture](FULL_MODEL_TESTING_CAPABILITY_ARCHITECTURE.md)
  — accepted capability classification, evidence and trust boundaries,
  prerequisite contracts, blocking scope, the eight-step Full Model Testing
  capability sequence, the parallel LocalMaxxing performance-benchmark lane,
  and release gates without merging their evaluation classes.

- [Multi-turn Transcript Architecture](MULTI_TURN_TRANSCRIPT_ARCHITECTURE.md)
  — accepted native multi-turn conversation identity, ordered-turn, observable
  state, feedback provenance, completion/recovery, scoring, source authority,
  privacy, compatibility, Agent Harness, comparison, validation, and milestone
  boundaries before schema or implementation.

- [Multi-turn Transcript Schema and Native Evaluation Contract](MULTI_TURN_TRANSCRIPT_SCHEMA_CONTRACT.md)
  — accepted single-authority contained transcript representation, closed event
  model, bounded supplied-feedback protocol, validation, additive result and
  fingerprint integration, reporting, and compatibility boundary.

- [Agent Harness Import Contract](AGENT_HARNESS_IMPORT_CONTRACT.md) — accepted
  `llmgauge.agent_harness_evidence.v0` external agent-environment identity and
  implemented bounded OMP-v3 importer: self-contained read-only source
  authority, repository/tool lifecycle and availability, native-transcript
  separation, privacy, compatibility, atomic import, additive
  result/fingerprint integration, structural validation, and fail-closed native
  consumer boundaries.
- [Agent-session Scoring and Reporting Contract](AGENT_SESSION_SCORING_REPORTING_CONTRACT.md)
  — accepted order-3c contract for Agent Harness-specific derivative scoring
  authority, source-verifier separation, evidence completeness, human review,
  attribution, recovery, reporting, comparison eligibility, publication, and
  fingerprint boundaries before any implementation.


- [Coding Suite Architecture and Scoring Contract](CODING_SUITE_ARCHITECTURE_SCORING_CONTRACT.md)
  — accepted `coding-core-v1` native single-turn identity, capability and
  task-family boundaries, evidence/scoring authority, comparison eligibility,
  suite coexistence, and separation from multi-turn, Agent Harness, and
  generated-code execution work.

- [Coding Suite Prompt and Task-Family Design](CODING_SUITE_PROMPT_TASK_FAMILY_DESIGN.md)
  — proposed `coding-core-v1` `0.1.0` static prompt-role inventory, exact
  capability ownership, response forms, ordered Smoke/Core membership, scoring
  roles, and explicit multi-turn repair exclusion.

- [Coding Suite Scoring-Method Design](CODING_SUITE_SCORING_METHOD_DESIGN.md)
  — accepted versioned manual rubric, three closed non-executing checks,
  side-by-side hybrid composition, scoreability, and bounded aggregation/claim
  rules for the fixed eight static coding roles.

- [Coding Suite Schema and Loader Contract](CODING_SUITE_SCHEMA_LOADER_CONTRACT.md)
  — accepted additive manifest metadata, exact profile and scoring-reference
  mappings, normalized identity, contained resource, source/package/installed,
  compatibility, and fail-closed loader boundaries for `coding-core-v1`.

- [Generic Core suite contract](GENERIC_CORE_SUITE_CONTRACT.md) — accepted
  `generic-core-v1` identity, profile, capability, scoring, comparison, and
  historical-suite coexistence boundaries before prompt design or implementation.

- [Generic Core prompt and scoring design](GENERIC_CORE_PROMPT_SCORING_DESIGN.md)
  — proposed `generic-core-v1` `0.1.0` prompt-role inventory, ordered Smoke/Core
  membership, task and fixture ownership, deterministic-check feasibility, and
  manual/hybrid scoring provenance before schema or suite implementation.

- [Generic Core schema and loader contract](GENERIC_CORE_SCHEMA_LOADER_CONTRACT.md)
  — accepted additive manifest, ordered-profile, scoring-reference, contained
  path-resolution, normalization, compatibility, and fail-closed loading
  boundaries before schema implementation.

- [Historical Practical Suite v0.1.0 contract](PRACTICAL_SUITE_V1_CONTRACT.md) —
  private source and rendering remain authoritative; tracked public prompt
  artifacts are deterministic sanitized derivatives, not replacement source.

- [Initial vLLM runtime integration contract](VLLM_RUNTIME_CONTRACT.md) —
  externally managed, loopback-only, text-only OpenAI-compatible server
  integration.
- [vLLM HTTP transport assessment](VLLM_HTTP_TRANSPORT_ASSESSMENT.md) —
  standard-library HTTP transport for the initial client; no third-party HTTP
  dependency.
- The implemented external adapter is an optional `backend=vllm` path using
  `http.client` against an operator-managed loopback server. It does not install,
  start, or supervise vLLM; llama.cpp remains the default backend. Requests are
  sequential and non-streaming, and runtime-native token/throughput fields are
  not equivalent across runtimes.
- [vLLM live integration smoke evidence](VLLM_LIVE_SMOKE_EVIDENCE.md) —
  completed real-runtime smoke for one fitting model and one prompt; historical
  pre-fingerprint evidence remains authoritative for that point in time.
- [vLLM fingerprint live smoke evidence](VLLM_FINGERPRINT_LIVE_SMOKE_EVIDENCE.md) —
  live `/version`, API-ready `server_state`, and opaque fingerprint capture
  against one operator-managed loopback server.
- [Cross-runtime comparison methodology](VLLM_CROSS_RUNTIME_COMPARISON_METHODOLOGY.md) —
  minimum rules for a bounded llama.cpp-versus-vLLM comparison, including
  template/input disclosure and non-equivalent runtime-native metrics.
- [Cross-runtime comparison evidence](VLLM_CROSS_RUNTIME_COMPARISON_EVIDENCE.md) —
  completed first prompt-specific comparison; F16 GGUF and BF16 Transformers
  weights are not proven bit-identical.
- [Cross-runtime second-prompt replication evidence](VLLM_CROSS_RUNTIME_SECOND_PROMPT_EVIDENCE.md) —
  completed second prompt-specific observation; directional replication only,
  not a combined runtime ranking.
- [Gemma 4 12B NVFP4 CPU-offload evidence](GEMMA4_12B_NVFP4_CPU_OFFLOAD_EVIDENCE.md) —
  completed one-checkpoint, one-host admission audit; `not_viable` only for the
  disclosed configuration after a construction-time BF16 LM-head CUDA OOM.
- [Fit Ladder real-workflow evidence](FIT_LADDER_REAL_WORKFLOW_EVIDENCE.md) —
  completed operator validation of total-failure and success-after-fallback
  terminal paths; orchestration and artifact evidence only, not model quality.
