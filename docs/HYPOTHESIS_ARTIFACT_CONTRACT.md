# Hypothesis artifact contract

The hypothesis step writes these files under the current run's `artifacts/` directory:

- `hypothesis_candidates.jsonl`: scored, traceable deterministic candidates.
- `hypothesis_hyperedges.jsonl`: normalized `HypothesisHyperedge` records.
- `hypothesis_reasoning_records.jsonl`: rule-derived explanations linked to conflict, mechanism, and evidence IDs.
- `hypothesis_validation_requirements.jsonl`: downstream requests with `not_run` status.
- `hypothesis_summary.json`: bounded counts, source modes, warnings, and top hypotheses.

Provenance fields distinguish conflict IDs, full-text confirmation IDs, mechanism edge/path IDs, evidence IDs, and observation IDs. Abstract-only records must set `requires_fulltext_confirmation` and `requires_manual_review`; they are never high confidence. JSONL is streamed rather than represented as a large JSON array.
