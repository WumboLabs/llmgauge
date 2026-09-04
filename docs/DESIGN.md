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

- [External Benchmark and LocalMaxxing Interoperability Contract](EXTERNAL_BENCHMARK_LOCALMAXXING_INTEROP_CONTRACT.md)
  — accepted external-text-benchmark evidence model, official-harness
  authority, imported-source containment, native-metric preservation,
  Bundle 1/2 LocalMaxxing compatibility as of 2026-08-16, and the
  conceptual `llmgauge benchmark` CLI. It adds no importer, schema code,
  or LocalMaxxing quality-submit behavior.
- [Bundle 1 qualification](BUNDLE1_QUALIFICATION.md) — pinned official
  EleutherAI `lm-evaluation-harness` `v0.4.12` identities, fail-closed
  qualification statuses, and the read-only `benchmark report` boundary.

- [Full Model Testing Capability Architecture](FULL_MODEL_TESTING_CAPABILITY_ARCHITECTURE.md)
  — accepted capability classification, evidence and trust boundaries,
  prerequisite contracts, blocking scope, the eight-step Full Model Testing
  capability sequence, the parallel LocalMaxxing performance-benchmark lane,
  and release gates without merging their evaluation classes.

- [Runtime-neutral Metrics and Expanded Failure Taxonomy Contract](RUNTIME_NEUTRAL_METRICS_FAILURE_TAXONOMY_CONTRACT.md)
  — accepted Area 4 additive evidence contract for versioned neutral metric
  records and derived closed failure classifications. It preserves native
  runtime evidence, legacy result validity, source authority, and explicit
  non-equivalence boundaries; it admits no collector, transport, or execution
  behavior.

- [Multi-turn Transcript Architecture](MULTI_TURN_TRANSCRIPT_ARCHITECTURE.md)
  — accepted native multi-turn conversation identity, ordered-turn, observable
  state, feedback provenance, completion/recovery, scoring, source authority,
  privacy, compatibility, Agent Harness, comparison, validation, and milestone
  boundaries before schema or implementation.

- [Multi-turn Transcript Schema and Native Evaluation Contract](MULTI_TURN_TRANSCRIPT_SCHEMA_CONTRACT.md)
  — accepted single-authority contained transcript representation, closed event
  model, bounded supplied-feedback protocol, validation, additive result and
  fingerprint integration, reporting, and compatibility boundary.

- [Transcript Comparison and Review Contract](TRANSCRIPT_COMPARISON_REVIEW_CONTRACT.md)
  — accepted bounded structural transcript comparison: exact identity
  eligibility, three-way structural classification, role and ordering
  preservation, recorded review-hook presentation, no aggregate, no ranking,
  and a fail-closed single-run public-export boundary.

- [Transcript Comparison Public Export Contract](TRANSCRIPT_COMPARISON_PUBLIC_EXPORT_CONTRACT.md)
  — accepted content-default-deny comparison-only public derivative
  (`llmgauge.public_transcript_comparison.v0`): closed allowlist projection of
  structural facts, sequence-number-only linkage, sanitized model labels,
  closed-world validation, fail-closed admission, no content, no private
  identifiers or full hashes, no aggregate or winner, and mandatory human
  review before publication.

- [Native Single-Transcript Public Derivative Contract](NATIVE_TRANSCRIPT_PUBLIC_DERIVATIVE_CONTRACT.md)
  — accepted content-default-deny single-run public derivative
  (`llmgauge.public_transcript.v0`): one transcript-bearing native result
  projected through the comparison derivative's shared per-run allowlist,
  sanitizer, closed-world validator, and staged write, plus closed protocol
  identity and numeric producer version; no content, private identifiers, or
  full hashes; no score or aggregate; mandatory human review before
  publication; single-run `export-public` stays fail-closed.

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
- [Agent-session Review Interface Contract](AGENT_SESSION_REVIEW_INTERFACE_CONTRACT.md)
  — accepted concrete `agent-session-review-v0` review-artifact, contained
  source-reference, derivative-validation, CLI, and Agent-Harness-report
  interface for the separately human-gated 3c implementation milestone.



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
  — accepted `generic-core-v1` `0.1.0` prompt-role inventory, ordered Smoke/Core
  membership, task and fixture ownership, deterministic-check feasibility, and
  manual/hybrid scoring provenance. Suite content now implements that inventory;
  D1-D7 scoring remains later work.

- [Generic Core schema and loader contract](GENERIC_CORE_SCHEMA_LOADER_CONTRACT.md)
  — accepted additive manifest, ordered-profile, scoring-reference, contained
  path-resolution, normalization, compatibility, and fail-closed loading
  boundaries before schema implementation.

- [Initial vLLM runtime integration contract](VLLM_RUNTIME_CONTRACT.md) —
  externally managed, loopback-only, text-only OpenAI-compatible server
  integration.
- [EXL2/EXL3 representation and ExLlama runtime qualification](EXL_RUNTIME_QUALIFICATION.md)
  — accepted M2.5 contract: EXL2/EXL3 are `checkpoint_directory` models with a
  separate `model_format` identity, fail-closed detection, the frozen-manifest
  v1 extension decision, ExLlamaV3 as a principal first-class runtime family,
  the EXL2/ExLlamaV2 compatibility lane, and TabbyAPI's server-role lifecycle
  disposition. Qualification only; no runtime is implemented.
- [vLLM HTTP transport assessment](VLLM_HTTP_TRANSPORT_ASSESSMENT.md) —
  standard-library HTTP transport for the initial client; no third-party HTTP
  dependency.
- The implemented external adapter is an optional `backend=vllm` path using
  `http.client` against an operator-managed loopback server. It does not install,
  start, or supervise vLLM; llama.cpp remains the default backend. Requests are
  sequential and non-streaming, and runtime-native token/throughput fields are
  not equivalent across runtimes.
- The adapter's real-runtime behavior was validated by bounded operator-local
  smoke runs; those run records were evaluation artifacts and are not tracked
  in this repository. Claim boundaries live in
  [VLLM_RUNTIME_CONTRACT.md](VLLM_RUNTIME_CONTRACT.md).
- [Cross-runtime comparison methodology](VLLM_CROSS_RUNTIME_COMPARISON_METHODOLOGY.md) —
  minimum rules for a bounded llama.cpp-versus-vLLM comparison, including
  template/input disclosure and non-equivalent runtime-native metrics.
- [Reasoning and sampling profile identity contract](REASONING_SAMPLING_PROFILE_CONTRACT.md)
  — accepted named/versioned profile substrate.
- [Vendor-aligned sampling profiles](VENDOR_ALIGNED_SAMPLING_PROFILES.md)
  — first qualified `vendor_aligned` builtins, source matrix, and
  requalification policy. Alignment is documented-request provenance only.

- Fit Ladder terminal-path behavior (total failure after all planned contexts;
  success after fallback) is stated sanitized in [FIT_LADDER.md](FIT_LADDER.md);
  the operator run records behind it were evaluation artifacts and are not
  tracked in this repository.
