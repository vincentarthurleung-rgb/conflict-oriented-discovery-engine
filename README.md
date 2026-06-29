# C.O.D.E. v4.0 MVP

C.O.D.E. is an agent-assisted, conflict-oriented scientific discovery system for the current ketamine antidepressant-response corpus. It is designed as:

- Agentic Control Plane: generates configs, validation plans, and critic reports.
- Deterministic Pipeline Core: performs extraction post-processing, ontology alignment, conflict discovery, context attribution, graph search, validation state assignment, and ranking.
- Evaluation Framework: provides a historical replay benchmark skeleton.
- Extension Modules: validators and agents can be expanded without changing the deterministic core.

## Layers

- Layer 0: Literature Acquisition via `scripts/stage0_fetch_pmc.py` and `scripts/stage0_5_fetch_abstracts.py`.
- Layer 1: Scientific Fact Extraction via `scripts/stage2_l1_extract.py`.
- Layer 2: Ontology Alignment via `code_engine.graph.ontology_alignment`.
- Layer 3: Conflict Discovery via `code_engine.graph.conflict_discovery`.
- Layer 4: Context Mining via `python -m code_engine.graph.context_mining`.
- Layer 5: Context Attribution via `code_engine.graph.context_attribution`.
- Layer 6: Mechanism Graph Search via `scripts/stage6_l4_infer.py`.
- Layer 7: External Validation via `scripts/stage7_l5_verify.py`.
- Layer 8: Scientific Report Generation via `scripts/stage8_l6_results.py`.

## Important Limits

- The current omics registry is curated/demo scale and is not full LINCS validation.
- Ontology alignment uses a local curated resolver cascade; unknown terms remain low-confidence unresolved records.
- L1 v2 is offline by default; API execution requires explicit `--execute --api`.
- Agents generate configuration and critique only; they are not scientific judges.
- Hypotheses with no validator coverage are `Unresolved_No_Coverage` and are not treated as passed.

## Current Clean Architecture Boundary

- `src/code_engine/` is the primary package and the starting point for new code.
- `src.*` legacy namespaces re-export `code_engine.*` implementations.
- `src/pipelines/stage*.py` retains legacy orchestration and API-dependent stages.
- `scripts/` contains legacy compatibility entrypoints.
- `configs/` is preferred; `config/schemas/` remains a legacy config path.
- `src/agents/` is a config-generation/control plane; agents are not scientific judges and do not change final scores.
- Legacy stage names remain for compatibility. New documentation explains the system as Layer 0-8 in `docs/STAGE_LAYER_MAPPING.md`.

See also:

- `docs/STAGE_LAYER_MAPPING.md`
- `docs/ARTIFACT_POLICY.md`
- `docs/CODE_REVIEW_GUIDE.md`
- `docs/PACKAGE_ARCHITECTURE.md`

Install the package in editable mode for development, or run commands directly
from the repository checkout through the source-tree bootstrap:

```bash
python -m pip install -e .
python -m code_engine.cli.query --help
```

## Review-Readiness Audits

The repository includes non-blocking validators for cached manifest and Stage1
payload artifacts. These do not rewrite Stage0/Stage1 outputs.

```bash
python -m src.pipelines.manifest_validation
```

Use `--strict` when review requires critical manifest/payload errors to fail the
command.

## Common Commands

Use cached data and rerun deterministic L2/L3:

```bash
python scripts/stage4_l2_normalize.py --strict-config
```

Allow demo fallback explicitly:

```bash
python scripts/stage4_l2_normalize.py --config-path missing.json --allow-fallback --no-strict-config
```

Mine span-grounded context mentions:

```bash
python -m code_engine.graph.context_mining
```

Run L4 graph search:

```bash
python scripts/stage6_l4_infer.py
```

Run L5 validator orchestrator:

```bash
python scripts/stage7_l5_verify.py
```

Run L6 report export:

```bash
python scripts/stage8_l6_results.py
```

Generate agentic support artifacts:

```bash
python -m src.agents.domain_bootstrap_agent "Ketamine antidepressant response"
python -m src.agents.context_axis_agent
python -m src.agents.validation_planner_agent
python -m src.agents.hypothesis_critic_agent
```

Run historical replay skeleton:

```bash
python -m code_engine.evaluation.historical_replay --cutoff-year 2010 --future-start 2011 --future-end 2015
```

## Query-Driven Incremental Discovery

The query layer sits above Layer 0-8. It normalizes a relation or topic, checks
the local knowledge graph first, and either assembles an evidence-bounded answer
or writes a delta ingestion plan. Its default behavior is offline and makes zero
LLM API calls.

```bash
python -m code_engine.cli.query --query "氯胺酮 - 抑郁症" --mode parse
python -m code_engine.cli.query --query "ketamine -> BDNF" --mode coverage
python -m code_engine.cli.query --query "ketamine -> synaptogenesis" --mode plan --dry-run
python -m code_engine.cli.query --query "ketamine -> BDNF" --mode answer --no-api
python -m code_engine.cli.query --query "esketamine -> depression" --mode update --dry-run --max-api-calls 50
```

Coverage verdicts use a fixed MVP score: exact pair `0.3`, conflict edge `0.2`,
context mentions `0.2`, validation result `0.1`, and sufficient neighbor evidence
`0.2`. Scores at least `0.65` need no update, scores from `0.30` to below `0.65`
recommend a delta update, and lower scores recommend a new corpus search plan.

L1 v2 defines one SHA-256 fingerprint over paper/chunk identity, domain, prompt
profile/version, output schema, extraction policy, and model name/family. Stage2
is a guarded wrapper around prompt compilation, cache planning, and explicit execution.

The current `update` mode only produces a dry-run plan. It does not fetch papers,
search the web, or call DeepSeek. The local JSON/in-memory knowledge store is an
MVP index, not a production graph database.

## Repository Data Policy

This repository does not treat raw PMC XML, PubMed abstract downloads, L1
outputs, processed graphs, query outputs, or generated reports as source code.
Raw literature is regenerable using the retained
`data/metadata/global_manifest.json` and the reviewed Stage0 acquisition
wrappers.

Current experimental outputs should be isolated under `runs/<run_id>/`. Old L1
prompt v1 outputs have been intentionally removed from the active workspace and
are not a current knowledge graph source. New L1 v2 runs should use the Domain
Router, Prompt Registry, and Prompt Compiler once their extraction integration
is complete. Tests use `tests/fixtures/`, not historical runtime artifacts.

See `docs/CLEANUP_POLICY.md` and `docs/ARTIFACT_POLICY.md`.

## Safe Legacy Cleanup And Fresh Runs

Runtime cleanup is inventory-first and dry-run by default:

```bash
python scripts/maintenance/cleanup_legacy_artifacts.py --dry-run
python scripts/maintenance/cleanup_legacy_artifacts.py --apply
```

Audits are written under `cleanup_reports/`. Missing current inventory,
knowledge-store, or LLM-cache files produce explicit empty states; query reports
include `runtime_data_status`, `knowledge_store_status`, and
`using_legacy_data`. Archived paths are never implicit inputs.

See `docs/FRESH_RUN_GUIDE.md` and `docs/LEGACY_CODE_POLICY.md`.

## C.O.D.E. v4.2 Research Architecture

The v4.2 layer extends pair-based graph records with first-class
`EvidenceRecord`, typed `MechanismEdge`, posterior-like uncertainty-aware
conflict state, and `HypothesisHyperedge`. A deterministic dry-lab loop checks
coverage before proposing delta ingestion, while heuristic policy scoring ranks
mechanism paths using fixed documented weights.

Agentic KG enrichment components return suggestions only. They cannot change
graph truth, validation status, conflict probabilities, coverage verdicts, or
scientific scores without deterministic validation. All v4.2 tests use local
fixtures and make zero API calls.

See `docs/V4_2_ARCHITECTURE.md` and `docs/RELATED_SYSTEMS_DESIGN_MATRIX.md`.

## Natural Language Research Intake

Natural-language requests are parsed into a `ResearchIntent` before any
extraction planning. The system selects a biomedical domain and prompt profile,
generates PubMed/PMC query strings, matches fixture/mock candidates against the
manifest inventory, checks each old L1 chunk fingerprint, and produces a dry-run
L1 batch plan.

```bash
python -m code_engine.cli.query \
  --query "我想了解一下当前氯胺酮在抑郁症的作用" \
  --mode intake --dry-run --no-api
```

Additional modes are `intent`, `search-plan`, and `l1-plan`. Search plans do not
perform online retrieval. Old L1 output is reusable only when chunk hash,
domain, prompt profile/version, output schema, extraction policy, and model
contract are compatible. Actual API calls remain zero.

See `docs/NATURAL_LANGUAGE_INTAKE_DESIGN.md`.

## Domain-Adaptive Scientific Workflow

`DomainRouter` now emits a complete `DomainProfile` for six supported domain
families. The profile controls literature-search templates, the L1 prompt and
required contexts, the L2 registry/resolver policy, and L5 validator planning.
Downstream normalization, conflict classification, result aggregation, and
scientific scoring remain deterministic. Scientific encoders may extract or
suggest structured information but do not adjudicate truth.

CuratedOmics is one curated/demo validator plugin, not the whole validation
layer and not full LINCS. Unconfigured external validator skeletons return
structured no-coverage/not-configured results. See
`docs/DOMAIN_ADAPTIVE_WORKFLOW.md` and `docs/DOMAIN_ADAPTIVE_VALIDATION.md`.

## Abstract-First Conflict Discovery

Large runs now use abstracts for low-cost claim screening, L2 normalization,
pharmacological direction normalization, and abstract-level Shannon entropy.
These outputs are conflict candidates, not final conflicts and not
high-confidence mechanism evidence. Full text is escalated only for papers in
the conflict focus set; ranked sections and bounded spans are extracted instead
of processing every full-text chunk.

Missing full text is recorded as a coverage gap, not a contradiction.
Mechanistic inhibition is distinct from therapeutic harm. Large-scale batch
evaluation measures problem-discovery yield, actionability, traceability, and
cost efficiency rather than treating hypothesis accuracy as the main endpoint.
See `docs/PROGRESSIVE_FULLTEXT_L1.md`,
`docs/ABSTRACT_FIRST_CONFLICT_SCREENING.md`, and
`docs/BATCH_DISCOVERY_EVALUATION.md`.

## Anchor-Based External Validation

Layer 6 extends the existing `code_engine.validation` package. Hypotheses,
conflicts, mechanism paths/gaps, gene sets, clinical contexts, entities, and
triples become provenance-preserving ValidationAnchors. Capability metadata
routes semantic questions to validators; QueryPlanner and ResourceGuard decide
whether each bounded query uses a local index, remote provider, cache, or is
blocked.

Large evidence and signal outputs are streaming JSONL. DuckDB, SQLite, indexed
Parquet, and small JSONL indexes are supported; unindexed large scans and
in-memory full databases are not. External evidence/signals are not proof, no
record is not contradiction, and cache miss is not no coverage. See
`docs/EXTERNAL_VALIDATION_ANCHORS.md` and
`docs/RESOURCE_AWARE_EXTERNAL_VALIDATION.md`.

## L1 v2 Extraction Consistency

L1 prompt planning uses fixed `temperature=0.0` and `top_p=1.0`; chunk index
does not change default sampling. Domain Router selects one of six domain
profiles, Prompt Compiler records a stable prompt hash, and complete
fingerprints determine cache compatibility. Old L1 files without fingerprint
and domain-profile metadata are not reusable unless explicitly allowed.

`L1ExtractedClaim` is EvidenceRecord-ready and retains fields needed for a
MechanismEdge after L2 normalization. `python -m code_engine.cli.extract
--dry-run --no-api` performs planning only and makes zero API calls. See
`docs/L1_EXTRACTION_V2.md`.

## Natural Language To Executable Literature Intake

Natural-language intake can now produce non-evidence seed triples, sanitized
PMC/PubMed search plans, manifest-aware acquisition, payload chunks, and L1 v2
claims. Dry-run remains the default. Real acquisition requires `--execute
--network`; real L1 calls require `--execute --api` and `DEEPSEEK_API_KEY`.

```bash
python -m code_engine.cli.intake \
  --query "我想了解一下当前氯胺酮在抑郁症中的作用" \
  --dry-run --no-api --no-network
```

Seed triples are planning objects with `is_evidence=false`; only claims
extracted from downloaded papers can become EvidenceRecord or enter L3. See
`docs/NATURAL_LANGUAGE_TO_LITERATURE_WORKFLOW.md`.

## Type-Aware Biomedical Normalization

### L2 Resolver Cascade Is Now The Default Mainline Normalizer

L2 now carries ResolverCascade decisions directly into L3: canonical IDs,
entity types, semantic levels, typed relations, statuses, and graph-use flags.
L3 pair keys prefer canonical IDs, preventing receptor complexes, gene
subunits, metabolites, parent compounds, assays, and phenotypes from being
collapsed by display-name normalization.

The old synonym-only path requires `--legacy-synonym-only`. Unknown uppercase
fallback remains visible in audit output but is low confidence and excluded
from high-confidence conflict statistics by default. The optional LLM candidate
proposer remains disabled and cannot determine final normalization.

Layer 2 now uses lexical normalization, entity typing, a local curated registry,
relation-aware candidates, and deterministic acceptance. It distinguishes gene
subunits from receptor complexes, metabolites and salts from parent compounds,
and assays from the phenotypes they measure.

Unknown uppercase terms remain traceable but are marked `unresolved_fallback`
with confidence at most `0.35`; they are not permitted in high-confidence graph
use. The optional candidate proposer is disabled and cannot adjudicate final
normalization decisions.

```bash
python -m code_engine.cli.normalize --term "GluA1" --json
python -m code_engine.cli.normalize --term "norketamine" --show-candidates
```

See `docs/BIOMEDICAL_ENTITY_NORMALIZATION.md`.
# Recommended workflow entry point

Use `python -m code_engine.cli.run --query "..." --dry-run --no-api --no-network --until report` for new research runs. It creates an isolated `runs/<run_id>/` RunState and report. Dry-run, no-API, and no-network are defaults; execution permissions must be explicit. See [End-to-End Workflow](docs/END_TO_END_WORKFLOW.md) and [RunState and Reproducibility](docs/RUN_STATE_AND_REPRODUCIBILITY.md). Stage scripts remain legacy/debug entry points.

Natural-language understanding is [LLM-first](docs/LLM_FIRST_SEMANTIC_INTAKE.md). Deterministic parsing is a semantically degraded no-API fallback; rules are limited to schema checks, allowed-domain validation, sanitization, evidence boundaries, and external-call guards. Low-confidence intake blocks execute mode unless explicitly allowed.

C.O.D.E. now includes an evidence-grounded [MechanismGraph MVP](docs/MECHANISM_GRAPH.md), moving the workflow toward `Paper → Evidence → Mechanism → Conflict → Hypothesis → Validation`. Mechanism edges come only from L2 paper observations; seed/user-intent triples never enter the graph. L3 remains unchanged and annotates matching mechanism edges after conflict discovery. Storage remains local JSON; see [Mechanism-Centered Knowledge Store](docs/MECHANISM_CENTERED_KNOWLEDGE_STORE.md).

Layer 2 uses the [Entity Resolution Hub](docs/ENTITY_RESOLUTION_HUB.md), combining explicit curated anchors, an audited cache, guarded external provider skeletons, and an optional ungrounded LLM proposer. A deterministic adjudicator makes every canonical decision. The old ketamine registry is a pilot fixture only; no API or network provider is enabled by default. See [L2 audit artifacts](docs/L2_ENTITY_RESOLUTION_AUDIT.md).

## External validation hardening

Before any pilot, local validation indexes are schema-bound directories with
`schema.json`, `manifest.json`, and bounded records. Builders, preflight, actual
resource accounting, and a deterministic aggregator benchmark are documented
in [Validation Index Schema](docs/VALIDATION_INDEX_SCHEMA.md), [Index Builders](docs/VALIDATION_INDEX_BUILDERS.md), [Preflight](docs/VALIDATION_PREFLIGHT.md), and [Aggregator Benchmark](docs/VALIDATION_AGGREGATOR_BENCHMARK.md).

Remote clients are guarded request-planning boundaries. They do not perform
HTTP by default; execution requires execute, network, and external-validation
permission together, plus a configured transport. Real databases must still go
through schema/manifest validation, query planning, and the resource guard.
This work is architecture hardening, not a pilot or evidence of hypothesis
accuracy.
