# Natural Language To Literature Workflow

## Execution Boundary

The primary guarded workflow is:

```text
natural-language request
-> ResearchIntent and non-evidence seed triples
-> sanitized PubMed/PMC search plan
-> manifest-aware acquisition
-> payload chunks
-> L1 v2 paper-evidence extraction
-> legacy-compatible L1 and Stage3 refinement
-> L2/L3
```

Dry-run is the default. Network access requires both `--execute --network`;
DeepSeek access requires both `--execute --api`. Tests inject fake clients and
never use either external service.

## Intent Is Not Evidence

The deterministic parser is used with `--no-api`; an LLM may return structured
`research_intent`, `seed_triples`, `search_concepts`, domains, filters, and
ambiguities when API execution is explicit. Every `SeedResearchTriple` is
forced to `source=user_intent_llm_parser` and `is_evidence=false`. Seeds are for
search expansion and report framing only. They cannot become EvidenceRecord or
enter L3 conflict statistics.

## Search And Acquisition

LLM-proposed queries pass through a deterministic sanitizer before being saved.
The plan separates PubMed and PMC queries, supports dates and limits, prefers
PMC full text, and retains PubMed abstract fallback. Stage0 wrappers now forward
to this plan-driven acquisition path; absent a plan/query they retain an audited
legacy ketamine-query fallback.

Candidates are deduplicated by PMID, PMCID, DOI, and normalized title hash, then
checked against both `global_manifest.json` and existing raw paths. New PMC XML
is written under `data/raw/xml/`; PubMed XML/abstract payloads under
`data/raw/abstracts/`.

## Executable L1

Each new chunk is prompt-compiled and cache-checked. Compatible cache entries
are reused. An incompatible chunk is only sent to DeepSeek when both execute/API
flags are present; otherwise it is reported in `extraction_needed`. Successful
claims are validated as `L1ExtractedClaim` and written to
`data/processed/l1_v2/`; the converter also writes the current legacy L1 shape
under `data/processed/l1/` for Stage3.

Failures are structured and do not create synthetic claims. Stage3 accepts both
formats and retains claim IDs, fingerprints, evidence sentences, refined
contexts, and EvidenceRecord-ready fields.
