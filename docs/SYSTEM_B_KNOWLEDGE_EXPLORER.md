# C.O.D.E. Atlas: Biomedical Evidence & Mechanism Explorer

C.O.D.E. Atlas is the human-facing knowledge navigation, evidence audit, and conflict triage workspace built on C.O.D.E. Engine outputs. It is a local, read-only research workspace over display KG v2 and provides overview, case, entity, linear chain, triple/evidence, conflict-lens, review, and paper-metrics views without loading the full clean KG as the default graph.

中文名称：C.O.D.E. Atlas：生物医学证据与机制图谱工作台。

Historically this layer was referred to as “System B” in internal development notes. The user-facing name is now C.O.D.E. Atlas.

```bash
python -m code_engine.cli.system_b_serve_knowledge_explorer \
  --display-kg-root system_b_outputs/three_case_clean_kg_v3 \
  --review-root system_b_outputs/three_case_review \
  --host 127.0.0.1 --port 8765
```

All JSONL inputs are cached at startup. Triple evidence is returned only by triple-detail requests and is bounded by `evidence_limit`. Validators remain side-panel annotations, conflict records remain triage overlays, and review metrics remain unavailable until annotations are completed.

## Interactive manual review

Atlas can save queue-backed annotations to `manual_review_annotations_live.json`, JSONL, and CSV files under the configured review root. Saves replace the prior record for the same `review_item_id` and use atomic file replacement. Live metrics are written alongside annotations.

Manual review labels assess extraction and triage quality. They do not constitute biological validation. Labels are never written back into Engine findings or clean KG scientific artifacts.

For authenticated public-preview configuration, see `docs/CODE_ATLAS_PUBLIC_PREVIEW_SECURITY.md`. Never expose no-auth mode beyond `127.0.0.1`.
