# System B Knowledge Explorer

The Knowledge Explorer is a local, read-only research workspace over display KG v2. It provides overview, case, entity, linear chain, triple/evidence, conflict-lens, review, and paper-metrics views without loading the full clean KG as the default graph.

```bash
python -m code_engine.cli.system_b_serve_knowledge_explorer \
  --display-kg-root system_b_outputs/three_case_clean_kg_v3 \
  --review-root system_b_outputs/three_case_review \
  --host 127.0.0.1 --port 8765
```

All JSONL inputs are cached at startup. Triple evidence is returned only by triple-detail requests and is bounded by `evidence_limit`. Validators remain side-panel annotations, conflict records remain triage overlays, and review metrics remain unavailable until annotations are completed.
