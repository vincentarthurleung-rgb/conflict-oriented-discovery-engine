# L2 Entity Resolution Audit

Each run records:

```text
artifacts/entity_resolution_candidates.jsonl
artifacts/entity_resolution_decisions.jsonl
artifacts/entity_resolution_audit.json
```

The candidate stream records provider identity, scoring components, grounding status, external IDs, warnings, and a reference to raw provider payload when available. The decision stream records every request, candidate set, selected candidate, deterministic reason, confidence, manual-review state, and provider trace.

The summary reports total mentions, resolution-status counts, and provider usage. Dry-runs and unresolved decisions never write accepted mappings. Only `resolved_curated` and `resolved_external_grounded` decisions may enter `data/index/entity_cache/accepted_mappings.jsonl`, and only during explicit execution. The cache is runtime data and remains gitignored.

The audit supports replay and debugging without embedding large raw provider responses. External candidates are never trusted solely because a provider returned them; deterministic adjudication remains mandatory.
