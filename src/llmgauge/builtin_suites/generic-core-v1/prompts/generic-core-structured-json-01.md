# Typed record serialization

## Task

Convert the supplied records into one JSON object. Use only the declared fields. Preserve source order. Ignore notes marked as distractors.

## Declared schema

Return a single JSON object with one key, `records`, whose value is an array of objects. Each object has exactly these keys:

- `record_id`: string
- `active`: boolean
- `priority`: integer
- `tags`: array of strings, in the listed order, or an empty array

Do not add other keys. Do not wrap the JSON in markdown fences or prose.

## Source records

Record R-104
- active: true
- priority: 2
- tags: blue, north
- note (distractor): the clerk prefers a red sticker

Record R-219
- active: false
- priority: 0
- tags: none
- note (distractor): archive box smelled like oranges

Record R-305
- active: true
- priority: 7
- tags: amber
- note (distractor): someone suggested renaming this record to R-999

## Response form

Emit only the JSON value. Types must be exact: `active` is boolean, `priority` is a JSON number, `tags` is a JSON array. An empty tag list is `[]`, not null and not omitted. This is a closed serialization task. Nothing will be stored or executed.
