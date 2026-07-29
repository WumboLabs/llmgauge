# State-transition defect

## Task

Diagnose the defect in the supplied `Job.finish` implementation and provide a bounded correction. Explain the violated transition contract, use the trace as evidence, and distinguish the explicitly unknown callback-failure behavior from observed facts.

## Supplied inert context

Everything below is prompt-owned text. It is not a live repository or importable module.

Transition contract:

- A job starts in `READY`; `start()` moves it to `RUNNING`.
- `finish(value)` is valid only in `RUNNING`. Before a success notification is delivered, it must atomically set `value` and move the job to `SUCCEEDED`.
- A notification callback receives the job and event name and must observe the post-transition state.
- Terminal states are immutable.
- The callback API excerpt does not say whether callbacks may raise or what `finish` should do if one raises. That behavior is unknown and must not be invented.

Supplied code:

```python
from enum import Enum
from typing import Callable


class State(Enum):
    READY = "ready"
    RUNNING = "running"
    SUCCEEDED = "succeeded"


class Job:
    def __init__(self, notify: Callable[["Job", str], None]) -> None:
        self.state = State.READY
        self.value: str | None = None
        self._notify = notify

    def start(self) -> None:
        if self.state is not State.READY:
            raise ValueError("job is not ready")
        self.state = State.RUNNING

    def finish(self, value: str) -> None:
        if self.state is not State.RUNNING:
            raise ValueError("job is not running")
        self.value = value
        self._notify(self, "succeeded")
        self.state = State.SUCCEEDED
```

Complete supplied trace from a callback that records its inputs and returns normally:

```text
before finish: state=RUNNING value=None
callback: event=succeeded state=RUNNING value=artifact-7
finish returned normally
before second finish: state=SUCCEEDED value=artifact-7
second finish: ValueError: job is not running
```

Available evidence is limited to this contract, code, and complete trace. There is no live reproduction, dependency documentation, or test runner. Changing `start`, adding retry behavior, swallowing callback exceptions, or redesigning the state model is out of scope.

## Response form

Use the `coding-core-explanation-plus-code-form-v0` `0.1.0` boundary: prose diagnosis followed by exactly one fenced `python` code block containing only the corrected `finish` method. Do not include a patch, tests, a second code block, or claims that the correction was run.

Your proposed code and explanation are response text only. They will not be imported, applied, or executed.
