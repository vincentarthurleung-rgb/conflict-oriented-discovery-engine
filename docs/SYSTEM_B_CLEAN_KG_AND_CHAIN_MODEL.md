# System B Clean KG and Chain Model

The clean KG is a biomedical navigation projection over case-bundle evidence. Its main graph contains only biomedical entities connected by aggregated scientific relations. Evidence sentences, claims, papers, validators, and pipeline artifacts remain provenance, annotations, badges, or conflict overlays; they are never graph nodes.

Triples aggregate repeated subject–normalized relation–object observations while retaining every source item in `triple_evidence_links.jsonl`. Original relations remain on triples alongside conservative normalized relations. Entity typing falls back to `unknown_biomedical_entity` when bundle metadata cannot support a more specific type.

`chain_index.jsonl` contains directed simple paths up to the configured depth. Each entity contributes at most its top 20 outgoing edges by evidence count to bound path growth. `conflict_lens_records.jsonl` is an overlay for weak, non-comparable, split, and hypothesis records; it is not the main KG and weak candidates are not findings.

Validators are exported as case-level annotations unless a reliable target mapping exists. This intentionally avoids turning LINCS, Reactome, Enrichr, or PubMed post-cutoff into biological entities or relations.

```bash
python -m code_engine.cli.system_b_build_clean_kg \
  --bundle-root batch_runs/three_case_concurrency_test/bundles \
  --output-root system_b_outputs/three_case_clean_kg \
  --max-chain-depth 3 --min-evidence-count 1 \
  --write-jsonl --write-csv --overwrite
```
