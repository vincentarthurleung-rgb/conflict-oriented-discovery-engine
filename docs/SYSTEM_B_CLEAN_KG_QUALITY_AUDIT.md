# System B Clean KG Quality Audit

Round 1.5 adds conservative entity cleanup and UI-layer type inference, scored triples and chains, a default display subgraph, and a standalone contamination/quality audit. These heuristics do not claim ontology-grade biomedical normalization.

Safe canonicalization normalizes whitespace, punctuation, selected Unicode variants, Greek alpha/beta/kappa, and trailing numeric parenthetical suffixes. Original labels remain aliases. More ambiguous spacing and hyphen similarities are review candidates rather than automatic merges.

The complete `clean_entities` and `clean_triples` artifacts remain available. `*_display` files exclude high-noise triples and triples whose endpoints are both unknown. Quality scores affect presentation only; they do not change System A findings or scientific classification.

```bash
python -m code_engine.cli.system_b_audit_clean_kg \
  --clean-kg-root system_b_outputs/three_case_clean_kg_v2 \
  --output-root system_b_outputs/three_case_clean_kg_v2_audit \
  --top-n 50 --write-csv --write-json --overwrite
```
