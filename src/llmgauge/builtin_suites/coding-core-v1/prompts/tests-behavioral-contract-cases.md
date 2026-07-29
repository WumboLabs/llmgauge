# Behavioral contract test cases

## Task

Write focused pytest tests for the supplied `SequenceGate` interface. Test observable state transitions and failure sensitivity, not private attributes or implementation plumbing.

## Supplied inert context

This interface and contract are prompt-owned text. They are not installed code.

```python
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class Decision:
    outcome: Literal["accepted", "duplicate"]
    last_accepted: int


class SequenceGate:
    def accept(self, sequence: int) -> Decision:
        """Process one sequence number according to the contract below."""
```

Behavioral contract:

1. A new gate has no accepted sequence. Its first call accepts any non-negative integer and returns `Decision("accepted", sequence)`.
2. After accepting `n`, a call with `n + 1` is accepted and advances the last accepted value.
3. A call with exactly the last accepted value returns `Decision("duplicate", last_accepted)` and does not advance state.
4. A negative first value, a value lower than the last accepted value, or a forward gap larger than one raises `ValueError` with message `sequence is out of order`.
5. A rejected call does not change state. A subsequent valid next value must still be accepted.
6. `bool` values are rejected with the same `ValueError`; although `bool` is an `int` subtype in Python, it is not a sequence number in this contract.
7. Inputs outside these cases and concurrency behavior are unspecified.

Assume the production class is imported as:

```python
from sequence_gate import Decision, SequenceGate
```

Available evidence is limited to the interface and contract. Do not invent private members, serialization, concurrency, or performance requirements. Do not reproduce a possible implementation inside the tests. There is no live module, test collector, or runner.

## Response form

Use `coding-core-code-only-tests-form-v0` `0.1.0`: return exactly one fenced `python` code block containing only a complete pytest test module. No prose is allowed before or after it, and no second code block is allowed.

The generated test module is response text only. It will not be imported, collected, or executed.
