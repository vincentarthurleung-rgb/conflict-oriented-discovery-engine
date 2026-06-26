# Technical Design Handbook

## Positioning

C.O.D.E. v4.0 is an agent-assisted, conflict-oriented scientific discovery MVP. Agents help prepare configuration, context axes, validation plans, and critiques. Deterministic code performs conflict calculation, attribution, validation status assignment, and ranking.

## Architecture

The system has three main planes.

- Agentic Control Plane: `src/agents/`
- Deterministic Pipeline Core: `src/pipelines/`, `src/schemas/`, `src/config/`, `src/validators/`
- Report Export: `src/reporting/`
- Evaluation Framework: `src/evaluation/`

The repository remains a research MVP, not a production package. Legacy script names are retained to keep existing workflows usable. See `docs/STAGE_LAYER_MAPPING.md` for the compatibility map.

## Deterministic Core

`src/schemas/` defines stable Pydantic objects for documents, triples, normalized entities, conflict edges, context mentions, context attribution, candidate hypotheses, validation results, and report items.

`src/config/loader.py` and `src/config/validation.py` prevent production silent fallback. Missing config or missing required sections raise an error unless `--allow-fallback` is explicitly provided. Fallback events are written to `reports/config_fallback_audit.json`. The old `src/pipelines/config_loader.py` remains as a compatibility wrapper.

`src/pipelines/stage5_shannon_matrix.py` is now an orchestrator. It writes legacy-compatible `data/processed/l3/integrated_shannon_graph.json` and new audit outputs:

- `data/processed/l2/entity_normalization_audit.json`
- `data/processed/l3/conflict_edges.json`
- `data/processed/l3/context_attribution.json`
- `reports/l3_conflict_summary.md`

## Conflict Rules

Current thresholds are explicit and reported:

- `marginal_entropy_conflict_gate = 0.10`
- `type_i_attribution_gate = 0.45`
- Type III: conflicting and `total_obs <= 2` or `independent_labs_count == 1`
- Type I: conflicting, non-Type III, attribution score `>= 0.45`
- Type II: conflicting, non-Type III, attribution score `< 0.45`
- Otherwise: `Uncontested`

## Context Handling

`src/pipelines/context_mining.py` produces span-grounded `ContextMention` records. A mention is accepted only when the span appears in the source evidence sentence. L4 still preserves `minimal_augmented_context_set`, but also emits `separating_contexts` so alternative values such as HYPOXIA and NORMOXIA are not presented as simultaneous conditions.

## Validation

`src/validators/curated_omics_validator.py` uses a curated/demo mini-index and reports:

- `Sign_Consistent_Under_Curated_Index`
- `Sign_Inconsistent_Under_Curated_Index`
- `Unresolved_No_Coverage`

The old pass-by-fallback behavior is removed from the new validation path. New outputs include `omics_anchor_gene` and `registry_anchor_gene` when a curated registry mapping exists.

Skeleton validators exist for LINCS, GEO, DrugBank, and ChEMBL. They do not perform real external validation yet.

## Current Limits

- The omics index is not full LINCS.
- Ontology alignment is alias-map plus uppercase fallback.
- LLM extraction remains cached/API-dependent.
- Historical replay is an evaluation skeleton using entity/context overlap, not semantic proof.
- Agent outputs are deterministic/template suggestions and configuration artifacts, not scientific verdicts.
- Runtime artifacts follow `docs/ARTIFACT_POLICY.md`.
