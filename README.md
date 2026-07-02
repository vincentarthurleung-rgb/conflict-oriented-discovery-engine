# C.O.D.E. — Conflict-Oriented Discovery Engine

**C.O.D.E.** is an agent-assisted, conflict-oriented biomedical discovery system. It acquires scientific literature, extracts structured claims, normalizes entities, discovers mechanistic conflicts, forms evidence-grounded hypotheses, and executes validation — all with deterministic core logic and zero implicit LLM fallback.

## Architecture Overview

The system is organized into **30+ modular packages** under `src/code_engine/`, spanning the full discovery pipeline:

| Package | Purpose |
|---------|---------|
| `acquisition` | PubMed/PMC literature acquisition, manifest management, diversified query dispatch |
| `batch` | Batch triple processing engine with resume/hash invalidation |
| `cli` | Command-line entry points (`run`, `intake`, `extract`, `query`, `normalize`, `validate`, `batch`, etc.) |
| `config` | Configuration loading, validation, pilot profiles |
| `corpus` | Global incremental corpus: paper registry, bibliographic provenance, knowledge merge, L1 task cache, coverage precheck |
| `domain` | Domain router, prompt registry/compiler, domain profile models |
| `encoder` | Scientific encoder: LLM-first semantic intake, semantic verifier, fallback parser |
| `evaluation` | Historical replay, batch discovery evaluation metrics |
| `evidence_graph` | Evidence graph builder, conflict reasoning, bundle builder, direction/polarity normalization |
| `external_data` | External data source management, API cache |
| `extraction` | L1 scientific fact extraction: abstract screening, progressive fulltext, evidence span selection, polarity analysis, L1 response model, client factory |
| `graph` | Knowledge store, conflict discovery, context mining/attribution, ontology alignment |
| `hypothesis` | Hypothesis formation: candidate builder, hyperedge builder, reasoning, scoring, search, IO, validation requirements |
| `mechanism` | Mechanism graph: edge builder, graph builder, conflict annotator, evidence linker, path finder |
| `normalization` | L2 entity normalization: resolver cascade, registry, entity type, layered grounding, adjudicator, external providers |
| `query` | Research intent parsing, search planner, intake pipeline, prompt compatibility |
| `reporting` | Full abstract pipeline reporting, whitebox case reports |
| `search` | Semantic search intent, query guard, context guard, search plan freeze/replay |
| `schemas` | Data models: L1 extraction, evidence, hypothesis hyperedge, reasoning record, triples, validation |
| `temporal` | Temporal reasoning: evidence timeline, hypothesis comparison, paper year filter, status classifier, windows |
| `tools` | Utility tools: rebuild graph/hypothesis, LINCS L1000 index builder, core observation audit |
| `validation` | External validation framework: router, registry, plugins (CuratedOmics, DrugBank, ChEMBL, GEO, etc.), index builders, remote clients, preflight, execution engine, benchmarks |
| `workflow` | Workflow orchestration: orchestrator, steps, run state, runtime provenance, reports |

## Quick Start

```bash
pip install -e .
python -m code_engine.cli.run --query "..." --dry-run --no-api --no-network --until report
```

Dry-run, no-API, and no-network are **defaults**. Execution requires explicit `--execute`, `--api`, and/or `--network` flags.

## CLI Entry Points

### Primary: `code_engine.cli.run` (recommended)

Creates an isolated `runs/<run_id>/` RunState and runs the full pipeline up to a configurable stage.

```bash
python -m code_engine.cli.run --query "metformin -> AMPK -> cancer" --dry-run --until report
python -m code_engine.cli.run --query "ketamine -> BDNF -> synaptogenesis" --execute --api --network --until l1
```

### Intake pipeline

```bash
python -m code_engine.cli.intake --query "我想了解一下氯胺酮在抑郁症中的作用" --dry-run --no-api --no-network
```

### Query

```bash
python -m code_engine.cli.query --query "ketamine -> BDNF" --mode coverage
python -m code_engine.cli.query --query "ketamine -> BDNF" --mode answer --no-api
```

### L1 Extraction

```bash
python -m code_engine.cli.extract --dry-run --no-api
python -m code_engine.cli.extract --paper-id PMC12345678 --domain general_biomedical
```

### L2 Normalization

```bash
python -m code_engine.cli.normalize --term "GluA1" --json
python -m code_engine.cli.normalize --term "norketamine" --show-candidates
```

### Search Plan Freeze / Replay

```bash
python -m code_engine.cli.run --query "..." --freeze-search-plan
python -m code_engine.cli.run --query "..." --replay-search-plan path/to/frozen.json
```

### Hypothesis Rebuild (from existing run)

```bash
python -m code_engine.tools.rebuild_graph_hypothesis --run-id 20260702_131449
```

### LINCS L1000 Index Build

```bash
python -m code_engine.tools.build_lincs_l1000_index --data-dir /path/to/LINCS
```

## Pipeline Overview

The discovery pipeline progresses through these logical stages:

```
Research Intent → Search Planning → Literature Acquisition → 
Abstract Screening → Progressive L1 Extraction → L2 Normalization → 
Evidence Graph → Conflict Discovery → Hypothesis Formation → 
Temporal Reasoning → External Validation → Report Generation
```

### Key Design Principles

- **Deterministic core**: L2 normalization, conflict classification, result aggregation, and scientific scoring are fully deterministic. LLM usage is limited to parsing, extraction, and structured suggestion.
- **No implicit fallback**: Every fallback path requires explicit opt-in. Low-confidence intent blocks execution unless `--allow-low-confidence` is set.
- **Run isolation**: Every `code_engine.cli.run` invocation creates an isolated `runs/<run_id>/` directory with its own RunState, artifacts, and provenance trace.
- **Progressive fulltext**: Abstracts are processed first; full-text escalation occurs only for papers in the conflict focus set, gated by conflict signal strength.
- **Evidence-grounded hypotheses**: Mechanism edges come only from L2 paper observations. Seed/user-intent triples are planning metadata (`is_evidence=false`) and never enter the evidence graph.
- **Domain-adaptive profiles**: `DomainRouter` selects one of six domain profiles (general_biomedical, neuropharmacology, drug_target_binding, pathway_biology, clinical_outcome, protein_interaction), controlling search templates, L1 prompts, L2 registry policy, and validation routing.
- **Source-gated evidence**: Query-only context does not enter the core graph. Cross-context mechanism queries are permitted but downgraded. Context source strength is audited.

## Key Modules

### Literature Acquisition (`code_engine.acquisition`)
- PubMed/PMC search with runtime year-range filtering
- Diversified acquisition: even split across queries, dedup, count taxonomy
- Full-text availability checking
- Search plan freeze/replay for deterministic reproduction

### L1 Extraction (`code_engine.extraction`)
- Abstract screening with configurable timeout and graceful degradation
- Progressive fulltext: ranked sections → bounded evidence spans
- Evidence span selection and section ranking
- Pharmacological direction/polarity analysis
- L1 response model with standardized output format
- Client factory: DeepSeek, fake/pilot, generic JSON clients
- Prompt registry with runtime semantics, version management, context slot resolution

### L2 Normalization (`code_engine.normalization`)
- Resolver cascade: lexical → curated registry → relation-aware → adjudicator
- Layered grounding: top-down/bottom-up entity resolution
- Entity type discrimination (gene subunits vs receptor complexes, metabolites vs parent compounds, assays vs phenotypes)
- External provider skeletons (MyGene, UniProt, PubChem, ChEMBL)
- LLM candidate proposer (disabled by default, cannot adjudicate)
- Entity Resolution Hub with audited cache

### Evidence Graph (`code_engine.evidence_graph`)
- Graph builder from L1 extraction results
- Bundle builder: related evidence packaged as verifiable units
- Conflict reasoning: true conflict vs information absence
- Direction/polarity normalization
- Graph IO (JSON/JSONL) and graph reports

### Hypothesis Formation (`code_engine.hypothesis`)
- Run-scoped, artifact-grounded hypothesis generation
- Candidate builder from evidence graph
- Hyperedge builder with provenance-aware edge construction
- Scoring with context weights and evidence accumulation
- Reasoning path tracing
- Search with run-scoped context awareness
- JSONL streaming IO for large-scale hypothesis sets
- Validation requirements derivation from hypothesis structure

### Temporal Reasoning (`code_engine.temporal`)
- Evidence timeline: chronological organization of evidence evolution
- Hypothesis comparison across time points
- Status classifier: support/contradict/contradiction detection
- Paper year filter: runtime-configurable year range (no hardcoded defaults)
- Sliding window analysis

### Corpus Management (`code_engine.corpus`)
- Paper registry: canonical identity management
- Bibliographic index: DOI/PMCID/PMID multi-key resolution
- Corpus cache: incremental updates with dedup
- Knowledge merge: cross-paper redundancy and conflict resolution
- L1 task cache: avoid re-extraction
- Coverage precheck: assess existing knowledge coverage
- Artifact provenance tracking

### External Validation (`code_engine.validation`)
- Router with domain-aware validator dispatch
- Registry of named validator plugins
- 14+ index schema configurations (ChEMBL, DrugBank, GEO, LINCS, etc.)
- Index builders: metadata-first construction from external sources
- Remote clients: guarded HTTP with rate limiting (ChEMBL, ClinicalTrials, OpenTargets, PubChem, Reactome, UniProt)
- Preflight: environment/resource readiness checks before execution
- Execution engine: batch validation with progress tracking
- Deterministic result aggregator with benchmark framework
- Skeleton validators for external resources
- LINCS L1000 local validator

### Workflow Orchestration (`code_engine.workflow`)
- Orchestrator with conditional branching and dynamic step composition
- Isolated RunState with full reproducibility metadata
- Runtime provenance: artifact source tracing, contamination preflight, run isolation
- Triple metadata extraction

### Domain & Search (`code_engine.domain`, `code_engine.search`)
- DomainRouter: 6 domain profiles with registry-only mode
- PromptRegistry: runtime template resolution with caching
- SemanticSearchIntent: LLM-first search intent generation
- QueryGuard: filter context-only / object-only incomplete queries
- ContextGuard: cross-context mechanism query permissions
- Search plan freeze/replay for deterministic reproduction

## Important Constraints

- **No static journal weights** in core reasoning. Belief weights are not used for conflict or hypothesis scoring.
- **No hardcoded temporal defaults**. Year range is runtime-configurable; missing-year papers excluded only when filter is enabled.
- **No silent zero download**. Acquisition diagnostics detect and report empty results.
- **No global evidence injection**. All evidence is traceable to specific papers.
- **No legacy pipeline in main workflow**. Stage scripts are legacy/debug entry points only.
- **Agents generate config and critique only**; they are not scientific judges and do not change final scores.
- **Hypotheses with no validator coverage** are `Unresolved_No_Coverage`, not treated as passed.
- **External evidence is not proof**, no record is not contradiction, cache miss is not no coverage.

## Repository Structure

```
src/code_engine/          # Primary package (30+ modules)
configs/                  # Single configuration root
docs/                     # Design documentation (50+ documents)
tests/                    # Test suite (200+ test files)
scripts/                  # Legacy/debug entry points
runs/                     # Isolated run outputs (.gitkeep)
data/                     # Data directories with README placeholders
```

## Domain Neutral Defaults

The system is **domain-neutral by default**. No domain-specific (e.g., ketamine) configuration is implicitly loaded. Domain-specific profiles are explicit pilot configurations:

```bash
python -m code_engine.cli.run --query "..." --pilot ketamine
```

## Documentation

Key design documents in `docs/`:

- [Architecture](docs/PACKAGE_ARCHITECTURE.md) · [V4.2 Architecture](docs/V4_2_ARCHITECTURE.md)
- [End-to-End Workflow](docs/END_TO_END_WORKFLOW.md) · [RunState & Reproducibility](docs/RUN_STATE_AND_REPRODUCIBILITY.md)
- [Domain-Adaptive Workflow](docs/DOMAIN_ADAPTIVE_WORKFLOW.md) · [Validation](docs/DOMAIN_ADAPTIVE_VALIDATION.md)
- [L1 Extraction V2](docs/L1_EXTRACTION_V2.md) · [Progressive Fulltext](docs/PROGRESSIVE_FULLTEXT_L1.md)
- [Abstract-First Conflict Screening](docs/ABSTRACT_FIRST_CONFLICT_SCREENING.md)
- [Biomedical Entity Normalization](docs/BIOMEDICAL_ENTITY_NORMALIZATION.md) · [Entity Resolution Hub](docs/ENTITY_RESOLUTION_HUB.md)
- [Mechanism Graph](docs/MECHANISM_GRAPH.md) · [Knowledge Store](docs/MECHANISM_CENTERED_KNOWLEDGE_STORE.md)
- [Hypothesis Formation](docs/RUN_SCOPED_HYPOTHESIS_FORMATION.md) · [Artifact Contract](docs/HYPOTHESIS_ARTIFACT_CONTRACT.md)
- [Global Incremental Corpus](docs/GLOBAL_INCREMENTAL_CORPUS.md) · [Paper Registry](docs/PAPER_REGISTRY_AND_BIBLIOGRAPHIC_PROVENANCE.md)
- [External Validation Anchors](docs/EXTERNAL_VALIDATION_ANCHORS.md) · [Resource-Aware Validation](docs/RESOURCE_AWARE_EXTERNAL_VALIDATION.md)
- [Validation Index Schema](docs/VALIDATION_INDEX_SCHEMA.md) · [Index Builders](docs/VALIDATION_INDEX_BUILDERS.md) · [Preflight](docs/VALIDATION_PREFLIGHT.md)
- [LLM-First Semantic Intake](docs/LLM_FIRST_SEMANTIC_INTAKE.md) · [Natural Language Intake](docs/NATURAL_LANGUAGE_INTAKE_DESIGN.md)
- [Batch Discovery Evaluation](docs/BATCH_DISCOVERY_EVALUATION.md)
- [Cleanup Policy](docs/CLEANUP_POLICY.md) · [Fresh Run Guide](docs/FRESH_RUN_GUIDE.md) · [Legacy Code Policy](docs/LEGACY_CODE_POLICY.md)
- [Stage/Layer Mapping](docs/STAGE_LAYER_MAPPING.md) · [Artifact Policy](docs/ARTIFACT_POLICY.md)
- [Code Review Guide](docs/CODE_REVIEW_GUIDE.md)

## Installation

```bash
git clone https://github.com/vincentarthurleung-rgb/conflict-oriented-discovery-engine
cd conflict-oriented-discovery-engine
pip install -e .
```

Requires Python 3.11+.
