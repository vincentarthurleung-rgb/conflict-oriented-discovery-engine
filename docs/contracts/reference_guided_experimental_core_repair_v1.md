# Reference-guided Experimental Core Repair v1

## Authority boundary

The production contracts in `experimental_core.repair_v1` never load an evaluation fixture. They accept source-grounded inputs from an upstream authority and apply deterministic structural, completeness, evidence, ambiguity, and provenance gates. A role such as `control`, a single remaining candidate, raw control metadata, or sentence co-occurrence is never sufficient authority.

The frozen input used by the offline replay is an `internal_source_grounded_reference_v1`. It is an evaluation and regression oracle, not Human Gold, Publication Gold, or runtime input. Task IDs, expected Factor IDs, expected answers, and root-cause labels occur only in the offline evaluation layer and generated audit artifacts.

## Versioned contracts

- `experimental_observed_result_structural_integrity_v2` represents exact missingness tokens with a value state and preserves full scientific sentences containing similar words.
- `experimental_measurement_semantic_integrity_v1` separates molecular exposure/grouping factors from clinical, phenotype, survival, and association endpoints.
- `experimental_arm_record_v1` composes atomic factors into a distinct experimental-arm identity and keeps role candidacy separate from role authority.
- `experimental_linkage_candidate_completeness_v1` blocks missing arms/factors and source gaps before annotation or materialization.
- `source_grounded_experimental_linkage_materialization_v1` writes immutable sidecars only after every fail-closed gate passes.
- `annotation_task_validity_gate_v1` routes deterministic resolution, structural repair, candidate/arm repair, source recovery, and human annotation separately.
- `experimental_observation_machine_reuse_readiness_v5_candidate` evaluates all core blockers, remains candidate-only, and does not replace active v4.

All contracts are strict (`extra=forbid`), versioned, immutable where they represent revisions, provenance-bearing, and deterministically identified without timestamps or absolute paths. Historical Raw, Parsed, Validated, Fulltext v3, projections, factors, measurements, results, observations, Candidate Pairs, and Formal Conflict artifacts remain read-only.
