# Inclusive interval-merge function

## Task

Implement one pure function named `merge_intervals` in the declared Python 3.11 subset. Return only the function definition. Do not mutate the input. Do not use the network or a third-party package. Do not execute the function.

## Language subset

- Python 3.11
- Standard library only
- One function definition and nothing else
- No module docstring, no tests, no example calls, no `if __name__` block

## Specification

`merge_intervals(intervals)` takes a list of inclusive integer intervals. Each interval is a two-item list `[start, end]` where `start` and `end` are integers and `start <= end`.

Behavior:

- Overlapping or touching intervals merge into one interval.
- Touching means inclusive endpoints meet, so `[1, 3]` and `[3, 6]` become `[1, 6]`.
- Nested intervals collapse into the outer interval.
- The result is a new list of disjoint intervals sorted by increasing start.
- An empty input returns `[]`.
- The input list and its nested lists must be left unchanged.
- Raise `ValueError` if any item is not a two-item list of integers, or if `start > end`.

## Examples

- `[]` → `[]`
- `[[1, 2], [5, 7]]` → `[[1, 2], [5, 7]]`
- `[[1, 4], [3, 8]]` → `[[1, 8]]`
- `[[1, 3], [3, 6]]` → `[[1, 6]]`
- `[[2, 10], [4, 5], [6, 9]]` → `[[2, 10]]`
- `[[8, 10], [-3, -1], [0, 4], [-1, 1]]` → `[[-3, 4], [8, 10]]`
- `[[4, 6], [4, 6], [6, 9]]` → `[[4, 9]]`
- `[[5, 2]]` → `ValueError`
- `[[1, 2.5]]` → `ValueError`
- `[[1, 2, 3]]` → `ValueError`

Bounded local cases exist for later inspection. They will not be run against this response.

## Response form

Return only one fenced `python` code block that contains the function definition. Do not claim the function was tested, imported, or executed. Generated code will not be executed in this evaluation.
