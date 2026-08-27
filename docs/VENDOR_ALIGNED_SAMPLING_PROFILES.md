# Vendor-aligned reasoning and sampling profiles

Status: **accepted content qualification** for the first shipped
`vendor_aligned` builtins. This document owns source provenance and
requalification. Runtime artifacts retain only the closed profile identity
defined in [REASONING_SAMPLING_PROFILE_CONTRACT.md](REASONING_SAMPLING_PROFILE_CONTRACT.md).

Accessed/qualified: **2026-08-26**.

## Purpose

Record how LLMGauge may declare that a named profile **reproduces a
vendor/model-family documented generation configuration** as requested
controls, without claiming quality, endorsement, or observed reasoning.

## Claim boundary

A `vendor_aligned` profile is requested/resolved provenance only.

It does **not** prove:

- vendor endorsement of LLMGauge;
- that reasoning, thinking, or a chat template occurred;
- that a runtime honored vendor-internal serving;
- equivalent quality to vendor-hosted inference;
- that unspecified sampler fields matched a vendor stack.

Allowed wording: “derived from documented vendor settings for \<scope\>.”
Forbidden wording: vendor-approved, official vendor profile, best/optimal
settings, “compatible” unless that word has a separate accepted meaning.

## Qualification methodology

Preferred evidence order:

1. official vendor/model-family documentation;
2. official vendor GitHub;
3. official vendor-owned Hugging Face model card;
4. official technical report when it states operational generation settings;
5. vendor-maintained inference examples.

Community blogs, forums, quantizer READMEs, inference-server defaults,
OpenRouter presets, and LLMGauge operator results are not authority.

For every admitted setting (`temperature`, `top_p`, `top_k`, `min_p`,
`seed`, `reasoning_mode`, `reasoning_effort`, `reasoning_budget`) classify:

- **EXPLICITLY SPECIFIED**
- **EXPLICITLY DEFAULT/UNSPECIFIED**
- **NOT ADDRESSED BY SOURCE**
- **NOT APPLICABLE**
- **NOT REPRESENTABLE BY CURRENT LLMGAUGE**

Do not guess omitted values. `null` is an intentional runtime-default
request and is part of content identity. Seed is never invented.

Scope follows the **narrowest justified** family/variant/mode in the source.

Verdicts: **QUALIFIED** (may ship), **PARTIALLY QUALIFIED** (document, do
not ship), **REJECTED** (insufficient, conflicting, or unrepresentable).

## Candidate matrix

| Candidate | Primary source | Explicit controls | Scope clear? | Representable? | Verdict |
|-----------|----------------|-------------------|--------------|----------------|---------|
| Qwen3 thinking | Qwen/Qwen3-8B model card Best Practices (family-wide Qwen3 notes) | temperature 0.6, top_p 0.95, top_k 20, min_p 0; enable_thinking true | Yes: Qwen3 thinking mode | Yes via `reasoning_mode=on` as LLMGauge request, not chat-template proof | QUALIFIED |
| Qwen3 non-thinking | same card | temperature 0.7, top_p 0.8, top_k 20, min_p 0; enable_thinking false | Yes: Qwen3 non-thinking | Yes via `reasoning_mode=off`. Optional `presence_penalty` is not a profile field | QUALIFIED |
| Gemma 4 instruct sampling | Google AI Gemma 4 model card Best Practices | temperature 1.0, top_p 0.95, top_k 64 across use cases | Yes: Gemma 4 standardized sampling; thinking is template tokens | Sampling yes; thinking tokens NOT REPRESENTABLE → `reasoning_mode=default` | QUALIFIED |
| DeepSeek-R1 series | official DeepSeek-R1 model card usage + eval | temperature 0.6 recommended; eval used top_p 0.95 | Yes: R1 series including distill, not V3/V4 | Sampling yes; prompt/`<think>` enforcement NOT REPRESENTABLE → `reasoning_mode=default` | QUALIFIED |
| Llama 3 official generate defaults | meta-llama/llama3 `generation.py` | temperature 0.6, top_p 0.9 code defaults | Llama 3 official stack, not family-wide instruct/reasoning recipe | Partial: code defaults, no seed/top_k recipe, not framed as documented recommendation | REJECTED for v1 |
| Mistral sampling docs | docs.mistral.ai sampling guidance | ranges, not one recipe | API/playground, not one open-weight family recipe | No single coherent control set without guessing | REJECTED |
| DeepSeek V4 | vendor HF cards | temperature/top_p plus thinking_mode/reasoning_effort | Distinct from R1 | thinking_mode / some effort semantics not faithfully mapped without expanding architecture | PARTIALLY QUALIFIED / deferred |
| Gemma 3 | Gemma 3 cards | no equivalent standardized sampling block | Weaker than Gemma 4 | Insufficient explicit recipe | REJECTED for v1 |

## Accepted profiles

Source URLs are documentation, not fingerprint inputs.

### `qwen3-thinking-v1`

- version `1`, kind `vendor_aligned`, source `builtin`
- settings: temperature `0.6`, top_p `0.95`, top_k `20`, min_p `0.0`,
  seed `null`, reasoning_mode `on`, reasoning_effort `null`,
  reasoning_budget `null`
- sources: [Qwen3-8B model card](https://huggingface.co/Qwen/Qwen3-8B)
  (Qwen Team; family Best Practices); consistent with
  [Qwen vLLM thinking examples](https://qwen.readthedocs.io/en/latest/deployment/vllm.html)
- scope: Qwen3 thinking-mode sampling as documented for Qwen3 instruct
  checkpoints (not Qwen2.5, not size-specific)
- mapping: `enable_thinking=True` → LLMGauge `reasoning_mode=on` (request
  only). Chat-template `enable_thinking` is outside this profile.
- omitted: presence_penalty (optional, unrepresentable); seed not specified

### `qwen3-nonthinking-v1`

- version `1`, kind `vendor_aligned`
- settings: temperature `0.7`, top_p `0.8`, top_k `20`, min_p `0.0`,
  seed `null`, reasoning_mode `off`, reasoning_effort `null`,
  reasoning_budget `null`
- sources: same Qwen3-8B Best Practices non-thinking paragraph
- scope: Qwen3 non-thinking mode
- mapping: `enable_thinking=False` → `reasoning_mode=off` (request only)
- omitted: optional presence_penalty; vLLM example max_tokens is not a
  profile field

### `gemma-4-instruct-v1`

- version `1`, kind `vendor_aligned`
- settings: temperature `1.0`, top_p `0.95`, top_k `64`, min_p `null`,
  seed `null`, reasoning_mode `default`, reasoning_effort `null`,
  reasoning_budget `null`
- source: [Gemma 4 model card](https://ai.google.dev/gemma/docs/core/model_card_4)
  (Google DeepMind; Sampling Parameters: use the same triple across use cases)
- scope: Gemma 4 documented sampling for instruct-tuned variants; not
  Gemma 3, not DiffusionGemma
- thinking: `<|think|>` / channel tokens are **NOT REPRESENTABLE**; the
  profile does not request `--reasoning`

### `deepseek-r1-v1`

- version `1`, kind `vendor_aligned`
- settings: temperature `0.6`, top_p `0.95`, top_k `null`, min_p `null`,
  seed `null`, reasoning_mode `default`, reasoning_effort `null`,
  reasoning_budget `null`
- source: [DeepSeek-R1 model card](https://huggingface.co/deepseek-ai/DeepSeek-R1)
  (DeepSeek-AI). Usage recommendation: temperature 0.5–0.7, 0.6 preferred.
  Evaluation sampling: temperature 0.6 and top_p 0.95
- scope: DeepSeek-R1 series including distill checkpoints named in that card;
  not DeepSeek-V3/V4
- omitted: system-prompt and forced `<think>` prefix (prompt/template, not
  sampler). `reasoning_mode=default` avoids implying a llama.cpp reasoning
  flag equals R1 CoT

Content hashes are computed from canonical `settings` only. Recompute with
`resolve_sampling_profile` rather than copying volatile prose into identity.

## Rejected / deferred

- **Llama 3 generate defaults:** official code defaults exist, but they are
  inference-stack defaults, not a cited family recipe with closed optional
  fields. Need an instruct/reasoning document that states operational
  sampling independently of example-function defaults.
- **Mistral:** range guidance, not one recipe.
- **Gemma 3:** no equivalent standardized sampling block.
- **DeepSeek V4:** thinking_mode / effort fields need a faithful mapping
  milestone if LLMGauge later represents them.
- **Qwen2.5 / other families:** not researched as QUALIFIED in this slice.

## Versioning and requalification

Material setting changes require a new `profile_version` (or new ID if
scope changes). Do not mutate ID+version in place.

Requalify when:

- the cited vendor document changes recommended sampling;
- the source URL disappears or is replaced;
- the model-family generation splits (new thinking protocol);
- LLMGauge adds a sampler field that was previously unrepresentable and
  material to the recipe (for example presence_penalty).

Runtime and tests stay offline. This document is the source-regression
contract; CI must not scrape vendor websites.

## User selection

```text
uv run llmgauge profiles list
uv run llmgauge profiles show qwen3-thinking-v1
uv run llmgauge run --sampling-profile qwen3-thinking-v1 --dry-run ...
```

The discovery commands read the shipped built-in profile registry directly.
Unknown IDs fail closed. There is no remote catalog.
