# EXL2 / EXL3 Representation and ExLlama Runtime Qualification (M2.5)

Status: accepted qualification contract. Architecture/qualification only —
this document implements no runtime behavior and changes no frozen schema.

## 1. Scope

This milestone qualifies EXL2, EXL3, ExLlamaV2, ExLlamaV3, and TabbyAPI
against the accepted first-class multi-runtime architecture
([FIRST_CLASS_RUNTIME_ARCHITECTURE.md](FIRST_CLASS_RUNTIME_ARCHITECTURE.md))
and the frozen M2 directory-provenance contract
(`llmgauge.checkpoint_directory_manifest.v0`). It answers, with primary-source
evidence:

- how EXL2/EXL3 checkpoints map onto accepted model source kinds;
- whether M2 manifest v0 captures their inference-material file sets;
- how model-format identity is represented and detected fail-closed;
- the ExLlamaV2 and ExLlamaV3 runtime dispositions and TabbyAPI's role;
- lifecycle, runtime-identity, evidence, and cross-runtime identity rules;
- the revised ordered multi-runtime program and exactly one next milestone.

Out of scope: runtime implementation, manifest implementation, dependency
admission, model download, runtime execution, benchmarking, release work.

## 2. Terminology (normative — layers never collapse)

| Layer | Values | Answers |
|---|---|---|
| Model source kind | `gguf_file`, `checkpoint_directory`, `served_model_reference` | Where/how is the model stored locally? |
| Model format (representation/encoding) | `hf_transformers`, `exl2`, `exl3`, `awq`, `gptq`, `gguf`, `unknown`, … | What on-disk encoding are the checkpoint weights? |
| Inference runtime | `llama.cpp`, `vllm`, `sglang`, `exllamav2`, `exllamav3` | What engine executes the model? |
| Server / transport implementation | `tabbyapi`, `openai_http`, process stdio | What surface does LLMGauge speak to? |

Rules:

- EXL2 and EXL3 are **model formats**, not runtimes. "EXL3 runtime" is
  prohibited language; ExLlamaV3 is the runtime.
- ExLlama is not a quantization format. ExLlamaV2/ExLlamaV3 are runtimes.
- TabbyAPI is a server implementation, never a model format and never a
  backend id in LLMGauge.
- Model quantization (checkpoint weights) and runtime cache quantization
  (KV cache configuration) are different facts and stay separate everywhere.

## 3. Inspected upstream identities (2026-09-03)

| Project | Ref | Commit/date | Role |
|---|---|---|---|
| turboderp-org/exllamav2 | `master` | `7dc12af3a81f34ac3f27cd7602ed539b638933ca` (last commit 2026-03-04); release `v0.3.2` (2025-07-13) | Archived EXL2 runtime authority |
| turboderp-org/exllamav3 | tag `v1.4.6` | `499890c75d20d8e7c9d061f37189ae611a5c9f0b` (published 2026-09-02) | Current EXL3 runtime authority |
| theroyallab/tabbyAPI | `main` | `13a8079eabb1761d6722c9fe9270d3a450803d50`; pins exllamav3 v1.4.6 wheels | Official ExLlamaV3 server |
| theroyallab/tabbyAPI | `exl2-checkpoint` | `79126f904c2e00aece026b36bb70bbb87e4892b2` (2026-06-27) | Preserved ExLlamaV2 serving path |

Load-bearing upstream statements verified from these refs:

- ExLlamaV2 README (master): "**This project is archived for now**.
  Development continues on ExLlamaV3."
- TabbyAPI README (main): "ExLlamaV2 models are no longer supported in the
  `main` branch. The last commit with Exllamav2 support is preserved on the
  `exl2-checkpoint` branch." That branch's README still lists
  "Exl2/GPTQ (deprecated, will be removed in the near future)".
- TabbyAPI main README: supported model types are "Exl3 (Highly recommended)"
  and "FP16/BF16"; TabbyAPI is "the official API backend server for
  ExllamaV3".
- TabbyAPI publishes no GitHub releases; its `pyproject.toml` version is
  `0.0.1` and `/.well-known/serviceinfo` carries no version field. TabbyAPI
  release/version identity is therefore weak upstream and must be captured
  from the running server (git checkout / package metadata), not assumed.

Local read-only inventory (no downloads, no execution): one real EXL3
checkpoint (`models/exl3/Qwen3.8-27B-SC_2.20bpw_H3_V3`, quantization_config
version 1.4.2), an ExLlamaV3 source checkout at exactly `v1.4.6`
(`runtime-tests/exllamav3-e2/src`), a stale `exllamav3` clone at `v0.0.6`,
no local EXL2 checkpoints, no ExLlamaV2 or TabbyAPI checkouts. The local
EXL3 layout independently confirms every file-set finding below.

## 4. EXL2 model-format contract (ExLlamaV2 `master` loader evidence)

**Required to load and run a converted EXL2 model:**

| File | Evidence |
|---|---|
| `config.json` | `ExLlamaV2Config` loads it unconditionally; architecture, `quantization_config->checkpoint_format` (GPTQ v2 offset) read from it |
| root-level `*.safetensors` (≥1) | loader globs `os.path.join(model_dir, "*.safetensors")`, raises if none; every tensor is located through that glob |
| `tokenizer.json` | tokenizer raises "Model does not include a tokenizer.json file. SentencePiece-only tokenizers are no longer supported" (since v0.2.3/v0.3.1; `tokenizer.model` is no longer used at all) |

**Optional but consumed when present:** `generation_config.json`,
`tokenizer_config.json` (added-token decoder, special tokens),
`added_tokens.json`, `preprocessor_config.json` (vision checkpoints only).

**Not consumed by the runtime:** `model.safetensors.index.json` (ExLlamaV2
never reads an index — glob only), `quantization_config.json` sidecar
(format evidence is the `config.json` `quantization_config` block written by
the compiler), `chat_template.jinja` (ExLlamaV2 core applies no HF chat
template; serving layers render templates via `transformers`).

**Conversion-only artifacts (must never become model identity):**
working-directory `job.json`/`job_new.json`, `measurement.json`,
`out_tensor/*.safetensors`, `output_temp_*.safetensors` (renamed into final
shards), calibration corpora (`standard_cal_data/*.utf8`). Final inference
shards are `output.safetensors` or `output-NNNNN-of-NNNNN.safetensors` —
still plain root-level `*.safetensors`, so the glob covers them.

**Authoritative format evidence:** `config.json.quantization_config.quant_method
== "exl2"` with `version`, `bits` (target average bpw), `head_bits`,
`calibration{rows,length,dataset}` — written by `conversion/compile.py` when
compiling a full model. Tensor-level signature: EXL2 linear layers store a
`.q_weight` tensor (plus `q_groups`/`head_suffix`/scale tensors), distinct
from GPTQ `.qweight`/`.qzeros`/`.scales` and from plain `.weight`.

## 5. EXL3 model-format contract (ExLlamaV3 `v1.4.6` loader evidence)

**Required to load and run a converted EXL3 model:**

| File | Evidence |
|---|---|
| `config.json` | `model/config.py` opens it unconditionally |
| root-level `*.safetensors` (≥1) | `SafetensorsCollection` globs the directory; required-tensor lookup is by scanned headers |
| `tokenizer.json` | tokenizer builds `HFTokenizer.from_file(<dir>/tokenizer.json)` unconditionally |

**Optional but consumed when present:** `tokenizer_config.json`,
`added_tokens.json`, `generation_config.json` (bonus EOS ids),
`preprocessor_config.json` (vision). Chat-template rendering
(`tokenizer.hf_chat_template`) lazily constructs
`AutoTokenizer.from_pretrained(directory)`, which consumes
`chat_template.jinja` / `tokenizer_config.json` / tokenizer files — so the
template surface is runtime-reachable even though the core loader does not
parse it directly.

**Not consumed by the load path:** `model.safetensors.index.json` (written by
the compiler when sharded, but the runtime globs and scans headers;
`util/add_safetensors_index.py` exists precisely because the index is
auxiliary), `quantization_config.json` sidecar (compiler/`util/
add_quant_config.py` output; the transformers-integration code comments it is
"just a compilation of the headers from each individual .safetensors file" and
uses the `SafetensorsCollection` instead).

**Conditionally required:** `ngram_embedding.safetensors` for PLE/n-gram
models (e.g. Qwen3.8-Flash-Next class). The compiler writes it standalone
into the output directory and deliberately excludes it from the index; the
runtime consumes it through the same directory glob
(`modules/ngram_embedding.py`, `modules/ple.py`). A directory containing it
is still fully covered by a root-glob manifest.

**Conversion-only artifacts:** `work_dir` checkpoints (`ckpt/job.json`,
`ckpt_new/job.json`), `measurement.json`, optimizer inputs, and calibration
traces. A published `cal_trace.safetensors` (present in the local checkpoint)
holds only calibration `input_ids` — a review/publication artifact, never
load-required, never identity.

**Authoritative format evidence:** per-tensor storage signature — EXL3
linear layers store `{key}.trellis` plus `{key}.su/.suh`, `{key}.sv/.svh`,
and `{key}.mul1`/`{key}.mcg` codebook scalars; `modules/linear.py` dispatches
`has_tensor_group(key, [["sv","svh"],["su","suh"],"trellis"]) → exl3`, else
`weight → fp16`. Declared evidence: `config.json.quantization_config` with
`quant_method == "exl3"`, `version` (converter ExLlamaV3 version), `bits`
(final average bpw), `head_bits`, `calibration{rows,cols}`, `out_scales`,
`codebook`, `mtp_bits`, `vision_bits`; the optional
`quantization_config.json` sidecar adds per-module `quant_format`,
`bits_per_weight`, and multiplier fields.

## 6. M2 manifest compatibility audit

Verdict vocabulary:

- `M2_V0_COMPLETE` — every file the runtime requires to load and run the
  format is selected into the canonical manifest by v0 rules; no
  inference-material file is excluded; identity is not diluted by
  conversion-only files.
- `M2_V0_PARTIAL` — the model loads and its manifest is buildable, but at
  least one inference-material or runtime-reachable file is outside the
  manifest, so identity is knowingly incomplete for that format.
- `M2_V0_INCOMPATIBLE` — the format cannot be represented by the
  checkpoint-directory manifest contract at all.

| File/evidence | M2 v0 | EXL2 requirement | EXL3 requirement | Result |
|---|---|---|---|---|
| `config.json` | required | required | required | covered |
| `generation_config.json` | optional | optional-consumed | optional-consumed | covered |
| root `*.safetensors` (no index) | selected when no index | required (glob) | required (glob) | covered |
| index + exactly-referenced shards | selected when index present | not used by runtime | not used by runtime | see finding E1 |
| `quantize_config.json` / `quantization_config.json` / `compression_config.json` | allowlisted sidecars | n/a | sidecar optional (declared quant + tensor-storage evidence) | covered |
| tokenizer allowlist (`tokenizer.json`, `tokenizer.model`, `tokenizer_config.json`, `special_tokens_map.json`, `added_tokens.json`) | optional | `tokenizer.json` required; config/added optional | same | covered |
| chat-template selection (`chat_template.jinja`/`chat_template.json`/embedded) | selected | not runtime-consumed (server-side rendering) | reachable via `AutoTokenizer.from_pretrained` | covered |
| `ngram_embedding.safetensors` | covered only when no index exists | n/a | conditionally required, excluded from index | see finding E2 |
| conversion-only files (`job.json`, `measurement.json`, `cal_trace.*`, `out_tensor/`, `output_temp_*`) | excluded | must be excluded | must be excluded | correct |
| `merges.txt`, `vocab.json`, `preprocessor_config.json` | excluded | not required by V2 text path | not required by V3 text path (vision only) | acceptable; vision is out of scope |

**EXL2_M2_MANIFEST = COMPLETE**

**EXL3_M2_MANIFEST = PARTIAL**

Findings:

- **E1 (EXL2, benign):** EXL2 output shards are named `output*.safetensors`
  and no index is written by the compiler. If a third-party publisher adds an
  index anyway, v0 would select only index-referenced shards — which for a
  correct index is the same set. The runtime ignores the index and globs;
  v0's index-driven selection is a *stricter*, deterministic superset rule
  that never drops a referenced shard. No extension needed.
- **E2 (EXL3, the real gap):** when an EXL3 model is sharded, the compiler
  writes `model.safetensors.index.json`, and v0 then selects *only*
  index-referenced shards. `ngram_embedding.safetensors` is deliberately not
  in the index yet is load-material for PLE models — v0 would omit it and
  still report `available`. Additionally, for any non-PLE sharded EXL3 model
  v0's manifest is *correct* (index shards = glob shards), but it records an
  index the runtime never reads; that is acceptable canonical-selection
  determinism, not a defect. The gap is bounded to: **root-level
  `*.safetensors` files that exist alongside an index are silently excluded
  from identity.** For EXL3 that set can contain a required file.
- **E3:** v0's `partial`-on-`auto_map` rule does not fire for EXL2/EXL3
  checkpoints (neither format requires custom code to load under ExLlama);
  no interaction.
- **E4:** the local real EXL3 checkpoint confirms the layout matrix:
  index present, 2 referenced shards, extra unreferenced
  `cal_trace.safetensors` (correctly excluded), `quantization_config.json`
  (allowlisted), `tokenizer.json`/`tokenizer_config.json`/`chat_template.jinja`
  (covered), no ngram table (so this specific model is v0-complete; the
  verdict is PARTIAL because the class of models with `ngram_embedding
  .safetensors` is not).

**Versioned extension decision (not implemented here):** M2 v0 stays frozen.
A future `llmgauge.checkpoint_directory_manifest.v1` must change weight-file
selection from "index-referenced shards, else root glob" to
**"union of index-referenced shards and root-level `*.safetensors`"** (root
non-recursive glob only; still never recursive). This is a breaking canonical
-selection change (previously excluded root shards enter the manifest), so it
requires a new schema id, new fingerprint semantics, and its own milestone.
v0 results remain valid and verifiable under v0 rules; v1 is selected only
for new collections. No format-specific allowlist expansion is admitted:
the union rule is format-neutral and closes E2 for every safetensors runtime
that globs (which includes both ExLlama loaders).

## 7. Model-format identity decision

`source_kind = checkpoint_directory` is necessary but **not sufficient**: a
BF16 HF checkpoint, an EXL2 checkpoint, an EXL3 checkpoint, and an AWQ/GPTQ
checkpoint share the directory source shape while being materially different
model representations.

Decision: add one new concept, **`model_format`** (field name
`model_format`, values lowercase snake tokens). Rejected alternatives:

- `checkpoint_format` — collides with ExLlamaV2's internal GPTQ
  `quantization_config.checkpoint_format` (`gptq_v2`) field; reusing the name
  would confuse declared-quantization evidence with format identity.
- `representation_format` — redundant with the already-named layer "model
  representation" in §4.1 of the architecture contract.
- extending `quant` (free-text profile label) — `quant` is a display label,
  not structured evidence, and must not gain semantics.
- new source kinds (`exl2_directory`, `exl3_directory`) — rejected: EXL2/EXL3
  checkpoints *are* checkpoint directories under the accepted definition;
  only the encoding differs.

`model_format` answers "what on-disk model representation/encoding is this
checkpoint?" without duplicating source kind or runtime. It is
**observation-derived evidence, never user-asserted truth**: the collector
proposes it from the detection rules in §8; the profile may carry an optional
user expectation used only for mismatch rejection.

Scope discipline: this qualification admits exactly the values needed to
represent EXL honestly — `exl2`, `exl3`, `hf_transformers`, `unknown` — plus
the rule that later formats (`awq`, `gptq`, `compressed_tensors`, …) enter
additively when their own qualification lands. No universal taxonomy is
established now.

Placement: `model_format` belongs in the checkpoint-provenance record
(alongside `checkpoint_quantization`) and in the fingerprint model identity
for directory provenance, because it is a property of the checkpoint bytes,
not of the runtime. It is a new *optional* field for existing v6 payloads —
but changing v6 payload content is frozen-version territory, so its
introduction rides the same future milestone that adopts manifest v1 and a
`run_fingerprint.v7` (see §16).

## 8. EXL2/EXL3 detection contract (fail-closed)

Prohibited evidence (never sufficient, never used at all): directory name,
filename, `-exl2`/`-exl3` suffixes, bpw in a name, file size, model card,
README, publication receipts (`crc32.txt` etc.).

**EXL2 detection (all steps required; any failure → not exl2):**

1. `config.json` parses and
   `quantization_config.quant_method == "exl2"` (string, exact, lowercase
   compare after trim). Record `{file: "config.json", field:
   "quantization_config.quant_method", value: "exl2"}` as source-labelled
   evidence, plus `version`, `bits`, `head_bits` when present.
2. Corroboration from hashed weight evidence: at least one root
   `*.safetensors` header contains a linear-layer tensor key ending in
   `.q_weight` (the EXL2 storage signature). Header inspection is metadata
   only (first bounded header read per file, size-capped like existing
   parsed-metadata limits).
3. Conflict rule: if `quantization_config` declares another method while
   `.q_weight` tensors dominate, or vice versa → `model_format = unknown`
   with a `conflict` warning; never guess.

**EXL3 detection (all steps required; any failure → not exl3):**

1. `config.json` parses and
   `quantization_config.quant_method == "exl3"`. Record the same
   source-labelled triple plus `version`, `bits`, `head_bits`, `codebook`,
   `out_scales` when present.
2. Corroboration: at least one root `*.safetensors` header contains a tensor
   key ending in `.trellis` (the EXL3 trellis-codebook signature; proven
   authoritative by `modules/linear.py` dispatch).
3. Optional sidecar agreement: when `quantization_config.json` is present,
   its `quant_method` must agree; disagreement → `conflict` → `unknown`.
4. Same conflict rule as EXL2.

**No defensible surface → `model_format = "unknown"`.** Unknown-format
checkpoints remain valid `checkpoint_directory` identities under current v0
semantics; format-specific *execution* gating (which runtime may load them)
is enforced by the runtime adapter, which fails closed on `unknown`.
`hf_transformers` is detected only negatively for now: no admitted
quantization/format signature present and plain `.weight` tensors — recorded
as `hf_transformers` with `declared quantization = absent`, mirroring the
existing M2 rule that unquantized models are not `partial`.

## 9. Quantization / bitrate identity

Separate facts, separate fields:

| Concept | Field home | EXL evidence |
|---|---|---|
| Model format | `model_format` | `exl2` / `exl3` per §8 |
| Requested bpw | profile/runtime setting (never checkpoint identity) | user/profile value |
| Checkpoint-declared target bpw | `checkpoint_quantization` extension: `bits` | `quantization_config.bits` (compiler: EXL2 `bits` is the *target* average; EXL3 stores `final_bits`, the achieved average) |
| Head-layer bpw | same record | `head_bits` |
| Per-module mixed precision | sidecar-derived, bounded | EXL3 `quantization_config.json.tensor_storage[*].bits_per_weight` (per-module map; record count + min/max + full map only in private evidence) |
| Effective average bpw | derived, labeled | DERIVABLE: Σ(n_bytes)·8 / Σ(weights) from the sidecar tensor-storage map, or from safetensors headers; label `derived_from_manifest`; `unknown` when no sidecar and header derivation is not implemented |
| Quantization algorithm | `checkpoint_quantization.algorithm` | EXL2: GPTQ-error-based mixed-bit (declared); EXL3: QTIP-derived trellis codebook (declared `codebook: mul1/mcg/3inst`) |
| EXL format version | `model_format_version` | `quantization_config.version` = converter library version (EXL2 `0.3.x`, EXL3 `1.4.x`) — converter identity, not runtime identity |
| Runtime cache quantization | runtime evidence only (`exllama_v3.cache_mode`) | Q4/Q6/Q8/FP16 KV-cache settings; **never** model format, never checkpoint fingerprint |

Rules:

- Do not flatten identity into `quant: "EXL3 4.0bpw"`. The free-text `quant`
  profile label may display that string; structured evidence lives in
  `model_format` + `checkpoint_quantization`.
- If exact average bitrate cannot be read from authoritative hashed model
  metadata, record `effective_bpw: unknown`. Never parse bpw from a
  directory name (the local `..._2.20bpw_...` directory declares `bits: 2.2`
  in config — the declaration is the evidence, the name is not).
- EXL2 `bits` is a target; EXL3 `bits` is the achieved final average
  (`final_bits` at compile). Record provenance of which semantic applies via
  the format-version field. Mixed per-layer precision is the norm for both;
  a single scalar never claims uniform quantization.

## 10. ExLlamaV2 runtime disposition

Upstream status (observed): archived; last master commit 2026-03-04; final
release v0.3.2 (2025-07-13) with prebuilt wheels pinned to CUDA 11.8/12.1 and
PyTorch 2.3/2.4; README points to ExLlamaV3. No maintained OpenAI server on
`main` of TabbyAPI; the preserved path is TabbyAPI `exl2-checkpoint` branch
@ `79126f9` (2026-06-27), which the branch itself labels as a checkpoint,
with Exl2/GPTQ marked "deprecated, will be removed in the near future".

Capabilities relevant to LLMGauge (observed from `master` source): dynamic
generator with batching, streaming async jobs, speculative decoding,
`time_enqueued`/`time_prefill`/`time_generate` per-job timings, autosplit
multi-GPU (`--gpu_split`), Q4 cache, LoRA, EXL2 + GPTQ loading, tokenizer
requiring `tokenizer.json`.

**Disposition: `COMPATIBILITY_TARGET` — first-class EXL2 *representation*
support through a pinned legacy *runtime* path.** Concretely:

- EXL2 model-format identity, detection, provenance, validation, report, and
  export treatment are full first-class product behavior (the format is not
  demoted; the user's EXL2 models are supported).
- Execution targets `exllamav2` pinned to the archived release line (v0.3.2
  wheel family) via TabbyAPI `exl2-checkpoint` as the *only* admitted serving
  path — no direct-library import of an archived CUDA/torch-pinned extension
  into LLMGauge's environment.
- "Full support" for an archived runtime means: complete identity/provenance,
  bounded managed/external lifecycle, honest evidence, and a
  **version-qualification policy frozen at the archived version** — not
  ongoing compatibility promises. Every ExLlamaV2 result records the exact
  pinned versions; upstream drift is impossible by definition, so
  reproducibility is *stronger*, not weaker, than for moving targets.
- ExLlamaV2 is excluded from the principal-runtime parity obligations of
  §13 (fit-ladder design, workflow parity beyond run/batch) with recorded
  reason; it is a compatibility lane, not a strategic line.

## 11. ExLlamaV3 first-class target

Observed current capability (v1.4.6): EXL3 and native FP16/BF16 safetensors
checkpoints; very large architecture matrix (~80 architecture modules);
tensor parallel (`--tensor_parallel`), expert parallel / MoE CPU offload and
per-layer expert split, autosplit layer distribution; dynamic/continuous
batching with paged attention; speculative decoding (draft model + n-gram
draft); quantized KV cache (fp16/quant/MLA/DSA/QSA/recurrent cache families);
LoRA; multimodal (vision) — **recorded as future capability only, explicitly
out of scope for this text-evaluation milestone**; streaming async
generator; per-job `time_enqueued`/`time_prefill`/`time_generate`;
`SafetensorsCollection` load metrics (first-open time, per-file header
scan); OpenAI-compatible serving via official TabbyAPI.

**Disposition: ExLlamaV3 / EXL3 is accepted as a principal first-class
runtime family** alongside llama.cpp, vLLM, and SGLang (§15). First-class
target shape:

1. Model identity: `checkpoint_directory` + `model_format` (`exl3` or
   `hf_transformers` for native FP16/BF16), manifest v1 selection (§6),
   tokenizer/template identity, three-way quantization.
2. Execution: text-only normalized evaluation; prompt and ordered-messages
   input forms; exact generation settings mapped to TabbyAPI request fields;
   raw/cleaned/failure preservation.
3. Lifecycle: managed-local first-class (launch TabbyAPI from structured
   argv, readiness via `/health`, admission via `/v1/model` +
   `/v1/models`, bounded shutdown, preserved logs); external-server mode
   permanently supported with §5.3 evidence ceiling.
4. Evidence: runtime identity per §12; namespaced `exllama_v3.*` evidence
   (cache mode, device split, draft config, job timings); no merged
   cross-runtime metric fictions.
5. Product workflow: validate/report/score/compare/export consume
   ExLlamaV3 results under existing claim boundaries.
6. Automation: run-batch and context ladder via capability flags;
   fit-ladder server semantics deferred with reason (same disposition as
   vLLM until designed).
7. Security: loopback-only default; TabbyAPI api-key/admin-key policy
   explicit; no telemetry; no network beyond admitted endpoint class.
8. Reproducibility: full runtime-identity capture (§12), launch config,
   manifest fingerprint, fingerprint eligibility.

## 12. Runtime identity requirements

A result is identified by (all recorded, none inferred):

- `runtime.family`: `exllamav2` | `exllamav3` — **distinct backend ids**, not
  one "exllama" backend with a version field. Evidence: different repos,
  incompatible formats (V3 cannot load EXL2: no `.q_weight` loader; V2
  cannot load EXL3), different servers/branches, different maintenance
  status. They share one *adapter family* (TabbyAPI transport, config
  surfaces) but are separate runtime identities.
- exact library version + source: `exllamav3.__version__` /
  `exllamav2.__version__` as reported by the server (TabbyAPI ModelCard /
  server logs / package metadata), labeled `server_reported`;
- wheel build tag (CUDA + PyTorch pinning, e.g. `1.4.6+cu128.torch2.10.0`)
  when observable — the extension ABI makes this part of runtime identity;
- server implementation/version: TabbyAPI commit-ish (no release tags
  exist upstream); `unknown` is honest when unobservable;
- model format + checkpoint identity (§7–§9);
- launch/configuration evidence: structured argv in managed mode,
  operator-supplied or `unknown` in external mode;
- device placement/split, cache mode, speculative configuration — runtime
  settings, recorded in runtime evidence, **never** in the checkpoint
  fingerprint (they do not alter checkpoint bytes).

Package version alone never claims full runtime state; each field carries its
own provenance class.

## 13. TabbyAPI role and lifecycle decision

**Role: server/transport implementation, not a runtime backend id.** LLMGauge
models `backend: exllamav3` (or `exllamav2`) with `server: tabbyapi` as the
transport/lifecycle detail — mirroring how `llama.cpp` owns its stdio server
and vLLM owns its OpenAI server. `backend: tabbyapi` is rejected: it would
hide the runtime identity that the acceptance contract requires.

Lifecycle comparison (evidence-backed):

| Mode | Assessment |
|---|---|
| A. Direct Python library import | **Rejected.** ExLlamaV2/V3 are compiled CUDA/torch-extension packages whose wheel ABI is pinned to exact CUDA+PyTorch combinations (upstream READMEs; TabbyAPI pins per-CUDA/torch wheels). Importing them would couple LLMGauge's own environment to CUDA/PyTorch the way vLLM would — LLMGauge deliberately avoids installing vLLM; the same dependency-isolation, crash-containment, and reproducibility arguments apply unchanged. |
| B. Managed server process | **First-class target.** LLMGauge launches TabbyAPI (operator-installed, path from bounded config; structured argv; never a shell string; never installs anything) and speaks loopback HTTP. Full §5.2 lifecycle: readiness deadline, admission verification, shutdown, preserved logs, honest exit classification. |
| C. External server | **Permanently supported** with the §5.3 evidence ceiling (no launch config, no load time, startup-scope provenance `operator_supplied`/`unknown`). This is the natural first implementation slice, exactly as vLLM was introduced. |

## 14. Runtime evidence matrix

| Evidence | ExLlamaV2 | ExLlamaV3 | Boundary / qualification |
|---|---|---|---|
| request wall time | DIRECTLY OBSERVABLE (client-side) | DIRECTLY OBSERVABLE (client-side) | existing per-request boundary |
| streaming TTFT (client-side SSE first-token) | DERIVABLE WITH BOUNDED METHOD | DERIVABLE WITH BOUNDED METHOD | requires its own exact-version qualification + preserved SSE evidence before admission (vLLM precedent) |
| native prefill time | DIRECTLY OBSERVABLE (`time_prefill` in job state) | DIRECTLY OBSERVABLE (`time_prefill`) | runtime-native, namespaced; server-side clock; qualification required before neutral-metric promotion |
| native generate time | DIRECTLY OBSERVABLE (`time_generate`) | DIRECTLY OBSERVABLE | same |
| queue time | DIRECTLY OBSERVABLE (`time_enqueued`) | DIRECTLY OBSERVABLE | batching makes it workload-dependent; disclose |
| prompt/generated token counts | DERIVABLE (tokenizer / usage fields) | DERIVABLE | usage-token source labeling per existing rules |
| decode throughput | DERIVABLE WITH BOUNDED METHOD (tokens ÷ generate time) | same | derived, labeled; never equal to llama.cpp `slot_print_timing` semantics |
| prefill throughput | DERIVABLE WITH BOUNDED METHOD | same | derived |
| load/admission time | VERSION-QUALIFICATION REQUIRED (server logs) | VERSION-QUALIFICATION REQUIRED (server logs; `SafetensorsCollection.metrics` not exposed via HTTP) | startup scope; never folded into request time |
| VRAM | DIRECTLY OBSERVABLE (external NVIDIA sampler) | same | existing sampler boundaries; per-device split disclosed |
| device placement / split | DIRECTLY OBSERVABLE (launch config + logs) | DIRECTLY OBSERVABLE | config evidence, not measurement, unless sampled |
| cache state (mode/size) | DIRECTLY OBSERVABLE (`/props`, ModelCard) | DIRECTLY OBSERVABLE (ModelCard `cache_mode`, `cache_size`) | configuration evidence |
| batching/queueing effects | DERIVABLE (slot stats via server) | DERIVABLE | TabbyAPI surfaces; version-qualified |
| runtime-native timings via HTTP | UNAVAILABLE (TabbyAPI exposes usage, not exllama job state — verify at implementation) | UNAVAILABLE (same) | if unexposed, client-side + log parsing are the only channels; classify honestly |

No metric is promised because a runtime "prints something"; each row earns
admission through the existing exact-version qualification discipline.

## 15. Cross-runtime identity and conversion lineage

Existing rules apply unchanged: a BF16 HF checkpoint, its EXL3 derivative,
and a GGUF Q4 derivative are **not** the same checkpoint identity. Expected
tier between an EXL derivative and its source: `same_family_declared` at
best, unless conversion lineage is recorded as evidence.

**Conversion lineage: accepted as optional high-value provenance, defined
here, implemented later.** A future `llmgauge.conversion_lineage.v0` record
may attach to a checkpoint provenance record and carry: source checkpoint
manifest fingerprint, converter identity/version (EXL2/EXL3
`quantization_config.version` is already converter evidence), target format,
requested bitrate, bounded conversion options, and the resulting checkpoint
manifest fingerprint. Provenance class rules apply: `operator_declared`
unless LLMGauge observed the conversion itself. Lineage upgrades a
comparison to `conversion_lineage` tier — it never claims "same weights"
(quantization is lossy) and is never required to load or score a
pre-existing downloaded EXL model.

## 16. First-class program and roadmap decisions

Principal runtime families (updated):

1. `llama.cpp` / GGUF — first-class, default (unchanged).
2. vLLM / native checkpoints — first-class target (unchanged).
3. SGLang / native checkpoints — first-class target (unchanged).
4. **ExLlamaV3 / EXL3 + supported native formats — first-class target
   (added).**
5. ExLlamaV2 / EXL2 — **compatibility lane** (§10): full representation
   identity, pinned legacy execution, excluded from parity obligations.

Manifest decision: option **B** — one versioned extension
(`checkpoint_directory_manifest.v1`, union weight-file selection, §6) is
required before EXL3 execution can claim complete identity. v0 remains frozen
and valid.

Program re-evaluation (evidence-backed, not mechanical preservation):

- M2 v0 suffices for EXL2 immediately and for non-PLE EXL3 models; the v1
  union rule is small, format-neutral, and unblocks the whole EXL line plus
  improves correctness for any glob-loading runtime.
- ExLlamaV3 is more relevant to WumboLabs consumer-GPU evaluation than
  SGLang (current local evidence: an active v1.4.6 e2 test environment and a
  real 27B EXL3 checkpoint; no SGLang deployment beyond scratch tests).
- vLLM identity (M3) consumes only M2 v0 and is already in flight
  architecturally; delaying it would idle the accepted vLLM track.

Revised ordered program:

| # | Milestone | Status |
|---|---|---|
| M1 | runtime-neutral model representation/profile contract | done |
| M2 | directory-model provenance + fingerprint eligibility (v0) | done |
| M2.5 | EXL/ExLlama qualification (this document) | done |
| M3 | vLLM first-class model identity | next |
| M4 | vLLM managed-local lifecycle | planned |
| M5 | vLLM workflow parity | planned |
| M8 | EXL manifest v1 + `model_format` identity (provenance extension, detection, fingerprint v7) | inserted before M6 |
| M9 | ExLlamaV3 external-server adapter (TabbyAPI transport, identity, evidence) | inserted before M7 |
| M10 | ExLlamaV3 managed lifecycle + workflow parity | planned |
| M11 | EXL2/ExLlamaV2 compatibility lane (pinned TabbyAPI `exl2-checkpoint`) | planned after M10 |
| M6 | shared server transport extraction + SGLang external adapter | resequenced after the EXL block (M8–M11) |
| M7 | SGLang lifecycle/parity + cross-runtime identity hardening | last; hardening covers four families |

Rationale: M8–M11 slot between the vLLM block and the SGLang block because
ExLlama reuses the vLLM-proven adapter shape (managed server + OpenAI
transport), the shared-transport extraction (M6) is stronger with TabbyAPI as
a second consumer, and EXL2 compatibility (M11) lands after the V3 line
proves the family's evidence machinery. The anti-big-bang rule holds: every
entry is one bounded runtime slice consuming already-accepted seams.

Transport sequencing: M9 builds the ExLlamaV3 adapter against the existing
`runners/vllm_http.py` primitives (internal reuse, no extraction), which is
exactly the evidence the §6 admission rule requires; M6 then performs the
behavior-preserving shared-transport extraction once three server adapters
(vLLM, ExLlamaV3, SGLang-to-be) have proven what is genuinely common.

## 17. Selected next implementation milestone

**M3 — vLLM first-class model identity** (unchanged selection, reconfirmed
against the EXL evidence). It remains the only milestone that everything else
(vLLM parity, shared transport, and by extension the ExLlama adapter family
that reuses the same seams) consumes first, it is implementation-ready today,
and nothing in this qualification blocks it. M8 (manifest v1 +
`model_format`) is the first EXL implementation milestone and enters the
queue immediately after the vLLM block, not before M3, because M3 does not
depend on it.

## 18. Explicit answers

1. EXL2 and EXL3 are both `checkpoint_directory` source-kind models. ✔
2. Yes — a separate `model_format` discriminator is required (§7).
3. M2 v0 captures every EXL2 inference-material file. ✔
4. M2 v0 does **not** capture `ngram_embedding.safetensors` for sharded EXL3
   (§6 E2); non-PLE EXL3 is covered.
5. `llmgauge.checkpoint_directory_manifest.v1`: union of index-referenced
   shards and root-level `*.safetensors` (§6).
6. EXL2: `config.json.quantization_config.quant_method == "exl2"` +
   `.q_weight` tensor-signature corroboration (§8).
7. EXL3: `quant_method == "exl3"` + `.trellis` tensor-signature
   corroboration (§8).
8. Bitrate recorded as structured checkpoint-declared evidence (`bits`,
   `head_bits`, per-module map, derived effective bpw), never from names
   (§9).
9. ExLlamaV2 and ExLlamaV3 are distinct runtime identities/backends sharing
   one adapter family (§12).
10. TabbyAPI is the server/transport implementation for both ExLlama
    generations, official for V3 (§13).
11. First-class ExLlama support = the eight-category contract of §11.
12. Yes — ExLlamaV3/EXL3 joins the principal runtime list (§16).
13. EXL2/ExLlamaV2 retains a compatibility lane with full representation
    identity and pinned legacy execution (§10).
14. EXL work enters after the vLLM block, before SGLang resequencing
    (§16); next milestone stays M3 (§17).
