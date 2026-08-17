# Audience-calibrated cache explanation

## Task

Explain the supplied Stamp-Check Cache protocol to a reader who is comfortable with ordinary files but is not a cache specialist. Include why the identity check prevents a stale read. Include the one disclosed tradeoff. Use the supplied terms consistently. Do not add facts from other systems.

## Audience

A volunteer archivist who understands folders and filenames, not networking or cache products.

## Protocol definition

Stamp-Check Cache stores each object under a stable name and a content stamp.

- The *name* is the object's public label, such as `card-17`.
- The *content stamp* is a short value computed from the current bytes. If the bytes change, the stamp changes.
- A *reader* that already has a copy sends the name and the stamp it currently holds.
- The *identity check* compares the reader's stamp with the store's current stamp for that name.
- If the stamps match, the store answers `unchanged` and sends no bytes.
- If the stamps differ, the store sends the current bytes and the new stamp.
- The store never answers `unchanged` when the stamps differ.

## Sequence

1. The store holds `card-17` with stamp `S1`.
2. The reader holds a copy with stamp `S1`.
3. A clerk replaces the bytes of `card-17`. The store now holds stamp `S2`.
4. The reader asks for `card-17` and presents stamp `S1`.
5. The identity check sees `S1` is not `S2`, so the store sends the new bytes and `S2`.

If step 5 were skipped and the store answered `unchanged` from the name alone, the reader would keep the old bytes after the clerk's replacement. That is the stale-read case this protocol is designed to prevent.

## Disclosed tradeoff

The identity check adds one stamp comparison to every read, including reads that return `unchanged`. The protocol accepts that extra comparison in exchange for refusing stale reads.

## Response form

Write a short explanation in ordinary language. Cover the mechanism, the causal link from the identity check to the avoided stale read, and the disclosed tradeoff. Do not describe a real product or a different cache. This is a text-only explanation. Nothing will be cached or executed.
