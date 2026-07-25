# Structured Experimental Observation Revision v1

This immutable sidecar revision references the source parsed, validated,
fulltext-v3, projection, context, and evidence-chain identities. It contains
only IDs of factor, measurement, result, and linkage records; scientific
conflict-derived fields are forbidden.

A historical observation may have multiple revisions linked by
`supersedes_revision_id`. Formal experimental types reject empty measurement or
result IDs. Interventional and observational-comparison types also reject empty
factor IDs. Descriptive measurement uses an explicit policy exemption rather
than treating an empty array as implicit not-applicable.

