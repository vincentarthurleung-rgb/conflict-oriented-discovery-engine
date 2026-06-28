# C.O.D.E. v4.2 Architecture

C.O.D.E. v4.2 remains a research MVP. Its core contribution is
conflict-conditioned mechanism discovery: contradictory relation evidence is
treated as information requiring context, support, and coverage analysis rather
than as a simple edge deletion decision.

## Principles

- EvidenceRecord is a first-class, auditable object.
- Mechanism edges are typed; biological relations are not equality aliases.
- Conflict is a posterior-like uncertainty-aware state in addition to a legacy hard label.
- A hypothesis can be a hyperedge spanning entities, contexts, paths, and missing links.
- Validation is coverage-aware; no coverage remains unresolved.
- A dry-lab planning loop precedes any future wet-lab loop.
- Agents suggest; deterministic code adjudicates scores, states, and coverage.
- LLM explanation, if later enabled, remains outside the quantitative core.

The probabilistic conflict values are normalized deterministic heuristic weights.
They are not a strict Bayesian posterior. The mechanism-path policy uses a fixed
linear scoring rule and has not been trained with reinforcement learning.

## Package Locations

- `code_engine.schemas.evidence`: grounded evidence records
- `code_engine.schemas.mechanism_edge`: typed mechanism edges
- `code_engine.graph.probabilistic_conflict`: uncertainty-aware conflict state
- `code_engine.hypothesis.hyperedge_builder`: legacy-to-hyperedge adapter
- `code_engine.hypothesis.policy_search`: heuristic path scoring
- `code_engine.loop.dry_lab_loop`: coverage-aware offline planning
- `code_engine.agents.kg_enrichment_agents`: structured suggestion interfaces
- `code_engine.reporting`: v4.2 blueprint and Markdown sections
- `code_engine.query.intent`: bilingual deterministic intent parsing
- `code_engine.query.search_planner`: retrieval-query planning without retrieval
- `code_engine.query.prompt_compatibility`: prompt-aware L1 reuse decisions
- `code_engine.query.l1_batch_planner`: dry-run incremental extraction batches
- `code_engine.normalization.registry`: local curated biomedical identities and relations
- `code_engine.normalization.resolver`: deterministic type-aware resolver cascade

## Current Limitations

- no full LINCS validation
- no online KG resolution
- no wet-lab automation
- no trained RL policy
- no hypergraph neural network
- no production graph database
- no automatic delta-ingestion execution
- L1 v2 API execution is an initial guarded adapter, not production orchestration
- no automatic online PubMed/PMC retrieval
- legacy stage wrappers are not yet uniformly run-root aware

A fresh workspace has no current graph by design. Query coverage reports expose
`runtime_data_status`, `knowledge_store_status`, and `using_legacy_data`; missing
L3 evidence results in insufficient coverage rather than stale-output reuse.

## Natural Language Intake

User prose is converted to ResearchIntent, search terms, candidate inventory
matches, prompt compatibility decisions, and an L1 batch plan. It does not flow
directly into extraction. Cache identity includes paper/chunk content plus the
domain, prompt profile/version, schema, policy, and model contract.

## L1 v2 Extraction Boundary

Stage2 compatibility paths forward to an offline L1 v2 planner. The default
sampling contract is fixed at temperature `0.0` and top-p `1.0`. Domain routing,
prompt compilation, complete chunk-level fingerprints, and EvidenceRecord-ready
claim schemas are package-owned. No API execution is implemented or triggered
by the default boundary. The guarded executor requires `--execute --api`.

Dynamic Stage0 accepts saved PubMed/PMC search plans and requires `--execute
--network`. Intent-derived seed triples are permanently non-evidence planning
objects; downstream conflict discovery receives only paper-derived L1 claims.

## Relation-Aware Layer 2

Layer 2 separates identity from typed biological relations. Gene aliases resolve
to gene IDs while retaining `subunit_of` links to receptor complexes; salts and
metabolites retain their own IDs and parent relations; assays retain `measures`
links to phenotypes. Unknown uppercase fallback is low-confidence and excluded
from high-confidence graph use. The local registry and deterministic rules make
the decision; optional candidate suggestions remain unvalidated.

`ResolverCascade` is now the default L2 mainline normalizer. L3 pair identity
prefers canonical IDs while preserving normalized names for compatibility.
Unknown uppercase fallback stays in the audit but is excluded from
high-confidence conflict statistics by default. Synonym-only behavior requires
`--legacy-synonym-only`; the optional LLM candidate proposer remains disabled.
