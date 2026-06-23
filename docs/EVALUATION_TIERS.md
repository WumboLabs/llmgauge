# Evaluation Tiers

LLMGauge evaluation tiers define what evidence a run produces and what claims
that evidence can support.

The purpose is to keep WumboLabs model testing honest: real hardware, real
testing, no hype.

A lower-tier result can be useful, but it must not be described as stronger
evidence than it is.

## Tier 0 — Load/Fit Check

### Purpose

Confirm that a model, quantization, runtime, and profile can load and generate
on the tested hardware.

### What it tests

- Model load success
- Basic generation sanity
- Runtime/profile wiring
- Prompt evaluation speed
- Generation speed
- Peak VRAM use
- VRAM headroom

### Evidence produced

- The model fits or does not fit under the tested configuration.
- The runtime/profile is operational or broken.
- Basic performance and memory characteristics are recorded.

### Allowed claims

- "This model fits on this hardware under this config."
- "This model generated a basic response."
- "This runtime/profile is operational."
- "This configuration has approximately this much VRAM headroom."

### Not allowed

- Quality claims
- Safety claims
- Recommendation claims
- Daily-driver claims
- Broad ranking claims

### When to run

Run Tier 0 before any deeper evaluation, after adding a new model profile, or
after changing the runtime/backend configuration.

### What comes next

If the model loads cleanly and has usable headroom, run a Tier 1 practical smoke
suite.

## Tier 1 — Practical Smoke Suite

### Purpose

Quickly screen a model for obvious practical failures before spending time on a
larger evaluation.

The current small practical suites, including `core-v1`, should be treated as
Tier 1 smoke evidence unless a future suite explicitly declares a stronger tier.

### What it tests

- Basic usefulness
- Basic honesty
- Basic technical reasoning
- Basic safety/conservatism
- Basic instruction following
- Obvious completion failures

### Evidence produced

- Whether the model is worth deeper testing.
- Whether the model shows immediate safety, honesty, hallucination, or
  completion problems.
- Whether the model can handle small practical tasks under controlled settings.

### Allowed claims

- "This model passed/failed an initial practical smoke screen."
- "This model showed obvious safety, honesty, or completion issues."
- "This model is/is not worth deeper evaluation."

### Not allowed

- Definitive rankings
- Daily-driver recommendations
- Broad practical-use claims
- "Best model" claims
- Claims outside the tested prompts, hardware, runtime, and settings

### When to run

Run Tier 1 after Tier 0 succeeds and before a larger Tier 2 practical evaluation.

### What comes next

If the model passes Tier 1 without severe failures, run Tier 2.

## Tier 2 — WumboLabs Practical Eval

### Purpose

Produce serious structured evidence for practical local model comparison on
consumer hardware.

Tier 2 is the first tier suitable as the basis for public WumboLabs comparison
reports, provided the run is validated, scored, and interpreted with caveats.

### What it tests

- Technical correctness
- Honesty and uncertainty handling
- Code usefulness
- Config reasoning
- Long-context retrieval
- Multi-step planning
- Output discipline
- Practical judgment
- Niche hallucination resistance
- Adversarial realism / prompt contamination resistance

### Evidence produced

- Dimensional manual scores
- Score rationales
- Failure labels
- Good labels
- Runtime speed
- VRAM use and headroom
- Prompt-level strengths and weaknesses
- Recurring model failure modes
- Comparison against a tested baseline

### Allowed claims

- "This model performed better/worse than another model on this suite."
- "This model is a strong candidate for this tested use case on this hardware."
- "This model showed recurring failure modes in these categories."
- "This model has these practical strengths and weaknesses under the tested
  conditions."

### Not allowed

- Universal model rankings
- Daily-driver recommendations by Tier 2 alone
- Claims outside the tested hardware/runtime/suite
- Long-term reliability claims
- Claims that ignore severe failure modes

### When to run

Run Tier 2 for models that pass Tier 1 and are plausible candidates for public
comparison.

### What comes next

If a model performs well in Tier 2, use it in a controlled daily-driver trial or
compare it against the current WumboLabs baseline.

## Tier 3 — Daily-Driver Trial

### Purpose

Evaluate a model through real use over days or weeks.

### What it tests

- Trust over time
- Reliability in organic workflows
- Annoyance and friction
- Speed/context comfort
- Repeated failure patterns
- Whether the model remains useful outside scripted prompts

### Evidence produced

- Notes from real workflows
- Recurring strengths and frustrations
- Practical trust boundaries
- Whether failures accumulate or remain tolerable

### Allowed claims

- "This model held up / did not hold up during real use."
- "This model is comfortable / uncomfortable as a daily-driver candidate."
- "This model is useful for these workflows and weak for these workflows."

### Not allowed

- Universal recommendation claims
- Untested hardware/runtime claims
- Benchmark-style generalization

### When to run

Run Tier 3 only after a model performs well enough in Tier 2 to deserve real
usage time.

### What comes next

If Tier 2 and Tier 3 both support the model, it may qualify for Tier 4
recommendation.

## Tier 4 — Recommendation

### Purpose

Make a public recommendation for a specific model, quantization, hardware class,
runtime, and use case.

### Required evidence

- Tier 2 practical evaluation
- Some Tier 3 daily-driver evidence
- Clear comparison baseline
- Known caveats
- Reproducible artifacts
- Hardware/runtime disclosure
- Severe failure modes disclosed

### Allowed claims

- "Recommended for this hardware/use case."
- "Best current WumboLabs-tested option for this class."
- "Preferred baseline for this tested local workflow."

### Not allowed

- Universal "best model" claims
- Claims that hide tested hardware limits
- Claims that ignore known severe failures
- Claims that generalize beyond the tested use case

## Claim discipline

Use the weakest applicable tier when describing a result.

If a model only has Tier 1 evidence, call it a smoke result.

If a model has Tier 2 evidence but no daily-driver evidence, call it a practical
evaluation result, not a recommendation.

If a model has excellent speed but poor safety or honesty, do not bury that
failure behind performance numbers.

If a model fits only with thin VRAM headroom, treat that as a practical risk.

## Public report rule

A public WumboLabs model report should state:

- Evaluation tier
- Model name
- Quantization
- Hardware
- Runtime/backend
- Context size
- Token budget
- Suite name and version
- Whether the result was manually scored
- Whether scores were validated before applying
- Prompt evaluation speed
- Generation speed
- Peak VRAM
- VRAM headroom
- Strengths
- Failure modes
- Practical verdict
- Claim limits
