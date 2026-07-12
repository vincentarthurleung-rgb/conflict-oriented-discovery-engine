# System A → C.O.D.E. Atlas Handoff Protocol

`atlas_handoff_v1` is the file boundary between the scientific pipeline and Atlas. System A owns scientific artifacts and never writes Atlas SQLite or calls Flask. Atlas is an offline, read-only consumer and never calls an LLM during ingestion.

A completed run publishes `artifacts/atlas_handoff_manifest.json` first and `artifacts/ATLAS_READY` last. Both are written through a temporary file, fsynced, and switched with `os.replace`. The marker contains the schema version and exact manifest SHA-256. Repeating publication of identical bytes is a no-op.

The manifest identifies the case, source run, prediction/profile/adapter versions, relative lineage, git/configuration provenance, timestamps, lane counts, and each artifact's relative path, SHA-256, byte size, JSONL record count, and required flag. Absolute paths, backslashes, `..`, paths outside the allowed run root, malformed JSON/JSONL, hash mismatch, unknown schema, incomplete status, and lane-accounting mismatch are rejected. Optional missing artifacts are reported; required missing artifacts block publication.

The v5 invariant is:

`input = core_seed_relation + seed_neighborhood_mechanism + reviewable_context_relation + off_seed_relation`

Exploratory and formal-conflict eligibility are recomputed from the re-entry audit. A partial or failed run never receives `ATLAS_READY`.

Future natural-language scheduling should launch System A and then reuse this exact publish/sync boundary; it must not bypass it with direct database or Flask writes.
