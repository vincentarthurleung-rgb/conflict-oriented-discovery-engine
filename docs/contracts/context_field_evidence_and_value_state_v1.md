# Context Field Evidence and Value State v1

Every Context field preserves `raw_text`, `provider_value`,
`extracted_value`, and `canonical_value` as distinct layers. Rejection or
normalization cannot erase the earlier layers. Provider offsets are candidates;
only a unique exact resolver bound to authoritative source bytes may issue
authoritative offsets.

Value states are `present`, `explicitly_absent`, `not_mentioned`,
`not_extracted`, `unknown`, `ambiguous`, `not_applicable`, `invalid`,
`unavailable`, and migration-only `legacy_null_unresolved`. `not_mentioned`
requires a sufficient source audit, `not_applicable` requires scope basis, and
`explicitly_absent` requires direct negative evidence.

