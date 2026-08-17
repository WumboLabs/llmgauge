# Grounded ledger extraction

## Task

Extract the posted ledger entries into one JSON object. Copy present values exactly. Use JSON `null` only where the source marks a value absent. Ignore notes and voided lines. Preserve source order of posted entries.

## Field meanings

- `entry_id`: the posted identifier
- `amount`: the posted numeric amount
- `currency`: the posted currency code
- `approved_by`: the named approver, or `null` when the source leaves approval blank

## Ledger

Posted L-17 amount 42.5 currency CRD approved_by Mira
Note (ignore): the clerk used a green pen.
Posted L-18 amount 8 currency CRD approved_by [absent]
Voided L-19 amount 3 currency CRD approved_by Nia — do not extract voided lines
Note (ignore): leftover tea on the counter.
Posted L-21 amount 105.25 currency CRD approved_by Tomas
Note (ignore): Tomas prefers morning review.

## Declared schema

Return a single JSON object with one key, `entries`, whose value is an array of objects. Each object has exactly:

- `entry_id`: string
- `amount`: number
- `currency`: string
- `approved_by`: string or null

Do not add other keys. Do not infer a missing approver. Do not include voided or note lines.

## Response form

Emit only the JSON value. No markdown fences or prose. This is a closed extraction mapping. Nothing will be posted or executed.
