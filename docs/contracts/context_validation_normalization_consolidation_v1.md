# Context Validation, Normalization, and Consolidation v1

Validation, normalization, and consolidation each produce immutable revisions.
Validity and completeness are independent: an unreported field does not
invalidate otherwise supported Context.

Consolidation priority is validated local evidence, validated same-observation
evidence, deterministic scope inheritance, historical validated consolidation,
then unresolved. Conflicts remain unresolved; no nearest-text heuristic,
majority vote, downstream demand, or LLM adjudication is permitted.

