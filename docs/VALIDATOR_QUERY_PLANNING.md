# Validator Query Planning

Every validator execution starts from `ValidationQueryPlan`. Plans record the
anchor/question, selected validator, query entities/context, execution mode,
index/cache identity, estimates, record/signal/payload/time limits, status,
reason, and warnings.

`auto` prefers an available local index, then a cache hit, then an explicitly
permitted remote provider. `local_index` with no index returns `no_index`.
`cache_only` with a miss returns `no_cache` plus
`cache_miss_is_not_no_coverage`. Remote mode without execute/network/external
validation is blocked. Entity-free broad queries are `too_broad`.

`ResourceGuard` blocks memory overrun and prohibited broad scans, truncates
record/signal/time/payload bounds, and forces concurrency to one. The execution
engine then processes plans sequentially, writes evidence/signals as JSONL, and
contains validator failures as structured error signals.

For local mode, planning also binds the validator's declared `schema_name`,
`schema_version`, and `source_database` to index metadata. Version mismatch,
missing required fields, or absent manifest produces `no_index` /
`external_index_not_configured`; validators do not silently read records.
