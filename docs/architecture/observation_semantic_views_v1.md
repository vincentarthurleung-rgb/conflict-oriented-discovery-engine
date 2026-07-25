# Observation Semantic Views v1

Status: Active

`NormalizedObservation` is projected into four non-overlapping views:

- `PropositionCoreView` identifies subject, direction-neutral relation family, endpoint/object, and optional outcome variable.
- `ContradictionResultView` owns direction, sign, polarity, qualitative/quantitative outcomes, and result category.
- `ContextEnvelopeRef` points to Observation Context readiness and identities without copying context facts.
- `GranularityQualificationView` exposes biological level, endpoint compartment, and endpoint subtype for explicit bridge assessment.

The proposition-core identity excludes observation and literature IDs, result values, context, evidence text, paths, timestamps, and downstream judgments. The full semantic-view identity may bind the observation ID. `observation_semantics` has no L3/L4 dependency.
