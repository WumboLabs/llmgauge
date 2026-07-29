# Closed-evidence API integration

## Task

Implement the bounded `deliver` function using only the supplied versioned API evidence. Explain the integration choices and identify the one evidence gap without filling it from external knowledge.

## Supplied inert context

All package documentation, dependency declarations, and source below are prompt-owned text. The package is not installed and no network or external documentation is available.

Dependency declaration:

```text
packetbox==2.4.0
```

Closed API excerpt for `packetbox` `2.4.0`:

```text
class Client:
    def send(self, payload: bytes, *, timeout_ms: int) -> Receipt

Client.send sends exactly one payload. timeout_ms must be an integer from 1
through 5000. It raises PacketTimeout when no receipt arrives before the
specified timeout. Other transport failures raise PacketError.

class Receipt:
    status: Literal["accepted", "rejected"]
    identifier: str | None

An accepted receipt has a non-empty identifier. A rejected receipt has
identifier None. The API excerpt does not state whether Client instances are
safe for concurrent calls.
```

Existing integration surface:

```python
from packetbox import Client, PacketError, PacketTimeout


class DeliveryRejected(RuntimeError):
    pass


def deliver(client: Client, message: str) -> str:
    """Send one UTF-8 message, returning its accepted receipt identifier."""
    raise NotImplementedError
```

Required behavior:

- Encode `message` as UTF-8 and call `client.send` exactly once with `timeout_ms=750`.
- Return the non-empty identifier for an accepted receipt.
- Raise `DeliveryRejected("packet was rejected")` for a rejected receipt.
- Let `PacketTimeout` and `PacketError` propagate unchanged.
- Do not add retries, logging, global state, validation beyond the supplied receipt contract, or concurrency controls.
- The only explicit evidence gap is client thread safety. State that it remains unknown and that this function makes no concurrency guarantee.

No live call, import, type check, or test run is possible. Do not claim compatibility with versions other than `2.4.0`.

## Response form

Use `coding-core-explanation-plus-code-form-v0` `0.1.0`: concise prose followed by exactly one fenced `python` code block containing only the completed `deliver` function. Do not repeat imports, classes, tests, or surrounding module code.

The proposed function is response text only. It will not be imported, called, or executed.
