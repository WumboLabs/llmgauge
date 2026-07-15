# vLLM HTTP Transport Assessment

- Status: Accepted
- Accepted: 2026-07-14
- Scope: HTTP transport requirements for the accepted vLLM runtime contract
- Decision type: Architecture, investigation, and dependency admission
- Parent contract: [VLLM_RUNTIME_CONTRACT.md](VLLM_RUNTIME_CONTRACT.md)

## Context

The [accepted vLLM runtime contract](VLLM_RUNTIME_CONTRACT.md) defines an
externally managed, loopback-only, credential-free, text-only, sequential,
non-streaming OpenAI-compatible HTTP client. Dependency admission is a decision,
not a presumed outcome. This assessment answers only whether Python 3.11+
standard-library facilities can satisfy that transport boundary without fragile
or misleading behavior, or whether one explicit third-party HTTP dependency must
be admitted later.

This document admits no runtime dependency, implements no adapter, and changes
no CLI, schema, lockfile, or production code.

Project constraints that bound the decision:

- LLMGauge remains local-first and dependency-light (`pydantic`, `pyyaml`,
  `rich`, `typer` only as of `v0.70.0`).
- `AGENTS.md` requires dependencies only when necessary, lightweight, and
  justified.
- Transport must bypass environment proxies, reject redirects, enforce loopback
  destinations, use bounded connection and request deadlines, avoid silent
  retries, bound response handling, and preserve deterministic failure evidence.

## Decision

**PASS: the Python standard library is admitted for the initial vLLM HTTP
transport.**

No third-party HTTP client is admitted by this decision.

The exact bounded approach is:

1. Prefer `http.client` plus `socket`, `ipaddress`, `urllib.parse`, `json`, and
   existing project `pydantic` validation.
2. Do **not** use default `urllib.request.urlopen` or any opener that inherits
   environment proxy discovery.
3. Parse and validate endpoints with `urllib.parse.urlsplit` before any network
   call.
4. Resolve hostnames with `socket.getaddrinfo`, require every resolved address
   to be loopback via `ipaddress`, then connect to a validated IP literal while
   sending the original host in the HTTP `Host` header.
5. Apply separate bounded connect and whole-request deadlines with monotonic
   wall-clock accounting and remaining socket timeouts.
6. Treat HTTP 3xx as `malformed_response` with bounded detail such as
   `redirect_disallowed`; never follow `Location`.
7. Read response bodies in bounded chunks with an explicit maximum size; decode
   JSON only from that bounded buffer; validate structure with project models.
8. Map exceptions and status classes to the contract failure taxonomy without
   silent retries.
9. Close connections deterministically in `finally` or equivalent context
   cleanup.
10. Test with local loopback fixtures only (`http.server`, temporary sockets, or
    mocks); no external network.

A future dependency may be reconsidered only if implementation proves a
documented security, timeout, cancellation, or maintainability gap that this
assessment did not anticipate. Convenience alone is not sufficient.

## Transport threat model

### Assets

- Operator privacy: home paths, hostnames, usernames, proxy environment values,
  local model paths, and raw endpoint strings must not leak into public artifacts
  or careless error text.
- Evaluation integrity: request timing, failure class, and raw evidence must
  reflect the single attempted request, not hidden retries or redirected trust
  boundaries.
- Local trust boundary: the only permitted destination class is loopback.

### Adversaries and failure modes

| Threat | Required control | Stdlib posture |
|---|---|---|
| Non-loopback endpoint (SSRF / remote exfiltration) | Reject non-loopback after resolution; no remote override in initial adapter | Enforce with `getaddrinfo` + `ipaddress.is_loopback` on every address; connect only to validated IP |
| DNS rebinding / post-validation destination change | Avoid connecting by re-resolved hostname after validation | Connect to validated IP literal; set `Host` from validated URL host |
| Credential URL or auth material | Reject userinfo; never send API keys, cookies, or arbitrary headers | `urlsplit` rejects username/password; fixed minimal headers only |
| Query/fragment smuggling or ambiguous endpoint identity | Reject query and fragment | `urlsplit` validation before connect |
| Environment proxy interception (`HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY`, `NO_PROXY`) | Bypass proxy discovery; never record proxy env values | `http.client` does not consult proxy env; never enable `urllib` proxy handlers |
| Redirect to a new trust boundary | Disable redirect following | `http.client` returns 3xx; adapter must not issue a second request |
| Unbounded wait | Separate connect and whole-request deadlines; timeouts are failures | Socket timeouts + monotonic deadline wrapper |
| Silent retry changing randomness, cache, or token use | No automatic retries | Adapter policy; stdlib does not retry by default |
| Oversized or hostile response body | Bound reads and JSON decode input size | Chunked `read` with max bytes before `json.loads` |
| Malformed JSON / unexpected OpenAI shape | Structural validation after bounded decode | `json` + existing `pydantic` models |
| Exception text leaking proxy URLs, full endpoint, or response headers | Sanitize transport errors and artifact fields | Implementation must format errors; record policy, not env values |
| Connection / FD leaks across sequential prompts | Deterministic cleanup | `close()` in `finally`; one request at a time |
| Operator cancellation misreported as model failure | Distinct `operator_cancellation` class | Map `KeyboardInterrupt` / explicit cancel path separately from transport errors |

Out of scope for this transport decision: TLS policy for remote hosts,
authentication, arbitrary headers, streaming, concurrent clients, connection
pools spanning evaluation identity, and automatic server lifecycle.

## Standard-library capability findings

Assessment target: CPython 3.11+ (project requires `requires-python = ">=3.11"`).
Local probes used the repository host interpreter and loopback-only fixtures.

| Requirement | Stdlib capability | Verdict |
|---|---|---|
| Parse and validate HTTP endpoint URLs | `urllib.parse.urlsplit` exposes scheme, host, port, path, query, fragment, username, password | Sufficient |
| Reject credentials, query, fragments, unsupported schemes | Explicit checks on `urlsplit` result; allow only `http` for the initial contract | Sufficient |
| Resolve `localhost` / hostnames to loopback-only | `socket.getaddrinfo`; classify with `ipaddress.ip_address(...).is_loopback` | Sufficient when every address is checked |
| IPv4 and IPv6 loopback | `127.0.0.0/8` and `::1` classified as loopback; HTTP hosts may use bracketed IPv6 form | Sufficient with careful host formatting |
| Reduce DNS rebinding / destination swap | Resolve → validate all → connect to IP + `Host` header | Sufficient for the initial local boundary |
| Bypass `HTTP_PROXY` / `HTTPS_PROXY` / `ALL_PROXY` / `NO_PROXY` | Default `urllib.request.urlopen` consults env proxies (observed: request failed against a dead proxy while loopback server was healthy). `http.client` does not use proxy env vars | Sufficient **if** `http.client` is required and default `urlopen` is forbidden |
| Disable redirects | `http.client` returns 3xx without following; probed local 302 left body unread as redirect | Sufficient with explicit non-follow policy |
| Separate bounded connection and whole-request deadlines | No single high-level multi-timeout object; achievable with `socket.create_connection(..., timeout=connect_timeout)` then remaining monotonic budget applied via `socket.settimeout` for send/recv | Sufficient with a thin deadline helper; not a security gap |
| Cancellation / interruption | Blocking socket I/O raises `KeyboardInterrupt` on SIGINT; closing a socket from a controlling path unblocks waits | Sufficient for sequential CLI evaluation; not equivalent to async cancel tokens |
| Bounded request and response bodies | Control request bytes; read response with max size and optional `Content-Length` pre-check | Sufficient |
| Bounded JSON decoding and structural validation | `json.loads` on bounded bytes; project already depends on `pydantic` | Sufficient |
| Deterministic transport-error classification | Map `TimeoutError`, `ConnectionRefusedError`, `ConnectionResetError`, `BrokenPipeError`, `OSError`, incomplete reads, and HTTP status classes explicitly | Sufficient |
| Connection cleanup | `HTTPConnection.close()` and socket close in `finally` | Sufficient |
| Deterministic unit tests with local fixtures only | `http.server` on `127.0.0.1`, temporary sockets, mocks; no package install | Sufficient |
| Avoid leaking credentials, proxy env, raw URLs, headers, full bodies into artifacts/errors | No automatic redaction; requires explicit sanitizers aligned with the contract endpoint identity fields | Sufficient when implemented deliberately |

### Limitations that were considered and rejected as dependency justifications

| Limitation | Why it does not force a third-party client |
|---|---|
| No first-class connect/read/write/pool timeout object (unlike some third-party clients) | A small monotonic deadline helper is ordinary, reviewable code and matches sequential single-request use |
| `urllib.request` proxy and redirect defaults are unsafe if used naively | Avoiding those defaults is simpler and clearer than adding a dependency to re-disable them |
| Manual `Host` header when connecting to IP literals | Required for honest loopback binding; third-party clients still need equivalent SSRF controls |
| Lower-level response parsing than a polished client API | Request volume is one non-streaming JSON POST/GET at a time; complexity stays bounded |
| Cancellation is socket/SIGINT based rather than structured async cancel | LLMGauge CLI evaluation is synchronous and sequential under this contract |
| Custom code must sanitize errors and artifacts | True for any client; libraries do not remove the product redaction duty |

No stdlib limitation was found that:

- necessarily violates the accepted security boundary when the bounded approach
  above is followed;
- makes timeout or cancellation semantics materially unreliable for sequential
  local requests;
- requires excessive custom networking beyond a focused transport helper;
- makes deterministic local testing impractical; or
- introduces unclear maintenance or compatibility risk relative to adding an
  HTTP stack and its transitive graph.

## Dependency-admission recommendation

**No third-party HTTP dependency is recommended.**

Packages commonly considered for convenience (`httpx`, `requests`, `urllib3`)
were evaluated only as alternatives, not as admissions:

| Concern | Finding relative to this contract |
|---|---|
| Demonstrated gap requiring admission | None after stdlib capability review |
| Proxy behavior | Still require explicit trust-env / proxy disable; wrong default remains a footgun |
| Redirects | Still require explicit disable |
| Loopback / SSRF policy | Still require custom URL and resolution guards |
| Timeouts | Richer APIs, but not required for one sequential non-streaming call |
| Transitive graph / supply chain | Additional packages and update surface for no new security property |
| Offline / packaging | Extra install weight for clean clones without improving local-first policy |
| Replacement cost | Higher once code and tests couple to client-specific APIs |

If a later milestone discovers a concrete stdlib gap, the candidate for
re-evaluation should be documented against this assessment with the exact failing
requirement. Until then, do not add an HTTP client “just in case.”

## Explicit standard-library PASS criteria

This assessment records **PASS** for standard-library use when the future
adapter implements all of the following non-negotiables:

1. Module boundary uses `http.client` + `socket` + `ipaddress` + `urllib.parse`
   (and project validation libraries already admitted), not default
   `urllib.request` proxy-aware openers.
2. Endpoint validation rejects non-`http` schemes, userinfo, query, and fragment.
3. Every resolved address is loopback before connect; connect target is the
   validated IP; `Host` carries the validated host/port identity.
4. Environment proxy variables are never read for routing and never written into
   artifacts; only a proxy-bypass policy flag or constant may be recorded.
5. Redirects are never followed.
6. Connect timeout and whole-request deadline are both enforced; expiry maps to
   `endpoint_unavailable` or `request_timeout` as appropriate.
7. No automatic retries of evaluation requests.
8. Response body input to JSON parsing is size-bounded.
9. Failures map into the contract taxonomy with bounded detail and sanitized
   endpoint identity.
10. Tests prove proxy bypass, redirect non-follow, loopback rejection, timeout
    classification, and body bounds using only local fixtures.

## Consequences

- Later implementation can proceed without a dependency-admission PR.
- Transport code will be slightly more explicit than a high-level client call;
  that explicitness is desirable at a security and evidence boundary.
- Reviewers should treat any proposal to introduce `httpx`/`requests` as a
  change to this decision, not as routine implementation detail.
- Remote TLS, auth, streaming, and concurrent transport remain deferred with the
  parent contract.

## Follow-on milestone

**Exact next milestone:** implement the externally managed vLLM adapter under the
parent contract, using only the standard-library transport approach accepted
here, plus additive schema, validator, report, and public-export work as needed
for that adapter. Do not manage the server lifecycle. Do not admit an HTTP
dependency unless a new documented gap forces a dedicated admission milestone.
