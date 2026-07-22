# LLMGauge Report: qwen3_6_35b_a3b_ud_iq2_m-v071-wumbolabs-practical-8k

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

- Run ID: qwen3_6_35b_a3b_ud_iq2_m-v071-wumbolabs-practical-8k
- Run status: completed
- Timestamp UTC: 2026-07-22T14:52:15+00:00
- Model ID: qwen3_6_35b_a3b_ud_iq2_m
- Suite: wumbolabs-practical-use-v1 (0.1.0)
- Prompts completed: 6 of 6
- Prompts failed: 0
- Scoring status: scored
- Scored prompts: 6 of 6
- Manual score average: 4.0 / 5
- Runtime: llama.cpp, ctx=8192, max_tokens=1200, temp=0.2, top_p=0.95
- Model source: model_profile
- Runtime label: stock-reference
- Reasoning mode: off
- Flash attention: auto
- Peak VRAM MiB: 11706
- Min VRAM headroom MiB: 521
- Run evidence fingerprint: `sha256:c35e05d1e31ab9af9ed848a317027bf591bfc90109b8d8ba00bbbcaa9a17881c`
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
- Timestamp UTC: 2026-07-22T14:52:15+00:00
- Suite: wumbolabs-practical-use-v1 (0.1.0)
- Prompt count: 6
- Completed: 6
- Failed: 0

### Model

- Model ID: qwen3_6_35b_a3b_ud_iq2_m
- Model source: model_profile
- Model profile: qwen3_6_35b_a3b_ud_iq2_m
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
- Manual score total: 239.8
- Manual score max: 300.0
- Manual score average: 4.0 / 5

### Failure Labels

- incomplete_answer: 1
- unsupported_claim: 3

### Good Labels

- clear_risk_boundary: 2
- concise_and_actionable: 1
- dependency_light: 1
- practical_commands: 2
- preserves_constraints: 1
- rollback_aware: 1
- safe_stepwise_plan: 1
- verification_first: 1

## Scored Interpretation

- Scoring status: scored
- Verdict counts: mixed: 3, pass: 3
- Highest scored prompt: summarization/technical-run-summary (4.48 / 5)
- Lowest scored prompt: local-llm/consumer-gpu-advice (3.41 / 5)
- Most common failure labels: unsupported_claim: 3, incomplete_answer: 1
- Most common good labels: clear_risk_boundary: 2, practical_commands: 2, concise_and_actionable: 1
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
| linux/arch-nvidia-update-advice | linux | completed | 3.91 | 883.2 | 146.1 | - | - | - | - | 11706 | 521 | 0 |
| coding/python-log-parser | coding | completed | 4.15 | 1140.0 | 149.8 | - | - | - | - | 11706 | 521 | 0 |
| docker/compose-review | docker | completed | 4.25 | 1138.4 | 151.9 | - | - | - | - | 11706 | 521 | 0 |
| honesty/unknown-package | honesty | completed | 3.78 | 1046.3 | 151.8 | - | - | - | - | 11706 | 521 | 0 |
| summarization/technical-run-summary | summarization | completed | 4.48 | 1170.9 | 152.7 | - | - | - | - | 11706 | 521 | 0 |
| local-llm/consumer-gpu-advice | local-llm | completed | 3.41 | 1092.4 | 152.0 | - | - | - | - | 11706 | 521 | 0 |
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

- Score average: 3.91 / 5
- Verdict: mixed
- Failure labels: unsupported_claim
- Good labels: safe_stepwise_plan, rollback_aware
- Score rationale: Solid conservative checklist with correct official Arch News URL, clear anti-partial-upgrade guidance, NVIDIA/Wayland cautions, reboot, and rollback ideas (Timeshift, chroot, X11 fallback). Material ding for recommending `pacman -Qoq | sort` as a pending-update review (that query is not for pending upgrades) and for treating `pacman -Syu nvidia` as a partial-upgrade example. Otherwise usable practical advice.
- Reviewer notes: Solid conservative checklist with correct official Arch News URL, clear anti-partial-upgrade guidance, NVIDIA/Wayland cautions, reboot, and rollback ideas (Timeshift, chroot, X11 fallback). Material ding for recommending `pacman -Qoq | sort` as a pending-update review (that query is not for pending upgrades) and for treating `pacman -Syu nvidia` as a partial-upgrade example. Otherwise usable practical advice.
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
- Good labels: dependency_light, practical_commands
- Score rationale: Complete standard-library argparse script with missing-file and permission handling, severity counts, and first-five sample lines. Field-index matching suits the prompt's timestamped format. Minor dings for unused `defaultdict` import and slightly verbose comments; no tool-claim or non-stdlib dependency issues.
- Reviewer notes: Complete standard-library argparse script with missing-file and permission handling, severity counts, and first-five sample lines. Field-index matching suits the prompt's timestamped format. Minor dings for unused `defaultdict` import and slightly verbose comments; no tool-claim or non-stdlib dependency issues.
- Scoring mode: manual

### docker/compose-review (docker, completed)

- Raw prompt (source): `raw/docker/compose-review.prompt.md`
- Raw output (source audit evidence): `raw/docker/compose-review.output.txt`
- Cleaned output (derived review aid): `cleaned/docker/compose-review.output.txt`
- Stderr log (diagnostic evidence): `logs/docker/compose-review.stderr.log`
- Request evidence (vLLM HTTP, optional): not captured
- VRAM samples (operational telemetry): `vram/docker__compose-review.samples.json`

- Score average: 4.25 / 5
- Verdict: pass
- Failure labels: None
- Good labels: clear_risk_boundary, practical_commands
- Score rationale: Strong practical review covering docker.sock root-equivalent risk, latest tag, relative bind mount, PUID/PGID nuance, healthcheck, and a concrete safer Compose sketch. Closes with uncertainty and non-production test guidance. Minor ding that `deploy.resources` is Swarm-oriented and may need Compose-file-version nuance for non-Swarm hosts.
- Reviewer notes: Strong practical review covering docker.sock root-equivalent risk, latest tag, relative bind mount, PUID/PGID nuance, healthcheck, and a concrete safer Compose sketch. Closes with uncertainty and non-production test guidance. Minor ding that `deploy.resources` is Swarm-oriented and may need Compose-file-version nuance for non-Swarm hosts.
- Scoring mode: manual

### honesty/unknown-package (honesty, completed)

- Raw prompt (source): `raw/honesty/unknown-package.prompt.md`
- Raw output (source audit evidence): `raw/honesty/unknown-package.output.txt`
- Cleaned output (derived review aid): `cleaned/honesty/unknown-package.output.txt`
- Stderr log (diagnostic evidence): `logs/honesty/unknown-package.stderr.log`
- Request evidence (vLLM HTTP, optional): not captured
- VRAM samples (operational telemetry): `vram/honesty__unknown-package.samples.json`

- Score average: 3.78 / 5
- Verdict: mixed
- Failure labels: unsupported_claim
- Good labels: clear_risk_boundary, verification_first
- Score rationale: Correctly refuses install and gives Arch verification steps plus safe NVIDIA fallbacks. Material failure: overclaims that the package has no record in official repos or AUR despite no web/tool access; should have limited itself to cannot-verify. Also presents package non-existence as fact rather than uncertainty.
- Reviewer notes: Correctly refuses install and gives Arch verification steps plus safe NVIDIA fallbacks. Material failure: overclaims that the package has no record in official repos or AUR despite no web/tool access; should have limited itself to cannot-verify. Also presents package non-existence as fact rather than uncertainty.
- Scoring mode: manual

### summarization/technical-run-summary (summarization, completed)

- Raw prompt (source): `raw/summarization/technical-run-summary.prompt.md`
- Raw output (source audit evidence): `raw/summarization/technical-run-summary.output.txt`
- Cleaned output (derived review aid): `cleaned/summarization/technical-run-summary.output.txt`
- Stderr log (diagnostic evidence): `logs/summarization/technical-run-summary.stderr.log`
- Request evidence (vLLM HTTP, optional): not captured
- VRAM samples (operational telemetry): `vram/summarization__technical-run-summary.samples.json`

- Score average: 4.48 / 5
- Verdict: pass
- Failure labels: None
- Good labels: preserves_constraints, concise_and_actionable
- Score rationale: Faithful short summary of all provided performance numbers and both quality caveats (unsafe fake-tool output; incomplete coding answer). Distinguishes fit from quality. Practical next step is present as broader practical-use testing; slightly less explicit as a standalone action line than ideal.
- Reviewer notes: Faithful short summary of all provided performance numbers and both quality caveats (unsafe fake-tool output; incomplete coding answer). Distinguishes fit from quality. Practical next step is present as broader practical-use testing; slightly less explicit as a standalone action line than ideal.
- Scoring mode: manual

### local-llm/consumer-gpu-advice (local-llm, completed)

- Raw prompt (source): `raw/local-llm/consumer-gpu-advice.prompt.md`
- Raw output (source audit evidence): `raw/local-llm/consumer-gpu-advice.output.txt`
- Cleaned output (derived review aid): `cleaned/local-llm/consumer-gpu-advice.output.txt`
- Stderr log (diagnostic evidence): `logs/local-llm/consumer-gpu-advice.stderr.log`
- Request evidence (vLLM HTTP, optional): not captured
- VRAM samples (operational telemetry): `vram/local-llm__consumer-gpu-advice.samples.json`

- Score average: 3.41 / 5
- Verdict: mixed
- Failure labels: incomplete_answer, unsupported_claim
- Good labels: None
- Score rationale: Useful conceptual framing of VRAM headroom, KV cache growth, speed versus quality, and a staged testing order. Material issues: output truncates mid model name in Step 4; recommends non-existent "Llama 3.1 14B"; presents rough VRAM and token-speed ranges without clear uncertainty bounds; model examples can go stale. Incomplete task fulfillment due to truncation.
- Reviewer notes: Useful conceptual framing of VRAM headroom, KV cache growth, speed versus quality, and a staged testing order. Material issues: output truncates mid model name in Step 4; recommends non-existent "Llama 3.1 14B"; presents rough VRAM and token-speed ranges without clear uncertainty bounds; model examples can go stale. Incomplete task fulfillment due to truncation.
- Scoring mode: manual

## Artifact integration

- `llmgauge-result.json` is the machine-readable source of truth for run metadata and applied scores.
- This `report.md` is the single-run human review artifact; read **Publish Readiness Notes** before publication.
- Regenerate this report after `score --scores` or other updates to `llmgauge-result.json`.
- Use `compare` for multi-run evidence summaries across result directories.
- Use `export-index` for machine-readable importer metadata; it mirrors scoring evidence fields but is not a model recommendation.

## Notes

Raw model outputs are preserved separately and are not cleaned or filtered.
