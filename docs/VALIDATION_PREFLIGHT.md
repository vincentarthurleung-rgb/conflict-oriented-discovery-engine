# External Validation Preflight

Preflight is a read-only readiness audit, not validation and not a pilot. It
lists validators/capabilities, checks schema/manifest/storage presence, cache
availability, SQLite/DuckDB requirements, resource-policy sanity, large-scan
policy, and whether remote clients remain disabled.

```bash
python -m code_engine.cli.validation_preflight \
  --validation-index-dir tests/fixtures/validation_indexes \
  --validation-cache-dir tests/fixtures/validation_cache --json
```

It writes `validation_preflight_report.json` and `.md`. It reads index metadata
and at most bounded samples; it does not scan records or access the network.
Missing optional validators are `not_configured`; malformed configured indexes
make the report `not_ready`. Missing DuckDB is warning-only when no
Parquet/DuckDB index is configured.
