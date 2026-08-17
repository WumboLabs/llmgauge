# Window-average defect review

## Task

Review the supplied function against the supplied specification and examples. Identify material defects with evidence from the code. Connect each defect to an observable consequence. Prioritize by severity. Recommend bounded corrections. Do not rewrite unrelated code. Do not rely on execution.

## Specification

`window_average(values, width)` should return the arithmetic mean of every inclusive contiguous window of exactly `width` integers, in source order.

- `values` is a list of integers.
- `width` is a positive integer.
- If `values` is empty, return `[]`.
- If `width` is less than 1, raise `ValueError`.
- If `width` is greater than `len(values)`, raise `ValueError`.
- The function must not mutate `values`.
- Each result item is a float: the sum of that window divided by `width`.

## Examples

- `window_average([2, 4, 6], 2)` should return `[3.0, 5.0]`
- `window_average([10], 1)` should return `[10.0]`
- `window_average([], 3)` should return `[]`
- `window_average([1, 2], 0)` should raise `ValueError`
- `window_average([1, 2], 3)` should raise `ValueError`

Python list slicing is inclusive on the start index and exclusive on the stop index. Integer division is not required; the specification asks for ordinary float division.

## Supplied code

```python
def window_average(values, width):
    values.append(0)
    result = []
    for i in range(len(values) - width):
        total = 0
        for j in range(width - 1):
            total += values[i + j]
        result.append(total / width)
    return result
```

## Response form

Write a prioritized review. For each material defect, cite the code and the contract it violates, state an observable consequence using the examples when possible, and recommend a bounded correction. Do not supply a full rewrite of an unrelated function. Do not claim the function was executed. This is a text-only review.
