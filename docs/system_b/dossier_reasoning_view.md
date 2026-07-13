# Dossier Reasoning View

System B consumes reasoning traces only as optional display/context artifacts. They do not change formal conflict counts, Clean KG nodes, or review/gold/metrics state.

## Dossier

Dossier detail includes `reasoning_traces`. Each trace is linked to existing dossier evidence by `claim_id` and shows:

- trace status: `complete`, `partial`, `not_found`, `unsupported_by_retrieved_passages`, `unavailable_abstract_only`, or `extraction_failed`
- claim identity hash
- reported steps with role, section, sentence IDs, and provenance type
- author conclusion if anchored
- strength profile booleans derived from step roles
- missing links and limitations

If a historical run has no reasoning artifacts, the API returns a missing message instead of treating the paper as low quality.

## Context Matrix

The Context Matrix includes reasoning-derived experimental fields when available:

- `intervention_type`
- `intervention_target`
- `control_group`
- `model_system`
- `dose`
- `duration`
- `assay_method`
- `measured_endpoint`
- `validation_design`
- `reasoning_trace_status`

Missing values display as `未报告`. Differences are represented as field values and provenance, not color alone.

## Compatibility

`atlas_handoff_v1` marks reasoning artifacts optional and advertises capabilities when they are present. The `fulltext_reentry_v5` adapter attaches reasoning to dossier evidence and context rows only; reasoning steps are stripped from graph and formal conflict projections.
