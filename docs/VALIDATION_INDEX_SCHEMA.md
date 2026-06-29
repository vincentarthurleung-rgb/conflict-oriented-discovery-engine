# Validation Index Schema

This is infrastructure hardening before any pilot. A local validator index is
an explicit directory, not an arbitrary database file:

```text
<index-root>/<index-name>/
  schema.json
  manifest.json
  records.jsonl | records.sqlite | records.parquet | records.duckdb
  README.md                         # optional
```

`schema.json` defines required/optional fields, query/entity/relation support,
keys, direction and score fields, and interpretation limits. `manifest.json`
binds one build to that schema and records source version, builder version,
record/field counts, storage path, checksum, and warnings. Schemas currently
use version `1.0.0` and live in `configs/validation/index_schemas/`.

The planner loads both files and checks validator name, index name, schema
version, storage format, and a sample record before allowing local execution.
Missing metadata, required fields, or version mismatch makes the index
unavailable. Flat legacy JSONL files are not executable through the primary
planner. No large database belongs in Git.
