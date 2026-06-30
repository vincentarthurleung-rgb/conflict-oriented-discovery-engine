# Graph Export Interface

C.O.D.E. produces graph-ready artifacts for the current run. It is not a global knowledge graph service. Corpus-wide integration, cross-topic queries, entity-centric research maps, graph databases, search services, and visualization belong to a future independent Knowledge Graph Explorer / Integrator.

## Consumer contract

A future KG system can ingest the JSONL node, graph-edge, evidence-bundle, graph-conflict, and reasoning-trace artifacts. Records use deterministic SHA-256-derived IDs and carry:

- `run_id`, `topic_id`, `query_id`, and `artifact_schema_version`;
- canonical entities and relation/direction/context fields;
- paper, DOI, title, journal, year, and evidence-span provenance where available;
- upstream/downstream linked IDs;
- `export_ready` and `export_warnings` for explicit degradation.

Missing metadata is represented as null or a warning; it is never fabricated. Bundle IDs are stable functions of subject canonical ID, object canonical ID, relation family, and polarity type. Evidence-edge IDs use paper and source-record identity. Graph conflict and reasoning-trace IDs derive from the bundle ID.

## Scope boundary

Artifacts are intentionally run-scoped. Avoiding cross-run merge keeps identity adjudication, topic reconciliation, storage lifecycle, global indexing, and UI concerns out of the scientific extraction and conflict-reasoning workflow. The future integrator can apply those policies without increasing the main system's runtime or semantic complexity.

Merged Evidence Graph is a run-level graph-ready reasoning layer, not a full corpus-level graph search or visualization system.
