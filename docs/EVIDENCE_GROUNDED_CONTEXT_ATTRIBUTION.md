# Evidence-grounded context attribution v4

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

The production schemas are `observation_context_extraction_v4` and
`context_pair_attribution_v2`; the extraction reader can read v2/v3 payloads
for offline revalidation. A legacy locally-inferred payload without components
is never auto-split or upgraded into provenance: it remains
`legacy_local_inference_unverifiable` and is rejected. They store concise audit
summaries, not hidden reasoning. The versioned registry composes `generic`, `biomedical`, `clinical`,
`chemistry`, `materials`, and `catalysis` profiles and declares factor type,
units, criticality, applicability, comparison/normalization policies, evidence
requirements, blocking/explanatory permissions, aliases, and prompt guidance.

Registry files are immutable contracts, not mutable aliases. Historical
Prompt v1/v2 and extraction v2 resolve explicitly to
`configs/context_attribution/context_registry_v1.json`; Prompt v3/v4 and
extraction v3/v4 resolve to `context_registry_v2.json`. The resolver checks the
requested version, registered path, internal version and SHA-256 and never
searches for or falls back to a “latest” file. Plan, cache, provider audit,
offline revalidation, handoff and completeness artifacts carry the resolved
version/path/hash/schema/source identity. The restored v1 file is the Git
history payload with SHA-256
`db0acb543603d0d1ffe06d29e101cd61eed2582e69a845b7df1d3eb21c40f7b9`.

For `explicit`, `raw_value` is a continuous surface copied from one selected
authoritative span. Matching permits only NFKC, case folding, whitespace
collapse, and punctuation/Unicode-separator normalization. Word reordering,
abbreviation expansion, synonym substitution, inferred comparator/design, and
cell-line-to-species knowledge are not accepted. `normalized_value` is separate and survives only an identity,
configured controlled mapping, or explicitly supplied resolver acceptance.
Unresolved optional candidates move to `normalized_candidate`; resolver-required
factors fail closed. `evidence_anchor_ids` are selected from the observation
contract. Model-authored `evidence_text` is ignored: the deterministic hydrator
replaces it with the exact authoritative span and preserves its hash, offsets,
section, and role in `authoritative_evidence`.

Validation rejects mismatched IDs, unknown/cross-claim anchors, hash/offset/text
errors, unsupported factors, invalid quantities/units, unsafe equivalence,
abstract references to fulltext, unbound or locally unsupported explicit
values, Methods-only result claims, silent resolution of conflicting values,
and unaccepted normalized candidates. Unknown values cannot be canonicalized.
Canonical species/entity candidates still require acceptance by the existing
resolver.

`inferred_from_local_chain` is distinct from `explicit`. Provider `raw_value`
must be null. Each `raw_components` item contains `chain_node_id`,
`field_path`, one strict `surface`, and `evidence_anchor_ids`. Every component
is checked independently against a non-null field and anchors owned by its
node. Node/field order and legal combinations come from immutable
`context_local_chain_composition_v2`; the provider cannot submit the
authoritative composed result.

The deterministic composer
`context_attribution_deterministic_composer_v1` creates `composed_value`,
`composition_rule`, and `composition_provenance`. Provenance records the
resolved field path/value plus authoritative anchor text, hash, offsets,
section, and role. Components from different intervention records cannot be
silently combined. Comparator composition accepts only `control`, `vehicle`,
`untreated`, `mock`, or `non-targeting siRNA` copied from the
`comparator_or_control.control_arm_raw` field. An intervention node cannot
prove a comparator. No cell-line-to-species composition rule exists, so A549
alone leaves species unknown.

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

Successful future provider calls are atomically recorded in
`context_attribution_provider_calls.jsonl`, separate from validated scientific
artifacts. Each row contains the request identity, complete prompt snapshot,
redacted raw body, parsed payload, finish reason, usage, HTTP status and
validation result, but never Authorization or API keys. Resume revalidates a
complete provider row instead of repeating that provider call.

Ledger terminal states distinguish `validated`, `rejected_schema`,
`rejected_validation`, and `failed_provider`. A comparison whose extraction
dependency is rejected becomes `blocked_dependency_validation`, not `pending`;
resume reopens it only after both dependency extractions validate.
`execution_status` describes engine/transport completion, while
`scientific_status` describes validation completeness. The legacy `status`
field mirrors `execution_status` only.

Scientific status has fixed precedence: interrupted, pending, bounded or
inconsistent work is `incomplete`; zero valid selected extractions with
rejections is `all_extractions_rejected`; mixed valid/rejected or
dependency-blocked work is `partial_validation_failure`; valid extractions but
no selected pair attribution is `no_pairs_attributed`; fully validated complete
coverage is `validated_complete`; and a fully validated selected smoke scope is
`validated_partial`. Publication readiness requires `validated_complete`.
Handoff rows require an actually validated pair; `status=completed` alone never
opens the gate. Atlas activation remains a separate explicit operation and is
always false here.

`--offline-revalidate-from SOURCE_RUN` reads only previously parsed extraction
payloads. It records the source run/payload and old/new validator versions,
performs zero provider/network calls, records whether original raw response,
finish reason and usage are actually available, writes no cache or handoff,
and never activates Atlas. Missing source registry hashes remain explicitly
unknown (`source_registry_hash_known=false`) rather than being reconstructed
from the current file.

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
- `context_attribution_provider_calls.jsonl`
- `context_attribution_offline_revalidation_payloads.jsonl` (offline replay only)
- `context_attribution_retry_queue.jsonl`
- `context_comparability_gate.jsonl`
- `context_attribution_summary.json`
- `context_attribution_completeness_report.json`
- `context_attribution_legacy_comparison.json`

The comparison report records pair count, factor coverage, unknown rate,
comparability distribution, evidence-binding failures, provider calls, and
cache reuse. Migration should proceed from offline fixtures and plan-only to a
single HIF1A canary before any broader provider run.
