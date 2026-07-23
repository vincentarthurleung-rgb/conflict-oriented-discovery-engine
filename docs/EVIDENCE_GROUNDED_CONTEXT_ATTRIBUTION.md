# Evidence-grounded context attribution v2

## Audit of the existing architecture

The repository has several historically named layers, so this audit follows
actual imports rather than stage labels.

- The package L4 context-mining entry point is
  `code_engine.graph.context_mining.mine_context_mentions`; its CLI scans L1.5
  refined files and writes `data/processed/l4/context_mentions.json`.
  `code_engine.reporting.full_abstract_pipeline.build_l4_context_mining` is the
  active run-scoped abstract/reentry report builder. Fulltext reentry calls that
  report builder after writing its L2 observations.
- The rule matcher is `graph/context_mining.py`. It searches configured phrase
  maps with regular expressions, plus span-checks pre-existing L1.5 context
  values. The run-scoped abstract reporter also uses fixed cancer/mechanism
  substring lists.
- Discovery-lane comparability is
  `discovery.lanes.evaluate_claim_comparability`. It compares subject/object
  families, relation class, intervention state and flattened context terms with
  a weighted deterministic score. Formal graph/source gates remain in
  `workflow.steps`, `evidence_graph.builders`, and
  `fulltext.evidence_projection`.
- Variational attribution is in `graph.context_attribution`. Before this
  change, `graph.conflict_discovery.build_conflict_graph` called it for every
  legacy grouped edge and its score influenced the legacy Type I/II label.
  The progressive workflow skips this whole legacy conflict step when L1 mode
  is not `legacy`; Formal v3 projection and fulltext confirmation did not use
  this EM function. It was therefore active in the legacy production path,
  but not the progressive/Formal v3 authority path.
- Abstract observation evidence comes from the L1/L2
  `evidence_sentence`. The v2 abstract contract now deliberately copies only
  that sentence, its run/paper provenance, observation ID, and read-only
  canonical/polarity references.
- Formal fulltext evidence is represented by
  `ExperimentalObservationV3`: exact `provenance.evidence_spans`, experiment
  context, a non-fanned-out `interventions` list and `combination_mode`,
  measurement, observed result, interpretation, statement role, evidence
  family, and eligibility. Stable source anchors are generated and resolved by
  `fulltext.evidence_anchors`.
- Deterministic candidate generation exists in the evidence graph and in
  `discovery.lanes.evaluate_weak_candidate_pairs`. Fulltext escalation reads
  `graph_conflict_candidates.jsonl` through
  `fulltext.candidate_selection`. Context attribution v2 applies its own
  narrow pre-screen only to same canonical endpoint/opposing-polarity,
  evidence-qualified pairs, never all observation pairs.
- Existing L4/L5 abstract artifacts are descriptive inputs to reporting and
  hypothesis presentation. Formal conflict eligibility remains owned by the
  strict-core, species, polarity, evidence-family, canonical-edge, conflict
  bundle, and projection gates. `fulltext.projection_handoff` explicitly keeps
  projection authoritative for formal fulltext strict core and reentry
  authoritative only for context lanes.
- Provider construction is centralized in
  `extraction.client_factory`; existing L1 cache support is in
  `extraction.llm_cache`, and run resume/provenance is in
  `workflow.orchestrator` and `workflow.runtime_provenance`. Fulltext recovery
  already uses call-by-call ledgers. Context attribution v2 has a separate
  content-addressed extraction/pair cache, call-by-call ledger, retry queue,
  hard call bounds, and explicit resume.
- Existing domain semantics are split between
  `domain.prompt_registry`, generated domain profiles, and the Formal v3
  `fulltext.experimental_semantics_registry`. Context attribution adds a
  separate cross-domain factor registry; it does not replace canonical entity
  resolvers or Formal v3 normalization.

## New production path

`configs/context_attribution/production.json` selects
`llm_evidence_grounded`. The old mode is named
`variational_em_experimental`, is disabled by default, has a distinct schema
profile, and is not eligible for production handoff. Default calls to the
legacy graph builder no longer invoke EM; an ablation must request the
experimental mode explicitly.

The new path is:

1. deterministic conflict-candidate screening;
2. one cached context extraction per observation;
3. one semantic comparison per retained pair;
4. deterministic schema, evidence, anchor, quantity/unit, normalization, and
   ownership validation;
5. a fail-closed comparability gate;
6. the unchanged formal conflict/hypothesis gates.

An LLM result never changes polarity, canonical IDs, strict core, derived sign,
confirmed-conflict status, or final hypothesis eligibility.

## Input contracts

`abstract_sentence_only` contains one evidence sentence and a synthetic anchor
covering exactly that sentence. Fulltext-looking fields are not copied. Missing
species, tissue, dose, stage, design, or other context must remain `unknown`.

`fulltext_evidence_chain` contains the direct result evidence and the local
chain:

`experimental_system → intervention_or_exposure → comparator_or_control →
measurement → observed_result → interpretation`.

Each node carries authoritative local anchor IDs. The contract also records
logic-chain ID, experiment/evidence family, intervention combination,
measurement identity, section/role, and provenance. Multiple interventions
remain one grouped experiment.

## Schemas, registry, and validation

The production schemas are `observation_context_extraction_v2` and
`context_pair_attribution_v2`. They store concise audit summaries, not hidden
reasoning. The versioned registry composes `generic`, `biomedical`, `clinical`,
`chemistry`, `materials`, and `catalysis` profiles and declares factor type,
units, criticality, applicability, comparison/normalization policies, evidence
requirements, blocking/explanatory permissions, aliases, and prompt guidance.

Validation rejects mismatched IDs, unknown/cross-claim anchors, hash/offset/text
errors, unsupported factors, invalid quantities/units, unsafe equivalence,
abstract references to fulltext, unbound or locally unsupported explicit
values, Methods-only result claims, silent resolution of conflicting values,
and unaccepted normalized candidates. Unknown values cannot be canonicalized.
Canonical species/entity candidates still require acceptance by the existing
resolver.

The gate blocks validated non-comparable pairs only when the registry permits
the blocking factor. Insufficient or invalid results remain reviewable and
cannot become confirmed conflicts. Conditional comparisons can remain
candidates with their explanatory factors, but only if every pre-existing
formal gate also passes.

## Execution and migration

The CLI defaults to planning. `--execute` permits only cached or fixture work
unless `--api` is also explicit. Provider clients are configured with zero
automatic retries, and extraction/comparison hard bounds are separate.
Artifacts are written into a new output run; no Atlas activation or active
pointer operation exists in this CLI.

Planning has two explicit purposes. `smoke` uses deterministic stratified
greedy coverage and a stable pair-ID tie-break. It selects pairs before deriving
the exact unique observation endpoint closure; its hard bound is therefore the
sum of uncached selected endpoints and uncached selected comparisons, not a
fixed cap. Missing input-mode or experimental categories are recorded as
unavailable rather than fabricated. `complete` covers every valid candidate
pair and every referenced observation. If either call cap is insufficient it
sets `plan_status=blocked_by_call_bound` and cannot claim complete coverage.

Plan-only accepts the repository-supported `deepseek` and `openai` provider
names plus explicit models and thinking mode. It validates metadata without
constructing a client, reading credential values, testing the network, or
making a provider call. Real calls still require both `--execute` and `--api`.
The auditable smoke selection is written to
`context_attribution_smoke_selection.json`.

The legacy L4 files are not overwritten. New outputs include:

- `observation_context_extractions.jsonl`
- `context_pair_attributions.jsonl`
- `context_attribution_validation_audit.jsonl`
- `context_attribution_execution_ledger.jsonl`
- `context_attribution_retry_queue.jsonl`
- `context_comparability_gate.jsonl`
- `context_attribution_summary.json`
- `context_attribution_completeness_report.json`
- `context_attribution_legacy_comparison.json`

The comparison report records pair count, factor coverage, unknown rate,
comparability distribution, evidence-binding failures, provider calls, and
cache reuse. Migration should proceed from offline fixtures and plan-only to a
single HIF1A canary before any broader provider run.
