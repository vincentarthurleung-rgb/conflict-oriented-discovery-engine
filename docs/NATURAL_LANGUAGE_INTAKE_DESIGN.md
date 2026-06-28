# Natural Language Research Intake Design

## Planning Flow

Natural-language user input is never sent directly to L1 extraction. The
deterministic intake flow is:

```text
user request
  -> ResearchIntent parsing
  -> biomedical domain and prompt-profile selection
  -> PubMed/PMC search-query planning
  -> fixture/mock candidate matching against manifest and artifact inventory
  -> per-chunk prompt compatibility decisions
  -> dry-run L1 batch plan
```

The intent parser recognizes a bounded Chinese/English biomedical vocabulary,
comparison/update/mechanism goals, evidence scope, and time scope. Unknown input
returns warnings instead of raising or inventing entities.

## Candidate And Inventory Boundary

Search planning generates query strings only. It does not contact PubMed or PMC.
Candidate papers must be supplied by a later retrieval executor or by test/mock
input. Candidates are deduplicated against local inventory by PMID, PMCID, DOI,
and normalized title hash. The retained manifest is never modified by matching.

## Prompt Compatibility

Old L1 output is reusable only when the chunk hash and extraction contract are
compatible. The prompt fingerprint includes:

- domain ID
- prompt profile ID
- prompt version
- output schema version
- extraction policy version
- model name and model family

The cache key additionally includes paper ID and chunk hash. A changed domain,
profile, prompt, schema, policy, or chunk hash forces re-extraction. Model-name
changes are reusable within the same family only when
`allow_model_family_reuse=True` is explicitly set.

## Execution Boundary

The L1 batch planner reports downloads, payload builds, reusable chunks,
first-time L1 chunks, re-extraction reasons, estimated calls/tokens, batches, and
budget status. `api_calls_made` remains zero. Real search, downloads, and L1 API
execution require a future explicit executor and budget approval.

This is a fixture-based dry-run planning MVP, not an automatic online literature
retrieval system.

