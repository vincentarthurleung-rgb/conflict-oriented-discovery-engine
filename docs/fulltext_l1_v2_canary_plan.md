# Fulltext L1 v2 Canary Plan (not executed)

Generated from local run artifacts on 2026-07-21. This is a plan only: no retrieval, download, provider, cleaner, or LLM call was made.

| Canary | Cached fulltexts | Missing fulltexts | Estimated v2 input blocks | Paid stage |
|---|---:|---:|---:|---|
| HIF1A | 15 | 0 | 160 (upper estimate from preserved selected chunks) | Fulltext L1 v2 only |
| EMT | 13 | 0 | 123 (upper estimate from preserved selected chunks) | Fulltext L1 v2 only |
| PI3K | 14 | 0 | 157 (upper estimate from preserved selected chunks) | Fulltext L1 v2 only |

Execution order for each canary:

1. Run `prepare_fulltext_inputs` against the listed immutable Fulltext L1 v1 run. Confirm the missing-only plan remains empty.
2. Create a new run; do not overwrite the source run. Run Fulltext L1 v2 with the cached `article_text.json` files.
3. Checkpoint after each v2 block through `cache/fulltext_l1_v2`; resume reuses successful cache entries and retries only parse/provider failures.
4. Continue through reasoning trace v2, experimental evidence chains, context consolidation, Fulltext L2 re-adjudication, and evidence projection.
5. Validate all safety counters and the end-to-end consistency report.
6. Stop before handoff/publication. Atlas remains unactivated until a separate explicit publication command.

Zero-network stages: input planning, cached article loading, v2 schema validation, context binding, deterministic chain construction, L2 re-adjudication using local candidates, evidence projection, bundling, and reports. Fulltext L1 v2 is the only expected paid stage. Reasoning trace can remain zero-cost when the structured v2 observation is complete; any optional trace-augmentation LLM call must be separately enabled and checkpointed.

Source runs:

- HIF1A: `runs/cta_d1f92fd42fc0fe1a8e27_hif1a_hypoxia_cancer_response_discovery_v1_fulltext_l1_v1`
- EMT: `runs/cta_117d184d5b78ddd030b2_emt_metastasis_drug_resistance_discovery_v1_fulltext_l1_v1`
- PI3K: `runs/cta_562c3b820b0f6047529b_pi3k_akt_mtor_cancer_resistance_discovery_v1_fulltext_l1_v1`
