# Source Snapshot v1

`source_snapshot_v1` is the immutable text actually supplied to an extraction
call, not a later reconstruction and not merely a block identifier. A complete
record includes the text, its SHA-256, source-file identity/hash, block/window
metadata, scope, and provenance. Absolute paths are excluded from canonical
identity.

Legacy records without the sent text are `incomplete`; the audit does not fetch
or fabricate it. Reparse and anchor validation reuse the same snapshot identity.
