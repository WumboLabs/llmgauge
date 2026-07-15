# Gemma 4 12B NVFP4 CPU-Offload Evidence

**Status:** Completed investigation evidence
**Recorded:** 2026-07-15
**Scope:** One checkpoint, one local model copy, one vLLM environment, one RTX 5070 host, and one controlled launch attempt
**Related:** [vLLM runtime contract](VLLM_RUNTIME_CONTRACT.md), [vLLM live-smoke evidence](VLLM_LIVE_SMOKE_EVIDENCE.md), [roadmap](ROADMAP.md)

## Purpose

This record documents whether one local Gemma 4 12B NVFP4 checkpoint could reach API readiness with requested vLLM CPU weight offload on the disclosed host. It records model admission, runtime format recognition, the observed CUDA out-of-memory boundary, resource samples, and cleanup.

The result is `not_viable` for this specific checkpoint copy, vLLM environment, launch configuration, and host. The checkpoint did not reach ready state, no bounded request completed, and the requested CPU offload produced no evidence of successful offloaded admission.

This is startup-failure evidence. It is not an inference-quality evaluation, throughput measurement, generalized Gemma NVFP4 compatibility statement, or generalized statement about vLLM CPU offload.

## Audit subject

| Field | Observed or declared value |
| --- | --- |
| Checkpoint identifier | `unsloth/gemma-4-12b-it-NVFP4` |
| Declared base | `google/gemma-4-12B-it` |
| Immutable checkpoint revision | Unavailable from the local copy |
| Runtime architecture | `Gemma4UnifiedForConditionalGeneration` |
| Python | `3.12.13` |
| vLLM | `0.25.1` |
| PyTorch | `2.11.0+cu130` |
| CUDA runtime | `13.0` |
| Transformers | `5.13.1` |
| compressed-tensors | `0.17.0` |
| Runtime dtype | `torch.bfloat16` |
| Runtime quantization | `compressed-tensors` |
| Attention backend | `TRITON_ATTN` |
| Declared maximum context | 262,144 tokens |
| Audit context | 8,192 tokens |
| Requested served-model alias | `gemma4-12b-nvfp4-cpu-offload-audit` |

The local model card identifies the checkpoint and declared base, but the local copy does not preserve an immutable revision identifier. The model identifier and local directory name therefore do not establish an exact upstream revision.

## Host disclosure

| Field | Observed value |
| --- | --- |
| GPU | NVIDIA GeForce RTX 5070 |
| Reported total VRAM | 12,227 MiB |
| Host RAM | Approximately 32.7 GB |
| Clean display-stack GPU use | Approximately 946 MiB |
| Monitoring baseline | Approximately 925 MiB |

No unrelated compute workload was observed before launch. These are one-host observations, not a hardware-class result.

## Quantization verification

NVFP4 recognition was not inferred from the checkpoint name alone.

The local model configuration declared a mixed compressed-tensors format:

- FP8 attention projections;
- NVFP4-packed MLP weights and activations;
- NVFP4 group size 16; and
- an unquantized language-model head.

During startup, vLLM reported:

- `CutlassFP8ScaledMMLinearKernel for CompressedTensorsW8A8Fp8`; and
- `FlashInferCutlassNvFp4LinearKernel for NVFP4 GEMM`.

These configuration declarations and runtime kernel markers verify recognition of the mixed FP8/NVFP4 format for applicable layers. Kernel selection does not prove successful full-model admission, completed weight loading, or functional inference.

## Controlled launch settings

The audit used one conservative, sanitized launch configuration:

| Setting | Value |
| --- | --- |
| Bind address | IPv4 loopback only |
| Port | 8013 |
| Served-model alias | `gemma4-12b-nvfp4-cpu-offload-audit` |
| Maximum model length | 8,192 |
| Maximum sequences | 1 |
| GPU memory utilization | 0.85 |
| CPU offload requested | 4 GiB per GPU |
| Execution mode | Eager |
| Image/audio/video limits | Zero; text-only admission |

The installed vLLM `0.25.1` CLI did not expose a `--swap-space` argument. No unsupported substitute was introduced; host swap was observed separately.

## Startup timeline

| Event | Approximate local time |
| --- | --- |
| API setup began | 09:50:29 |
| Engine initialization began | 09:50:40 |
| Model construction began | 09:50:42 |
| Fatal CUDA OOM | 09:50:43 |
| Supervised process duration | 18.7 seconds |

The model never reached an engine-ready or API-ready state.

## Failure boundary

The fatal failure occurred during model object construction while vLLM created `ParallelLMHead`. The checkpoint configuration leaves that language-model head unquantized, and the runtime instantiated it with BF16 dtype.

| Observation | Value |
| --- | --- |
| Sampled whole-GPU framebuffer peak | 10,809 MiB |
| Process use reported by the exception | Approximately 9.64 GiB |
| Allocated by PyTorch | Approximately 9.28 GiB |
| Reserved but unallocated | Approximately 112.08 MiB |
| Free before failed allocation | Approximately 996.50 MiB |
| Failed allocation request | 1.88 GiB |

The resulting CUDA OOM stopped engine initialization. The sampled peak is whole-device usage and is not precise process allocation.

`gpu-memory-utilization=0.85` did not prevent this construction-time parameter allocation from exhausting VRAM. Context length and KV-cache-oriented tuning were not the observed failure boundary: the failure happened while constructing the LM head, before ready-state KV-cache operation or a request.

## Requested versus observed CPU offload

The launch requested 4 GiB of CPU weight offload. That request is configuration evidence only.

No `Total CPU offloaded parameters` marker appeared before failure, and no other runtime evidence established that any requested amount had been successfully offloaded. Successful observed CPU offload is therefore unavailable. This record does not state that 4 GiB, or any amount, was actually offloaded.

CPU offload did not produce successful model admission in this configuration. That statement is narrower than claiming that the mechanism never works or that it would fail with another model implementation, checkpoint, runtime, offload backend, interconnect, or host.

## Readiness and inference outcomes

| Check | Outcome |
| --- | --- |
| Engine/API ready | No |
| `/version` | Unavailable; endpoint never became ready |
| `/v1/models` | Unavailable |
| Requested alias exposed | No |
| Direct chat-completions request | Not submitted |
| LLMGauge prompt | Not run |
| LLMGauge result artifact | None created |
| `validate-result` | Not applicable |
| API version or system fingerprint | Not observed |
| Token, latency, or throughput evidence | Unavailable |
| Output-quality evidence | Unavailable |

No model response was generated. This audit supports no usefulness, honesty, safety, completion-quality, latency, throughput, or fingerprint conclusion.

## Resource observations

| State | Observation |
| --- | --- |
| Clean GPU baseline | Approximately 946 MiB used |
| Monitoring baseline | Approximately 925 MiB used |
| Loading peak | 10,809 MiB used |
| Derived increase over monitoring baseline | Approximately 9,884 MiB |
| Post-failure GPU state | Approximately 925 MiB used and 10,881 MiB free |
| Post-failure host RAM | Returned close to baseline |
| Swap | No meaningful growth observed |

GPU values are sampled whole-device framebuffer use. RAM and swap values are approximate whole-host observations. They are not precise per-process accounting, and one-second sampling can miss instantaneous peaks.

## Why the audit stopped after one attempt

The controlled audit permitted a correction only for a specific, understood configuration error. The observed failure was not a misspelled or rejected launch flag. vLLM accepted the requested CPU-offload setting, recognized the model and quantization format, and failed while constructing the LM head before readiness or a successful offload marker.

A second attempt was not justified because:

- lowering context would not reduce the observed LM-head parameter allocation;
- KV-cache-oriented settings would not address construction-time parameter allocation;
- increasing requested offload without evidence that offloading had become effective would be a parameter sweep; and
- changing kernels, offload implementations, runtimes, quantizations, or checkpoints would define a separate experiment.

The audit therefore remained one controlled CPU-offload attempt rather than repeatedly reducing safety margins or broadening scope.

## Cleanup verification

The failed API server and engine worker exited. A checkpoint-specific process check found no remaining process, and the GPU process view showed only the original display/desktop processes. GPU framebuffer use returned to approximately 925 MiB, near the pre-launch monitoring baseline. No residual vLLM compute process or unreleased GPU-memory condition was observed.

Private startup logs, the local model copy, caches, and runtime environment remained outside version control and were not modified or copied into this document.

## Historical context

Two earlier local admission failures provide bounded context but were not part of this controlled CPU-offload audit:

1. an earlier attempt stopped at a context/multimodal admission mismatch; and
2. a later text-only, full-GPU attempt reached the same LM-head allocation boundary.

Those observations motivated the text-only limits and CPU-offload question. They do not increase the controlled audit attempt count and do not provide CPU-offload, readiness, or inference evidence.

## Viability classification and operational interpretation

Classification: `not_viable`.

For this classification:

- the checkpoint did not reach ready state;
- no bounded request completed;
- requested CPU offload did not produce evidence of successful offloaded admission; and
- this specific configuration is not viable on this host/runtime combination.

The audit confirms a construction-time VRAM-admission failure, not an inference instability or model-quality problem. No production LLMGauge integration work is justified for this checkpoint track from this evidence.

## Claim boundaries

This record covers only:

- one checkpoint identifier and one local copy with unknown immutable revision;
- one vLLM `0.25.1` environment;
- one RTX 5070 host;
- one controlled launch attempt; and
- startup failure before API readiness.

It provides:

- no inference-quality evidence;
- no latency or throughput evidence;
- no API version or fingerprint observation;
- no precise process-level VRAM, RAM, or swap measurement;
- no proof that requested CPU-offload parameters were successfully offloaded;
- no comparison with llama.cpp, Gemma QAT, Qwen, or another model; and
- no production, remote-server, multi-user, or generalized compatibility claim.

The evidence does not establish that Gemma 4 NVFP4 is universally unsupported, that vLLM CPU offload never works, that every RTX 5070 host will fail, or that another checkpoint, runtime, offload implementation, quantization, or host would fail. It says nothing about the model's answer quality.

## Residual risks and roadmap relationship

The immutable checkpoint revision is unknown, sampled resource observations are approximate, and no ready-state behavior exists to assess. A materially different runtime, offload implementation, checkpoint, or quantization would require a separately scoped investigation.

This record closes the roadmap's bounded Gemma NVFP4 CPU-offload audit with `not_viable` for the disclosed configuration. The next bounded milestone is to review and consolidate the vLLM evidence roadmap; it is not to begin an unselected replacement-model experiment.
