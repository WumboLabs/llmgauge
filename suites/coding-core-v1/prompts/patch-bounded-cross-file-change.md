# Bounded cross-file patch

## Task

Return one minimal patch that adds support for an optional `request_timeout_ms` configuration key. Modify only the two allowed paths. Preserve all unrelated behavior and resist the adjacent cleanup opportunities.

## Supplied inert repository context

The tree, files, and observations below are prompt-owned text, not a live repository.

```text
src/
  config.py
  legacy_logging.py
tests/
  test_config.py
  test_legacy_logging.py
```

`src/config.py`:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class ClientConfig:
    endpoint: str
    retries: int = 2
    request_timeout_ms: int = 1000


def load_client_config(raw: dict[str, object]) -> ClientConfig:
    endpoint = raw.get("endpoint")
    if not isinstance(endpoint, str) or not endpoint:
        raise ValueError("endpoint must be a non-empty string")
    retries = raw.get("retries", 2)
    if not isinstance(retries, int) or isinstance(retries, bool) or retries < 0:
        raise ValueError("retries must be a non-negative integer")
    return ClientConfig(endpoint=endpoint, retries=retries)
```

`tests/test_config.py`:

```python
import pytest

from src.config import ClientConfig, load_client_config


def test_load_client_config_uses_defaults() -> None:
    assert load_client_config({"endpoint": "local"}) == ClientConfig(endpoint="local")


def test_load_client_config_rejects_negative_retries() -> None:
    with pytest.raises(ValueError, match="retries must be a non-negative integer"):
        load_client_config({"endpoint": "local", "retries": -1})
```

`src/legacy_logging.py` contains an unrelated `# TODO: replace print calls` and `tests/test_legacy_logging.py` has duplicated setup. Neither affects this request.

Required behavior:

- Missing `request_timeout_ms` keeps the dataclass default of `1000`.
- An explicit value is accepted only when it is an integer from `1` through `60000`, inclusive. Booleans are not integers for this contract.
- Invalid values raise `ValueError` with exactly `request_timeout_ms must be an integer from 1 through 60000`.
- Existing endpoint and retry behavior stays unchanged.
- Add focused tests for the accepted boundaries and representative invalid values.

Allowed paths are exactly `src/config.py` and `tests/test_config.py`. Do not edit logging files, rename fields, add dependencies, refactor existing validation, or change exception types or existing messages. The supplied facts are complete; no shell, repository, formatter, or test runner is available.

## Response form

Use `coding-core-bounded-patch-form-v0` `0.1.0`: output only one bounded patch envelope from `*** Begin Patch` through `*** End Patch`. It may contain `*** Update File:` sections only for the two allowed paths and unified hunks beginning with `@@`. Do not add prose or Markdown fences.

The patch is response text only. It will not be applied, imported, compiled, executed, or tested.
