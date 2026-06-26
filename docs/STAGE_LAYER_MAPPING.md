# Stage / Layer Mapping

This project keeps legacy stage names for compatibility. New documentation uses Layer 0-8 to describe responsibilities.

| Legacy Stage/File | New Layer Meaning | Main Responsibility | Status |
| --- | --- | --- | --- |
| `scripts/stage0_fetch_pmc.py` | L0 Literature Acquisition | PMC full-text fetching | legacy wrapper |
| `scripts/stage0_5_fetch_abstracts.py` | L0 Literature Acquisition | PubMed abstract fetching | legacy wrapper |
| `scripts/stage1_clean_weight.py` | L0/L1 Input Preparation | payload extraction and journal weighting | legacy wrapper |
| `src/pipelines/stage2_l1_extract.py` | L1 Scientific Fact Extraction | LLM tuple extraction | core, API-dependent |
| `src/pipelines/stage3_l1_5_refiner.py` | L1.5 Context Refinement | context-field refinement | core, API-dependent |
| `src/pipelines/ontology_alignment.py` | L2 Ontology Alignment | conservative normalization | core |
| `src/pipelines/conflict_discovery.py` | L3 Conflict Discovery | entropy and conflict typing | core |
| `src/pipelines/context_mining.py` | L4 Context Mining | evidence-span context extraction | core |
| `src/pipelines/context_attribution.py` | L5 Context Attribution | entropy/legacy EM attribution | core |
| `src/pipelines/stage6_l4_beam_search.py` | L6 Hypothesis Search | candidate hypothesis generation | core with legacy name |
| `src/pipelines/stage7_l5_falsification.py` | L7 External Validation | validator orchestration | core with legacy name |
| `src/pipelines/stage8_l6_Exporter_Orchestrator.py` | L8 Report Export | compatibility report export facade | thin legacy facade |
| `src/reporting/ranking.py` | L8 Report Export | deterministic ranking | core |
| `src/reporting/blueprint.py` | L8 Report Export | report blueprint construction | core |
| `src/reporting/markdown.py` | L8 Report Export | markdown rendering | core |

## Wrapper Scripts

`scripts/` contains CLI entrypoints and compatibility wrappers. New deterministic code should live in `src/`, with scripts delegating to those modules.

## Core Modules

Core deterministic modules are in:

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
5. `src/schemas/`
6. `src/config/`
7. `src/pipelines/stage5_shannon_matrix.py`
8. `src/pipelines/ontology_alignment.py`, `conflict_discovery.py`, `context_attribution.py`
9. `src/validators/`
10. `src/reporting/`
