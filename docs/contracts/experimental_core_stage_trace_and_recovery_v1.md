# Experimental Core Stage Trace and Recovery v1

The stage trace covers raw Provider response, parsed candidate, schema-valid
L1, deterministic validation, fulltext v3, evidence projection, extraction
asset revision, and context/downstream consumer view. Each stage records core
counts, field status, evidence count, and payload hash.

First-loss diagnosis reports the first nonempty-to-empty transition. Missing
raw lineage remains `raw_unavailable` or `legacy_lineage_unavailable`; it is not
misreported as Provider omission.

Recovery order is existing structured fields, parsed payload, validated
observation, fulltext v3, evidence projection, authoritative raw response, then
explicit local-reference reconstruction. Each recovery is an immutable
revision. Claim prose, context, domain knowledge, text similarity, and
downstream conflict pairs are prohibited recovery sources.

