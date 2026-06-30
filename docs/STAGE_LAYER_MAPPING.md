# Stage / Layer Mapping

This project keeps legacy stage names for compatibility. New documentation uses Layer 0-8 to describe responsibilities.

The Query-Driven Incremental Discovery Layer sits above Layer 0-8. It is not a
replacement stage: `code_engine.query` asks what the existing layers already cover,
while package-owned acquisition, graph, and extraction modules index reusable artifacts. Its current
update mode creates a dry-run delta plan only.

| Legacy Stage/File | New Layer Meaning | Main Responsibility | Status |
| --- | --- | --- | --- |
| `scripts/stage0_fetch_pmc.py` | L0 Literature Acquisition | PMC full-text fetching | legacy wrapper |
| `scripts/stage0_5_fetch_abstracts.py` | L0 Literature Acquisition | PubMed abstract fetching | legacy wrapper |
| `scripts/stage1_clean_weight.py` | L0/L1 Input Preparation | payload extraction and journal weighting | legacy wrapper |
| `src/pipelines/stage2_l1_extract.py` | L1 Scientific Fact Extraction | LLM tuple extraction | core, API-dependent |
| `src/pipelines/stage3_l1_5_refiner.py` | L1.5 Context Refinement | context-field refinement | core, API-dependent |
| `src/pipelines/ontology_alignment.py` | L2 Ontology Alignment | delegates to `code_engine.graph.ontology_alignment` | legacy import wrapper |
| `src/pipelines/conflict_discovery.py` | L3 Conflict Discovery | delegates to `code_engine.graph.conflict_discovery` | legacy import wrapper |
| `src/pipelines/context_mining.py` | L4 Context Mining | delegates to `code_engine.graph.context_mining` | legacy import/CLI wrapper |
| `src/pipelines/context_attribution.py` | L5 Context Attribution | delegates to `code_engine.graph.context_attribution` | legacy import wrapper |
| `src/pipelines/stage6_l4_beam_search.py` | L6 Hypothesis Search | candidate hypothesis generation | core with legacy name |
| `src/pipelines/stage7_l5_falsification.py` | L7 External Validation | validator orchestration | core with legacy name |
| `src/pipelines/stage8_l6_Exporter_Orchestrator.py` | L8 Report Export | compatibility report export facade | thin legacy facade |
| `code_engine.reporting` | L8 Report Export | ranking, blueprints, markdown | core package |
| `code_engine.acquisition.manifest` | Cross-layer local index | paper processing-state inventory | query support |
| `code_engine.graph.knowledge_store` | Cross-layer local index | JSON artifact query adapter | query support |
| `code_engine.query` | Above L0-L8 | coverage, delta planning, local answer assembly | offline MVP |
| `code_engine.graph.probabilistic_conflict` | L3 extension | posterior-like uncertainty-aware conflict state | deterministic v4.2 |
| `code_engine.hypothesis.hyperedge_builder` | L6 extension | context/path/evidence hypothesis hyperedge | deterministic v4.2 |
| `code_engine.loop.dry_lab_loop` | Above L0-L8 | coverage-aware closed-loop planning | planning only |
| `code_engine.agents.kg_enrichment_agents` | Control plane | structured KG enrichment suggestions | no graph mutation |

## Wrapper Scripts

`scripts/` contains legacy CLI entrypoints. New code should live in
`src/code_engine/`; package CLIs live in `code_engine.cli`.

## Core Modules

Core package modules are in `src/code_engine/`. These old namespaces now remain
as compatibility wrappers:

- `src/pipelines/`
- `src/reporting/`
- `src/validators/`
- `src/schemas/`
- `src/config/`

## Legacy Compatibility Fields

These fields may still appear in old artifacts and compatibility outputs:

- `lincs_target_gene_matched`: use `omics_anchor_gene`, `registry_anchor_gene`, or `anchor_gene` in new code.
- `lincs_falsification_status`: use `validation_status` in new code.
- `falsified_hypotheses_vetted.json`: use `validated_hypotheses.json` in new code.
- `minimal_augmented_context_set`: retained for compatibility; prefer `separating_contexts` for interpretation.

## Recommended Reading Order

1. `README.md`
2. `docs/TECHNICAL_DESIGN_HANDBOOK.md`
3. `docs/STAGE_LAYER_MAPPING.md`
4. `docs/ARTIFACT_POLICY.md`
5. `docs/PACKAGE_ARCHITECTURE.md`
6. `src/code_engine/schemas/`, `src/code_engine/config/`, and `common/`
7. `src/code_engine/normalization/` and `graph/`
8. `src/code_engine/hypothesis/` and `validation/`
9. `src/code_engine/query/`
10. `src/code_engine/reporting/` and `evaluation/`
11. `src/pipelines/stage5_shannon_matrix.py` for legacy orchestration
12. old `src.*` wrappers only when checking compatibility
