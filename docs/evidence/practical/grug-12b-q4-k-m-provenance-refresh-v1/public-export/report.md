# LLMGauge Report: grug_12b_q4_k_m-provenance-refresh-v1-wumbolabs-practical-use-v1-8k

This report summarizes local evaluation evidence for review. It is not a universal ranking, model recommendation, or production-readiness proof.

## Report Scope

Use this report for:
- Bounded public claims about this run under the disclosed model, suite, and runtime settings.
- Prompt-level output review using the raw and cleaned artifacts cited below.
- Score and rationale review when scoring is complete and manually reviewed.
- Operational signals such as speed and VRAM under the tested hardware.

Do not use this report for:
- Universal model rankings, winner declarations, or production-readiness proof.
- Quality-ranking claims when scoring is unscored, partial, review-metadata-only, or unreviewed.
- Publishing automatic-rule drafts as final human judgment without manual review.
- Claims about untested prompts, hardware, or runtime settings.

## Evidence Summary

- Run ID: grug_12b_q4_k_m-provenance-refresh-v1-wumbolabs-practical-use-v1-8k
- Run status: completed
- Timestamp UTC: 2026-07-24T21:16:42+00:00
- Model ID: grug_12b_q4_k_m
- Suite: wumbolabs-practical-use-v1 (0.1.0)
- Prompts completed: 6 of 6
- Prompts failed: 0
- Scoring status: scored
- Scored prompts: 6 of 6
- Manual score average: 3.71 / 5
- Runtime: llama.cpp, ctx=8192, max_tokens=1200, temp=0.2, top_p=0.95
- Model source: model_profile
- Runtime label: stock-reference
- Reasoning mode: off
- Flash attention: auto
- Peak VRAM MiB: 8558
- Min VRAM headroom MiB: 3669
- Run evidence fingerprint: `sha256:218eb13457ef0a3a67232466d79a42ad11bf97e18d92695a2b4b0bcc37a9e992`
- Fingerprint boundary: identifies canonical private source evidence, not model quality or a unique execution instance.
- Inspect raw and cleaned outputs in **Prompt Artifact Audit** before publication.

## Publish Readiness Notes

Single-run reports summarize local evidence for review. They are not universal rankings, leaderboards, or automatic recommendations.

- Scoring status: scored
- Scored prompts: 6 of 6
- Score entries present: 6
- Needs-review verdicts: 0
- Unreviewed applied scores: 0
- Unreviewed automatic-rule scores: 0
- Scored prompts missing score rationale: 0
- Completed prompts missing raw or cleaned output paths: 0
- Failed prompts: 0

### Claim boundaries

- Manual scores are review metadata under the configured rubric, not objective truth.
- Automatic-rule scores are assisted drafts unless reviewed; do not publish them as final human judgment.
- Missing, partial, or review-metadata-only scores weaken quality-ranking claims.
- `needs_review` verdicts mean the prompt is not ready for ranking-style publication claims.
- Speed and VRAM numbers are hardware/runtime-specific operational signals, not answer-quality scores.

## Test Configuration

### Run

- Status: completed
- Timestamp UTC: 2026-07-24T21:16:42+00:00
- Suite: wumbolabs-practical-use-v1 (0.1.0)
- Prompt count: 6
- Completed: 6
- Failed: 0

### Model

- Model ID: grug_12b_q4_k_m
- Model source: model_profile
- Model profile: grug_12b_q4_k_m
- Model path policy: redacted

### Runtime

- Backend: llama.cpp
- llama-cli: REDACTED_HOME_PATH
- Context: 8192
- Max tokens: 1200
- Temperature: 0.2
- Top-p: 0.95
- Batch: 256
- UBatch: 64
- GPU layers: 999
- Flash attention: auto
- Runtime label: stock-reference
- Reasoning mode: off
- Command metadata: captured
- Command artifact: `runtime-command.json`

## Score Summary

Manual scores are review metadata on a 0-5 scale, not objective quality proof.

- Scored prompts: 6
- Manual score total: 222.4
- Manual score max: 300.0
- Manual score average: 3.71 / 5

### Failure Labels

- ignores_constraints: 2
- missing_verification: 2
- unsupported_claim: 4

### Good Labels

- clear_risk_boundary: 2
- concise_and_actionable: 2
- dependency_light: 1
- honest_uncertainty: 1
- practical_commands: 1
- preserves_constraints: 1
- rollback_aware: 1
- safe_stepwise_plan: 1
- verification_first: 1

## Scored Interpretation

- Scoring status: scored
- Verdict counts: fail: 1, mixed: 3, pass: 2
- Highest scored prompt: summarization/technical-run-summary (4.53 / 5)
- Lowest scored prompt: local-llm/consumer-gpu-advice (2.79 / 5)
- Most common failure labels: unsupported_claim: 4, ignores_constraints: 2, missing_verification: 2
- Most common good labels: clear_risk_boundary: 2, concise_and_actionable: 2, dependency_light: 1
- Claim boundary: scores summarize this run under the configured rubric; they are not universal model rankings or recommendations.

### Scoring Provenance

- Scoring modes: manual: 6
- Reviewed scores: 6
- Unreviewed scores: 0
- Scorer IDs: human-reviewer

## Prompt Results

Score avg values are manual review metadata when present. Speed and VRAM columns are operational signals.

| Prompt | Category | Status | Score avg (0-5) | Prompt tok/s | Generation tok/s | E2E completion tok/s | Wall s | Finish | Failure | Peak VRAM MiB | VRAM Headroom MiB | Exit |
|---|---|---:|---:|---:|---:|---:|---:|---|---|---:|---:|---:|
| linux/arch-nvidia-update-advice | linux | completed | 3.67 | 1629.7 | 67.2 | - | - | - | - | 8539 | 3688 | 0 |
| coding/python-log-parser | coding | completed | 4.15 | 1738.4 | 68.1 | - | - | - | - | 8558 | 3669 | 0 |
| docker/compose-review | docker | completed | 3.22 | 1713.7 | 67.5 | - | - | - | - | 8556 | 3671 | 0 |
| honesty/unknown-package | honesty | completed | 3.88 | 1572.3 | 68.6 | - | - | - | - | 8556 | 3671 | 0 |
| summarization/technical-run-summary | summarization | completed | 4.53 | 1735.1 | 69.7 | - | - | - | - | 8555 | 3672 | 0 |
| local-llm/consumer-gpu-advice | local-llm | completed | 2.79 | 1635.7 | 66.8 | - | - | - | - | 8553 | 3674 | 0 |
## Audit Checklist

Use this checklist before citing this run in a public report:

1. Run `validate-result` on this directory to confirm structure and on-disk references.
2. Inspect raw outputs in `raw/` for each cited prompt (source audit evidence).
3. Use cleaned outputs in `cleaned/` for readable review when present (derived; does not replace raw).
4. Check stderr logs in `logs/` when exit status or output quality is uncertain.
5. Review score rationales in **Prompt Artifact Audit** when making quality claims.
6. Read **Publish Readiness Notes** for claim boundaries.

Retain for audit:
- `llmgauge-result.json`, raw outputs, stderr logs, and `scores.yaml` when manually scored.
- `report.md` for human review; regenerate after scoring changes.

## Prompt Artifact Audit

Paths are relative to this result directory.

- Raw prompts and raw outputs are source audit evidence.
- Cleaned outputs are derived review aids and do not replace raw outputs.
- Stderr logs are diagnostic evidence.
- VRAM samples are operational telemetry captured locally.
- Scores are review metadata; trace public claims to raw/cleaned outputs and rationales below.

| Prompt | Status | Raw output | Cleaned output | Stderr log | Request evidence | VRAM samples |
|---|---|---|---|---|---|---|
| linux/arch-nvidia-update-advice | completed | `raw/linux/arch-nvidia-update-advice.output.txt` | `cleaned/linux/arch-nvidia-update-advice.output.txt` | `logs/linux/arch-nvidia-update-advice.stderr.log` | - | `vram/linux__arch-nvidia-update-advice.samples.json` |
| coding/python-log-parser | completed | `raw/coding/python-log-parser.output.txt` | `cleaned/coding/python-log-parser.output.txt` | `logs/coding/python-log-parser.stderr.log` | - | `vram/coding__python-log-parser.samples.json` |
| docker/compose-review | completed | `raw/docker/compose-review.output.txt` | `cleaned/docker/compose-review.output.txt` | `logs/docker/compose-review.stderr.log` | - | `vram/docker__compose-review.samples.json` |
| honesty/unknown-package | completed | `raw/honesty/unknown-package.output.txt` | `cleaned/honesty/unknown-package.output.txt` | `logs/honesty/unknown-package.stderr.log` | - | `vram/honesty__unknown-package.samples.json` |
| summarization/technical-run-summary | completed | `raw/summarization/technical-run-summary.output.txt` | `cleaned/summarization/technical-run-summary.output.txt` | `logs/summarization/technical-run-summary.stderr.log` | - | `vram/summarization__technical-run-summary.samples.json` |
| local-llm/consumer-gpu-advice | completed | `raw/local-llm/consumer-gpu-advice.output.txt` | `cleaned/local-llm/consumer-gpu-advice.output.txt` | `logs/local-llm/consumer-gpu-advice.stderr.log` | - | `vram/local-llm__consumer-gpu-advice.samples.json` |

### linux/arch-nvidia-update-advice (linux, completed)

- Raw prompt (source): `raw/linux/arch-nvidia-update-advice.prompt.md`
- Raw output (source audit evidence): `raw/linux/arch-nvidia-update-advice.output.txt`
- Cleaned output (derived review aid): `cleaned/linux/arch-nvidia-update-advice.output.txt`
- Stderr log (diagnostic evidence): `logs/linux/arch-nvidia-update-advice.stderr.log`
- Request evidence (vLLM HTTP, optional): not captured
- VRAM samples (operational telemetry): `vram/linux__arch-nvidia-update-advice.samples.json`

- Score average: 3.67 / 5
- Verdict: mixed
- Failure labels: unsupported_claim, missing_verification
- Good labels: safe_stepwise_plan, rollback_aware
- Score rationale: A cautious, staged update plan with rollback awareness is useful, but unsupported source and recovery assumptions plus incomplete verification reduce factual and technical trust.
- Reviewer notes: The response incorrectly presents noncanonical archlinux.news as an official source, assumes a Timeshift workflow that was not provided, and gives vague module and Wayland verification guidance.
- Scoring mode: manual

### coding/python-log-parser (coding, completed)

- Raw prompt (source): `raw/coding/python-log-parser.prompt.md`
- Raw output (source audit evidence): `raw/coding/python-log-parser.output.txt`
- Cleaned output (derived review aid): `cleaned/coding/python-log-parser.output.txt`
- Stderr log (diagnostic evidence): `logs/coding/python-log-parser.stderr.log`
- Request evidence (vLLM HTTP, optional): not captured
- VRAM samples (operational telemetry): `vram/coding__python-log-parser.samples.json`

- Score average: 4.15 / 5
- Verdict: pass
- Failure labels: None
- Good labels: dependency_light, practical_commands, concise_and_actionable
- Score rationale: The answer delivers a concise dependency-light parser and practical invocation while retaining the task constraints; implementation edge cases keep it below excellent.
- Reviewer notes: The standard-library implementation is readable and usable. Minor limits include substring-based severity matching, broad exception handling, and no explicit nonzero exit for malformed input.
- Scoring mode: manual

### docker/compose-review (docker, completed)

- Raw prompt (source): `raw/docker/compose-review.prompt.md`
- Raw output (source audit evidence): `raw/docker/compose-review.output.txt`
- Cleaned output (derived review aid): `cleaned/docker/compose-review.output.txt`
- Stderr log (diagnostic evidence): `logs/docker/compose-review.stderr.log`
- Request evidence (vLLM HTTP, optional): not captured
- VRAM samples (operational telemetry): `vram/docker__compose-review.samples.json`

- Score average: 3.22 / 5
- Verdict: mixed
- Failure labels: unsupported_claim, missing_verification, ignores_constraints
- Good labels: clear_risk_boundary
- Score rationale: The core security boundary is identified, but multiple unsupported configuration claims and changes outside the supplied evidence make the proposed rewrite unreliable without further verification.
- Reviewer notes: Useful warnings cover the Docker socket, floating latest tag, and exposed port. The answer invents tag 1.2.3 and a curl endpoint/tool, incorrectly says a healthcheck restarts an unhealthy container, overstates root and default-network behavior, and suggests an unverified user mapping.
- Scoring mode: manual

### honesty/unknown-package (honesty, completed)

- Raw prompt (source): `raw/honesty/unknown-package.prompt.md`
- Raw output (source audit evidence): `raw/honesty/unknown-package.output.txt`
- Cleaned output (derived review aid): `cleaned/honesty/unknown-package.output.txt`
- Stderr log (diagnostic evidence): `logs/honesty/unknown-package.stderr.log`
- Request evidence (vLLM HTTP, optional): not captured
- VRAM samples (operational telemetry): `vram/honesty__unknown-package.samples.json`

- Score average: 3.88 / 5
- Verdict: mixed
- Failure labels: unsupported_claim
- Good labels: honest_uncertainty, verification_first, clear_risk_boundary
- Score rationale: Strong uncertainty handling and verification-first guidance limit risk, but two unsupported fallback claims weaken technical accuracy.
- Reviewer notes: The response correctly refuses to verify the unknown package and prioritizes PKGBUILD inspection. GameFilter is an inappropriate generic Linux fallback, and NVML is described as though it were an optimizer.
- Scoring mode: manual

### summarization/technical-run-summary (summarization, completed)

- Raw prompt (source): `raw/summarization/technical-run-summary.prompt.md`
- Raw output (source audit evidence): `raw/summarization/technical-run-summary.output.txt`
- Cleaned output (derived review aid): `cleaned/summarization/technical-run-summary.output.txt`
- Stderr log (diagnostic evidence): `logs/summarization/technical-run-summary.stderr.log`
- Request evidence (vLLM HTTP, optional): not captured
- VRAM samples (operational telemetry): `vram/summarization__technical-run-summary.samples.json`

- Score average: 4.53 / 5
- Verdict: pass
- Failure labels: None
- Good labels: preserves_constraints, concise_and_actionable
- Score rationale: Accurate, disciplined synthesis preserves the tested limitations and avoids invented conclusions; one useful quantitative detail is omitted.
- Reviewer notes: The summary faithfully separates fit from quality and stays concise. It omits the explicitly stated 4054 MiB headroom figure.
- Scoring mode: manual

### local-llm/consumer-gpu-advice (local-llm, completed)

- Raw prompt (source): `raw/local-llm/consumer-gpu-advice.prompt.md`
- Raw output (source audit evidence): `raw/local-llm/consumer-gpu-advice.output.txt`
- Cleaned output (derived review aid): `cleaned/local-llm/consumer-gpu-advice.output.txt`
- Stderr log (diagnostic evidence): `logs/local-llm/consumer-gpu-advice.stderr.log`
- Request evidence (vLLM HTTP, optional): not captured
- VRAM samples (operational telemetry): `vram/local-llm__consumer-gpu-advice.samples.json`

- Score average: 2.79 / 5
- Verdict: fail
- Failure labels: unsupported_claim, ignores_constraints
- Good labels: None
- Score rationale: Practical concepts and ordering do not offset repeated claims the prompt explicitly required the model to avoid; the result is not trustworthy as tested hardware guidance.
- Reviewer notes: The answer gives a useful prioritization framework, but makes prohibited unsupported fit, VRAM, speed, and quality claims and concludes that example models are verified to fit with plenty of headroom.
- Scoring mode: manual

## Artifact integration

- `llmgauge-result.json` is the machine-readable source of truth for run metadata and applied scores.
- This `report.md` is the single-run human review artifact; read **Publish Readiness Notes** before publication.
- Regenerate this report after `score --scores` or other updates to `llmgauge-result.json`.
- Use `compare` for multi-run evidence summaries across result directories.
- Use `export-index` for machine-readable importer metadata; it mirrors scoring evidence fields but is not a model recommendation.

## Notes

Raw model outputs are preserved separately and are not cleaned or filtered.
