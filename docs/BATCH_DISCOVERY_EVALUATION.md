# Batch Discovery Evaluation

## Experimental Endpoint

The batch experiment measures automated scientific problem discovery, not
hypothesis accuracy. A prompt bank is processed into abstract conflict
candidates, a deterministic human-annotation sample, optional full-text
confirmation statistics, hypothesis counts, and cost metrics.

Primary metrics are prompt/paper scale, abstract claim yield, valid conflict
yield, actionable conflict yield, traceability, full-text escalation yield, and
cost efficiency. Hypothesis counts are reported, but accuracy is not the main
endpoint.

```bash
python -m code_engine.cli.batch_discovery \
  --prompt-bank tests/fixtures/prompt_bank_small.jsonl \
  --max-prompts 10 --l1-mode abstract_screening \
  --sample-conflicts 5 --dry-run --no-api --no-network
```

Batch mode is dry-run/offline by default. It writes manifests, candidates,
focus sets, annotation schema/sample, metrics, hypothesis statistics, and a
Markdown report under one batch directory. `--resume` reuses completed batch
artifacts. Human labels distinguish valid contextual/direct conflicts,
actionability, extraction/normalization/polarity/context errors, duplicates,
non-conflicts, insufficient evidence, and uncertainty.

Optional Layer 6 work uses the same anchor-based `code_engine.validation`
pipeline as single runs. Batch mode does not create a parallel validation
system and retains per-prompt/resource caps.

`--batch-external-validation` adds anchor, question, route, query-plan,
execution, aggregation, and metrics artifacts. It is disabled by default.
`local_index` and `cache_only` can execute offline when the caller explicitly
executes a non-dry batch; remote mode remains blocked without all guards. Batch
statuses can be grouped by conflict/hypothesis provenance, but they are not a
measurement of hypothesis accuracy. Missing index, no coverage, and cache miss
remain distinct.
# Hypothesis traceability

Batch discovery emits `batch_hypothesis_candidates.jsonl`, `batch_hypothesis_hyperedges.jsonl`, and `batch_hypothesis_summary.json`. Abstract conflicts produce low-confidence follow-ups; available full-text confirmations upgrade grounding. Metrics cover candidate count, traceability, grounding, manual review, and validation readiness—not hypothesis accuracy.

Overlapping prompts resolve papers through one registry and reuse identical abstract task signatures. Batch metrics report unique papers, duplicate hits, overlap rate, task-cache hits/misses, estimated calls saved, and missing DOI/journal rates.
