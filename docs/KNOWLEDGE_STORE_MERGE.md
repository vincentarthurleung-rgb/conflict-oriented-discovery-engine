# KnowledgeStore merge

Run papers, claims, observations, conflicts, full-text evidence, mechanism nodes/edges/paths, hypotheses, and validation results are deduplicated into JSONL collections. Stable object-specific keys prevent repeated claims, evidence, mechanisms, or hypotheses. Inserted records retain first/last seen run, source run IDs, source artifact references, and bibliographic provenance.

The default produces only `knowledge_merge_plan.json`, audit JSONL, and a run-local summary. `--update-global-knowledge-store` is required for global writes. External validation records remain conservative signals, not proof.
