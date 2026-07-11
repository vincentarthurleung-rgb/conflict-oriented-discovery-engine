# Conflict / Context Evaluation Adapter Mapping

The adapters inspect real local artifacts and do not infer fields from filenames alone.

Conflict prediction candidates are searched in this order:

- `conflict_lens_records.jsonl`
- `weak_conflict_candidates.jsonl`
- `non_comparable_pairs.jsonl`

Accepted unit keys are `review_item_id`, `evaluation_unit_id`, `record_id`, then `pair_id`. Gold labels come only from frozen `conflict_pair_v1` Gold records. `different_context_non_comparable`, `duplicate_evidence`, and `insufficient_information` are never counted as true conflicts. `insufficient_information` is excluded from the binary denominator.

Context prediction candidates are searched in this order:

- `triple_contexts.jsonl`
- `context_predictions.jsonl`
- `context_matrix.jsonl`

Accepted unit keys are `review_item_id`, `evaluation_unit_id`, `triple_id`, then `record_id`. Context factor normalization is deterministic. Aliases are `time -> duration`, `cancer_type -> disease_subtype`, `disease_type -> disease_subtype`, and `method -> assay_method`; every mapping is recorded in adapter rows.
