# System B Review Queue and Metrics

System B converts completed or partial case bundles into a reproducible manual-review queue, an empty annotation template, and automated case/paper count summaries. It does not alter System A or claim biological validation.

## Manual review goal

Reviewers assess whether a claim is supported by its source, whether a reviewable observation is relevant and mechanistically useful, whether weak and non-comparable candidates were triaged correctly, and whether full text adds information beyond abstract evidence. The target is evidence-extraction and triage quality—not proof of biological truth.

Recommended sampling per case:

- 30 randomly sampled fulltext claims
- top 20 fulltext reviewable observations
- top 20 abstract reviewable observations
- 10 low-priority context observations
- all weak candidates
- all non-comparable direction pairs
- all formal hypotheses

Sampling is deterministic for a fixed case ID and seed. Missing optional artifacts are reported and do not abort generation. A directory containing `case_bundle_manifest.json` is a bundle; bundle roots are scanned recursively, supporting both `case_bundles/` and batch-run bundle trees.

## Annotation and future metrics

Complete `manual_review_annotations_template.csv` without changing identity or provenance columns. Manual precision, direction accuracy, context capture rate, and precision@K must not be reported before annotation is complete.

Future scored metrics are:

- claim precision
- direction accuracy
- context capture rate
- reviewable precision@20
- noise leakage rate
- non-comparable rejection accuracy
- weak candidate precision
- fulltext re-entry yield
- fulltext novelty rate
- case-level utility rate
- inter-annotator agreement

The optional annotation-scoring CLI is intentionally deferred until annotation value conventions and denominator rules are finalized; implementing these metrics without that contract would create misleading results.

## Generate artifacts

```bash
python -m code_engine.cli.system_b_generate_review_queue \
  --bundle-root batch_runs/three_case_concurrency_test/bundles \
  --output-root system_b_outputs/three_case_review \
  --top-reviewable-per-case 20 \
  --random-fulltext-claims-per-case 30 \
  --low-priority-context-per-case 10 \
  --include-all-weak-candidates \
  --include-all-non-comparable-pairs \
  --include-formal-hypotheses \
  --seed 42 --write-csv --write-jsonl --overwrite
```

`paper_metrics_starter.*` contains automated counts only. It is a manuscript-planning input, not a validated results table.
