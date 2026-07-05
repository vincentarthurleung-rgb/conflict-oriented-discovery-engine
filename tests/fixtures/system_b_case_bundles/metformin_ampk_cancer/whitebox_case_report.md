# White-Box Case Report: metformin–AMPK–cancer

## Case type
Positive-control style evidence extraction case.

## Search/replay status
Frozen LLM-v1 search plan replayed without drift.

## L1 stability
46/46 abstracts successfully processed. No parse/schema/timeout failures.

## Core evidence
3 strong-context core observations support metformin-associated AMPK activation in cancer contexts.

## Conflict result
No true graph conflict was detected under the strict source gate.

## Hypothesis result
No high-confidence or graph-conflict hypothesis was generated. 2 abstract-only manual-review follow-ups were retained separately.

## Interpretation
The system correctly extracted cancer-specific metformin–AMPK core evidence while avoiding false conflict inflation.

## Paper-ready result
In the metformin–AMPK–cancer case, C.O.D.E. retrieved 47 candidate abstracts and successfully processed 46 with no L1 parsing, schema, or timeout failures. The L2 context gate retained 328 observations and identified 3 strong-context core observations directly supporting AMPK activation by metformin in cancer-related settings. These core observations were directionally consistent. Under the strict graph conflict source gate, no true positive-vs-negative multi-paper conflict was detected, and the system produced no high-confidence graph-conflict hypothesis. This case demonstrates that the system can extract mechanistically meaningful core evidence while avoiding false conflict inflation.

## Pipeline completeness

| Stage | Status | Mode | Notes |
|---|---|---|---|
| L1 Abstract extraction | completed | abstract_screening | 46/46 successful |
| L2 Context gate | completed | abstract_context_gate | 328 retained |
| L3 Graph conflict gate | completed | strict_source_gate | 0 true conflicts |
| L4 Context mining | completed | abstract_context_mining | context factors extracted |
| L5 Context attribution | completed | abstract_context_attribution | core/exclusion reasons explained |
| L6 Mechanism graph | completed | abstract_level_mechanism_graph | mechanism graph built from L2 |
| L7 External validation | partially_completed | lincs_l1000_transcriptomic_consistency | 42 metformin signatures; mixed interpretation |

This case is complete for the abstract-mode C.O.D.E. pipeline. Full-text confirmation and external validation were not executed because those modules were intentionally not configured in this run.

## External perturbation validation

- Status: partially completed
- Validator: LINCS L1000 local Level 5
- Validation type: transcriptomic consistency validation
- Matched metformin signatures: 42
- Interpretation: mixed
- Limitation: L1000 validates transcriptomic consistency, not direct AMPK phosphorylation.
- No case-specific threshold tuning or gene-set expansion was applied. The LINCS result remains mixed.

## L3.5 OA Full-Text Retrieval and Confirmation

- status: not_enabled
- candidate_paper_count: 0
- pmcid_resolved_count: 0
- oa_available_count: 0
- fulltext_downloaded_count: 0
- fulltext_l1_claim_count: 0
- fulltext_confirmed_conflict_count: 0
- copyright_safe: True
- non_oa_skipped_count: 0
- message: Full-text confirmation is disabled by case policy.
