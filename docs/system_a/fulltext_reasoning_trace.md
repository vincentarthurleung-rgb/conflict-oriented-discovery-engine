# Fulltext Claim-centered Reasoning Trace

Fulltext reasoning traces are evidence-process artifacts for full-text claims. Claims remain the formal conflict input; reasoning traces explain how the paper supports a claim and supply experimental context.

## Boundaries

- Claim: immutable `subject -> relation -> object -> sign` object from Fulltext L1.
- Reasoning trace: anchored sequence of reported experiment, observation, rescue/blocking, and author interpretation steps.
- Context consolidation: deterministic merge of claim-scoped context and evidence-chain experimental context with field provenance.

Reasoning steps never become `ScientificTriple` records, formal conflict edges, sign votes, or KG nodes. Abstract-only claims receive `unavailable_abstract_only`; abstracts are not forced to produce full reasoning chains.

## Retrieval And Extraction

The `fulltext_reasoning_trace` stage builds claim-centered passages from the same paper only. It prioritizes the claim evidence sentence, Results, Methods, figure/table captions, Discussion interpretation, subject/object co-occurrence, and intervention/rescue/blocking terms. Retrieval is deterministic and does not call a model.

Extraction uses a separate prompt version, `fulltext_reasoning_trace_prompt_v1`, and schema version, `fulltext_reasoning_trace_v1`. Each accepted step must have an allowed role, valid sentence IDs, section provenance, anchored reported text, and provenance type `reported` or `reconstructed_from_reported_steps`.

## Cache

Reasoning cache keys include stable paper identity, fulltext/passage content hashes, content-based claim identity hash, prompt version, provider/model, schema version, extractor version, and retrieval config. They exclude run directories, output paths, local claim IDs, local passage IDs, attempts, timestamps, and orchestration IDs. A shared content-addressed cache under `data/interim/cache/fulltext_reasoning_trace` enables cross-run reuse. Context consolidation rule changes do not invalidate reasoning extraction.

The upstream Fulltext L1 stage has its own shared chunk cache. Its key is based on document identity, chunk content hash, target focus, prompt/schema/provider/model, extractor version, chunker version, and chunker scientific config. A forced Fulltext L1 stage can therefore materialize a new run while still making zero provider calls if all chunks hit cache.

## Artifacts

- `artifacts/fulltext_claim_passage_index.jsonl`
- `artifacts/fulltext_reasoning_traces.jsonl`
- `artifacts/fulltext_reasoning_trace_summary.json`
- `artifacts/fulltext_context_consolidations.jsonl`
- `artifacts/fulltext_context_consolidation_summary.json`

## Re-run

```bash
PYTHONPATH=src python -m code_engine.cli.run_case_to_atlas \
  --case-id <CASE_ID> \
  --from-stage fulltext_reasoning_trace \
  --to-stage atlas_sync \
  --api \
  --network
```

Rebuild only context and downstream Atlas projection offline:

```bash
PYTHONPATH=src python -m code_engine.cli.run_case_to_atlas \
  --case-id <CASE_ID> \
  --from-stage fulltext_context_consolidation \
  --to-stage atlas_sync \
  --offline
```

Dry-run is read-only and reports expected reasoning API use, cache hits, context rebuild status, and the stage reuse decision. Repeating an identical completed request should show `fulltext_reasoning_trace=reuse`, `fulltext_context_consolidation=reuse`, and expected reasoning API calls of zero.
