# Technical Design Handbook

## Positioning

C.O.D.E. v4.0 is an agent-assisted, conflict-oriented scientific discovery MVP. Agents help prepare configuration, context axes, validation plans, and critiques. Deterministic code performs conflict calculation, attribution, validation status assignment, and ranking.

## Architecture

The package-oriented implementation lives under `src/code_engine/`:

- Deterministic graph core: `code_engine.normalization`, `code_engine.graph`
- Contracts and config: `code_engine.schemas`, `code_engine.config`
- Validation and reporting: `code_engine.validation`, `code_engine.reporting`
- Query-driven discovery: `code_engine.query`
- Artifact adapters: `code_engine.acquisition.manifest`, `code_engine.extraction.llm_cache`
- Evaluation and future presentation: `code_engine.evaluation`, `code_engine.visualization`

The repository remains a research MVP, not a production-ready package. Legacy
`src.*` paths and scripts are retained as compatibility wrappers. See
`docs/PACKAGE_ARCHITECTURE.md` and `docs/STAGE_LAYER_MAPPING.md`.

## Deterministic Core

`code_engine.schemas` defines stable Pydantic objects for documents, triples, normalized entities, conflict edges, context mentions, context attribution, candidate hypotheses, validation results, and report items.

`code_engine.config` prevents silent data fallback. `configs/` is preferred;
legacy `config/schemas/` resolution is audited. Missing content or sections still
raise unless fallback is explicitly enabled. Old config modules are wrappers.

`src/pipelines/stage5_shannon_matrix.py` is now an orchestrator. It writes legacy-compatible `data/processed/l3/integrated_shannon_graph.json` and new audit outputs:

- `data/processed/l2/entity_normalization_audit.json`
- `data/processed/l3/conflict_edges.json`
- `data/processed/l3/context_attribution.json`
- `reports/l3_conflict_summary.md`

## Conflict Rules

Current thresholds are explicit and reported:

- `marginal_entropy_conflict_gate = 0.10`
- `type_i_attribution_gate = 0.45`
- Type III: conflicting and `total_obs <= 2` or `independent_labs_count == 1`
- Type I: conflicting, non-Type III, attribution score `>= 0.45`
- Type II: conflicting, non-Type III, attribution score `< 0.45`
- Otherwise: `Uncontested`

## Context Handling

`src/pipelines/context_mining.py` produces span-grounded `ContextMention` records. A mention is accepted only when the span appears in the source evidence sentence. L4 still preserves `minimal_augmented_context_set`, but also emits `separating_contexts` so alternative values such as HYPOXIA and NORMOXIA are not presented as simultaneous conditions.

## Validation

`code_engine.validation.curated_omics` uses a curated/demo mini-index and reports:

- `Sign_Consistent_Under_Curated_Index`
- `Sign_Inconsistent_Under_Curated_Index`
- `Unresolved_No_Coverage`

The old pass-by-fallback behavior is removed from the new validation path. New outputs include `omics_anchor_gene` and `registry_anchor_gene` when a curated registry mapping exists.

Skeleton validators exist for LINCS, GEO, DrugBank, and ChEMBL. They do not perform real external validation yet.

Validation is planned through `DomainAdaptiveValidationRouter` and executed
through `ValidatorRegistry` plugins. CuratedOmics is one curated/demo plugin,
not the complete validation layer. The router cannot mark support; the
deterministic aggregator combines plugin results. GEO, binding, pathway,
interaction, and clinical plugins return structured not-configured/no-coverage
results until local indexes exist.

## Domain-Adaptive Workflow

A first-class `DomainProfile` propagates from ResearchIntent through search,
L1 prompt/context selection, L2 registry/policy selection, and validation
planning. The six current profiles are rules-based and deterministic.
Scientific encoders remain limited to parsing, extraction, and suggestion;
L2/L3/L5 status logic and scoring remain deterministic. See
`DOMAIN_ADAPTIVE_WORKFLOW.md` and `DOMAIN_ADAPTIVE_VALIDATION.md`.

## Current Limits

- The omics index is not full LINCS.
- Ontology alignment uses a local curated resolver cascade; unmatched terms remain low-confidence fallback records.
- LLM extraction remains cached/API-dependent.
- Historical replay is an evaluation skeleton using entity/context overlap, not semantic proof.
- Agent outputs are deterministic/template suggestions and configuration artifacts, not scientific verdicts.
- Runtime artifacts follow `docs/ARTIFACT_POLICY.md`.

## Query-Driven Incremental Discovery Layer

`code_engine.query` is an upper layer over the existing deterministic pipeline. Query
parsing reuses conservative entity normalization, then coverage analysis reads
only the local artifact inventory and JSON knowledge store. Sufficient coverage
can produce an answer from existing hypotheses and evidence. Partial or
insufficient coverage produces missing dimensions and a dry-run ingestion plan;
it does not fabricate an unsupported mechanism.

`code_engine.acquisition.manifest` records per-paper progress through raw,
Stage1, L1, L1.5, L2, L3, L4, and L5 artifacts. PMID, PMCID, DOI, and normalized
title hashes are retained as duplicate-detection keys. `code_engine.graph.knowledge_store`
adapts current and legacy fields, preferring v2 normalized fields and recording
a warning when canonical-name/uppercase fallback is required.

LLM extraction reuse is represented by:

```text
sha256(paper_id + chunk_id + chunk_hash + domain_id + prompt_profile_id
       + prompt_version + output_schema_version + extraction_policy_version
       + model_name + model_family)
```

Only explicitly recorded completed extractions count as cache hits. Existing L1
files without complete fingerprint provenance are not guessed into the cache.

The current update command is planning-only, even when `--mode update` is used.
It does not run Stage0, Stage2, DeepSeek, or network search. The knowledge store
is a local JSON cache with in-memory indexes, not a production graph database.

## v4.2 Evidence And Mechanism Layer

`EvidenceRecord` unifies paper identifiers, grounded sentence/quote spans,
statement/evidence type, claim role, prompt profile, domain, confidence, and
warnings. Legacy evidence sentences are adapted into minimal records; ungrounded
records cannot carry high confidence.

`MechanismEdge` adds typed biological relations and entity types without
collapsing receptor complexes, genes, metabolites, compounds, and phenotypes
into equality aliases. Existing subject-object pairs remain readable.

Conflict edges retain Type I/II/III while adding a deterministic normalized
state derived from relation entropy, evidence count, independent labs, and
context attribution. This is a posterior-like heuristic, not Bayesian inference.

Hypotheses can be represented as hyperedges containing entities, separating
contexts, mechanism paths, missing links, bottlenecks, evidence IDs, validation
requirements, and coverage status. Reporting prefers these fields and falls
back to legacy CandidateHypothesis dictionaries.

The dry-lab loop and policy search do not call an LLM. Agents return structured
suggestions with mandatory deterministic-validation flags. See
`docs/V4_2_ARCHITECTURE.md` for limitations.

## Natural Language Intake And Prompt-Aware L1 Planning

`code_engine.query.intent` maps bounded Chinese/English expressions to a
ResearchIntent containing entities, condition, mechanism/comparison goals,
domain, evidence scope, and time scope. It reuses the normalization facade and
the explicit DomainRouter; unresolved input produces warnings.

`search_planner` generates primary, mechanism, behavioral, clinical, and
pairwise comparison queries. It does not retrieve papers. Fixture/mock candidates
are matched to artifact inventory using PMID, PMCID, DOI, and normalized title
hash.

Prompt compatibility is evaluated per chunk. Reuse requires an unchanged chunk
hash and compatible domain, prompt profile, prompt version, output schema,
extraction policy, and model contract. Same-family model reuse is opt-in. The L1
batch planner then separates reusable chunks, first extraction, prompt/schema/policy/hash
re-extraction, payload builds, downloads, estimated cost, and budget status.
No download or API execution occurs in this planning layer.

L1 v2 prompt compilation is package-owned. Default sampling uses temperature
`0.0` and top-p `1.0`; chunk index does not alter it. `L1ExtractedClaim` retains
grounded spans, context slots, extraction metadata, and a complete fingerprint,
and converts to EvidenceRecord or the legacy tuple contract. Stage2 is offline
by default; its initial API adapter and cache write-through require explicit execution.

The intake executor adds separate gates for external effects. Saved search plans
drive PMC/PubMed acquisition only with `execute+network`; L1 v2 calls occur only
with `execute+api`. Candidate papers are deduplicated against manifest metadata
and raw paths. Seed triples are typed non-evidence planning records and are not
accepted by EvidenceRecord or conflict-discovery interfaces. Successful L1 v2
claims write through the cache and also produce a legacy Stage3-compatible file.

## Type-Aware Resolver Cascade

`code_engine.normalization` replaces alias-map/uppercase-only normalization with
lexical cleanup, entity typing, local registry lookup, candidate scoring, typed
relations, deterministic decision status, and audit output. The preferred
registry is `configs/normalization/entity_registry.json`; the synchronized
legacy path remains under `config/schemas/`.

Resolved entities carry canonical IDs, semantic levels, external-ID placeholders,
relations, match type, candidates, confidence, warnings, and an explicit
high-confidence graph permission. Ambiguous and fuzzy candidates cannot enter
that graph tier. Unknown terms receive `unresolved_fallback` and confidence no
greater than `0.35`.

Layer 3 thresholds are unchanged. Observation and conflict traceability now
retain normalization graph-use permission so a later filtering policy can
separate registry-resolved evidence from unresolved legacy terms. The optional
candidate proposer is disabled and cannot select final canonical entities.
# Workflow orchestration boundary

`code_engine.workflow` owns sequencing, RunState persistence, isolation, resume, and permission gates. Scientific formulas remain in their layer modules. `code_engine.cli.run` is the main entry point; Stage scripts are retained for legacy/debug use.
