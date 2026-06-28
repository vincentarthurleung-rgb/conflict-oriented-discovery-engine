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
