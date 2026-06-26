# Code Review Guide

This guide is for reviewing the current research MVP without mistaking legacy names for the newer Layer 0-8 architecture.

## Recommended Reading Order

1. `README.md`
2. `docs/STAGE_LAYER_MAPPING.md`
3. `src/schemas/`
4. `src/config/`
5. `src/pipelines/ontology_alignment.py`
6. `src/pipelines/conflict_discovery.py`
7. `src/pipelines/context_mining.py`
8. `src/pipelines/context_attribution.py`
9. `src/validators/`
10. `src/reporting/`
11. `tests/`

## Legacy Wrappers

`scripts/` files are compatibility entrypoints. They should delegate to `src/`
modules and should not become the main home for new deterministic logic.

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

## Current Technical Debt

- Stage2/Stage3 still depend on LLM API access or cached outputs.
- Old stage filenames remain for compatibility.
- Historical replay is still a skeleton benchmark.
- Full ontology lookup is not implemented.
- Full LINCS parsing and validation are not implemented.
