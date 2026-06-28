# Code Review Guide

This guide is for reviewing the current research MVP without mistaking legacy names for the newer Layer 0-8 architecture.

## Recommended Reading Order

1. `README.md`
2. `docs/PACKAGE_ARCHITECTURE.md`
3. `src/code_engine/schemas/`
4. `src/code_engine/config/`
5. `src/code_engine/normalization/` and `src/code_engine/graph/`
6. `src/code_engine/hypothesis/` and `src/code_engine/validation/`
7. `src/code_engine/query/`
8. `src/code_engine/reporting/` and `src/code_engine/evaluation/`
9. `docs/STAGE_LAYER_MAPPING.md`
10. compatibility wrappers under `src/` and `scripts/`
11. `tests/`

For v4.2, review evidence and adjudication boundaries in this order:

1. `code_engine.schemas.evidence` and `mechanism_edge`
2. `code_engine.graph.probabilistic_conflict`
3. `code_engine.hypothesis.hyperedge_builder`, `reasoning`, and `policy_search`
4. `code_engine.loop.dry_lab_loop`
5. `code_engine.agents.kg_enrichment_agents`
6. `code_engine.reporting`

For natural-language intake, review:

1. `code_engine.query.intent`
2. `code_engine.query.search_planner`
3. `code_engine.acquisition.manifest.match_candidate_papers_to_inventory`
4. `code_engine.query.prompt_compatibility`
5. `code_engine.query.l1_batch_planner`
6. `code_engine.query.cli`

For Layer 2 normalization, review:

1. `configs/normalization/entity_registry.json`
2. `code_engine.normalization.lexical` and `entity_type`
3. `code_engine.normalization.registry` and `resolver`
4. `code_engine.graph.ontology_alignment`
5. `tests/test_normalization_resolver_cascade.py`

## Legacy Wrappers

`scripts/` and old `src.*` modules are compatibility entrypoints. New
deterministic logic belongs under `src/code_engine/`.

These names are legacy wrappers or legacy-named modules:

- `scripts/stage4_l2_normalize.py`
- `scripts/stage6_l4_infer.py`
- `scripts/stage7_l5_verify.py`
- `scripts/stage8_l6_results.py`
- `src/pipelines/stage6_l4_beam_search.py`
- `src/pipelines/stage7_l5_falsification.py`
- `src/pipelines/stage8_l6_Exporter_Orchestrator.py`

Do not infer new layer semantics directly from these filenames. For example,
`stage6_l4_beam_search.py` is a legacy name for Layer 6 hypothesis search.

## Legacy Compatibility Fields

These fields may still appear for backward compatibility:

- `target_gene`: registry legacy field; prefer `registry_anchor_gene` or `omics_anchor_gene`.
- `lincs_target_gene_matched`: legacy report/export field; prefer `anchor_gene`.
- `lincs_falsification_status`: legacy validation status field; prefer `validation_status`.
- `falsified_hypotheses_vetted.json`: legacy output alias; prefer `validated_hypotheses.json`.
- `minimal_augmented_context_set`: legacy context list; prefer `separating_contexts`.

New code and reports should prefer current fields and treat legacy fields as compatibility inputs only.

## High-Priority Review Points

- Config fallback must be explicit and audited.
- Context mentions must remain evidence-span grounded.
- Missing validation coverage must remain `Unresolved_No_Coverage`, not passed.
- Reports should avoid over-strong validation language.
- The curated omics registry must not be described as full LINCS validation.
- Query modes must remain offline by default and report `api_calls_made=0`.
- Insufficient coverage must not generate an unsupported hypothesis.
- `update` currently means dry-run planning only, not paper retrieval or LLM execution.
- A cache hit requires the full paper/chunk/prompt/model/schema key.
- L1 default temperature must remain `0.0`; scheduling requires an explicit experimental flag.
- Old L1 without complete fingerprint metadata must not be reused by default.
- Seed triples must remain `is_evidence=false` and must never enter L3.
- Network/API clients must require `--execute` plus their explicit gate.
- LLM-proposed literature queries must pass deterministic sanitization.
- Ungrounded evidence must not carry high confidence.
- Posterior-like conflict values must remain deterministic and labeled heuristic.
- Agent suggestions must never directly mutate graph truth or scientific scores.
- Insufficient dry-lab coverage must not emit a strong mechanism conclusion.
- Search plans must not be represented as retrieved papers.
- Old L1 reuse requires compatible content and prompt fingerprints.
- Intake and update modes must keep actual API calls at zero.
- Receptor complexes must not collapse to one gene subunit.
- Metabolites and salts must retain typed relations to parent compounds.
- Unresolved uppercase fallback must remain low-confidence and graph-ineligible.
- Candidate proposer output must require deterministic validation.
- Empty runtime directories must yield explicit empty states and insufficient
  coverage, never stale archive reuse.
- Reads from `artifacts/legacy/` or `quarantine/` require explicit opt-in.

## Current Technical Debt

- Stage2 has a guarded executable adapter; production retry/observability remains limited.
- Old stage filenames remain for compatibility.
- Historical replay is still a skeleton benchmark.
- Full ontology lookup is not implemented.
- Full LINCS parsing and validation are not implemented.
- Full downstream L1.5-L8 orchestration from intake is not yet automatic.
- Query candidate-paper search is local metadata matching, not an online literature search.
- The knowledge store is local JSON/in-memory indexing, not a graph database.
- Stage2, Stage3, Layer6 search, and agent modules are not fully migrated into package-owned implementations.
- The source-tree bootstrap exists only for uninstalled checkout execution.
- Legacy stage wrappers still use fixed runtime paths and are not fully run-root aware.

Review `docs/LEGACY_CODE_POLICY.md` and
`cleanup_reports/legacy_code_scan.md` before removing compatibility code.
