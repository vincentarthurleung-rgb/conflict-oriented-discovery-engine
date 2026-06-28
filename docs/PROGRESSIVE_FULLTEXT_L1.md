# Progressive Full-Text L1

## Processing Model

C.O.D.E. uses abstracts for broad, low-cost claim screening and full text for
targeted evidence, context, and mechanism confirmation:

```text
abstracts -> abstract claims -> L2 -> entropy candidates
          -> conflict focus set -> available full text
          -> ranked sections -> selected spans -> full-text L1 evidence
```

Full-text extraction is not an all-chunk pass. Only papers linked to an
abstract conflict candidate are eligible, and only high-ranked sections and
bounded evidence-bearing spans are sent to L1. References, funding, author
contributions, and unrelated boilerplate are excluded deterministically.

`source_scope=abstract` and the abstract evidence tiers are never eligible for
the high-confidence MechanismGraph. A missing or inaccessible full text is
retained as a coverage gap; it is not contradictory evidence.

## Modes And Guards

The CLI supports `abstract_screening`, `progressive_fulltext`,
`fulltext_oracle`, and `legacy`. The package CLI defaults to abstract screening;
the programmatic workflow retains a legacy default for backward compatibility.
Full-text escalation additionally requires `--enable-fulltext-escalation`.

Every L1 phase computes calls, input tokens, and estimated cost before
execution. Execute mode is blocked on budget overrun unless
`--allow-budget-overrun` is explicit. API calls still require `--execute --api`;
acquisition requires `--execute --network`. Cache keys include the source text
and prompt profile.

Confirmed full-text conflicts and mechanism gaps can become ValidationAnchors.
External validators assess these anchors through planned and resource-guarded
queries; they never reinterpret abstract candidates as proof.
