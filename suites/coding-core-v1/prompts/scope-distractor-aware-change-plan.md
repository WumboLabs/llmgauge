# Distractor-aware change plan

## Task

Produce a narrow change plan for the requested CSV-export correction. Name the files and behavioral checks needed, preserve explicit non-goals, and call out unknowns that must be resolved before editing. Do not provide patch text or implementation code.

## Supplied inert repository context

The tree and excerpts below are prompt-owned text, not a live repository.

```text
src/
  csv_export.py
  json_export.py
  cli.py
tests/
  test_csv_export.py
  test_json_export.py
docs/
  export-format.md
```

Requested change:

`export_rows` currently emits bare fields. Change only CSV export behavior so fields containing a comma, double quote, carriage return, or newline follow RFC-style CSV quoting: surround the field with double quotes and double each embedded double quote. Preserve row order, column order, the existing comma delimiter, and the existing `\n` row terminator.

Supplied interface and current behavior:

```python
def export_rows(rows: list[list[str]]) -> str:
    return "".join(",".join(row) + "\n" for row in rows)
```

`tests/test_csv_export.py` currently covers plain fields and empty input. `docs/export-format.md` says CSV uses comma-separated text but does not specify escaping.

Adjacent facts and distractors:

- `src/json_export.py` sorts object keys despite a comment saying insertion order; this is unrelated.
- `src/cli.py` has duplicated error formatting; this is unrelated.
- `tests/test_json_export.py` uses a deprecated assertion helper; this is unrelated.
- The requested change does not authorize a CSV library dependency, delimiter options, streaming, CLI changes, JSON changes, or broad export refactoring.
- Whether a zero-field row should emit `\n` or no output is not specified by the supplied contract. Existing behavior emits `\n`; preserve it unless the owner separately changes the contract.

Allowed production path: `src/csv_export.py`.
Allowed focused test path: `tests/test_csv_export.py`.
Documentation may change only if the plan explains why the established output contract must be recorded in `docs/export-format.md`.

No repository search, dependency documentation, formatter, or test runner is available. Proposed steps and checks must remain bounded to supplied facts.

## Response form

Use `coding-core-explanation-only-form-v0` `0.1.0`. Return a prose plan under exactly these headings, in order: `Scope`, `Files and changes`, `Behavioral checks`, `Unknowns and stop conditions`, and `Explicit non-goals`. Fenced code blocks, patch hunks, and implementation code are forbidden.

The plan is review text only. Nothing will be applied or executed.
