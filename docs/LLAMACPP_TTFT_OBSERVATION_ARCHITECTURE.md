# LLAMA.CPP TTFT Observation Architecture

## Status

**BLOCKED / DEFERRED — CURRENT NATIVE INTERFACE CANNOT PROVE TTFT**

The current native `llama-cli` subprocess interface cannot provide LLMGauge
with a defensible observation of `llmgauge.metric.v1.time_to_first_token`
under the accepted Area 4 definition. This is an architecture and feasibility
milestone only: no production TTFT collection is implemented, and no schema,
result, fingerprint, or runner behavior changes here.

The native CLI exposes only decoded-text UI rendering on stdout. It provides
no machine-readable generated-token boundary, it echoes the prompt onto the
generated-output stream unconditionally (the `--no-display-prompt` flag is not
honored by this build's `llama-cli` chat path), and it renders a banner,
reasoning markers, a timing line, and an exit message on the same stdout
stream. Separating "first generated token" from that stream would require
text-subtraction heuristics and would still observe a decoded-text piece, not
a token boundary. Both are explicitly blocked by the accepted semantic
boundary.

The embedded `llama-server` HTTP interface that `llama-cli` itself uses *does*
expose a per-token SSE stream carrying raw token IDs (with
`return_tokens`/`stream`), which is a genuine machine-readable token boundary.
Using it, however, requires talking to `llama-server` directly and owning its
lifecycle — a substantially different runtime architecture that belongs to a
separate backend rather than the current native `llama-cli` path. That option
is architecturally recorded here and explicitly deferred, not implemented.

## Metric authority

The accepted definition comes from
[RUNTIME_NEUTRAL_METRICS_FAILURE_TAXONOMY_CONTRACT.md](RUNTIME_NEUTRAL_METRICS_FAILURE_TAXONOMY_CONTRACT.md):

> `llmgauge.metric.v1.time_to_first_token` measures seconds from the request
> start boundary above to availability of the first generated output token at
> the LLMGauge transport boundary. It requires a streaming or equivalent
> admitted observation that identifies that moment. A non-streaming
> request/response does not fabricate TTFT from total duration.

The contract requires a *generated output token* boundary, not a byte, chunk,
or decoded-text piece, and it makes TTFT `unavailable` (never zero) when no
first token is observable. The milestone's non-negotiable semantic boundary
forbids substituting "time to first output byte/chunk", "first line printed",
"first non-empty output", or any value inferred from llama.cpp final timing
counters for TTFT.

## Current native execution boundary

The native runner is `src/llmgauge/runners/llama_cpp.py`
(`run_llama_cpp`). It:

1. records `started_at = time.monotonic()` immediately before `subprocess.Popen`;
2. launches `llama-cli` with `stdout=subprocess.PIPE, stderr=subprocess.PIPE,
   text=True`;
3. loops on `process.communicate(timeout=wait_seconds)` until the child exits
   or the per-turn deadline is reached (killing on timeout);
4. on return, reads the complete buffered stdout and stderr at once;
5. records `elapsed_seconds = time.monotonic() - started_at` after
   `communicate()` returns.

This is a **completed-process / `communicate()`-style boundary**. Output is
not incrementally consumed; the caller receives the full stdout and stderr
only after the process completes or is killed on timeout. The existing Area 4
evidence records this as
`request_wall_time_boundary: "process_launch_to_terminal_output_receipt"`.

Because output is only available after the child completes, the current code
has no access to the moment the first generated output becomes available. TTFT
cannot be derived from it.

## Upstream llama.cpp evidence

All source findings are from the installed binary's own source checkout,
proven identical by version string.

- Installed executable:
  `<operator-local>/llama.cpp-current/bin/llama-cli`
  (symlink to
  `<operator-local>/llama.cpp-sm120-upgrade/build-cuda-sm120-new/bin/llama-cli`)
- Reported build: `version: 0.1.0-dev (build 10449, commit 0d9ceae1e)`,
  built with GNU 15.3.1 for Linux x86_64.
- Source checkout: `<operator-local>/llama.cpp-sm120-upgrade`
  at `HEAD = 0d9ceae1e38291035605613ab41a8f5e693d6fcd`
  ("ui: read structuredContent from MCP tool result when content is empty").
- **INSTALLED BINARY ↔ SOURCE correspondence is proven**: the binary reports
  commit `0d9ceae1e`, which is exactly the source checkout HEAD.

Relevant source paths:

- `tools/cli/main.cpp`, `tools/cli/cli.cpp` — thin entry points into
  `cli_context`.
- `tools/cli/cli-context.cpp` — chat loop, prompt handling, streaming.
- `tools/cli/cli-ui.h` — console rendering (`assistant_turn::push`).
- `tools/cli/cli-client.cpp` — SSE client (`post_sse`).
- `common/console.cpp` — `console::log` / `console::flush`, `simple_io`.
- `tools/server/server-context.cpp` — server-side per-token partial responses.
- `tools/server/server-task.cpp`, `server-chat.cpp` — OAI-compat SSE framing.
- `common/arg.cpp`, `common/common.h` — `--no-display-prompt` flag and
  `display_prompt` field.

## What the host can observe

The LLMGauge transport boundary for the native CLI is `llama-cli`'s **stdout
pipe**. Under `--simple-io --single-turn`, the stdout stream carries, in
order:

1. an ASCII logo banner plus build/model/modalities info (`ui::show_message`);
2. a prompt echo line `> <prompt>` (unconditional when a prompt is supplied);
3. optional `[Start thinking]` / `[End thinking]` markers and streamed
   reasoning content, when the model emits reasoning;
4. streamed decoded content pieces of the generated answer;
5. a trailing `[ Prompt: … | Generation: … ]` timing line
   (`--show-timings`, default on);
6. an `Exiting...` message.

Each non-empty decoded content piece in step 4 is written via
`console::log("%s", …)` (a `vfprintf` to stdout) followed by
`console::flush()` (`fflush(stdout)`). Empty pieces write nothing and do not
flush.

## Token / piece / byte distinction

The emission chain is: model token → server detokenizes to
`tkn.text_to_send` (`server-context.cpp:3783`
`common_token_to_piece(...)`) → one SSE partial response per generated token
(`server-context.cpp:1810`
`send_partial_response(slot, result, false)`, `:1995`
`res->content = tkn.text_to_send`, `res->tokens = { tkn.tok }`) → OAI-compat
`delta.content` (`server-chat.cpp:612`, empty content omitted) → `llama-cli`
extracts `delta.content` only (`cli-context.cpp:396`) → `assistant_turn::push`
writes + flushes non-empty text to stdout (`cli-ui.h:223-224`).

The host observes only the final stdout bytes. These are **decoded text
pieces**, not token IDs. Multiple, distinct, and non-equivalent facts:

- **token ID** — never emitted on stdout;
- **decoded token piece** — one token detokenizes to a text piece (possibly
  empty);
- **byte sequence** — the piece's UTF-8 bytes;
- **stdout write** — one write+flush per non-empty piece;
- **pipe read chunk** — the OS may coalesce several writes into one read;
- **character/line** — display-level units.

Consequences for boundary detection:

- A generated token whose piece decodes to empty (control/special tokens,
  whitespace-only handling, partial multibyte continuation) produces **no
  stdout write and no flush**, so it is invisible.
- A decoded piece may be a partial UTF-8 multibyte sequence; the server
  explicitly formats incomplete UTF-8 for output
  (`server-common.h:502-503`), so a "character" boundary is not guaranteed.
- Several child writes can be coalesced by the pipe into a single read.
- Reasoning content is emitted before the final `content`, so the first
  "generated output" on stdout may be reasoning, not the answer's first token.

The first generated **token** boundary is therefore not observable on stdout.
Only "first non-empty decoded content byte/chunk" is observable, and even that
is contaminated by the preceding banner and prompt echo (see below).

## Candidate architectures

### A. Pipe-based incremental read

Feasible host-side (proven by synthetic experiment: concurrent stdout/stderr
drain, timeout kill+reap, exact byte equivalence, no deadlock). But it does
not add a token boundary. The host still sees only the decoded-text UI
stream. Incremental reading would let the host timestamp the *first non-empty
content byte/chunk*, which is not a generated-token boundary and is preceded
by banner + prompt echo. **REJECT for TTFT.**

### B. PTY-based observation

A PTY changes terminal detection, buffering, formatting, and color/control
behavior. It does not add token information (the child still emits the same
decoded-text UI). It introduces semantic mutation for no TTFT benefit.
**REJECT.**

### C. llama.cpp machine-readable / event output

`llama-cli` has no flag that emits a token/event stream to stdout.
`--log-prompts-dir` logs prompts, not generated tokens. The embedded server's
SSE *does* carry raw token IDs, but `llama-cli` discards them and does not
forward them. **REJECT for the `llama-cli` path.**

### D. llama-server / HTTP streaming

The embedded `llama-server` emits one SSE partial response per generated
token, carrying both decoded content and the raw token ID (`tokens` field,
populated when `stream` or `return_tokens` is set). A client could observe a
genuine per-token boundary and compute TTFT correctly. However, reaching it
requires either (a) driving `llama-cli`'s internal server (not exposed), or
(b) starting and owning a `llama-server` process directly. (b) replaces the
native `llama-cli` execution with a long-lived server lifecycle and a separate
HTTP transport — a substantial runtime architecture change that belongs to a
different backend. **DEFER** (recorded here, not implemented).

### E. Library / API embedding

Could give direct token callbacks, but requires C bindings and a new
dependency, which the milestone forbids. **REJECT / DEFER** conceptually.

## Selected architecture or blocker

**Blocker.** The current native `llama-cli` subprocess interface cannot prove
the required first generated-token boundary. TTFT is **NOT CURRENTLY
FEASIBLE** through it. A future `llama-server`-backed backend (option D) is
the only native llama.cpp route that exposes a proven token boundary, and it
is a separate, substantial runtime architecture change.

## Request-start boundary

The current request-start timestamp is `started_at = time.monotonic()` in
`run_llama_cpp`, set after the optional initial VRAM sample and immediately
before `subprocess.Popen`. It therefore includes process launch, model load,
prompt evaluation, generation, and output receipt in `elapsed_seconds`. The
existing Area 4 evidence records this as
`request_wall_time_boundary: process_launch_to_terminal_output_receipt`.

Because TTFT is blocked at the observation boundary, no new request-start
timestamp is introduced here. Had TTFT been feasible, the architecture would
reuse the exact existing `started_at` timestamp (preferred option A) so TTFT
and request wall time share a common origin.

## Output ownership and prompt echo

Generated model output is **not** the sole owner of the native CLI stdout
stream. The banner and the prompt echo share it:

- `cli-context.cpp:495-496` echoes the prompt unconditionally:
  `buffer = params.prompt; user_turn.echo(buffer);`. `echo` writes
  `\n> <prompt>` to stdout (`cli-ui.h:159-165`).
- `params.display_prompt` is parsed by `--no-display-prompt`
  (`arg.cpp:1490-1496`, field default `true` at `common.h:567`) but is **never
  read** in the `tools/cli/*` code path. Only the separate
  `tools/completion/completion.cpp` tool honors it. LLMGauge passes
  `--no-display-prompt`, and it has no effect in this build's `llama-cli`.
- The ASCII banner is always written before generation
  (`cli-context.cpp:459` `ui::show_message(banner)`).

Detecting the first generated token would therefore require subtracting the
known prompt text and banner from stdout. The milestone treats prompt
subtraction as suspect and a likely blocker, and the raw stream offers no
unambiguous generated-output owner.

## Buffering / flush behavior

Two independent facts are required, and only the host side holds:

- **HOST CAN READ INCREMENTALLY**: proven. The synthetic experiment drains
  stdout and stderr concurrently with no deadlock and exact byte
  preservation.
- **CHILD EMITS INCREMENTALLY**: the `llama-cli` UI flushes after every
  non-empty decoded content piece (`cli-ui.h:223-224`
  `console::log` + `console::flush`, where `console::flush` is
  `fflush(stdout)` at `console.cpp:1163-1165`). So generated content is
  explicitly flushed per piece even to a pipe. However, the banner and prompt
  echo are written without an explicit flush; under a pipe they are
  block-buffered and flushed together with the first generated piece, so the
  "first output byte" is not a reliable generated-token signal even at the
  byte level.

## stdout/stderr concurrency

The server-side diagnostics (load time, prompt-eval, generation TPS) are
logged to stderr; the UI content is on stdout. Any future incremental reader
must drain both concurrently to avoid deadlock. The synthetic experiment
demonstrates the required concurrent-drain pattern with the Python standard
library (a reader thread per stream). Ordering across the two streams is not
guaranteed; they are separate, independent byte streams. This is not a blocker
for TTFT (the blocker is the absence of a token boundary), but it is a
required property of any future streaming collector.

## Raw-output compatibility

The current `communicate()` path preserves the complete stdout and stderr as
the raw artifact. A future streaming collector must reproduce byte-equivalent
stdout and stderr, preserve exit status, timeout/failure/retry evidence, and
produce the same cleaned output. The synthetic experiment confirms exact
byte-equivalence is achievable with incremental reads for a single stream.
Because no streaming collector is implemented in this milestone, current raw
preservation is unchanged.

## Failure / timeout / retry semantics

For a future TTFT (only reachable via a server-backed backend):

- successful output with a proven first token → value with availability;
- empty successful generation, error before first token, timeout before first
  token → `unavailable`, never zero;
- timeout after first token → a partial value is allowed only with a defined
  completion state and never as a clean completion;
- cancellation → no fabricated event;
- malformed output → no token event, `unavailable`;
- every retry/attempt owns its own observation; a later success does not erase
  an earlier unavailable/failed observation.

None of this is implemented here.

## Proposed future evidence ownership

For a future server-backed TTFT, the proposed evidence concept is a transport
observation record owned by the future backend's native execution evidence,
recording:

- `request_started_monotonic_offset`;
- `first_generated_token_elapsed_seconds`;
- `observation_method` (e.g. token-stream version);
- execution/attempt identity and source/backend.

The metric record would live under the accepted `runtime_neutral_metrics`
measurement with `metric_id` `llmgauge.metric.v1.time_to_first_token`,
`provenance=llmgauge_observed` when LLMGauge timestamps the token event
(no token content stored), and `evidence_refs` pointing at the preserved
evidence. This is proposed only; nothing is implemented.

## Schema / fingerprint impact

This milestone changes no schema and no fingerprint. The future TTFT metric
would be an additive record inside the already-admitted
`llmgauge.runtime_neutral_metrics.v1` object, following the existing
measurement structure. Whether a future native execution evidence artifact
already falls under an existing fingerprint payload, or would require a new
fingerprint version, must be decided at the point that a server-backed backend
is admitted; it is flagged as an implementation decision, not changed here.

## Comparison/reporting boundary

Two future TTFT observations may be shown side by side only with disclosed
runtime/backend identity, observation-method version, workload identity, cache
state, context/settings, hardware/device scope, and completion state. TTFT is
not automatically equivalent across differing workloads, cache states, or
backends. No ranking or score. Report concept (future):

```
TTFT           0.842 s
provenance     LLMGauge observed
observation    llama.cpp token-stream v1
cache state    cold
equivalence    unproven
```

and unavailable form:

```
TTFT           unavailable
reason         no first generated token observed
```

## Security / privacy

A future TTFT observation must not be spoofable by model output, diagnostic
output, or the prompt; must not let binary/control output break the parser;
must not create fake token boundaries from partial UTF-8; must not deadlock on
stderr; must kill/reap on timeout; and must not add unbounded output
accumulation, shell execution, secrets, or new paths. These are the standing
requirements for any future implementation. No such collector exists in this
milestone, so there is no new attack surface here.

## Feasibility decision

**NOT CURRENTLY FEASIBLE** through the current native `llama-cli` CLI path.

The required first **generated token** boundary is not observable on the
native CLI's stdout: the stream is decoded-text UI rendering, contaminated by
an unconditional prompt echo and banner, with no machine-readable token
signal. Detecting a first token there would require text heuristics and would
still observe a decoded-text piece, both explicitly blocked by the accepted
semantic boundary. The only native llama.cpp route with a proven token
boundary is the `llama-server` HTTP streaming interface (raw token IDs per
SSE event), which requires a separate server-backed runtime architecture and
is deferred.

## Implementation acceptance gates

A later implementation may be admitted only if all of the following hold (for
the server-backed path, or any future native route that actually exposes a
proven generated-token boundary):

1. Proven first **generated token** boundary.
2. Proven generated-output ownership.
3. No prompt-echo false trigger.
4. No diagnostic false trigger.
5. Incremental child emission under pipe.
6. Concurrent stdout/stderr draining.
7. Exact final raw-output equivalence.
8. Existing cleaned-output equivalence.
9. Existing timeout/exit behavior preserved.
10. Retry behavior preserved.
11. Empty/failure/no-token → `unavailable`.
12. Monotonic timing.
13. Request-start boundary unchanged.
14. Synthetic chunk/coalescing tests.
15. UTF-8 edge tests.
16. No model-text heuristic.
17. No PTY semantic mutation unless explicitly accepted.
18. Historical results unchanged.
19. No new dependency without separate approval.
20. Bounded real-model proof only after later human authorization.
