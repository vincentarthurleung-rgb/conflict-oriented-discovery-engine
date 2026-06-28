# End-to-End Workflow

`python -m code_engine.cli.run` is the recommended production-facing entry point. Stage scripts remain available as legacy and debugging entry points.

The default is a local dry run with API and network access disabled:

```bash
python -m code_engine.cli.run \
  --query "我想了解一下当前氯胺酮在抑郁症中的作用" \
  --dry-run --no-api --no-network --until report
```

Execution and external access are independent permissions. `--execute` never enables API or network access. Use `--execute --api` for configured LLM extraction or `--execute --network` for configured literature acquisition. Resume is also deny-by-default:

```bash
python -m code_engine.cli.run --resume runs/<run_id> --execute --until report
```

Steps are `intake`, `search`, `acquisition`, `payload`, `l1`, `l1_5`, `l2`, `conflict`, `hypothesis`, `validation`, and `report`. DomainProfile metadata is carried from intake into search, L1 planning, normalization policy, and validation planning. User-intent seed triples are search-planning inputs with `is_evidence=false`; they are never EvidenceRecords or conflict-graph observations.

LLMs and scientific encoders encode candidate structure. Deterministic modules adjudicate normalization, conflicts, ranking, and coverage. ValidationRouter selects validators; validators produce validation results. A partial report with blocked steps is a normal reproducibility artifact, not necessarily a failed run.
