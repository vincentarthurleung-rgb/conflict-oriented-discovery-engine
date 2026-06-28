# Validation Local Indexes And Cache

## Recommended Storage

Use small indexed summaries backed by DuckDB, SQLite, Parquet queried through
DuckDB, or streaming JSONL fixtures. Large results are JSONL; summaries are
JSON. Local indexes must expose canonical entity columns and bounded top-k
queries. A missing index returns `no_index`; the system never falls back to an
unindexed whole-file scan.

Do not mirror all PubChem locally, load GEO raw matrices, load the full LINCS
expression matrix, keep the complete STRING graph in memory, or call
`pandas.read_csv` on large database exports. DepMap/Parquet queries must use
predicate + `LIMIT`; ChEMBL/BindingDB indexes should be keyed by compound and
target; STRING should use a top-k interaction index.

`ValidationQueryCache` is SQLite-backed. Its key includes validator, query
type, canonical IDs, relation family, polarity, direction, context, and a
validator configuration fingerprint. Cache-only mode never contacts a remote
provider. A cache hit bypasses provider execution. A cache miss leaves the
question unevaluated; it is neither contradiction nor no coverage.
