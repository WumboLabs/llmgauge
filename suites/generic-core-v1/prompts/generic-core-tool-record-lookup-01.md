# Declared archive-record lookup

## Task

Select exactly one tool from the supplied catalog and emit its structured arguments for the user request. The catalog is a declaration only. Do not invoke a tool. Do not claim that a lookup ran or succeeded.

## User request

Find archive record NQ-204 in the north-quay collection. I only need the current record, not its history.

## Tool catalog

### lookup_archive_record

Use this tool to request one archive record.

Arguments:

- `collection` (string, required): the collection name
- `record_id` (string, required): the record identifier
- `include_history` (boolean, required): true only when historical revisions are requested

### list_archive_collections

Use this tool to list collection names at a site.

Arguments:

- `site` (string, required): the site name

### write_archive_note

Use this tool to attach a note after a record has already been retrieved.

Arguments:

- `record_id` (string, required)
- `note` (string, required)

## Selection rules

- Choose exactly one tool.
- Use `lookup_archive_record` for a single known record identifier.
- Set `include_history` to false when the user asks only for the current record.
- Do not invent a tool.
- Do not include undeclared argument names.
- Do not add a field that claims execution, success, or a returned record.

## Response form

Emit only this JSON object and nothing else:

```
{"tool": "<tool_name>", "arguments": {<declared arguments>}}
```

No markdown fences, no prose, and no second request. This is a native-response preparation task. No tool will be called and no archive will be read.
