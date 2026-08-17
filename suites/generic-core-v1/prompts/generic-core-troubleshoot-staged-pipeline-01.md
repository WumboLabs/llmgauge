# Staged-pipeline diagnosis

## Task

Diagnose the inconsistent counts in the supplied three-stage pipeline. Separate observations from hypotheses. Rank the remaining plausible causes. Propose the safest next checks that would distinguish those causes. Do not claim a single root cause unless the observations leave only one. Do not recommend destructive repair before diagnosis. Do not claim any check has been run.

## Pipeline

```
Intake -> Normalize -> Publish
```

- Intake accepts a card record if it has a non-empty `card_id` and a payload string.
- Normalize lowercases keys and rejects a record that lacks `card_id` after that step.
- Publish writes only records that Normalize accepted and that have a checksum matching the payload bytes.

## Stage invariants

| stage | invariant |
| --- | --- |
| Intake | Count of accepted records equals the number of input records with a non-empty `card_id`. |
| Normalize | Count of accepted records never exceeds Intake accepted. Rejected records keep their original payload. |
| Publish | Count of published records equals Normalize accepted records whose checksum matches the payload. |

## Symptoms

Today's batch report says Intake accepted 12, Normalize accepted 12, and Publish wrote 10. Two published records have a checksum warning in the report. No record was deleted by an operator.

## Observations

- OBS-1: The intake file lists 12 records with non-empty `card_id` values NQ-01 through NQ-12.
- OBS-2: Normalize wrote 12 accepted rows. None of those rows is missing `card_id`.
- OBS-3: Publish wrote 10 rows. NQ-04 and NQ-11 are absent from the published file.
- OBS-4: The report marks NQ-04 and NQ-11 with `checksum_mismatch`.
- OBS-5: The payload for NQ-04 in Normalize output differs by one trailing space from the intake payload.
- OBS-6: The laptop clock was set back five minutes at lunch. Several log lines show that clock change.

## Irrelevant log lines

- LOG-A: `printer tray empty`
- LOG-B: `volunteer Nia refilled the kettle`
- LOG-C: `screensaver started on the unused kiosk`

## Response form

State what is known, what remains unknown, and the remaining plausible causes. Propose the smallest safe checks that would distinguish those causes. Do not invent environment state beyond the notes. Do not recommend deleting records, rewriting the store, or rerunning a live system. This is a text-only diagnosis. Nothing will be executed.
