# Extraction Field Evidence and Value State v1

Each important field keeps `raw_text`, `provider_value`/`extracted_value`, and
`canonical_value` separately. Normalization and rejection never overwrite the
first two. Anchor IDs and precision, validation state, rejection reasons, and
normalization identity are sidecar metadata.

New values use `present`, `explicitly_absent`, `not_mentioned`,
`not_extracted`, `unknown`, `ambiguous`, `not_applicable`, `invalid`, or
`unavailable`. `not_mentioned` requires source audit; provider omission is not
enough. `not_applicable` requires a scope basis. `legacy_null_unresolved` is
migration-only and preserves the ambiguity of old nullable fields.

Historical anchor reconstruction is exact-substring, unique-match, Unicode-NFC
and source-hash bound. Fuzzy matching has no authority.
