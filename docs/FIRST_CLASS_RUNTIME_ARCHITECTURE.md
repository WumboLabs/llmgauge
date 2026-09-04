# First-Class Multi-Runtime Architecture and Native Model Support Contract

- Status: Accepted
- Accepted: 2026-09-03
- Scope: Architecture and product-contract definition only. This document
  implements no runtime behavior, changes no schema, and admits no dependency.
- Decision type: Architecture contract and implementation program
- Baseline: `main` @ `cfe7b7af4fc82fb8319956d2bc5f9513b059a116` (v0.78.0;
  1460 passed, 2 skipped)
- Related:
  - [VLLM_RUNTIME_CONTRACT.md](VLLM_RUNTIME_CONTRACT.md)
  - [VLLM_HTTP_TRANSPORT_ASSESSMENT.md](VLLM_HTTP_TRANSPORT_ASSESSMENT.md)
  - [VLLM_CROSS_RUNTIME_COMPARISON_METHODOLOGY.md](VLLM_CROSS_RUNTIME_COMPARISON_METHODOLOGY.md)
  - [VLLM_STREAMING_TTFT_ARCHITECTURE.md](VLLM_STREAMING_TTFT_ARCHITECTURE.md)
  - [VLLM_AREA4_EVIDENCE_MAPPING.md](VLLM_AREA4_EVIDENCE_MAPPING.md)
  - [RUNTIME_NEUTRAL_METRICS_FAILURE_TAXONOMY_CONTRACT.md](RUNTIME_NEUTRAL_METRICS_FAILURE_TAXONOMY_CONTRACT.md)
  - [ARTIFACT_SCHEMAS.md](ARTIFACT_SCHEMAS.md)
  - [PUBLIC_REPORTING.md](PUBLIC_REPORTING.md)
  - [ROADMAP.md](ROADMAP.md)

## 1. Motivation

LLMGauge's product question is "is this model useful, honest, fast, and
VRAM-viable on real consumer hardware?" Historically that question has been
encoded as "can this GGUF run through `llama-cli`?" The execution architecture
is now broader than that framing, but the product model still carries
single-file, subprocess-shaped assumptions in planning, provenance,
fingerprints, validation, reporting, comparison, and export.

Modern inference runtimes admit models natively as Hugging Face /
Transformers-style checkpoint directories (safetensors shards, tokenizer and
chat-template assets, quantization metadata such as BF16, FP16, FP8, AWQ, GPTQ,
and compressed-tensors). Evaluating those checkpoints only after conversion to
GGUF measures a different artifact, a different quantization, and often a
different numerical implementation than the one practitioners actually run
under vLLM or SGLang.

The accepted long-term direction is first-class multi-runtime evaluation:

```text
llama.cpp / GGUF                          -> first-class runtime + representation
vLLM  / native HF-Transformers checkpoint -> first-class runtime + representation
SGLang / native HF-Transformers checkpoint -> first-class runtime + representation
```

First-class does **not** mean "send an OpenAI-compatible request to another
server." It means each runtime family reaches the same product quality of
identity, provenance, evidence, validation, reporting, workflow integration,
and defensible claim boundaries — while remaining honestly different where
their lifecycles, metrics, and telemetry are not equivalent.

Support is capability-qualified, never assumed: a runtime or quantization is
supported only where LLMGauge can observe and disclose it. Universal support
for every checkpoint format or quantization scheme is explicitly not promised.

## 2. Current state

### 2.1 Execution flow (as implemented)

```text
Typer CLI (src/llmgauge/cli.py)
  -> run / run-batch / run-ladder / fit-ladder
  -> commands/run_helpers.resolve_run_options
       (config + model profile + sampling profile -> backend-specific dict)
  -> commands/run_helpers.execute_run
       -> backend == "llama.cpp": LlamaCppRunConfig -> run_llama_cpp
            -> bounded llama-cli subprocess per prompt
       -> backend == "vllm": VllmExternalConfig -> readiness check
            -> OpenAI-compatible loopback HTTP (vllm_http.py), opt-in SSE
  -> raw/cleaned/logs + runtime evidence artifacts
  -> llmgauge-result.json -> run fingerprint -> report.md
  -> validate-result / score / compare / export-index / export-public
```

### 2.2 Implemented runtime inventory

| Runtime | Source | Lifecycle | Model representation |
|---|---|---|---|
| llama.cpp | `runners/llama_cpp.py` (297 lines) | LLMGauge-owned bounded subprocess per prompt | GGUF file |
| vLLM (external) | `runners/vllm_external.py` (1443 lines) over `runners/vllm_http.py` (748 lines) | Operator-managed loopback server; LLMGauge never starts/stops/supervises | Served-model name only; local directory provenance deferred |
| SGLang | none | — | — |
| Ollama / TensorRT-LLM / NIM | none (roadmap possibilities) | — | — |

There is no runtime enum, registry, factory, abstract base class, protocol, or
common runner-result type. Backend admission is a closed string allowlist
(`llama.cpp`, `vllm`) duplicated in `core/schemas.py` (profile and runtime
config validators) and `commands/run_helpers._normalize_backend`.
`execute_run` and `execute_multi_turn_run` branch directly on the backend
string. `reject_unsupported_vllm_command` fail-closes `run-batch`,
`run-ladder`, and `fit-ladder` to vLLM.

### 2.3 Mature llama.cpp evidence surface

GGUF file provenance (filename, size, full SHA-256, public `sha256:`+16
display fingerprint), executable backend provenance, `runtime-command.json`,
process-window VRAM sampling, parsed llama metrics, lineage-qualified native
diagnostics (`UPSTREAM_IDENTITY_ALLOWLIST`; 912 placement-qualified identities,
44 also qualifying slot timing), Area 4 neutral metrics, run fingerprints
`v0`–`v5`, full workflow integration (run/batch/ladders/fit-ladder/score/
report/compare/export), and LocalMaxxing (a deliberately llama.cpp-only named
benchmark method).

### 2.4 Bounded vLLM surface

Real but deliberately narrow: loopback-only, text-only, sequential,
non-streaming default, opt-in streaming SSE evidence (`--vllm-streaming-evidence`,
qualified for exactly vLLM 0.27.1), readiness/served-model checks, observed
`/version`, optional `system_fingerprint`, request-window peak VRAM, Area 4
request wall time and TTFT mapping, failure taxonomy, validation, reporting,
comparison consumption, and public export sanitization. Model identity is
`provenance_kind: served_model_only` with null hashes and no run fingerprint;
`--model-path` and profile `path` are rejected for `backend=vllm`.

The accepted [vLLM runtime contract](VLLM_RUNTIME_CONTRACT.md) already defines
a bounded directory-model provenance design (§6 reuses it; it is not
implemented). This document does not weaken any existing conservative evidence
semantics, including the exact-version TTFT qualification and the llama.cpp
lineage allowlist policy.

## 3. Definition of a first-class runtime

A runtime is first-class when it satisfies the acceptance contract in §3.2 for
every `REQUIRED_COMMON` capability and its own `REQUIRED_RUNTIME_SPECIFIC`
capabilities, with every other capability classified. Accepting an HTTP request
does not make a runtime first-class; the current vLLM adapter is explicitly a
bounded adapter, not yet first-class.

### 3.1 Capability classes

| Class | Meaning |
|---|---|
| `REQUIRED_COMMON` | Same observable contract on every first-class runtime; comparable under shared semantics. |
| `REQUIRED_RUNTIME_SPECIFIC` | Must exist on every first-class runtime, but with runtime-native evidence sources and semantics; never merged into a fake common field. |
| `OPTIONAL_RUNTIME_SPECIFIC` | Valuable where the runtime defensibly exposes it; absence is honest `unavailable`. |
| `NOT_APPLICABLE` | The concept has no truthful meaning for that runtime; recorded as such, not as a failure. |
| `DEFERRED_WITH_REASON` | In scope for the target design but explicitly postponed with a recorded reason. |

Examples: llama.cpp `slot_print_timing` is `REQUIRED_RUNTIME_SPECIFIC`
(native-source evidence); vLLM request-boundary TTFT is a runtime-specific
evidence source supporting one neutral metric identity; SGLang scheduler
statistics are `OPTIONAL_RUNTIME_SPECIFIC`; a persistent-server "process exit
status" is `NOT_APPLICABLE` in the external-server mode.

### 3.2 First-class acceptance contract

A runtime reaches first-class status only when all eight categories are
accepted, tested, and documented:

1. **Model identity** — exact requested model; observed model identity where
   the runtime exposes it; local checkpoint provenance (file or directory
   manifest per §4); tokenizer identity; chat-template identity; quantization
   identity with requested / checkpoint-declared / observed-effective kept
   separate.
2. **Execution** — one normalized evaluation per prompt from a suite or plain
   input; exact input preservation (prompt text or ordered chat messages, with
   the selected form recorded); exact generation settings mapped without
   silent dropping or approximation; raw output, cleaned derivative, and
   failure preservation.
3. **Lifecycle** — LLMGauge-managed bounded startup, readiness, model
   admission, and shutdown (§5) as the first-class mode; externally managed
   mode remains supported with its evidence ceiling (§5.3) and is labeled as
   such.
4. **Evidence** — runtime identity (version with source; qualification policy
   where native observation is version-sensitive); model identity per §4;
   settings disclosure with requested-vs-observed separation; timing boundary
   declaration; memory boundary declaration where sampled; runtime-native
   evidence preserved under a runtime namespace; failures classified without
   concealment.
5. **Product workflow** — `validate-result`, `report`, `score`, `compare`,
   `export-index`, and `export-public` all consume the runtime's artifacts
   under the same claim boundaries, with runtime-specific fields rendered
   honestly rather than as blanks in llama-shaped columns.
6. **Automation workflows** — `run-batch`, `run-ladder`, and `fit-ladder`
   execute through capability-gated paths (§7.3) or fail closed with an
   explicit capability statement; a first-class runtime is not restricted to
   one-off `run`.
7. **Security / boundary** — loopback-only default; managed-mode process
   ownership with structured argv and no shell passthrough; authentication
   policy explicit; endpoint/path privacy handling per the existing transport
   threat model; no network behavior beyond the admitted endpoint class;
   no telemetry.
8. **Reproducibility** — runtime version and identity provenance; launch
   arguments or server configuration captured; checkpoint revision or
   manifest fingerprint; tokenizer/template identity; runtime methodology
   label; run fingerprint eligibility under §9 rules.

## 4. Model representation architecture

### 4.1 Three model source kinds

A model representation is a discriminated source kind, not a path shape:

| Source kind | Meaning | Identity mechanism |
|---|---|---|
| `gguf_file` | Single local GGUF file | File SHA-256 + size + filename (implemented today) |
| `checkpoint_directory` | Local Hugging Face / Transformers-style checkpoint directory | Bounded canonical manifest fingerprint (§4.2) |
| `served_model_reference` | Model admitted by an operator-managed server, identified by served-model name | Requested/observed served identity + optional binding to a local source (§4.3) |

`gguf_file` remains first-class and unchanged. `checkpoint_directory` is the
new first-class representation for vLLM/SGLang native evaluation.
`served_model_reference` remains valid but is an attestation-grade identity,
not a cryptographic one, unless bound to a local source.

### 4.2 Directory-model provenance: reuse the accepted design

The [vLLM runtime contract §Directory-model provenance](VLLM_RUNTIME_CONTRACT.md)
already accepts a bounded directory provenance design. This document adopts it
verbatim as the common `checkpoint_directory` provenance semantics — it is not
vLLM-specific and no second incompatible directory fingerprint system may be
created:

- collection is local and offline; no repository resolution or download;
- record: repository/model identifier when known (never a local directory
  path), immutable revision/commit when locally available (mutable labels kept
  separate), architecture from local `config.json`, requested quantization
  separately from locally observed quantization metadata;
- bounded canonical file manifest (non-recursive, lexicographically ordered):
  `config.json` + optional `generation_config.json`;
  `model.safetensors.index.json` plus exactly its `weight_map` shards
  (otherwise the selected root `*.safetensors`); allowlisted quantization
  sidecars (`quantize_config.json`, `quantization_config.json`,
  `compression_config.json`); allowlisted tokenizer files (`tokenizer.json`,
  `tokenizer.model`, `tokenizer_config.json`, `special_tokens_map.json`,
  `added_tokens.json`); the selected `chat_template.jinja` /
  `chat_template.json` or the config file carrying the selected embedded
  template;
- every entry: normalized model-root-relative path, byte size, full SHA-256;
- manifest fingerprint: SHA-256 over deterministic UTF-8 JSON containing a
  versioned manifest-schema identifier and the ordered entries; public display
  form `sha256:` + first 16 lowercase hex characters (display identifier only);
- tokenizer identity: canonical fingerprint over the selected tokenizer
  manifest entries;
- chat-template identity: selected source, selection method, full SHA-256 of
  the exact template bytes (or canonical extracted string), shortened public
  fingerprint; unidentified server-side templating yields `partial` and
  forbids any "same rendered input" claim;
- status vocabulary `available` / `partial` / `unavailable` with specific
  warnings; an evaluation-relevant dependency outside the allowlist forces
  `partial`, never ad hoc manifest expansion or a recursive whole-directory
  hash;
- full hashes and manifest entries remain private evidence; public export
  carries only approved shortened fingerprints and sanitized identifiers.

The existing single-file cache/identity machinery (`core/identity.py`
`hash_file` with path/size/mtime/inode validation) is a `gguf_file` mechanism.
Directory provenance requires its own identity-validated cache strategy (entry
identity per file plus manifest-root identity); the single-file cache format
must not be stretched to represent a directory.

### 4.3 Model identity is independent of runtime

The same checkpoint directory evaluated under vLLM and under SGLang has one
model identity: the `checkpoint_directory` manifest fingerprint. Runtime is
recorded separately (§7). A `served_model_reference` may be bound to a local
source (the operator declares which checkpoint directory the server admitted);
the binding is recorded with its provenance class (`operator_declared`,
`server_reported`, or `llmgauge_observed` in managed mode) and never upgraded
silently. Display-name equality across runtimes is never cryptographic
identity.

### 4.4 Quantization identity

Three facts stay separate for every runtime: requested quantization (user/
profile setting), checkpoint-declared quantization (from hashed local config),
and observed effective quantization (from defensible runtime evidence;
otherwise `unknown`). A filename, a `load_format`, or a dtype never proves an
effective quantization scheme.

## 5. Lifecycle architecture

### 5.1 The decision

Does first-class vLLM/SGLang support require LLMGauge-managed local server
lifecycle? **Yes — managed-local mode is the first-class target mode for
server-backed runtimes.** External-server mode remains a permanently supported
mode with a lower evidence ceiling, not a failure state.

Rationale from repository constraints: the acceptance contract (§3.2) requires
startup/model-admission evidence, launch-configuration capture, bounded
shutdown, and reproducibility facts that an operator-managed server
structurally cannot provide from the client side (the current adapter proves
this ceiling: no load time, no placement, no launch config, no fingerprint).
Managed mode is also the shape LLMGauge already owns for llama.cpp, so it is
the product-consistent design.

### 5.2 Managed-local mode (target)

For a server-backed runtime, LLMGauge:

1. launches the runtime server as a bounded local subprocess from structured
   argv (never a shell string, never arbitrary passthrough; launch arguments
   come from bounded validated profile/config options);
2. records the launch configuration as authoritative evidence (argv,
   executable identity where locally resolvable, environment policy facts
   without secrets);
3. polls a bounded readiness endpoint with an explicit deadline; readiness
   failure is a recorded startup failure, not a retried evaluation;
4. verifies model admission (requested model identity observed in the
   runtime's model/metadata surfaces) before any evaluation request;
5. executes evaluation requests under the existing per-request boundary;
6. shuts down the server it owns, with bounded termination, preserved server
   logs, and honest nonzero-exit/signal reporting;
7. never installs the runtime, downloads models, or restarts a failed server
   mid-run.

### 5.3 Evidence boundary between lifecycle scopes

The accepted two-scope rule is generalized unchanged:

- **Startup/admission scope**: launch configuration, process identity,
  readiness timeline, model-admission start/completion or failure, load-time
  memory evidence, bounded startup diagnostics.
- **Per-request scope**: normalized request, response or classified failure,
  request wall time, usage, finish reason, request-window telemetry, raw
  artifacts.

Load time is never added into request wall time; admission duration is never
used to compute generation throughput; a server being API-ready never implies
warm or cold. In external-server mode the startup scope is partial or
operator-supplied and its provenance is labeled accordingly
(`server_reported` / `operator_supplied` / `unknown`).

## 6. Shared transport versus runtime adapters

The roadmap's "shared OpenAI-compatible HTTP transport" is redefined narrowly:
shared plumbing where semantics are genuinely common, not a generic OpenAI
backend.

**Sharable (proven-common mechanics):**

- bounded loopback endpoint validation and resolution (loopback-only,
  reject userinfo/query/fragment, connect to validated IP with `Host`);
- proxy-environment bypass, redirect refusal, no-retry policy;
- connect + whole-request monotonic deadline handling;
- bounded response-body reads and bounded JSON decode;
- SSE framing: event accumulation, `[DONE]` detection, per-event monotonic
  timestamps, bounded event/body size enforcement;
- sanitized endpoint identity reporting and transport error classification
  scaffolding.

**Never shared (runtime-specific):**

- launch commands and managed-lifecycle semantics;
- readiness semantics (vLLM `/v1/models` + `/version` vs SGLang
  `/health_generate` + `/model_info` + `/v1/models` + `/server_info`);
- model-admission evidence surfaces and their field meanings;
- request extensions (vLLM `return_token_ids=true` vs SGLang
  `return_meta_info`, which is rejected with streaming — the token-boundary
  observation method differs per runtime and per version);
- version qualification policy per observation method;
- reasoning-parser behavior and output-channel semantics;
- runtime-native telemetry, scheduler statistics, and metrics endpoints;
- failure-taxonomy mapping from runtime errors to contract classes.

Admission rule for extraction: shared transport code is extracted from
`runners/vllm_http.py` only when a second runtime adapter demonstrably needs
the same primitive, and only after the existing vLLM tests continue to pass
against the extracted module unchanged in behavior. Until then, vLLM keeps its
transport module.

## 7. Runtime adapters and capability disclosure

### 7.1 Smallest viable seams

The architecture admits exactly these internal seams, each justified by an
existing duplication or fail-closed gate. No plugin framework, entry points,
dynamic discovery, or universal runner ABC is admitted.

1. **Model source reference + provenance provider** — a discriminated source
   kind (§4) with per-kind provenance collection functions in `core/identity`
   space; consumed by planning, fingerprinting, validation, and export.
2. **Runtime descriptor (static internal registry)** — one module-level
   mapping from backend id to: capability flags, settings it accepts, its
   provenance kinds, and its evidence artifact family. Replaces the duplicated
   closed allowlists and `reject_unsupported_vllm_command` with a capability
   query. It is internal, closed, and edited per runtime — not user-extensible.
3. **Normalized invocation result envelope** — the shared fields already
   conceptually present in both `LlamaCppRunResult` and `VllmRequestResult`
   (generated text, finish reason, backend token counts with source labels,
   wall time with boundary id, failure class/detail, evidence references),
   while each adapter keeps its native payload namespaced. This formalizes
   what `core/multi_turn.ModelInvocationResult` already proves is possible.
4. **Lifecycle controller (server-backed runtimes)** — managed-mode launch /
   readiness / admission / shutdown per §5.2, owned by the runtime adapter,
   producing the startup-scope artifact.
5. **Shared loopback HTTP/SSE transport** — extracted per §6's admission rule.

Explicitly rejected: a generic "OpenAI-compatible backend" that hides runtime
identity; a universal metrics struct that merges non-equivalent native fields;
per-runtime forks of the result schema; a dependency-injected plugin system;
rewriting the llama.cpp execution path behind a new abstraction before the
seams above are proven by the vLLM program.

### 7.2 Runtime-specific evidence stays namespaced

Native evidence keeps runtime-owned identities under the existing pattern:
`llama_cpp_timing`, `slot_print_timing`, `llama_cpp_placement`,
`vllm-runtime-evidence.json`, `request/*.json`, `request/*.stream.json`.
Neutral Area 4 records (`llmgauge.metric.v1.*`) remain the only cross-runtime
vocabulary, and only where the accepted boundary/workload checks pass.
Reports render adapter settings from what each runtime represents; llama-shaped
columns (batch/ubatch/GPU layers/flash-attn) must not be presented as common
fields for server runtimes.

### 7.3 Capability-gated automation

`run-batch`, `run-ladder`, and `fit-ladder` generalize through the runtime
descriptor's capability flags, not by assuming every runtime tunes every knob:

- context ladder: meaningful for any runtime with a context limit; the plan
  axis is context only;
- fit ladder: llama.cpp's fallback axes (context, batch, ubatch, GPU layers)
  are adapter-specific attempt settings; a server-backed runtime's fit surface
  is admission viability and bounded launch configuration, which is a
  different (and initially deferred-with-reason) design;
- batch: sequential multi-profile execution is transport-independent and
  becomes available when the adapter declares safe sequential execution;
- LocalMaxxing remains a named llama.cpp interoperability method
  (`NOT_APPLICABLE` for other runtimes; other runtimes would need their own
  separately contracted benchmark methods).

## 8. vLLM first-class target (current → target delta)

| Surface | Current (bounded adapter) | First-class target |
|---|---|---|
| Model profiles | served-model name only; local paths rejected | `checkpoint_directory` profile with manifest provenance; served-name binding to local source with provenance class |
| Model provenance | `served_model_only`, null hashes, no fingerprint | Directory manifest fingerprint (§4.2); tokenizer + chat-template identity; quantization three-way disclosure; fingerprint eligibility under §9 |
| Launch configuration | none (operator-owned) | Managed mode: captured argv + executable identity + config evidence |
| Lifecycle | external only | Managed-local primary (§5.2); external retained with labeled evidence ceiling (§5.3) |
| Admission evidence | `/v1/models` listing + `/version` | Plus startup/admission artifact in managed mode; load-time evidence separated from request evidence |
| Single run | text-only, sequential, non-streaming default + opt-in streaming | Unchanged request semantics; input forms extended (below) |
| Chat/messages input | suite prompt wrapped as system+user messages | Explicit ordered-messages input form preserved role-by-role; multi-turn sends role-preserving history instead of flattened text |
| Sampling profiles | temp/top-p applied; `runtime.profile` not persisted; top-k/min-p/seed rejected | Capability-negotiated: supported settings applied and persisted with profile identity evidence; unsupported settings fail closed (current behavior preserved) |
| Batch / ladder / fit-ladder | fail-closed rejection | Batch + context ladder via capability flags; fit-ladder design deferred with reason (server fit semantics differ) |
| Multi-turn | works via flattened rendered turns | Role-preserving transcript execution |
| Validation / report / compare / export | already consume vLLM results | Extended for new provenance kinds and lifecycle artifacts; adapter-settings rendering per §7.2 |
| Streaming / TTFT | exact 0.27.1 qualification | Unchanged; qualification broadened only by separately reviewed evidence milestones, never by this contract |
| VRAM | request-window device-used sampler | Plus managed-mode server-window observation as a distinct boundary; never conflated |
| Native metrics | usage tokens, end-to-end completion TPS | Plus defensibly observed server-reported timing where version-qualified; `generation_tps`/`prompt_eval_tps` remain null, not fabricated |

## 9. SGLang first-class target

SGLang is not vLLM with a different label. Research against current upstream
documentation/source (2026-09) establishes the target shape; the first
implementation slice remains external-server mode (mirroring how vLLM was
introduced), then managed mode per §5.

**Genuinely reusable from the vLLM program:** the shared loopback HTTP/SSE
transport primitives (§6), the directory-model provenance provider (§4.2), the
normalized invocation result, capability-gated workflows, validation/report/
export extension patterns, and the exact-version-qualification discipline for
any native observation method.

**SGLang-specific requirements (observed upstream facts):**

- launch entrypoint `sglang serve --model-path …` (with `--served-model-name`,
  `--chat-template`, `--dtype`, `--quantization`, `--context-length`,
  `--mem-fraction-static`, tp/dp options);
- readiness: `/health_generate` (exercises a real one-token generation path;
  `/health` is weaker); model admission: `/model_info` (served name,
  `model_path`, `tokenizer_path`, `weight_version`, `load_format`, parser
  settings) plus `/v1/models` (exact id, `max_model_len`); configuration
  evidence: `/server_info` (resolved launch args including declared
  quantization/dtype/kv-cache-dtype, version, startup time, scheduler info);
- quantization is frequently auto-detected from checkpoint config; declared
  launch quantization, checkpoint-declared quantization, and effective
  quantization must be recorded as three separate labeled facts (§4.4);
- chat-template resolution order (SGLang built-in by model path → processor
  template → tokenizer template) means a `None` template argument does **not**
  prove which template was used; no public endpoint exposes the effective
  template text, so first-class template identity requires an explicit
  `--chat-template` file captured and hashed by LLMGauge, or an honest
  `partial`/`unobserved` label;
- SGLang can update weights without restart; admission identity must be
  captured before and after the run to expose mid-run drift;
- streaming: standard OpenAI SSE; `return_meta_info` is rejected with
  streaming, so the vLLM token-ID observation method does not transfer —
  TTFT must be client-side from preserved SSE evidence, with its own
  exact-version qualification after end-to-end fixture proof;
- `/metrics` (opt-in Prometheus) and `meta_info.e2e_latency` are aggregate or
  supplementary evidence, never per-request TTFT substitutes; memory-pool and
  token-capacity fields are configuration evidence, not measured VRAM — the
  independent NVIDIA sampler remains the VRAM mechanism;
- release cadence is fast (multiple 0.5.x releases per quarter) with
  deprecated endpoint churn — exact-version qualification and
  non-deprecated-endpoint-only contracts are required.

**No commitment is made here to any metric that cannot be defensibly
observed.** Load-time, placement, and steady-state VRAM boundaries for SGLang
follow the same admit-only-on-proof rule as Area 4.

## 10. Cross-runtime evaluation identity

Comparing the same model family across GGUF/llama.cpp, safetensors/vLLM, and
safetensors/SGLang is legitimate only under disclosure. A GGUF quantized
derivative and a BF16/FP8/AWQ checkpoint are not the same model binary or the
same numerical implementation.

Identity tiers (recorded, never inferred from a display name):

| Tier | Evidence | Permitted claim |
|---|---|---|
| `same_checkpoint_identity` | Matching manifest fingerprints (or operator-verified conversion lineage recorded as evidence) | Same weights content; representation/quant differences still disclosed |
| `same_family_declared` | Shared family identifier + declared upstream lineage | Same family; not same weights |
| `display_name_match` | Names coincide | No same-model claim |

Every cross-runtime comparison must preserve and disclose: model-family
relationship tier; exact checkpoint identity per side; representation (GGUF
file vs directory); quantization/dtype (three-way per §4.4); tokenizer
identity; chat-template identity; runtime and runtime version; sampling
settings; input rendering (prompt vs messages vs server-side template); and
evidence boundary (process window vs request window vs server window).

Comparison behavior evolves additively: `compare` keeps its current
like-for-like setting groups, and the model-identity tier becomes an explicit
disclosure line rather than a silent `mixed_model` note; quality-ranking
claims remain gated by the accepted methodology document, which stays
authoritative for claim language.

## 11. Schema and compatibility assessment

No schema changes occur in this milestone. The compatibility strategy for the
program:

**Expected additive (no version bump):**

- new optional profile fields (source-kind discriminator values, checkpoint
  root, launch-config reference) under `extra="allow"` and tolerant loading;
- new optional `model.provenance` fields (`provenance_kind` values beyond
  `served_model_only`, manifest fingerprint, tokenizer/template identity,
  quantization triple) — older results without them remain valid;
- new optional artifacts (`server-runtime-evidence.json`-family files for
  server-backed runs, admission/startup artifacts) referenced optionally from
  `runtime`;
- new optional runtime fields namespaced per adapter; capability disclosure in
  reports/comparisons;
- validators accepting previously valid artifacts unchanged.

**Would require a versioned change:**

- any new required field or changed semantics in `llmgauge.result.v0`
  (avoided; none is planned);
- run-fingerprint payload extension to cover directory-manifest identity or
  managed-lifecycle evidence → new `run_fingerprint` payload version (v6+);
  existing v0–v5 payloads remain byte-verifiable under their original rules;
- a model-profiles document schema bump only if the discriminator becomes a
  required field — the preferred path keeps it optional with
  `gguf_file`-implicit behavior for legacy documents;
- public-derivative schema additions follow the existing
  `llmgauge.public_*.v0` pattern with human review before publication.

Historical results (v0.x through 1.0 policy) must remain valid and readable
throughout the program. `runtime-command.json` remains structured llama.cpp
process evidence and is never repurposed for HTTP/server runs.

## 12. Migration risk analysis (llama.cpp regression protection)

Core requirement: llama.cpp/GGUF behavior stays stable while multi-runtime
support lands incrementally. The anti-pattern to avoid is a big-bang rewrite
around a new backend abstraction.

| Risk | Vector | Control |
|---|---|---|
| Default-runtime drift | backend resolution changes during registry introduction | `llama.cpp` remains the default for every legacy config/profile/flag combination; regression tests pin default resolution and command construction before refactors |
| Profile breakage | discriminator added to `ModelProfileEntry` | Legacy profiles validate unchanged with implicit `gguf_file`; `extra="allow"` preserved; CRUD commands keep current flags |
| Fingerprint invalidation | payload changes | v0–v5 payloads frozen; new identity kinds enter only via new payload versions |
| Evidence-semantics weakening | generalization pressure on lineage/timing/TTFT gates | `UPSTREAM_IDENTITY_ALLOWLIST`, the 912/44 manifest, and exact-0.27.1 TTFT qualification are untouchable by runtime-generalization milestones |
| Report/comparison regressions | shared renderers rewritten | Adapter settings render conditionally; existing llama columns/rows byte-stable for llama-only comparisons |
| Ladder/batch behavior change | capability-gate refactor | `reject_unsupported_vllm_command` replaced by capability query with identical llama.cpp pass-through behavior and identical vLLM rejection messages until parity milestones change them deliberately |
| Export leakage of new provenance | directory paths/hashes | Export allowlist extended only in the same milestone that adds sanitizer coverage; full hashes and paths stay private |
| LocalMaxxing coupling | shared helpers | LocalMaxxing stays llama.cpp-only; no shared-code extraction may import its telemetry assumptions |
| Test-suite churn | refactors | Each milestone keeps the full suite green without editing llama.cpp assertions except where a contract change is the milestone's named purpose |

## 13. Ordered development program

Seven bounded milestones. Each is independently inspectable, testable, and
mergeable; none may weaken §12's protected semantics.

### M1 — Runtime-neutral model representation and profile contract (implementation)

- **Status:** Implemented (post-v0.78 on `main`).
- **Goal:** source-kind discrimination (`gguf_file` | `checkpoint_directory` |
  `served_model_reference`) implemented in model-profile validation,
  resolution, and CLI surface — no execution behavior change.
- **Depends on:** this document.
- **Likely files:** `core/schemas.py`, `core/config.py`,
  `core/model_profiles_store.py`, `commands/models.py`, `commands/setup.py`
  (guided-setup source awareness), `commands/run_helpers.py` (resolution only),
  tests.
- **Proof:** legacy GGUF profiles validate and resolve byte-identically; new
  directory/served profile shapes validate with clear errors; `model add`
  accepts a checkpoint root without touching execution; full suite green.
- **Non-goals:** no provenance hashing, no runner changes, no schema artifact
  changes.

### M2 — Directory-model provenance collection and fingerprint eligibility

- **Status:** Implemented (post-v0.78 on `main`).
- **Goal:** implement §4.2 provenance collection (manifest, tokenizer,
  template, quantization-declared), its cache strategy, additive
  `model.provenance` fields, validator coverage, report/export handling, and
  the new run-fingerprint payload version for manifest identity.
- **Depends on:** M1.
- **Likely files:** `core/identity.py`, `core/run_fingerprint.py`,
  `core/result_validation.py`, `core/public_export.py`, `core/reports.py`,
  `docs/ARTIFACT_SCHEMAS.md`, tests.
- **Proof:** synthetic checkpoint-directory fixtures prove `available` /
  `partial` / `unavailable` states, fingerprint recomputation, cache
  invalidation on file identity change, and private/public disclosure split.
- **Non-goals:** no runtime can consume directory provenance yet (vLLM wiring
  is M3); no server lifecycle.

### M3 — vLLM first-class model identity

- **Goal:** vLLM profiles bind `checkpoint_directory` (local provenance) and
  `served_model_reference` (requested/observed identity with binding
  provenance class); quantization three-way disclosure; tokenizer/template
  identity in results; sampling-profile persistence for vLLM runs; fingerprint
  eligibility for vLLM results with local provenance.
- **Depends on:** M1, M2.
- **Likely files:** `commands/run_helpers.py`, `runners/vllm_external.py`,
  `core/schemas.py`, `core/result_validation.py`, `core/reports.py`,
  `core/compare.py`, `core/public_export.py`, `docs/VLLM_RUNTIME_CONTRACT.md`
  (status alignment), tests.
- **Proof:** dry-run + synthetic-fixture runs prove identity binding,
  fail-closed mismatch behavior, and additive validation; existing vLLM
  artifacts remain valid.
- **Non-goals:** no managed lifecycle, no batch/ladders, no TTFT qualification
  change.

### M4 — vLLM managed-local lifecycle

- **Goal:** §5.2 launch/readiness/admission/shutdown for an operator-configured
  vLLM server, with the startup-scope artifact and §5.3 evidence separation;
  external mode retained and labeled.
- **Depends on:** M3.
- **Likely files:** new `runners/` lifecycle module, `commands/run_helpers.py`,
  `core/schemas.py` (bounded launch options), validators, reports, tests with
  scripted loopback transports (labeled synthetic).
- **Proof:** scripted-server tests prove bounded startup, readiness deadline,
  admission verification, shutdown, log preservation, nonzero-exit honesty, and
  that no load time enters request wall time.
- **Non-goals:** no SGLang, no fit-ladder server design, no dependency
  admission (stdlib subprocess + existing transport).

### M5 — vLLM workflow parity

- **Goal:** capability-gated `run-batch` and context ladder for vLLM;
  role-preserving multi-turn messages; adapter-aware report/comparison
  rendering (§7.2); fit-ladder disposition recorded as
  `DEFERRED_WITH_REASON` with its design note.
- **Depends on:** M3 (M4 not strictly required for external-mode batch).
- **Likely files:** `commands/batch.py`, `commands/ladders.py`,
  `run_helpers.py`, `core/batch.py`, `core/ladder.py`, `core/compare.py`,
  `core/reports.py`, `core/multi_turn.py` (invocation contract), tests.
- **Proof:** batch/ladder orchestration over scripted transports; transcript
  role preservation; llama-only comparison output unchanged.
- **Non-goals:** no SGLang, no concurrency, no LocalMaxxing change.

### M6 — Shared server transport extraction + SGLang external adapter

- **Goal:** extract the proven-common §6 primitives from `vllm_http.py` (no
  behavior change), then implement the SGLang external-mode adapter:
  `/health_generate` readiness, `/model_info` + `/v1/models` admission,
  bounded `/server_info` projection capture, three-way quantization, template
  policy per §9, client-side SSE TTFT under its own exact-version
  qualification, failure taxonomy mapping.
- **Depends on:** M4, M5 (proven adapter shape).
- **Likely files:** new shared transport module, new `runners/sglang_external.py`,
  `core/schemas.py` (backend admission), validators, reports, export, tests.
- **Proof:** synthetic loopback fixtures prove readiness/admission/
  mismatch/timeout paths; vLLM tests pass unchanged against extracted
  transport; no unqualified TTFT emitted.
- **Non-goals:** no SGLang managed lifecycle, no `/generate` evaluation path,
  no metrics-endpoint claims.

### M7 — SGLang lifecycle/parity + cross-runtime identity hardening

- **Goal:** SGLang managed-local mode, batch/ladder parity, and the §10
  identity-tier disclosure in `compare`/reports/export across all three
  families.
- **Depends on:** M6.
- **Likely files:** SGLang adapter/lifecycle modules, `core/compare.py`,
  `core/reports.py`, `docs/VLLM_CROSS_RUNTIME_COMPARISON_METHODOLOGY.md`
  (extend to three families), tests.
- **Proof:** three-way synthetic comparison fixtures prove tiered identity
  disclosure and that no false same-model or metric-equivalence claim is
  representable.
- **Non-goals:** no Ollama/TensorRT-LLM/NIM, no release work.

Program order rationale: foundation (M1–M2) before any runtime consumes it;
vLLM matures first because its contract, transport, evidence, and workflow
surface are already partially built; shared plumbing is extracted only after
two adapters prove what is genuinely common (M6); SGLang consumes the proven
pattern; cross-runtime identity hardening lands last when all three families
have real artifacts to disclose.

## 14. Selected next milestone

**M1 — Runtime-neutral model representation and profile contract** (§13 M1).

It is the only prerequisite that everything else consumes, it is bounded to
profile/config/CLI validation with zero execution-path behavior change, it is
backward-compatible by construction (legacy GGUF profiles unchanged), and it is
independently provable with schema and CLI tests. No other prerequisite was
found more fundamental: the transport, lifecycle, and evidence designs already
have accepted contracts; the model-identity generalization does not.

> Update (2026-09-03): M1 is implemented on `main` (post-v0.78). The selected
> next milestone was M2 — directory-model provenance collection and
> fingerprint eligibility (§13 M2).

> Update (2026-09-03): M2 — directory-model provenance collection and
> fingerprint eligibility (§13 M2) is implemented on `main` (post-v0.78):
> bounded local checkpoint-directory identity, the versioned canonical
> manifest, the separate identity-validated directory cache, tokenizer and
> chat-template identity, checkpoint-declared quantization evidence, additive
> `model.provenance` validation/report/export handling, and the frozen
> `llmgauge.run_fingerprint.v6` payload for manifest identity. No runtime
> consumes directory provenance yet. The selected next milestone is now
> M3 — vLLM first-class model identity (§13 M3).

## 15. Consequences

- The product framing shifts from "GGUF through llama.cpp, plus a bounded vLLM
  adapter" to three first-class runtime families with honest, namespaced
  differences.
- Model identity becomes a runtime-independent concept; the same checkpoint
  under vLLM and SGLang is one model evaluated twice, not two unrelated
  identities.
- Managed server lifecycle becomes in-scope product behavior for
  server-backed runtimes while external-server mode keeps its supported,
  labeled evidence ceiling.
- No existing evidence qualification is weakened; every new observation
  method earns its own exact-version qualification before admission.
- The roadmap's runtime-interoperability track is re-expressed as this
  program; Ollama, TensorRT-LLM, and NIM remain possible later runtimes that
  would enter through the same acceptance contract, with no promised version or
  date.
