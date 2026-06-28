# Legacy Code Scan

Generated from a repository search for fixed runtime paths, legacy scientific
fields, old status labels, and historical artifact filenames.

## Acceptable Legacy Compatibility

| Location | Reference | Reason |
| --- | --- | --- |
| `src/code_engine/reporting/blueprint.py` | `target_gene`, `lincs_target_gene_matched` | Reads old records after current anchor fields; output uses current names. |
| `src/code_engine/reporting/markdown.py` | old strong validation statuses | Sanitizes historical labels; tests assert they are not rendered. |
| `src/code_engine/validation/curated_omics.py` | `target_gene` | Last-priority compatibility input. |
| `src.storage`, `src.query`, migrated `src.pipelines` modules | re-exports | Preserve imports while implementation is owned by `code_engine`. |
| `tests/test_l6_legacy_fields.py`, `tests/test_reporting_v42_fields.py` | old fields/statuses | Negative compatibility tests. |

## Should Migrate Later

| Location | Finding | Migration target |
| --- | --- | --- |
| `src/pipelines/stage2_l1_extract.py` | substantial extraction logic and fixed interim/L1 paths | package extraction orchestration with a run root |
| `src/pipelines/stage3_l1_5_refiner.py` | fixed old L1/L1.5 paths | package refinement orchestration |
| `src/pipelines/stage5_shannon_matrix.py` | compatibility orchestrator writes fixed L2/L3/report paths | run-scoped graph orchestration |
| `src/pipelines/stage6_l4_beam_search.py` | full search orchestration and fixed L3/L4 paths | `code_engine.hypothesis` runner |
| `src/pipelines/stage7_l5_falsification.py` | full validation orchestration plus legacy aliases | `code_engine.validation` runner |
| `src/pipelines/stage8_l6_Exporter_Orchestrator.py` | legacy Stage8 entrypoint | package reporting CLI |
| `src/agents/*.py` | fixed data/report paths | run-scoped control-plane I/O |

## Dangerous Old-Data Dependencies

- Stage6 reads `data/processed/l3/integrated_shannon_graph.json` by default.
- Stage7 reads `data/processed/l4/hypothesis_search_results.json` by default.
- Stage8 compatibility scripts may read historical L5 filenames.
- Historical replay and critic agents assume previous processed outputs exist.

These files are preserved for compatibility but are not called by clean-workspace
query loaders. Missing package-owned inventory, knowledge store, or LLM cache now
returns an explicit empty state. `artifacts/legacy/` and `quarantine/` are rejected
unless a caller explicitly opts into a legacy source.

## Obsolete Artifact References

- `falsified_hypotheses_vetted.json`: legacy L5 alias; current name is
  `validated_hypotheses.json`.
- `lincs_falsification_status`: legacy status field; current field is
  `validation_status`.
- `Passed_By_General_Fallback` and
  `Verified_By_Hardened_Omics_Sign_Locked`: historical labels accepted only for
  sanitization or negative tests.
- Old `reports/*.json` and `data/processed/l6/*` names belong to legacy stage
  output contracts, not current source or truth.
