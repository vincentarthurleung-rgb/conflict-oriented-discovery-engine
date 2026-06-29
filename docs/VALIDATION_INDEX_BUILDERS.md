# Validation Index Builders

Builders convert bounded JSONL, CSV, or TSV sources into the formal index
directory. They stream records, validate required fields, write normalized
JSONL, and produce schema and manifest files. They do not download sources or
load a full table with pandas.

```bash
python -m code_engine.cli.build_validation_index \
  --validator reactome \
  --source tests/fixtures/validation_sources/reactome_small.jsonl \
  --output-dir /tmp/code_validation_indexes/reactome --dry-run
```

Dry-run estimates record and field coverage and writes planned metadata, but
not records. Inputs over the conservative source-size limit are blocked unless
`--allow-large-source` is explicit. That opt-in does not disable per-record
streaming or query-time resource guards.
