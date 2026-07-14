# vLLM Runtime Integration Contract

- Status: Accepted
- Accepted: 2026-07-14
- Scope: Initial externally managed, local vLLM integration
- Decision type: Architecture and evidence contract

## Context

LLMGauge currently evaluates GGUF models by launching `llama.cpp` directly for
each run. vLLM has a different lifecycle: it admits a model into a persistent
server and serves inference requests over an API. Treating those lifecycles as
identical would mix model-loading evidence with request evidence and would make
latency and failure claims misleading.

A local investigation of `unsloth/gemma-4-12b-it-NVFP4` with vLLM 0.25.1 on an
RTX 5070 12 GB system established a narrow result. The runtime stack recognized
the platform and checkpoint and selected native FP8 and NVFP4 implementations
on SM120. Text-only loading required image, audio, and video inputs to be
disabled. Full-GPU model admission then failed while allocating a
higher-precision output head after approximately 9.64 GiB was already in use;
inference was not reached. This is evidence of a 12 GB fit failure during model
admission. It is not evidence of an unsupported architecture, checkpoint
format, quantization kernel, or model in general.

This decision admits no dependency and implements no runtime behavior. It
defines the boundary that later implementation milestones must preserve.

## Accepted decisions

### Runtime ownership and initial capability

The initial vLLM backend is an OpenAI-compatible HTTP client for a server that an
operator manages outside LLMGauge.

LLMGauge will:

- accept only a loopback endpoint;
- evaluate text-only input;
- issue one evaluation request at a time;
- use non-streaming responses;
- perform bounded readiness and served-model checks separately from evaluation
  requests; and
- preserve request, response-derived, error, provenance, and telemetry evidence
  in the normal result lifecycle.

LLMGauge will not install vLLM or its dependencies, download models, or start,
stop, restart, supervise, configure, or recover the server. The operator owns
server lifecycle, model admission, device selection, and server logs. A server
failure remains visible; LLMGauge must not silently restart it.

The initial contract excludes multimodal inputs, streaming, remote or cloud
endpoints, authentication, arbitrary request headers, LoRA adapters,
speculative decoding, batching, concurrency benchmarking, distributed
inference, and automatic server lifecycle management.

### Backend boundary

The two supported runtime shapes have different ownership:

| Concern | Direct-process runtime (`llama.cpp`) | Persistent-server runtime (vLLM) |
|---|---|---|
| Lifecycle owner | LLMGauge launches a bounded subprocess | Operator manages a server outside LLMGauge |
| Invocation | Structured process arguments | Bounded OpenAI-compatible HTTP request |
| Model admission | Occurs within the launched process | Occurs before evaluation and outside request timing |
| Failure evidence | Exit status and process logs | HTTP/transport response plus separately supplied server evidence |
| Reuse | Normally process-scoped | Server and admitted model may span requests or runs |

The common backend responsibilities are deliberately narrow:

1. accept one normalized evaluation request;
2. preserve the exact prompt or ordered chat messages used for that request;
3. map supported generation settings without silently changing them;
4. execute or submit exactly one non-streaming request;
5. return generated text and available usage and finish metadata;
6. measure request wall time at the LLMGauge boundary;
7. classify failures without converting them into successful results;
8. identify the runtime and model as far as evidence permits; and
9. preserve raw and normalized evidence through relative artifact references.

Lifecycle control, installation, model acquisition, runtime tuning, and a
universal plugin API are not common responsibilities. This contract does not
create a backend registry or speculative plugin framework. Later code should
introduce only the smallest interface required to keep the existing direct
runner and the vLLM request adapter honest about their different lifecycles.

## Request and result normalization

Normalization provides comparison vocabulary, not an assertion that runtimes
have equivalent implementations.

### Request concepts

| Concept | Contract |
|---|---|
| Input | Exactly one plain prompt or one ordered list of chat messages with roles and text content. Preserve the selected form and the exact rendered prompt when the runtime exposes it. |
| Model selection | A requested served-model name for vLLM; a local GGUF identity for `llama.cpp`. Record the requested value separately from the observed model identity. |
| Context limit | Record the requested context limit. Record an effective or server-advertised limit only when observed; otherwise use `unknown`. Do not infer it from a model card or filename. |
| Generation limit | Record the requested maximum completion-token count and the backend field used to express it. A server-side cap is separate observed evidence when available. |
| Sampling | Record requested temperature, top-p, seed, and any other admitted bounded setting. Unsupported settings must fail capability validation rather than be dropped or approximated. |
| Reasoning behavior | Preserve requested reasoning metadata under the existing compatibility rule. Do not infer effective reasoning behavior from a request setting. |

A prompt and chat messages are alternative input forms, not automatically
interchangeable. Applying a tokenizer chat template can change the evaluated
input and must be attributable to a specific tokenizer and chat-template
identity. LLMGauge must not silently convert one form to the other with an
unidentified template.

### Result concepts

| Concept | Contract and equivalence boundary |
|---|---|
| Generated text | Preserve the exact response text supplied by the backend before any cleaned review derivative. Chat content and direct text output share this concept but may have different framing. |
| Finish reason | Preserve the backend value and map it to a small normalized value only when the mapping is lossless. Unknown values remain available as backend-specific evidence. |
| Prompt tokens | Use a backend-reported count when present and label its source. Tokenizer-side recounting is not equivalent and must be separately labeled. |
| Completion tokens | Use a backend-reported count when present and label its source. Do not derive a count from text length. |
| Request wall time | Monotonic time from immediately before request transmission through receipt and validation of the complete non-streaming response. It includes local transport, server queueing, prefill, decoding, and response transfer. |
| Error | One normalized failure class plus preserved bounded backend detail. Transport success does not imply evaluation success. |
| Runtime identity | Backend kind plus requested and observed backend provenance. Missing version or kernel evidence remains `unknown`. |
| Model identity | Requested model selection plus observed served identity and local provenance when available. A matching display name alone is not cryptographic identity. |
| Evidence artifacts | Relative references to authoritative raw input/output, bounded response/error evidence, optional server-startup evidence, and optional telemetry. Cleaned output remains derived. |

Token counts from different tokenizers may not be equivalent. Finish-reason
vocabularies may not map exactly. Context limits, server queue time, backend
prefix caching, speculative behavior, sampling implementations, and memory
measurements may be unavailable or non-equivalent. Reports and comparisons must
surface these limits rather than fill them with guessed values.

## Startup, model-admission, and request evidence

A persistent server creates two evidence scopes that must never be merged.

### Server startup and model-admission evidence

This scope may identify:

- server process and version information;
- model admission start and completion or failure;
- requested model and quantization settings;
- device and implementation selection;
- load-time memory evidence; and
- bounded startup diagnostics supplied by the operator or obtained from a
  defensible runtime metadata source.

Because LLMGauge does not own the server lifecycle, startup evidence can be
partial or unavailable. Its provenance must identify whether a value was
server-reported, observed in a bounded operator-supplied artifact, or supplied
as operator metadata. Unrestricted server logs are not copied implicitly.

A model-admission duration, when available, is a startup metric. It must not be
added to request latency or used to calculate generation throughput.

### Per-request evaluation evidence

This scope begins at the LLMGauge request boundary and contains the normalized
request, complete response or classified failure, wall time, usage, finish
reason, request-time telemetry, and raw prompt/output artifacts. It must not
claim to measure server startup or model loading.

Server-state terminology is conservative:

- `cold`: direct evidence shows this is the first evaluation request after a
  fresh server start or fresh model admission. The label does not move startup
  duration into request latency.
- `warm`: direct evidence shows the same server/model admission has already
  completed at least one successful request. It does not claim cache state,
  cache reuse, or identical server load.
- `unknown`: the default when lifecycle history is not observed by LLMGauge.

A server being ready is not enough to label a request warm. A first request is
not enough to label it cold without evidence of a fresh lifecycle.

## Directory-model provenance

Transformers or safetensors checkpoints require a directory identity rather
than the current single-GGUF-file identity. Collection is local and offline; it
must not resolve or download repository data over the network.

The model provenance record should contain:

- repository or model identifier when known, never a local directory path;
- immutable revision or commit when locally available, with mutable labels and
  operator-supplied identifiers kept separate;
- architecture from local configuration when available;
- requested quantization separately from locally observed quantization metadata;
- a bounded evaluation-relevant file manifest;
- every manifest entry's normalized relative path, byte size, and full local
  SHA-256;
- a canonical full manifest fingerprint and shortened public display
  fingerprint;
- tokenizer identity;
- chat-template identity; and
- `available`, `partial`, or `unavailable` status with specific warnings.

### Canonical file set

The initial canonical manifest is limited to files that determine text model
weights, model configuration, tokenization, or chat rendering:

1. `config.json` and, when present, `generation_config.json`;
2. `model.safetensors.index.json` and exactly the weight shards referenced by
   its `weight_map`; otherwise all root-level `*.safetensors` files selected by
   the admitted local checkpoint;
3. present quantization sidecars from the explicit allowlist
   `quantize_config.json`, `quantization_config.json`, and
   `compression_config.json`, when the selected runtime configuration uses
   them;
4. present tokenizer files from the explicit allowlist
   `tokenizer.json`, `tokenizer.model`, `tokenizer_config.json`,
   `special_tokens_map.json`, and `added_tokens.json`; and
5. the selected standalone `chat_template.jinja` or `chat_template.json`, or
   the configuration file that contains the selected embedded chat template.

An admitted checkpoint that depends on an evaluation-relevant file outside
these allowlists has `partial` provenance until a later versioned canonical set
admits that file. Implementations must not silently add files ad hoc or replace
this bounded selection with a recursive hash of every directory file.
Documentation, examples, caches, optimizer states, unrelated processor assets,
and unselected multimodal assets are outside the initial text-evaluation
manifest.

Paths are normalized model-root-relative paths and ordered lexicographically.
The canonical manifest fingerprint is the full SHA-256 of deterministic UTF-8
JSON containing a versioned manifest schema identifier and the ordered entries
with path, size, and full file SHA-256. The public display form is `sha256:` plus
the first 16 lowercase hexadecimal characters. It is a display identifier, not
a substitute for the full local fingerprint.

Tokenizer identity is a canonical fingerprint over the selected tokenizer
manifest entries. Chat-template identity records the selected source, selection
method, and full SHA-256 of the exact template bytes or canonical extracted
string, plus a shortened public fingerprint. If server-side templating cannot be
identified, provenance is `partial`; LLMGauge must not claim that two chat runs
used the same rendered input.

Missing local repository metadata, revision, tokenizer assets, template source,
or some hashes must be reported as partial or unavailable. It must not make an
otherwise usable result invalid unless the absent identity is required to
interpret the evaluated input. Full local hashes and manifest entries remain
private evidence. Public export retains only approved shortened fingerprints
and separately approved, sanitized model identifiers or filenames.

## vLLM backend provenance

Requested configuration and observed implementation are separate fields with
separate evidence sources. The desired backend record includes:

| Metadata | Contract |
|---|---|
| vLLM version | Observed version and evidence source; `unknown` if the OpenAI-compatible API does not expose it. |
| Python, PyTorch, CUDA runtime, Transformers | Observed version values with source, never inferred from the client environment. |
| compressed-tensors | Record observed version when relevant; otherwise `not_applicable` or `unknown`, not an invented version. |
| Served model name | Preserve requested name and model-list or response-observed name separately; mismatch is a failure. |
| Lifecycle ownership | `external_operator` for this contract. |
| Endpoint identity | Sanitized scheme, loopback class, and port only; no user information, query, fragment, credentials, or arbitrary path. |
| Device | Observed device class and model only from bounded server or operator evidence. |
| Compute capability | Observed major/minor capability with source; do not infer it solely from a GPU marketing name. |
| Quantization | Preserve requested mode separately from checkpoint metadata and observed implementation. |
| Kernel or implementation | Record only defensible observed selection evidence and its source. Absence remains `unknown`. |

Client Python or CUDA metadata is not server metadata. Operator-supplied startup
facts must be labeled as such. A requested `nvfp4` mode, a checkpoint declaring
NVFP4, and startup evidence selecting an NVFP4 kernel are three different facts.

## Initial metrics

The initial backend supports only these normalized metrics:

- request wall time;
- backend-reported prompt tokens, when present;
- backend-reported completion tokens, when present;
- end-to-end completion throughput, calculated only as completion tokens divided
  by positive request wall time and labeled as end-to-end rather than decode-only
  throughput;
- raw and normalized finish reason where a lossless mapping exists;
- bounded server-reported usage metadata;
- sampled peak GPU memory, with sampler, interval, device scope, and collection
  status;
- request-timeout classification; and
- runtime-error classification.

Sampled peak GPU memory is an observed sample maximum, not an exact allocator
peak and not necessarily attributable only to vLLM. Missing samples remain
unavailable. Server-reported usage is preserved with its source and is not
silently replaced by a local tokenizer recount.

Time to first token is deferred until streaming is designed and implemented.
Non-streaming responses cannot establish it. LLMGauge must not fabricate prompt
evaluation throughput from total wall time or from token counts without a
separate server-reported prefill duration. It must not label end-to-end
completion throughput as decode throughput.

## Security and privacy boundaries

The initial transport is intentionally local and credential-free:

- Accept `http` endpoints only when every resolved destination is loopback.
  Loopback IP literals are preferred; `localhost` requires loopback-only
  resolution.
- Reject non-loopback destinations. Remote and cloud support is deferred rather
  than enabled by an override in the initial adapter.
- Reject URL user information, credentials, query strings, and fragments.
  Redirects are disabled; a redirect is not followed to a new trust boundary.
- Use explicit bounded connection and whole-request timeouts. A timeout is a
  recorded failure, not permission to wait indefinitely.
- Do not read, emit, or preserve API keys, bearer tokens, cookies, credential
  URLs, or authentication headers.
- Do not accept arbitrary request headers. The adapter owns a fixed minimal
  content-negotiation header set.
- Bypass environment-proxy discovery explicitly for loopback requests. Record
  the proxy-bypass policy, not proxy environment values. `HTTP_PROXY`,
  `HTTPS_PROXY`, `ALL_PROXY`, and `NO_PROXY` contents must not enter artifacts.
- Do not silently retry an evaluation request. A retry can consume different
  randomness, cache state, server load, and tokens. Any future explicit retry
  workflow must preserve every attempt as separate evidence.
- Keep readiness and served-model checks distinct from the evaluation request;
  bounded readiness polling must not become a hidden request retry.
- Sanitize endpoint reporting to the bounded identity above. Raw URLs, response
  headers, and unrestricted response bodies must not be copied into public
  metadata.

New vLLM artifacts may enter public export only after the export allowlist,
sanitization, secret/path checks, and structural validation cover them. Public
export must remain a separate derivative, must not mutate source evidence, must
omit full local hashes, and must still require human review.

## Artifact and schema compatibility

vLLM evidence follows the existing result lifecycle: the private result
directory remains canonical; raw input and output remain authoritative;
cleaned output remains derived; validation checks structure rather than answer
quality; and public export creates a sanitized copy without changing the source.

Later schema work must be additive:

- keep `llmgauge.result.v0` top-level contracts and existing prompt artifacts;
- add optional runtime lifecycle, server-state, request-metric, model-provenance,
  backend-provenance, error-classification, startup-evidence, and
  server-response-evidence fields or referenced artifacts;
- keep backend-specific metadata namespaced rather than forcing false common
  fields;
- tolerate missing new fields and preserve unknown optional fields; and
- continue accepting valid llama.cpp and legacy v0.x results through 1.0 under
  the existing compatibility policy.

`runtime-command.json` is structured `llama.cpp` process evidence. It must not be
repurposed to pretend an HTTP request is a subprocess command. A server-backed
run may omit that artifact and use a separately versioned optional request or
runtime evidence artifact. Exact filenames and JSON fields belong to the later
schema milestone, after implementation needs are proven.

Extending canonical run fingerprints requires an explicitly versioned canonical
payload that includes authoritative vLLM evidence without changing the meaning
of existing fingerprints. Old fingerprints remain verifiable under their
original rules. Validators and public export must be updated before a new
backend artifact becomes part of the durable contract.

## Failure taxonomy

Every failed attempt remains failed evidence with a normalized class and bounded
backend detail:

| Failure class | Meaning |
|---|---|
| `endpoint_unavailable` | Loopback connection could not be established or closed before a valid response. |
| `readiness_failure` | The bounded readiness check did not establish a ready API. |
| `served_model_mismatch` | The requested served-model identity was not available or the response identified a different model. |
| `request_timeout` | The bounded evaluation-request deadline expired. |
| `malformed_response` | The response could not satisfy the expected bounded OpenAI-compatible shape. |
| `server_request_error` | The server rejected a syntactically valid request with a client- or server-error response. |
| `model_admission_load_failure` | Startup evidence shows model admission or loading failed before inference. Preserve a more specific resource-fit label when supported. |
| `request_execution_failure` | The admitted model failed while executing an evaluation request. |
| `incomplete_usage_metadata` | Output may be usable, but required-for-claim usage fields are absent or incomplete. This is not silently upgraded to complete metrics. |
| `unsupported_capability` | The requested input or setting is outside the admitted text-only, non-streaming contract. |
| `operator_cancellation` | The operator cancelled the LLMGauge request or externally managed runtime operation. |

Transport errors and model failures are not interchangeable. An HTTP error does
not by itself prove model admission failed. A process disappearing during a
request is a request-execution failure unless separate startup evidence proves a
new admission failure.

The observed Gemma NVFP4 event is
`model_admission_load_failure` with a resource/VRAM-fit classification on the
tested 12 GB configuration. Since architecture recognition and native kernel
selection succeeded before allocation failed, classifying it as
`unsupported_capability` or a generic unsupported-model failure would contradict
the evidence.

## Deferred scope

The following remain explicitly deferred:

- production Python, CLI, schema, validator, report, and public-export changes;
- dependency and lockfile changes;
- vLLM installation or model download behavior;
- automatic server lifecycle or recovery;
- multimodal input and media provenance;
- streaming and time to first token;
- remote endpoints, cloud services, TLS policy, authentication, and arbitrary
  headers;
- LoRA, speculative decoding, batching, concurrent load tests, distributed
  inference, and scheduler benchmarking;
- automatic hardware tuning or CPU-offload selection;
- generalized backend plugins; and
- release metadata or release work.

## Follow-on milestones

The proposed sequence is accepted with one qualification: dependency admission
is a decision, not a presumed outcome.

1. **HTTP transport assessment and dependency admission, if needed.** Prove
   whether the Python standard library can satisfy loopback validation, proxy
   bypass, redirect rejection, bounded connect/request timeouts, cancellation,
   bounded JSON handling, and deterministic tests. Add a lightweight dependency
   only if a documented gap remains. This is the exact recommended next
   milestone.
2. **Externally managed vLLM adapter.** Implement the text-only, single-request,
   non-streaming boundary plus additive schema, validator, report, and
   public-export support. Do not manage the server.
3. **Fitting-model integration smoke.** Against an operator-reviewed local
   server and a checkpoint known to fit, verify admission evidence, one request,
   artifacts, metrics, failure handling, and public sanitization. This is the
   first real-runtime proof; unit tests alone do not establish integration.
4. **Cross-runtime comparison methodology.** Define which prompts, token budgets,
   templates, sampling settings, metrics, and server-state disclosures permit a
   bounded llama.cpp/vLLM comparison. Do not assume token or throughput
   equivalence.
5. **Gemma NVFP4 CPU-offload audit.** Keep this a separate investigation with
   preserved startup evidence. It may evaluate whether CPU offload changes the
   12 GB fit result, but it must not gate the generic adapter or reinterpret the
   original full-GPU failure.

The fifth milestone is intentionally separate from backend implementation and
may be scheduled independently after the contract. Its outcome is a fit result
for one checkpoint, runtime build, configuration, and device—not a general model
support claim.

## Consequences

This boundary keeps LLMGauge as the evaluation and evidence layer while making a
persistent local runtime possible. It sacrifices automatic convenience and
broad endpoint support to preserve lifecycle truth, privacy, deterministic
request semantics, and artifact compatibility. Cross-runtime reports will have
more explicit unknown and non-equivalent fields; that is preferable to false
precision.
