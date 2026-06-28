# Resource-Aware External Validation

## Execution Pipeline

```text
anchor -> semantic question -> capability route -> query plan
       -> resource guard -> streaming evidence -> streaming signals
       -> conservative aggregate result
```

Validators are selected through capability metadata. The router only creates
routes. `ValidatorQueryPlanner` selects `local_index`, `remote_api`,
`cache_only`, `disabled`, or blocked execution before any provider is called.
Remote execution requires all of `--execute --network --external-validation`
and a remote-capable query mode. Default operation is offline planning.

For a 32 GB RAM workstation, the default resource policy limits validation to
4096 MB estimated memory, 100 records per validator, 200 records per anchor, 30
signals per validator, 200 signals per run, 5 MB raw payload per validator, 30
seconds per query, and one concurrent query. Large local scans are denied.

Evidence and signals are streamed to JSONL. They are conservative assessment
inputs, not proof. No record found is not contradiction. Cache miss is not no
coverage. Missing indexes/providers produce `external_index_not_configured`.
Trial existence is not efficacy support; binding activity is not mechanism
proof; pathway membership is not causality proof; cancer cell-line dependency
is not clinical efficacy.
